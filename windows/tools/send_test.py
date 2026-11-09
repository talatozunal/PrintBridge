#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""M1 uçtan uca test istemcisi (curl yerine).

Örnek:
    py -3 tools\\send_test.py --pin 123456 --text "Merhaba PrintBridge"
    py -3 tools\\send_test.py --pin 123456 --file foto.jpg --copies 2
    py -3 tools\\send_test.py --token pb_xxx --file belge.pdf --paper A4
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

BASE = "http://127.0.0.1:8477/api/v1"


def request_json(method: str, url: str, payload: dict | None = None, token: str | None = None) -> dict:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP {exc.code}: {body}", file=sys.stderr)
        raise SystemExit(2) from exc


def upload(url: str, token: str, filename: str, content: bytes, options: dict, idem: str) -> dict:
    boundary = "----printbridge" + uuid.uuid4().hex
    ctype = mimetypes.guess_type(filename)[0] or "application/octet-stream"

    parts: list[bytes] = []
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="options"\r\n\r\n'
        f"{json.dumps(options, ensure_ascii=False)}\r\n".encode("utf-8")
    )
    parts.append(
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {ctype}\r\n\r\n".encode("utf-8")
    )
    parts.append(content)
    parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(parts)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Idempotency-Key": idem,
        "Content-Length": str(len(body)),
    }
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}", file=sys.stderr)
        raise SystemExit(2) from exc


def main(argv: list[str]) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="PrintBridge M1 test istemcisi")
    parser.add_argument("--host", default="127.0.0.1", help="Ajan adresi")
    parser.add_argument("--port", type=int, default=8477)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", type=Path, help="Gönderilecek dosya")
    group.add_argument("--text", help="Düz metin gönder (test için)")
    auth = parser.add_mutually_exclusive_group()
    auth.add_argument("--pin", help="PC ekranındaki 6 haneli PIN")
    auth.add_argument("--token", help="Önceden alınmış cihaz token'ı")
    parser.add_argument("--copies", type=int, default=1)
    parser.add_argument("--paper", default="A4")
    parser.add_argument("--fit", default="fit", choices=["fit", "fill"])
    parser.add_argument("--orientation", default="auto", choices=["auto", "portrait", "landscape"])
    parser.add_argument("--page-range", default=None)
    parser.add_argument("--no-wait", action="store_true", help="İş durumunu beklemeden çık")
    args = parser.parse_args(argv)

    base = f"http://{args.host}:{args.port}/api/v1"

    health = request_json("GET", f"{base}/health")
    print(f"Ajan: {health['name']} v{health['version']} · yazıcı hazır: {health['printerReady']}")

    token = args.token
    if not token:
        if not args.pin:
            raise SystemExit("--pin veya --token gerekli.")
        paired = request_json(
            "POST",
            f"{base}/pair",
            {"pin": args.pin, "deviceName": "send_test", "deviceId": "send-test"},
        )
        token = paired["token"]
        print(f"Eşleşti: {paired['agentName']} · token {token[:12]}…")
        for printer in paired["printers"]:
            print(f"  yazıcı: {printer['name']} [{printer['status']}] kâğıtlar: {', '.join(printer['papers'][:6])}")

    if args.text is not None:
        filename = "test.txt"
        content = args.text.encode("utf-8")
    else:
        if not args.file.exists():
            raise SystemExit(f"Dosya yok: {args.file}")
        filename = args.file.name
        content = args.file.read_bytes()

    options = {
        "copies": args.copies,
        "paper": args.paper,
        "orientation": args.orientation,
        "fit": args.fit,
        "pageRange": args.page_range,
        "jobName": f"PrintBridge test — {filename}",
    }
    job = upload(f"{base}/jobs", token, filename, content, options, uuid.uuid4().hex)
    print(f"İş gönderildi: {job['id']} ({len(content)} bayt)")

    if args.no_wait:
        return 0

    deadline = time.time() + 90
    last_status = None
    while time.time() < deadline:
        state = request_json("GET", f"{base}/jobs/{job['id']}", token=token)
        if state["status"] != last_status:
            print(f"  durum: {state['status']}  ({state['printedPages']}/{state['pages']} sayfa)")
            last_status = state["status"]
        if state["status"] in ("done", "failed", "canceled"):
            if state.get("error"):
                print(f"  HATA: {state['error']['code']} — {state['error']['message']}")
            return 0 if state["status"] == "done" else 1
        time.sleep(0.4)

    print("Zaman aşımı; iş hâlâ sürüyor.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

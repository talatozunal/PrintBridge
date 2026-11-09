# -*- coding: utf-8 -*-
"""Uçtan uca HTTP testleri (sahte yazıcı arka ucu ile)."""

from __future__ import annotations

import io
import json
import time

from PIL import Image

from agent.tests.conftest import wait_for


def jpeg_bytes(size=(800, 600), color=(180, 40, 40)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def test_health_is_public(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["name"]
    assert body["printerReady"] is True
    assert body["paired"] is False


def test_unauthorized_without_token(client):
    response = client.get("/api/v1/jobs")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_pairing_with_wrong_pin(client, app):
    pin = app.state.pairing.refresh()
    wrong = "000000" if pin != "000000" else "111111"
    response = client.post("/api/v1/pair", json={"pin": wrong, "deviceName": "x"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_pin"


def test_pairing_success_and_printers(client, token, auth):
    response = client.get("/api/v1/printers", headers=auth)
    assert response.status_code == 200
    printers = response.json()["printers"]
    assert printers[0]["id"] == "Fake Printer"
    assert printers[0]["status"] == "ready"
    assert "A4" in printers[0]["papers"]


def test_print_image_job(client, auth, backend):
    response = client.post(
        "/api/v1/jobs",
        headers=auth,
        files={"file": ("foto.jpg", jpeg_bytes(), "image/jpeg")},
        data={"options": json.dumps({"paper": "A4", "fit": "fit", "jobName": "Test foto"})},
    )
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "queued"

    job = wait_for(client, body["id"], auth)
    assert job["status"] == "done", job
    assert job["printedPages"] == 1
    assert job["pages"] == 1
    assert job["progress"] == 1.0

    call = backend.calls[-1]
    assert call["printer"] == "Fake Printer"
    assert call["options"]["paper"] == "A4"
    assert call["options"]["orientation"] == "landscape"  # 800x600 görsel
    assert call["title"] == "Test foto"


def test_print_text_with_copies(client, auth, backend):
    text = "\n".join(f"Satır {i} — şğüİ" for i in range(20))
    response = client.post(
        "/api/v1/jobs",
        headers=auth,
        files={"file": ("not.txt", text.encode("utf-8"), "text/plain")},
        data={"options": json.dumps({"copies": 2, "pageRange": "1"})},
    )
    assert response.status_code == 202, response.text

    job = wait_for(client, response.json()["id"], auth)
    assert job["status"] == "done", job
    # 1 sayfa × 2 kopya
    assert job["printedPages"] == 2


def test_idempotency_key_prevents_duplicate(client, auth, backend):
    payload = {
        "files": {"file": ("foto.jpg", jpeg_bytes(), "image/jpeg")},
        "data": {"options": "{}"},
        "headers": {**auth, "Idempotency-Key": "anahtar-1"},
    }
    first = client.post("/api/v1/jobs", **payload)
    second = client.post("/api/v1/jobs", **payload)
    assert first.status_code == 202 and second.status_code == 202
    assert first.json()["id"] == second.json()["id"]

    wait_for(client, first.json()["id"], auth)
    time.sleep(0.2)
    assert len(backend.calls) == 1


def test_unsupported_file_type(client, auth):
    response = client.post(
        "/api/v1/jobs",
        headers=auth,
        files={"file": ("virus.exe", b"MZ\x90\x00\x00", "application/octet-stream")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_type"


def test_file_too_large(client, auth):
    big = b"a" * (2 * 1024 * 1024 + 1024)
    response = client.post(
        "/api/v1/jobs",
        headers=auth,
        files={"file": ("buyuk.txt", big, "text/plain")},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "too_large"


def test_invalid_options(client, auth):
    response = client.post(
        "/api/v1/jobs",
        headers=auth,
        files={"file": ("a.txt", b"merhaba", "text/plain")},
        data={"options": json.dumps({"copies": 0})},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_options"


def test_queue_busy(client, auth, app):
    app.state.config.max_queue = 0
    response = client.post(
        "/api/v1/jobs",
        headers=auth,
        files={"file": ("a.txt", b"merhaba", "text/plain")},
    )
    assert response.status_code == 423
    assert response.json()["error"]["code"] == "busy"


def test_cancel_job(client, auth, backend):
    backend.delay = 0.15
    text = "\n".join(f"Satır {i}" for i in range(160))
    response = client.post(
        "/api/v1/jobs",
        headers=auth,
        files={"file": ("uzun.txt", text.encode("utf-8"), "text/plain")},
    )
    assert response.status_code == 202
    job_id = response.json()["id"]

    time.sleep(0.2)
    cancel = client.delete(f"/api/v1/jobs/{job_id}", headers=auth)
    assert cancel.status_code == 202

    job = wait_for(client, job_id, auth)
    assert job["status"] in ("canceled", "done")
    if job["status"] == "canceled":
        assert job["printedPages"] < job["pages"] or job["pages"] == 0


def test_retry_after_failure(client, auth, backend):
    backend.fail_next = True
    response = client.post(
        "/api/v1/jobs",
        headers=auth,
        files={"file": ("a.txt", b"merhaba dunya", "text/plain")},
    )
    assert response.status_code == 202
    failed = wait_for(client, response.json()["id"], auth)
    assert failed["status"] == "failed"
    assert failed["error"]["code"] == "spool_failed"

    retry = client.post(f"/api/v1/jobs/{failed['id']}/retry", headers=auth)
    assert retry.status_code == 202
    retried = wait_for(client, retry.json()["id"], auth)
    assert retried["status"] == "done"


def test_devices_list_and_revoke(client, auth):
    devices = client.get("/api/v1/devices", headers=auth).json()["devices"]
    assert any(d["name"] == "pytest" for d in devices)

    device_id = devices[0]["id"]
    assert client.delete(f"/api/v1/devices/{device_id}", headers=auth).status_code == 202
    # Token artık geçersiz
    assert client.get("/api/v1/jobs", headers=auth).status_code == 401


def test_token_as_query_param(client, token):
    response = client.get(f"/api/v1/jobs?token={token}")
    assert response.status_code == 200


def test_job_preview_png(client, auth):
    response = client.post(
        "/api/v1/jobs",
        headers=auth,
        files={"file": ("onizleme.jpg", jpeg_bytes((1024, 768)), "image/jpeg")},
    )
    assert response.status_code == 202, response.text
    job = wait_for(client, response.json()["id"], auth)
    assert job["status"] == "done", job

    preview = client.get(f"/api/v1/jobs/{job['id']}/preview.png", headers=auth)
    assert preview.status_code == 200, preview.text
    assert preview.headers["content-type"] == "image/png"
    assert preview.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(preview.content) > 1000

    # Görsel tek sayfa: 2. sayfa yok.
    missing = client.get(f"/api/v1/jobs/{job['id']}/preview.png?page=2", headers=auth)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"


def test_missing_printer_falls_back_to_windows_default(client, auth, backend, app):
    # Kayıtlı yazıcı adı değişmiş/çıkarılmış olsa bile Windows varsayılanına düşülür.
    app.state.config.default_printer = "Eski Yazıcı"
    response = client.post(
        "/api/v1/jobs",
        headers=auth,
        files={"file": ("belge.txt", b"yazici degisti", "text/plain")},
    )
    assert response.status_code == 202
    job = wait_for(client, response.json()["id"], auth)
    assert job["status"] == "done", job
    assert backend.calls[-1]["printer"] == "Fake Printer"


def test_job_preview_requires_auth(client, auth):
    response = client.post(
        "/api/v1/jobs",
        headers=auth,
        files={"file": ("a.txt", b"merhaba", "text/plain")},
    )
    assert response.status_code == 202
    job = wait_for(client, response.json()["id"], auth)

    preview = client.get(f"/api/v1/jobs/{job['id']}/preview.png")
    assert preview.status_code == 401
    assert preview.json()["error"]["code"] == "unauthorized"

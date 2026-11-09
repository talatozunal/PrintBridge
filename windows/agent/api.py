# -*- coding: utf-8 -*-
"""HTTP API (docs/PROTOCOL.md).

Uçlar:
    GET    /api/v1/health
    POST   /api/v1/pair
    GET    /api/v1/printers
    POST   /api/v1/jobs            (multipart)
    GET    /api/v1/jobs
    GET    /api/v1/jobs/{id}
    DELETE /api/v1/jobs/{id}
    POST   /api/v1/jobs/{id}/retry
    GET    /api/v1/jobs/{id}/preview.png
    GET    /api/v1/devices
    DELETE /api/v1/devices/{id}
"""

from __future__ import annotations

import ipaddress
import json
import logging
import re
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Form, Header, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from . import __version__
from .config import Config
from .errors import (
    AppError,
    Busy,
    Conflict,
    InvalidOptions,
    NotFound,
    TooLarge,
    Unauthorized,
    UnsupportedType,
)
from .jobs import JobStore, PrintWorker, new_job_id
from .printer import Geometry, WindowsBackend
from .render import RenderOptions, auto_orientation, detect_kind, iter_pages
from .security import PairingPin, TokenStore

log = logging.getLogger("printbridge.api")

OPTION_SETS = {
    "orientation": {"auto", "portrait", "landscape"},
    "fit": {"fit", "fill"},
}
PAGE_RANGE_RE = re.compile(r"^[0-9,\-\s]{1,64}$")
ALLOWED_SUFFIXES = {
    ".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff", ".webp", ".heic", ".heif",
    ".pdf", ".txt", ".text", ".md", ".log", ".csv", "",
}


class PairRequest(BaseModel):
    pin: str
    deviceName: str | None = None
    deviceId: str | None = None


def _error_payload(exc: AppError) -> dict[str, Any]:
    error: dict[str, Any] = {"code": exc.code, "message": exc.message}
    if exc.detail:
        error["detail"] = exc.detail
    return {"error": error}


def _is_private_host(host: str | None) -> bool:
    if not host:
        return False
    if host in ("localhost", "testclient"):
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_loopback or address.is_private or address.is_link_local


def _normalize_options(raw: dict[str, Any], printer_ids: list[str], fallback_name: str) -> dict[str, Any]:
    try:
        copies_value = raw.get("copies", 1)
        copies = 1 if copies_value is None or copies_value == "" else int(copies_value)
    except (TypeError, ValueError) as exc:
        raise InvalidOptions("Kopya sayısı sayı olmalı.") from exc
    if not 1 <= copies <= 99:
        raise InvalidOptions("Kopya sayısı 1–99 arasında olmalı.")

    paper = str(raw.get("paper", "A4") or "A4").strip()
    if len(paper) > 32:
        raise InvalidOptions("Kâğıt adı çok uzun.")

    orientation = str(raw.get("orientation", "auto") or "auto").lower()
    if orientation not in OPTION_SETS["orientation"]:
        raise InvalidOptions("Yön 'auto', 'portrait' veya 'landscape' olmalı.")

    fit = str(raw.get("fit", "fit") or "fit").lower()
    if fit not in OPTION_SETS["fit"]:
        raise InvalidOptions("Yerleştirme 'fit' veya 'fill' olmalı.")

    page_range = raw.get("pageRange")
    if page_range is not None:
        page_range = str(page_range).strip()
        if page_range and not PAGE_RANGE_RE.fullmatch(page_range):
            raise InvalidOptions("Sayfa aralığı biçimi '1-3,5' gibi olmalı.")

    printer = raw.get("printer")
    if printer:
        printer = str(printer)
        if printer_ids and printer not in printer_ids:
            raise InvalidOptions(f"Yazıcı bulunamadı: {printer}")

    job_name = str(raw.get("jobName") or fallback_name).strip()[:120] or fallback_name

    return {
        "printer": printer,
        "copies": copies,
        "paper": paper,
        "orientation": orientation,
        "fit": fit,
        "pageRange": page_range or None,
        "jobName": job_name,
    }


def create_app(
    config: Config | None = None,
    backend=None,
    allow_any_client: bool = False,
) -> FastAPI:
    cfg = config or Config.load()
    store = JobStore(cfg.db_path)
    stale = store.fail_stale()
    if stale:
        log.warning("%d yarım kalmış iş 'failed' olarak işaretlendi", stale)

    tokens = TokenStore(cfg)
    pairing = PairingPin(cfg.pin_ttl_seconds, cfg.pin_max_attempts)
    backend = backend or WindowsBackend()
    worker = PrintWorker(store, backend, cfg)
    max_bytes = cfg.max_mb * 1024 * 1024

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        worker.start()
        try:
            yield
        finally:
            worker.stop()
            worker.join(timeout=10)

    app = FastAPI(
        title="PrintBridge Agent",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if allow_any_client else None,
        redoc_url=None,
    )
    app.state.config = cfg
    app.state.store = store
    app.state.tokens = tokens
    app.state.pairing = pairing
    app.state.backend = backend
    app.state.worker = worker
    app.state.allow_any_client = allow_any_client

    # --- hata biçimi ------------------------------------------------------

    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError):
        return JSONResponse(status_code=exc.http_status, content=_error_payload(exc))

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "invalid_options",
                    "message": "İstek biçimi geçersiz.",
                    "detail": str(exc.errors()[:3]),
                }
            },
        )

    # --- ağ sınırı --------------------------------------------------------

    @app.middleware("http")
    async def private_network_only(request: Request, call_next):
        if not app.state.allow_any_client and not _is_private_host(
            request.client.host if request.client else None
        ):
            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "code": "forbidden",
                        "message": "Yalnızca yerel ağdan erişilebilir.",
                    }
                },
            )
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > max_bytes + 1024 * 1024:
            return JSONResponse(
                status_code=413,
                content={
                    "error": {
                        "code": "too_large",
                        "message": f"Dosya {cfg.max_mb} MB sınırını aşıyor.",
                    }
                },
            )
        return await call_next(request)

    # --- kimlik -----------------------------------------------------------

    def require_token(request: Request) -> dict:
        header = request.headers.get("authorization", "")
        raw = header[7:].strip() if header.lower().startswith("bearer ") else None
        if not raw:
            raw = request.query_params.get("token")
        record = tokens.verify(raw)
        if record is None:
            raise Unauthorized()
        return record

    def require_token_or_local(request: Request) -> dict:
        """Tepsi uygulamasındaki önizleme gibi yerel tarayıcı istekleri için."""
        host = request.client.host if request.client else None
        if host in ("127.0.0.1", "::1"):
            return {"id": "local", "name": "local"}
        return require_token(request)

    def known_printers() -> list:
        try:
            return backend.list_printers()
        except Exception as exc:  # noqa: BLE001
            log.warning("Yazıcılar listelenemedi: %s", exc)
            return []

    # --- uçlar ------------------------------------------------------------

    @app.get("/")
    async def root():
        return {"name": "PrintBridge Agent", "version": __version__, "api": "/api/v1"}

    @app.get("/api/v1/health")
    async def health():
        printers = known_printers()
        ready = any(p.status == "ready" for p in printers)
        return {
            "name": cfg.agent_name,
            "agentId": cfg.agent_id,
            "version": __version__,
            "paired": bool(cfg.tokens),
            "printerReady": ready,
            "printers": len(printers),
            "port": cfg.port,
        }

    @app.post("/api/v1/pair")
    async def pair(body: PairRequest):
        pairing.verify(body.pin)
        token = tokens.create(body.deviceName or "iOS", body.deviceId)
        printers = [p.to_dict() for p in known_printers()]
        return {
            "token": token,
            "agentName": cfg.agent_name,
            "agentId": cfg.agent_id,
            "version": __version__,
            "printers": printers,
        }

    @app.get("/api/v1/printers")
    async def list_printers(_device: dict = Depends(require_token)):
        printers = [p.to_dict() for p in known_printers()]
        if cfg.default_printer:
            for printer in printers:
                if printer["id"] == cfg.default_printer:
                    printer["default"] = True
        return {"printers": printers}

    @app.post("/api/v1/jobs", status_code=202)
    async def create_job(
        request: Request,
        file: UploadFile = File(...),
        options: str = Form("{}"),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        _device: dict = Depends(require_token),
    ):
        if store.queue_depth() >= cfg.max_queue:
            raise Busy(f"Kuyrukta {cfg.max_queue} iş var; biraz sonra deneyin.")

        if idempotency_key:
            if len(idempotency_key) > 128:
                raise InvalidOptions("Idempotency-Key çok uzun.")
            existing = store.by_idempotency(idempotency_key)
            if existing is not None:
                return JSONResponse(
                    status_code=202,
                    content={
                        "id": existing.id,
                        "status": existing.status,
                        "statusUrl": f"/api/v1/jobs/{existing.id}",
                    },
                )

        try:
            raw_options = json.loads(options) if options else {}
        except json.JSONDecodeError as exc:
            raise InvalidOptions("options alanı geçerli JSON değil.") from exc
        if not isinstance(raw_options, dict):
            raise InvalidOptions("options bir JSON nesnesi olmalı.")

        printers = known_printers()
        printer_ids = [p.id for p in printers]
        normalized = _normalize_options(
            raw_options, printer_ids, Path(file.filename or "belge").stem
        )

        job_id = new_job_id()
        suffix = Path(file.filename or "").suffix.lower()
        suffix = suffix if suffix in ALLOWED_SUFFIXES else ""
        destination = cfg.spool_dir / f"{job_id}{suffix}"

        size = 0
        head = b""
        try:
            with destination.open("wb") as handle:
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    if not head:
                        head = chunk[:4096]
                    size += len(chunk)
                    if size > max_bytes:
                        raise TooLarge(f"Dosya {cfg.max_mb} MB sınırını aşıyor.")
                    handle.write(chunk)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        finally:
            await file.close()

        if size == 0:
            destination.unlink(missing_ok=True)
            raise UnsupportedType("Boş dosya gönderildi.")

        kind = detect_kind(file.filename or "", head)
        if kind == "unknown":
            destination.unlink(missing_ok=True)
            raise UnsupportedType()

        job = store.create(
            job_id=job_id,
            job_name=normalized["jobName"],
            filename=file.filename or destination.name,
            kind=kind,
            content_type=file.content_type,
            options=normalized,
            file_path=str(destination),
            idempotency_key=idempotency_key,
        )
        worker.wake()
        log.info("Yeni iş: %s · %s · %.1f KB · %s", job.id, kind, size / 1024, normalized["jobName"])
        return {
            "id": job.id,
            "status": job.status,
            "statusUrl": f"/api/v1/jobs/{job.id}",
        }

    @app.get("/api/v1/jobs")
    async def list_jobs(
        limit: int = Query(default=20, ge=1, le=100),
        before: str | None = None,
        _device: dict = Depends(require_token),
    ):
        jobs = store.list(limit=limit, before=before)
        return {
            "jobs": [job.to_dict() for job in jobs],
            "next": jobs[-1].id if len(jobs) == limit else None,
        }

    @app.get("/api/v1/jobs/{job_id}")
    async def get_job(job_id: str, _device: dict = Depends(require_token)):
        return store.require(job_id).to_dict()

    @app.delete("/api/v1/jobs/{job_id}", status_code=202)
    async def cancel_job(job_id: str, _device: dict = Depends(require_token)):
        job = store.require(job_id)
        if job.status not in ("queued", "rendering", "printing"):
            raise Conflict("Yalnızca bekleyen veya basılmakta olan iş iptal edilebilir.")
        store.update(job_id, status="canceled")
        log.info("İş iptal istendi: %s", job_id)
        return {"id": job_id, "status": "canceled"}

    @app.post("/api/v1/jobs/{job_id}/retry", status_code=202)
    async def retry_job(job_id: str, _device: dict = Depends(require_token)):
        job = store.retry(job_id)
        worker.wake()
        return {
            "id": job.id,
            "status": job.status,
            "statusUrl": f"/api/v1/jobs/{job.id}",
        }

    @app.get("/api/v1/jobs/{job_id}/preview.png")
    async def job_preview(
        job_id: str,
        page: int = Query(default=1, ge=1, le=100),
        _device: dict = Depends(require_token_or_local),
    ):
        job = store.require(job_id)
        if not job.file_path or not Path(job.file_path).exists():
            raise NotFound("Önizleme için dosya bulunamadı.")

        options = dict(job.options or {})
        printer_name = options.get("printer") or cfg.default_printer
        if not printer_name:
            default = backend.default_printer()
            printer_name = default.id if default else None
        if not printer_name:
            raise NotFound("Önizleme için yazıcı yok.")

        if options.get("orientation", "auto") == "auto" and job.kind == "image":
            options["orientation"] = auto_orientation(Path(job.file_path))

        if job.kind == "image" and page > 1:
            raise NotFound("Görsel tek sayfadır.")

        render_options = RenderOptions(
            fit=options.get("fit", "fit"),
            page_range=str(page),
            max_pages=cfg.max_pages,
            render_dpi=150,
        )

        def _render() -> bytes:
            try:
                geometry = backend.preview_geometry(printer_name, options, cfg.margin_mm)
            except Exception:  # yazıcı kapalıysa A4 varsayımıyla önizle
                geometry = Geometry(4760, 6814, 600, 600, cfg.margin_mm)
            try:
                pages = iter_pages(Path(job.file_path), job.kind, geometry, render_options)
                first = next(iter(pages), None)
            except AppError:
                raise
            except Exception as exc:  # noqa: BLE001
                raise RenderFailed("Önizleme oluşturulamadı.", detail=str(exc)) from exc
            if first is None:
                raise NotFound("İstenen sayfa yok.")
            buffer = BytesIO()
            first.save(buffer, format="PNG")
            return buffer.getvalue()

        data = await run_in_threadpool(_render)
        return Response(content=data, media_type="image/png", headers={"Cache-Control": "no-store"})

    @app.get("/api/v1/devices")
    async def list_devices(_device: dict = Depends(require_token)):
        return {
            "devices": [
                {"id": d.id, "name": d.name, "createdAt": d.created_at}
                for d in tokens.list_devices()
            ]
        }

    @app.delete("/api/v1/devices/{device_id}", status_code=202)
    async def revoke_device(device_id: str, _device: dict = Depends(require_token)):
        if not tokens.revoke(device_id):
            raise NotFound("Cihaz bulunamadı.")
        return {"id": device_id, "revoked": True}

    return app

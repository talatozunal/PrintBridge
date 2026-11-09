# -*- coding: utf-8 -*-
"""İş modeli, SQLite deposu ve tek işçilik yazdırma kuyruğu.

Tek fiziksel yazıcı olduğu için işler sırayla basılır. Durumlar:
    queued → rendering → printing → done | failed | canceled
"""

from __future__ import annotations

import json
import logging
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import render
from .config import Config
from .errors import AppError, Conflict, JobCanceled, NotFound
from .printer import Geometry

log = logging.getLogger("printbridge.jobs")

ACTIVE_STATES = ("queued", "rendering", "printing")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_job_id() -> str:
    # Sıralanabilir + tahmin edilemez: zaman damgası (ms) + rastgele.
    return f"job_{int(time.time() * 1000):013d}{secrets.token_hex(3)}"


@dataclass
class Job:
    id: str
    status: str
    job_name: str
    filename: str
    kind: str
    options: dict[str, Any]
    pages: int = 0
    printed_pages: int = 0
    error_code: str | None = None
    error_message: str | None = None
    file_path: str | None = None
    content_type: str | None = None
    created_at: str = ""
    started_at: str | None = None
    finished_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        progress = 0.0
        if self.status == "done":
            progress = 1.0
        elif self.pages > 0:
            progress = min(1.0, self.printed_pages / self.pages)
        elif self.status in ("rendering", "printing"):
            progress = 0.0

        payload: dict[str, Any] = {
            "id": self.id,
            "status": self.status,
            "progress": round(progress, 3),
            "pages": self.pages,
            "printedPages": self.printed_pages,
            "createdAt": self.created_at,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
            "jobName": self.job_name,
            "filename": self.filename,
            "kind": self.kind,
            "error": None,
        }
        if self.error_code or self.error_message:
            payload["error"] = {
                "code": self.error_code or "spool_failed",
                "message": self.error_message or "Yazdırma başarısız.",
            }
        return payload


SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id              TEXT PRIMARY KEY,
    status          TEXT NOT NULL,
    job_name        TEXT NOT NULL,
    filename        TEXT NOT NULL,
    kind            TEXT NOT NULL,
    content_type    TEXT,
    options         TEXT NOT NULL DEFAULT '{}',
    pages           INTEGER NOT NULL DEFAULT 0,
    printed_pages   INTEGER NOT NULL DEFAULT 0,
    error_code      TEXT,
    error_message   TEXT,
    file_path       TEXT,
    idempotency_key TEXT UNIQUE,
    created_at      TEXT NOT NULL,
    started_at      TEXT,
    finished_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status, created_at);
"""


class JobStore:
    def __init__(self, db_path: Path):
        self._path = Path(db_path)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    # --- dönüşüm ----------------------------------------------------------

    @staticmethod
    def _to_job(row: sqlite3.Row) -> Job:
        return Job(
            id=row["id"],
            status=row["status"],
            job_name=row["job_name"],
            filename=row["filename"],
            kind=row["kind"],
            options=json.loads(row["options"] or "{}"),
            pages=row["pages"],
            printed_pages=row["printed_pages"],
            error_code=row["error_code"],
            error_message=row["error_message"],
            file_path=row["file_path"],
            content_type=row["content_type"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
        )

    # --- yazma ------------------------------------------------------------

    def create(
        self,
        *,
        job_id: str,
        job_name: str,
        filename: str,
        kind: str,
        content_type: str | None,
        options: dict[str, Any],
        file_path: str,
        idempotency_key: str | None = None,
    ) -> Job:
        created = now_iso()
        with self._lock:
            self._conn.execute(
                """INSERT INTO jobs (id, status, job_name, filename, kind, content_type,
                                     options, file_path, idempotency_key, created_at)
                   VALUES (?, 'queued', ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    job_id,
                    job_name,
                    filename,
                    kind,
                    content_type,
                    json.dumps(options, ensure_ascii=False),
                    file_path,
                    idempotency_key,
                    created,
                ),
            )
            self._conn.commit()
            row = self._conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return self._to_job(row)

    def update(self, job_id: str, **fields: Any) -> None:
        allowed = {
            "status",
            "pages",
            "printed_pages",
            "error_code",
            "error_message",
            "started_at",
            "finished_at",
            "file_path",
            "job_name",
        }
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return
        assignments = ", ".join(f"{key} = ?" for key in updates)
        with self._lock:
            self._conn.execute(
                f"UPDATE jobs SET {assignments} WHERE id = ?",
                (*updates.values(), job_id),
            )
            self._conn.commit()

    def fail_stale(self) -> int:
        """Ajan çökmüşse yarım kalan işleri başarısız işaretle."""
        with self._lock:
            cursor = self._conn.execute(
                """UPDATE jobs
                      SET status = 'failed',
                          error_code = 'agent_restarted',
                          error_message = 'Ajan yeniden başladı; iş tamamlanmadı.',
                          finished_at = ?
                    WHERE status IN ('rendering', 'printing')""",
                (now_iso(),),
            )
            self._conn.commit()
            return cursor.rowcount

    # --- okuma ------------------------------------------------------------

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return self._to_job(row) if row else None

    def require(self, job_id: str) -> Job:
        job = self.get(job_id)
        if job is None:
            raise NotFound()
        return job

    def list(self, limit: int = 20, before: str | None = None) -> list[Job]:
        with self._lock:
            if before:
                row = self._conn.execute(
                    "SELECT created_at FROM jobs WHERE id = ?", (before,)
                ).fetchone()
                if row:
                    rows = self._conn.execute(
                        "SELECT * FROM jobs WHERE created_at < ? ORDER BY created_at DESC LIMIT ?",
                        (row["created_at"], limit),
                    ).fetchall()
                else:
                    rows = []
            else:
                rows = self._conn.execute(
                    "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
                ).fetchall()
        return [self._to_job(r) for r in rows]

    def next_queued(self) -> Job | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM jobs WHERE status = 'queued' ORDER BY created_at ASC, id ASC LIMIT 1"
            ).fetchone()
        return self._to_job(row) if row else None

    def queue_depth(self) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM jobs WHERE status IN ('queued', 'rendering', 'printing')"
            ).fetchone()
        return int(row["n"])

    def by_idempotency(self, key: str) -> Job | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM jobs WHERE idempotency_key = ?", (key,)
            ).fetchone()
        return self._to_job(row) if row else None

    def active_with_file(self, path: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT 1 FROM jobs WHERE file_path = ? AND status IN ('queued','rendering','printing') LIMIT 1",
                (path,),
            ).fetchone()
        return row is not None

    def retry(self, job_id: str) -> Job:
        original = self.require(job_id)
        if original.status not in ("failed", "canceled"):
            raise Conflict("Yalnızca başarısız veya iptal edilmiş işler yeniden denenebilir.")
        if not original.file_path or not Path(original.file_path).exists():
            raise Conflict("İşin dosyası artık yok; yeniden göndermeniz gerekiyor.")

        new_id = new_job_id()
        return self.create(
            job_id=new_id,
            job_name=original.job_name,
            filename=original.filename,
            kind=original.kind,
            content_type=original.content_type,
            options=original.options,
            file_path=original.file_path,
            idempotency_key=None,
        )


class PrintWorker(threading.Thread):
    def __init__(self, store: JobStore, backend, config: Config):
        super().__init__(name="print-worker", daemon=True)
        self._store = store
        self._backend = backend
        self._config = config
        self._stop_event = threading.Event()
        self._wake = threading.Event()
        self._last_cleanup = 0.0

    # --- dış arayüz -------------------------------------------------------

    def wake(self) -> None:
        self._wake.set()

    def stop(self) -> None:
        self._stop_event.set()
        self._wake.set()

    # --- döngü ------------------------------------------------------------

    def run(self) -> None:
        log.info("Yazdırma işçisi başladı")
        while not self._stop_event.is_set():
            try:
                job = self._store.next_queued()
            except Exception:  # noqa: BLE001
                log.exception("Kuyruk okunamadı")
                job = None

            if job is None:
                self._wake.wait(0.5)
                self._wake.clear()
                self._maybe_cleanup()
                continue

            self._process(job)

        log.info("Yazdırma işçisi durdu")

    # --- tek iş -----------------------------------------------------------

    def _process(self, job: Job) -> None:
        log.info("İş alındı: %s (%s, %s)", job.id, job.kind, job.filename)
        self._store.update(job.id, status="rendering", started_at=now_iso())

        options = dict(job.options or {})
        printer_name = self._resolve_printer(options)
        if not printer_name:
            self._fail(job, "printer_not_found", "Kullanılabilir yazıcı yok.")
            return

        # Görselde "auto" yönü, görselin en-boy oranına göre seç.
        if options.get("orientation", "auto") == "auto" and job.kind == "image":
            options["orientation"] = render.auto_orientation(Path(job.file_path or ""))

        render_options = render.RenderOptions(
            fit=options.get("fit", "fit"),
            page_range=options.get("pageRange"),
            max_pages=self._config.max_pages,
            render_dpi=self._config.render_dpi,
        )
        path = Path(job.file_path or "")
        copies = int(options.get("copies", 1) or 1)

        def pages_factory(geometry: Geometry):
            return render.iter_pages(
                path,
                job.kind,
                geometry,
                render_options,
                on_total=lambda count: self._store.update(job.id, pages=count * copies),
            )

        def on_page(count: int) -> None:
            self._store.update(job.id, status="printing", printed_pages=count)

        def should_cancel() -> bool:
            current = self._store.get(job.id)
            return current is None or current.status == "canceled"

        try:
            printed = self._backend.print_job(
                printer_name=printer_name,
                options=options,
                pages_factory=pages_factory,
                title=job.job_name or job.filename,
                margin_mm=self._config.margin_mm,
                on_page=on_page,
                should_cancel=should_cancel,
            )
            self._store.update(
                job.id,
                status="done",
                printed_pages=printed,
                pages=printed,
                finished_at=now_iso(),
            )
            log.info("İş tamamlandı: %s (%d sayfa)", job.id, printed)
        except JobCanceled:
            self._store.update(job.id, status="canceled", finished_at=now_iso())
            log.info("İş iptal edildi: %s", job.id)
        except AppError as exc:
            self._fail(job, exc.code, exc.message)
            log.warning("İş başarısız: %s · %s · %s", job.id, exc.code, exc.detail or "")
        except Exception as exc:  # noqa: BLE001
            self._fail(job, "internal_error", "Beklenmeyen hata; ajan loglarına bakın.")
            log.exception("İş sırasında beklenmeyen hata: %s", job.id)

    def _fail(self, job: Job, code: str, message: str) -> None:
        self._store.update(
            job.id,
            status="failed",
            error_code=code,
            error_message=message,
            finished_at=now_iso(),
        )

    def _resolve_printer(self, options: dict) -> str | None:
        """İstenen yazıcı yoksa (ad değişti/çıkarıldı) Windows varsayılanına düş.

        iPhone'daki uygulama eski bir yazıcı adı göndermiş olabilir; kullanıcı
        ayar değiştirmek zorunda kalmadan yazdırmaya devam etsin.
        """
        requested = options.get("printer") or self._config.default_printer
        try:
            printers = self._backend.list_printers()
        except Exception as exc:  # noqa: BLE001
            log.warning("Yazıcılar listelenemedi: %s", exc)
            printers = []

        known = {p.id for p in printers} | {p.name for p in printers}
        fallback = next((p.id for p in printers if p.is_default), printers[0].id if printers else None)

        if requested and requested in known:
            return requested
        if requested:
            log.warning(
                "Yazıcı bulunamadı: '%s' — Windows varsayılanı kullanılacak: '%s'",
                requested,
                fallback,
            )
        return fallback

    # --- temizlik ---------------------------------------------------------

    def _maybe_cleanup(self) -> None:
        now = time.monotonic()
        if now - self._last_cleanup < 1800:
            return
        self._last_cleanup = now
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self._config.retention_hours)
        spool = self._config.spool_dir
        if not spool.exists():
            return

        removed = 0
        for item in spool.iterdir():
            if not item.is_file():
                continue
            try:
                modified = datetime.fromtimestamp(item.stat().st_mtime, timezone.utc)
                if modified < cutoff and not self._store.active_with_file(str(item)):
                    item.unlink()
                    removed += 1
            except OSError:
                continue
        if removed:
            log.info("%d eski dosya silindi", removed)

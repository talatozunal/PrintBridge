# -*- coding: utf-8 -*-
"""Ajan yapılandırması.

Varsayılan konum:  %ProgramData%\\PrintBridge\\config.json
Geliştirme/test için: PRINTBRIDGE_DATA_DIR ortam değişkeni ile taşınabilir.
"""

from __future__ import annotations

import json
import os
import secrets
import socket
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def default_data_dir() -> Path:
    override = os.environ.get("PRINTBRIDGE_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    program_data = os.environ.get("PROGRAMDATA")
    if program_data:
        return Path(program_data) / "PrintBridge"
    return Path.home() / "AppData" / "Local" / "PrintBridge"


@dataclass
class Config:
    data_dir: Path
    agent_name: str
    agent_id: str
    host: str = "0.0.0.0"
    port: int = 8477
    default_printer: str | None = None
    margin_mm: float = 10.0
    render_dpi: int = 300
    max_mb: int = 50
    max_pages: int = 100
    max_queue: int = 10
    retention_hours: int = 24
    pin_ttl_seconds: int = 300
    pin_max_attempts: int = 5
    tokens: list[dict[str, Any]] = field(default_factory=list)

    # --- türetilmiş yollar -------------------------------------------------

    @property
    def config_path(self) -> Path:
        return self.data_dir / "config.json"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "jobs.db"

    @property
    def spool_dir(self) -> Path:
        return self.data_dir / "spool"

    @property
    def log_dir(self) -> Path:
        return self.data_dir / "logs"

    # --- yükleme / kaydetme ------------------------------------------------

    @classmethod
    def load(cls, data_dir: Path | None = None) -> "Config":
        base = (data_dir or default_data_dir()).resolve()
        path = base / "config.json"

        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
        else:
            raw = {}

        cfg = cls(
            data_dir=base,
            agent_name=raw.get("agentName") or socket.gethostname(),
            agent_id=raw.get("agentId") or secrets.token_hex(8),
            host=raw.get("host", "0.0.0.0"),
            port=int(raw.get("port", 8477)),
            default_printer=raw.get("defaultPrinter"),
            margin_mm=float(raw.get("marginMm", 10.0)),
            render_dpi=int(raw.get("renderDpi", 300)),
            max_mb=int(raw.get("maxMb", 50)),
            max_pages=int(raw.get("maxPages", 100)),
            max_queue=int(raw.get("maxQueue", 10)),
            retention_hours=int(raw.get("retentionHours", 24)),
            tokens=list(raw.get("tokens", [])),
        )

        for directory in (cfg.data_dir, cfg.spool_dir, cfg.log_dir):
            directory.mkdir(parents=True, exist_ok=True)

        if not path.exists():
            cfg.save()
        return cfg

    def save(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "agentName": self.agent_name,
            "agentId": self.agent_id,
            "host": self.host,
            "port": self.port,
            "defaultPrinter": self.default_printer,
            "marginMm": self.margin_mm,
            "renderDpi": self.render_dpi,
            "maxMb": self.max_mb,
            "maxPages": self.max_pages,
            "maxQueue": self.max_queue,
            "retentionHours": self.retention_hours,
            "tokens": self.tokens,
        }
        tmp = self.config_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.config_path)


def lan_addresses() -> list[str]:
    """Makinenin özel ağ adreslerini (kabaca) döndürür; tanıtım/QR için."""
    addresses: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            addresses.add(info[4][0])
    except OSError:
        pass
    try:
        # Varsayılan rotanın arayüz adresi (UDP bağlantısı paket göndermez).
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            addresses.add(sock.getsockname()[0])
    except OSError:
        pass
    return sorted(a for a in addresses if not a.startswith("127."))

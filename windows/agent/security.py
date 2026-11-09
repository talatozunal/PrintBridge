# -*- coding: utf-8 -*-
"""Eşleştirme PIN'i ve cihaz anahtarları (token) yönetimi."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from .config import Config
from .errors import InvalidPin, TooManyAttempts


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Device:
    id: str
    name: str
    created_at: str


class TokenStore:
    """Cihaz başlı başına uzun ömürlü token; yalnızca SHA-256 özeti saklanır."""

    def __init__(self, config: Config):
        self._config = config
        self._lock = threading.Lock()

    def create(self, device_name: str, device_id: str | None = None) -> str:
        raw = "pb_" + secrets.token_urlsafe(32)
        record = {
            "id": device_id or uuid.uuid4().hex,
            "name": (device_name or "Bilinmeyen cihaz").strip()[:64],
            "hash": _hash_token(raw),
            "createdAt": _now_iso(),
            "lastSeenAt": None,
        }
        with self._lock:
            # Aynı cihaz yeniden eşleşirse eski kaydı düşür.
            self._config.tokens = [t for t in self._config.tokens if t.get("id") != record["id"]]
            self._config.tokens.append(record)
            self._config.save()
        return raw

    def verify(self, raw: str | None) -> dict | None:
        if not raw:
            return None
        candidate = _hash_token(raw)
        with self._lock:
            for record in self._config.tokens:
                if hmac.compare_digest(record.get("hash", ""), candidate):
                    record["lastSeenAt"] = _now_iso()
                    return record
        return None

    def list_devices(self) -> list[Device]:
        with self._lock:
            return [
                Device(id=r["id"], name=r.get("name", "?"), created_at=r.get("createdAt", ""))
                for r in self._config.tokens
            ]

    def revoke(self, device_id: str) -> bool:
        with self._lock:
            before = len(self._config.tokens)
            self._config.tokens = [t for t in self._config.tokens if t.get("id") != device_id]
            if len(self._config.tokens) != before:
                self._config.save()
                return True
        return False


class PairingPin:
    """PC ekranında gösterilen 6 haneli, süreli PIN."""

    def __init__(self, ttl_seconds: int = 300, max_attempts: int = 5):
        self.ttl = ttl_seconds
        self.max_attempts = max_attempts
        self._lock = threading.Lock()
        self._pin = ""
        self._expires_at = 0.0
        self._attempts = 0
        self.refresh()

    def refresh(self) -> str:
        with self._lock:
            self._pin = f"{secrets.randbelow(1_000_000):06d}"
            self._expires_at = time.monotonic() + self.ttl
            self._attempts = 0
            return self._pin

    def current(self) -> str:
        with self._lock:
            if time.monotonic() >= self._expires_at:
                self._pin = f"{secrets.randbelow(1_000_000):06d}"
                self._expires_at = time.monotonic() + self.ttl
                self._attempts = 0
            return self._pin

    @property
    def seconds_left(self) -> int:
        with self._lock:
            return max(0, int(self._expires_at - time.monotonic()))

    def verify(self, pin: str | None) -> bool:
        with self._lock:
            if time.monotonic() >= self._expires_at:
                raise InvalidPin("PIN'in süresi doldu. PC'de yeni PIN oluşturun.")
            if self._attempts >= self.max_attempts:
                raise TooManyAttempts()
            if not pin or not hmac.compare_digest(str(pin).strip(), self._pin):
                self._attempts += 1
                if self._attempts >= self.max_attempts:
                    raise TooManyAttempts()
                raise InvalidPin()
            self._attempts = 0
            return True

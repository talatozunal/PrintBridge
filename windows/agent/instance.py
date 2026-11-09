# -*- coding: utf-8 -*-
"""Tek örnek kilidi: aynı anda iki ajan çalışıp aynı yazıcıyı kilitlemesin."""

from __future__ import annotations

import logging

log = logging.getLogger("printbridge.instance")

MUTEX_NAME = "PrintBridgeAgent-single-instance"


class SingleInstance:
    def __init__(self, name: str = MUTEX_NAME):
        self._name = name
        self._handle = None

    def acquire(self) -> bool:
        try:
            import win32api
            import win32event
            import winerror

            self._handle = win32event.CreateMutex(None, True, self._name)
            if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
                log.warning("Ajan zaten çalışıyor (%s)", self._name)
                return False
            return True
        except ImportError:
            return True
        except Exception as exc:  # noqa: BLE001
            log.warning("Tek örnek kilidi alınamadı: %s", exc)
            return True

    def release(self) -> None:
        if self._handle is None:
            return
        try:
            import win32api

            win32api.CloseHandle(self._handle)
        except Exception:  # noqa: BLE001
            pass
        finally:
            self._handle = None

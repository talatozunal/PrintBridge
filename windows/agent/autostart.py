# -*- coding: utf-8 -*-
"""Windows oturum açılışında otomatik başlatma (HKCU\\...\\Run).

Yönetici izni gerektirmez; Görev Zamanlayıcı'ya göre daha basit ve güvenilir.
"""

from __future__ import annotations

import logging
import sys

log = logging.getLogger("printbridge.autostart")

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "PrintBridgeAgent"


def launcher_command() -> str:
    """Kayıt defterine yazılacak komut."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    return f'"{sys.executable}" -m agent.tray'


def is_enabled() -> bool:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _kind = winreg.QueryValueEx(key, VALUE_NAME)
            return bool(value)
    except FileNotFoundError:
        return False
    except OSError:
        return False


def set_enabled(enabled: bool, command: str | None = None) -> None:
    import winreg

    if enabled:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command or launcher_command())
        log.info("Otomatik başlatma açıldı: %s", command or launcher_command())
        return

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, VALUE_NAME)
        log.info("Otomatik başlatma kapatıldı")
    except FileNotFoundError:
        pass

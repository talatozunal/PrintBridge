# -*- coding: utf-8 -*-
"""Windows Güvenlik Duvarı kuralı (netsh) ve yönetici yükseltmesi.

Ajan 0.0.0.0:8477 dinlediği için iPhone'un bağlanabilmesi adına gelen TCP
kuralı gerekir. Kural yalnızca "Özel" ağ profiline eklenir; yönetici izni
gerekir. Tepsideki ayarlardan veya `--firewall` ile çalıştırılabilir.
"""

from __future__ import annotations

import ctypes
import logging
import subprocess
import sys
from pathlib import Path

log = logging.getLogger("printbridge.firewall")

RULE_NAME = "PrintBridge Agent"
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


def build_add_args(port: int, program: str | None = None) -> list[str]:
    args = [
        "netsh",
        "advfirewall",
        "firewall",
        "add",
        "rule",
        f"name={RULE_NAME}",
        "dir=in",
        "action=allow",
        "protocol=TCP",
        f"localport={int(port)}",
        "profile=private",
        "enable=yes",
    ]
    if program:
        args.append(f"program={program}")
    return args


def build_delete_args() -> list[str]:
    return ["netsh", "advfirewall", "firewall", "delete", "rule", f"name={RULE_NAME}"]


def build_show_args() -> list[str]:
    return ["netsh", "advfirewall", "firewall", "show", "rule", f"name={RULE_NAME}"]


def _run(args: list[str]) -> tuple[int, str]:
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            errors="replace",
            creationflags=CREATE_NO_WINDOW,
        )
    except OSError as exc:
        return 1, str(exc)
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:  # noqa: BLE001
        return False


def rule_exists() -> bool:
    code, _output = _run(build_show_args())
    return code == 0


def add_rule(port: int, program: str | None = None) -> tuple[bool, str]:
    if rule_exists():
        _run(build_delete_args())
    code, output = _run(build_add_args(port, program))
    if code == 0:
        log.info("Güvenlik duvarı kuralı eklendi (TCP %s)", port)
        return True, f"Güvenlik duvarı kuralı eklendi: TCP {port} (özel ağ)."
    log.warning("Güvenlik duvarı kuralı eklenemedi: %s", output.strip())
    return False, f"Kural eklenemedi (kod {code}).\n{output.strip()[:400]}"


def remove_rule() -> tuple[bool, str]:
    code, output = _run(build_delete_args())
    if code == 0:
        return True, "Güvenlik duvarı kuralı kaldırıldı."
    return False, f"Kural kaldırılamadı (kod {code}).\n{output.strip()[:400]}"


def _elevate_params(args: list[str]) -> tuple[str, str, str]:
    """(exe, parametreler, çalışma dizini) — kaynak ve paketlenmiş mod."""
    if getattr(sys, "frozen", False):
        return sys.executable, subprocess.list2cmdline(args), str(Path(sys.executable).parent)
    project_root = Path(__file__).resolve().parent.parent
    params = subprocess.list2cmdline(["-m", "agent.tray", *args])
    return sys.executable, params, str(project_root)


def elevate(args: list[str]) -> bool:
    """UAC istemiyle aynı uygulamayı yönetici olarak yeniden başlatır."""
    exe, params, directory = _elevate_params(args)
    try:
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", exe, params, directory, 1
        )
        return int(result) > 32
    except Exception as exc:  # noqa: BLE001
        log.warning("Yönetici yükseltmesi başarısız: %s", exc)
        return False

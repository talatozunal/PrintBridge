# -*- coding: utf-8 -*-
"""PrintBridge Agent giriş noktası.

Kullanım:
    py -3 -m agent.main
    PrintBridge-Agent.exe  (PyInstaller)
"""

from __future__ import annotations

import argparse

import uvicorn

from .api import create_app
from .config import Config, lan_addresses
from .discovery import Discovery
from .logging_setup import setup_logging
from .printer import WindowsBackend
from .security import TokenStore


def print_diagnostics(config: Config) -> str:
    """Kurulum/bağlantı sorunlarını teşhis için düz metin rapor."""
    backend = WindowsBackend()
    lines = [
        f"Agent adı: {config.agent_name}  (id: {config.agent_id})",
        f"Veri dizini: {config.data_dir}",
        f"API: http://{config.host}:{config.port}/api/v1",
        "",
        "Yazıcılar:",
    ]
    for printer in backend.list_printers():
        lines.append(
            f"  - {printer.id} [{printer.status}] (varsayılan={printer.is_default}) "
            f"— {printer.driver} @ {printer.port}"
        )
        lines.append(f"    kâğıtlar: {', '.join(sorted(printer.papers, key=str.upper))[:80]}")
    lines.append("")
    lines.append("Eşleşmiş cihazlar:")
    for device in TokenStore(config).list_devices():
        lines.append(f"  - {device.name} ({device.id}) {device.created_at}")

    text = "\n".join(lines)
    print(text)
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PrintBridge Agent")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--reload", action="store_true", help="Geliştirme modu (sadece kaynak çalıştırmada)")
    parser.add_argument("--diagnose", action="store_true", help="Tanılama raporu yazdır ve çık")
    parser.add_argument("--allow-any-client", action="store_true", help="Yalnızca test için")
    args = parser.parse_args(argv)

    config = Config.load()
    setup_logging(config)

    if args.diagnose:
        print_diagnostics(config)
        return 0

    host = args.host or config.host
    port = args.port or config.port
    app = create_app(config, allow_any_client=args.allow_any_client)

    addresses = lan_addresses() or ["127.0.0.1"]
    pin = app.state.pairing.current()
    print()
    print("=" * 58)
    print("  PrintBridge Agent")
    print("=" * 58)
    print(f"  Adres   : http://{addresses[0]}:{port}")
    for extra in addresses[1:]:
        print(f"            http://{extra}:{port}")
    print(f"  Eşleşme : PIN {pin}  ({app.state.pairing.seconds_left} sn geçerli)")
    print(f"  Veri    : {config.data_dir}")

    discovery = Discovery(config, port=port)
    if args.reload:
        print("  Keşif   : --reload modunda kapalı")
    else:
        discovery.start()
        print("  Keşif   : mDNS açık" if discovery.active else "  Keşif   : mDNS kapalı (QR / elle IP)")
    print("=" * 58)
    print()

    try:
        uvicorn.run(app, host=host, port=port, reload=args.reload, log_config=None)
    finally:
        discovery.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""mDNS yayını (`_printbridge._tcp`) ve QR eşleştirme yükü.

mDNS, iPhone'un aynı Wi-Fi ağında PC'yi otomatik bulmasını sağlar. Yayın
başlatılamazsa (port dolu, güvenlik duvarı, zeroconf yok) ajan çalışmaya devam
eder; keşif için QR kod / elle IP yedeği kullanılır.
"""

from __future__ import annotations

import logging
import re
import socket
from urllib.parse import urlencode

from .config import Config, lan_addresses

SERVICE_TYPE = "_printbridge._tcp.local."
PROTOCOL_VERSION = "1"

log = logging.getLogger("printbridge.discovery")


def primary_address() -> str:
    """iPhone'un kullanacağı en olası LAN adresi."""
    addresses = lan_addresses()
    return addresses[0] if addresses else "127.0.0.1"


def qr_payload(config: Config, host: str | None = None) -> str:
    """Tepside gösterilen QR'ın içeriği (PIN içermez; uygulama PIN sorar)."""
    query = urlencode(
        {
            "v": PROTOCOL_VERSION,
            "host": host or primary_address(),
            "port": config.port,
            "id": config.agent_id,
            "name": config.agent_name,
        }
    )
    return f"printbridge://pair?{query}"


def txt_records(config: Config, printers: int = 0) -> dict[bytes, bytes]:
    return {
        b"v": PROTOCOL_VERSION.encode("ascii"),
        b"name": config.agent_name.encode("utf-8", "replace"),
        b"id": config.agent_id.encode("ascii", "replace"),
        b"path": b"/api/v1",
        b"pair": b"required",
        b"printers": str(max(0, int(printers))).encode("ascii"),
    }


def service_name(config: Config, attempt: int = 0) -> str:
    """DNS etiketi kurallarına uygun, çakışmada artırılabilir ad."""
    base = re.sub(r"[^A-Za-z0-9-]+", "-", config.agent_name).strip("-") or "PrintBridge"
    base = base[:40]
    suffix = config.agent_id[:6] or "agent"
    if attempt:
        suffix = f"{suffix}-{attempt + 1}"
    return f"{base}-{suffix}.{SERVICE_TYPE}"


class Discovery:
    """Zeroconf yayınını başlatır/durdurur; hatalarda sessizce devre dışı kalır."""

    def __init__(self, config: Config, port: int | None = None, printers: int = 0):
        self.config = config
        self.port = port or config.port
        self.printers = printers
        self._zeroconf = None
        self._info = None
        self.active = False

    def start(self) -> bool:
        if self.active:
            return True
        try:
            from zeroconf import NonUniqueNameException, ServiceInfo, Zeroconf
        except Exception as exc:  # noqa: BLE001
            log.warning("zeroconf kullanılamıyor; mDNS kapalı: %s", exc)
            return False

        addresses = [socket.inet_aton(ip) for ip in lan_addresses() if ":" not in ip]
        if not addresses:
            addresses = [socket.inet_aton("127.0.0.1")]

        try:
            zeroconf = Zeroconf()
        except Exception as exc:  # noqa: BLE001
            log.warning("mDNS başlatılamadı: %s", exc)
            return False

        server = f"{socket.gethostname()}.local."
        for attempt in range(3):
            info = ServiceInfo(
                SERVICE_TYPE,
                service_name(self.config, attempt),
                addresses=addresses,
                port=self.port,
                properties=txt_records(self.config, self.printers),
                server=server,
            )
            try:
                zeroconf.register_service(info)
            except NonUniqueNameException:
                log.warning("mDNS adı çakıştı, yeniden deneniyor: %s", info.name)
                continue
            except Exception as exc:  # noqa: BLE001
                log.warning("mDNS yayını başlatılamadı: %s", exc)
                zeroconf.close()
                return False

            self._zeroconf = zeroconf
            self._info = info
            self.active = True
            log.info("mDNS yayını hazır: %s (port %s)", info.name, self.port)
            return True

        zeroconf.close()
        log.warning("mDNS için benzersiz ad bulunamadı; yayın kapalı.")
        return False

    def stop(self) -> None:
        zeroconf, info = self._zeroconf, self._info
        self._zeroconf = None
        self._info = None
        self.active = False
        if zeroconf is None:
            return
        try:
            if info is not None:
                zeroconf.unregister_service(info)
        except Exception as exc:  # noqa: BLE001
            log.debug("mDNS kaydı kaldırılamadı: %s", exc)
        try:
            zeroconf.close()
        except Exception:  # noqa: BLE001
            pass

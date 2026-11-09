# -*- coding: utf-8 -*-
"""mDNS/QR yardımcılarının saf fonksiyon testleri (ağa dokunmaz)."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from agent import discovery


def test_qr_payload_roundtrip(config):
    payload = discovery.qr_payload(config, "192.168.1.20")
    assert payload.startswith("printbridge://pair?")

    parsed = urlparse(payload)
    query = parse_qs(parsed.query)
    assert parsed.scheme == "printbridge"
    assert parsed.netloc == "pair"
    assert query["host"] == ["192.168.1.20"]
    assert query["port"] == [str(config.port)]
    assert query["id"] == [config.agent_id]
    assert query["name"] == [config.agent_name]
    # PIN, QR içine gömülmez; uygulama kullanıcıdan ister.
    assert "pin" not in query


def test_txt_records(config):
    records = discovery.txt_records(config, printers=2)
    assert records[b"v"] == b"1"
    assert records[b"name"] == config.agent_name.encode()
    assert records[b"id"] == config.agent_id.encode()
    assert records[b"path"] == b"/api/v1"
    assert records[b"pair"] == b"required"
    assert records[b"printers"] == b"2"


def test_service_name_is_dns_safe(config):
    name = discovery.service_name(config)
    assert name.endswith(discovery.SERVICE_TYPE)
    label = name[: -len(discovery.SERVICE_TYPE) - 1]
    assert 0 < len(label) <= 63
    assert " " not in label
    assert discovery.service_name(config, attempt=1) != name


def test_service_name_sanitizes_odd_characters(config):
    config.agent_name = "Masaüstü PC / Ofis #1"
    label = discovery.service_name(config).split(".")[0]
    assert " " not in label and "/" not in label and "#" not in label


def test_discovery_stop_without_start_is_safe(config):
    instance = discovery.Discovery(config)
    instance.stop()
    assert instance.active is False

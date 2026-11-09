# -*- coding: utf-8 -*-
"""Test yardımcıları: geçici veri dizini, sahte yazıcı arka ucu, HTTP istemcisi."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from agent.api import create_app
from agent.config import Config
from agent.errors import JobCanceled, SpoolFailed
from agent.printer import Geometry, PrinterInfo


class FakeBackend:
    """Gerçek yazıcıya dokunmayan, davranışı taklit eden arka uç."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.printed_pages = 0
        self.delay = 0.0
        self.fail_next = False
        self.on_print = None

    def list_printers(self) -> list[PrinterInfo]:
        return [
            PrinterInfo(
                id="Fake Printer",
                name="Fake Printer",
                driver="Fake Driver",
                port="USB001",
                status_bits=0,
                papers={"A4": 9, "Letter": 1},
                is_default=True,
            )
        ]

    def default_printer(self) -> PrinterInfo | None:
        return self.list_printers()[0]

    def preview_geometry(self, printer_name: str, options: dict, margin_mm: float = 10.0) -> Geometry:
        return Geometry(4760, 6814, 600, 600, margin_mm)

    def print_job(
        self,
        printer_name: str,
        options: dict,
        pages_factory,
        title: str,
        margin_mm: float = 10.0,
        on_page=None,
        should_cancel=None,
    ) -> int:
        if self.fail_next:
            self.fail_next = False
            raise SpoolFailed("Test için yazdırma hatası.", detail="injected")

        self.calls.append(
            {"printer": printer_name, "title": title, "options": dict(options), "margin": margin_mm}
        )
        if self.on_print:
            self.on_print()

        geometry = Geometry(4760, 6814, 600, 600, margin_mm)
        count = 0
        copies = int(options.get("copies", 1) or 1)
        for _copy in range(copies):
            for _page in pages_factory(geometry):
                if should_cancel and should_cancel():
                    raise JobCanceled()
                if self.delay:
                    time.sleep(self.delay)
                count += 1
                if on_page:
                    on_page(count)
        self.printed_pages = count
        return count


@pytest.fixture()
def config(tmp_path) -> Config:
    cfg = Config.load(tmp_path / "data")
    cfg.render_dpi = 150           # testleri hızlı tut
    cfg.default_printer = "Fake Printer"
    cfg.max_mb = 2
    cfg.max_queue = 5
    cfg.save()
    return cfg


@pytest.fixture()
def backend() -> FakeBackend:
    return FakeBackend()


@pytest.fixture()
def app(config, backend):
    return create_app(config, backend=backend, allow_any_client=True)


@pytest.fixture()
def client(app):
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def token(client, app) -> str:
    pin = app.state.pairing.current()
    response = client.post(
        "/api/v1/pair", json={"pin": pin, "deviceName": "pytest", "deviceId": "test-device"}
    )
    assert response.status_code == 200, response.text
    return response.json()["token"]


@pytest.fixture()
def auth(token) -> dict:
    return {"Authorization": f"Bearer {token}"}


def wait_for(client: TestClient, job_id: str, auth: dict, timeout: float = 20.0) -> dict:
    deadline = time.time() + timeout
    last = {}
    while time.time() < deadline:
        response = client.get(f"/api/v1/jobs/{job_id}", headers=auth)
        assert response.status_code == 200, response.text
        last = response.json()
        if last["status"] in ("done", "failed", "canceled"):
            return last
        time.sleep(0.05)
    raise AssertionError(f"İş zamanında bitmedi: {last}")

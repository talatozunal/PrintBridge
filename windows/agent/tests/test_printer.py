# -*- coding: utf-8 -*-
"""Geometri, hata eşleme ve sayfa aralığı testleri."""

from __future__ import annotations

import pytest

from agent.errors import InvalidOptions
from agent.printer import Geometry, map_windows_error, mm_to_px, px_to_mm
from agent.render import parse_page_range


def test_mm_px_roundtrip():
    assert mm_to_px(10, 600) == 236
    assert abs(px_to_mm(236, 600) - 9.99) < 0.02


def test_geometry_a4():
    geometry = Geometry(printable_w_px=4760, printable_h_px=6814, dpi_x=600, dpi_y=600, margin_mm=10)
    assert round(geometry.page_w_mm) == 202
    assert round(geometry.page_h_mm) == 288

    width, height = geometry.canvas_size(300)
    assert (width, height) == (2380, 3407)

    x0, y0, x1, y1 = geometry.content_box(300)
    assert x0 == y0 == 118
    assert x1 == width - 118 and y1 == height - 118
    assert x0 < x1 and y0 < y1


def test_geometry_margin_too_large_falls_back():
    geometry = Geometry(1000, 1000, 600, 600, margin_mm=200)
    x0, y0, x1, y1 = geometry.content_box(600)
    assert (x0, y0) == (0, 0) and (x1, y1) == (1000, 1000)


def test_geometry_landscape_is_swapped_by_driver():
    geometry = Geometry(6814, 4760, 600, 600, 10)
    assert geometry.page_w_mm > geometry.page_h_mm


@pytest.mark.parametrize(
    "spec,total,expected",
    [
        (None, 3, [1, 2, 3]),
        ("", 3, [1, 2, 3]),
        ("all", 2, [1, 2]),
        ("1", 3, [1]),
        ("1-3", 5, [1, 2, 3]),
        ("2-3,1", 3, [2, 3, 1]),
        (" 4 , 4 ", 5, [4]),
    ],
)
def test_parse_page_range_valid(spec, total, expected):
    assert parse_page_range(spec, total) == expected


@pytest.mark.parametrize("spec,total", [("0", 3), ("4", 3), ("3-1", 3), ("a-b", 3), ("1-", 3)])
def test_parse_page_range_invalid(spec, total):
    with pytest.raises(InvalidOptions):
        parse_page_range(spec, total)


def test_map_windows_error_known_code():
    exc = OSError()
    exc.winerror = 1803
    mapped = map_windows_error(exc)
    assert mapped.code == "spool_failed"
    assert "bulunamadı" in mapped.message
    assert "0x070B" in (mapped.detail or "")


def test_map_windows_error_unknown_code():
    mapped = map_windows_error(RuntimeError("patladı"))
    assert mapped.code == "spool_failed"
    assert "patladı" in (mapped.detail or "")

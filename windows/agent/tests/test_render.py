# -*- coding: utf-8 -*-
"""Render testleri: tür tespiti, görsel yerleştirme, metin sayfalama, PDF."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from agent.errors import InvalidOptions
from agent.printer import Geometry
from agent.render import (
    RenderOptions,
    detect_kind,
    iter_image_pages,
    iter_pdf_pages,
    iter_text_pages,
)

GEOMETRY = Geometry(
    printable_w_px=4760, printable_h_px=6814, dpi_x=600, dpi_y=600, margin_mm=10
)
LONG_TEXT = "\n".join(f"Satır {i} — şğüİÖÇ 1234567890" for i in range(120))


def make_image(path: Path, size=(1200, 800), color=(200, 30, 30)) -> Path:
    image = Image.new("RGB", size, color)
    draw = ImageDraw.Draw(image)
    draw.ellipse([50, 50, 300, 300], fill=(20, 120, 220))
    image.save(path, quality=95)
    return path


@pytest.mark.parametrize(
    "filename,head,expected",
    [
        ("a.pdf", b"%PDF-1.7\n", "pdf"),
        ("a.jpg", b"\xff\xd8\xff\xe0", "image"),
        ("a.png", b"\x89PNG\r\n\x1a\n", "image"),
        ("a.heic", b"\x00\x00\x00\x18ftypheic", "image"),
        ("a.txt", b"merhaba", "text"),
        ("a.bin", b"\x00\x01\x02\x03", "unknown"),
        ("foto", b"\xff\xd8\xff", "image"),
    ],
)
def test_detect_kind(filename, head, expected):
    assert detect_kind(filename, head) == expected


def test_image_page_layout(tmp_path):
    path = make_image(tmp_path / "foto.jpg")
    pages = list(iter_image_pages(path, GEOMETRY, RenderOptions(render_dpi=150)))
    assert len(pages) == 1

    page = pages[0]
    assert page.size == GEOMETRY.canvas_size(150)
    assert page.mode == "RGB"

    width, height = page.size
    assert page.getpixel((5, 5))[0] > 240           # kenar boşluğu beyaz
    assert page.getpixel((width // 2, height // 2))[0] > 100  # ortada görsel var
    assert page.getpixel((width // 2, height - 5))[0] > 240   # alt boşluk beyaz


def test_image_fill_crops(tmp_path):
    path = make_image(tmp_path / "genis.png", size=(3000, 600), color=(10, 200, 10))
    fit_page = list(iter_image_pages(path, GEOMETRY, RenderOptions(fit="fit", render_dpi=150)))[0]
    fill_page = list(iter_image_pages(path, GEOMETRY, RenderOptions(fit="fill", render_dpi=150)))[0]

    width, height = fit_page.size
    x0, y0, x1, y1 = GEOMETRY.content_box(150)

    # "fit"te görsel dikeyde ortada ince bir şerit olur; üstte beyaz kalır.
    assert fit_page.getpixel((width // 2, y0 + 5))[0] > 240
    # "fill"te içerik kutusunun üst kenarına kadar dolar.
    assert fill_page.getpixel((width // 2, y0 + 5))[1] > 150


def test_text_pagination(tmp_path):
    path = tmp_path / "metin.txt"
    path.write_text(LONG_TEXT, encoding="utf-8")

    pages = list(iter_text_pages(path, GEOMETRY, RenderOptions(render_dpi=150)))
    assert len(pages) >= 2
    for page in pages:
        assert page.size == GEOMETRY.canvas_size(150)
        assert page.convert("L").getextrema()[0] < 128  # sayfada mürekkep var


def test_text_page_range(tmp_path):
    path = tmp_path / "metin.txt"
    path.write_text(LONG_TEXT, encoding="utf-8")

    all_pages = list(iter_text_pages(path, GEOMETRY, RenderOptions(render_dpi=150)))
    only_first = list(
        iter_text_pages(path, GEOMETRY, RenderOptions(page_range="1", render_dpi=150))
    )
    assert len(only_first) == 1
    assert len(all_pages) > 1


def test_text_max_pages_limit(tmp_path):
    path = tmp_path / "metin.txt"
    path.write_text(LONG_TEXT, encoding="utf-8")
    with pytest.raises(InvalidOptions):
        list(iter_text_pages(path, GEOMETRY, RenderOptions(max_pages=1, render_dpi=150)))


def test_text_turkish_cp1254(tmp_path):
    path = tmp_path / "eski.txt"
    path.write_bytes("Türkçe şğüİÖÇ karakterler\r\nikinci satır".encode("cp1254"))
    pages = list(iter_text_pages(path, GEOMETRY, RenderOptions(render_dpi=150)))
    assert len(pages) == 1
    assert pages[0].convert("L").getextrema()[0] < 128


def test_pdf_pages(tmp_path):
    path = tmp_path / "belge.pdf"
    pages = [Image.new("RGB", (595, 842), color) for color in ("white", "white", "white")]
    draw = ImageDraw.Draw(pages[0])
    draw.rectangle([50, 50, 500, 300], fill=(30, 30, 200))
    pages[0].save(
        path, save_all=True, append_images=pages[1:], resolution=72.0, quality=90
    )

    rendered = list(iter_pdf_pages(path, GEOMETRY, RenderOptions(render_dpi=150)))
    assert len(rendered) == 3
    assert rendered[0].size == GEOMETRY.canvas_size(150)
    assert rendered[0].convert("L").getextrema()[0] < 100

    selected = list(
        iter_pdf_pages(path, GEOMETRY, RenderOptions(page_range="2", render_dpi=150))
    )
    assert len(selected) == 1


def test_pdf_page_range_out_of_bounds(tmp_path):
    path = tmp_path / "tek.pdf"
    Image.new("RGB", (300, 300), "white").save(path, "PDF", resolution=72.0)
    with pytest.raises(InvalidOptions):
        list(iter_pdf_pages(path, GEOMETRY, RenderOptions(page_range="5", render_dpi=150)))


def test_render_reports_total_pages(tmp_path):
    text_path = tmp_path / "uzun.txt"
    text_path.write_text(LONG_TEXT, encoding="utf-8")
    totals: list[int] = []
    rendered = list(
        iter_text_pages(
            text_path, GEOMETRY, RenderOptions(render_dpi=150), on_total=totals.append
        )
    )
    assert totals == [len(rendered)]

    pdf_path = tmp_path / "iki.pdf"
    pages = [Image.new("RGB", (300, 300), "white") for _ in range(2)]
    pages[0].save(pdf_path, save_all=True, append_images=pages[1:], resolution=72.0)
    totals.clear()
    rendered = list(
        iter_pdf_pages(
            pdf_path, GEOMETRY, RenderOptions(page_range="2", render_dpi=150), on_total=totals.append
        )
    )
    assert totals == [1] and len(rendered) == 1

    image_path = make_image(tmp_path / "tek.jpg", size=(300, 200))
    totals.clear()
    list(iter_image_pages(image_path, GEOMETRY, RenderOptions(render_dpi=150), on_total=totals.append))
    assert totals == [1]

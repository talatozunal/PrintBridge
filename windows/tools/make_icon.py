# -*- coding: utf-8 -*-
"""Tepsi/exe simgesini üretir: agent/assets/printbridge.ico

Kullanım:
    py -3 tools/make_icon.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "agent" / "assets"
SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]

BLUE = (21, 87, 190, 255)
WHITE = (255, 255, 255, 255)
GLASS = (21, 87, 190, 255)


def draw_icon(size: int = 256) -> Image.Image:
    """256 px taban çizim; küçük boyutlar PIL tarafından ölçeklenir."""
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    unit = size / 64.0

    def box(x0: float, y0: float, x1: float, y1: float) -> list[float]:
        return [x0 * unit, y0 * unit, x1 * unit, y1 * unit]

    draw.rounded_rectangle(box(2, 2, 62, 62), radius=14 * unit, fill=BLUE)
    draw.rectangle(box(18, 13, 46, 23), fill=WHITE)
    draw.rounded_rectangle(box(12, 24, 52, 46), radius=4 * unit, fill=WHITE)
    draw.rectangle(box(19, 38, 45, 55), fill=GLASS)
    draw.rectangle(box(23, 42, 41, 51), fill=WHITE)
    draw.ellipse(box(44, 28, 49, 33), fill=GLASS)
    return image


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)
    target = ASSETS / "printbridge.ico"
    icon = draw_icon(256)
    icon.save(target, format="ICO", sizes=[(size, size) for size in SIZES])
    print(f"Yazıldı: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

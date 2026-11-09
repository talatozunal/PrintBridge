# -*- coding: utf-8 -*-
"""Dosya → sayfa görüntüsü dönüşümü (görsel, metin, PDF).

Her sayfa, sürücünün bildirdiği yazdırılabilir alanın mm ölçüsünde bir PIL
görüntüsü olarak üretilir. Baskı anında GDI bu görüntüyü aygıt pikseline
ölçekler; böylece render çözünürlüğü ile yazıcı çözünürlüğü ayrışır.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .errors import InvalidOptions, RenderFailed
from .printer import Geometry

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff", ".webp", ".heic", ".heif"}
TEXT_EXTS = {".txt", ".text", ".md", ".log", ".csv"}
PDF_EXTS = {".pdf"}

# iPhone'dan gelen HEIC dosyalarını Pillow'a tanıt (paket varsa).
try:  # pragma: no cover - ortamda paket olmayabilir
    from pillow_heif import register_heif_opener

    register_heif_opener()
except Exception:  # noqa: BLE001
    pass


@dataclass(frozen=True)
class RenderOptions:
    fit: str = "fit"
    page_range: str | None = None
    max_pages: int = 100
    render_dpi: int = 300


def detect_kind(filename: str, head: bytes) -> str:
    """Sihirli baytlara (ve gerekirse uzantıya) göre içerik türü."""
    suffix = Path(filename).suffix.lower()

    if head.startswith(b"%PDF"):
        return "pdf"
    if head.startswith(b"\xff\xd8\xff") or head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image"
    if head.startswith(b"GIF8") or head.startswith(b"BM"):
        return "image"
    if head[:2] in (b"II", b"MM"):
        return "image"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image"
    if head[4:8] == b"ftyp":  # HEIC/HEIF/AVIF kutusu
        return "image"

    if suffix in PDF_EXTS:
        return "pdf"
    if suffix in IMAGE_EXTS:
        return "image"
    if suffix in TEXT_EXTS:
        return "text"

    # Uzantı tanıdık değilse: NUL içermeyen, çözülebilen içerik metin sayılır.
    if head and b"\x00" not in head:
        try:
            head.decode("utf-8")
            return "text"
        except UnicodeDecodeError:
            return "unknown"
    return "unknown"


def parse_page_range(spec: str | None, total: int) -> list[int]:
    """'1-3,5' → [1,2,3,5]. Boş/None → tüm sayfalar."""
    if total <= 0:
        raise InvalidOptions("Belgede yazdırılabilir sayfa yok.")
    if spec is None or not str(spec).strip() or str(spec).strip().lower() in ("all", "tümü"):
        return list(range(1, total + 1))

    pages: list[int] = []
    for part in str(spec).split(","):
        chunk = part.strip()
        if not chunk:
            continue
        try:
            if "-" in chunk:
                first, last = chunk.split("-", 1)
                start, end = int(first), int(last)
            else:
                start = end = int(chunk)
        except ValueError as exc:
            raise InvalidOptions(f"Sayfa aralığı anlaşılamadı: '{chunk}'") from exc
        if start < 1 or end < start or end > total:
            raise InvalidOptions(
                f"Sayfa aralığı belge dışında: '{chunk}' (belge {total} sayfa)."
            )
        pages.extend(range(start, end + 1))

    if not pages:
        raise InvalidOptions("Sayfa aralığı boş.")
    # Tekrarları at, sırayı koru.
    return list(dict.fromkeys(pages))


def render_dpi_for(geometry: Geometry, requested: int) -> int:
    return max(150, min(geometry.dpi_x, requested))


def auto_orientation(path: Path) -> str:
    """Görsel yataysa yatay sayfa; açılamazsa dikey."""
    try:
        with Image.open(path) as image:
            return "landscape" if image.width > image.height else "portrait"
    except Exception:  # noqa: BLE001
        return "portrait"


# --- fontlar --------------------------------------------------------------

_FONT_CACHE: dict[tuple[int, bool], ImageFont.FreeTypeFont] = {}
_FONT_DIR = Path("C:/Windows/Fonts")
_FONT_FILES = {
    False: ("arial.ttf", "segoeui.ttf", "calibri.ttf", "tahoma.ttf"),
    True: ("arialbd.ttf", "segoeuib.ttf", "calibrib.ttf", "tahomabd.ttf"),
}


def load_font(px: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    px = max(6, int(px))
    key = (px, bold)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    for name in _FONT_FILES[bold]:
        path = _FONT_DIR / name
        if path.exists():
            font = ImageFont.truetype(str(path), px)
            _FONT_CACHE[key] = font
            return font
    font = ImageFont.load_default(size=px)
    _FONT_CACHE[key] = font
    return font


# --- ortak yerleştirme ----------------------------------------------------


def _place(page: Image.Image, img: Image.Image, box: tuple[int, int, int, int], fit: str) -> None:
    x0, y0, x1, y1 = box
    box_w, box_h = x1 - x0, y1 - y0
    src_w, src_h = img.size
    if src_w <= 0 or src_h <= 0:
        raise RenderFailed("Görsel boyutu geçersiz.")

    scale = min(box_w / src_w, box_h / src_h) if fit == "fit" else max(box_w / src_w, box_h / src_h)
    new_w = max(1, int(round(src_w * scale)))
    new_h = max(1, int(round(src_h * scale)))

    resample = Image.Resampling.LANCZOS if scale < 1 else Image.Resampling.BICUBIC
    scaled = img.resize((new_w, new_h), resample)

    left = x0 + (box_w - new_w) // 2
    top = y0 + (box_h - new_h) // 2

    if fit == "fill":
        crop = (
            max(0, -left),
            max(0, -top),
            new_w - max(0, left + new_w - x1),
            new_h - max(0, top + new_h - y1),
        )
        if crop != (0, 0, new_w, new_h):
            scaled = scaled.crop(crop)
            left = max(left, x0)
            top = max(top, y0)

    page.paste(scaled, (left, top))


def _open_image(path: Path) -> Image.Image:
    try:
        img = Image.open(path)
        img.load()
    except Exception as exc:  # noqa: BLE001
        raise RenderFailed(f"Görsel açılamadı: {path.name}", detail=str(exc)) from exc

    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P", "PA"):
        img = img.convert("RGBA")
        background = Image.new("RGB", img.size, "white")
        background.paste(img, mask=img.split()[-1])
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")
    return img


# --- metin ----------------------------------------------------------------


def _decode_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp1254", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise RenderFailed("Metin dosyası çözülemedi (kodlama tanınmadı).")


def _wrap_lines(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    scratch = ImageDraw.Draw(Image.new("L", (8, 8)))
    lines: list[str] = []

    def width(value: str) -> float:
        return scratch.textlength(value, font=font)

    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.replace("\t", "    ")
        if not line.strip():
            lines.append("")
            continue

        current = ""
        for word in line.split(" "):
            candidate = word if not current else f"{current} {word}"
            if width(candidate) <= max_width:
                current = candidate
                continue

            if current:
                lines.append(current)
                current = ""

            # Kutudan uzun tek kelimeyi karakter karakter böl.
            while word and width(word) > max_width:
                cut = 1
                while cut < len(word) and width(word[: cut + 1]) <= max_width:
                    cut += 1
                lines.append(word[:cut])
                word = word[cut:]
            current = word

        if current:
            lines.append(current)

    return lines or [""]


def iter_text_pages(
    path: Path, geometry: Geometry, options: RenderOptions, on_total=None
) -> Iterator[Image.Image]:
    dpi = render_dpi_for(geometry, options.render_dpi)
    text = _decode_text(path)

    body_px = max(8, int(round(11 * dpi / 72)))
    footer_px = max(7, int(round(8 * dpi / 72)))
    body = load_font(body_px)
    footer = load_font(footer_px)

    width, height = geometry.canvas_size(dpi)
    x0, y0, x1, y1 = geometry.content_box(dpi)
    line_h = int(round(body_px * 1.45))
    footer_h = int(round(footer_px * 2.6))

    lines = _wrap_lines(text, body, x1 - x0)
    available_h = max(line_h, (y1 - footer_h) - y0)
    per_page = max(1, available_h // line_h)
    total_pages = max(1, math.ceil(len(lines) / per_page))

    if total_pages > options.max_pages:
        raise InvalidOptions(
            f"Belge {total_pages} sayfa; sınır {options.max_pages}. Sayfa aralığı seçin."
        )

    selected = set(parse_page_range(options.page_range, total_pages))
    if on_total:
        on_total(len(selected))

    for page_no in range(1, total_pages + 1):
        if page_no not in selected:
            continue
        page = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(page)

        start = (page_no - 1) * per_page
        chunk = lines[start : start + per_page]
        y = y0
        for line in chunk:
            if line:
                draw.text((x0, y), line, font=body, fill=(0, 0, 0))
            y += line_h

        label = f"Sayfa {page_no} / {total_pages}"
        draw.text((x1, y1 - footer_h), label, font=footer, fill=(90, 90, 90), anchor="ra")
        yield page


# --- görsel ---------------------------------------------------------------


def iter_image_pages(
    path: Path, geometry: Geometry, options: RenderOptions, on_total=None
) -> Iterator[Image.Image]:
    dpi = render_dpi_for(geometry, options.render_dpi)
    if on_total:
        on_total(1)
    page = Image.new("RGB", geometry.canvas_size(dpi), "white")
    _place(page, _open_image(path), geometry.content_box(dpi), options.fit)
    yield page


# --- PDF ------------------------------------------------------------------


def iter_pdf_pages(
    path: Path, geometry: Geometry, options: RenderOptions, on_total=None
) -> Iterator[Image.Image]:
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:  # pragma: no cover
        raise RenderFailed("PDF desteği için pypdfium2 kurulu değil.") from exc

    dpi = render_dpi_for(geometry, options.render_dpi)
    try:
        document = pdfium.PdfDocument(str(path))
    except Exception as exc:  # noqa: BLE001
        raise RenderFailed("PDF açılamadı; dosya bozuk olabilir.", detail=str(exc)) from exc

    try:
        total = len(document)
        if total == 0:
            raise RenderFailed("PDF boş.")
        selected = parse_page_range(options.page_range, total)
        if len(selected) > options.max_pages:
            raise InvalidOptions(
                f"Seçilen {len(selected)} sayfa sınırı aşıyor (en çok {options.max_pages})."
            )
        if on_total:
            on_total(len(selected))

        width, height = geometry.canvas_size(dpi)
        box = geometry.content_box(dpi)
        for page_no in selected:
            try:
                bitmap = document[page_no - 1].render(scale=dpi / 72)
                img = bitmap.to_pil().convert("RGB")
            except Exception as exc:  # noqa: BLE001
                raise RenderFailed(
                    f"PDF {page_no}. sayfa çizilemedi.", detail=str(exc)
                ) from exc
            page = Image.new("RGB", (width, height), "white")
            _place(page, img, box, "fit")
            yield page
    finally:
        try:
            document.close()
        except Exception:
            pass


# --- giriş noktası --------------------------------------------------------


def iter_pages(
    path: Path,
    kind: str,
    geometry: Geometry,
    options: RenderOptions,
    on_total=None,
) -> Iterator[Image.Image]:
    if kind == "image":
        yield from iter_image_pages(path, geometry, options, on_total)
    elif kind == "text":
        yield from iter_text_pages(path, geometry, options, on_total)
    elif kind == "pdf":
        yield from iter_pdf_pages(path, geometry, options, on_total)
    else:
        raise RenderFailed(f"Desteklenmeyen içerik türü: {kind}")

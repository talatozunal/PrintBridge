#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PrintBridge — M0 spike.

Tek bir görseli (veya kalibrasyon sayfasını) Windows yazdırma kuyruğu üzerinden
USB yazıcıya basar. Amaç: sürücü + DEVMODE + GDI davranışını doğrulamak.

Örnekler
--------
    py -3 tools\\m0_spike.py --list
    py -3 tools\\m0_spike.py --info
    py -3 tools\\m0_spike.py --dry-run --preview kalibrasyon.png
    py -3 tools\\m0_spike.py
    py -3 tools\\m0_spike.py foto.jpg --copies 2 --orientation landscape
    py -3 tools\\m0_spike.py foto.jpg --paper Letter --fit fill --margin-mm 5

Not: --dry-run baskı yapmaz, sadece hesaplanan sayfayı ve raporu üretir.
"""

from __future__ import annotations

import argparse
import ctypes
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

try:
    import win32con
    import win32gui
    import win32print
    import win32ui
    from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageWin
except ImportError as exc:  # pragma: no cover
    sys.exit(
        f"Eksik modül: {exc.name}\n"
        "Kurulum:  py -3 -m pip install pywin32 Pillow"
    )

# --- sabitler -------------------------------------------------------------

DMPAPER = {"A4": 9, "LETTER": 1, "LEGAL": 5, "A5": 11, "A3": 8}

DM_PAPERSIZE = getattr(win32con, "DM_PAPERSIZE", 0x00000002)
DM_ORIENTATION = getattr(win32con, "DM_ORIENTATION", 0x00000001)
DM_COPIES = getattr(win32con, "DM_COPIES", 0x00000100)
DMORIENT_PORTRAIT = getattr(win32con, "DMORIENT_PORTRAIT", 1)
DMORIENT_LANDSCAPE = getattr(win32con, "DMORIENT_LANDSCAPE", 2)

CAP = {
    "HORZRES": getattr(win32con, "HORZRES", 8),
    "VERTRES": getattr(win32con, "VERTRES", 10),
    "LOGPIXELSX": getattr(win32con, "LOGPIXELSX", 88),
    "LOGPIXELSY": getattr(win32con, "LOGPIXELSY", 90),
    "PHYSICALWIDTH": getattr(win32con, "PHYSICALWIDTH", 110),
    "PHYSICALHEIGHT": getattr(win32con, "PHYSICALHEIGHT", 111),
    "PHYSICALOFFSETX": getattr(win32con, "PHYSICALOFFSETX", 112),
    "PHYSICALOFFSETY": getattr(win32con, "PHYSICALOFFSETY", 113),
}

PRINTER_STATUS = {
    0x00000001: "duraklatılmış",
    0x00000002: "hata",
    0x00000008: "kâğıt sıkışması",
    0x00000010: "kâğıt bitti",
    0x00000020: "kâğıt sorunu",
    0x00000040: "kâğıt yolu sorunu",
    0x00000080: "çevrimdışı",
    0x00000200: "çıktı kuyruğu dolu",
    0x00040000: "toner bitti",
    0x00080000: "kapak açık",
    0x00100000: "kullanıcı müdahalesi gerekiyor",
    0x40000000: "yazıcı hatası",
}

MM_PER_INCH = 25.4

_gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
_gdi32.GetDeviceCaps.argtypes = (ctypes.c_void_p, ctypes.c_int)
_gdi32.GetDeviceCaps.restype = ctypes.c_int


def get_device_caps(hdc: int, index: int) -> int:
    return int(_gdi32.GetDeviceCaps(ctypes.c_void_p(int(hdc)), index))


# --- küçük yardımcılar ----------------------------------------------------


def log(msg: str = "") -> None:
    print(msg, flush=True)


def mm_to_px(mm: float, dpi: int) -> int:
    return int(round(mm * dpi / MM_PER_INCH))


def px_to_mm(px: int, dpi: int) -> float:
    return px * MM_PER_INCH / dpi


def printer_status_text(status: int) -> str:
    if status == 0:
        return "hazır"
    labels = [text for bit, text in PRINTER_STATUS.items() if status & bit]
    return ", ".join(labels) if labels else f"bilinmeyen (0x{status:08X})"


def list_printers() -> list[str]:
    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    return [p[2] for p in win32print.EnumPrinters(flags, None, 1)]


# --- yazıcı bilgisi -------------------------------------------------------


@dataclass
class PrinterInfo:
    name: str
    driver: str
    port: str
    status: int
    jobs: int
    papers: dict[str, int]


def read_printer(name: str) -> PrinterInfo:
    try:
        handle = win32print.OpenPrinter(name)
    except Exception as exc:  # pywintypes.error
        raise SystemExit(
            f"Yazıcı açılamadı: {name}\n{exc}\n\nBulunan yazıcılar:\n  "
            + "\n  ".join(list_printers())
        ) from exc

    try:
        data = win32print.GetPrinter(handle, 2)
    finally:
        win32print.ClosePrinter(handle)

    papers: dict[str, int] = {}
    try:
        ids = win32print.DeviceCapabilities(name, data["pPortName"], 2)  # DC_PAPERS
        names = win32print.DeviceCapabilities(name, data["pPortName"], 16)  # DC_PAPERNAMES
        for paper_id, paper_name in zip(ids, names):
            papers[str(paper_name).strip()] = int(paper_id)
    except Exception:
        papers = dict(DMPAPER)

    return PrinterInfo(
        name=name,
        driver=data["pDriverName"],
        port=data["pPortName"],
        status=data["Status"],
        jobs=data["cJobs"],
        papers=papers,
    )


# --- sayfa geometrisi -----------------------------------------------------


@dataclass
class Layout:
    dpi_x: int
    dpi_y: int
    printable_w: int
    printable_h: int
    physical_w: int
    physical_h: int
    hard_offset_x: int
    hard_offset_y: int
    margin_px: int
    content: tuple[int, int, int, int]

    @property
    def compose_dpi(self) -> int:
        """Sayfayı hangi çözünürlükte üreteceğiz (1:1 baskı için cihaz DPI'ı)."""
        return min(self.dpi_x, 600)

    def describe(self) -> str:
        dpi = self.dpi_x
        return (
            f"  Yazdırılabilir alan : {px_to_mm(self.printable_w, dpi):.1f} × "
            f"{px_to_mm(self.printable_h, dpi):.1f} mm  "
            f"({self.printable_w} × {self.printable_h} px @ {dpi} dpi)\n"
            f"  Fiziksel kâğıt     : {px_to_mm(self.physical_w, dpi):.1f} × "
            f"{px_to_mm(self.physical_h, dpi):.1f} mm\n"
            f"  Sürücü kenar payı  : sol {px_to_mm(self.hard_offset_x, dpi):.1f} mm, "
            f"üst {px_to_mm(self.hard_offset_y, dpi):.1f} mm\n"
            f"  Bizim kenar boşluğu: {px_to_mm(self.margin_px, dpi):.1f} mm\n"
            f"  İçerik alanı       : {self.content[2] - self.content[0]} × "
            f"{self.content[3] - self.content[1]} px"
        )


def build_layout(hdc: int, margin_mm: float) -> Layout:
    # HDC'nin sahibi çağıran taraftır; burada sadece sorguluyoruz.
    caps = {key: get_device_caps(hdc, value) for key, value in CAP.items()}

    dpi_x = caps["LOGPIXELSX"] or 600
    dpi_y = caps["LOGPIXELSY"] or 600
    # Bazı sürücüler LOGPIXELS'i garip döndürür; baskı için 300–1200 bandına sıkıştır.
    dpi_x = max(300, min(dpi_x, 1200))
    dpi_y = max(300, min(dpi_y, 1200))

    margin_px = mm_to_px(margin_mm, dpi_x)
    content = (
        margin_px,
        margin_px,
        caps["HORZRES"] - margin_px,
        caps["VERTRES"] - margin_px,
    )
    if content[2] <= content[0] or content[3] <= content[1]:
        raise SystemExit("Kenar boşluğu sayfayı kapladı; --margin-mm değerini küçültün.")

    return Layout(
        dpi_x=dpi_x,
        dpi_y=dpi_y,
        printable_w=caps["HORZRES"],
        printable_h=caps["VERTRES"],
        physical_w=caps["PHYSICALWIDTH"] or caps["HORZRES"],
        physical_h=caps["PHYSICALHEIGHT"] or caps["VERTRES"],
        hard_offset_x=caps["PHYSICALOFFSETX"],
        hard_offset_y=caps["PHYSICALOFFSETY"],
        margin_px=margin_px,
        content=content,
    )


# --- görsel hazırlama -----------------------------------------------------


def load_image(path: Path) -> Image.Image:
    try:
        img = Image.open(path)
    except Exception as exc:
        raise SystemExit(f"Görsel açılamadı: {path}\n{exc}") from exc

    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        background = Image.new("RGB", img.size, "white")
        background.paste(img, mask=img.split()[-1])
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")
    return img


def place_image(page: Image.Image, img: Image.Image, box: tuple[int, int, int, int], fit: str) -> None:
    """Görseli kutuya 'fit' (tamamı görünür) veya 'fill' (kırparak doldur) yerleştir."""
    x0, y0, x1, y1 = box
    box_w, box_h = x1 - x0, y1 - y0
    src_w, src_h = img.size
    scale = min(box_w / src_w, box_h / src_h) if fit == "fit" else max(box_w / src_w, box_h / src_h)

    new_w = max(1, int(round(src_w * scale)))
    new_h = max(1, int(round(src_h * scale)))
    resample = Image.Resampling.LANCZOS if scale < 1 else Image.Resampling.BICUBIC
    scaled = img.resize((new_w, new_h), resample)

    left = x0 + (box_w - new_w) // 2
    top = y0 + (box_h - new_h) // 2

    if fit == "fill":
        # Kutu dışına taşan kısmı kırp.
        crop = (
            max(0, -left),
            max(0, -top),
            new_w - max(0, left + new_w - x1),
            new_h - max(0, top + new_h - y1),
        )
        scaled = scaled.crop(crop)
        left = max(left, x0)
        top = max(top, y0)

    page.paste(scaled, (left, top))


def load_font(px: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    fonts_dir = Path("C:/Windows/Fonts")
    candidates = (
        ["arialbd.ttf", "segoeuib.ttf", "calibrib.ttf"]
        if bold
        else ["arial.ttf", "segoeui.ttf", "calibri.ttf"]
    )
    for name in candidates:
        path = fonts_dir / name
        if path.exists():
            return ImageFont.truetype(str(path), px)
    return ImageFont.load_default(size=px)


def compose_calibration(layout: Layout, info: PrinterInfo, args: argparse.Namespace) -> Image.Image:
    dpi = layout.compose_dpi
    scale = dpi / layout.dpi_x  # layout ölçüleri cihaz px; sayfa dpi'ı farklıysa ölçekle

    page_w = int(round(layout.printable_w * scale))
    page_h = int(round(layout.printable_h * scale))
    page = Image.new("RGB", (page_w, page_h), "white")
    draw = ImageDraw.Draw(page)

    def px(mm: float) -> int:
        return mm_to_px(mm, dpi)

    margin = int(round(layout.margin_px * scale))
    x0, y0 = margin, margin
    x1, y1 = page_w - margin, page_h - margin

    # Kenar çerçeveleri: dış = sürücü sınırı, iç = bizim kenar boşluğu.
    draw.rectangle([0, 0, page_w - 1, page_h - 1], outline=(200, 200, 200), width=max(1, px(0.2)))
    draw.rectangle([x0, y0, x1, y1], outline=(0, 0, 0), width=max(1, px(0.35)))

    # 10 mm cetvel (üst ve sol).
    ruler = px(10)
    for i, x in enumerate(range(x0, x1 + 1, ruler)):
        length = px(4) if i % 5 == 0 else px(2)
        draw.line([(x, y0), (x, y0 + length)], fill=(120, 120, 120), width=1)
    for i, y in enumerate(range(y0, y1 + 1, ruler)):
        length = px(4) if i % 5 == 0 else px(2)
        draw.line([(x0, y), (x0 + length, y)], fill=(120, 120, 120), width=1)

    # 5 mm köşe kareleri: fotoğrafın gerçekten nereden başladığını gözle doğrulamak için.
    sq = px(5)
    draw.rectangle([x0, y0, x0 + sq, y0 + sq], outline=(0, 0, 0), width=1)
    draw.rectangle([x1 - sq, y1 - sq, x1, y1], outline=(0, 0, 0), width=1)

    title_font = load_font(px(7), bold=True)
    head_font = load_font(px(4.2), bold=True)
    body_font = load_font(px(3.6))
    small_font = load_font(px(2.8))

    left = x0 + px(6)
    top = y0 + px(8)
    line_h = px(5.4)

    draw.text((left, top), "PrintBridge M0 — Kalibrasyon Sayfası", font=title_font, fill=(0, 0, 0))
    top += px(11)

    draw.text((left, top), "Yazıcı", font=head_font, fill=(0, 0, 0))
    top += line_h
    for label, value in [
        ("Ad", info.name),
        ("Sürücü", info.driver),
        ("Port", info.port),
        ("Durum", printer_status_text(info.status)),
        ("Kâğıt", f"{args.paper} · {args.orientation} · {args.copies} kopya"),
        ("Çözünürlük", f"{layout.dpi_x} × {layout.dpi_y} dpi"),
        ("Tarih", datetime.now().strftime("%d.%m.%Y %H:%M:%S")),
    ]:
        draw.text((left, top), f"{label:<12}: {value}", font=body_font, fill=(0, 0, 0))
        top += line_h * 0.78

    top += px(4)
    draw.text((left, top), "Ölçüm", font=head_font, fill=(0, 0, 0))
    top += line_h
    for line in layout.describe().strip().splitlines():
        draw.text((left, top), line.strip(), font=small_font, fill=(40, 40, 40))
        top += line_h * 0.72

    # Türkçe karakter testi.
    top += px(3)
    draw.text((left, top), "Türkçe karakter testi", font=head_font, fill=(0, 0, 0))
    top += line_h
    draw.text(
        (left, top),
        "ş ğ ı İ ö ç ü Ş Ğ I Ö Ç Ü  —  1234567890  —  %&@#()[]{}",
        font=body_font,
        fill=(0, 0, 0),
    )
    top += line_h * 1.4
    draw.text(
        (left, top),
        "Bu satırlar kesilmeden, çerçevenin içinde ve düz okunuyorsa yön doğru.",
        font=small_font,
        fill=(60, 60, 60),
    )

    # Gri tonlama rampası.
    top += px(8)
    ramp_h = px(12)
    steps = 11
    step_w = (x1 - x0 - px(12)) // steps
    for i in range(steps):
        value = int(round(255 * i / (steps - 1)))
        rx = left + i * step_w
        draw.rectangle([rx, top, rx + step_w - 2, top + ramp_h], fill=(value, value, value))
        label = f"{int(round(100 * i / (steps - 1)))}%"
        draw.text((rx + px(0.5), top + ramp_h + px(1)), label, font=small_font, fill=(0, 0, 0))

    # Geometri testi: daire + çapraz.
    top += ramp_h + px(8)
    size = min(px(60), page_h - top - px(20))
    if size > px(10):
        cx, cy = left + size // 2, top + size // 2
        draw.ellipse([cx - size // 2, cy - size // 2, cx + size // 2, cy + size // 2], outline=(0, 0, 0), width=max(1, px(0.3)))
        draw.line([(cx - size // 2, cy - size // 2), (cx + size // 2, cy + size // 2)], fill=(0, 0, 0), width=max(1, px(0.2)))
        draw.line([(cx - size // 2, cy + size // 2), (cx + size // 2, cy - size // 2)], fill=(0, 0, 0), width=max(1, px(0.2)))
        draw.text((cx + size // 2 + px(6), cy - px(2)), "Daire yuvarlak ve\nçaprazlar düz mü?", font=small_font, fill=(0, 0, 0))

    draw.text(
        (left, y1 - px(9)),
        "PrintBridge M0 · Bu sayfa sürücü/GDI doğrulaması için üretildi.",
        font=small_font,
        fill=(90, 90, 90),
    )
    return page


def compose_photo(layout: Layout, path: Path, args: argparse.Namespace) -> Image.Image:
    dpi = layout.compose_dpi
    scale = dpi / layout.dpi_x

    page_w = int(round(layout.printable_w * scale))
    page_h = int(round(layout.printable_h * scale))
    page = Image.new("RGB", (page_w, page_h), "white")

    img = load_image(path)
    box = tuple(int(round(v * scale)) for v in layout.content)
    place_image(page, img, box, args.fit)
    return page


# --- baskı ----------------------------------------------------------------


def print_page(
    printer_name: str,
    devmode,
    page: Image.Image,
    layout: Layout,
    job_title: str,
    dry_run: bool,
) -> int | None:
    if dry_run:
        return None

    hdc = None
    dc = None
    started = False
    try:
        hdc = win32gui.CreateDC("WINSPOOL", printer_name, devmode)
        if not hdc:
            raise RuntimeError("CreateDC başarısız (geçersiz yazıcı adı veya sürücü?)")
        dc = win32ui.CreateDCFromHandle(hdc)
        job_id = dc.StartDoc(job_title)
        started = True
        dc.StartPage()
        dib = ImageWin.Dib(page)
        dib.draw(hdc, (0, 0, layout.printable_w, layout.printable_h))
        dc.EndPage()
        dc.EndDoc()
        started = False
        return job_id
    except Exception:
        if started and dc is not None:
            try:
                dc.AbortDoc()
            except Exception:
                pass
        raise
    finally:
        if dc is not None:
            try:
                dc.DeleteDC()
            except Exception:
                pass
        elif hdc:
            try:
                win32gui.DeleteDC(hdc)
            except Exception:
                pass


def apply_devmode(printer_name: str, args: argparse.Namespace):
    handle = win32print.OpenPrinter(printer_name)
    try:
        devmode = win32print.GetPrinter(handle, 2)["pDevMode"]
    finally:
        win32print.ClosePrinter(handle)

    if devmode is None:
        raise SystemExit("Sürücü DEVMODE döndürmedi; bu yazıcıyla GDI baskı desteklenmiyor olabilir.")

    fields = 0
    if args.paper:
        devmode.PaperSize = DMPAPER[args.paper.upper()]
        fields |= DM_PAPERSIZE
    if args.orientation in ("portrait", "landscape"):
        devmode.Orientation = DMORIENT_LANDSCAPE if args.orientation == "landscape" else DMORIENT_PORTRAIT
        fields |= DM_ORIENTATION
    if args.copies > 0:
        devmode.Copies = args.copies
        fields |= DM_COPIES
    devmode.Fields = fields
    return devmode


# --- CLI ------------------------------------------------------------------


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PrintBridge M0 — görsel veya kalibrasyon sayfası bastırır.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("image", nargs="?", type=Path, help="JPEG/PNG/BMP dosyası (boşsa kalibrasyon sayfası)")
    parser.add_argument("--printer", default=None, help="Yazıcı adı (varsayılan: Windows varsayılan yazıcısı)")
    parser.add_argument("--paper", default="A4", choices=[p.lower() for p in DMPAPER] + list(DMPAPER))
    parser.add_argument("--orientation", default="portrait", choices=["portrait", "landscape", "auto"])
    parser.add_argument("--copies", type=int, default=1)
    parser.add_argument("--margin-mm", type=float, default=10.0)
    parser.add_argument("--fit", default="fit", choices=["fit", "fill"])
    parser.add_argument("--preview", type=Path, default=None, help="Sayfayı PNG olarak kaydet")
    parser.add_argument("--dry-run", action="store_true", help="Baskı yapma, sadece rapor/önizleme")
    parser.add_argument("--list", action="store_true", help="Yazıcıları listele ve çık")
    parser.add_argument("--info", action="store_true", help="Sürücü/kâğıt bilgisini göster ve çık")
    parser.add_argument("--yes", action="store_true", help="Onay sormadan bas")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    args = parse_args(argv)
    args.paper = args.paper.upper()

    if args.list:
        printers = list_printers()
        default = win32print.GetDefaultPrinter()
        for name in printers:
            print(f"{'*' if name == default else ' '} {name}")
        return 0

    printer_name = args.printer or win32print.GetDefaultPrinter()

    # "auto" yön: görsel yataysa yatay sayfa.
    if args.orientation == "auto":
        if args.image and args.image.exists():
            try:
                with Image.open(args.image) as probe:
                    args.orientation = "landscape" if probe.width > probe.height else "portrait"
            except Exception:
                args.orientation = "portrait"
        else:
            args.orientation = "portrait"

    info = read_printer(printer_name)

    if args.info:
        log(f"Yazıcı : {info.name}")
        log(f"Sürücü : {info.driver}")
        log(f"Port   : {info.port}")
        log(f"Durum  : {printer_status_text(info.status)}")
        log(f"Kuyruk : {info.jobs} iş")
        log("Kâğıtlar:")
        for name, paper_id in info.papers.items():
            log(f"  {name:<18} id={paper_id}")
        return 0

    started = time.perf_counter()
    devmode = apply_devmode(printer_name, args)

    hdc = win32gui.CreateDC("WINSPOOL", printer_name, devmode)
    if not hdc:
        raise SystemExit("CreateDC başarısız: yazıcı adı veya sürücü geçersiz.")
    try:
        # NOT: build_layout kendi DC'sini oluşturup siler; cihaz ölçüleri aynı olduğu için sorun yok.
        layout = build_layout(hdc, args.margin_mm)
    finally:
        win32gui.DeleteDC(hdc)

    log(f"Yazıcı : {info.name}")
    log(f"Sürücü : {info.driver}  ·  Port: {info.port}")
    log(f"Durum  : {printer_status_text(info.status)}")
    log(f"Kâğıt  : {args.paper}  ·  {args.orientation}  ·  {args.copies} kopya  ·  {args.fit}")
    log(layout.describe())

    if info.status & 0x00000080:
        log("\nUYARI: Yazıcı çevrimdışı görünüyor. USB kablosunu ve gücü kontrol edin.")

    if args.image:
        if not args.image.exists():
            raise SystemExit(f"Dosya bulunamadı: {args.image}")
        log(f"\nGörsel hazırlanıyor: {args.image}")
        page = compose_photo(layout, args.image, args)
    else:
        log("\nKalibrasyon sayfası hazırlanıyor…")
        page = compose_calibration(layout, info, args)

    if args.preview:
        args.preview.parent.mkdir(parents=True, exist_ok=True)
        page.save(args.preview)
        log(f"Önizleme kaydedildi: {args.preview.resolve()}  ({page.width}×{page.height})")

    if args.dry_run:
        log(f"\n--dry-run: baskı yapılmadı. Süre {time.perf_counter() - started:.2f} sn")
        return 0

    if not args.yes:
        answer = input(f"\n'{printer_name}' yazıcısına gönderilsin mi? [e/H] ").strip().lower()
        if answer not in ("e", "evet", "y", "yes"):
            log("İptal edildi.")
            return 1

    prep = time.perf_counter() - started
    log("\nYazdırma kuyruğuna gönderiliyor…")
    job_id = print_page(
        printer_name,
        devmode,
        page,
        layout,
        job_title=f"PrintBridge M0 {datetime.now():%H:%M:%S}",
        dry_run=False,
    )
    total = time.perf_counter() - started
    log(f"Kuyruğa verildi. İş kimliği: {job_id}")
    log(f"Hazırlık {prep:.2f} sn · toplam {total:.2f} sn · sayfa {page.width}×{page.height}")
    log("\nYazıcıdan çıkan sayfayı kontrol edin:")
    log("  1) Çerçeve kâğıdın kenarına yapışık mı, 10 mm boşluk var mı?")
    log("  2) Yazılar düz ve kesiksiz mi (yön doğru mu)?")
    log("  3) Türkçe karakterler (ş ğ ı İ) doğru mu?")
    log("  4) Gri rampa 11 ayrı kutu halinde mi?")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        raise SystemExit(130)

# -*- coding: utf-8 -*-
"""Windows yazıcı erişimi: numaralandırma, DEVMODE, sayfa geometrisi, GDI baskı.

Baskı hattı (bkz. docs/PLAN.md §4):
    sayfa görüntüsü (PIL)  →  StretchDIBits  →  sürücü  →  USB
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass, field
from typing import Callable, Iterable

import win32con
import win32gui
import win32print
import win32ui
from PIL import Image, ImageWin

from .errors import InvalidOptions, JobCanceled, PrinterUnavailable, SpoolFailed

MM_PER_INCH = 25.4

DMPAPER_FALLBACK = {
    "LETTER": 1,
    "LEGAL": 5,
    "A3": 8,
    "A4": 9,
    "A5": 11,
    "B4": 12,
    "B5": 13,
    "EXECUTIVE": 7,
}

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

STATUS_BITS = {
    0x00000001: "paused",
    0x00000002: "error",
    0x00000008: "paper_jam",
    0x00000010: "paper_out",
    0x00000020: "paper_problem",
    0x00000080: "offline",
    0x00000200: "busy",
    0x00040000: "no_toner",
    0x00080000: "door_open",
    0x00100000: "user_intervention",
    0x00400000: "no_toner",
}

_gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
_gdi32.GetDeviceCaps.argtypes = (ctypes.c_void_p, ctypes.c_int)
_gdi32.GetDeviceCaps.restype = ctypes.c_int


def get_device_caps(hdc: int, index: int) -> int:
    return int(_gdi32.GetDeviceCaps(ctypes.c_void_p(int(hdc)), index))


def mm_to_px(mm: float, dpi: int) -> int:
    return int(round(mm * dpi / MM_PER_INCH))


def px_to_mm(px: float, dpi: int) -> float:
    return px * MM_PER_INCH / dpi


# --- geometri -------------------------------------------------------------


@dataclass(frozen=True)
class Geometry:
    """Sürücünün bildirdiği yazdırılabilir alan + kullanıcı kenar boşluğu."""

    printable_w_px: int
    printable_h_px: int
    dpi_x: int
    dpi_y: int
    margin_mm: float = 10.0

    @property
    def dpi(self) -> int:
        return self.dpi_x

    @property
    def page_w_mm(self) -> float:
        return px_to_mm(self.printable_w_px, self.dpi_x)

    @property
    def page_h_mm(self) -> float:
        return px_to_mm(self.printable_h_px, self.dpi_y)

    def canvas_size(self, dpi: int) -> tuple[int, int]:
        return mm_to_px(self.page_w_mm, dpi), mm_to_px(self.page_h_mm, dpi)

    def content_box(self, dpi: int) -> tuple[int, int, int, int]:
        width, height = self.canvas_size(dpi)
        margin = mm_to_px(self.margin_mm, dpi)
        if width - 2 * margin < 50 or height - 2 * margin < 50:
            margin = 0
        return margin, margin, width - margin, height - margin

    def describe(self) -> str:
        return (
            f"{self.page_w_mm:.1f} × {self.page_h_mm:.1f} mm @ {self.dpi_x} dpi "
            f"({self.printable_w_px} × {self.printable_h_px} px), "
            f"kenar {self.margin_mm:.1f} mm"
        )


# --- yazıcı bilgisi -------------------------------------------------------


@dataclass
class PrinterInfo:
    id: str
    name: str
    driver: str
    port: str
    status_bits: int = 0
    papers: dict[str, int] = field(default_factory=dict)
    is_default: bool = False

    @property
    def status(self) -> str:
        bits = self.status_bits
        if bits & 0x00000080:
            return "offline"
        if bits & (0x00000002 | 0x00000008 | 0x00000010 | 0x00040000 | 0x00080000 | 0x00400000):
            return "error"
        if bits & 0x00000200:
            return "busy"
        return "ready"

    @property
    def status_text(self) -> str:
        if self.status_bits == 0:
            return "hazır"
        labels = [text for bit, text in STATUS_BITS.items() if self.status_bits & bit]
        return ", ".join(labels) if labels else f"0x{self.status_bits:08X}"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "driver": self.driver,
            "port": self.port,
            "status": self.status,
            "statusText": self.status_text,
            "papers": sorted(self.papers.keys(), key=str.upper),
            "default": self.is_default,
            "duplex": False,
            "color": False,
        }


def printer_status_bits(name: str) -> int:
    handle = win32print.OpenPrinter(name)
    try:
        return int(win32print.GetPrinter(handle, 2).get("Status", 0))
    finally:
        win32print.ClosePrinter(handle)


def read_papers(name: str, port: str) -> dict[str, int]:
    papers: dict[str, int] = {}
    try:
        ids = win32print.DeviceCapabilities(name, port, 2)  # DC_PAPERS
        names = win32print.DeviceCapabilities(name, port, 16)  # DC_PAPERNAMES
        for paper_id, paper_name in zip(ids, names):
            papers[str(paper_name).strip()] = int(paper_id)
    except Exception:
        pass
    return papers or dict(DMPAPER_FALLBACK)


class WindowsBackend:
    """Gerçek Windows yazıcı arka ucu. Testlerde FakeBackend kullanılır."""

    # --- keşif ------------------------------------------------------------

    def list_printers(self) -> list[PrinterInfo]:
        flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        try:
            default = win32print.GetDefaultPrinter()
        except Exception:
            default = None

        result: list[PrinterInfo] = []
        for entry in win32print.EnumPrinters(flags, None, 2):
            name = entry["pPrinterName"]
            handle = win32print.OpenPrinter(name)
            try:
                record = win32print.GetPrinter(handle, 2)
            finally:
                win32print.ClosePrinter(handle)
            result.append(
                PrinterInfo(
                    id=name,
                    name=name,
                    driver=entry.get("pDriverName") or record.get("pDriverName", ""),
                    port=entry.get("pPortName") or record.get("pPortName", ""),
                    status_bits=int(entry.get("Status", 0)),
                    papers=read_papers(name, record.get("pPortName", "")),
                    is_default=(name == default),
                )
            )
        return result

    def get_printer(self, name: str) -> PrinterInfo:
        for printer in self.list_printers():
            if printer.id == name or printer.name == name:
                return printer
        raise PrinterUnavailable(
            f"Yazıcı bulunamadı: {name}",
            code="printer_not_found",
            detail="Yazıcı USB'den çıkarılmış veya adı değişmiş olabilir.",
        )

    def default_printer(self) -> PrinterInfo | None:
        for printer in self.list_printers():
            if printer.is_default:
                return printer
        printers = self.list_printers()
        return printers[0] if printers else None

    # --- DEVMODE ----------------------------------------------------------

    def make_devmode(self, printer: PrinterInfo, paper: str, orientation: str):
        handle = win32print.OpenPrinter(printer.id)
        try:
            devmode = win32print.GetPrinter(handle, 2)["pDevMode"]
        finally:
            win32print.ClosePrinter(handle)
        if devmode is None:
            raise SpoolFailed("Sürücü DEVMODE döndürmedi; bu yazıcı GDI ile yazdırılamıyor.")

        fields = 0
        paper_key = (paper or "auto").strip()
        if paper_key and paper_key.lower() != "auto":
            paper_id = None
            for name, value in printer.papers.items():
                if name.upper() == paper_key.upper():
                    paper_id = value
                    break
            if paper_id is None:
                paper_id = DMPAPER_FALLBACK.get(paper_key.upper())
            if paper_id is None:
                supported = ", ".join(sorted(printer.papers, key=str.upper)) or "A4, Letter"
                raise InvalidOptions(
                    f"Yazıcı '{paper_key}' kâğıdını desteklemiyor. Desteklenenler: {supported}"
                )
            devmode.PaperSize = paper_id
            fields |= DM_PAPERSIZE

        if orientation in ("portrait", "landscape"):
            devmode.Orientation = (
                DMORIENT_LANDSCAPE if orientation == "landscape" else DMORIENT_PORTRAIT
            )
            fields |= DM_ORIENTATION

        # Kopyaları uygulama tarafında çeviriyoruz (sürücüye güvenmiyoruz).
        devmode.Copies = 1
        fields |= DM_COPIES
        devmode.Fields = fields
        return devmode

    # --- geometri ---------------------------------------------------------

    def geometry(self, hdc: int, margin_mm: float) -> Geometry:
        caps = {key: get_device_caps(hdc, value) for key, value in CAP.items()}
        dpi_x = max(300, min(caps["LOGPIXELSX"] or 600, 1200))
        dpi_y = max(300, min(caps["LOGPIXELSY"] or 600, 1200))
        return Geometry(
            printable_w_px=caps["HORZRES"],
            printable_h_px=caps["VERTRES"],
            dpi_x=dpi_x,
            dpi_y=dpi_y,
            margin_mm=margin_mm,
        )

    def preview_geometry(self, printer_name: str, options: dict, margin_mm: float = 10.0) -> Geometry:
        """Baskı yapmadan, sürücünün gerçek sayfa ölçüsünü öğren (önizleme için)."""
        printer = self.get_printer(printer_name)
        devmode = self.make_devmode(
            printer, options.get("paper", "A4"), options.get("orientation", "auto")
        )
        hdc = win32gui.CreateDC("WINSPOOL", printer.id, devmode)
        if not hdc:
            raise PrinterUnavailable("Önizleme için yazıcı bağlamı oluşturulamadı.")
        try:
            return self.geometry(hdc, margin_mm)
        finally:
            win32gui.DeleteDC(hdc)

    # --- baskı ------------------------------------------------------------

    def print_job(
        self,
        printer_name: str,
        options: dict,
        pages_factory: Callable[[Geometry], Iterable[Image.Image]],
        title: str,
        margin_mm: float = 10.0,
        on_page: Callable[[int], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> int:
        printer = self.get_printer(printer_name)
        if printer.status in ("offline", "error"):
            raise PrinterUnavailable(
                "Yazıcı hazır değil: " + printer.status_text,
                detail=f"status=0x{printer.status_bits:08X}",
            )

        devmode = self.make_devmode(
            printer, options.get("paper", "A4"), options.get("orientation", "auto")
        )
        copies = int(options.get("copies", 1) or 1)

        hdc = win32gui.CreateDC("WINSPOOL", printer.id, devmode)
        if not hdc:
            raise SpoolFailed("Yazdırma aygıtı bağlamı (DC) oluşturulamadı.")

        dc = None
        doc_open = False
        printed = 0
        try:
            geometry = self.geometry(hdc, margin_mm)
            dc = win32ui.CreateDCFromHandle(hdc)
            for _copy in range(copies):
                dc.StartDoc(title)
                doc_open = True
                try:
                    for page in pages_factory(geometry):
                        if should_cancel and should_cancel():
                            raise JobCanceled()
                        dc.StartPage()
                        ImageWin.Dib(page).draw(
                            hdc, (0, 0, geometry.printable_w_px, geometry.printable_h_px)
                        )
                        dc.EndPage()
                        printed += 1
                        if on_page:
                            on_page(printed)
                except Exception:
                    if doc_open:
                        try:
                            dc.AbortDoc()
                        except Exception:
                            pass
                        doc_open = False
                    raise
                dc.EndDoc()
                doc_open = False
            return printed
        except JobCanceled:
            raise
        except (PrinterUnavailable, InvalidOptions, SpoolFailed):
            raise
        except Exception as exc:  # pywintypes.error vb.
            raise map_windows_error(exc) from exc
        finally:
            if dc is not None:
                try:
                    dc.DeleteDC()
                except Exception:
                    pass
            try:
                win32gui.DeleteDC(hdc)
            except Exception:
                pass


def map_windows_error(exc: Exception) -> SpoolFailed:
    """Windows/spooler hata kodlarını kullanıcıya anlamlı mesaja çevirir."""
    code = getattr(exc, "winerror", None)
    if code is None:
        args = getattr(exc, "args", ())
        code = args[0] if args and isinstance(args[0], int) else 0

    messages = {
        2: "Yazdırma dosyası bulunamadı.",
        5: "Yazıcıya erişim reddedildi (yönetici izni veya sürücü kısıtı).",
        6: "Geçersiz yazdırma tutamacı; yazıcı bağlantısı koptu.",
        8: "Bellek yetersiz; daha küçük bir dosya deneyin.",
        87: "Sürücü geçersiz bir parametre bildirdi (kâğıt/yön).",
        1722: "Yazdırma servisi (Print Spooler) çalışmıyor.",
        1726: "Yazdırma servisiyle bağlantı kurulamadı.",
        1801: "Yazıcı adı geçersiz; yazıcı kaldırılmış olabilir.",
        1803: "Yazıcı bulunamadı; USB bağlantısını kontrol edin.",
        3010: "Sürücü yeniden başlatma bekliyor.",
    }
    detail = f"{type(exc).__name__}: {exc}"
    if code:
        detail = f"winerror={code} (0x{code:04X}) · {detail}"
    return SpoolFailed(messages.get(code, SpoolFailed.message), detail=detail)

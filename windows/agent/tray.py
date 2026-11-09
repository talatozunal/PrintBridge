# -*- coding: utf-8 -*-
"""PrintBridge Agent — Windows tepsi uygulaması.

Sunucuyu arka planda başlatır; simge menüsünden PIN, işler, ayarlar ve loglara
erişim verir. Tkinter ana iş parçacığında, pystray simgesi kendi iş
parçacığında çalışır; tüm pencere açma işlemleri kuyruk üzerinden ana iş
parçacığına aktarılır (Tk thread-safe değildir).

Çalıştırma:
    py -3 -m agent.tray
    py -3 -m agent.tray --diagnose
    py -3 -m agent.tray --autostart on
"""

from __future__ import annotations

import argparse
import logging
import os
import queue
import sys
import threading
import time
import tkinter as tk
import webbrowser
from io import BytesIO
from tkinter import messagebox, ttk
from typing import Callable

import pystray
import uvicorn
from PIL import Image, ImageDraw, ImageTk

from . import __version__, autostart, firewall
from .api import create_app
from .config import Config, default_data_dir, lan_addresses
from .discovery import Discovery, primary_address, qr_payload
from .instance import SingleInstance
from .logging_setup import setup_logging

log = logging.getLogger("printbridge.tray")

STATUS_TR = {
    "queued": "Bekliyor",
    "rendering": "Hazırlanıyor",
    "printing": "Basılıyor",
    "done": "Tamam",
    "failed": "Hata",
    "canceled": "İptal",
}


def make_icon_image() -> Image.Image:
    """64×64 tepsi simgesi: mavi zemin üzerinde beyaz yazıcı."""
    image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle([2, 2, 62, 62], radius=14, fill=(21, 87, 190, 255))
    draw.rectangle([18, 13, 46, 22], fill=(255, 255, 255, 255))
    draw.rounded_rectangle([12, 24, 52, 46], radius=4, fill=(255, 255, 255, 255))
    draw.rectangle([19, 38, 45, 55], fill=(21, 87, 190, 255))
    draw.rectangle([23, 42, 41, 51], fill=(255, 255, 255, 255))
    draw.ellipse([44, 28, 49, 33], fill=(21, 87, 190, 255))
    return image


class AgentRuntime:
    """Uvicorn sunucusunu arka plan iş parçacığında çalıştırır."""

    def __init__(self, config: Config):
        self.config = config
        self.app = create_app(config)
        self.backend = self.app.state.backend
        self.store = self.app.state.store
        self.worker = self.app.state.worker
        self.server = uvicorn.Server(
            uvicorn.Config(
                self.app,
                host=config.host,
                port=config.port,
                log_level="warning",
                access_log=False,
                log_config=None,
            )
        )
        self.thread = threading.Thread(target=self.server.run, name="printbridge-http", daemon=True)
        self.discovery: Discovery | None = None

    def start(self, timeout: float = 10.0) -> bool:
        self.thread.start()
        deadline = time.time() + timeout
        while time.time() < deadline:
            if getattr(self.server, "started", False):
                try:
                    printers = len(self.backend.list_printers())
                except Exception:  # noqa: BLE001
                    printers = 0
                self.discovery = Discovery(self.config, self.config.port, printers)
                self.discovery.start()
                return True
            if not self.thread.is_alive():
                return False
            time.sleep(0.05)
        return False

    def stop(self) -> None:
        if self.discovery is not None:
            self.discovery.stop()
        self.server.should_exit = True
        if self.thread.is_alive():
            self.thread.join(timeout=5)


class TrayController:
    def __init__(
        self, root: tk.Tk, runtime: AgentRuntime, icon: pystray.Icon, first_run: bool = False
    ):
        self.root = root
        self.runtime = runtime
        self.icon = icon
        self.config = runtime.config
        self.first_run = first_run
        self._actions: queue.Queue[Callable[[], None]] = queue.Queue()
        self._windows: dict[str, tk.Toplevel] = {}
        self.root.after(120, self._pump)

    # --- iş parçacığı köprüsü ---------------------------------------------

    def dispatch(self, action: Callable[[], None]) -> None:
        self._actions.put(action)

    def _pump(self) -> None:
        while True:
            try:
                action = self._actions.get_nowait()
            except queue.Empty:
                break
            try:
                action()
            except Exception:  # noqa: BLE001
                log.exception("Tepsi eylemi başarısız")
        self.root.after(120, self._pump)

    # --- menü --------------------------------------------------------------

    def build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem(lambda item: self.status_text(), None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Eşleştirme PIN'i", lambda item: self.dispatch(self.show_pin), default=True),
            pystray.MenuItem("QR ile eşleştir", lambda item: self.dispatch(self.show_qr)),
            pystray.MenuItem(
                lambda item: f"İşler ({self.runtime.store.queue_depth()} bekliyor)",
                lambda item: self.dispatch(self.show_jobs),
            ),
            pystray.MenuItem("Ayarlar", lambda item: self.dispatch(self.show_settings)),
            pystray.MenuItem("Kurulum sihirbazı", lambda item: self.dispatch(self.show_welcome)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Paneli aç", lambda item: self.dispatch(self.open_panel)),
            pystray.MenuItem("Logları aç", lambda item: self.dispatch(self.open_logs)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Çıkış", lambda item: self.dispatch(self.quit)),
        )

    def status_text(self) -> str:
        try:
            printers = self.runtime.backend.list_printers()
            printer = next((p for p in printers if p.is_default), printers[0] if printers else None)
            if printer is None:
                return "Yazıcı bulunamadı"
            state = "hazır" if printer.status == "ready" else printer.status_text
            return f"{printer.name} — {state}"
        except Exception:  # noqa: BLE001
            return "Durum alınamadı"

    # --- pencere yardımcısı ------------------------------------------------

    def _window(self, key: str, title: str, size: str, builder: Callable[[tk.Toplevel], None]) -> tk.Toplevel:
        existing = self._windows.get(key)
        if existing is not None and existing.winfo_exists():
            existing.deiconify()
            existing.lift()
            existing.focus_force()
            return existing

        window = tk.Toplevel(self.root)
        window.title(title)
        window.geometry(size)
        window.minsize(360, 220)
        self._windows[key] = window

        def close() -> None:
            self._windows.pop(key, None)
            window.destroy()

        window.protocol("WM_DELETE_WINDOW", close)
        builder(window)
        return window

    # --- PIN ---------------------------------------------------------------

    def show_pin(self) -> None:
        pairing = self.runtime.app.state.pairing

        def build(window: tk.Toplevel) -> None:
            window.resizable(False, False)
            window.attributes("-topmost", True)
            tk.Label(
                window,
                text="iPhone'daki PrintBridge uygulamasına bu PIN'i girin",
                wraplength=320,
            ).pack(padx=24, pady=(22, 8))

            pin_var = tk.StringVar(value=pairing.current())
            pin_label = tk.Label(window, textvariable=pin_var, font=("Consolas", 36, "bold"))
            pin_label.pack(padx=24, pady=4)

            info_var = tk.StringVar()
            tk.Label(window, textvariable=info_var, fg="#555").pack(pady=(0, 8))

            buttons = tk.Frame(window)
            buttons.pack(pady=(4, 20))

            def tick() -> None:
                if not window.winfo_exists():
                    return
                pin_var.set(pairing.current())
                info_var.set(f"Kalan süre: {pairing.seconds_left} sn")
                window.after(1000, tick)

            def refresh() -> None:
                pairing.refresh()
                tick()

            def copy() -> None:
                window.clipboard_clear()
                window.clipboard_append(pin_var.get())

            tk.Button(buttons, text="Yeni PIN", command=refresh).pack(side="left", padx=4)
            tk.Button(buttons, text="Kopyala", command=copy).pack(side="left", padx=4)
            tk.Button(buttons, text="Kapat", command=window.destroy).pack(side="left", padx=4)
            tick()

        self._window("pin", "Eşleştirme PIN'i", "380x300", build)

    # --- QR ----------------------------------------------------------------

    def show_qr(self) -> None:
        pairing = self.runtime.app.state.pairing

        def build(window: tk.Toplevel) -> None:
            window.resizable(False, False)
            window.attributes("-topmost", True)
            host = primary_address()

            image_label = tk.Label(window)
            image_label.pack(padx=18, pady=(16, 6))

            payload = qr_payload(self.config, host)
            try:
                import segno

                buffer = BytesIO()
                segno.make(payload, error="m").save(buffer, kind="png", scale=6, border=2)
                buffer.seek(0)
                photo = ImageTk.PhotoImage(Image.open(buffer))
                image_label.configure(image=photo)
                image_label.image = photo  # referansı tut
            except Exception as exc:  # noqa: BLE001
                log.warning("QR oluşturulamadı: %s", exc)
                image_label.configure(text="QR oluşturulamadı.\nAdresi elle girin.", pady=60)

            tk.Label(
                window,
                text=f"http://{host}:{self.config.port}",
                font=("Consolas", 11, "bold"),
            ).pack(padx=18)
            tk.Label(
                window,
                text="iPhone Kamera uygulamasıyla okutun;\nuygulama açılmazsa adresi elle girin.",
                fg="#555",
                justify="center",
            ).pack(pady=(6, 8))

            pin_var = tk.StringVar(value=f"PIN: {pairing.current()}")
            tk.Label(window, textvariable=pin_var, font=("Consolas", 15, "bold")).pack()

            info_var = tk.StringVar()
            tk.Label(window, textvariable=info_var, fg="#777").pack(pady=(2, 10))

            buttons = tk.Frame(window)
            buttons.pack(pady=(0, 16))

            def tick() -> None:
                if not window.winfo_exists():
                    return
                pin_var.set(f"PIN: {pairing.current()}")
                info_var.set(f"Kalan süre: {pairing.seconds_left} sn")
                window.after(1000, tick)

            def renew() -> None:
                pairing.refresh()
                tick()

            def copy() -> None:
                window.clipboard_clear()
                window.clipboard_append(f"http://{host}:{self.config.port}  PIN {pairing.current()}")

            tk.Button(buttons, text="Yeni PIN", command=renew).pack(side="left", padx=4)
            tk.Button(buttons, text="Kopyala", command=copy).pack(side="left", padx=4)
            tk.Button(buttons, text="Kapat", command=window.destroy).pack(side="left", padx=4)
            tick()

        self._window("qr", "QR ile Eşleştir", "400x600", build)

    # --- ilk kurulum -------------------------------------------------------

    def _add_firewall_rule(self, status_var: tk.StringVar) -> None:
        if firewall.rule_exists():
            status_var.set("Güvenlik duvarı kuralı zaten ekli.")
            return
        if firewall.is_admin():
            program = sys.executable if getattr(sys, "frozen", False) else None
            _ok, message = firewall.add_rule(self.config.port, program)
            status_var.set(message)
            return
        if firewall.elevate(["--firewall", str(self.config.port)]):
            status_var.set("Yönetici onayı istendi; onayladıktan sonra kural eklenecek.")
        else:
            status_var.set("Yönetici izni verilmedi; kural eklenemedi.")

    def show_welcome(self) -> None:
        auto_label = "Otomatik (Windows varsayılanı)"

        def build(window: tk.Toplevel) -> None:
            window.resizable(False, False)
            window.attributes("-topmost", True)
            cfg = self.config
            address = lan_addresses()[0] if lan_addresses() else "127.0.0.1"

            tk.Label(
                window, text="PrintBridge'e hoş geldiniz", font=("Segoe UI", 16, "bold")
            ).pack(pady=(18, 4))
            tk.Label(
                window,
                text="iPhone'dan USB yazıcıya yazdırmak için son adımlar:",
                wraplength=460,
                justify="left",
                fg="#444",
            ).pack(padx=22, pady=(0, 12))

            frame = tk.Frame(window)
            frame.pack(fill="x", padx=22)
            tk.Label(frame, text="Yazıcı", anchor="w").grid(row=0, column=0, sticky="w", pady=5)
            try:
                printers = [auto_label] + [p.id for p in self.runtime.backend.list_printers()]
            except Exception:  # noqa: BLE001
                printers = [auto_label]
            printer_var = tk.StringVar(value=cfg.default_printer or auto_label)
            ttk.Combobox(frame, textvariable=printer_var, values=printers, width=46).grid(
                row=0, column=1, sticky="w", pady=5
            )

            autostart_var = tk.BooleanVar(value=True)
            tk.Checkbutton(
                window, text="Windows açılışında otomatik başlat", variable=autostart_var
            ).pack(anchor="w", padx=22, pady=(10, 6))

            firewall_status = tk.StringVar(
                value="Güvenlik duvarı kuralı ekli."
                if firewall.rule_exists()
                else "Güvenlik duvarı kuralı yok; iPhone bağlanamayabilir."
            )
            row = tk.Frame(window)
            row.pack(fill="x", padx=22)
            tk.Button(
                row,
                text="Güvenlik duvarı kuralı ekle",
                command=lambda: self._add_firewall_rule(firewall_status),
            ).pack(side="left")
            tk.Label(
                window, textvariable=firewall_status, fg="#555", wraplength=460, justify="left"
            ).pack(anchor="w", padx=22, pady=(4, 8))

            tk.Label(
                window,
                text=f"Adres: http://{address}:{cfg.port}",
                font=("Consolas", 11, "bold"),
            ).pack(pady=(6, 2))
            tk.Label(
                window,
                text=f"PIN: {self.runtime.app.state.pairing.current()}",
                font=("Consolas", 13, "bold"),
            ).pack()
            tk.Label(
                window,
                text="PIN 5 dakikada bir yenilenir; tepsideki QR penceresinden de görebilirsiniz.",
                fg="#777",
                wraplength=460,
            ).pack(pady=(2, 12))

            buttons = tk.Frame(window)
            buttons.pack(pady=(0, 16))

            def start() -> None:
                selected = printer_var.get()
                cfg.default_printer = None if selected == auto_label else (selected or None)
                cfg.save()
                try:
                    autostart.set_enabled(autostart_var.get())
                except Exception as exc:  # noqa: BLE001
                    messagebox.showwarning(
                        "PrintBridge",
                        f"Otomatik başlatma ayarlanamadı: {exc}",
                        parent=window,
                    )
                window.destroy()
                self.show_qr()

            tk.Button(buttons, text="Başla", command=start).pack(side="left", padx=6)
            tk.Button(buttons, text="Kapat", command=window.destroy).pack(side="left", padx=6)

        self._window("welcome", "PrintBridge — İlk Kurulum", "540x540", build)

    # --- işler -------------------------------------------------------------

    def show_jobs(self) -> None:
        def build(window: tk.Toplevel) -> None:
            columns = ("time", "status", "name", "pages")
            tree = ttk.Treeview(window, columns=columns, show="headings", selectmode="browse")
            for column, heading, width in (
                ("time", "Saat", 80),
                ("status", "Durum", 100),
                ("name", "İş", 320),
                ("pages", "Sayfa", 70),
            ):
                tree.heading(column, text=heading)
                tree.column(column, width=width, anchor="w" if column == "name" else "center")
            tree.pack(fill="both", expand=True, padx=10, pady=10)

            status_var = tk.StringVar(value="")
            tk.Label(window, textvariable=status_var, anchor="w", fg="#555").pack(fill="x", padx=12)

            def selected_job_id() -> str | None:
                selection = tree.selection()
                return selection[0] if selection else None

            def refresh() -> None:
                if not window.winfo_exists():
                    return
                current = selected_job_id()
                tree.delete(*tree.get_children())
                for job in self.runtime.store.list(limit=50):
                    stamp = (job.created_at or "")[11:19]
                    tree.insert(
                        "",
                        "end",
                        iid=job.id,
                        values=(
                            stamp,
                            STATUS_TR.get(job.status, job.status),
                            job.job_name,
                            f"{job.printed_pages}/{job.pages}" if job.pages else "-",
                        ),
                    )
                if current and tree.exists(current):
                    tree.selection_set(current)
                status_var.set(
                    f"Toplam {len(tree.get_children())} iş · kuyruk: {self.runtime.store.queue_depth()}"
                    f" · yazıcı: {self.status_text()}"
                )
                window.after(2000, refresh)

            def cancel() -> None:
                job_id = selected_job_id()
                if not job_id:
                    return
                job = self.runtime.store.get(job_id)
                if job and job.status in ("queued", "rendering", "printing"):
                    self.runtime.store.update(job_id, status="canceled")
                    refresh()

            def retry() -> None:
                job_id = selected_job_id()
                if not job_id:
                    return
                try:
                    clone = self.runtime.store.retry(job_id)
                    self.runtime.worker.wake()
                    status_var.set(f"Yeniden denendi: {clone.id}")
                except Exception as exc:  # noqa: BLE001
                    messagebox.showwarning("PrintBridge", str(exc), parent=window)
                refresh()

            def preview() -> None:
                job_id = selected_job_id()
                if job_id:
                    webbrowser.open(
                        f"http://127.0.0.1:{self.config.port}/api/v1/jobs/{job_id}/preview.png"
                    )

            buttons = tk.Frame(window)
            buttons.pack(fill="x", padx=10, pady=(0, 10))
            tk.Button(buttons, text="Yenile", command=refresh).pack(side="left", padx=2)
            tk.Button(buttons, text="Önizle", command=preview).pack(side="left", padx=2)
            tk.Button(buttons, text="İptal", command=cancel).pack(side="left", padx=2)
            tk.Button(buttons, text="Yeniden dene", command=retry).pack(side="left", padx=2)
            tk.Button(buttons, text="Kapat", command=window.destroy).pack(side="right", padx=2)

            refresh()

        self._window("jobs", "Yazdırma İşleri", "720x420", build)

    # --- ayarlar -----------------------------------------------------------

    def show_settings(self) -> None:
        auto_label = "Otomatik (Windows varsayılanı)"

        def build(window: tk.Toplevel) -> None:
            cfg = self.config
            frame = tk.Frame(window)
            frame.pack(fill="both", expand=True, padx=16, pady=12)

            try:
                printer_names = [auto_label] + [p.id for p in self.runtime.backend.list_printers()]
            except Exception:  # noqa: BLE001
                printer_names = [auto_label]

            printer_var = tk.StringVar(value=cfg.default_printer or auto_label)
            margin_var = tk.StringVar(value=str(cfg.margin_mm))
            dpi_var = tk.StringVar(value=str(cfg.render_dpi))
            maxmb_var = tk.StringVar(value=str(cfg.max_mb))
            retention_var = tk.StringVar(value=str(cfg.retention_hours))
            autostart_var = tk.BooleanVar(value=autostart.is_enabled())

            rows = [
                ("Yazıcı", ttk.Combobox(frame, textvariable=printer_var, values=printer_names, width=48)),
                ("Kenar boşluğu (mm)", tk.Spinbox(frame, from_=0, to=40, increment=1, textvariable=margin_var, width=8)),
                ("Render çözünürlüğü", ttk.Combobox(frame, textvariable=dpi_var, values=["150", "200", "300"], width=8)),
                ("Maks. dosya (MB)", tk.Spinbox(frame, from_=1, to=200, textvariable=maxmb_var, width=8)),
                ("Dosya saklama (saat)", tk.Spinbox(frame, from_=1, to=720, textvariable=retention_var, width=8)),
            ]
            for index, (label, widget) in enumerate(rows):
                tk.Label(frame, text=label, anchor="w").grid(row=index, column=0, sticky="w", pady=6)
                widget.grid(row=index, column=1, sticky="w", pady=6)

            tk.Checkbutton(
                frame,
                text="Windows açılışında otomatik başlat",
                variable=autostart_var,
            ).grid(row=len(rows), column=0, columnspan=2, sticky="w", pady=(10, 4))

            firewall_status = tk.StringVar(
                value="Güvenlik duvarı kuralı ekli."
                if firewall.rule_exists()
                else "Güvenlik duvarı kuralı yok; iPhone bağlanamayabilir."
            )
            tk.Button(
                frame,
                text="Güvenlik duvarı kuralı ekle",
                command=lambda: self._add_firewall_rule(firewall_status),
            ).grid(row=len(rows) + 1, column=0, columnspan=2, sticky="w", pady=(4, 0))
            tk.Label(
                frame, textvariable=firewall_status, fg="#555", wraplength=500, justify="left"
            ).grid(row=len(rows) + 2, column=0, columnspan=2, sticky="w", pady=(2, 6))

            tk.Label(
                frame,
                text=f"Şu an kullanılacak yazıcı: {self.status_text()}\n"
                "Otomatik seçilirse Windows varsayılanı izlenir; yazıcı adı değişse bile\n"
                "sistemdeki geçerli yazıcıya düşülür.",
                fg="#444",
                justify="left",
            ).grid(row=len(rows) + 3, column=0, columnspan=2, sticky="w", pady=(4, 8))

            discovery = self.runtime.discovery
            tk.Label(
                frame,
                text="Keşif: mDNS açık" if discovery and discovery.active
                else "Keşif: mDNS kapalı (QR / elle IP kullanın)",
                fg="#444",
            ).grid(row=len(rows) + 4, column=0, columnspan=2, sticky="w")

            tk.Label(
                frame,
                text=f"Adres: http://{lan_addresses()[0] if lan_addresses() else '127.0.0.1'}:{cfg.port}\n"
                "Port ve ağ arayüzü değişikliği için uygulamayı yeniden başlatın.",
                fg="#666",
                justify="left",
            ).grid(row=len(rows) + 5, column=0, columnspan=2, sticky="w", pady=(6, 12))

            def save() -> None:
                try:
                    margin = float(margin_var.get().replace(",", "."))
                    if not 0 <= margin <= 40:
                        raise ValueError("Kenar boşluğu 0–40 mm olmalı.")
                    dpi = int(dpi_var.get())
                    if dpi not in (150, 200, 300):
                        raise ValueError("Çözünürlük 150, 200 veya 300 olmalı.")
                    max_mb = int(maxmb_var.get())
                    if not 1 <= max_mb <= 200:
                        raise ValueError("Dosya sınırı 1–200 MB olmalı.")
                    retention = int(retention_var.get())
                    if not 1 <= retention <= 720:
                        raise ValueError("Saklama süresi 1–720 saat olmalı.")
                except ValueError as exc:
                    messagebox.showerror("PrintBridge", str(exc), parent=window)
                    return

                selected = printer_var.get()
                cfg.default_printer = None if selected == auto_label else (selected or None)
                cfg.margin_mm = margin
                cfg.render_dpi = dpi
                cfg.max_mb = max_mb
                cfg.retention_hours = retention
                cfg.save()
                try:
                    autostart.set_enabled(autostart_var.get())
                except Exception as exc:  # noqa: BLE001
                    messagebox.showwarning(
                        "PrintBridge", f"Otomatik başlatma ayarlanamadı: {exc}", parent=window
                    )
                messagebox.showinfo("PrintBridge", "Ayarlar kaydedildi.", parent=window)

            buttons = tk.Frame(window)
            buttons.pack(fill="x", padx=16, pady=(0, 14))
            tk.Button(buttons, text="Kaydet", command=save).pack(side="right", padx=4)
            tk.Button(buttons, text="Kapat", command=window.destroy).pack(side="right", padx=4)

        self._window("settings", "PrintBridge Ayarları", "580x560", build)

    # --- diğer -------------------------------------------------------------

    def open_panel(self) -> None:
        webbrowser.open(f"http://127.0.0.1:{self.config.port}/api/v1/health")

    def open_logs(self) -> None:
        try:
            os.startfile(str(self.config.log_dir))
        except OSError:
            messagebox.showinfo("PrintBridge", f"Log dizini: {self.config.log_dir}")

    def quit(self) -> None:
        log.info("Tepsi uygulaması kapatılıyor")
        try:
            self.icon.stop()
        except Exception:  # noqa: BLE001
            pass
        self.runtime.stop()
        try:
            self.root.after(50, self.root.destroy)
        except Exception:  # noqa: BLE001
            pass


def run_tray(config: Config, first_run: bool = False) -> int:
    root = tk.Tk()
    root.withdraw()
    root.title("PrintBridge")

    runtime = AgentRuntime(config)
    if not runtime.start():
        messagebox.showerror(
            "PrintBridge",
            f"Sunucu {config.port} portunda başlatılamadı.\n"
            "Port başka bir uygulama tarafından kullanılıyor olabilir.",
        )
        return 1

    icon = pystray.Icon(
        "PrintBridge", make_icon_image(), f"PrintBridge — {config.agent_name}"
    )
    controller = TrayController(root, runtime, icon, first_run=first_run)
    icon.menu = controller.build_menu()

    threading.Thread(target=icon.run, name="tray-icon", daemon=True).start()
    log.info("Tepsi uygulaması hazır (port %s)", config.port)
    if first_run:
        root.after(600, controller.show_welcome)

    try:
        root.mainloop()
    except KeyboardInterrupt:
        controller.quit()
    finally:
        runtime.stop()
    return 0


def _notify_already_running() -> None:
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(
            "PrintBridge",
            "PrintBridge Agent zaten çalışıyor.\n"
            "Tepsi simgesinden erişebilirsiniz.",
        )
        root.destroy()
    except Exception:  # noqa: BLE001
        pass


def _show_message(title: str, message: str) -> None:
    try:
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo(title, message)
        root.destroy()
    except Exception:  # noqa: BLE001
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PrintBridge Agent (tepsi uygulaması)")
    parser.add_argument("--diagnose", action="store_true", help="Tanılama raporu yazdır")
    parser.add_argument("--headless", action="store_true", help="Yalnızca HTTP sunucusu")
    parser.add_argument("--autostart", choices=["on", "off"], help="Otomatik başlatmayı aç/kapat")
    parser.add_argument(
        "--firewall",
        type=int,
        nargs="?",
        const=0,
        metavar="PORT",
        help="Güvenlik duvarı kuralını ekle (yönetici gerekir)",
    )
    parser.add_argument(
        "--version", action="version", version=f"PrintBridge Agent {__version__}"
    )
    args = parser.parse_args(argv)

    base = default_data_dir()
    first_run = not (base / "config.json").exists()
    config = Config.load()
    setup_logging(config)

    if args.firewall is not None:
        port = args.firewall or config.port
        program = sys.executable if getattr(sys, "frozen", False) else None
        ok, message = firewall.add_rule(port, program)
        if getattr(sys, "frozen", False):
            _show_message("PrintBridge — Güvenlik Duvarı", message)
        else:
            print(message)
        return 0 if ok else 1

    if args.autostart:
        autostart.set_enabled(args.autostart == "on")
        print("Otomatik başlatma:", "açık" if autostart.is_enabled() else "kapalı")
        return 0

    if args.diagnose:
        from .main import print_diagnostics

        text = print_diagnostics(config)
        if getattr(sys, "frozen", False):
            # Penceresiz exe'de konsol yok: raporu dosyaya yaz ve aç.
            report = config.data_dir / "diagnose.txt"
            report.write_text(text, encoding="utf-8")
            os.startfile(str(report))
        return 0

    if args.headless:
        from .main import main as headless_main

        return headless_main([])

    instance = SingleInstance()
    if not instance.acquire():
        _notify_already_running()
        return 0

    try:
        return run_tray(config, first_run=first_run)
    finally:
        instance.release()


if __name__ == "__main__":
    raise SystemExit(main())

# PrintBridge — Durum Raporu

> Son güncelleme: 2026-11-02 · Windows 10 · Python 3.12 · Samsung SCX-4623F (USB001)

## Tamamlananlar

| Aşama | Durum | Not |
|---|---|---|
| **M0 — Spike** | ✅ | Kalibrasyon + fotoğraf yolu; gerçek sürücüde ölçümler alındı |
| **M1 — Agent MVP** | ✅ | HTTP API, kuyruk, görsel/metin/PDF baskı, hata eşleme, testler |
| M2 — Tepsi/önizleme | ✅ | Tepsi (pystray + tkinter), PIN/işler/ayarlar pencereleri, önizleme ucu, otomatik başlatma, tek örnek kilidi, PyInstaller `.exe` |
| M3 — Keşif/PIN | ✅ | mDNS `_printbridge._tcp` yayını + TXT, QR penceresi (`segno`), PIN/token, özel IP filtresi, firewall betiği |
| M4 — iOS | ⏳ | Başlanmadı |

## Doğrulanan ölçümler (gerçek sürücü)

```
Yazdırılabilir alan : 201,5 × 288,5 mm  (4760 × 6814 px @ 600 dpi)
Fiziksel kâğıt     : 210,0 × 296,9 mm
Sürücü kenar payı  : sol/üst 4,2 mm
Kullanıcı kenarı   : 10 mm (yapılandırılabilir)
A4 kâğıt kimliği   : 9 (DeviceCapabilities)
```

## Uçtan uca doğrulama

- `pytest`: **68 test geçiyor** (render, geometri, kuyruk, API, önizleme, keşif/QR, firewall komutları, iptal, retry, idempotency).
- Gerçek ajan + gerçek yazıcı:
  - `tools/send_test.py --text ...` → iş `done`, 1 sayfa basıldı.
  - `tools/send_test.py --file test.pdf --page-range 1-2` → iş `done`, 2 sayfa basıldı.
  - Baskı sonrası Windows kuyruğu temiz (0 iş).
- mDNS: `_printbridge._tcp.local.` yayını `zeroconf` ile doğrulandı
  (`DESKTOP-AB12-c5bf38…`, `192.168.1.20:8477`, TXT: `v=1 name=… id=… path=/api/v1 pair=required printers=1`).
- Paketlenmiş `.exe` (48,5 MB): başlatıldı, `/api/v1/health` yanıt verdi, mDNS yayını görüldü, süreç kapatıldı.

## Nasıl çalıştırılır

```powershell
# bağımlılıklar
py -3 -m pip install -r requirements.txt

# tepsi uygulaması (önerilen)
py -3 -m agent.tray

# yalnızca sunucu (konsolda PIN görünür)
py -3 -m agent.main

# tek dosya exe
dist\PrintBridge-Agent.exe

# başka bir terminalde
py -3 tools\send_test.py --pin <PIN> --text "Merhaba"
py -3 tools\send_test.py --pin <PIN> --file belge.pdf --copies 1 --paper A4
```

Paketleme: `powershell -ExecutionPolicy Bypass -File tools\build_agent.ps1`
(çıktı `dist\PrintBridge-Agent.exe`; `-Console` hata ayıklama, `-SkipTests` hızlı derleme).

Otomatik başlatma: tepsi > Ayarlar > "Windows açılışında otomatik başlat"
veya `py -3 -m agent.tray --autostart on`.

Ajan verisi: `%ProgramData%\PrintBridge\` (config.json, jobs.db, spool/, logs/).
Geliştirme için `PRINTBRIDGE_DATA_DIR` ile taşınabilir.

## Bilinen eksikler / sonraki adımlar

1. **İlk çalıştırma sihirbazı** tamamlandı (yazıcı seçimi, firewall, otomatik başlatma).
2. **Windows Güvenlik Duvarı kuralı**: `agent/firewall.py` + `tools/firewall.ps1`; tepsiden veya `--firewall` ile yönetici yetkisiyle eklenebilir.
3. iOS uygulaması (M4) — Mac/Xcode erişimi gerekli.
4. TLS + sertifika pinleme (şimdilik LAN + bearer token; QR'da `fp` alanı ayrıldı).
5. Temiz Windows 10 sanal makinesinde kurulum provası.

## Notlar

- Yazıcı seçimi: iş seçeneği → ayarlardaki yazıcı → Windows varsayılanı. Kayıtlı yazıcı
  artık yoksa (ad değişti/çıkarıldı) ajan otomatik olarak Windows varsayılanına düşer,
  iş `printer_not_found` ile başarısız olmaz. Ayarlarda "Otomatik (Windows varsayılanı)"
  seçilerek yazıcı değişiklikleri doğrudan izlenebilir.
- Görsel yönü `auto` seçildiğinde en-boy oranına göre yatay/dikey sayfa seçilir.
- mDNS yayını başlatılamazsa ajan çalışmaya devam eder; tepsideki QR penceresi ve elle IP girişi yedek yoldur.
- Metin dosyaları UTF-8/UTF-8-SIG/cp1254/latin-1 sırasıyla denenir; Türkçe karakterler GDI Unicode ile basılır.
- PDF sayfaları pypdfium2 ile 300 dpi rasterlenip kâğıt kenar boşluğuna oturtulur.
- İşler tek işçiyle sıralı basılır; kuyruk dolduğunda `423 busy`, yazıcı hazır değilse `409 printer_offline` döner.

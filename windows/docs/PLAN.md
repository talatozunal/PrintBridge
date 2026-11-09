# PrintBridge — Proje Planı

> Amaç: iOS 16+ bir iPhone'dan fotoğraf, PDF ve metin gönderip, USB ile Windows 10
> PC'ye bağlı yazıcıda yazdırmak. Yazıcıda ağ yok; PC köprü görevi görür.

---

## 1. Problemin tanımı

Yazıcı modeli **Samsung SCX-4623F** (HP markası altında da satıldı), yalnızca USB.
Bu makinede kurulu sürücü:

```
Samsung SCX-4623 Series (USB001) — Samsung Universal Print Driver 3 — Port: USB001
```

AirPrint olmadığı için iPhone doğrudan yazdıramaz. Çözüm: iPhone → PC (LAN) → USB.
PC tarafında mutlaka çalışan bir ajan (`.exe`) olacak, iPhone tarafında bir uygulama.

**Kapsam (v1):** JPEG/PNG/HEIC fotoğraf, PDF, düz metin. Kopya sayısı, kâğıt
(A4/Letter), yön, sayfa aralığı. İş durumu ve hata mesajı. Tek yazıcı, tek kullanıcı.

**Kapsam dışı (v1):** Office (docx/xlsx) doğrudan basımı, tarama, çoklu yazıcı,
bulut/uzak ağ, renkli baskı (yazıcı tek renk).

---

## 2. Mimari

```
┌──────────────────────── iPhone ────────────────────────┐
│ PrintBridge iOS (SwiftUI, iOS 16+)                     │
│  • Keşif: NWBrowser (_printbridge._tcp) / QR / elle IP │
│  • Eşleştirme: PIN + token (Keychain)                  │
│  • Kaynak: PhotosPicker, .fileImporter, Share Extension│
│  • Yükleme: URLSession (background), multipart         │
│  • Durum: polling 0.5 sn / WebSocket                   │
└───────────────────────┬────────────────────────────────┘
                        │ HTTP/1.1, JSON + multipart, LAN
                        │ Authorization: Bearer <token>
┌───────────────────────▼────────────────────────────────┐
│ Windows 10 PC — PrintBridge Agent (.exe)               │
│  ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌───────────┐ │
│  │ HTTP API │→│ JobQueue │→│ Renderer  │→│ GDI Spool │ │
│  │ FastAPI  │ │ SQLite   │ │PIL/pdfium │ │ pywin32   │ │
│  └──────────┘ └──────────┘ └───────────┘ └─────┬─────┘ │
│  Keşif: zeroconf (mDNS)   Tepsi: pystray      │       │
└───────────────────────────────────────────────┼───────┘
                                                │ DEVMODE + DIB
                                     Windows Print Spooler
                                                │ USB001
                                        Samsung SCX-4623F
```

### Neden bu mimari?

| Seçenek | Değerlendirme |
|---|---|
| **PC ajanı + iOS uygulaması** (seçilen) | Mevcut donanım yeterli, sürücü zaten kurulu, tam kontrol, hızlı geliştirme |
| Raspberry Pi + CUPS + Avahi (AirPrint köprüsü) | Ek donanım, ek bakım; yazıcı yine USB ile Pi'ye taşınmalı |
| Ajanın AirPrint/IPP sunması | iPhone'da uygulama gerekmez, çok zarif; ama IPP + URF/PWG raster sunucusu yazmak büyük iş → **Faz 4 fikri** |
| Bulut kuyruğu (Firebase vb.) | Ağ dışından erişim sağlar ama internet, hesap, gizlilik ve gecikme maliyeti getirir; gerek yok |

---

## 3. Teknoloji seçimi

| Katman | Seçim | Gerekçe |
|---|---|---|
| iOS | SwiftUI, iOS 16+, Network.framework, PhotosUI, UniformTypeIdentifiers | Ek kütüphane yok; iOS 16 hedefi `NavigationStack` + `PhotosPicker` ile rahat |
| Agent dili | **Python 3.12** (makinede kurulu) | Prototip hızı, `pywin32` ile GDI'ya doğrudan erişim, `pypdfium2` ile PDF rasterleme |
| HTTP | FastAPI + Uvicorn | Async, otomatik OpenAPI, multipart ve streaming kolay |
| Görüntü | Pillow, `pillow-heif` | EXIF yönü, ölçekleme, DIB üretimi |
| PDF | pypdfium2 | Lisansı temiz, hızlı, sayfa sayfa render |
| Yazdırma | `pywin32` + GDI (`CreateDCW`, `StartDocW`, `StretchDIBits`) | Sürücüye en yakın, en öngörülebilir yol; kopya/kâğıt/yön DEVMODE ile |
| Keşif | `zeroconf` | Saf Python mDNS; iOS tarafında `NWBrowser` |
| Tepsi | `pystray` + `tkinter` ayar penceresi | Tek .exe içinde, ek runtime yok |
| Paketleme | PyInstaller `--onefile --noconsole` | Kullanıcı tek `.exe` çalıştırır |
| Depolama | SQLite (`%ProgramData%\PrintBridge\jobs.db`) | İş geçmişi, yeniden deneme, tanılama |
| Alternatif | .NET 8 (WinForms/WPF) | Daha "native" ve servis dostu; ancak bu makinede SDK yok, Python ile 2-3 gün daha hızlıyız. Karar değişirse iş mantığı aynı kalır |

> Not: Agent **Windows servisi olarak değil**, oturum açılışında başlayan tepsi
> uygulaması olarak çalışacak. Servis (Session 0) bazı yazıcı sürücülerinde GDI
> baskısında sorun çıkarabilir; ayrıca kullanıcı PIN/ayar penceresini göremez.

---

## 4. Yazdırma hattı (projenin en riskli yeri)

Her dosya türü tek bir çıkışa bağlanır: **sayfa başına 24-bit DIB → GDI**.

```
Dosya → [Tür tespiti]
   ├─ Görsel  : Pillow aç → EXIF orientation uygula → CMYK→RGB → sayfaya yerleştir
   ├─ PDF     : pypdfium2 → sayfa render (300 dpi, gri tonlamaya çevrilebilir)
   └─ Metin   : UTF-8 çöz → GDI DrawTextW ile sayfalara böl (Arial/Consolas 11 pt)

DIB (sayfa) → StartDocW → StartPage → StretchDIBits → EndPage → EndDoc
                ↑
         DEVMODE: dmPaperSize (A4=9), dmOrientation, dmCopies, dmPrintQuality
```

Kurallar:

- **Yerleştirme:** varsayılan "sığdır" (fit) + 10 mm kenar boşluğu; "doldur" (fill)
  seçeneği kırpar. Yazıcının yazdırılabilir alanı `GetDeviceCaps(HORZRES/VERTRES)`
  ile okunur — sabit varsayılmaz.
- **Kuyruk:** tek worker thread, sıralı. Tek fiziksel yazıcı varken paralel baskı
  sürücüyü kilitler. İş durumları: `queued → rendering → printing → done | failed | canceled`.
- **Kalıcılık:** yüklenen dosya `%ProgramData%\PrintBridge\spool\<uuid>` altında;
  başarılı/başarısız işten 24 saat sonra silinir (ayarlanabilir).
- **İdempotans:** `Idempotency-Key` başlığı; ağ kopunca aynı iş iki kez basılmasın.
- **Sınırlar:** 50 MB dosya, 100 sayfa, 20 000 px kenar (bellek koruması).
- **Hata eşlemesi:** spooler hata kodları (`ERROR_PRINTER_OFFLINE`, `ERROR_PAPER_EMPTY`,
  `ERROR_INVALID_HANDLE` …) kullanıcıya Türkçe mesaja çevrilir; ham kod log'a yazılır.
- **Önizleme (opsiyonel):** ilk sayfanın PNG'si `GET /jobs/{id}/preview.png` ile
  iPhone'da gösterilebilir.

**M0 spike (ilk iş):** Python + pywin32 ile tek bir JPEG'i SCX-4623F'te A4 olarak
bastıran 60 satırlık script. Sürücü/DEVMODE davranışı burada doğrulanmadan
uygulama yazılmaz.

**M0 ölçüm sonucu (bu makinede, gerçek sürücü):**

```
Yazdırılabilir alan : 201,5 × 288,5 mm  (4760 × 6814 px @ 600 dpi)
Fiziksel kâğıt     : 210,0 × 296,9 mm
Sürücü kenar payı  : sol/üst 4,2 mm (100 px)
```

Yani sürücü A4'ü 600 dpi'da 4960×7014 px olarak modelliyor; yazdırılabilir alan
kenarlardan ~4,2 mm içeride. 10 mm kullanıcı kenar boşluğu buna eklendiğinde
içerik alanı 4288×6342 px kalıyor. Bu sayılar sabit kodlanmayacak, her açılışta
`GetDeviceCaps` ile okunacak (yazıcı değişirse doğru çalışsın).

---

## 5. Ağ, keşif ve eşleştirme

1. Agent açılışta 5353/udp üzerinden mDNS yayını yapar:
   `_printbridge._tcp` · TXT: `v=1`, `name=DESKTOP-XXX`, `id=<uuid>`, `path=/api/v1`, `pair=required`
2. iPhone `NWBrowser` ile aynı ağdaki ajanları listeler (2 sn içinde).
3. mDNS çalışmazsa: agent tepsi menüsünde **QR kod** (adres + port + parmak izi) ve
   elle IP girme ekranı.
4. **Eşleştirme:** agent 6 haneli PIN gösterir (5 dk geçerli, 5 deneme hakkı).
   Uygulama `POST /pair` ile PIN + cihaz adı gönderir, uzun ömürlü token alır ve
   Keychain'e yazar. PC'den tek tuşla iptal edilebilir.
5. Sabit port **8477**; agent yalnızca özel ağ arayüzlerine bağlanır.
6. İlk çalıştırmada Windows Güvenlik Duvarı kuralı eklenir (gelen TCP 8477, özel ağ).

---

## 6. Güvenlik

- Token'sız hiçbir uç (pair/health hariç) cevap vermez; `hmac.compare_digest` ile karşılaştırma.
- Yalnızca `192.168/16`, `10/8`, `172.16/12`, `fe80::/10` kaynakları kabul edilir; internet'e
  port açma yok, UPnP yok.
- PIN denemeleri rate-limit + kilit; token'lar cihaz bazlı ve iptal edilebilir.
- Dosya adı asla yola yazılmaz; UUID + uzantı doğrulaması, MIME sihirli bayt kontrolü.
- Yüklenen dosyalar 24 saat sonra silinir; iş geçmişinde yalnızca meta veri tutulur.
- Log'larda dosya içeriği yok, sadece iş kimliği ve sonuç.
- (Faz 2) TLS: kendinden imzalı sertifika, QR ile gelen SHA-256 parmak izi pinleme.

---

## 7. iOS uygulaması

**Ekranlar**

1. **Yazıcılar** — bulunan ajanlar, çevrimiçi durumu, "Eşleştir" akışı (PIN girişi).
2. **Yazdır** — seçilen belge önizlemesi; kopya, kâğıt, yön, sığdır/doldur, sayfa aralığı.
3. **İşler** — son 20 iş, durum rozetleri, hata mesajı, yeniden dene.
4. **Ayarlar** — eşleşmeyi kaldır, varsayılan yazıcı, dil (TR/EN), tanılama bilgisi.

**Teknik notlar**

- `Info.plist`: `NSLocalNetworkUsageDescription`, `NSBonjourServices = [_printbridge._tcp]`.
  İzin reddedilirse elle IP girişi çalışmaya devam eder.
- `PhotosPicker` (fotoğraf) + `.fileImporter` (PDF/txt) + **Share Extension** (her uygulamadan
  "PrintBridge'e Gönder"). Share Extension ile uygulama aynı App Group ve Keychain
  erişimini paylaşır; yükleme `URLSession` background configuration ile yapılır.
- HEIC → yüklemeden önce JPEG'e çevrilir (PC tarafında `pillow-heif` yine de destekler).
- Yükleme iptal/yeniden deneme; Wi-Fi değişince ajan yeniden keşfedilir.
- Türkçe karakterler (ş, ğ, ı, İ) için metin UTF-8 gönderilir, PC'de GDI Unicode API kullanılır.
- Minimum hedef iOS 16.0; iPhone + iPad (universal), karanlık mod.

**Dağıtım**

| Yol | Maliyet | Süre | Not |
|---|---|---|---|
| **Jailbreak + TrollStore** (seçilen cihaz) | 0 | kalıcı | İmza süresi yok, 7 günlük yenileme derdi yok |
| Ücretsiz Apple ID + AltStore/SideStore | 0 | 7 günde yenileme | JB'siz cihazlar için yedek |
| TestFlight | 99 $/yıl | 90 günlük build | Geliştirme sırasında en rahat hata ayıklama |
| Ad Hoc | 99 $/yıl | 1 yıl | 100 cihaz |

Hedef cihaz jailbreak'li olduğu için uygulama TrollStore ile kalıcı olarak kurulabilir;
App Store veya ücretli hesap gerekmiyor. Yine de Debug build için Xcode + ücretsiz
provisioning profili yeterli (7 günlük süre sadece dağıtımda önemli).

---

## 8. Windows agent bileşenleri

```
agent/
  main.py            # uvicorn başlatma, tek örnek kilidi (mutex)
  config.py          # %ProgramData%\PrintBridge\config.json
  api.py             # /pair, /printers, /jobs, /health, /ws
  jobs.py            # SQLite + tek worker kuyruk + iptal
  render.py          # image / pdf / text → sayfa DIB listesi
  printer.py         # EnumPrinters, DEVMODE, GDI StartDoc/StretchDIBits, hata eşleme
  discovery.py       # zeroconf yayını, QR payload
  tray.py            # pystray menü, PIN penceresi, iş listesi
  logging_setup.py   # dönen dosya log (%ProgramData%\PrintBridge\logs)
  assets/            # simgeler
```

- **Ayarlar:** varsayılan yazıcı, port, kâğıt, kenar boşluğu, dosya saklama süresi,
  otomatik başlatma, eşleşmiş cihazlar.
- **Tepsi menüsü:** durum, "PIN göster", "QR göster", "İşler", "Ayarlar", "Logları aç", "Çıkış".
- **Otomatik başlatma:** HKCU `Software\Microsoft\Windows\CurrentVersion\Run`
  (yönetici gerektirmez; Görev Zamanlayıcı'ya göre daha basit).
  Kurulumda bir kez yönetici izniyle firewall kuralı eklenir.
- **Tanılama:** `--diagnose` parametresi sürücü, port, kâğıt listesi ve test baskısı raporu üretir.

---

## 9. Yol haritası

| # | Adım | Süre | Kabul kriteri |
|---|---|---|---|
| **M0** | Spike: JPEG → GDI → SCX-4623F | 0,5 gün | A4, doğru yön, kenar boşluğu makul, çökme yok |
| **M1** | Agent MVP: upload + görsel/metin baskı + CLI test | 2-3 gün | `curl` ile gönderilen iş basılıyor; durum `done` |
| **M2** | PDF + seçenekler + iş geçmişi + tepsi/ayar | 2 gün | 10 sayfalık PDF, 3 kopya, yatay A4 doğru |
| **M3** | Keşif + eşleştirme + güvenlik + firewall | 1 gün | Uygulama ajanı buluyor; token'sız istek 401 |
| **M4** | iOS MVP: keşif, eşleşme, foto/PDF seç, seçenekler, yükleme, durum | 3-4 gün | Uçtan uca iPhone'dan baskı |
| **M5** | Share Extension + arka plan yükleme + hata UX | 2 gün | Safari'den "Paylaş → Yazdır" çalışıyor |
| **M6** | Kurulum, otomatik başlatma, log, README, TR/EN | 1-2 gün | Yeni PC'de 10 dk'da kurulum |
| **M7** | Test matrisi + cila | 1-2 gün | Aşağıdaki matris yeşil |

**Toplam:** ~2-3 hafta (yarı zamanlı). Kritik yol M0 → M1 → M4.

---

## 10. Test matrisi

- 20 MP iPhone fotoğrafı (HEIC), dikey/yatay, EXIF yönü 6.
- 1 ve 30 sayfalık PDF; taranmış (görüntü) ve metin PDF.
- Türkçe karakterli uzun metin; sayfa taşması.
- 3 kopya, yatay A4, Letter kâğıt, sayfa aralığı `2-4`.
- Yazıcı kapalı / USB çıkarık / kâğıt bitti / toner az → anlaşılır hata.
- PC uykuya geçti → uygulama "yazıcı çevrimdışı" der, kuyruğa almaz.
- Wi-Fi değişimi, mDNS kapalı modem, iki iPhone aynı anda.
- 49 MB ve 51 MB dosya; 100+ sayfa; bozuk PDF.
- Token iptali, yanlış PIN ×5, eşleşmemiş cihaz.
- Uygulama arka planda/öldürülmüşken yükleme; share extension.
- Yeniden başlatma sonrası kuyruk kalıcılığı.

---

## 11. Riskler ve önlemler

| Risk | Etki | Önlem |
|---|---|---|
| Samsung evrensel sürücüde DEVMODE kâğıt/yön davranışı | Baskı yanlış kâğıt/yönde | M0'da `DeviceCapabilities` ile kâğıt listesini oku, sabit kodlama yapma; testte Letter/A4 doğrula |
| GDI baskıda Session 0 sorunları | Servis modunda basmıyor | Tepsi uygulaması (kullanıcı oturumu) ile başla |
| iOS yerel ağ izni reddi | Keşif çalışmaz | Elle IP + QR her zaman yedek |
| mDNS 5353 çakışması (Bonjour/iTunes) | Yayın başlamaz | `zeroconf` hatasını yut, QR/elle IP'ye düş, log'a yaz |
| Ücretsiz imza 7 gün | Uygulama açılmıyor | AltStore otomatik yenileme; uzun vadede TestFlight |
| PC uykuda | Erişilemez | Ayarlarda "uykuyu engelle" seçeneği; WoL Faz 3 |
| 50 MB üstü / bellek | OOM | Akışlı yükleme, boyut/sayfa sınırı, 300 dpi üstü render'ı küçült |
| Antivirüs tek `.exe`'yi karantinaya alır | Ajan çalışmaz | İmzalı exe (Faz 3), kurulum notunda istisna |

---

## 12. Sonraki fazlar

1. **Tarama:** SCX-4623F tarayıcısı WIA ile → PDF/JPG olarak iPhone'a gönder.
2. **AirPrint emülasyonu:** Agent IPP Everywhere + URF raster sunsun; iPhone'un
   yerleşik yazdırma menüsü uygulamasız çalışsın.
3. **Office dönüştürme:** LibreOffice headless ile docx/xlsx → PDF.
4. **TLS + sertifika pinleme**, çok kullanıcı/rol, web yönetim paneli.
5. **WoL / PC uyandırma**, çoklu yazıcı seçimi.

---

## 13. Klasör yapısı (hedef)

```
PrintBridge/
  docs/            PLAN.md, PROTOCOL.md, BACKLOG.md
  agent/           Python kaynak + requirements.txt
  agent/tests/     pytest: render, protokol, hata eşleme
  ios/PrintBridge/ Xcode projesi (SwiftUI)
  tools/           m0_spike.py, build_agent.ps1, make_qr.py
  installer/       Inno Setup / install.ps1
```

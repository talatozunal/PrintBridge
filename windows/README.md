# PrintBridge

iPhone (iOS 16+) → Wi-Fi/LAN → Windows 10 PC → USB yazıcı (HP/Samsung SCX-4623F).

Ağ bağlantısı olmayan bir yazıcıyı, USB ile bağlı olduğu PC üzerinden iPhone'dan
kullanılabilir hale getiren iki parçalı bir sistem:

| Bileşen | Teknoloji | Görev |
|---|---|---|
| **PrintBridge iOS** | SwiftUI, iOS 16+ | Belge/fotoğraf seç, yazdırma seçenekleri, PC'yi bul, gönder, durumu izle |
| **PrintBridge Agent** | Python 3.12 + FastAPI, tek `.exe` | Dosyayı al, sayfaya yerleştir, Windows yazdırma kuyruğuna ver |

Belgeler:

- [`docs/PLAN.md`](docs/PLAN.md) — mimari, teknoloji seçimi, yol haritası, riskler
- [`docs/PROTOCOL.md`](docs/PROTOCOL.md) — HTTP API sözleşmesi ve keşif (mDNS) tanımı
- [`docs/BACKLOG.md`](docs/BACKLOG.md) — kilometre taşları ve kabul kriterleri
- [`docs/STATUS.md`](docs/STATUS.md) — nerede olduğumuz, ölçümler, eksikler

Hedeflenen akış:

```
[Fotoğraflar / Dosyalar / Safari]  --paylaş-->  PrintBridge iOS
                                                     |
                                           HTTP + token (LAN)
                                                     v
                                    PrintBridge Agent (Windows, tepsi)
                                                     |
                                              Windows Print Spooler
                                                     v
                                              USB yazıcı (SCX-4623F)
```

## Durum (M0–M3, M6 cila)

- **Agent MVP tamamlandı**: tüm uçlar, SQLite kuyruk, görsel/metin/PDF render, GDI baskı.
- **Keşif**: mDNS `_printbridge._tcp`, QR penceresi, PIN/token, özel IP filtresi.
- **Paketleme**: tek `.exe` (PyInstaller), tepsi uygulaması, otomatik başlatma, ilk kurulum sihirbazı.
- **Testler**: 68 test geçiyor; gerçek yazıcıda Türkçe metin ve 2 sayfalık PDF basıldı.
- **iOS (PhonePrint)**: SwiftUI istemci tamamlandı; keşif, QR/PIN eşleştirme, dosya/fotoğraf seçimi, yükleme ve durum izleme çalışıyor.

## Windows tarafı — son kullanıcı kurulumu

1. `dist\PrintBridge-Agent.exe` dosyasını çalıştırın (ilk çalıştırmada veri dizini
   `%ProgramData%\PrintBridge\` oluşturulur).
2. İlk kurulum sihirbazı açılır:
   - yazıcıyı seçin (varsayılan: **Otomatik — Windows varsayılanı**),
   - "Windows açılışında otomatik başlat" seçeneğini işaretleyin,
   - "Güvenlik duvarı kuralı ekle" düğmesine basın (yönetici onayı ister).
3. Tepsi simgesinden **QR ile eşleştir** veya **Eşleştirme PIN'i** seçeneğini kullanın:
   - **QR**: iPhone Kamera veya PhonePrint uygulamasının QR tarayıcısı ile okutun.
   - **PIN**: 6 haneli PIN, 5 dakika geçerli; 5 hatalı denemede kilitlenir.
4. Adres: `http://<PC-IP>:8477` (mDNS ile otomatik bulunur).

### Güvenlik duvarı (manuel)

Yönetici PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File tools\firewall.ps1
# kaldırmak için:
powershell -ExecutionPolicy Bypass -File tools\firewall.ps1 -Remove
```

Veya tepsideki **Ayarlar → Güvenlik duvarı kuralı ekle** düğmesi.

### Otomatik başlatma

- Tepsi uygulaması HKCU `Software\Microsoft\Windows\CurrentVersion\Run` anahtarına
  `PrintBridge` değeri yazar; Windows açılışında sessizce başlar.
- Kapatmak için tepsi menüsünden **Çıkış** veya
  `py -3 -m agent.tray --autostart off`.

## Geliştirici kurulumu

Gereksinimler: Windows 10, Python 3.12, (isteğe bağlı) PowerShell 5.1+.

```powershell
cd C:\PrintBridge
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
py -3 -m pip install -r requirements.txt
```

Çalıştırma:

```powershell
py -3 -m agent.tray            # tepsi uygulaması
py -3 -m agent.main             # yalnızca HTTP sunucusu
py -3 -m agent.tray --diagnose  # tanılama raporu
```

Testler:

```powershell
py -3 -m pytest -q
```

Paketleme (tek `.exe`):

```powershell
powershell -ExecutionPolicy Bypass -File tools\build_agent.ps1
# testleri atlamak için:
powershell -ExecutionPolicy Bypass -File tools\build_agent.ps1 -SkipTests
```

Çıktı: `dist\PrintBridge-Agent.exe` (~48,5 MB).

### Veri dizini

- Varsayılan: `%ProgramData%\PrintBridge\` (`config.json`, `jobs.db`, `spool\`, `logs\`).
- Geliştirme/test: `PRINTBRIDGE_DATA_DIR` ortam değişkeni ile değiştirilebilir.

### Yazıcı seçimi

- `config.default_printer = null` (varsayılan) → **Otomatik (Windows varsayılanı)**.
- İş seçeneği → `config.default_printer` → Windows varsayılanı fallback; kayıtlı yazıcı bulunamazsa
  sistemdeki geçerli yazıcıya düşülür (yazıcı değişikliğinde ayar güncellemesi gerekmez).

## Sorun giderme

- **iPhone bağlanamıyor**: PC ve iPhone aynı Wi-Fi'da mı? Güvenlik duvarı kuralı eklendi mi?
  `tools\firewall.ps1` yönetici olarak çalıştırın.
- **mDNS çalışmıyor**: modem/erişim noktası mDNS'i blokluyor olabilir; tepside **QR ile eşleştir**
  veya elle IP girin.
- **Yazıcı bulunamadı**: Windows'ta yazıcı varsayılan olarak ayarlı mı? Ayarlar → yazıcı listesi.
- **Loglar**: `%ProgramData%\PrintBridge\logs\agent.log`.

## Lisans

[MIT](../LICENSE)
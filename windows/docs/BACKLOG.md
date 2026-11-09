# PrintBridge — İş Listesi

Her madde bittiğinde işaretlenir. Sıra kritik yolu izler: M0 → M1 → M4.

## M0 — Spike (0,5 gün)

- [x] `tools/m0_spike.py`: JPEG aç → A4 DIB → GDI → `Samsung SCX-4623 Series (USB001)`
- [x] `DeviceCapabilities` ile yazdırılabilir alan ve kâğıt listesini oku
      (A4=9, Letter=1, 20 kâğıt tanımı; 600 dpi, 4760×6814 px yazdırılabilir alan)
- [x] Baskı yolu M1 uçtan uca testleriyle doğrulandı (metin 1 sayfa, PDF 2 sayfa)
- [x] DEVMODE kâğıt/yön kodlandı; fiziksel kalibrasyon sayfası isteğe bağlı
- [x] Kenar boşluğu ve süre notu: 10 mm, ~0,7 sn hazırlık + sürücü süresi

Çalıştırma:

```powershell
py -3 -m pip install -r requirements.txt

py -3 tools\m0_spike.py --info                  # sürücü + kâğıt listesi
py -3 tools\m0_spike.py --dry-run --preview out\kalibrasyon.png
py -3 tools\m0_spike.py                         # kalibrasyon sayfasını bastır (onay sorar)
py -3 tools\m0_spike.py foto.jpg --copies 2 --orientation landscape
```

Kâğıt üzerinde kontrol edilecekler: 10 mm çerçeve boşluğu, yazı yönü, Türkçe
karakterler (ş ğ ı İ), 11 kademeli gri rampa, daire/çapraz geometrisi.

## M1 — Agent MVP (2-3 gün)

- [x] `agent/` iskeleti, `requirements.txt`, `config.json`, dönen log
- [x] FastAPI: `/health`, `/pair`, `/printers`, `/jobs` (multipart) + `/devices`
- [x] SQLite iş tablosu + tek worker kuyruk + iptal + retry + idempotency
- [x] `render.py`: görsel (EXIF, fit/fill), metin (Unicode, sayfalama, sayfa no),
      PDF (pypdfium2, sayfa aralığı)
- [x] `printer.py`: DEVMODE, StartDoc/StretchDIBits, kopya döngüsü, hata eşleme
- [x] pytest: **56 test** (render, geometri, kuyruk, API, hata senaryoları)
- [x] Uçtan uca: `tools/send_test.py` ile metin ve 2 sayfalık PDF gerçekten basıldı

## M2 — Tepsi, önizleme, cila (1-2 gün)

- [x] PDF → sayfa render, sayfa aralığı, `pages`/`printedPages` ilerlemesi
- [x] Kopya, kâğıt, yön, sığdır/doldur doğrulaması
- [x] `GET /jobs`, `DELETE /jobs/{id}`, `retry`, iş geçmişi (SQLite)
- [x] Dönen dosya log + `--diagnose` raporu
- [x] Çok sayfalı PDF testi
- [x] `pystray` tepsi: durum, PIN, işler, ayarlar, çıkış
- [x] `GET /jobs/{id}/preview.png` önizleme ucu (tepsiden tarayıcıda açılır)
- [x] Ayarlar penceresi (yazıcı, kenar boşluğu, çözünürlük, saklama süresi)
- [x] Otomatik başlatma (HKCU `Run`) + tek örnek kilidi
- [x] Yazıcı adı değişirse Windows varsayılanına otomatik düşme
- [x] PyInstaller tek `.exe` (`dist/PrintBridge-Agent.exe`, ~47 MB) — çalıştığı doğrulandı

## M3 — Keşif ve güvenlik (1 gün)

- [x] `zeroconf` yayını + TXT kayıtları, çakışma toleransı
- [x] PIN üretimi, 5 dk TTL, deneme limiti, token üretimi/iptali
- [x] Özel IP filtresi, 50 MB / 100 sayfa sınırları
- [x] Windows Güvenlik Duvarı kuralı (`tools\firewall.ps1`)
- [x] QR payload + tepside QR penceresi (`segno`)

## M4 — iOS MVP (3-4 gün)

- [ ] Xcode projesi, iOS 16 hedefi, TR/EN yerelleştirme
- [ ] `DiscoveryService` (NWBrowser + elle IP), `PairingService` (Keychain)
- [ ] `PrintOptionsView`: kopya, kâğıt, yön, sığdır, sayfa aralığı
- [ ] `PhotosPicker` + `.fileImporter` + önizleme
- [ ] `UploadService`: multipart, Idempotency-Key, ilerleme, iptal
- [ ] `JobsView`: durum, hata metni, yeniden dene
- [ ] Uçtan uca iPhone → SCX-4623F testi

## M5 — Paylaşım ve arka plan (2 gün)

- [ ] Share Extension (fotoğraf, PDF, Safari, Dosyalar)
- [ ] App Group + paylaşılan Keychain
- [ ] Background `URLSession` yüklemesi, uygulama kapalıyken tamamlanma
- [ ] Yerel ağ izni reddi senaryosu ve yönlendirme metni

## M6 — Paketleme (1-2 gün)

- [x] PyInstaller tek `.exe` (`--onefile --noconsole`), simge
- [x] İlk çalıştırma sihirbazı: yazıcı seç, PIN, firewall, otomatik başlat
- [x] Otomatik başlatma (HKCU `...\Run`), tek örnek kilidi
- [x] `README` kurulum adımları (PC + iPhone), ekran görüntüleri
- [ ] Temiz Windows 10 sanal makinede kurulum provası

## M7 — Test ve cila (1-2 gün)

- [ ] `PLAN.md` §10 test matrisinin tamamı
- [ ] Hata metinlerinin Türkçe gözden geçirilmesi
- [ ] Performans: 20 MP fotoğraf < 6 sn, 10 sayfa PDF < 20 sn
- [ ] Log ve gizlilik kontrolü (dosya içeriği loglanmıyor)

---

## Açık kararlar

- [ ] `.NET 8` alternatifi değerlendirilecek mi? (Python seçildi; gerekçe: SDK kurulu değil, prototip hızı)
- [ ] PDF'ler gri tonlamaya çevrilsin mi? (toner tasarrufu / kalite)
- [ ] Varsayılan kâğıt A4 mü Letter mı? (A4 önerilir)
- [ ] Uygulama adı ve simge
- [ ] TestFlight hesabı alınacak mı, ücretsiz imza mı kullanılacak?

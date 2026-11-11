# PrintBridge / PhonePrint

iPhone'den, aynı Wi-Fi ağındaki Windows 10 PC'ye USB ile bağlı yazıcıya
fotoğraf ve belge gönderip yazdırma.

Sistem iki parçadan oluşur:

| Bileşen | Klasör | Platform | Teknoloji |
| --- | --- | --- | --- |
| **PhonePrint** (iOS uygulaması) | [`ios/`](ios) | iPhone, iOS 16+ | SwiftUI |
| **PrintBridge Agent** (Windows ajanı) | [`windows/`](windows) | Windows 10 | Python 3.12 + FastAPI |

```
[Fotoğraflar / Dosyalar / Safari]  --paylaş-->  PhonePrint (iPhone)
                                                    |
                                         HTTP + bearer token (LAN)
                                                    v
                                    PrintBridge Agent (Windows, tepsi)
                                                    |
                                            Windows Print Spooler
                                                    v
                                             USB yazıcı
```

## Nasıl çalışır

1. Windows PC'de `PrintBridge-Agent.exe` çalışır; yazıcı USB ile bu PC'ye bağlıdır.
2. Ajan, yerel ağda mDNS (`_printbridge._tcp`) ile kendini duyurur ve bir QR /
   6 haneli PIN ile eşleştirme sunar.
3. iPhone'daki PhonePrint uygulaması ajanı otomatik bulur (veya IP girilir),
   PIN/QR ile eşleşir ve cihaza özel bir token alır.
4. Seçilen fotoğraf veya belge (PDF, JPEG, PNG, HEIC, TXT) LAN üzerinden ajana
   yüklenir; ajan dosyayı sayfaya yerleştirip Windows yazdırma kuyruğuna verir.
5. İş durumu uygulamada canlı izlenir; iptal ve yeniden deneme desteklenir.

## Özellikler

**iOS (PhonePrint)**
- mDNS ile PC'yi otomatik bulma, QR kod ile eşleştirme, elle IP/port girme
- 6 haneli PIN ile eşleştirme; token Keychain'de saklanır
- Fotoğraf ve belge seçimi
- Kopya sayısı, kâğıt boyutu, yön, sayfaya sığdırma ve sayfa aralığı seçenekleri
- Yükleme durumu takibi, iptal, yeniden deneme ve iş geçmişi
- Türkçe, İngilizce, Almanca, Fransızca ve İtalyanca arayüz; uygulama içinden
  yeniden başlatmadan dil değiştirme

**Windows ajanı**
- Tek `.exe` (PyInstaller), tepsi uygulaması, isteğe bağlı otomatik başlatma
- FastAPI + SQLite iş kuyruğu, idempotency, yeniden deneme
- Görsel, metin ve PDF render; GDI ile baskı
- mDNS keşif, QR/PIN eşleştirme, token hash'leme, hız sınırlama
- Güvenlik duvarı kuralı yardımcısı ve tanılama

## Kurulum

### Windows ajanı

```powershell
cd windows
py -3 -m pip install -r requirements.txt
py -3 -m pytest -q
powershell -ExecutionPolicy Bypass -File tools\build_agent.ps1
```

Çıktı: `windows\dist\PrintBridge-Agent.exe`. Ayrıntılar için
[`windows/README.md`](windows/README.md).

### iOS uygulaması

1. `ios/PhonePrint.xcodeproj` dosyasını Xcode ile açın.
2. **Signing & Capabilities** bölümünde kendi Apple Developer ekibinizi seçin.
3. Bir iPhone seçip çalıştırın (`⌘R`). Ayrıntılar için [`ios/README.md`](ios/README.md).

## Güvenlik ve gizlilik

- Depoda **hiçbir playlist, sağlayıcı hesabı, kullanıcı adı, şifre veya API
  anahtarı** bulunmaz.
- Eşleştirme token'ı yalnızca çalışma zamanında üretilir; ajan tarafında
  SHA-256 özeti saklanır, iOS tarafında Keychain'de tutulur.
- Trafik LAN üzerinde HTTP + bearer token ile korunur; TLS henüz yoktur.
  Uygulamayı yalnızca güvendiğiniz yerel ağlarda kullanın.
- `NSAllowsLocalNetworking` yalnızca yerel ağ erişimi içindir; genel ATS
  istisnası (`NSAllowsArbitraryLoads`) veya sağlayıcı istisnası yoktur.

## Belgeler

Ajan protokolü, mimari ve durum notları: [`windows/docs/`](windows/docs).

## Lisans

[MIT](LICENSE)

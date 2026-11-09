# PhonePrint (iOS)

PrintBridge Windows ajanına bağlanan iPhone uygulaması. SwiftUI, iOS 16+.

## Gereksinimler

- macOS 13+ ve Xcode 15+
- iOS 16+ iPhone
- Aynı Wi-Fi ağında çalışan PrintBridge Agent (Windows)

## Çalıştırma

1. `PhonePrint.xcodeproj` dosyasını Xcode ile açın.
2. **Signing & Capabilities** → kendi Apple Developer ekibinizi seçin
   (depoda geliştirici ekibi tanımlı değildir).
3. Bir iPhone veya Simulator seçip çalıştırın (`⌘R`).

Uygulama ilk açılışta yerel ağ ve kamera izni ister; bu izinler ajanı bulmak ve
QR kod okutmak için gereklidir.

## Özellikler

- mDNS (`_printbridge._tcp`) ile PC'yi otomatik bulma
- QR kod (`printbridge://pair?...`) ile eşleştirme
- Elle IP/port girerek bağlanma
- 6 haneli PIN ile eşleştirme; token Keychain'de saklanır
- Fotoğraf/belge seçimi; kopya, kâğıt, yön, sığdırma ve sayfa aralığı seçenekleri
- Multipart yükleme, durum izleme, iptal ve yeniden deneme
- Yazıcı değiştiğinde ayar güncellemesi gerekmez (ajan Windows varsayılanına düşer)

## Yapılandırma

`Info.plist` içinde yerel ağ için gerekli anahtarlar hazır gelir:

- `NSLocalNetworkUsageDescription`
- `NSBonjourServices = [_printbridge._tcp]`
- `NSCameraUsageDescription`
- `NSPhotoLibraryUsageDescription`

Genel ATS istisnası veya sağlayıcı istisnası **yoktur**.

## Notlar

- Yükleme uygulama açıkken yapılır; sonuç iş listesinden okunur.
- TLS henüz yok; trafik LAN üzerinde HTTP + bearer token ile korunur.
- Simulator'da mDNS keşfi çalışmayabilir; elle IP girerek bağlanın.

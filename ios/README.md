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
- Beş dil: Türkçe, İngilizce, Almanca, Fransızca, İtalyanca

## Dil desteği

Arayüz beş dilde gelir ve varsayılan olarak cihazın dilini kullanır. Dil,
uygulama yeniden başlatılmadan değişir.

- **Eşleşmemiş ekran:** gezinme çubuğunun solundaki küre düğmesi.
- **Eşleşmiş ekran:** **Ayarlar → Dil** satırı.

Seçim `UserDefaults` içinde `appLanguage` anahtarında saklanır. Çeviriler
`PhonePrint/tr|en|de|fr|it.lproj/Localizable.strings` dosyalarındadır;
`InfoPlist.strings` izin metinlerini, `Dil.swift` ise dil yöneticisini ve
`DilSecici` sayfasını içerir. Ajanın döndürdüğü hata kodları
(`unauthorized`, `invalid_pin`, `printer_offline`, …) `server.*` anahtarlarıyla
yerelleştirilir; kod tanınmıyorsa sunucunun mesajı gösterilir.

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

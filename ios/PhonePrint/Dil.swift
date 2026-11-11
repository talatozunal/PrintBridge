import SwiftUI
import Combine

// MARK: - DİL YÖNETİMİ
//
// Uygulama içi dil seçimi. Seçim UserDefaults'ta saklanır; dil değişince tüm
// metinler ve biçimler anında güncellenir. Yeniden başlatma gerekmez.
//
// Çeviriler projedeki <dil>.lproj/Localizable.strings dosyalarında durur.
// Yeni bir dil eklemek için: aynı anahtarlarla yeni bir .lproj klasörü açın,
// desteklenenDiller listesine kodunu ekleyin ve UygulamaDili'ne bir case yazın.

enum UygulamaDili: String, CaseIterable, Identifiable {
    case sistem
    case tr
    case en
    case de
    case fr
    case it

    var id: String { rawValue }

    /// Dilin kendi dilindeki adı. Çevrilmez.
    var ozAd: String {
        switch self {
        case .sistem: return ""
        case .tr: return "Türkçe"
        case .en: return "English"
        case .de: return "Deutsch"
        case .fr: return "Français"
        case .it: return "Italiano"
        }
    }
}

final class Yerellestirme: ObservableObject {
    /// Ağ katmanı gibi ortamlardan da erişilebilen ortak örnek.
    static let paylasilan = Yerellestirme()

    static let dilAnahtari = "appLanguage"
    static let desteklenenDiller = ["tr", "en", "de", "fr", "it"]

    /// Eksik anahtar tespiti için görünmez işaret.
    private static let eksik = "\u{0}__eksik__"

    @Published var secim: String {
        didSet {
            UserDefaults.standard.set(secim, forKey: Self.dilAnahtari)
        }
    }

    init() {
        let kayitli = UserDefaults.standard.string(forKey: Self.dilAnahtari)
            ?? UygulamaDili.sistem.rawValue
        secim = UygulamaDili(rawValue: kayitli) != nil ? kayitli : UygulamaDili.sistem.rawValue
    }

    /// "sistem" seçiliyse cihazın bu uygulama için tercih ettiği dil,
    /// değilse kullanıcının seçtiği dil.
    var kod: String {
        let aday = secim == UygulamaDili.sistem.rawValue ? Self.sistemKodu : secim
        return Self.desteklenenDiller.contains(aday) ? aday : "tr"
    }

    static var sistemKodu: String {
        let aday = Bundle.main.preferredLocalizations.first ?? "tr"
        let kisa = String(aday.prefix(2)).lowercased()
        return desteklenenDiller.contains(kisa) ? kisa : "tr"
    }

    var locale: Locale { Locale(identifier: kod) }

    /// Bir dil seçeneğinin menüde görünen adı.
    func dilAdi(_ secenek: UygulamaDili) -> String {
        secenek == .sistem ? metin("dil.sistem") : secenek.ozAd
    }

    /// Seçicinin satırında gösterilen dil adı.
    var seciliDilAdi: String {
        if secim == UygulamaDili.sistem.rawValue { return metin("dil.sistem") }
        return UygulamaDili(rawValue: secim)?.ozAd ?? ""
    }

    private var paket: Bundle {
        guard let yol = Bundle.main.path(forResource: kod, ofType: "lproj"),
              let paket = Bundle(path: yol) else { return .main }
        return paket
    }

    private static var turkcePaket: Bundle? {
        guard let yol = Bundle.main.path(forResource: "tr", ofType: "lproj") else { return nil }
        return Bundle(path: yol)
    }

    /// Seçili dildeki metni döndürür. Anahtar o dilde yoksa Türkçe metne,
    /// o da yoksa anahtarın kendisine düşer.
    func metin(_ anahtar: String) -> String {
        let deger = paket.localizedString(forKey: anahtar, value: Self.eksik, table: nil)
        if deger != Self.eksik { return deger }

        if kod != "tr", let tr = Self.turkcePaket {
            let trDeger = tr.localizedString(forKey: anahtar, value: Self.eksik, table: nil)
            if trDeger != Self.eksik { return trDeger }
        }

        return anahtar
    }

    /// Biçimlendirilebilir anahtarlar için (ör. "%@").
    func metin(_ anahtar: String, _ degerler: CVarArg...) -> String {
        String(format: metin(anahtar), locale: locale, arguments: degerler)
    }

    /// Ajanın döndürdüğü hata kodunu yerel metne çevirir. Kod tanınmıyorsa
    /// sunucunun gönderdiği mesaj olduğu gibi gösterilir.
    func sunucuHatasi(kod: String, mesaj: String) -> String {
        let anahtar = "server.\(kod)"
        let yerel = metin(anahtar)
        return yerel == anahtar ? mesaj : yerel
    }

    /// Bayt sayısını seçili dilin ondalık ayracıyla biçimlendirir.
    func baytMetni(_ bayt: Int64) -> String {
        let metin = ByteCountFormatter.string(fromByteCount: bayt, countStyle: .file)
        let hedef = locale.decimalSeparator ?? ","
        let sistem = Locale.current.decimalSeparator ?? "."
        return metin.replacingOccurrences(of: sistem, with: hedef)
    }
}

// MARK: - DİL SEÇİCİ

struct DilSecici: View {
    @EnvironmentObject private var dil: Yerellestirme
    @Environment(\.dismiss) private var kapat

    var body: some View {
        VStack(spacing: 0) {
            HStack {
                Text(dil.metin("dil.baslik"))
                    .font(.headline)
                Spacer()
                Button(dil.metin("dil.kapat")) { kapat() }
            }
            .padding()

            List {
                ForEach(UygulamaDili.allCases) { secenek in
                    Button {
                        dil.secim = secenek.rawValue
                    } label: {
                        HStack {
                            Text(secenek == .sistem ? dil.metin("dil.sistem") : secenek.ozAd)
                                .foregroundStyle(.primary)
                            Spacer()
                            if dil.secim == secenek.rawValue {
                                Image(systemName: "checkmark")
                                    .foregroundStyle(.orange)
                            }
                        }
                    }
                }
            }
            #if os(tvOS)
            .listStyle(.plain)
            #endif
        }
        #if os(tvOS)
        .frame(width: 760, height: 560)
        #endif
    }
}

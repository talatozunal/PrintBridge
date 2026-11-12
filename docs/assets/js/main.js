/* =========================================================
   PrintBridge — site betiği
   - İki dilli arayüz (Türkçe, İngilizce)
   - Mobil menü, dil menüsü, kaydırma efektleri, SSS akordeonu
   ========================================================= */

(function () {
  "use strict";

  var I18N = {
    tr: {
      "meta.title": "PrintBridge — iPhone'den Windows yazıcısına",
      "meta.description": "iPhone'den, aynı Wi-Fi ağındaki Windows 10 PC'ye USB ile bağlı yazıcıya fotoğraf ve belge gönderin. Bulut yok, hesap yok; yalnızca yerel ağ.",
      "a11y.skip": "İçeriğe geç",
      "nav.features": "Özellikler",
      "nav.arch": "Mimari",
      "nav.privacy": "Gizlilik",
      "nav.faq": "S.S.S.",
      "nav.cta": "GitHub",
      "hero.badge": "Yerel ağ · Bulutsuz yazdırma",
      "hero.title": "iPhone'den yazdırın,",
      "hero.titleAccent": "Windows yazıcıya.",
      "hero.lead": "PhonePrint, aynı Wi-Fi ağındaki Windows 10 PC'ye USB ile bağlı yazıcıya fotoğraf ve belge gönderir. Bulut, hesap veya sürücü kurulumu yok; iş ajan üzerinden Windows yazdırma kuyruğuna gider.",
      "hero.cta1": "Kaynak kodu gör",
      "hero.cta2": "Nasıl çalışır",
      "hero.chip1": "İnternetsiz",
      "hero.chip2": "QR / PIN eşleştirme",
      "hero.chip3": "Beş dil",
      "hero.note": "iOS 16+ · Windows 10 · USB yazıcı",
      "mock.connected": "Bağlı",
      "mock.file": "fatura.pdf",
      "mock.size": "240 KB",
      "mock.copies": "Kopya",
      "mock.paper": "Kâğıt",
      "mock.orientation": "Yön",
      "mock.portrait": "Dikey",
      "mock.fit": "Sığdır",
      "mock.on": "Açık",
      "mock.status": "Yazdırılıyor · %68",
      "mock.button": "Yazdır",
      "float.group": "QR / PIN",
      "float.groupSub": "6 haneli eşleştirme",
      "float.badge": "Bearer token",
      "float.badgeSub": "Cihaza özel anahtar",
      "float.lang": "5 dil",
      "stats.1": "parça",
      "stats.2": "dosya türü",
      "stats.3": "USB yazıcı",
      "stats.4": "bulut",
      "stats.5": "dil",
      "features.eyebrow": "Özellikler",
      "features.title": "Telefonda seçin, yazıcıda basın",
      "features.lead": "Sistem iki parçadan oluşur: iPhone uygulaması ve Windows ajanı.",
      "group.ios": "iPhone · PhonePrint",
      "group.win": "Windows · PrintBridge Agent",
      "i1.title": "Otomatik Keşif",
      "i1.text": "Ajan mDNS ile kendini duyurur; uygulama PC'yi bulur, gerekirse IP/port elle girilir.",
      "i2.title": "QR ve PIN Eşleştirme",
      "i2.text": "QR kodu okutun veya 6 haneli PIN'i girin; cihaza özel token Keychain'de saklanır.",
      "i3.title": "Yazdırma Seçenekleri",
      "i3.text": "Kopya sayısı, kâğıt boyutu, yön, sayfaya sığdırma ve sayfa aralığı.",
      "i4.title": "Canlı İş Takibi",
      "i4.text": "Yükleme durumu, iptal, yeniden deneme ve iş geçmişi tek ekranda.",
      "i5.title": "Fotoğraf ve Belge",
      "i5.text": "Fotoğraflar, Dosyalar veya Safari'den PDF, JPEG, PNG, HEIC ve TXT gönderin.",
      "i6.title": "Beş Dil",
      "i6.text": "Türkçe, İngilizce, Almanca, Fransızca, İtalyanca; yeniden başlatmadan değişir.",
      "w1.title": "Tek .exe, Tepside",
      "w1.text": "PyInstaller ile paketlenmiş ajan tepside çalışır; otomatik başlatma isteğe bağlıdır.",
      "w2.title": "İş Kuyruğu",
      "w2.text": "FastAPI ve SQLite; idempotency ve yeniden deneme ile işleri sıraya alır.",
      "w3.title": "Görsel, Metin, PDF",
      "w3.text": "Dosyayı sayfaya yerleştirir ve GDI ile Windows yazdırma kuyruğuna verir.",
      "w4.title": "mDNS ve Eşleştirme",
      "w4.text": "Yerel ağda keşif, QR/PIN eşleştirme, token hash'leme ve hız sınırlama.",
      "w5.title": "Güvenlik Duvarı",
      "w5.text": "Kural yardımcısı ve tanılama ile ajanın ağda erişilebilir olmasını sağlar.",
      "w6.title": "Sıfır Bulut",
      "w6.text": "Hiçbir veri dışarıya çıkmaz; dosyalar yalnızca LAN üzerinden ajana gider.",
      "arch.eyebrow": "Mimari",
      "arch.title": "Dört durak, tek yerel ağ",
      "arch.lead": "Dosya telefondan çıkar, ajan üzerinden yazıcıya ulaşır.",
      "flow.1t": "iPhone · PhonePrint",
      "flow.1s": "Belgeyi seçer, seçenekleri ayarlar",
      "flow.a1": "HTTP + token",
      "flow.2t": "Windows · Ajan",
      "flow.2s": "mDNS, QR/PIN ve bearer token",
      "flow.a2": "Yazdırma işi",
      "flow.3t": "Windows Spooler",
      "flow.3s": "İşi yazdırma kuyruğuna alır",
      "flow.a3": "USB",
      "flow.4t": "USB Yazıcı",
      "flow.4s": "Sayfayı basar",
      "how.eyebrow": "Nasıl çalışır",
      "how.title": "Altı adımda ilk baskı",
      "how.1t": "Ajanı başlatın",
      "how.1d": "Windows PC'de PrintBridge-Agent.exe çalışsın; yazıcı USB ile bağlı olsun.",
      "how.2t": "Eşleştirin",
      "how.2d": "QR kodu okutun veya 6 haneli PIN'i girin; uygulama cihaza özel token alır.",
      "how.3t": "Belgeyi seçin",
      "how.3d": "Fotoğraflar, Dosyalar veya Safari'den bir fotoğraf ya da belge seçin.",
      "how.4t": "Seçenekleri ayarlayın",
      "how.4d": "Kopya, kâğıt boyutu, yön ve sayfa aralığını belirleyin.",
      "how.5t": "Gönderin",
      "how.5d": "Dosya LAN üzerinden ajana yüklenir ve yazdırma kuyruğuna verilir.",
      "how.6t": "Durumu izleyin",
      "how.6d": "İlerlemeyi görün; gerekirse iptal edin veya yeniden deneyin.",
      "privacy.eyebrow": "Gizlilik",
      "privacy.title": "Veri buluta çıkmaz, LAN'da kalır.",
      "privacy.lead": "Eşleştirme token'ı çalışma zamanında üretilir; ajan yalnızca SHA-256 özetini saklar, iPhone token'ı Keychain'de tutar.",
      "privacy.1": "Depoda playlist, hesap, kullanıcı adı, şifre veya API anahtarı yok.",
      "privacy.2": "Trafik LAN üzerinde HTTP + bearer token ile korunur; uygulama yalnızca yerel ağa erişir.",
      "privacy.3": "Alınan dosyalar Windows yazdırma kuyruğuna verilir; kalıcı bir bulut kopyası oluşmaz.",
      "privacy.note": "TLS henüz yoktur. Ajanı yalnızca güvendiğiniz yerel ağlarda kullanın.",
      "privacy.link": "Güvenlik notlarını okuyun",
      "privacy.badge": "LAN içinde",
      "faq.eyebrow": "S.S.S.",
      "faq.title": "Sık sorulan sorular",
      "faq.1q": "İnternet gerekiyor mu?",
      "faq.1a": "Hayır. Telefon ve Windows PC aynı Wi-Fi ağındaysa yeterli; bulut veya hesap yok.",
      "faq.2q": "Hangi yazıcılar destekleniyor?",
      "faq.2a": "Windows 10'un yazdırma kuyruğuna kurulu, PC'ye USB ile bağlı yazıcılar.",
      "faq.3q": "Hangi dosyaları gönderebilirim?",
      "faq.3a": "PDF, JPEG, PNG, HEIC ve TXT. Fotoğraflar, Dosyalar veya Safari paylaşım menüsünden gönderilir.",
      "faq.4q": "Android veya Mac sürümü var mı?",
      "faq.4a": "Şimdilik iPhone için iOS 16+ uygulaması ve Windows 10 ajanı var.",
      "faq.5q": "Aktarım güvenli mi?",
      "faq.5a": "Eşleştirme token'ı Keychain'de, özeti ajanda saklanır. Trafik LAN'da HTTP + bearer token ile korunur; TLS henüz yoktur, güvenilmeyen ağlarda kullanmayın.",
      "faq.6q": "Ücretli mi?",
      "faq.6a": "Hayır. Proje MIT lisanslı ve açık kaynak; App Store sürümü henüz yayınlanmadı.",
      "dl.title": "İki parça, tek depo",
      "dl.lead": "Windows ajanını derleyin, iPhone uygulamasını Xcode ile çalıştırın.",
      "dl.github": "GitHub'da görüntüle",
      "dl.docs": "Windows kurulumu",
      "dl.ios": "iOS kurulumu",
      "dl.note": "App Store sürümü yok; ajan PyInstaller ile .exe olarak paketlenir.",
      "footer.tagline": "iPhone'den Windows yazıcısına, yerel ağ üzerinden.",
      "footer.by": "Talat Özünal"
    },
    en: {
      "meta.title": "PrintBridge — From iPhone to a Windows printer",
      "meta.description": "Send photos and documents from iPhone to a printer connected by USB to a Windows 10 PC on the same Wi-Fi network. No cloud, no account; local network only.",
      "a11y.skip": "Skip to content",
      "nav.features": "Features",
      "nav.arch": "Architecture",
      "nav.privacy": "Privacy",
      "nav.faq": "FAQ",
      "nav.cta": "GitHub",
      "hero.badge": "Local network · Cloud-free printing",
      "hero.title": "Print from your iPhone,",
      "hero.titleAccent": "to a Windows printer.",
      "hero.lead": "PhonePrint sends photos and documents to a printer connected by USB to a Windows 10 PC on the same Wi-Fi network. No cloud, account or driver setup; the job goes through the agent into the Windows print queue.",
      "hero.cta1": "View source code",
      "hero.cta2": "How it works",
      "hero.chip1": "No internet",
      "hero.chip2": "QR / PIN pairing",
      "hero.chip3": "Five languages",
      "hero.note": "iOS 16+ · Windows 10 · USB printer",
      "mock.connected": "Connected",
      "mock.file": "invoice.pdf",
      "mock.size": "240 KB",
      "mock.copies": "Copies",
      "mock.paper": "Paper",
      "mock.orientation": "Orientation",
      "mock.portrait": "Portrait",
      "mock.fit": "Fit",
      "mock.on": "On",
      "mock.status": "Printing · 68%",
      "mock.button": "Print",
      "float.group": "QR / PIN",
      "float.groupSub": "6-digit pairing",
      "float.badge": "Bearer token",
      "float.badgeSub": "Device-specific key",
      "float.lang": "5 languages",
      "stats.1": "parts",
      "stats.2": "file types",
      "stats.3": "USB printer",
      "stats.4": "cloud",
      "stats.5": "languages",
      "features.eyebrow": "Features",
      "features.title": "Pick on the phone, print on the printer",
      "features.lead": "The system has two parts: an iPhone app and a Windows agent.",
      "group.ios": "iPhone · PhonePrint",
      "group.win": "Windows · PrintBridge Agent",
      "i1.title": "Automatic Discovery",
      "i1.text": "The agent advertises itself over mDNS; the app finds the PC, or you can enter an IP/port manually.",
      "i2.title": "QR and PIN Pairing",
      "i2.text": "Scan the QR code or enter the 6-digit PIN; the device-specific token is stored in the Keychain.",
      "i3.title": "Print Options",
      "i3.text": "Copies, paper size, orientation, fit-to-page and page range.",
      "i4.title": "Live Job Tracking",
      "i4.text": "Upload status, cancel, retry and job history on one screen.",
      "i5.title": "Photos and Documents",
      "i5.text": "Send PDF, JPEG, PNG, HEIC and TXT from Photos, Files or Safari.",
      "i6.title": "Five Languages",
      "i6.text": "Turkish, English, German, French, Italian; switch without restarting.",
      "w1.title": "Single .exe, in the Tray",
      "w1.text": "The PyInstaller-packaged agent runs in the system tray; autostart is optional.",
      "w2.title": "Job Queue",
      "w2.text": "FastAPI and SQLite queue jobs with idempotency and retries.",
      "w3.title": "Image, Text, PDF",
      "w3.text": "Places the file on the page and sends it to the Windows print queue via GDI.",
      "w4.title": "mDNS and Pairing",
      "w4.text": "Local discovery, QR/PIN pairing, token hashing and rate limiting.",
      "w5.title": "Firewall Helper",
      "w5.text": "A rule helper and diagnostics keep the agent reachable on the network.",
      "w6.title": "Zero Cloud",
      "w6.text": "No data leaves your network; files only travel over the LAN to the agent.",
      "arch.eyebrow": "Architecture",
      "arch.title": "Four stops, one local network",
      "arch.lead": "The file leaves the phone and reaches the printer through the agent.",
      "flow.1t": "iPhone · PhonePrint",
      "flow.1s": "Picks the document and options",
      "flow.a1": "HTTP + token",
      "flow.2t": "Windows · Agent",
      "flow.2s": "mDNS, QR/PIN and bearer token",
      "flow.a2": "Print job",
      "flow.3t": "Windows Spooler",
      "flow.3s": "Queues the job for printing",
      "flow.a3": "USB",
      "flow.4t": "USB Printer",
      "flow.4s": "Prints the page",
      "how.eyebrow": "How it works",
      "how.title": "First print in six steps",
      "how.1t": "Start the agent",
      "how.1d": "Run PrintBridge-Agent.exe on the Windows PC; the printer is connected by USB.",
      "how.2t": "Pair",
      "how.2d": "Scan the QR code or enter the 6-digit PIN; the app receives a device-specific token.",
      "how.3t": "Pick a document",
      "how.3d": "Choose a photo or document from Photos, Files or Safari.",
      "how.4t": "Set the options",
      "how.4d": "Choose copies, paper size, orientation and page range.",
      "how.5t": "Send",
      "how.5d": "The file uploads to the agent over the LAN and enters the print queue.",
      "how.6t": "Track the status",
      "how.6d": "Watch progress; cancel or retry if needed.",
      "privacy.eyebrow": "Privacy",
      "privacy.title": "Data never reaches the cloud; it stays on the LAN.",
      "privacy.lead": "The pairing token is generated at runtime; the agent stores only its SHA-256 hash and the iPhone keeps the token in the Keychain.",
      "privacy.1": "The repository contains no playlist, account, username, password or API key.",
      "privacy.2": "Traffic is protected on the LAN with HTTP + bearer token; the app only accesses the local network.",
      "privacy.3": "Received files are handed to the Windows print queue; no permanent cloud copy is created.",
      "privacy.note": "TLS is not implemented yet. Use the agent only on local networks you trust.",
      "privacy.link": "Read the security notes",
      "privacy.badge": "On the LAN",
      "faq.eyebrow": "FAQ",
      "faq.title": "Frequently asked questions",
      "faq.1q": "Does it need internet?",
      "faq.1a": "No. It is enough that the phone and the Windows PC are on the same Wi-Fi network; there is no cloud or account.",
      "faq.2q": "Which printers are supported?",
      "faq.2a": "Printers installed in the Windows 10 print queue and connected to the PC by USB.",
      "faq.3q": "Which files can I send?",
      "faq.3a": "PDF, JPEG, PNG, HEIC and TXT, sent from Photos, Files or the Safari share sheet.",
      "faq.4q": "Is there an Android or Mac version?",
      "faq.4a": "For now there is an iOS 16+ app for iPhone and a Windows 10 agent.",
      "faq.5q": "Is the transfer secure?",
      "faq.5a": "The pairing token lives in the Keychain and its hash on the agent. Traffic is protected on the LAN with HTTP + bearer token; TLS is not implemented yet, so do not use it on untrusted networks.",
      "faq.6q": "Is it paid?",
      "faq.6a": "No. The project is MIT-licensed and open source; the App Store version has not been released yet.",
      "dl.title": "Two parts, one repository",
      "dl.lead": "Build the Windows agent and run the iPhone app from Xcode.",
      "dl.github": "View on GitHub",
      "dl.docs": "Windows setup",
      "dl.ios": "iOS setup",
      "dl.note": "No App Store release; the agent is packaged as a .exe with PyInstaller.",
      "footer.tagline": "From iPhone to a Windows printer, over your local network.",
      "footer.by": "Talat Özünal"
    }
  };

  var STORAGE_KEY = "printbridge.lang";
  var DEFAULT_LANG = "tr";
  var SUPPORTED = ["tr", "en"];
  var CODES = { tr: "TR", en: "EN" };

  var root = document.documentElement;
  var langBox = document.getElementById("lang");
  var langButton = document.getElementById("langButton");
  var langMenu = document.getElementById("langMenu");
  var langCode = document.getElementById("langCode");
  var burger = document.getElementById("burger");
  var nav = document.getElementById("nav");
  var header = document.getElementById("header");

  function normalize(code) {
    if (!code) return null;
    var base = String(code).toLowerCase().split("-")[0];
    return SUPPORTED.indexOf(base) >= 0 ? base : null;
  }

  function storedLang() {
    try { return normalize(localStorage.getItem(STORAGE_KEY)); } catch (e) { return null; }
  }

  function browserLang() {
    var list = navigator.languages || [navigator.language || ""];
    for (var i = 0; i < list.length; i++) {
      var found = normalize(list[i]);
      if (found) return found;
    }
    return null;
  }

  function translate(code) {
    var dict = I18N[code] || I18N[DEFAULT_LANG];
    var nodes = document.querySelectorAll("[data-i18n]");
    for (var i = 0; i < nodes.length; i++) {
      var key = nodes[i].getAttribute("data-i18n");
      if (Object.prototype.hasOwnProperty.call(dict, key)) {
        nodes[i].textContent = dict[key];
      }
    }
    document.title = dict["meta.title"] || document.title;
    var desc = document.querySelector('meta[name="description"]');
    if (desc && dict["meta.description"]) desc.setAttribute("content", dict["meta.description"]);
    root.setAttribute("lang", code);
    if (langCode) langCode.textContent = CODES[code] || code.toUpperCase();

    var items = document.querySelectorAll(".lang__item");
    for (var j = 0; j < items.length; j++) {
      var active = items[j].getAttribute("data-lang") === code;
      items[j].classList.toggle("is-active", active);
      items[j].setAttribute("aria-current", active ? "true" : "false");
    }
  }

  function setLang(code, remember) {
    var safe = SUPPORTED.indexOf(code) >= 0 ? code : DEFAULT_LANG;
    translate(safe);
    if (remember) {
      try { localStorage.setItem(STORAGE_KEY, safe); } catch (e) { /* yoksay */ }
    }
  }

  /* --- dil menüsü --- */
  function openLang(open) {
    if (!langBox || !langButton) return;
    langBox.classList.toggle("is-open", open);
    langButton.setAttribute("aria-expanded", open ? "true" : "false");
  }

  if (langButton) {
    langButton.addEventListener("click", function (event) {
      event.stopPropagation();
      openLang(!langBox.classList.contains("is-open"));
    });
  }

  if (langMenu) {
    langMenu.addEventListener("click", function (event) {
      var button = event.target.closest(".lang__item");
      if (!button) return;
      setLang(button.getAttribute("data-lang"), true);
      openLang(false);
      if (langButton) langButton.focus();
    });
  }

  document.addEventListener("click", function (event) {
    if (langBox && !langBox.contains(event.target)) openLang(false);
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      openLang(false);
      closeNav();
    }
  });

  /* --- mobil menü --- */
  function closeNav() {
    if (!nav || !burger) return;
    nav.classList.remove("is-open");
    burger.setAttribute("aria-expanded", "false");
  }

  if (burger) {
    burger.addEventListener("click", function () {
      var open = !nav.classList.contains("is-open");
      nav.classList.toggle("is-open", open);
      burger.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  if (nav) {
    nav.addEventListener("click", function (event) {
      if (event.target.closest("a")) closeNav();
    });
  }

  /* --- kaydırma durumu --- */
  function onScroll() {
    if (!header) return;
    header.classList.toggle("is-scrolled", window.scrollY > 8);
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  /* --- görünürlük animasyonu --- */
  var revealItems = document.querySelectorAll("[data-reveal]");
  if ("IntersectionObserver" in window) {
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-in");
          observer.unobserve(entry.target);
        }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });

    for (var r = 0; r < revealItems.length; r++) {
      revealItems[r].classList.add("will-reveal");
      observer.observe(revealItems[r]);
    }
  } else {
    for (var s = 0; s < revealItems.length; s++) revealItems[s].classList.add("is-in");
  }

  /* --- SSS: aynı anda tek soru açık kalsın --- */
  var faqItems = document.querySelectorAll(".faq__item");
  for (var f = 0; f < faqItems.length; f++) {
    faqItems[f].addEventListener("toggle", function () {
      if (!this.open) return;
      for (var k = 0; k < faqItems.length; k++) {
        if (faqItems[k] !== this) faqItems[k].open = false;
      }
    });
  }

  /* --- başlangıç dili --- */
  var initial = storedLang() || DEFAULT_LANG;
  setLang(initial, false);
  if (!storedLang()) {
    var detected = browserLang();
    if (detected && detected !== DEFAULT_LANG) setLang(detected, false);
  }
})();

import SwiftUI

struct DiscoveryView: View {
    @StateObject private var discovery = DiscoveryService()
    @State private var selected: DiscoveredAgent?
    @State private var showingManual = false
    @State private var showingScanner = false
    @State private var isLanguagePresented = false
    @EnvironmentObject var appState: AppState
    @EnvironmentObject private var dil: Yerellestirme

    var body: some View {
        NavigationStack {
            List(discovery.agents) { agent in
                Button {
                    selected = agent
                } label: {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(agent.name).font(.headline)
                        Text("\(agent.hostName):\(agent.port)")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                }
            }
            .navigationTitle(dil.metin("discovery.title"))
            .toolbar {
                ToolbarItemGroup(placement: .topBarLeading) {
                    Button {
                        isLanguagePresented = true
                    } label: {
                        Label(dil.metin("dil.sec"), systemImage: "globe")
                    }
                }
                ToolbarItemGroup(placement: .topBarTrailing) {
                    Button(dil.metin("discovery.qr")) { showingScanner = true }
                    Button(dil.metin("discovery.manual")) { showingManual = true }
                }
            }
            .overlay {
                if discovery.agents.isEmpty {
                    ProgressView(dil.metin("discovery.searching"))
                }
            }
            .sheet(item: $selected) { agent in
                PairingView(agent: agent)
            }
            .sheet(isPresented: $showingManual) {
                ManualConnectView { agent in
                    showingManual = false
                    // Sayfa kapanmadan yeni sayfa açmayı denememek için kısa gecikme.
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.45) {
                        selected = agent
                    }
                }
            }
            .sheet(isPresented: $showingScanner) {
                QRScannerView { code in
                    showingScanner = false
                    if let agent = parsePairURL(code) {
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.45) {
                            selected = agent
                        }
                    }
                }
                .ignoresSafeArea()
            }
            .sheet(isPresented: $isLanguagePresented) {
                DilSecici()
            }
        }
        .onAppear { discovery.start() }
        .onDisappear { discovery.stop() }
    }
}

private func parsePairURL(_ code: String) -> DiscoveredAgent? {
    guard let url = URL(string: code),
          url.scheme == "printbridge",
          url.host == "pair" else {
        return nil
    }
    // printbridge://pair?...
    let comps = URLComponents(url: url, resolvingAgainstBaseURL: false)
    let q = comps?.queryItems ?? []
    func value(_ name: String) -> String? { q.first(where: { $0.name == name })?.value }
    guard let host = value("host") else { return nil }
    let port = Int(value("port") ?? "8477") ?? 8477
    let id = value("id") ?? host
    let name = value("name") ?? host
    return DiscoveredAgent(id: id, name: name, hostName: host, port: port, txt: [:])
}

struct ManualConnectView: View {
    var onConnect: (DiscoveredAgent) -> Void
    @EnvironmentObject private var dil: Yerellestirme
    @Environment(\.dismiss) private var dismiss
    @State private var host = ""
    @State private var port = "8477"

    var body: some View {
        NavigationStack {
            Form {
                TextField(dil.metin("manual.host"), text: $host)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .keyboardType(.URL)
                TextField(dil.metin("manual.port"), text: $port).keyboardType(.numberPad)
            }
            .navigationTitle(dil.metin("manual.title"))
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button(dil.metin("manual.connect")) {
                        guard !host.isEmpty, let p = Int(port) else { return }
                        onConnect(DiscoveredAgent(id: "manual-\(host)", name: host,
                                                  hostName: host, port: p, txt: [:]))
                        dismiss()
                    }
                }
                ToolbarItem(placement: .cancellationAction) {
                    Button(dil.metin("common.cancel")) { dismiss() }
                }
            }
        }
    }
}

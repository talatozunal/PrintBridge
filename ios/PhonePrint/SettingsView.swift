import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var appState: AppState
    @EnvironmentObject private var dil: Yerellestirme
    @State private var printers: [Printer] = []
    @State private var isLanguagePresented = false

    var body: some View {
        NavigationStack {
            Form {
                Section(dil.metin("settings.agent")) {
                    Text(appState.agentName ?? "-")
                    if let base = appState.baseURL {
                        Text(base.absoluteString).font(.caption).foregroundStyle(.secondary)
                    }
                }
                Section(dil.metin("settings.printers")) {
                    ForEach(printers) { p in
                        HStack {
                            Text(p.name)
                            Spacer()
                            if p.isDefault { Image(systemName: "checkmark") }
                        }
                    }
                }
                Section {
                    Button {
                        isLanguagePresented = true
                    } label: {
                        HStack {
                            Text(dil.metin("dil.sec"))
                            Spacer()
                            Text(dil.seciliDilAdi).foregroundStyle(.secondary)
                        }
                    }
                    .sheet(isPresented: $isLanguagePresented) {
                        DilSecici()
                    }
                }
                Section {
                    Button(dil.metin("settings.unpair"), role: .destructive) {
                        appState.clearSession()
                    }
                }
            }
            .navigationTitle(dil.metin("settings.title"))
            .task {
                guard let base = appState.baseURL, let token = appState.token else { return }
                let client = APIClient(baseURL: base, token: token)
                printers = (try? await client.printers()) ?? []
            }
        }
    }
}

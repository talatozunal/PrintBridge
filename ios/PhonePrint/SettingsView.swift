import SwiftUI

struct SettingsView: View {
    @EnvironmentObject var appState: AppState
    @State private var printers: [Printer] = []

    var body: some View {
        NavigationStack {
            Form {
                Section("Ajan") {
                    Text(appState.agentName ?? "-")
                    if let base = appState.baseURL {
                        Text(base.absoluteString).font(.caption).foregroundStyle(.secondary)
                    }
                }
                Section("Yazıcılar") {
                    ForEach(printers) { p in
                        HStack {
                            Text(p.name)
                            Spacer()
                            if p.isDefault { Image(systemName: "checkmark") }
                        }
                    }
                }
                Section {
                    Button("Eşleşmeyi kaldır", role: .destructive) {
                        appState.clearSession()
                    }
                }
            }
            .navigationTitle("Ayarlar")
            .task {
                guard let base = appState.baseURL, let token = appState.token else { return }
                let client = APIClient(baseURL: base, token: token)
                printers = (try? await client.printers()) ?? []
            }
        }
    }
}

import SwiftUI

struct ContentView: View {
    @EnvironmentObject var appState: AppState
    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        Group {
            if appState.isPaired {
                VStack(spacing: 0) {
                    if appState.connectionLost {
                        connectionBanner
                    }
                    TabView {
                        PrintView().tabItem { Label("Yazdır", systemImage: "printer") }
                        JobHistoryView().tabItem { Label("İşler", systemImage: "list.bullet") }
                        SettingsView().tabItem { Label("Ayarlar", systemImage: "gear") }
                    }
                }
            } else {
                DiscoveryView()
            }
        }
        .task(id: appState.isPaired) {
            if appState.isPaired { await appState.verifyConnection() }
        }
        .onChange(of: scenePhase) { phase in
            if phase == .active, appState.isPaired {
                Task { await appState.verifyConnection() }
            }
        }
    }

    private var connectionBanner: some View {
        HStack {
            Image(systemName: "wifi.exclamationmark")
            Text("PC'ye ulaşılamıyor")
            Spacer()
            if appState.isReconnecting {
                ProgressView()
            } else {
                Button("Tekrar dene") { Task { await appState.verifyConnection() } }
            }
        }
        .font(.footnote)
        .padding(10)
        .background(Color.yellow.opacity(0.25))
    }
}

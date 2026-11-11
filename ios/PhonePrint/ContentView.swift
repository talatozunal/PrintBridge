import SwiftUI

struct ContentView: View {
    @EnvironmentObject var appState: AppState
    @EnvironmentObject private var dil: Yerellestirme
    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        Group {
            if appState.isPaired {
                VStack(spacing: 0) {
                    if appState.connectionLost {
                        connectionBanner
                    }
                    TabView {
                        PrintView().tabItem { Label(dil.metin("tab.print"), systemImage: "printer") }
                        JobHistoryView().tabItem { Label(dil.metin("tab.jobs"), systemImage: "list.bullet") }
                        SettingsView().tabItem { Label(dil.metin("tab.settings"), systemImage: "gear") }
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
            Text(dil.metin("conn.unreachable"))
            Spacer()
            if appState.isReconnecting {
                ProgressView()
            } else {
                Button(dil.metin("conn.retry")) { Task { await appState.verifyConnection() } }
            }
        }
        .font(.footnote)
        .padding(10)
        .background(Color.yellow.opacity(0.25))
    }
}

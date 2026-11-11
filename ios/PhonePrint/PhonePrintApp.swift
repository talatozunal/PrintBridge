import SwiftUI
import Combine

@main
struct PhonePrintApp: App {
    @StateObject private var appState = AppState()
    @StateObject private var dil = Yerellestirme.paylasilan

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(appState)
                .environmentObject(dil)
        }
    }
}

final class AppState: ObservableObject {
    private enum Keys {
        static let baseURL = "pairedBaseURL"
        static let agentName = "pairedAgentName"
        static let agentId = "pairedAgentId"
    }

    @Published var token: String?
    @Published var agentName: String?
    @Published var agentId: String?
    @Published var printers: [Printer] = []
    @Published var baseURL: URL?
    @Published var isReconnecting = false
    @Published var connectionLost = false

    var isPaired: Bool { token != nil && baseURL != nil }

    init() {
        let defaults = UserDefaults.standard
        token = KeychainStore.readToken()
        // Token Keychain'de, adres bilgileri UserDefaults'ta saklanır.
        if token != nil {
            baseURL = defaults.string(forKey: Keys.baseURL).flatMap(URL.init(string:))
            agentName = defaults.string(forKey: Keys.agentName)
            agentId = defaults.string(forKey: Keys.agentId)
        }
    }

    func setSession(token: String, response: PairResponse, base: URL) {
        KeychainStore.saveToken(token)
        self.token = token
        self.agentName = response.agentName
        self.agentId = response.agentId
        self.printers = response.printers
        self.baseURL = base
        self.connectionLost = false

        let defaults = UserDefaults.standard
        defaults.set(base.absoluteString, forKey: Keys.baseURL)
        defaults.set(response.agentName, forKey: Keys.agentName)
        defaults.set(response.agentId, forKey: Keys.agentId)
    }

    func clearSession() {
        KeychainStore.deleteToken()
        token = nil
        agentName = nil
        agentId = nil
        printers = []
        baseURL = nil
        connectionLost = false

        let defaults = UserDefaults.standard
        defaults.removeObject(forKey: Keys.baseURL)
        defaults.removeObject(forKey: Keys.agentName)
        defaults.removeObject(forKey: Keys.agentId)
    }

    /// Uygulama açılırken / öne gelirken çağrılır: kayıtlı PC'ye ulaşılıyor mu bakar,
    /// ulaşılamazsa aynı agentId'yi mDNS ile yeniden arar (IP değişmiş olabilir).
    @MainActor
    func verifyConnection() async {
        guard let token, let base = baseURL, !isReconnecting else { return }
        isReconnecting = true
        defer { isReconnecting = false }

        if await loadPrinters(base: base, token: token) {
            connectionLost = false
            return
        }
        if let id = agentId,
           let found = await rediscover(agentId: id),
           await loadPrinters(base: found, token: token) {
            baseURL = found
            UserDefaults.standard.set(found.absoluteString, forKey: Keys.baseURL)
            connectionLost = false
            return
        }
        connectionLost = true
    }

    @MainActor
    private func loadPrinters(base: URL, token: String) async -> Bool {
        let client = APIClient(baseURL: base, token: token)
        do {
            printers = try await client.printers()
            return true
        } catch {
            return false
        }
    }

    @MainActor
    private func rediscover(agentId: String) async -> URL? {
        let discovery = DiscoveryService()
        discovery.start()
        defer { discovery.stop() }
        for _ in 0..<10 {
            try? await Task.sleep(nanoseconds: 500_000_000)
            if let agent = discovery.agents.first(where: { $0.id == agentId }),
               let url = agent.baseURL {
                return url
            }
        }
        return nil
    }
}

import SwiftUI

struct PairingView: View {
    let agent: DiscoveredAgent
    @EnvironmentObject var appState: AppState
    @Environment(\.dismiss) private var dismiss
    @State private var pin = ""
    @State private var deviceName = UIDevice.current.name
    @State private var isLoading = false
    @State private var error: String?

    var body: some View {
        NavigationStack {
            Form {
                Section("PC") {
                    Text(agent.name)
                    Text(agent.hostName).font(.caption).foregroundStyle(.secondary)
                }
                Section("Eşleştirme") {
                    TextField("Cihaz adı", text: $deviceName)
                    TextField("PIN", text: $pin).keyboardType(.numberPad)
                }
                if let error { Text(error).foregroundStyle(.red) }
            }
            .navigationTitle("Eşleştir")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Eşleştir") { Task { await pair() } }
                        .disabled(pin.count != 6 || isLoading)
                }
                ToolbarItem(placement: .cancellationAction) {
                    Button("İptal") { dismiss() }
                }
            }
        }
    }

    private func pair() async {
        guard let base = agent.baseURL else { return }
        isLoading = true
        defer { isLoading = false }
        do {
            let deviceId = UIDevice.current.identifierForVendor?.uuidString ?? UUID().uuidString
            let client = APIClient(baseURL: base)
            let resp = try await client.pair(pin: pin, deviceName: deviceName, deviceId: deviceId)
            await MainActor.run {
                appState.setSession(token: resp.token, response: resp, base: base)
                dismiss()
            }
        } catch {
            await MainActor.run { self.error = error.localizedDescription }
        }
    }
}

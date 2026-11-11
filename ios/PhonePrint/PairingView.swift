import SwiftUI

struct PairingView: View {
    let agent: DiscoveredAgent
    @EnvironmentObject var appState: AppState
    @EnvironmentObject private var dil: Yerellestirme
    @Environment(\.dismiss) private var dismiss
    @State private var pin = ""
    @State private var deviceName = UIDevice.current.name
    @State private var isLoading = false
    @State private var error: String?

    var body: some View {
        NavigationStack {
            Form {
                Section(dil.metin("pairing.pc")) {
                    Text(agent.name)
                    Text(agent.hostName).font(.caption).foregroundStyle(.secondary)
                }
                Section(dil.metin("pairing.section")) {
                    TextField(dil.metin("pairing.deviceName"), text: $deviceName)
                    TextField(dil.metin("pairing.pin"), text: $pin).keyboardType(.numberPad)
                }
                if let error { Text(error).foregroundStyle(.red) }
            }
            .navigationTitle(dil.metin("pairing.title"))
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button(dil.metin("pairing.action")) { Task { await pair() } }
                        .disabled(pin.count != 6 || isLoading)
                }
                ToolbarItem(placement: .cancellationAction) {
                    Button(dil.metin("common.cancel")) { dismiss() }
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

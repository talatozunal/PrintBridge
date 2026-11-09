import SwiftUI

struct JobHistoryView: View {
    @EnvironmentObject var appState: AppState
    @State private var jobs: [Job] = []
    @State private var selected: Job?

    var body: some View {
        NavigationStack {
            List(jobs) { job in
                Button {
                    selected = job
                } label: {
                    HStack {
                        VStack(alignment: .leading) {
                            Text(job.jobName ?? job.id).font(.headline)
                            Text(job.statusText).font(.caption).foregroundStyle(.secondary)
                        }
                        Spacer()
                        if let p = job.progress {
                            Text("\(Int(p * 100))%").font(.caption)
                        }
                    }
                }
            }
            .navigationTitle("İşler")
            .sheet(item: $selected) { JobDetailView(job: $0) }
            .task { await load() }
            .refreshable { await load() }
        }
    }

    private func load() async {
        guard let base = appState.baseURL, let token = appState.token else { return }
        let client = APIClient(baseURL: base, token: token)
        if let list = try? await client.jobs() {
            await MainActor.run { jobs = list }
        }
    }
}

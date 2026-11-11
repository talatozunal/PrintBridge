import SwiftUI
import UIKit

struct JobDetailView: View {
    let initialJob: Job
    @EnvironmentObject var appState: AppState
    @EnvironmentObject private var dil: Yerellestirme
    @State private var job: Job
    @State private var preview: Image?
    @State private var timer: Timer?

    init(job: Job) {
        self.initialJob = job
        _job = State(initialValue: job)
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    Text(job.jobName ?? dil.metin("job.defaultName")).font(.title2.bold())
                    Text(statusText).foregroundStyle(.secondary)
                    ProgressView(value: job.progressValue)
                    if let pages = job.pages {
                        Text(dil.metin("job.pages", job.printedPages ?? 0, pages))
                    }
                    if let err = job.error {
                        Text(Yerellestirme.paylasilan.sunucuHatasi(kod: err.code, mesaj: err.message))
                            .foregroundStyle(.red)
                    }
                    if let preview {
                        preview.resizable().scaledToFit()
                    }
                    HStack {
                        if !job.isTerminal {
                            Button(dil.metin("job.cancel")) { Task { await cancel() } }
                        }
                        if job.status == "failed" {
                            Button(dil.metin("job.retry")) { Task { await retry() } }
                        }
                    }
                }.padding()
            }
            .navigationTitle(dil.metin("job.title"))
            .navigationBarTitleDisplayMode(.inline)
        }
        .onAppear { startPolling() }
        .onDisappear { timer?.invalidate() }
    }

    private var statusText: String {
        job.statusText
    }

    private func startPolling() {
        Task { await refresh() }
        timer?.invalidate()
        timer = Timer.scheduledTimer(withTimeInterval: 1.5, repeats: true) { _ in
            Task { await refresh() }
        }
    }

    private func refresh() async {
        guard let base = appState.baseURL, let token = appState.token else { return }
        let client = APIClient(baseURL: base, token: token)
        do {
            let j = try await client.job(id: job.id)
            await MainActor.run {
                job = j
                if j.isTerminal { timer?.invalidate() }
            }
            // Önizleme sadece bir kez indirilir.
            if preview == nil, j.status == "done" || j.status == "printing" {
                await loadPreview()
            }
        } catch { }
    }

    private func loadPreview() async {
        guard let base = appState.baseURL, let token = appState.token else { return }
        let client = APIClient(baseURL: base, token: token)
        let url = client.previewURL(jobId: job.id, page: 1)
        var req = URLRequest(url: url)
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        if let (data, _) = try? await URLSession.shared.data(for: req),
           let ui = UIImage(data: data) {
            await MainActor.run { preview = Image(uiImage: ui) }
        }
    }

    private func cancel() async {
        guard let base = appState.baseURL, let token = appState.token else { return }
        let client = APIClient(baseURL: base, token: token)
        try? await client.cancel(id: job.id)
        await refresh()
    }

    private func retry() async {
        guard let base = appState.baseURL, let token = appState.token else { return }
        let client = APIClient(baseURL: base, token: token)
        if let newJob = try? await client.retry(id: job.id) {
            await MainActor.run {
                job = newJob
                preview = nil
                startPolling()
            }
        }
    }
}

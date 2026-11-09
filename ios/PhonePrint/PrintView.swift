import SwiftUI
import PhotosUI
import UIKit
import UniformTypeIdentifiers

struct PrintView: View {
    @EnvironmentObject var appState: AppState
    @State private var selectedItem: PhotosPickerItem?
    @State private var fileURL: URL?
    @State private var fileName: String?
    @State private var options = PrintOptions()
    @State private var isPickingFile = false
    @State private var isPrinting = false
    @State private var error: String?
    @State private var job: Job?
    @State private var showingJob = false

    var body: some View {
        NavigationStack {
            Form {
                Section("Dosya") {
                    PhotosPicker(selection: $selectedItem, matching: .images) {
                        Label("Fotoğraf seç", systemImage: "photo")
                    }
                    Button("Dosya seç") { isPickingFile = true }
                    if let fileName { Text(fileName).font(.caption) }
                }
                Section("Seçenekler") {
                    Picker("Kâğıt", selection: Binding(
                        get: { options.paper ?? (appState.printers.first?.papers?.first ?? "A4") },
                        set: { options.paper = $0 }
                    )) {
                        ForEach(appState.printers.first?.papers ?? ["A4", "Letter"], id: \.self) { Text($0) }
                    }
                    Stepper("Kopya: \(options.copies)", value: $options.copies, in: 1...99)
                    Picker("Yön", selection: $options.orientation) {
                        Text("Otomatik").tag("auto")
                        Text("Dikey").tag("portrait")
                        Text("Yatay").tag("landscape")
                    }
                    Picker("Sığdır", selection: $options.fit) {
                        Text("Sığdır").tag("fit")
                        Text("Doldur").tag("fill")
                        Text("Gerçek boyut").tag("none")
                    }
                    TextField("Sayfa aralığı (1-3,5)", text: Binding(
                        get: { options.pageRange ?? "" },
                        set: { options.pageRange = $0.isEmpty ? nil : $0 }
                    ))
                    TextField("İş adı", text: Binding(
                        get: { options.jobName ?? "" },
                        set: { options.jobName = $0.isEmpty ? nil : $0 }
                    ))
                }
                if let error { Text(error).foregroundStyle(.red) }
            }
            .navigationTitle("Yazdır")
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("Yazdır") { Task { await print() } }
                        .disabled(fileURL == nil || isPrinting)
                }
            }
            .fileImporter(isPresented: $isPickingFile, allowedContentTypes: [.image, .pdf, .plainText]) { result in
                guard case .success(let url) = result else { return }
                // Files uygulamasından gelen URL'ler güvenlik kapsamlıdır; okumadan önce erişim açılmalı.
                let scoped = url.startAccessingSecurityScopedResource()
                defer { if scoped { url.stopAccessingSecurityScopedResource() } }
                let tmp = FileManager.default.temporaryDirectory
                    .appendingPathComponent("\(UUID().uuidString)-\(url.lastPathComponent)")
                do {
                    try FileManager.default.copyItem(at: url, to: tmp)
                    fileURL = tmp
                    fileName = url.lastPathComponent
                    self.error = nil
                } catch {
                    self.error = error.localizedDescription
                }
            }
            .onChange(of: selectedItem) { newItem in
                Task {
                    // Seçilen veri HEIC olabilir; yazıcıya gerçek JPEG olarak gönderilir.
                    guard let data = try? await newItem?.loadTransferable(type: Data.self),
                          let image = UIImage(data: data),
                          let jpeg = image.jpegData(compressionQuality: 0.9) else { return }
                    let tmp = FileManager.default.temporaryDirectory
                        .appendingPathComponent("\(UUID().uuidString).jpg")
                    do {
                        try jpeg.write(to: tmp)
                        await MainActor.run {
                            fileURL = tmp
                            fileName = "Fotoğraf"
                            error = nil
                        }
                    } catch {
                        await MainActor.run { self.error = error.localizedDescription }
                    }
                }
            }
            .sheet(isPresented: $showingJob) {
                if let job { JobDetailView(job: job) }
            }
        }
    }

    private func print() async {
        guard let base = appState.baseURL, let token = appState.token, let fileURL else { return }
        isPrinting = true
        defer { isPrinting = false }
        do {
            options.printer = appState.printers.first(where: { $0.isDefault })?.id
                ?? appState.printers.first?.id
            // Geçici dosya adı UUID içerdiği için iş adı olarak kullanıcının
            // seçtiği özgün adı gönder.
            if options.jobName == nil, let fileName {
                options.jobName = URL(fileURLWithPath: fileName)
                    .deletingPathExtension().lastPathComponent
            }
            let client = APIClient(baseURL: base, token: token)
            let key = UUID().uuidString
            let created = try await client.createJob(fileURL: fileURL, options: options, idempotencyKey: key)
            await MainActor.run {
                job = created
                showingJob = true
            }
        } catch {
            await MainActor.run { self.error = error.localizedDescription }
        }
    }
}

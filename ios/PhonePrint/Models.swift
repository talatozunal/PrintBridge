import Foundation

struct Printer: Codable, Identifiable, Hashable {
    let id: String
    let name: String
    let `default`: Bool?
    let status: String?
    let papers: [String]?
    let duplex: Bool?
    let color: Bool?

    var isDefault: Bool { `default` ?? false }
    var isReady: Bool { status == "ready" }
}

struct PairResponse: Codable {
    let token: String
    let agentName: String
    let agentId: String
    let printers: [Printer]
}

struct HealthResponse: Codable {
    let name: String
    let version: String
    let paired: Bool
    let printerReady: Bool
}

struct JobError: Codable {
    let code: String
    let message: String
    let detail: String?
}

struct Job: Codable, Identifiable {
    let id: String
    let status: String
    let progress: Double?
    let pages: Int?
    let printedPages: Int?
    let createdAt: String?
    let startedAt: String?
    let finishedAt: String?
    let error: JobError?
    let jobName: String?

    var isTerminal: Bool {
        status == "done" || status == "failed" || status == "canceled"
    }
    var progressValue: Double { progress ?? 0 }

    var statusText: String {
        switch status {
        case "queued": return "Kuyrukta"
        case "rendering": return "Hazırlanıyor"
        case "printing": return "Yazdırılıyor"
        case "done": return "Tamamlandı"
        case "failed": return "Başarısız"
        case "canceled": return "İptal edildi"
        default: return status
        }
    }
}

struct JobListResponse: Codable {
    let jobs: [Job]
    let next: String?
}

struct PrintersResponse: Codable {
    let printers: [Printer]
}

struct PrintOptions: Codable {
    var printer: String?
    var copies: Int = 1
    var paper: String?
    var orientation: String = "auto"
    var fit: String = "fit"
    var pageRange: String?
    var jobName: String?
}

struct DiscoveredAgent: Identifiable, Hashable {
    let id: String
    let name: String
    let hostName: String
    let port: Int
    let txt: [String: String]

    var baseURL: URL? {
        URL(string: "http://\(hostName):\(port)")
    }
}

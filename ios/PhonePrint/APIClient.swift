import Foundation

final class APIClient {
    let baseURL: URL
    let token: String?

    init(baseURL: URL, token: String? = nil) {
        self.baseURL = baseURL
        self.token = token
    }

    // MARK: - Health / Pair / Printers

    func health() async throws -> HealthResponse {
        try await request(path: "health", method: "GET")
    }

    func pair(pin: String, deviceName: String, deviceId: String) async throws -> PairResponse {
        let body: [String: Any] = [
            "pin": pin,
            "deviceName": deviceName,
            "deviceId": deviceId
        ]
        let data = try JSONSerialization.data(withJSONObject: body)
        return try await request(path: "pair", method: "POST", body: data,
                                 headers: ["Content-Type": "application/json"])
    }

    func printers() async throws -> [Printer] {
        let resp: PrintersResponse = try await request(path: "printers", method: "GET")
        return resp.printers
    }

    // MARK: - Jobs

    func createJob(fileURL: URL, options: PrintOptions, idempotencyKey: String) async throws -> Job {
        let boundary = "Boundary-\(UUID().uuidString)"
        var body = Data()

        let filename = fileURL.lastPathComponent
        let mime = mimeType(for: fileURL)
        let fileData = try Data(contentsOf: fileURL)

        body.append("--\(boundary)\r\n")
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"\(filename)\"\r\n")
        body.append("Content-Type: \(mime)\r\n\r\n")
        body.append(fileData)
        body.append("\r\n")

        let optsData = try JSONEncoder().encode(options)
        body.append("--\(boundary)\r\n")
        body.append("Content-Disposition: form-data; name=\"options\"\r\n")
        body.append("Content-Type: application/json\r\n\r\n")
        body.append(optsData)
        body.append("\r\n")
        body.append("--\(boundary)--\r\n")

        var req = URLRequest(url: baseURL.appendingPathComponent("jobs"))
        req.httpMethod = "POST"
        req.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        if let token { req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        req.setValue(idempotencyKey, forHTTPHeaderField: "Idempotency-Key")
        req.httpBody = body

        let (data, response) = try await URLSession.shared.data(for: req)
        try validate(response: response, data: data)
        return try JSONDecoder().decode(Job.self, from: data)
    }

    func job(id: String) async throws -> Job {
        try await request(path: "jobs/\(id)", method: "GET")
    }

    func jobs(limit: Int = 20, before: String? = nil) async throws -> [Job] {
        var path = "jobs?limit=\(limit)"
        if let before { path += "&before=\(before)" }
        let resp: JobListResponse = try await request(path: path, method: "GET")
        return resp.jobs
    }

    func cancel(id: String) async throws {
        _ = try await requestRaw(path: "jobs/\(id)", method: "DELETE")
    }

    func retry(id: String) async throws -> Job {
        try await request(path: "jobs/\(id)/retry", method: "POST")
    }

    func previewURL(jobId: String, page: Int = 1) -> URL {
        baseURL.appendingPathComponent("jobs/\(jobId)/preview.png")
            .appendingQueryItems([URLQueryItem(name: "page", value: String(page))])
    }

    // MARK: - Internals

    private func request<T: Decodable>(path: String, method: String, body: Data? = nil, headers: [String: String] = [:]) async throws -> T {
        let data = try await requestRaw(path: path, method: method, body: body, headers: headers)
        return try JSONDecoder().decode(T.self, from: data)
    }

    /// `path` bir sorgu dizesi içerebilir ("jobs?limit=20"). `appendingPathComponent`
    /// "?" karakterini yüzde-kodladığı için URL'yi parçalara ayırarak kuruyoruz.
    private func url(for path: String) -> URL {
        let parts = path.split(separator: "?", maxSplits: 1, omittingEmptySubsequences: false)
        guard var comps = URLComponents(url: baseURL, resolvingAgainstBaseURL: false) else {
            return baseURL
        }
        var basePath = comps.path
        if !basePath.hasSuffix("/") { basePath += "/" }
        basePath += String(parts[0])
        comps.path = basePath
        if parts.count > 1 { comps.percentEncodedQuery = String(parts[1]) }
        return comps.url ?? baseURL.appendingPathComponent(path)
    }

    private func requestRaw(path: String, method: String, body: Data? = nil, headers: [String: String] = [:]) async throws -> Data {
        var req = URLRequest(url: url(for: path))
        req.httpMethod = method
        if let token { req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        for (k, v) in headers { req.setValue(v, forHTTPHeaderField: k) }
        req.httpBody = body
        let (data, response) = try await URLSession.shared.data(for: req)
        try validate(response: response, data: data)
        return data
    }

    private func validate(response: URLResponse, data: Data) throws {
        guard let http = response as? HTTPURLResponse else { return }
        guard (200..<300).contains(http.statusCode) else {
            if let err = try? JSONDecoder().decode(ServerError.self, from: data) {
                throw APIError.server(code: err.error.code, message: err.error.message)
            }
            throw APIError.http(status: http.statusCode)
        }
    }

    private func mimeType(for url: URL) -> String {
        switch url.pathExtension.lowercased() {
        case "jpg", "jpeg": return "image/jpeg"
        case "png": return "image/png"
        case "heic": return "image/heic"
        case "pdf": return "application/pdf"
        case "txt": return "text/plain"
        default: return "application/octet-stream"
        }
    }
}

struct ServerError: Codable { let error: JobError }

enum APIError: LocalizedError {
    case server(code: String, message: String)
    case http(status: Int)

    var errorDescription: String? {
        switch self {
        case .server(_, let message): return message
        case .http(let status): return "HTTP \(status)"
        }
    }
}

extension URL {
    func appendingQueryItems(_ items: [URLQueryItem]) -> URL {
        var comps = URLComponents(url: self, resolvingAgainstBaseURL: false)
        var existing = comps?.queryItems ?? []
        existing.append(contentsOf: items)
        comps?.queryItems = existing
        return comps?.url ?? self
    }
}

extension Data {
    mutating func append(_ string: String) {
        if let data = string.data(using: .utf8) { append(data) }
    }
}

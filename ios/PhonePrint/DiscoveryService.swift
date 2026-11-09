import Foundation
import Combine
import Darwin
import Network

final class DiscoveryService: NSObject, ObservableObject {
    @Published var agents: [DiscoveredAgent] = []

    private let browser = NetServiceBrowser()
    private var resolving: [NetService] = []

    override init() {
        super.init()
        browser.delegate = self
    }

    func start() {
        agents = []
        browser.searchForServices(ofType: "_printbridge._tcp.", inDomain: "local.")
    }

    func stop() {
        browser.stop()
        resolving.forEach { $0.stop() }
        resolving.removeAll()
    }

    /// NetService'in çözdüğü adreslerden ilk IPv4'ü döndürür.
    private static func ipv4Address(from addresses: [Data]?) -> String? {
        guard let addresses else { return nil }
        for data in addresses {
            let ip: String? = data.withUnsafeBytes { raw in
                guard let base = raw.baseAddress else { return nil }
                let family = base.assumingMemoryBound(to: sockaddr.self).pointee.sa_family
                guard family == sa_family_t(AF_INET) else { return nil }
                var addr = base.assumingMemoryBound(to: sockaddr_in.self).pointee.sin_addr
                var buffer = [CChar](repeating: 0, count: Int(INET_ADDRSTRLEN))
                guard inet_ntop(AF_INET, &addr, &buffer, socklen_t(INET_ADDRSTRLEN)) != nil else {
                    return nil
                }
                return String(cString: buffer)
            }
            if let ip { return ip }
        }
        return nil
    }
}

extension DiscoveryService: NetServiceBrowserDelegate {
    func netServiceBrowser(_ browser: NetServiceBrowser, didFind service: NetService, moreComing: Bool) {
        service.delegate = self
        resolving.append(service)
        service.resolve(withTimeout: 5)
    }

    func netServiceBrowser(_ browser: NetServiceBrowser, didRemove service: NetService, moreComing: Bool) {
        let name = service.name
        DispatchQueue.main.async {
            self.agents.removeAll { $0.name == name }
        }
    }

    func netServiceBrowser(_ browser: NetServiceBrowser, didNotSearch errorDict: [String: NSNumber]) {
        print("mDNS search error: \(errorDict)")
    }
}

extension DiscoveryService: NetServiceDelegate {
    func netServiceDidResolveAddress(_ sender: NetService) {
        let txtData = sender.txtRecordData()
        let dict = txtData.map { NetService.dictionary(fromTXTRecord: $0) } ?? [:]
        let txt = dict.reduce(into: [String: String]()) { result, pair in
            if let value = String(data: pair.value, encoding: .utf8) {
                result[pair.key] = value
            }
        }
        let id = txt["id"] ?? sender.name
        let agent = DiscoveredAgent(
            id: id,
            name: txt["name"] ?? sender.name,
            // .local isimleri bazı ağlarda çözümlenemediği için önce TXT'teki
            // IP'yi, sonra çözümlenen IPv4 adresini kullan.
            hostName: txt["host"] ?? Self.ipv4Address(from: sender.addresses) ?? sender.hostName ?? sender.name,
            port: sender.port,
            txt: txt
        )
        DispatchQueue.main.async {
            if !self.agents.contains(where: { $0.id == agent.id }) {
                self.agents.append(agent)
            }
        }
        resolving.removeAll { $0 === sender }
    }

    func netService(_ sender: NetService, didNotResolve errorDict: [String: NSNumber]) {
        print("resolve error for \(sender.name): \(errorDict)")
        resolving.removeAll { $0 === sender }
    }
}

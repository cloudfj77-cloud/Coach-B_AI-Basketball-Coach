import Foundation
import Security
import SwiftUI

enum Secrets {
    static func read() -> String {
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: "HoopJournal", kSecAttrAccount as String: "api-token",
            kSecReturnData as String: true, kSecMatchLimit as String: kSecMatchLimitOne]
        var result: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
              let data = result as? Data else { return "" }
        return String(data: data, encoding: .utf8) ?? ""
    }
    static func save(_ token: String) throws {
        let query: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: "HoopJournal", kSecAttrAccount as String: "api-token"]
        let update = [kSecValueData as String: Data(token.utf8)]
        let status = SecItemUpdate(query as CFDictionary, update as CFDictionary)
        if status == errSecItemNotFound {
            var entry = query
            entry[kSecValueData as String] = Data(token.utf8)
            entry[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
            guard SecItemAdd(entry as CFDictionary, nil) == errSecSuccess else { throw APIError.message("无法保存访问令牌") }
        } else if status != errSecSuccess { throw APIError.message("无法更新访问令牌") }
    }
}

enum APIError: LocalizedError {
    case message(String)
    var errorDescription: String? { if case .message(let text) = self { return text }; return nil }
}

@MainActor final class Journal: ObservableObject {
    @Published var trainings: [Training] = []
    @Published var error: String?
    @Published var loading = false
    @Published var connected = false
    @Published var server = UserDefaults.standard.string(forKey: "server") ?? ""
    var token = Secrets.read()
    private let encoder = JSONEncoder()
    private let decoder = JSONDecoder()
    private lazy var session: URLSession = {
        let configuration = URLSessionConfiguration.default
        configuration.timeoutIntervalForRequest = 120
        configuration.timeoutIntervalForResource = 3600
        #if DEBUG
        if let host = UserDefaults.standard.string(forKey: "localCertificateHost"),
           let certificate = UserDefaults.standard.data(forKey: "localCertificate") {
            return URLSession(configuration: configuration,
                              delegate: LocalServerTrust(host: host, certificate: certificate), delegateQueue: nil)
        }
        #endif
        return URLSession(configuration: configuration)
    }()
    var configured: Bool { !server.isEmpty && !token.isEmpty }
    var usesMac: Bool {
        guard let host = URL(string: server)?.host else { return false }
        return host == UserDefaults.standard.string(forKey: "localCertificateHost")
    }

    init() {
        #if DEBUG
        if let url = ProcessInfo.processInfo.environment["HOOP_LOCAL_SERVER"],
           let host = URL(string: url)?.host, URL(string: url)?.scheme == "https",
           let key = ProcessInfo.processInfo.environment["HOOP_LOCAL_TOKEN"],
           let encoded = ProcessInfo.processInfo.environment["HOOP_LOCAL_CERT"],
           let certificate = Data(base64Encoded: encoded),
           SecCertificateCreateWithData(nil, certificate as CFData) != nil {
            do {
                try Secrets.save(key)
                UserDefaults.standard.set(url, forKey: "server")
                UserDefaults.standard.set(host, forKey: "localCertificateHost")
                UserDefaults.standard.set(certificate, forKey: "localCertificate")
                server = url; token = key
            } catch { self.error = error.localizedDescription }
        }
        if let url = ProcessInfo.processInfo.environment["HOOP_TEST_SERVER"],
           let key = ProcessInfo.processInfo.environment["HOOP_TEST_TOKEN"] {
            server = url; token = key
        }
        #endif
    }

    func request(_ path: String, method: String = "GET") throws -> URLRequest {
        guard let base = URL(string: server), base.host != nil else { throw APIError.message("请先在设置中填写训练服务地址") }
        var allowed = base.scheme == "https"
        #if DEBUG
        allowed = allowed || (base.scheme == "http" && ["127.0.0.1", "localhost"].contains(base.host!))
        #endif
        guard allowed else { throw APIError.message("云端服务必须使用 HTTPS") }
        guard let url = URL(string: server.trimmingCharacters(in: CharacterSet(charactersIn: "/")) + path) else { throw APIError.message("服务地址无效") }
        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        return request
    }

    private func check(_ data: Data, _ response: URLResponse) throws {
        guard let response = response as? HTTPURLResponse, (200..<300).contains(response.statusCode) else {
            let message = (try? JSONSerialization.jsonObject(with: data) as? [String: String])?["error"]
            throw APIError.message(message ?? "无法连接训练服务，请检查网络与设置")
        }
    }

    func fetch() async {
        guard configured else { return }
        loading = true
        defer { loading = false }
        do {
            var req = try request("/api/sessions")
            req.timeoutInterval = 15
            #if DEBUG
            NSLog("Coach B: fetching training records")
            #endif
            let (data, response) = try await session.data(for: req)
            try check(data, response)
            trainings = try decoder.decode([Training].self, from: data)
            connected = true
            #if DEBUG
            NSLog("Coach B: fetched %d training records", trainings.count)
            #endif
        } catch {
            connected = false
            self.error = usesMac ? "无法连接 Mac。请确认电脑服务已启动、手机和电脑在同一网络，并允许本地网络访问。\n\(error.localizedDescription)" : error.localizedDescription
            #if DEBUG
            NSLog("Coach B: fetch failed (%ld): %@", (error as NSError).code, error.localizedDescription)
            #endif
        }
    }

    func upload(file: URL, title: String, date: Date) async throws -> Training {
        var components = URLComponents()
        let formatter = DateFormatter(); formatter.dateFormat = "yyyy-MM-dd"
        components.queryItems = [URLQueryItem(name: "title", value: title), URLQueryItem(name: "date", value: formatter.string(from: date)), URLQueryItem(name: "player", value: "蓝色 2 号球衣，白色短裤；不要与深色无袖 12 号混淆")]
        var req = try request("/api/upload?" + (components.percentEncodedQuery ?? ""), method: "POST")
        req.setValue("application/octet-stream", forHTTPHeaderField: "Content-Type")
        let (data, response) = try await session.upload(for: req, fromFile: file)
        try check(data, response)
        let training = try decoder.decode(Training.self, from: data)
        await fetch()
        return training
    }

    func action(_ training: Training, _ action: String) async throws {
        var req = try request("/api/sessions/\(training.id)/\(action)", method: "POST")
        req.httpBody = Data("{}".utf8)
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let (data, response) = try await session.data(for: req)
        try check(data, response)
        await fetch()
    }

    func saveShots(_ shots: [Shot], for training: Training) async throws {
        struct Update: Encodable { let revision: Int; let shots: [Shot] }
        var req = try request("/api/sessions/\(training.id)", method: "PUT")
        req.httpBody = try encoder.encode(Update(revision: training.revision, shots: shots))
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let (data, response) = try await session.data(for: req)
        try check(data, response)
        await fetch()
    }

    func download(_ training: Training, kind: String) async throws -> URL {
        let (temp, response) = try await session.download(for: request("/api/sessions/\(training.id)/\(kind)"))
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else { throw APIError.message("视频暂时无法下载，请稍后重试") }
        let file = FileManager.default.temporaryDirectory.appendingPathComponent("\(training.id)-\(kind)-\(training.revision).mp4")
        if FileManager.default.fileExists(atPath: file.path) { try FileManager.default.removeItem(at: file) }
        try FileManager.default.moveItem(at: temp, to: file)
        return file
    }

    func settings(url: String, key: String) throws {
        try Secrets.save(key.trimmingCharacters(in: .whitespacesAndNewlines))
        server = url.trimmingCharacters(in: .whitespacesAndNewlines)
        token = key.trimmingCharacters(in: .whitespacesAndNewlines)
        UserDefaults.standard.set(server, forKey: "server")
        trainings = []
        connected = false
    }
}

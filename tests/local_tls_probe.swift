// Integration probe: run against a local HTTPS server with the supplied DER cert.
// No token is used: HTTP 401 proves TLS succeeded without exposing training data.
import Foundation

@main struct LocalTLSProbe {
    static func main() throws {
        let url = URL(string: CommandLine.arguments[1])!
        let cert = try Data(contentsOf: URL(fileURLWithPath: CommandLine.arguments[2]))
        let cases: [(String, URLSessionDelegate?, Bool)] = [
            ("paired certificate", LocalServerTrust(host: url.host!, certificate: cert), true),
            ("different host", LocalServerTrust(host: "unpaired.invalid", certificate: cert), false),
            ("different certificate", LocalServerTrust(host: url.host!, certificate: Data()), false),
            ("unpaired system trust", nil, false)
        ]
        var failures = 0
        for (name, delegate, expected) in cases {
            let config = URLSessionConfiguration.ephemeral
            config.timeoutIntervalForRequest = 10
            let session = URLSession(configuration: config, delegate: delegate, delegateQueue: nil)
            let done = DispatchSemaphore(value: 0)
            var accepted = false
            session.dataTask(with: url) { _, response, error in
                accepted = error == nil && (response as? HTTPURLResponse)?.statusCode == 401
                done.signal()
            }.resume()
            let finished = done.wait(timeout: .now() + 15) == .success
            let passed = finished && accepted == expected
            print("\(passed ? "PASS" : "FAIL"): \(name)")
            if !passed { failures += 1 }
            session.invalidateAndCancel()
        }
        if failures > 0 { exit(1) }
    }
}

import Foundation
import Security

#if DEBUG
// A personal Mac certificate is provisioned over USB, never downloaded from a server.
// This only trusts that exact certificate, for that exact host; normal TLS policy
// (including hostname and expiration checks) still applies.
final class LocalServerTrust: NSObject, URLSessionDelegate {
    let host: String
    let certificate: Data
    init(host: String, certificate: Data) {
        self.host = host
        self.certificate = certificate
    }

    func urlSession(_ session: URLSession, didReceive challenge: URLAuthenticationChallenge,
                    completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void) {
        guard challenge.protectionSpace.authenticationMethod == NSURLAuthenticationMethodServerTrust,
              challenge.protectionSpace.host.lowercased() == host.lowercased(),
              let trust = challenge.protectionSpace.serverTrust,
              let leaf = SecTrustGetCertificateAtIndex(trust, 0),
              SecCertificateCopyData(leaf) as Data == certificate,
              let anchor = SecCertificateCreateWithData(nil, certificate as CFData) else {
            completionHandler(.performDefaultHandling, nil)
            return
        }
        SecTrustSetAnchorCertificates(trust, [anchor] as CFArray)
        SecTrustSetAnchorCertificatesOnly(trust, true)
        if SecTrustEvaluateWithError(trust, nil) {
            completionHandler(.useCredential, URLCredential(trust: trust))
        } else {
            completionHandler(.cancelAuthenticationChallenge, nil)
        }
    }
}
#endif

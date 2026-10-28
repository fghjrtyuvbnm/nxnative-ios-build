import Foundation

final class FixtureProtocol: URLProtocol {
    static var requests: [URLRequest] = []
    override class func canInit(with request: URLRequest) -> Bool { true }
    override class func canonicalRequest(for request: URLRequest) -> URLRequest { request }
    override func startLoading() {
        Self.requests.append(request)
        let response = HTTPURLResponse(url: request.url!, statusCode: 200, httpVersion: "HTTP/1.1", headerFields: ["Content-Type": "text/x-xml-plist"])!
        client?.urlProtocol(self, didReceive: response, cacheStoragePolicy: .notAllowed)
        client?.urlProtocol(self, didLoad: Data("synthetic-response".utf8))
        client?.urlProtocolDidFinishLoading(self)
    }
    override func stopLoading() {}
}

@main struct GSAContract {
static func main() async throws {
    var original = URLRequest(url: URL(string: "https://gsa.apple.com/grandslam/GsService2")!)
    original.httpMethod = "POST"
    original.httpBody = Data("synthetic-srp-body".utf8)
    // Reproduce the old server-metadata + fixed-agent mismatch without accounts.
    original.setValue("synthetic-Mac-provider-identity", forHTTPHeaderField: "X-MMe-Client-Info")
    original.setValue("SYNTHETIC_OTP", forHTTPHeaderField: "X-Apple-I-MD")
    let prepared = GMRGSAClient.prepare(original)
    guard prepared.value(forHTTPHeaderField: "X-MMe-Client-Info") == GMRGSAClient.clientInfo,
          prepared.value(forHTTPHeaderField: "User-Agent") == GMRGSAClient.userAgent,
          prepared.value(forHTTPHeaderField: "Accept") == "text/x-xml-plist",
          prepared.httpBody == original.httpBody,
          prepared.value(forHTTPHeaderField: "X-Apple-I-MD") == "SYNTHETIC_OTP",
          original.value(forHTTPHeaderField: "X-MMe-Client-Info") == "synthetic-Mac-provider-identity" else {
        fatalError("GSA policy modified provider data or SRP payload")
    }
    let configuration = URLSessionConfiguration.ephemeral
    configuration.protocolClasses = [FixtureProtocol.self]
    for _ in ["init", "complete", "apptokens"] {
        let (data, response) = try await GMRGSAClient.send(original, configuration: configuration)
        guard data == Data("synthetic-response".utf8), (response as? HTTPURLResponse)?.statusCode == 200 else { fatalError("Mock transport failed") }
    }
    guard FixtureProtocol.requests.count == 3 else { fatalError("Unexpected retry or missing GSA phase") }
    for request in FixtureProtocol.requests {
        guard request.value(forHTTPHeaderField: "X-MMe-Client-Info") == GMRGSAClient.clientInfo,
              request.value(forHTTPHeaderField: "Connection") == "close" else { fatalError("Policy not applied at transport") }
    }
    print("GSA/provider identity separation, payload integrity and three-phase mock transport passed")
}}

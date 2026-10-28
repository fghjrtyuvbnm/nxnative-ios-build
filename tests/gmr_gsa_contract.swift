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
    let stock = "<MacBookPro13,2> <macOS;13.1;22C65> <com.apple.AuthKit/1 (com.apple.dt.Xcode/fixture)>"
    original.setValue(stock, forHTTPHeaderField: "X-MMe-Client-Info")
    original.setValue("SYNTHETIC_OTP", forHTTPHeaderField: "X-Apple-I-MD")
    let prepared = GMRGSAClient.prepare(original)
    guard prepared.value(forHTTPHeaderField: "X-MMe-Client-Info") == GMRGSAClient.clientInfo,
          prepared.value(forHTTPHeaderField: "User-Agent") == GMRGSAClient.userAgent,
          prepared.value(forHTTPHeaderField: "Accept") == "text/x-xml-plist",
          prepared.value(forHTTPHeaderField: "X-Xcode-Version") == "14.2 (14C18)",
          prepared.value(forHTTPHeaderField: "X-Apple-App-Info") == "com.apple.gs.xcode.auth",
          prepared.httpBody == original.httpBody,
          prepared.value(forHTTPHeaderField: "X-Apple-I-MD") == "SYNTHETIC_OTP",
          original.value(forHTTPHeaderField: "X-MMe-Client-Info") == stock else {
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
    guard GMRAuthenticationContext.stage("init") == "Apple GSA first init" else { fatalError("Wrong initial stage") }
    await GMRAuthenticationContext.$secondFactorCompleted.withValue(true) {
        guard GMRAuthenticationContext.stage("init") == "Apple GSA post-2FA init" else { fatalError("Post-2FA round lost") }
    }
    guard GMRAuthenticationContext.stage("init") == "Apple GSA first init" else { fatalError("Round state leaked into next login") }
    let isolated = await withTaskGroup(of: Bool.self, returning: Bool.self) { group in
        for state in [true, false, true, false] {
            group.addTask {
                GMRAuthenticationContext.$secondFactorCompleted.withValue(state) {
                    GMRAuthenticationContext.stage("init") == (state ? "Apple GSA post-2FA init" : "Apple GSA first init")
                }
            }
        }
        for await valid in group { if !valid { return false } }
        return true
    }
    guard isolated else { fatalError("Concurrent authentication round state leaked") }
    let oldMac = GMRGSAClient.identity("<Fixture> <macOS;10.12.6;fixture> <com.apple.AuthKit/1 (com.apple.akd/1.0)>", agent: "old-agent")
    guard oldMac.name == "current-mac", oldMac.client == GMRGSAClient.currentMac, oldMac.agent == GMRGSAClient.currentMacAgent else { fatalError("Legacy Mac backend incorrectly treated as Windows") }
    let supplied = GMRGSAClient.identity("<Fixture> <macOS;26.6;fixture>", agent: "provider-agent")
    guard supplied.name == "provider-pair", supplied.agent == "provider-agent" else { fatalError("Provider pair lost") }
    guard GMRGSAClient.identity("<Fixture> <Android;14;fixture>", agent: "android-agent").name == "windows-compatibility" else { fatalError("Android fallback regression") }
    var macRequest = original
    macRequest.setValue("<Fixture> <macOS;10.12.6;fixture>", forHTTPHeaderField: "X-MMe-Client-Info")
    let macPrepared = GMRGSAClient.prepare(macRequest)
    guard macPrepared.value(forHTTPHeaderField: "X-MMe-Client-Info") == GMRGSAClient.currentMac,
          macPrepared.value(forHTTPHeaderField: "User-Agent") == GMRGSAClient.currentMacAgent else { fatalError("Profile not applied at request boundary") }
    macRequest.setValue("application/json", forHTTPHeaderField: "Accept")
    let secondFactor = GMRGSAClient.identityRequest(macRequest)
    guard secondFactor.value(forHTTPHeaderField: "X-MMe-Client-Info") == macPrepared.value(forHTTPHeaderField: "X-MMe-Client-Info"),
          secondFactor.value(forHTTPHeaderField: "User-Agent") == macPrepared.value(forHTTPHeaderField: "User-Agent"),
          secondFactor.value(forHTTPHeaderField: "Accept") == "application/json" else { fatalError("Second-factor identity mismatch or format changed") }
    guard GMRGSAClient.prepare(macPrepared).allHTTPHeaderFields == macPrepared.allHTTPHeaderFields else { fatalError("Identity policy is not idempotent") }
    print("GSA and second-factor base identity parity passed; endpoint formats preserved")
    print("Stock/Android, legacy Mac and provider-pair identity selection fixtures passed")
    print("GSA application headers and isolated first/post-2FA round fixtures passed")
    print("GSA/provider identity separation, payload integrity and three-phase mock transport passed")
}}

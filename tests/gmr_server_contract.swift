import Foundation

func response(_ status: Int, _ mime: String = "application/json") -> HTTPURLResponse {
    HTTPURLResponse(url: URL(string: "https://example.invalid/v3/get_headers")!, statusCode: status, httpVersion: "HTTP/1.1", headerFields: ["Content-Type": mime])!
}
func expectFailure(_ data: String, _ status: Int, _ mime: String, _ expected: String) {
    do {
        _ = try GMRServer.object(Data(data.utf8), response: response(status, mime), stage: "fixture")
        fatalError("Expected response failure")
    } catch {
        let message = error.localizedDescription
        guard message.contains(expected), !message.contains("PRIVATE_MARKER"), !message.contains("3840") else { fatalError("Unsafe or unhelpful diagnostic") }
    }
}

@main struct Contract {
static func main() throws {
    // Original call on the same synthetic HTML response reproduces the report.
    do {
        _ = try JSONSerialization.jsonObject(with: Data("<html>PRIVATE_MARKER</html>".utf8))
        fatalError("Original parser unexpectedly accepted HTML")
    } catch {
        let original = error as NSError
        guard original.domain == NSCocoaErrorDomain && original.code == 3840 else { fatalError("Original failure not reproduced") }
    }
    expectFailure("<html>PRIVATE_MARKER</html>", 200, "text/html", "Expected JSON")
    expectFailure("<html>PRIVATE_MARKER</html>", 403, "text/html", "HTTP 403")
    expectFailure("", 200, "application/json", "Empty response")
    expectFailure("PRIVATE_MARKER", 200, "application/json", "Invalid JSON")
    expectFailure("[]", 200, "application/json", "Expected a JSON object")
    let object = try GMRServer.object(Data("{\"ok\":true}".utf8), response: response(200), stage: "fixture")
    guard object["ok"] as? Bool == true else { fatalError("Valid JSON rejected") }
    let metadata = Data("{\"client_info\":\"synthetic-client\",\"user_agent\":\"synthetic-agent\"}".utf8)
    let pair = try GMRServer.clientInfo(metadata, response: response(200))
    guard pair.0 == "synthetic-client" && pair.1 == "synthetic-agent" else { fatalError("Metadata mismatch") }
    do { _ = try GMRServer.clientInfo(Data("{}".utf8), response: response(200)); fatalError("Missing fields accepted") }
    catch { guard error.localizedDescription.contains("metadata is missing") else { fatalError("Wrong metadata diagnostic") } }
    guard try GMRServer.baseURL(" https://example.invalid/// ").absoluteString == "https://example.invalid" else { fatalError("Normalization failed") }
    for bad in ["http://example.invalid", "https://user:pass@example.invalid", "https://example.invalid?token=PRIVATE_MARKER", "https://example.invalid/v3/get_headers"] {
        do { _ = try GMRServer.baseURL(bad); fatalError("Unsafe base accepted") } catch { }
    }
    let harness = Harness()
    harness.url = URL(string: "https://example.invalid")!
    Keychain.shared.adiPb = "synthetic-state"
    Keychain.shared.identifier = "synthetic-id"
    guard try !harness.configureServer("https://example.invalid/"), Keychain.shared.adiPb != nil, harness.resets == 0 else { fatalError("Same-server state lost") }
    do { _ = try harness.configureServer("invalid"); fatalError("Invalid change accepted") } catch { }
    guard Keychain.shared.adiPb != nil && harness.resets == 0 else { fatalError("Invalid URL mutated state") }
    guard try harness.configureServer("https://other.invalid"), Keychain.shared.adiPb == nil, Keychain.shared.identifier == nil, harness.resets == 1 else { fatalError("Cross-server state retained") }
    guard try !harness.configureServer("https://other.invalid/"), harness.resets == 1 else { fatalError("Repeated reset") }
    print("Original HTML response reproduced NSCocoa 3840; safe response and server lifecycle fixtures passed")
}}

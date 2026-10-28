import Foundation

func http(_ status: Int, _ mime: String = "text/x-xml-plist") -> HTTPURLResponse {
    HTTPURLResponse(url: URL(string: "https://example.invalid/validate?PRIVATE_MARKER")!, statusCode: status, httpVersion: "HTTP/1.1", headerFields: ["Content-Type": mime, "Set-Cookie": "PRIVATE_MARKER"])!
}
func plist(_ value: [String: Any], _ format: PropertyListSerialization.PropertyListFormat = .xml) throws -> Data {
    try PropertyListSerialization.data(fromPropertyList: value, format: format, options: 0)
}
@main struct TwoFactorContract {
static func main() throws {
    let invalid = Data("<html>PRIVATE_MARKER</html>".utf8)
    do { _ = try PropertyListSerialization.propertyList(from: invalid, format: nil); fatalError("Original parse accepted HTML") }
    catch { guard (error as NSError).domain == NSCocoaErrorDomain else { fatalError("Unexpected original parse error") } }
    for (body, status, mime) in [(invalid, 200, "text/html"), (invalid, 403, "text/html"), (Data(), 200, "text/x-xml-plist"), (Data("{\"PRIVATE_MARKER\":true}".utf8), 200, "application/json")] {
        do { _ = try GMRAuthResponse.plist(body, response: http(status, mime), stage: "Apple 2FA validate"); fatalError("Malformed response accepted") }
        catch {
            let message = error.localizedDescription
            guard message.contains("Apple 2FA validate"), message.contains("HTTP \(status)"), !message.contains("PRIVATE_MARKER"), !message.contains("3840") else { fatalError("Unsafe or missing diagnostic") }
        }
    }
    for format in [PropertyListSerialization.PropertyListFormat.xml, .binary] {
        let success = try GMRAuthResponse.plist(plist(["ec": 0], format), response: http(200), stage: "Apple 2FA validate")
        guard try GMRAuthResponse.code(success, stage: "fixture") == 0 else { fatalError("Valid response failed") }
    }
    guard try GMRAuthResponse.code(["ec": "-21669"], stage: "fixture") == -21669 else { fatalError("String error code lost") }
    guard try GMRAuthResponse.code([:], stage: "fixture") == 0 else { fatalError("AltSign empty-dictionary semantics changed") }
    do { _ = try GMRAuthResponse.code(["ec": "invalid"], stage: "fixture"); fatalError("Invalid error code accepted") } catch { }
    var original = URLRequest(url: URL(string: "https://example.invalid/validate")!)
    original.setValue("application/x-buddyml", forHTTPHeaderField: "Accept")
    original.setValue("SYNTHETIC_CODE", forHTTPHeaderField: "security-code")
    let request = GMRAuthResponse.preferPlist(original)
    guard request.value(forHTTPHeaderField: "Accept") == "text/x-xml-plist",
          request.value(forHTTPHeaderField: "security-code") == "SYNTHETIC_CODE" else { fatalError("Request negotiation regression") }
    // Multi-step fixture: validation success does not hide the next failure.
    _ = try GMRAuthResponse.plist(plist(["ec": 0]), response: http(200), stage: "Apple 2FA validate")
    do { _ = try GMRAuthResponse.plist(invalid, response: http(502, "text/html"), stage: "Apple GSA apptokens"); fatalError("Post-verification failure ignored") }
    catch { guard error.localizedDescription.contains("Apple GSA apptokens") else { fatalError("Wrong failure stage") } }
    do { _ = try GMRAuthResponse.localPlist(invalid, stage: "Apple decrypted app token"); fatalError("Invalid decrypted payload accepted") }
    catch { guard !error.localizedDescription.contains("PRIVATE_MARKER") else { fatalError("Decrypted body leaked") } }
    print("Trusted-device plist negotiation, failure stages and post-2FA lifecycle fixtures passed")
}}

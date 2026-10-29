import Foundation

func http(_ status: Int, _ mime: String = "application/json") -> HTTPURLResponse {
    HTTPURLResponse(url: URL(string: "https://example.invalid/PRIVATE_APP_ID")!, statusCode: status, httpVersion: "HTTP/1.1", headerFields: ["Content-Type": mime])!
}
@main struct CapabilityResponseContract {
static func main() throws {
    let error = Data("{\"errors\":[{\"code\":\"FORBIDDEN_ERROR\",\"detail\":\"EXTENDED_VIRTUAL_ADDRESSING PRIVATE_APP_ID PRIVATE_TOKEN\",\"source\":{\"pointer\":\"/data/attributes/PRIVATE_APP_ID\"}}]}".utf8)
    for status in [200, 400, 403, 409] {
        do { _ = try GMRCapabilityResponse.object(error, response: http(status)); fatalError("Structured API error accepted") }
        catch {
            let message = error.localizedDescription
            guard message.contains("HTTP \(status)"), message.contains("FORBIDDEN_ERROR"), message.contains("EXTENDED_VIRTUAL_ADDRESSING"), !message.contains("PRIVATE_APP_ID"), !message.contains("PRIVATE_TOKEN") else { fatalError("Capability error lost or private values exposed") }
        }
    }
    let success = try GMRCapabilityResponse.object(Data("{\"data\":{\"type\":\"bundleIds\"}}".utf8), response: http(200))
    try GMRCapabilityResponse.requireUpdateResource(success)
    let empty = try GMRCapabilityResponse.object(Data(), response: http(204))
    try GMRCapabilityResponse.requireUpdateResource(empty)
    for (data, response) in [(Data(), http(200)), (Data("<html>PRIVATE_TOKEN</html>".utf8), http(503, "text/html"))] {
        do { _ = try GMRCapabilityResponse.object(data, response: response); fatalError("Invalid capability response accepted") }
        catch { guard !error.localizedDescription.contains("PRIVATE_TOKEN") else { fatalError("Response body exposed") } }
    }
    do { try GMRCapabilityResponse.requireUpdateResource([:]); fatalError("Missing update resource accepted") } catch { }
    print("Capability HTTP/JSON errors, 204 handling and private-value omission fixtures passed")
}}

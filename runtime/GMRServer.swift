import Foundation

struct GMRResponseError: LocalizedError {
    let errorDescription: String?
    init(_ message: String) { errorDescription = message }
}

enum GMRServer {
    // Snapshot of SideStore/anisette-servers; availability is not a login guarantee.
    static let presets: [(name: String, address: String)] = [
        ("SideStore (New)", "https://new.ani.sidestore.io"),
        ("jkcoxson (Mac)", "https://mac-ani.jkcoxson.com"),
        ("jkcoxson (Windows ADI)", "https://ani.jkcoxson.com"),
        ("SideStore", "https://ani.sidestore.io")
    ]

    static func baseURL(_ input: String) throws -> URL {
        let trimmed = input.trimmingCharacters(in: .whitespacesAndNewlines)
        guard var parts = URLComponents(string: trimmed), parts.scheme == "https",
              let host = parts.host, !host.isEmpty, parts.user == nil, parts.password == nil,
              parts.query == nil, parts.fragment == nil else {
            throw GMRResponseError("Use an HTTPS server base URL without credentials, query or fragment.")
        }
        while parts.path.hasSuffix("/") { parts.path.removeLast() }
        guard !parts.path.contains("/v3/"), let url = parts.url else {
            throw GMRResponseError("Enter the server base URL, not a /v3 endpoint.")
        }
        return url
    }

    static func object(_ data: Data, response: HTTPURLResponse?, stage: String) throws -> [String: Any] {
        let code = response?.statusCode ?? 0
        let mime = response?.mimeType ?? "unknown"
        // Only fixed stage labels and response metadata are exposed. No bodies,
        // URL paths/queries, cookies, authentication headers or identifiers.
        let context = "\(stage): HTTP \(code), MIME \(mime), bytes \(data.count)"
        guard let response, (200..<300).contains(response.statusCode) else {
            throw GMRResponseError(context + ". Server request failed; check the selected server/network.")
        }
        guard !data.isEmpty else { throw GMRResponseError(context + ". Empty response.") }
        guard mime == "application/json" || mime.hasSuffix("+json") || mime == "text/plain" || mime == "application/octet-stream" else {
            throw GMRResponseError(context + ". Expected JSON; the server returned another format.")
        }
        do {
            guard let object = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                throw GMRResponseError(context + ". Expected a JSON object.")
            }
            return object
        } catch let error as GMRResponseError { throw error }
        catch { throw GMRResponseError(context + ". Invalid JSON; no response body was logged.") }
    }

    static func clientInfo(_ data: Data, response: HTTPURLResponse?) throws -> (String, String) {
        let value = try object(data, response: response, stage: "Anisette v3 client_info")
        guard let client = value["client_info"] as? String, !client.isEmpty,
              let agent = value["user_agent"] as? String, !agent.isEmpty else {
            throw GMRResponseError("Anisette v3 client_info: required metadata is missing. Select a compatible v3 server.")
        }
        return (client, agent)
    }
}

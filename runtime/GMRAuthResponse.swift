import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

public struct GMRAuthResponseError: LocalizedError {
    public let errorDescription: String?
    public init(_ message: String) { errorDescription = message }
}

public enum GMRAuthResponse {
    static func shape(_ data: Data) -> String {
        if data.isEmpty { return "empty" }
        if data.starts(with: Data("bplist".utf8)) { return "binary-plist" }
        let prefix = String(decoding: data.prefix(256), as: UTF8.self).trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        if prefix.hasPrefix("<!doctype html") || prefix.hasPrefix("<html") { return "html" }
        if prefix.contains("<plist") || prefix.hasPrefix("<?xml") { return "xml" }
        if prefix.hasPrefix("{") || prefix.hasPrefix("[") { return "json" }
        return "other"
    }

    public static func context(_ data: Data, response: URLResponse?, stage: String) -> String {
        let http = response as? HTTPURLResponse
        return "\(stage): HTTP \(http?.statusCode ?? 0), MIME \(http?.mimeType ?? "unknown"), bytes \(data.count), format \(shape(data))"
    }

    public static func requireHTTP(_ data: Data, response: URLResponse?, stage: String) throws {
        guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
            throw GMRAuthResponseError(context(data, response: response, stage: stage) + ". Request rejected; no response body was logged.")
        }
    }

    public static func localPlist(_ data: Data, stage: String) throws -> [String: Any] {
        do {
            guard let value = try PropertyListSerialization.propertyList(from: data, format: nil) as? [String: Any] else {
                throw GMRAuthResponseError("\(stage): expected a plist dictionary.")
            }
            return value
        } catch let error as GMRAuthResponseError { throw error }
        catch { throw GMRAuthResponseError("\(stage): invalid plist, bytes \(data.count), format \(shape(data)). No decrypted content was logged.") }
    }

    public static func plist(_ data: Data, response: URLResponse?, stage: String) throws -> [String: Any] {
        try requireHTTP(data, response: response, stage: stage)
        do { return try localPlist(data, stage: stage) }
        catch { throw GMRAuthResponseError(context(data, response: response, stage: stage) + ". Expected a plist dictionary; no response body was logged.") }
    }

    public static func code(_ value: [String: Any], stage: String) throws -> Int {
        // AltSign permits an omitted ec in a successfully decoded dictionary.
        guard let raw = value["ec"] else { return 0 }
        if let code = raw as? Int { return code }
        if let text = raw as? String, let code = Int(text) { return code }
        throw GMRAuthResponseError("\(stage): invalid error-code field.")
    }

    public static func preferPlist(_ input: URLRequest) -> URLRequest {
        var request = input
        request.setValue("text/x-xml-plist", forHTTPHeaderField: "Accept")
        request.setValue("text/x-xml-plist", forHTTPHeaderField: "Content-Type")
        return request
    }
}

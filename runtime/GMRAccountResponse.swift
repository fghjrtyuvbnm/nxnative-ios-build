import Foundation
import CoreFoundation

public enum GMRAccountResponse {
    static let fields = ["email", "personId", "dsFirstName", "dsLastName", "firstName", "lastName"]

    static func resultCode(_ value: Any?) -> Int? {
        if let number = value as? NSNumber, CFGetTypeID(number) != CFBooleanGetTypeID() { return Int(number.stringValue) }
        if let text = value as? String { return Int(text) }
        return nil
    }

    public static func requireSuccess(_ response: [String: Any], stage: String) throws {
        guard let raw = response["resultCode"] else { return }
        guard let code = resultCode(raw) else {
            throw GMRAuthResponseError(stage + ": invalid resultCode type=" + kind(raw) + ". No response values logged.")
        }
        if code != 0 {
            throw GMRAuthResponseError(stage + ": Apple developer service returned resultCode=" + String(code) + ". No account or token values logged.")
        }
    }

    static func kind(_ value: Any?) -> String {
        guard let value else { return "missing" }
        if value is NSNull { return "null" }
        if value is String { return "string" }
        if let value = value as? NSNumber { return CFGetTypeID(value) == CFBooleanGetTypeID() ? "boolean" : "number" }
        if value is [String: Any] { return "object" }
        if value is [Any] { return "array" }
        return "other"
    }

    public static func schema(_ response: [String: Any], section: String) -> String {
        // Only allowlisted field names and type labels. No values, keys from
        // arbitrary dictionaries, account identifiers or response bodies.
        let selected = section == "teams" ? "teams" : "developer"
        let code = resultCode(response["resultCode"]).map(String.init) ?? kind(response["resultCode"])
        return "section=" + selected + ":" + kind(response[selected]) + ", resultCode=" + code
    }

    public static func decodeAccount(_ response: [String: Any]) throws -> Account {
        try requireSuccess(response, stage: "Apple account lookup")
        guard let developer = response["developer"] as? [String: Any] else {
            throw GMRAuthResponseError("Apple account lookup schema: " + schema(response, section: "developer") + ". No response values logged.")
        }
        // Decodable ignores unknown keys. Selecting its fields also prevents
        // unrelated plist-only values from breaking a JSON representation.
        let selected = developer.filter { fields.contains($0.key) }
        do {
            let data = try JSONSerialization.data(withJSONObject: selected)
            return try JSONDecoder().decode(Account.self, from: data)
        } catch {
            var field = "account", reason = "serialization"
            switch error {
            case DecodingError.keyNotFound(let key, _): field = key.stringValue; reason = "missing-field"
            case DecodingError.typeMismatch(_, let context): field = context.codingPath.last?.stringValue ?? "account"; reason = "type-mismatch"
            case DecodingError.valueNotFound(_, let context): field = context.codingPath.last?.stringValue ?? "account"; reason = "null-field"
            case DecodingError.dataCorrupted(let context): field = context.codingPath.last?.stringValue ?? "account"; reason = "invalid-field"
            default: break
            }
            if !fields.contains(field) { field = "account" }
            let shape = fields.map { $0 + ":" + kind(developer[$0]) }.joined(separator: ", ")
            throw GMRAuthResponseError("Apple account decode: " + reason + ", field=" + field + "; " + shape + ". No account values logged.")
        }
    }
}

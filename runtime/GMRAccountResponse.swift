import Foundation
import CoreFoundation

public enum GMRAccountResponse {
    static let fields = ["email", "personId", "dsFirstName", "dsLastName", "firstName", "lastName"]

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
        return "section=" + selected + ":" + kind(response[selected]) + ", resultCode=" + kind(response["resultCode"])
    }

    public static func decodeAccount(_ response: [String: Any]) throws -> Account {
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

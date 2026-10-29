import Foundation
import CoreFoundation

public enum GMRCapabilityResponse {
    static let emptyMarker = "_gmrEmptyUpdateResponse"
    static let memoryNames = ["INCREASED_MEMORY_LIMIT", "EXTENDED_VIRTUAL_ADDRESSING"]

    static func safeCode(_ value: Any?) -> String {
        guard let text = value as? String, !text.isEmpty, text.utf8.count <= 100,
              text.utf8.allSatisfy({ (48...57).contains($0) || (65...90).contains($0) || $0 == 95 || $0 == 46 || $0 == 45 }) else { return "unavailable" }
        return text
    }

    // Recognize fixed phrases only. These are classifications of server wording,
    // not proof of an account restriction or a reason to change membership.
    static func reason(_ error: [String: Any]) -> String {
        let text = ((error["title"] as? String ?? "") + " " + (error["detail"] as? String ?? "")).lowercased()
        var labels: [String] = []
        for (phrase, label) in [
            ("forbidden for security reasons", "generic_security_rejection"),
            ("api key in use does not allow", "credential_not_allowed"),
            ("not authorized", "not_authorized"),
            ("not permitted", "not_permitted"),
            ("do not have permission", "permission_not_granted"),
            ("does not have permission", "permission_not_granted"),
            ("required agreement", "agreement_required"),
            ("must be enrolled", "enrollment_required"),
            ("not available for your team", "unavailable_for_team"),
            ("insufficient privileges", "insufficient_privileges"),
            ("session has expired", "session_expired")
        ] where text.contains(phrase) {
            if !labels.contains(label) { labels.append(label) }
        }
        return labels.isEmpty ? "unclassified" : labels.joined(separator: ",")
    }

    public static func object(_ data: Data, response: URLResponse?) throws -> [String: Any] {
        let stage = "Apple capability update"
        let http = response as? HTTPURLResponse
        if http?.statusCode == 204 && data.isEmpty { return [emptyMarker: true, "_gmrHTTPStatus": 204] }
        let context = GMRAuthResponse.context(data, response: response, stage: stage)
        let parsed = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
        if let errors = parsed?["errors"] as? [[String: Any]], !errors.isEmpty {
            let codes = errors.prefix(4).map { error -> String in
                var label = "code=" + safeCode(error["code"]) + ", server_reason=" + reason(error)
                if let source = error["source"] as? [String: Any], let pointer = source["pointer"] as? String {
                    let allowed = Set(["data", "attributes", "relationships", "bundleIdCapabilities", "capability", "enabled", "settings", "teamId", "seedId", "bundleType", "identifier", "name", "hasExclusiveManagedCapabilities", "type", "id"])
                    label += ", source=/" + pointer.split(separator: "/").prefix(12).map { allowed.contains(String($0)) ? String($0) : "field" }.joined(separator: "/")
                }
                // Report only the two public capability names, never arbitrary
                // server detail/title/source strings or resource identifiers.
                let detail = error["detail"] as? String ?? ""
                for name in memoryNames where detail.contains(name) { label += ", capability=" + name }
                return label
            }.joined(separator: "; ")
            throw GMRAuthResponseError(context + "; " + codes + ". No server detail or identifiers logged.")
        }
        try GMRAuthResponse.requireHTTP(data, response: response, stage: stage)
        guard var parsed else {
            throw GMRAuthResponseError(context + ". Expected a JSON object; no response body logged.")
        }
        try GMRAccountResponse.requireSuccess(parsed, stage: stage)
        parsed["_gmrHTTPStatus"] = http?.statusCode ?? 0
        return parsed
    }

    public static func receipt(_ value: [String: Any]) -> String {
        let status = value["_gmrHTTPStatus"] as? Int ?? 0
        let prefix = "Update response: HTTP " + String(status) + ". "
        guard let resource = value["data"] as? [String: Any] else {
            return prefix + "No resource details returned. This response does not verify installed permissions."
        }
        let relationships = resource["relationships"] as? [String: Any]
        let relationship = relationships?["bundleIdCapabilities"] as? [String: Any]
        guard let entries = relationship?["data"] as? [[String: Any]] else {
            return prefix + "No inline capability details returned. This response does not verify installed permissions."
        }
        // Only accept explicit inline state and the two public capability names.
        // Link-only IDs, unknown resources, settings and arbitrary text are omitted.
        var details: [String] = []
        for entry in entries {
            guard entry["type"] as? String == "bundleIdCapabilities",
                  let attrs = entry["attributes"] as? [String: Any],
                  let raw = attrs["enabled"] as? NSNumber,
                  CFGetTypeID(raw) == CFBooleanGetTypeID(),
                  let rels = entry["relationships"] as? [String: Any],
                  let cap = rels["capability"] as? [String: Any],
                  let capData = cap["data"] as? [String: Any],
                  capData["type"] as? String == "capabilities",
                  let name = capData["id"] as? String, memoryNames.contains(name) else { continue }
            details.append(name + "=" + (raw.boolValue ? "enabled" : "disabled"))
        }
        return prefix + (details.isEmpty ? "No explicit inline memory state returned. " : "Inline response state: " + details.prefix(4).joined(separator: "; ") + ". ") + "This response does not verify installed permissions."
    }

    public static func requireUpdateResource(_ value: [String: Any]) throws {
        if value[emptyMarker] as? Bool == true { return }
        guard value["data"] is [String: Any] else {
            throw GMRAuthResponseError("Apple capability update schema: resource data missing. State must be checked by readback.")
        }
    }
}

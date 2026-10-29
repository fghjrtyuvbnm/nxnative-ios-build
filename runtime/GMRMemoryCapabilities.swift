import Foundation
import CoreFoundation

public enum GMRMemoryCapabilities {
    public enum Selection: Equatable {
        case both, increased, extended

        public var identifiers: [String] {
            switch self {
            case .both: return ["INCREASED_MEMORY_LIMIT", "EXTENDED_VIRTUAL_ADDRESSING"]
            case .increased: return ["INCREASED_MEMORY_LIMIT"]
            case .extended: return ["EXTENDED_VIRTUAL_ADDRESSING"]
            }
        }

        var aliases: [String] {
            switch self {
            case .both: return GMRMemoryCapabilities.increased + GMRMemoryCapabilities.extended
            case .increased: return GMRMemoryCapabilities.increased
            case .extended: return GMRMemoryCapabilities.extended
            }
        }

        func confirmed(_ app: AppID) -> Bool {
            switch self {
            case .both: return GMRMemoryCapabilities.bothConfirmed(app)
            case .increased: return GMRMemoryCapabilities.enabled(GMRMemoryCapabilities.increased, app)
            case .extended: return GMRMemoryCapabilities.enabled(GMRMemoryCapabilities.extended, app)
            }
        }
    }
    static let increased = ["increasedMemoryLimit", "INCREASED_MEMORY_LIMIT"]
    static let extended = ["extendedVirtualAddressing", "EXTENDED_VIRTUAL_ADDRESSING"]

    static func enabled(_ aliases: [String], _ app: AppID) -> Bool {
        if aliases.contains(where: { app.enabledFeatureIdentifiers.contains($0) }) { return true }
        return aliases.contains { key in
            if let value = app.features[key] as? NSNumber { return value.stringValue == "1" }
            if let value = app.features[key] as? String { return ["true", "yes", "1"].contains(value.lowercased()) }
            return false
        }
    }

    public static func bothConfirmed(_ app: AppID) -> Bool { enabled(increased, app) && enabled(extended, app) }

    public static func summary(_ app: AppID) -> String {
        "Increased Memory Limit=" + (enabled(increased, app) ? "confirmed" : "not confirmed") + "; Extended Virtual Addressing=" + (enabled(extended, app) ? "confirmed" : "not confirmed")
    }

    static func safeError(_ error: Error) -> String {
        if let safe = error as? GMRAuthResponseError { return safe.localizedDescription }
        return "System error code=" + String((error as NSError).code)
    }

    public static func apply(_ selection: Selection = .increased, read: () async throws -> AppID, update: (AppID) async throws -> Void) async throws -> (AppID, String) {
        let requested = "Requested: " + selection.identifiers.joined(separator: ", ") + ". "
        let before = try await read()
        if selection.confirmed(before) { return (before, requested + "Selected capabilities were already confirmed on the App ID. " + summary(before) + ". Re-sign the target IPA to update its profile.") }
        var updateError: Error?
        do { try await update(before) } catch { updateError = error }
        let after: AppID
        do { after = try await read() }
        catch {
            let updateStatus = updateError.map(safeError) ?? "Update request completed"
            throw GMRAuthResponseError(requested + updateStatus + ". App ID readback failed: " + safeError(error) + ". Capability state is not confirmed.")
        }
        let memoryAliases = Set(selection.aliases)
        let unrelatedBefore = Set(before.enabledFeatureIdentifiers).subtracting(memoryAliases)
        let unrelatedAfter = Set(after.enabledFeatureIdentifiers).subtracting(memoryAliases)
        guard unrelatedBefore.isSubset(of: unrelatedAfter) else {
            throw GMRAuthResponseError(requested + "Apple capability readback: other previously enabled features are no longer listed. Do not re-sign until the App ID is reviewed.")
        }
        guard selection.confirmed(after) else {
            throw GMRAuthResponseError(requested + (updateError.map(safeError) ?? "Apple capability update returned") + ". Readback: " + summary(after))
        }
        var message = requested + (selection == .both ? "Both memory capabilities confirmed on the App ID by readback. " : "Selected memory capability confirmed on the App ID by readback. ") + summary(after) + ". Re-sign the target IPA, then verify its installed profile and signature."
        if let updateError { message += " Update transport also reported: " + safeError(updateError) }
        return (after, message)
    }
}

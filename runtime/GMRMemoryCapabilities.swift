import Foundation
import CoreFoundation

public enum GMRMemoryCapabilities {
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

    public static func apply(read: () async throws -> AppID, update: (AppID) async throws -> Void) async throws -> (AppID, String) {
        let before = try await read()
        if bothConfirmed(before) { return (before, "Both memory capabilities were already confirmed on the App ID. Re-sign the target IPA to update its profile.") }
        var updateError: Error?
        do { try await update(before) } catch { updateError = error }
        let after: AppID
        do { after = try await read() }
        catch {
            let updateStatus = updateError.map(safeError) ?? "Update request completed"
            throw GMRAuthResponseError(updateStatus + ". App ID readback failed: " + safeError(error) + ". Capability state is not confirmed.")
        }
        let memoryAliases = Set(increased + extended)
        let unrelatedBefore = Set(before.enabledFeatureIdentifiers).subtracting(memoryAliases)
        let unrelatedAfter = Set(after.enabledFeatureIdentifiers).subtracting(memoryAliases)
        guard unrelatedBefore.isSubset(of: unrelatedAfter) else {
            throw GMRAuthResponseError("Apple capability readback: other previously enabled features are no longer listed. Do not re-sign until the App ID is reviewed.")
        }
        guard bothConfirmed(after) else {
            throw GMRAuthResponseError((updateError.map(safeError) ?? "Apple capability update returned") + ". Readback: " + summary(after))
        }
        var message = "Both memory capabilities confirmed on the App ID by readback. Re-sign the target IPA, then verify its installed profile and signature."
        if let updateError { message += " Update transport also reported: " + safeError(updateError) }
        return (after, message)
    }
}

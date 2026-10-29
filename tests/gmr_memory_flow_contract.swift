import Foundation

func app(_ flags: [String]) -> AppID {
    var result = AppID(name: "Synthetic", identifier: "FIXTURE_ID", bundleIdentifier: "invalid.fixture", expirationDate: nil, features: [:])
    result.enabledFeatureIdentifiers = flags
    return result
}
let both = ["increasedMemoryLimit", "extendedVirtualAddressing"]

@main struct MemoryFlowContract {
static func main() async throws {
    let parsed = AppID(responseDictionary: ["name": "Synthetic", "appIdId": "FIXTURE_ID", "identifier": "invalid.fixture", "features": [:], "enabledFeatures": both])!
    guard GMRMemoryCapabilities.bothConfirmed(parsed) else { fatalError("Enabled feature IDs were lost by the model") }
    var state = app(["EXISTING_FEATURE"]), reads = 0, updates = 0
    let (_, result) = try await GMRMemoryCapabilities.apply(.both, read: { reads += 1; return state }, update: { _ in updates += 1; state = app(["EXISTING_FEATURE"] + both) })
    guard reads == 2 && updates == 1 && result.contains("confirmed") else { fatalError("Update/readback lifecycle failed") }
    updates = 0
    _ = try await GMRMemoryCapabilities.apply(.both, read: { state }, update: { _ in updates += 1 })
    guard updates == 0 else { fatalError("Already-enabled App ID was mutated") }
    state = app([])
    let (_, partial) = try await GMRMemoryCapabilities.apply(.both, read: { state }, update: { _ in state = app(["increasedMemoryLimit"]) })
    guard partial.contains("Warning:"), partial.contains("Extended Virtual Addressing=not confirmed"), !partial.contains("Both memory capabilities confirmed") else { fatalError("Partial capability state misrepresented") }
    state = app([])
    do {
        _ = try await GMRMemoryCapabilities.apply(.both, read: { state }, update: { _ in throw GMRAuthResponseError("Apple capability update: HTTP 403 code=FORBIDDEN_ERROR") })
        fatalError("Denied update reported success")
    } catch { guard error.localizedDescription.contains("FORBIDDEN_ERROR") && error.localizedDescription.contains("Readback:") else { fatalError("Server error or readback state lost") } }
    state = app([])
    let (_, recovered) = try await GMRMemoryCapabilities.apply(.both, read: { state }, update: { _ in state = app(both); throw GMRAuthResponseError("HTTP response lost after commit") })
    guard recovered.contains("also reported") else { fatalError("Transport failure was silently hidden after confirmed readback") }
    state = app(["EXISTING_FEATURE"])
    do {
        _ = try await GMRMemoryCapabilities.apply(.both, read: { state }, update: { _ in state = app(both) })
        fatalError("Loss of unrelated enabled features was ignored")
    } catch { guard error.localizedDescription.contains("other previously enabled") else { fatalError("Unrelated feature loss not identified") } }
    state = app([]); reads = 0
    let (_, unreadable) = try await GMRMemoryCapabilities.apply(.both, read: {
        reads += 1
        if reads > 1 { throw NSError(domain: "fixture", code: -1, userInfo: [NSLocalizedDescriptionKey: "PRIVATE_TOKEN"]) }
        return state
    }, update: { _ in state = app(both) })
    guard unreadable.contains("Warning:"), unreadable.contains("not confirmed"), !unreadable.contains("PRIVATE_TOKEN") else { fatalError("Readback failure diagnostics unsafe") }
    print("Memory update/precheck/readback, partial denial, transport ambiguity and unrelated-feature preservation fixtures passed")
}}

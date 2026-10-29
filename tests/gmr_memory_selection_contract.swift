import Foundation

func fixture(_ flags: [String]) -> AppID {
    var value = AppID(name: "Fixture", identifier: "FIXTURE_ID", bundleIdentifier: "invalid.fixture", expirationDate: nil, features: [:])
    value.enabledFeatureIdentifiers = flags
    return value
}

@main struct MemorySelectionContract {
static func main() async throws {
    var state = fixture([]), updates = 0
    do {
        #if BASELINE
        _ = try await GMRMemoryCapabilities.apply(read: { state }, update: { _ in updates += 1; state = fixture(["increasedMemoryLimit"]) })
        #else
        let (_, message) = try await GMRMemoryCapabilities.apply(read: { state }, update: { _ in updates += 1; state = fixture(["increasedMemoryLimit"]) })
        guard message.contains("Selected memory capability confirmed"), message.contains("Extended Virtual Addressing=not confirmed") else { fatalError("Single-item success misrepresented other permission") }
        #endif
    } catch {
        #if BASELINE
        guard updates == 1 && error.localizedDescription.contains("Extended Virtual Addressing=not confirmed") else { fatalError("Unexpected baseline failure") }
        print("1.0.8 policy RED: isolated Increased Memory success rejected because the other capability is absent")
        exit(42)
        #else
        throw error
        #endif
    }
    #if BASELINE
    fatalError("Expected baseline behavioral failure was not reproduced")
    #else
    guard GMRMemoryCapabilities.Selection.increased.identifiers == ["INCREASED_MEMORY_LIMIT"], GMRMemoryCapabilities.Selection.extended.identifiers == ["EXTENDED_VIRTUAL_ADDRESSING"] else { fatalError("Single action requested multiple permissions") }
    _ = try await GMRMemoryCapabilities.apply(.increased, read: { state }, update: { _ in updates += 1 })
    guard updates == 1 else { fatalError("Already-confirmed selected permission updated again") }
    let (_, second) = try await GMRMemoryCapabilities.apply(.extended, read: { state }, update: { _ in state = fixture(["increasedMemoryLimit", "extendedVirtualAddressing"]) })
    guard second.contains("Increased Memory Limit=confirmed"), second.contains("Extended Virtual Addressing=confirmed") else { fatalError("Sequential permission enablement failed") }
    state = fixture(["increasedMemoryLimit"])
    do {
        _ = try await GMRMemoryCapabilities.apply(.extended, read: { state }, update: { _ in state = fixture(["extendedVirtualAddressing"]) })
        fatalError("Previously confirmed other memory permission was lost")
    } catch { guard error.localizedDescription.contains("previously enabled features") else { fatalError("Other memory permission loss unrecognized") } }
    state = fixture([])
    do {
        _ = try await GMRMemoryCapabilities.apply(.extended, read: { state }, update: { _ in throw GMRAuthResponseError("HTTP 403 code=FORBIDDEN_ERROR") })
        fatalError("403 treated as successful permission update")
    } catch { guard error.localizedDescription.contains("Requested: EXTENDED_VIRTUAL_ADDRESSING"), error.localizedDescription.contains("HTTP 403") else { fatalError("Selected permission or denial missing") } }
    print("Single-capability selection, skip, sequential readback and other-memory preservation GREEN")
    #endif
}}

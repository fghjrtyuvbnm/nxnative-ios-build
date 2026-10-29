import Foundation

func unknownApp() -> AppID {
    AppID(name: "Fixture", identifier: "FIXTURE_ID", bundleIdentifier: "invalid.fixture", expirationDate: nil, features: [:])
}

@main struct MemoryUncertaintyContract {
static func main() async throws {
    var reads = 0, writes = 0
    do {
        let (_, message) = try await GMRMemoryCapabilities.apply(read: { reads += 1; return unknownApp() }, update: { _ in writes += 1 })
        guard reads == 2, writes == 1, message.contains("Update request accepted"), message.contains("Warning:"), message.contains("not confirmed"), !message.contains("confirmed on the App ID") else { fatalError("Acknowledgement confused with permission confirmation") }
    } catch {
        #if BASELINE_UNCERTAINTY
        guard writes == 1, error.localizedDescription.contains("Apple capability update returned"), error.localizedDescription.contains("not confirmed") else { fatalError("Unexpected baseline failure") }
        print("1.0.9 uncertainty RED: accepted update with inconclusive listing was incorrectly thrown as failure")
        exit(42)
        #else
        throw error
        #endif
    }
    #if BASELINE_UNCERTAINTY
    fatalError("Baseline uncertainty failure was not reproduced")
    #else
    reads = 0
    let (_, unavailable) = try await GMRMemoryCapabilities.apply(read: {
        reads += 1
        if reads > 1 { throw NSError(domain: "fixture", code: -1, userInfo: [NSLocalizedDescriptionKey: "PRIVATE_TOKEN"]) }
        return unknownApp()
    }, update: { _ in writes += 1 })
    guard unavailable.contains("Warning:"), unavailable.contains("unavailable"), !unavailable.contains("PRIVATE_TOKEN") else { fatalError("Unreadable listing is not represented safely as inconclusive") }
    do {
        _ = try await GMRMemoryCapabilities.apply(read: { unknownApp() }, update: { _ in throw GMRAuthResponseError("HTTP 403 code=FORBIDDEN_ERROR") })
        fatalError("Actual server rejection downgraded to accepted warning")
    } catch { guard error.localizedDescription.contains("HTTP 403") else { fatalError("Actual rejection lost") } }
    print("Accepted/unconfirmed and unavailable listing warnings GREEN; server rejection remains an error")
    #endif
}}

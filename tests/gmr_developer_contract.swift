import Foundation

func fixture(_ nonce: String, device: String = "SYNTHETIC_DEVICE") -> AnisetteData {
    AnisetteData(machineID: "SYNTHETIC_MACHINE", oneTimePassword: nonce, localUserID: "SYNTHETIC_LOCAL", routingInfo: 0, deviceUniqueIdentifier: device, deviceSerialNumber: "0", deviceDescription: "<Fixture> <macOS;26.6;fixture>", date: Date(), locale: Locale(identifier: "en_US"), timeZone: TimeZone(secondsFromGMT: 0)!)
}
enum FixtureError: Error { case refreshFailed }

@main struct DeveloperContract {
static func main() async throws {
    let base = AppleAPISession(dsid: "SYNTHETIC_DSID", authToken: "SYNTHETIC_TOKEN", anisetteData: fixture("consumed-token-nonce"))
    base.providerUserAgent = "provider-agent"
    var calls = 0
    base.anisetteDataRefreshHandler = { calls += 1; return fixture("fresh-\(calls)") }
    let accountRequest = try await base.requestContext()
    let teamRequest = try await base.requestContext()
    guard calls == 2,
          accountRequest.anisetteData.oneTimePassword == "fresh-1",
          teamRequest.anisetteData.oneTimePassword == "fresh-2",
          base.anisetteData.oneTimePassword == "consumed-token-nonce",
          accountRequest.dsid == base.dsid, teamRequest.authToken == base.authToken,
          teamRequest.authTokens == base.authTokens else { fatalError("Developer request freshness or token integrity failed") }
    var request = URLRequest(url: URL(string: "https://example.invalid/developer")!)
    request.setValue(teamRequest.anisetteData.deviceDescription, forHTTPHeaderField: "X-MMe-Client-Info")
    let prepared = GMRGSAClient.identityRequest(request, providerAgent: teamRequest.providerUserAgent)
    guard prepared.value(forHTTPHeaderField: "User-Agent") == "provider-agent" else { fatalError("Provider pair was lost after login task ended") }
    base.anisetteDataRefreshHandler = { throw FixtureError.refreshFailed }
    do { _ = try await base.requestContext(); fatalError("Refresh failure fell back to consumed nonce") }
    catch FixtureError.refreshFailed { }
    base.anisetteDataRefreshHandler = { fixture("fresh-other", device: "OTHER_SYNTHETIC_DEVICE") }
    do { _ = try await base.requestContext(); fatalError("Provisioning identity change accepted") }
    catch { guard !error.localizedDescription.contains("SYNTHETIC_DEVICE") else { fatalError("Provisioning identifier leaked") } }
    let legacy = AppleAPISession(dsid: "SYNTHETIC", authToken: "SYNTHETIC", anisetteData: fixture("legacy"))
    guard try await legacy.requestContext().anisetteData.oneTimePassword == "legacy" else { fatalError("Existing initializer compatibility changed") }
    print("Developer per-request freshness, unchanged base session, provider pair and failure propagation fixtures passed")
}}

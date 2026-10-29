import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

public struct GMRGSAIdentity: Sendable {
    public let name: String
    public let client: String
    public let agent: String
}

public enum GMRGSAClient {
    // SideInstaller client_info_to_use policy: stock/Android -> Windows;
    // macOS before 10.13 -> current Mac; otherwise retain the provider's pair.
    // Only public client metadata changes; machine identifiers and OTPs do not.
    public static let clientInfo = "<PC> <Windows;6.2(0,0);9200> <com.apple.AuthKit/1 (com.apple.iTunes/12.12.4.1)>"
    public static let userAgent = "akd/1.0 CFNetwork/808.1.4"
    public static let currentMac = "<MacBookPro18,3> <macOS;26.6;25F84> <com.apple.AuthKit/1 (com.apple.akd/1.0)>"
    public static let currentMacAgent = "AuthKit/1 (Macintosh; OS X 26.6) (com.apple.akd/1.0)"
    @TaskLocal public static var providerUserAgent: String? = nil

    public static func identity(_ client: String?, agent: String?) -> GMRGSAIdentity {
        let value = (client ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        if value == currentMac { return GMRGSAIdentity(name: "current-mac", client: currentMac, agent: currentMacAgent) }
        if value == clientInfo { return GMRGSAIdentity(name: "windows-compatibility", client: clientInfo, agent: userAgent) }
        let stock = ["<MacBookPro13,2> <macOS;13.1;22C65>", "<MacBookPro15,1> <Mac OS X;10.15.2;19C57>"]
        if value.isEmpty || stock.contains(where: { value.hasPrefix($0) }) || value.contains("<Android;") {
            return GMRGSAIdentity(name: "windows-compatibility", client: clientInfo, agent: userAgent)
        }
        let expression = try! NSRegularExpression(pattern: "<(?:macOS|Mac OS X);(\\d+)(?:\\.(\\d+))?")
        let ns = value as NSString
        if let match = expression.firstMatch(in: value, range: NSRange(location: 0, length: ns.length)),
           let major = Int(ns.substring(with: match.range(at: 1))) {
            let minor = match.range(at: 2).location == NSNotFound ? 0 : Int(ns.substring(with: match.range(at: 2))) ?? 0
            if major < 10 || (major == 10 && minor < 13) {
                return GMRGSAIdentity(name: "current-mac", client: currentMac, agent: currentMacAgent)
            }
        }
        let selectedAgent = (agent ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        return GMRGSAIdentity(name: "provider-pair", client: value, agent: selectedAgent.isEmpty ? userAgent : selectedAgent)
    }

    public static func identityRequest(_ input: URLRequest, providerAgent: String? = nil) -> URLRequest {
        var request = input
        let selected = identity(input.value(forHTTPHeaderField: "X-MMe-Client-Info"), agent: providerAgent ?? providerUserAgent)
        request.setValue(selected.client, forHTTPHeaderField: "X-MMe-Client-Info")
        request.setValue(selected.agent, forHTTPHeaderField: "User-Agent")
        request.setValue("14.2 (14C18)", forHTTPHeaderField: "X-Xcode-Version")
        request.setValue("com.apple.gs.xcode.auth", forHTTPHeaderField: "X-Apple-App-Info")
        return request
    }

    public static func prepare(_ input: URLRequest) -> URLRequest {
        var request = identityRequest(input)
        request.setValue("text/x-xml-plist", forHTTPHeaderField: "Accept")
        request.setValue("close", forHTTPHeaderField: "Connection")
        return request
    }

    public static func send(_ input: URLRequest, configuration: URLSessionConfiguration = .ephemeral) async throws -> (Data, URLResponse) {
        // A distinct session per request avoids reusing a spent GSA connection.
        // No retry, identity rotation or authentication-error suppression.
        let session = URLSession(configuration: configuration)
        defer { session.finishTasksAndInvalidate() }
        return try await session.data(for: prepare(input))
    }
}

public enum GMRAuthenticationContext {
    @TaskLocal public static var secondFactorCompleted = false

    public static func stage(_ operation: String, clientInfo: String? = nil) -> String {
        let safeOperation = ["init", "complete", "apptokens"].contains(operation) ? operation : "unknown"
        let stage = (secondFactorCompleted ? "Apple GSA post-2FA " : "Apple GSA first ") + safeOperation
        guard let clientInfo else { return stage }
        return stage + " [profile=" + GMRGSAClient.identity(clientInfo, agent: GMRGSAClient.providerUserAgent).name + "]"
    }
}

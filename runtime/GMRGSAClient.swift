import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

public enum GMRGSAClient {
    // Temporary GrandSlam compatibility identity documented by SideInstaller
    // and SideStore PR 1683. This is deliberately separate from the selected
    // provider's provisioning metadata. It does not alter machine IDs or OTPs.
    public static let clientInfo = "<PC> <Windows;6.2(0,0);9200> <com.apple.AuthKit/1 (com.apple.iTunes/12.12.4.1)>"
    public static let userAgent = "akd/1.0 CFNetwork/808.1.4"

    public static func prepare(_ input: URLRequest) -> URLRequest {
        var request = input
        request.setValue(clientInfo, forHTTPHeaderField: "X-MMe-Client-Info")
        request.setValue(userAgent, forHTTPHeaderField: "User-Agent")
        request.setValue("text/x-xml-plist", forHTTPHeaderField: "Accept")
        request.setValue("14.2 (14C18)", forHTTPHeaderField: "X-Xcode-Version")
        request.setValue("com.apple.gs.xcode.auth", forHTTPHeaderField: "X-Apple-App-Info")
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

    public static func stage(_ operation: String) -> String {
        let safeOperation = ["init", "complete", "apptokens"].contains(operation) ? operation : "unknown"
        return (secondFactorCompleted ? "Apple GSA post-2FA " : "Apple GSA first ") + safeOperation
    }
}

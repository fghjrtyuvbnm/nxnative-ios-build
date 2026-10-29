import Foundation

struct StartupMemoryState {
    enum Status { case present, missing, unknown }
    let signature: Int32
    let profile: Int32

    var status: Status {
        if signature == 0 || profile == 0 { return .missing }
        if signature == 1 && profile == 1 { return .present }
        return .unknown
    }
    var message: String {
        switch status {
        case .present: return "Increased Memory Limit is present in the app signature and provisioning profile."
        case .missing: return "Increased Memory Limit is missing from a signing layer. Refresh the App ID capability and re-sign this IPA."
        case .unknown: return "Increased Memory Limit could not be verified from the installed signing data."
        }
    }
    static func flag(_ value: Int32) -> String { value == 1 ? "Present" : value == 0 ? "Missing" : "Unknown" }
    static func budget(available: UInt64, footprint: UInt64?) -> UInt64? {
        guard let footprint else { return nil }
        let result = available.addingReportingOverflow(footprint)
        return result.overflow ? nil : result.partialValue
    }
}

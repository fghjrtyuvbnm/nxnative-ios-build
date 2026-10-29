import Foundation

@main struct AccountResponseContract {
static func main() throws {
    let valid: [String: Any] = ["developer": ["email": "PRIVATE_EMAIL@example.invalid", "personId": "123456789", "unrelatedPlistDate": Date()]]
    let account = try GMRAccountResponse.decodeAccount(valid)
    guard account.identifier == 123456789 else { fatalError("Account schema conversion failed") }
    let invalid: [[String: Any]] = [
        [:], ["developer": NSNull()], ["developer": []],
        ["developer": ["email": "PRIVATE_EMAIL@example.invalid", "personId": "PRIVATE_IDENTIFIER"]],
        ["developer": ["personId": "123456789"]]
    ]
    for response in invalid {
        do { _ = try GMRAccountResponse.decodeAccount(response); fatalError("Invalid account accepted") }
        catch {
            let message = error.localizedDescription
            guard message.contains("Apple account"), !message.contains("PRIVATE_EMAIL"), !message.contains("PRIVATE_IDENTIFIER"), !message.contains("123456789") else { fatalError("Account values leaked or stage missing") }
        }
    }
    let shape = GMRAccountResponse.schema(["teams": "PRIVATE_MARKER", "resultCode": 1], section: "teams")
    guard shape.contains("teams:string"), !shape.contains("PRIVATE_MARKER") else { fatalError("Team diagnostics leaked values") }
    let serviceCodes: [Any] = [1100, "1100"]
    for code in serviceCodes {
        do {
            _ = try GMRAccountResponse.decodeAccount(["resultCode": code, "developer": ["email": "PRIVATE_EMAIL@example.invalid", "personId": "123456789"]])
            fatalError("Service rejection was accepted because account data existed")
        } catch {
            guard error.localizedDescription.contains("resultCode=1100"), !error.localizedDescription.contains("PRIVATE_EMAIL") else { fatalError("Numeric service result was lost") }
        }
    }
    guard GMRAccountResponse.schema(["resultCode": 1100], section: "developer").contains("resultCode=1100") else { fatalError("Result diagnostic only showed the type") }
    // Multi-step account persistence contract: decoding and Codable round-trip
    // must retain the same public numeric identifier and email.
    let restored = try JSONDecoder().decode(Account.self, from: JSONEncoder().encode(account))
    guard restored.identifier == account.identifier && restored.appleID == account.appleID else { fatalError("Account round-trip changed identity") }
    print("Account lookup/decode stages, private-value omission and Codable round-trip fixtures passed")
}}

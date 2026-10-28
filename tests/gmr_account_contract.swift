import Foundation

func accountData(_ identifier: Any) throws -> Data {
    try JSONSerialization.data(withJSONObject: ["email": "synthetic@example.invalid", "personId": identifier, "firstName": "Synthetic", "lastName": "Fixture"])
}

@main struct AccountContract {
static func main() throws {
    let numeric = try JSONDecoder().decode(Account.self, from: accountData(123456789))
    guard numeric.identifier == 123456789 else { fatalError("Numeric account ID changed") }
    do {
        let string = try JSONDecoder().decode(Account.self, from: accountData("123456789"))
        guard string.identifier == numeric.identifier else { fatalError("String identifier was not preserved") }
    } catch {
        print("Account numeric-string regression: original decoder rejected a valid numeric representation")
        exit(42)
    }
    let invalidValues: [Any] = ["invalid-ID", "9999999999999999999999999999999999999999", true, 1.5, NSNull()]
    for invalid in invalidValues {
        do { _ = try JSONDecoder().decode(Account.self, from: accountData(invalid)); fatalError("Invalid ID was silently coerced") } catch { }
    }
    let missingNames = try JSONDecoder().decode(Account.self, from: Data("{\"email\":\"synthetic@example.invalid\",\"personId\":\"123456789\"}".utf8))
    guard missingNames.firstName == "Unknown", missingNames.lastName == "Unknown" else { fatalError("Name defaults changed") }
    print("Numeric/string account IDs, malformed IDs and name fallback fixtures passed")
}}

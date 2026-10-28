"""Preserve Account's Int API while accepting lossless decimal string IDs."""
import pathlib, shutil
from prepare_gmr_login import replace_once

def prepare(dependency):
    dependency = pathlib.Path(dependency)
    model = dependency/'Sources/StosSign_Common/Models/Apple API/Account.swift'
    text = model.read_text()
    text = replace_once(text, 'identifier = try container.decode(Int.self, forKey: .identifier)', '''if let numeric = try? container.decode(Int.self, forKey: .identifier) {
            identifier = numeric
        } else {
            let decimal = try container.decode(String.self, forKey: .identifier)
            guard !decimal.isEmpty, decimal.utf8.allSatisfy({ $0 >= 48 && $0 <= 57 }), let numeric = Int(decimal) else {
                throw DecodingError.dataCorruptedError(forKey: .identifier, in: container, debugDescription: "Expected a lossless decimal account identifier")
            }
            identifier = numeric
        }''')
    model.write_text(text)
    runtime = pathlib.Path(__file__).resolve().parents[1]/'runtime/GMRAccountResponse.swift'
    shutil.copyfile(runtime, dependency/'Sources/StosSign_Common/GMRAccountResponse.swift')
    api = dependency/'Sources/StosSign_API/AppleAPI.swift'; text = api.read_text()
    begin = text.index('    public func fetchAccount(session:')
    start = text.index('        guard let dictionary = response["developer"]', begin)
    end = text.index('        return account', start)+len('        return account')
    text = text[:start]+'        return try GMRAccountResponse.decodeAccount(response)'+text[end:]
    begin = text.index('    public func fetchTeamsForAccount(')
    end = text.index('    public func fetchDevicesForTeam(', begin)
    part = text[begin:end]
    part = replace_once(part, 'throw AppleAPIError.badServerResponse', 'throw GMRAuthResponseError("Apple team lookup schema: " + GMRAccountResponse.schema(response, section: "teams") + ". No response values logged.")')
    text = text[:begin]+part+text[end:]
    api.write_text(text)
    return {'account_numeric_string_ids_supported': True, 'account_and_team_schema_diagnostics': True, 'account_identifier_public_type': 'Int'}

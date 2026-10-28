"""Align trusted-device response negotiation and identify every plist boundary."""
import pathlib, shutil
from prepare_gmr_login import replace_once

def prepare(source, dependency):
    dependency = pathlib.Path(dependency)
    runtime = pathlib.Path(__file__).resolve().parents[1]/'runtime/GMRAuthResponse.swift'
    shutil.copyfile(runtime, dependency/'Sources/StosSign_Common/GMRAuthResponse.swift')
    path = dependency/'Sources/StosSign_Auth/Authentication.swift'; text = path.read_text()
    text = replace_once(text, '''let (data, _) = try await AppleAPI.shared.session.data(for: request)
        
        guard let responseDictionary = try PropertyListSerialization.propertyList(
            from: data,
            format: nil
        ) as? [String: Any],''', '''let (data, response) = try await AppleAPI.shared.session.data(for: request)
        let operation = ["init", "complete", "apptokens"].contains(requestParameters["o"] as? String ?? "") ? requestParameters["o"] as! String : "unknown"
        let responseDictionary = try GMRAuthResponse.plist(data, response: response, stage: "Apple GSA " + operation)
        guard''')
    text = replace_once(text, '''guard let decryptedDictionary = try PropertyListSerialization.propertyList(
            from: decryptedData,
            format: nil
        ) as? [String: Any],''', '''let decryptedDictionary = try GMRAuthResponse.localPlist(decryptedData, stage: "Apple decrypted account")
        guard''')
    text = replace_once(text, '''guard let tokensDictionary = try PropertyListSerialization.propertyList(
            from: token,
            format: nil
        ) as? [String: Any] else {
            throw URLError(.badServerResponse)
        }''', '''let tokensDictionary = try GMRAuthResponse.localPlist(token, stage: "Apple decrypted app token")''')
    text = replace_once(text, '''let (data, _) = try await AppleAPI.shared.session.data(for: verifyRequest)
        
        guard let responseDictionary = try PropertyListSerialization.propertyList(
            from: data,
            format: nil
        ) as? [String: Any] else {
            throw URLError(.badServerResponse)
        }
        
        let errorCode = responseDictionary["ec"] as? Int ?? 0''', '''verifyRequest = GMRAuthResponse.preferPlist(verifyRequest)
        let (data, response) = try await AppleAPI.shared.session.data(for: verifyRequest)
        let responseDictionary = try GMRAuthResponse.plist(data, response: response, stage: "Apple 2FA validate")
        let errorCode = try GMRAuthResponse.code(responseDictionary, stage: "Apple 2FA validate")''')
    # Only the first requestCode call is the trusted-device plist endpoint.
    old = 'let _ = try? await AppleAPI.shared.session.data(for: request)'
    if text.count(old) != 2: raise ValueError('Pinned code-request contexts differ')
    text = text.replace(old, '''let (codeData, codeResponse) = try await AppleAPI.shared.session.data(for: GMRAuthResponse.preferPlist(request))
            try GMRAuthResponse.requireHTTP(codeData, response: codeResponse, stage: "Apple 2FA request code")''', 1)
    # Preserve the separate SMS endpoint's response format.
    text = text.replace(old, '''let (codeData, codeResponse) = try await AppleAPI.shared.session.data(for: request)
        try GMRAuthResponse.requireHTTP(codeData, response: codeResponse, stage: "Apple SMS request code")''', 1)
    path.write_text(text)
    api = dependency/'Sources/StosSign_API/AppleAPI.swift'; text = api.read_text()
    text = replace_once(text, '''let (data, _) = try await self.session.data(for: request)
        
        guard let responseDictionary = try PropertyListSerialization.propertyList(from: data, options: [], format: nil) as? [String: Any] else {
            throw AppleAPIError.badServerResponse
        }
        
        return responseDictionary''', '''let (data, response) = try await self.session.data(for: request)
        let label: String
        switch requestURL.lastPathComponent {
        case "viewDeveloper.action": label = "Apple account lookup"
        case "listTeams.action": label = "Apple team lookup"
        case "listAppIds.action": label = "Apple App ID lookup"
        default: label = "Apple developer service"
        }
        return try GMRAuthResponse.plist(data, response: response, stage: label)''')
    api.write_text(text)
    return {'trusted_device_plist_negotiation': True, 'post_2fa_plist_stage_diagnostics': True, 'twofactor_original_response_semantics_retained': True}

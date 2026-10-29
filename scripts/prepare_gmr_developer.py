"""Give every developer request fresh one-time data and a stable identity pair."""
import pathlib
from prepare_gmr_login import replace_once

def prepare(dependency):
    dependency = pathlib.Path(dependency)
    path = dependency/'Sources/StosSign_API/AppleAPISession.swift'; text = path.read_text()
    text = replace_once(text, '    public var anisetteData: AnisetteData', '''    public var anisetteData: AnisetteData
    public var anisetteDataRefreshHandler: (() async throws -> AnisetteData)?
    public var providerUserAgent: String?

    public func requestContext() async throws -> AppleAPISession {
        let fresh: AnisetteData
        if let refresh = anisetteDataRefreshHandler { fresh = try await refresh() }
        else { fresh = anisetteData }
        guard fresh.localUserID == anisetteData.localUserID,
              fresh.deviceUniqueIdentifier == anisetteData.deviceUniqueIdentifier else {
            throw GMRAuthResponseError("Apple developer request: provisioning identity changed; sign in again. No identifiers logged.")
        }
        let request = AppleAPISession(dsid: dsid, authTokens: authTokens, anisetteData: fresh)
        request.authToken = authToken
        request.providerUserAgent = providerUserAgent
        return request
    }''')
    path.write_text(text)
    path = dependency/'Sources/StosSign_Auth/Authentication.swift'; text = path.read_text()
    text = replace_once(text, '            let account = try await AppleAPI.shared.fetchAccount(session: session)', '''            session.anisetteDataRefreshHandler = anisetteDataRefreshHandler
            session.providerUserAgent = GMRGSAClient.providerUserAgent
            let account = try await AppleAPI.shared.fetchAccount(session: session)''')
    path.write_text(text)
    path = dependency/'Sources/StosSign_API/AppleAPI.swift'; text = path.read_text()
    methods = [('sendServicesRequest', 'sendEditRequest'), ('sendEditRequest', 'sendRequestWithURL'), ('sendRequestWithURL', 'fetchAccount')]
    for name, following in reversed(methods):
        start = text.index('    public func '+name+'(')
        end = text.index('    public func '+following+'(', start)
        part = text[start:end]
        opening = part.index('\n')+1
        part = part[:opening]+'        let requestSession = try await session.requestContext()\n'+part[opening:]
        for field in ('dsid', 'authToken', 'authTokens', 'anisetteData'):
            part = part.replace('session.'+field, 'requestSession.'+field)
        lines = part.splitlines(); inserted = 0; output = []
        for line in lines:
            if 'let (data,' in line and '.data(for: request)' in line:
                output.append('        request = GMRGSAClient.identityRequest(request, providerAgent: requestSession.providerUserAgent)')
                inserted += 1
            output.append(line)
        if inserted != 1: raise ValueError('Developer request transport context differs')
        part = '\n'.join(output)+'\n'
        text = text[:start]+part+text[end:]
    text = replace_once(text, '        return try GMRAuthResponse.plist(data, response: response, stage: label)', '''        let decoded = try GMRAuthResponse.plist(data, response: response, stage: label)
        try GMRAccountResponse.requireSuccess(decoded, stage: label)
        return decoded''')
    path.write_text(text)
    return {'developer_request_fresh_anisette': True, 'developer_request_identity_pair_preserved': True, 'developer_result_code_numeric_diagnostics': True}

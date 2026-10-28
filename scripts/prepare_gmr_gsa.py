"""Keep provider provisioning identity distinct from GrandSlam compatibility."""
import pathlib, shutil
from prepare_gmr_login import replace_once

def prepare(source, dependency):
    dependency = pathlib.Path(dependency)
    kit = pathlib.Path(__file__).resolve().parents[1]
    shutil.copyfile(kit/'runtime/GMRGSAClient.swift', dependency/'Sources/StosSign_Common/GMRGSAClient.swift')
    path = dependency/'Sources/StosSign_Auth/Authentication.swift'; text = path.read_text()
    text = replace_once(text, 'let (data, response) = try await AppleAPI.shared.session.data(for: request)', 'let (data, response) = try await GMRGSAClient.send(request)')
    text = replace_once(text, 'stage: "Apple GSA " + operation', 'stage: GMRAuthenticationContext.stage(operation, clientInfo: anisetteData.deviceDescription)')
    text = replace_once(text, '''httpHeaders.forEach { request.addValue($0.value, forHTTPHeaderField: $0.key) }
        
        return request''', '''httpHeaders.forEach { request.addValue($0.value, forHTTPHeaderField: $0.key) }
        return GMRGSAClient.identityRequest(request)''')
    original = '''return try await authenticate(
                appleID: unsanitizedAppleID,
                password: password,
                anisetteData: freshAnisetteData,
                smsClientInfo: smsClientInfo,
                verificationHandler: verificationHandler,
                anisetteDataRefreshHandler: anisetteDataRefreshHandler
            )'''
    if text.count(original) != 2: raise ValueError('Post-2FA recursion contexts differ')
    text = text.replace(original, '''return try await GMRAuthenticationContext.$secondFactorCompleted.withValue(true) {
                try await authenticate(
                    appleID: unsanitizedAppleID,
                    password: password,
                    anisetteData: freshAnisetteData,
                    smsClientInfo: smsClientInfo,
                    verificationHandler: verificationHandler,
                    anisetteDataRefreshHandler: anisetteDataRefreshHandler
                )
            }''')
    path.write_text(text)
    login = pathlib.Path(source)/'GetMoreRam/LoginViewModel.swift'; app_text = login.read_text()
    app_text = replace_once(app_text, 'let (account, session) = try await Authentication.authenticate(', 'let (account, session) = try await GMRGSAClient.$providerUserAgent.withValue(AnisetteDataHelper.shared.userAgent) {\n                try await Authentication.authenticate(')
    app_text = replace_once(app_text, '''try await AnisetteDataHelper.shared.getAnisetteData(refresh: true)
            })''', '''try await AnisetteDataHelper.shared.getAnisetteData(refresh: true)
            })
            }''')
    login.write_text(app_text)
    helper = pathlib.Path(source)/'GetMoreRam/AnisetteDataHelper.swift'; helper_text = helper.read_text()
    helper_text = replace_once(helper_text, '_ = try GMRServer.clientInfo(data, response: response as? HTTPURLResponse)', 'let (client, agent) = try GMRServer.clientInfo(data, response: response as? HTTPURLResponse)\n        let selected = GMRGSAClient.identity(client, agent: agent)')
    helper_text = replace_once(helper_text, 'return "v3 metadata is valid. This check does not test Apple sign-in."', 'return "v3 metadata is valid. GSA profile: \\(selected.name). This check does not test Apple sign-in."')
    helper.write_text(helper_text)
    server = pathlib.Path(source)/'GetMoreRam/GMRServer.swift'
    server.write_text(server.read_text().replace('jkcoxson (Windows ADI)', 'jkcoxson (ani)'))
    # GSA and second-factor requests use the same provider-aware base identity;
    # endpoint-specific plist/SMS formats and provisioning remain independent.
    return {'gsa_identity_separate_from_provisioning': True, 'gsa_provider_aware_identity_selection': True, 'gsa_session_per_request': True, 'automatic_authentication_retries': 0, 'gsa_application_headers_aligned': True, 'first_and_post_2fa_stage_labels': True, 'twofactor_identity_aligned_with_gsa': True}

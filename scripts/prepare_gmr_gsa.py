"""Keep provider provisioning identity distinct from GrandSlam compatibility."""
import pathlib, shutil
from prepare_gmr_login import replace_once

def prepare(source, dependency):
    dependency = pathlib.Path(dependency)
    kit = pathlib.Path(__file__).resolve().parents[1]
    shutil.copyfile(kit/'runtime/GMRGSAClient.swift', dependency/'Sources/StosSign_Common/GMRGSAClient.swift')
    path = dependency/'Sources/StosSign_Auth/Authentication.swift'; text = path.read_text()
    text = replace_once(text, 'let (data, response) = try await AppleAPI.shared.session.data(for: request)', 'let (data, response) = try await GMRGSAClient.send(request)')
    text = replace_once(text, 'stage: "Apple GSA " + operation', 'stage: GMRAuthenticationContext.stage(operation)')
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
    # Apply the GSA policy only to GsService2 SRP/token requests. Trusted-device,
    # SMS and provider provisioning retain their independent endpoint policies.
    return {'gsa_windows_identity_separate_from_provider': True, 'gsa_session_per_request': True, 'automatic_authentication_retries': 0, 'gsa_application_headers_aligned': True, 'first_and_post_2fa_stage_labels': True}

"""Offline response/negotiation contracts, with no account or verification code."""
import pathlib, subprocess

def main(dependency, out):
    kit = pathlib.Path(__file__).resolve().parents[1]
    dependency, out = pathlib.Path(dependency), pathlib.Path(out)
    binary = out/'twofactor-contract'
    subprocess.run(['swiftc', '-parse-as-library', str(dependency/'Sources/StosSign_Common/GMRAuthResponse.swift'), str(kit/'tests/gmr_twofactor_contract.swift'), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
    auth = (dependency/'Sources/StosSign_Auth/Authentication.swift').read_text()
    if auth.count('PropertyListSerialization.propertyList(') != 0:
        raise ValueError('Unlabelled authentication plist parsing remains')
    if 'try? await AppleAPI.shared.session.data(for: request)' in auth:
        raise ValueError('Code-request errors are still discarded')
    print('All authentication plist boundaries labelled; code-request failures preserved', flush=True)

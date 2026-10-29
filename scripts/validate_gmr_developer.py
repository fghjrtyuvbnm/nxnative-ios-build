"""Post-change synthetic coverage; real Apple nonce replay is not tested here."""
import pathlib, subprocess

def main(dependency, out):
    dependency, out = pathlib.Path(dependency), pathlib.Path(out)
    kit = pathlib.Path(__file__).resolve().parents[1]
    session = out/'DeveloperSession.swift'
    session.write_text((dependency/'Sources/StosSign_API/AppleAPISession.swift').read_text().replace('import StosSign_Common', ''))
    common = dependency/'Sources/StosSign_Common'
    binary = out/'developer-contract'
    subprocess.run(['swiftc', '-parse-as-library', str(common/'Models/Anisette/AnisetteData.swift'), str(common/'GMRAuthResponse.swift'), str(common/'GMRGSAClient.swift'), str(session), str(kit/'tests/gmr_developer_contract.swift'), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
    text = (dependency/'Sources/StosSign_API/AppleAPI.swift').read_text()
    if text.count('let requestSession = try await session.requestContext()') != 3: raise ValueError('Not all developer transports request fresh context')
    if text.count('providerAgent: requestSession.providerUserAgent') != 3: raise ValueError('Developer identity pair was not preserved')
    print('Three developer transports use request-local context; no live Apple account or nonce replay performed', flush=True)

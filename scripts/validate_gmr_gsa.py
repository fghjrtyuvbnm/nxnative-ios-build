"""Exercise the exact old header policy and the new production GSA helper offline."""
import pathlib, subprocess

def main(dependency, out):
    dependency, out = pathlib.Path(dependency), pathlib.Path(out)
    kit = pathlib.Path(__file__).resolve().parents[1]
    auth = (dependency/'Sources/StosSign_Auth/Authentication.swift').read_text()
    begin = auth.index('        var httpHeaders = [', auth.index('public static func sendAuthenticationRequest('))
    end = auth.index('\n        let bodyData', begin)
    old = out/'gsa-legacy.swift'
    old.write_text('''import Foundation
struct Fixture { let deviceDescription: String }
func headers(_ anisetteData: Fixture) -> [String: String] {
'''+auth[begin:end]+'''
return httpHeaders
}
let value = headers(Fixture(deviceDescription: "synthetic-Mac-provider-identity"))
// The required Windows policy fails under the exact prior header expression.
if value["X-MMe-Client-Info"]?.contains("Windows") != true { exit(42) }
exit(0)
''')
    baseline = out/'gsa-legacy'
    subprocess.run(['swiftc', str(old), '-o', str(baseline)], check=True)
    if subprocess.run([str(baseline)]).returncode != 42: raise ValueError('Original policy mismatch not reproduced')
    binary = out/'gsa-contract'
    helper = dependency/'Sources/StosSign_Common/GMRGSAClient.swift'
    subprocess.run(['swiftc', '-parse-as-library', str(helper), str(kit/'tests/gmr_gsa_contract.swift'), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
    text = helper.read_text()
    if 'let session = URLSession(configuration: configuration)' not in text or 'defer { session.finishTasksAndInvalidate() }' not in text:
        raise ValueError('Per-request session lifecycle changed')
    print('Original provider-derived GSA identity mismatch reproduced; independent session lifecycle checked', flush=True)

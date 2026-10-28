"""Native offline regression from the exact old/new response-routing expressions."""
import pathlib, subprocess, sys

def main(legacy, modern, out):
    legacy, modern, out = pathlib.Path(legacy), pathlib.Path(modern), pathlib.Path(out)
    old = (legacy/'Sources/StosSign/Apple API/AppleAPI.swift').read_text()
    new = (modern/'Sources/StosSign_Auth/Authentication.swift').read_text()
    start = 'let authType = statusDictionary["au"] as? String'
    baseline = old[old.index(start):old.index('switch authType {', old.index(start))] + '\nreturn authType\n'
    candidate = new[new.index(start):new.index('switch effectiveAuthType {', new.index(start))] + '\nreturn effectiveAuthType\n'
    cases = '''
let cases: [([String: Any], String?)] = [
    (["hsc": 409], "trustedDeviceSecondaryAuth"),
    (["hsc": 409, "au": ""], "trustedDeviceSecondaryAuth"),
    (["au": "trustedDeviceSecondaryAuth"], "trustedDeviceSecondaryAuth"),
    (["hsc": 409, "au": "secondaryAuth"], "secondaryAuth"),
    (["hsc": 200], nil), ([:], nil), (["au": "unknown"], "unknown")
]
for (status, expected) in cases { if route(status) != expected { exit(42) } }
print("Seven offline authentication routing fixtures passed")
'''
    for kind, body in [('legacy', baseline), ('candidate', candidate)]:
        file = out/('route-'+kind+'.swift')
        file.write_text('import Foundation\nfunc route(_ statusDictionary: [String: Any]) -> String? {\n'+body+'}\n'+cases)
        binary = out/('route-'+kind)
        subprocess.run(['swiftc', str(file), '-o', str(binary)], check=True)
        p = subprocess.run([str(binary)])
        if kind == 'legacy' and p.returncode != 42: raise ValueError('Expected original routing failure absent')
        if kind == 'candidate' and p.returncode != 0: raise ValueError('Candidate routing regression')
    # This executes the exact freshness helper with synthetic data and a mocked
    # supplier; it never makes a network request or contains an account.
    begin = new.index('private static func refreshedAnisetteData(')
    end = new.index('\n    /// Optional:', begin)
    helper = new[begin:end].replace('private static func', 'static func')
    file = out/'freshness.swift'; binary = out/'freshness'
    file.write_text('''import Foundation
struct AnisetteData { let nonce: Int }
enum Probe {
'''+helper+'''
}
@main struct Test {
static func main() async throws {
    var calls = 0
    let original = AnisetteData(nonce: 1)
    let fresh = try await Probe.refreshedAnisetteData(original, using: { calls += 1; return AnisetteData(nonce: 2) })
    guard fresh.nonce == 2 && calls == 1 else { exit(43) }
    let unchanged = try await Probe.refreshedAnisetteData(original, using: nil)
    guard unchanged.nonce == 1 else { exit(44) }
    print("Freshness callback and fallback fixtures passed")
}}
''')
    subprocess.run(['swiftc', '-parse-as-library', str(file), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
    print('Original missing-au/409 RED observed; updated routing GREEN', flush=True)

if __name__ == '__main__': main(*sys.argv[1:])

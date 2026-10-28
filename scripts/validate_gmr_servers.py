"""Run Foundation contracts and the exact deployed configuration method offline."""
import pathlib, subprocess

def main(source, out):
    app = pathlib.Path(source)/'GetMoreRam'; out = pathlib.Path(out)
    kit = pathlib.Path(__file__).resolve().parents[1]
    text = (app/'AnisetteDataHelper.swift').read_text()
    start = text.index('    @discardableResult\n    func configureServer(')
    end = text.index('\n    func checkServer(', start)
    method = text[start:end]
    harness = out/'server-harness.swift'
    harness.write_text('''import Foundation
final class Keychain {
    static let shared = Keychain()
    var adiPb: String?
    var identifier: String?
}
final class Harness {
    var url: URL?
    var resets = 0
    func resetClientInfo() { resets += 1 }
'''+method+'\n}\n')
    binary = out/'server-contract'
    subprocess.run(['swiftc', '-parse-as-library', str(app/'GMRServer.swift'), str(harness), str(kit/'tests/gmr_server_contract.swift'), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
    if any(marker in text for marker in ('Anisette used:', 'Original JSON:', 'Got response:')):
        raise ValueError('Raw authentication logging remains')
    print('No raw authentication response logging; server contracts passed', flush=True)

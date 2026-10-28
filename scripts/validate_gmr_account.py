"""Run the exact pinned Account model before and after the lossless ID repair."""
import pathlib, subprocess

def main(dependency, out, original=False):
    kit = pathlib.Path(__file__).resolve().parents[1]
    dependency, out = pathlib.Path(dependency), pathlib.Path(out)
    model = dependency/'Sources/StosSign_Common/Models/Apple API/Account.swift'
    binary = out/('account-original' if original else 'account-candidate')
    subprocess.run(['swiftc', '-parse-as-library', str(model), str(kit/'tests/gmr_account_contract.swift'), '-o', str(binary)], check=True)
    status = subprocess.run([str(binary)]).returncode
    if status != (42 if original else 0): raise ValueError('Account regression result differs')
    if original:
        print('Original Account numeric-string RED observed', flush=True)
        return
    binary = out/'account-response-contract'
    common = dependency/'Sources/StosSign_Common'
    subprocess.run(['swiftc', '-parse-as-library', str(model), str(common/'GMRAuthResponse.swift'), str(common/'GMRAccountResponse.swift'), str(kit/'tests/gmr_account_response_contract.swift'), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
    print('Candidate Account GREEN; Int public API preserved', flush=True)

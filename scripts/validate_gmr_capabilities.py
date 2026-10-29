"""Synthetic capability responses and state transitions; no live Apple updates."""
import pathlib, subprocess

def main(dependency, out):
    dependency, out = pathlib.Path(dependency), pathlib.Path(out)
    kit = pathlib.Path(__file__).resolve().parents[1]; common = dependency/'Sources/StosSign_Common'
    model = common/'Models/Apple API'
    for baseline in (True, False):
        binary = out/('memory-uncertainty-baseline' if baseline else 'memory-uncertainty-candidate')
        runtime = kit/'tests/fixtures/gmr-memory-1.0.9.swift' if baseline else common/'GMRMemoryCapabilities.swift'
        command = ['swiftc', '-parse-as-library'] + (['-D', 'BASELINE_UNCERTAINTY'] if baseline else [])
        subprocess.run(command + list(map(str, [model/'AppID.swift', common/'GMRAuthResponse.swift', runtime, kit/'tests/gmr_memory_uncertainty_contract.swift'])) + ['-o', str(binary)], check=True)
        status = subprocess.run([str(binary)]).returncode
        if status != (42 if baseline else 0): raise ValueError('Accepted/unconfirmed baseline/candidate behavior differs')
    # Exact 1.0.8 runtime snapshot: the same single-item lifecycle fails
    # behaviorally, not because the new Selection API is missing.
    for baseline in (True, False):
        binary = out/('memory-selection-baseline' if baseline else 'memory-selection-candidate')
        runtime = kit/'tests/fixtures/gmr-memory-1.0.8.swift' if baseline else common/'GMRMemoryCapabilities.swift'
        command = ['swiftc', '-parse-as-library'] + (['-D', 'BASELINE'] if baseline else [])
        subprocess.run(command + list(map(str, [model/'AppID.swift', common/'GMRAuthResponse.swift', runtime, kit/'tests/gmr_memory_selection_contract.swift'])) + ['-o', str(binary)], check=True)
        status = subprocess.run([str(binary)]).returncode
        if status != (42 if baseline else 0): raise ValueError('Single-item baseline/candidate behavior differs')
    for name, sources in [
        ('capability-response', [model/'Account.swift', common/'GMRAuthResponse.swift', common/'GMRAccountResponse.swift', common/'GMRCapabilityResponse.swift', kit/'tests/gmr_capability_response_contract.swift']),
        ('memory-flow', [model/'AppID.swift', common/'GMRAuthResponse.swift', common/'GMRMemoryCapabilities.swift', kit/'tests/gmr_memory_flow_contract.swift'])
    ]:
        binary = out/name
        subprocess.run(['swiftc', '-parse-as-library', *map(str, sources), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
    api = (dependency/'Sources/StosSign_API/AppleAPI.swift').read_text()
    if 'print("Server Response: \\(response)")' in api: raise ValueError('Raw capability response logging remains')
    print('Capability protocol and readback regressions passed; no live permission grant tested', flush=True)

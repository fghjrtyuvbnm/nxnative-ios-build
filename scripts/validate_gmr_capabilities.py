"""Synthetic capability responses and state transitions; no live Apple updates."""
import pathlib, subprocess

def main(dependency, out):
    dependency, out = pathlib.Path(dependency), pathlib.Path(out)
    kit = pathlib.Path(__file__).resolve().parents[1]; common = dependency/'Sources/StosSign_Common'
    model = common/'Models/Apple API'
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

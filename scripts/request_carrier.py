"""Create an explicitly authorized ad-hoc entitlement request carrier, not a provisioned app."""
import hashlib, json, pathlib, plistlib, struct, subprocess, sys, zipfile, os, time

KEYS = {'com.apple.developer.kernel.increased-memory-limit'}
SOURCE_SHA = '81e29cf34568b3a8752e42ac16b47d459de3d853b8dd8b311f4de0efaa12c5e9'
NAME = 'FINAL-FANTASY-RESONANCE-HK-1.0.1-ios18-vm-audit-unsigned.ipa'
STAGE = 'initialization'

def stage(name):
    global STAGE
    STAGE = name
    print('Carrier stage: '+name, flush=True)

def native_command(args, base):
    result = subprocess.run(args, capture_output=True)
    if result.returncode:
        # Keep command diagnostics private; no credential or environment dump.
        from private_io import gh, DATA_REPOSITORY
        diagnostic = base/'codesign-diagnostic.json'
        diagnostic.write_text(json.dumps({'stage': STAGE, 'exit_code': result.returncode, 'stderr': result.stderr.decode(errors='replace')}, indent=2))
        tag = 'request-carrier-diagnostic-'+os.environ['GITHUB_RUN_ID']
        gh('release', 'create', tag, '--repo', DATA_REPOSITORY, '--title', 'Private request-carrier signing diagnostic', '--notes', 'Failed build diagnostic only; no installable IPA.', '--prerelease')
        gh('release', 'upload', tag, '--repo', DATA_REPOSITORY, diagnostic)
        raise RuntimeError('Native command failed; diagnostic retained privately')
    return result

def download_original(base):
    from private_io import gh, DATA_REPOSITORY
    release = json.loads(gh('api', f'repos/{DATA_REPOSITORY}/releases/tags/ios18-launcher-40649605564?refresh={time.time_ns()}').stdout)
    matches = [a for a in release['assets'] if a['name'] == NAME]
    if len(matches) != 1: raise ValueError('Exactly one original asset required')
    asset = matches[0]
    env = dict(os.environ)
    if env.get('PRIVATE_DATA_TOKEN'): env['GH_TOKEN'] = env['PRIVATE_DATA_TOKEN']
    with (base/NAME).open('wb') as output:
        result = subprocess.run(['gh', 'api', f'repos/{DATA_REPOSITORY}/releases/assets/{asset["id"]}?refresh={time.time_ns()}', '-H', 'Accept: application/octet-stream'], env=env, stdout=output, stderr=subprocess.PIPE, timeout=180)
    if result.returncode or (base/NAME).stat().st_size != asset['size']: raise ValueError('Original asset download incomplete')

def validate_requests(value):
    if set(value) != KEYS or any(value[k] is not True for k in KEYS):
        raise ValueError('Exactly one Boolean Increased Memory Limit request required')

def canonical_request(data):
    value = plistlib.loads(data)
    validate_requests(value)
    return plistlib.dumps(value, fmt=plistlib.FMT_XML, sort_keys=True)

def digest(data): return hashlib.sha256(data).hexdigest()

def sections(data):
    if data[:4] != b'\xcf\xfa\xed\xfe': raise ValueError('Thin little-endian Mach-O required')
    result = {}; pos = 32
    for _ in range(struct.unpack_from('<I', data, 16)[0]):
        cmd, size = struct.unpack_from('<II', data, pos)
        if size < 8 or pos + size > len(data): raise ValueError('Invalid load command')
        if cmd == 0x19:
            count = struct.unpack_from('<I', data, pos + 64)[0]
            for i in range(count):
                off = pos + 72 + i * 80
                name, segment, addr, length, offset = struct.unpack_from('<16s16sQQI', data, off)
                flags = struct.unpack_from('<I', data, off + 64)[0] & 255
                # Zero-fill sections have no file-backed bytes.
                if flags not in (1, 12, 18):
                    if offset + length > len(data): raise ValueError('Section out of bounds')
                    result[(segment, name)] = (length, digest(data[offset:offset + length]))
        pos += size
    if not result: raise ValueError('No file-backed sections')
    return result

def main(base):
    from private_io import assert_private, gh, DATA_REPOSITORY
    stage('private-source-check')
    assert_private()
    base = pathlib.Path(base); base.mkdir(parents=True, exist_ok=False)
    source = base / NAME
    stage('download-original')
    download_original(base)
    stage('verify-original-and-requests')
    if digest(source.read_bytes()) != SOURCE_SHA: raise ValueError('Source IPA differs')
    request_source = pathlib.Path(__file__).resolve().parents[1] / 'runtime/MemoryRequirements.entitlements'
    request = base/'MemoryRequirements.entitlements'
    # AMFI's XML reader is stricter than Python's; give codesign canonical LF XML.
    request.write_bytes(canonical_request(request_source.read_bytes()))
    unpack = base / 'unpacked'
    with zipfile.ZipFile(source) as z:
        for n in z.namelist():
            p = pathlib.PurePosixPath(n)
            if p.is_absolute() or '..' in p.parts or '\\' in n: raise ValueError('Unsafe archive path')
        z.extractall(unpack)
    apps = list((unpack / 'Payload').glob('*.app'))
    if len(apps) != 1: raise ValueError('One app required')
    app = apps[0]; info = plistlib.loads((app / 'Info.plist').read_bytes())
    binary = app / info['CFBundleExecutable']
    if info['CFBundleVersion'] != '1.0.7': raise ValueError('Source version differs')
    if (app / 'embedded.mobileprovision').exists(): raise ValueError('Unexpected provisioning')
    before = sections(binary.read_bytes())
    files = {p.relative_to(app).as_posix(): digest(p.read_bytes()) for p in app.rglob('*') if p.is_file() and p != binary}
    binary.chmod(0o755)
    stage('embed-and-verify-single-request')
    native_command(['codesign', '--force', '--sign', '-', '--entitlements', str(request), '--timestamp=none', str(app)], base)
    stage('verify-native-signature')
    native_command(['codesign', '--verify', '--strict', str(app)], base)
    stage('verify-native-entitlements')
    actual = native_command(['codesign', '-d', '--entitlements', ':-', str(app)], base).stdout
    validate_requests(plistlib.loads(actual))
    details = subprocess.run(['codesign', '-dvv', str(app)], check=True, capture_output=True).stderr.decode()
    if 'Signature=adhoc' not in details or 'Authority=' in details: raise ValueError('Unexpected signing identity')
    if before != sections(binary.read_bytes()): raise ValueError('Executable section bytes changed')
    for name, sha in files.items():
        if digest((app / name).read_bytes()) != sha: raise ValueError('Original resource changed')
    out = base / NAME.replace('-unsigned', '-increased-memory-only-adhoc-request-carrier')
    stage('pack-and-verify-resources')
    subprocess.run(['ditto', '-c', '-k', '--keepParent', str(unpack / 'Payload'), str(out)], check=True, capture_output=True)
    with zipfile.ZipFile(out) as z:
        if z.testzip(): raise ValueError('ZIP CRC failed')
    report = {'kind': 'adhoc-request-carrier', 'source_sha256': SOURCE_SHA, 'sha256': digest(out.read_bytes()), 'bytes': out.stat().st_size,
              'bundle_build': '1.0.7', 'requests': sorted(KEYS), 'signed_adhoc': True, 'apple_certificate_used': False,
              'profile_permissions_granted': False, 'executable_sections_unchanged': True, 'original_resources_unchanged': True,
              'native_codesign_verification': True, 'gameplay_verified': False}
    check = out.with_suffix('.verification.json'); check.write_text(json.dumps(report, indent=2))
    stage('private-publication')
    assert_private(); tag = 'ios18-request-carrier-' + os.environ['GITHUB_RUN_ID']
    gh('release', 'create', tag, '--repo', DATA_REPOSITORY, '--title', 'iOS 18 Increased Memory Limit only request carrier', '--notes', 'Not Apple provisioned or directly installable. Requests Increased Memory Limit only; Extended Virtual Addressing is absent. Requires final signing with a matching capable profile. Original unsigned IPA remains available.', '--prerelease')
    gh('release', 'upload', tag, '--repo', DATA_REPOSITORY, out, check)
    print('Verified ad-hoc request carrier published privately; no profile permissions granted.', flush=True)

if __name__ == '__main__':
    try: main(*sys.argv[1:])
    except Exception as error:
        print('Carrier preparation failed at '+STAGE+' ('+type(error).__name__+'); no raw diagnostics or private URLs logged.', flush=True)
        raise SystemExit(1)

"""Build the pinned public helper without credentials or Apple signing."""
import hashlib, json, os, pathlib, plistlib, shutil, subprocess, sys, zipfile

SOURCE = 'a176a5c0271af8f462170065132021fb683b1706'
URL = 'https://github.com/Loganbogan9/GetMoreRamExtended.git'

def run(*args, cwd=None, log=None):
    if log:
        with log.open('ab') as output:
            p = subprocess.run(args, cwd=cwd, stdout=output, stderr=subprocess.STDOUT)
        if p.returncode:
            lines = log.read_text(errors='replace').splitlines()
            for line in lines[-65:]: print(line, flush=True)
            raise RuntimeError('Build command failed; inspect build log')
    else: subprocess.run(args, cwd=cwd, check=True)

def main(base):
    base = pathlib.Path(base); base.mkdir(parents=True, exist_ok=False)
    source = base/'source'; log = base/'build.log'
    run('git', 'init', str(source))
    run('git', 'fetch', '--depth=1', URL, SOURCE, cwd=source, log=log)
    run('git', 'checkout', '--detach', 'FETCH_HEAD', cwd=source, log=log)
    print('Fetching pinned OpenSSL submodule', flush=True)
    run('git', 'submodule', 'update', '--init', '--recursive', '--depth=1', cwd=source, log=log)
    implementation = (source/'Entitlement/AppIDViewModel.swift').read_text()
    if any(token not in implementation for token in ('INCREASED_MEMORY_LIMIT', 'EXTENDED_VIRTUAL_ADDRESSING')):
        raise ValueError('Both capability actions required')
    print('Building unsigned ARM64 iOS 18 helper with locked packages', flush=True)
    run('xcodebuild', '-project', 'Entitlement.xcodeproj', '-scheme', 'Entitlement', '-configuration', 'Release', '-sdk', 'iphoneos', '-destination', 'generic/platform=iOS', '-derivedDataPath', str(base/'derived'), '-disableAutomaticPackageResolution', '-onlyUsePackageVersionsFromResolvedFile', 'IPHONEOS_DEPLOYMENT_TARGET=18.0', 'ARCHS=arm64', 'CODE_SIGNING_ALLOWED=NO', 'CODE_SIGNING_REQUIRED=NO', 'CODE_SIGN_IDENTITY=', 'DEVELOPMENT_TEAM=', 'INFOPLIST_KEY_CFBundleDisplayName=GetMoreRam Extended', 'build', cwd=source, log=log)
    app = base/'derived/Build/Products/Release-iphoneos/Entitlement.app'
    info = plistlib.loads((app/'Info.plist').read_bytes())
    if info['MinimumOSVersion'] != '18.0': raise ValueError('Wrong deployment target')
    executable = app/info['CFBundleExecutable']
    arches = subprocess.check_output(['lipo', '-archs', str(executable)], text=True).strip()
    if arches != 'arm64': raise ValueError('Unexpected architecture')
    # Prebuilt upstream frameworks may retain their vendor signatures even
    # when Xcode signing is disabled. Remove those, not their executable code.
    removed = 0
    for path in sorted(app.rglob('*')):
        if not path.is_file() or path.is_symlink(): continue
        with path.open('rb') as stream: magic = stream.read(4)
        if magic not in (b'\xcf\xfa\xed\xfe', b'\xce\xfa\xed\xfe', b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca'): continue
        if subprocess.run(['codesign', '-d', str(path)], capture_output=True).returncode == 0:
            run('codesign', '--remove-signature', str(path)); removed += 1
    for directory in app.rglob('_CodeSignature'):
        if directory.is_symlink() or app.resolve() not in directory.resolve().parents:
            raise ValueError('Unsafe signature directory')
        shutil.rmtree(directory)
    print('Removed prebuilt dependency signatures: ' + str(removed), flush=True)
    p = subprocess.run(['codesign', '-d', str(app)], capture_output=True)
    if p.returncode == 0: raise ValueError('Unexpected app signature')
    if list(app.rglob('embedded.mobileprovision')) or list(app.rglob('_CodeSignature')):
        raise ValueError('Unexpected provisioning/signature directory')
    libraries = subprocess.check_output(['otool', '-L', str(executable)], text=True)
    (base/'linked-libraries.txt').write_text(libraries)
    for line in libraries.splitlines()[1:]:
        name = line.strip().split(' (')[0]
        if name.startswith('@rpath/') and not (app/'Frameworks'/name.removeprefix('@rpath/')).exists():
            raise ValueError('Missing bundled dynamic dependency')
    payload = base/'Payload'; payload.mkdir()
    run('ditto', str(app), str(payload/app.name))
    ipa = base/'GetMoreRamExtended-ios18-unsigned.ipa'
    run('ditto', '-c', '-k', '--keepParent', str(payload), str(ipa))
    with zipfile.ZipFile(ipa) as z:
        if z.testzip(): raise ValueError('ZIP CRC failed')
    report = {'source_repository': URL, 'source_commit': SOURCE, 'bundle_identifier': info['CFBundleIdentifier'], 'version': info['CFBundleShortVersionString'], 'minimum_ios': info['MinimumOSVersion'], 'architecture': arches, 'signed': False, 'prebuilt_signatures_removed': removed, 'apple_credentials_used': False, 'both_capability_actions_present': True, 'sha256': hashlib.sha256(ipa.read_bytes()).hexdigest(), 'bytes': ipa.stat().st_size, 'device_login_tested': False, 'capability_grant_tested': False}
    ipa.with_suffix('.verification.json').write_text(json.dumps(report, indent=2))
    print('Unsigned helper built and package checks passed', flush=True)

def publish(base):
    from private_io import assert_private, gh, DATA_REPOSITORY
    assert_private(); base = pathlib.Path(base)
    tag = 'getmoreram-extended-' + os.environ['GITHUB_RUN_ID']
    gh('release', 'create', tag, '--repo', DATA_REPOSITORY, '--title', 'GetMoreRamExtended unsigned iOS 18 build', '--notes', 'Build of Loganbogan9/GetMoreRamExtended at a176a5c0271af8f462170065132021fb683b1706. Unsigned ARM64, minimum iOS 18. No Apple credentials used. Device login and capability grants are not verified.', '--prerelease')
    gh('release', 'upload', tag, '--repo', DATA_REPOSITORY, base/'GetMoreRamExtended-ios18-unsigned.ipa', base/'GetMoreRamExtended-ios18-unsigned.verification.json', base/'build.log', base/'linked-libraries.txt')
    print('Helper package and build evidence saved privately', flush=True)

if __name__ == '__main__':
    if sys.argv[1] == 'publish': publish(sys.argv[2])
    else: main(sys.argv[1])

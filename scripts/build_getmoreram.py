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
    loginfix = os.environ.get('GMR_LOGIN_FIX') == '1'
    serverfix = os.environ.get('GMR_SERVER_FIX') == '1'
    twofactorfix = os.environ.get('GMR_TWOFACTOR_FIX') == '1'
    gsafix = os.environ.get('GMR_GSA_FIX') == '1'
    commit = '6bd5cf9733900d925370865d60c7db8906e60bab' if loginfix else SOURCE
    url = 'https://github.com/no1ce21/GetMoreRam.git' if loginfix else URL
    project_name = 'GetMoreRam' if loginfix else 'Entitlement'
    run('git', 'init', str(source))
    run('git', 'fetch', '--depth=1', url, commit, cwd=source, log=log)
    run('git', 'checkout', '--detach', 'FETCH_HEAD', cwd=source, log=log)
    print('Fetching pinned OpenSSL submodule', flush=True)
    run('git', 'submodule', 'update', '--init', '--recursive', '--depth=1', cwd=source, log=log)
    extra = {}
    if loginfix:
        from prepare_gmr_login import prepare, DEPENDENCY
        from validate_gmr_login import main as validate
        dependency = source/'LoginStosSign'; run('git', 'init', str(dependency))
        run('git', 'fetch', '--depth=1', 'https://github.com/no1ce21/StosSign.git', DEPENDENCY, cwd=dependency, log=log)
        run('git', 'checkout', '--detach', 'FETCH_HEAD', cwd=dependency, log=log)
        legacy = base/'legacy-auth'; run('git', 'init', str(legacy))
        run('git', 'fetch', '--depth=1', 'https://github.com/stossy11/StosSign.git', '70a80bdd2b570020e917ec4a6fb79a8cf4ba1100', cwd=legacy, log=log)
        run('git', 'checkout', '--detach', 'FETCH_HEAD', cwd=legacy, log=log)
        print('Running offline original/candidate authentication regressions', flush=True)
        validate(legacy, dependency, base)
        extra = prepare(source, dependency)
        if serverfix:
            from prepare_gmr_servers import prepare as servers
            from validate_gmr_servers import main as validate_servers
            extra.update(servers(source))
            validate_servers(source, base)
        if twofactorfix:
            from prepare_gmr_twofactor import prepare as twofactor
            from validate_gmr_twofactor import main as validate_twofactor
            extra.update(twofactor(source, dependency))
            validate_twofactor(dependency, base)
        if gsafix:
            from prepare_gmr_gsa import prepare as gsa
            from validate_gmr_gsa import main as validate_gsa
            extra.update(gsa(source, dependency))
            validate_gsa(dependency, base)
    implementation = (source/project_name/'AppIDViewModel.swift').read_text()
    if any(token not in implementation for token in ('INCREASED_MEMORY_LIMIT', 'EXTENDED_VIRTUAL_ADDRESSING')):
        raise ValueError('Both capability actions required')
    print('Building unsigned ARM64 iOS 18 helper with locked packages', flush=True)
    run('xcodebuild', '-project', project_name+'.xcodeproj', '-scheme', project_name, '-configuration', 'Release', '-sdk', 'iphoneos', '-destination', 'generic/platform=iOS', '-derivedDataPath', str(base/'derived'), '-disableAutomaticPackageResolution', '-onlyUsePackageVersionsFromResolvedFile', 'IPHONEOS_DEPLOYMENT_TARGET=18.0', 'ARCHS=arm64', 'CODE_SIGNING_ALLOWED=NO', 'CODE_SIGNING_REQUIRED=NO', 'CODE_SIGN_IDENTITY=', 'DEVELOPMENT_TEAM=', 'PRODUCT_BUNDLE_IDENTIFIER=com.stos.Entitlement', 'MARKETING_VERSION='+('1.0.5' if gsafix else '1.0.3' if twofactorfix else '1.0.2' if serverfix else '1.0.1' if loginfix else '1.0'), 'CURRENT_PROJECT_VERSION='+('6' if gsafix else '4' if twofactorfix else '3' if serverfix else '2' if loginfix else '1'), 'INFOPLIST_KEY_CFBundleDisplayName=GetMoreRam Extended', 'build', cwd=source, log=log)
    app = base/('derived/Build/Products/Release-iphoneos/'+project_name+'.app')
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
    ipa = base/('GetMoreRamExtended-ios18-gsa-1.0.5-unsigned.ipa' if gsafix else 'GetMoreRamExtended-ios18-twofactor-unsigned.ipa' if twofactorfix else 'GetMoreRamExtended-ios18-serverfix-unsigned.ipa' if serverfix else 'GetMoreRamExtended-ios18-loginfix-unsigned.ipa' if loginfix else 'GetMoreRamExtended-ios18-unsigned.ipa')
    run('ditto', '-c', '-k', '--keepParent', str(payload), str(ipa))
    with zipfile.ZipFile(ipa) as z:
        if z.testzip(): raise ValueError('ZIP CRC failed')
    report = {'source_repository': url, 'source_commit': commit, 'bundle_identifier': info['CFBundleIdentifier'], 'version': info['CFBundleShortVersionString'], 'minimum_ios': info['MinimumOSVersion'], 'architecture': arches, 'signed': False, 'prebuilt_signatures_removed': removed, 'apple_credentials_used': False, 'both_capability_actions_present': True, 'sha256': hashlib.sha256(ipa.read_bytes()).hexdigest(), 'bytes': ipa.stat().st_size, 'device_login_tested': False, 'capability_grant_tested': False, **extra}
    ipa.with_suffix('.verification.json').write_text(json.dumps(report, indent=2))
    print('Unsigned helper built and package checks passed', flush=True)

def publish(base):
    from private_io import assert_private, gh, DATA_REPOSITORY
    assert_private(); base = pathlib.Path(base)
    loginfix = os.environ.get('GMR_LOGIN_FIX') == '1'
    serverfix = os.environ.get('GMR_SERVER_FIX') == '1'
    twofactorfix = os.environ.get('GMR_TWOFACTOR_FIX') == '1'
    gsafix = os.environ.get('GMR_GSA_FIX') == '1'
    tag = ('getmoreram-gsa-' if gsafix else 'getmoreram-twofactor-' if twofactorfix else 'getmoreram-serverfix-' if serverfix else 'getmoreram-loginfix-' if loginfix else 'getmoreram-extended-') + os.environ['GITHUB_RUN_ID']
    ipa = base/('GetMoreRamExtended-ios18-gsa-1.0.5-unsigned.ipa' if gsafix else 'GetMoreRamExtended-ios18-twofactor-unsigned.ipa' if twofactorfix else 'GetMoreRamExtended-ios18-serverfix-unsigned.ipa' if serverfix else 'GetMoreRamExtended-ios18-loginfix-unsigned.ipa' if loginfix else 'GetMoreRamExtended-ios18-unsigned.ipa')
    gh('release', 'create', tag, '--repo', DATA_REPOSITORY, '--title', 'GetMoreRamExtended unsigned iOS 18 build', '--notes', 'Unsigned ARM64 helper, minimum iOS 18. Source provenance and offline checks are recorded in the verification report. No Apple credentials used. Device login and capability grants are not verified.', '--prerelease')
    gh('release', 'upload', tag, '--repo', DATA_REPOSITORY, ipa, ipa.with_suffix('.verification.json'), base/'build.log', base/'linked-libraries.txt')
    print('Helper package and build evidence saved privately', flush=True)

if __name__ == '__main__':
    if sys.argv[1] == 'publish': publish(sys.argv[2])
    else: main(sys.argv[1])

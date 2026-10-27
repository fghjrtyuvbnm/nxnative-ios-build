"""Behavioral RED on the stock launcher, then GREEN on the external-data UI."""
import json
import os
import pathlib
import shutil
import subprocess
import sys

def run(repo,work):
    repo=pathlib.Path(repo).resolve();work=pathlib.Path(work).resolve();work.mkdir(parents=True,exist_ok=True)
    kit=pathlib.Path(__file__).resolve().parents[1]
    devices=json.loads(subprocess.check_output(['xcrun','simctl','list','devices','available','--json']))['devices']
    candidates=[d for runtime,ds in devices.items() if 'iOS-26' in runtime for d in ds if d.get('isAvailable') and 'iPhone' in d['name']]
    if not candidates:raise RuntimeError('No iOS 26 simulator runtime is installed; this is an environment failure, not behavioral RED')
    device=candidates[0]['udid']
    subprocess.run(['xcrun','simctl','boot',device],check=False,capture_output=True)
    subprocess.run(['xcrun','simctl','bootstatus',device,'-b'],check=True,timeout=180)
    for mode in (('external',) if os.environ.get('UI_EXTERNAL_ONLY')=='1' else ('stock','external')):
        project=work/mode;src=project/'Sources';tests=project/'Tests';src.mkdir(parents=True);tests.mkdir()
        if mode=='external':
            from apply_runtime import apply
            apply(repo)
        for name in ('Launcher.swift','LauncherSettings.swift')+ (('GameDataCore.swift','ExternalGameData.swift') if mode=='external' else ()):
            shutil.copyfile(repo/'dm/ios/Sources'/name,src/name)
        shutil.copyfile(kit/'runtime/ui/Harness.swift',src/'Harness.swift')
        shutil.copyfile(kit/'runtime/ui/FolderUITests.swift',tests/'FolderUITests.swift')
        config='''name: FolderHarness
options:
  deploymentTarget:
    iOS: "26.0"
targets:
  FolderHarness:
    type: application
    platform: iOS
    sources: [Sources]
    info:
      path: Info.plist
      properties:
        CFBundleDisplayName: FFR Folder Test
        UILaunchStoryboardName: ""
        UISupportedInterfaceOrientations: [UIInterfaceOrientationLandscapeLeft, UIInterfaceOrientationLandscapeRight]
        UIFileSharingEnabled: true
        LSSupportsOpeningDocumentsInPlace: true
        DMExternalGameData: true
        DMExternalRomFSMarker: FFRS/Content/Paks/FFRS-Switch.ucas
        DMExternalDataIdentity:
          title_id: 0100B8A026F14000
          main_build: b7f965b9d7227db8e29f04e84ea7331b
          shader_chain: test
          shader_inputs: input
    settings:
      PRODUCT_BUNDLE_IDENTIFIER: org.nxnative.folderharness
      PRODUCT_NAME: FolderHarness
      SWIFT_VERSION: "5.0"
      CODE_SIGNING_ALLOWED: NO
      GENERATE_INFOPLIST_FILE: NO
  FolderTests:
    type: bundle.ui-testing
    platform: iOS
    sources: [Tests]
    dependencies:
      - target: FolderHarness
    settings:
      PRODUCT_BUNDLE_IDENTIFIER: org.nxnative.folderharness.tests
      SWIFT_VERSION: "5.0"
      GENERATE_INFOPLIST_FILE: YES
      CODE_SIGNING_ALLOWED: NO
schemes:
  FolderHarness:
    build:
      targets:
        FolderHarness: all
        FolderTests: [test]
    test:
      targets: [FolderTests]
'''
        (project/'project.yml').write_text(config,encoding='utf-8')
        subprocess.run(['xcodegen','generate','--spec',project/'project.yml'],cwd=project,check=True)
        log=work/(mode+'.log')
        print('Begin production launcher UI test: '+mode,flush=True)
        try:
            with log.open('w') as f:
                p=subprocess.run(['xcodebuild','-project',project/'FolderHarness.xcodeproj','-scheme','FolderHarness','-destination','id='+device,
                    '-parallel-testing-enabled','NO','-maximum-concurrent-test-simulator-destinations','1',
                    '-test-timeouts-enabled','YES','-default-test-execution-time-allowance','60','-maximum-test-execution-time-allowance','120',
                    '-derivedDataPath',project/'dd','-resultBundlePath',work/(mode+'.xcresult'),'CODE_SIGNING_ALLOWED=NO','test'],stdout=f,stderr=subprocess.STDOUT,timeout=420)
        except subprocess.TimeoutExpired:
            print('\n'.join(log.read_text(errors='replace').splitlines()[-120:]),flush=True)
            raise RuntimeError('iOS simulator test timed out; no behavioral pass is claimed')
        text=log.read_text(errors='replace')
        if mode=='stock':
            if p.returncode==0 or 'XCTAssertTrue failed - EXTERNAL_FOLDER_PICKER_MISSING' not in text:
                raise RuntimeError('Stock UI did not fail at the expected behavioral assertion; inspect stock.log')
            print('RED verified: stock launcher has no external-folder picker',flush=True)
        elif p.returncode:raise RuntimeError('External folder UI test failed; inspect external.log')
        else:print('GREEN verified: folder picker opens, cancellation retains launcher and Play stays disabled without data',flush=True)
    shot=subprocess.run(['xcrun','simctl','io',device,'screenshot',work/'external-launcher.png'],capture_output=True,text=True,timeout=90)
    if shot.returncode:print('Optional final screenshot unavailable; the successful XCTest assertions and their screenshot attachment remain in external.xcresult',flush=True)

if __name__=='__main__':run(*sys.argv[1:])

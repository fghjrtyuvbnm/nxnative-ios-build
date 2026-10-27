"""Compile on macOS; leave the large final RomFS packaging to Windows."""
import importlib.util
import os
import pathlib
import subprocess
import sys
import json
import plistlib
from contracts import TITLE, BUILD, sha256
from transfer import split_file

def main(repo,work,mode='full'):
    repo=pathlib.Path(repo).resolve();work=pathlib.Path(work).resolve()
    manifest=json.loads((work/'input-manifest.json').read_text())
    if manifest.get('input_kind')!='shader-only':raise ValueError('This workflow expects the verified Windows shader-only input')
    sys.path.insert(0,str(repo/'dm/games'));import game
    spec=importlib.util.spec_from_file_location('nsp_build',repo/'scripts/build_ipa_from_nsp.py')
    b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
    g=game.load(TITLE);logs=work/'logs';logs.mkdir(parents=True,exist_ok=True)
    ex=work/'extract/v1';patched=work/'patched_v1'
    env=dict(os.environ,DM_GAME=TITLE,GAME=TITLE,DM_ROOT=str(work),WORK=str(work/'tmp'),J='3',PYTHONUTF8='1')
    b.configure_dotnet(env)
    os.environ.update(DM_GAME=TITLE,GAME=TITLE)
    b.PROG.mode='lines';b.PROG.plan(6)
    xlate=repo/'dm/gfx/tools/dmsh_xlate_bin/dmsh_xlate'
    b.check_prereqs(env,xlate)
    if b.build_mismatch(ex,'v1',g): raise ValueError('Unregistered modules')
    # Rewriting was done on Windows. Recheck source provenance before using it.
    if BUILD not in (patched/'main.fixups.tsv').read_text(): raise ValueError('Wrong rewritten build')
    for m in g.words('modules'):
        if not (patched/f'{m}.patched.bin').is_file(): raise ValueError('Missing rewritten module')
    b.chain_header(sys.executable,repo,env,logs)
    sh=work/'shader'
    if mode=='prepared':
        pkey=b.package_key(sh/'pkg')
    elif mode=='full':
        b.decode_ue_shaders(repo,{'v1':ex},'v1',patched,work,env,logs,g)
        pkey=b.split_shaders(sys.executable,repo,[ex/'RomFS'],[ex/'ExeFS/main'],sh/'pkg',env,logs,g,dlc_roms=list((work/'aoc').glob('*')))
    else:raise ValueError('Unknown build mode')
    ios=b.build_shaders(sys.executable,repo,sh,xlate,env,logs,g,pkey)
    results=json.loads((sh/'cache'/('b-'+b.chain_of(repo))/'_b_build.json').read_text())
    failed=[r for r in results if r['st']!='ok']
    if len(results)!=73496 or len(failed)>11:raise ValueError(f'Unexpected shader build results: {len(results)} total, {len(failed)} failed')
    ie=dict(env,W=str(work/'ipa'),PATCHED=str(patched),ROMFS=str(ex/'RomFS'),MSL_IOS=str(ios),GFXAPI='nvn',FONT_PY=sys.executable,
        DM_DISPLAY_NAME='FINAL FANTASY RESONANCE',DM_BUNDLE_ID='org.nxnative.'+TITLE.lower(),DM_APP_VERSION='1.0.1',
        AOC=str(work/'aoc'),DM_XCODE_DERIVED_DATA=str(work/'xcode-dd'),DM_LANG='zh-Hans',DM_SHOW_FPS='1',DM_PSO_GPUS='none',DM_ENTITLEMENTS='')
    if (ex/'icon.jpg').is_file():ie['DM_ICON']=str(ex/'icon.jpg')
    b.PROG.stage('Prepare unsigned Xcode project')
    b.run(['bash',repo/'dm/ios/tools/build_ipa.sh','--prepare-xcode'],logs/'prepare_xcode.log',env=ie)
    external=os.environ.get('EXTERNAL_LAUNCHER')=='1'
    if external:
        inputs=subprocess.check_output([sys.executable,repo/'dm/gfx/tools/dmsh_chain.py','--inputs'],env=env,text=True).strip()
        identity=dict(title_id=TITLE,main_build=BUILD,shader_chain=b.chain_of(repo),shader_inputs=inputs)
        plist=work/'ipa/xcode/Gen/Info.plist';info=plistlib.loads(plist.read_bytes())
        info.update(DMExternalGameData=True,DMExternalDataVersion=1,DMExternalDataIdentity=identity,
                    DMExternalRomFSMarker=g.get('romfs_marker'),LSSupportsOpeningDocumentsInPlace=True,UIFileSharingEnabled=True)
        plist.write_bytes(plistlib.dumps(info))
    b.PROG.stage('Compile unsigned iOS application')
    dd=work/'xcode-dd'
    project=work/'ipa/xcode/DmIOS.xcodeproj'
    scheme=f'FINAL FANTASY RESONANCE ({TITLE})'
    b.run(['xcodebuild','-project',project,'-scheme',scheme,'-configuration','Release',
        '-destination','generic/platform=iOS','-derivedDataPath',dd,'CODE_SIGNING_ALLOWED=NO','CODE_SIGNING_REQUIRED=NO',
        'CODE_SIGN_IDENTITY=','DM_COPY_GAME_RESOURCES=NO','DM_XCODE_OUTPUT_ROOT='+str(dd),
        'SYMROOT='+str(dd/'Build/Products'),'OBJROOT='+str(dd/'Build/Intermediates.noindex'),'build'],logs/'xcodebuild.log',env=ie)
    app=dd/'Build/Products/Release-iphoneos/DmIOS.app'
    out=work/'output';out.mkdir(exist_ok=True)
    template=out/'FFR-HK-unsigned-template.ipa';arc='Payload/DmIOS.app';chain=b.chain_of(repo)
    b.PROG.stage('Pack compiled template without local RomFS')
    cmd=[sys.executable,repo/'dm/ios/tools/pack_ipa.py',template,'--store',g.get('zip_store')]
    for name in ('_CodeSignature','embedded.mobileprovision','romfs','msl','aoc'):cmd+=['--skip',f'{arc}/{name}']
    cmd += [f'{arc}={app}',f'{arc}/msl/b-{chain}={ios}/b-{chain}',f'{arc}/aoc={work}/aoc']
    b.run(cmd,logs/'pack_template.log',env=ie)
    parts=split_file(template,out,'template')
    report={'title_id':TITLE,'main_build':BUILD,'template_sha256':sha256(template),'template_bytes':template.stat().st_size,
        'parts':parts,'romfs_packaging':'Required on Windows','signed':False,'runtime_tested':False,'shader_total':len(results),'shader_failed':failed}
    if external:report.update(external_data_runtime=True,external_data_identity=identity,romfs_packaging='Export separate data folder on Windows')
    (out/'result-manifest.json').write_text(json.dumps(report,indent=2))
    b.PROG.close()
    print('Unsigned template ready. Complete the IPA on Windows with the original extracted RomFS.',flush=True)

if __name__=='__main__':main(*sys.argv[1:])

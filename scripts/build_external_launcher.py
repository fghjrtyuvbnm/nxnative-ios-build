"""Reuse finished shader libraries and tables; compile only the external-folder launcher."""
import importlib.util
import json
import os
import pathlib
import plistlib
import shutil
import subprocess
import sys
import zipfile
from contracts import TITLE, BUILD, sha256
from external_pack import APP, check_archive_name, reconstruct
from transfer import split_file

def restore_tables(archive,dest,profile,chain,inputs):
    dest=pathlib.Path(dest);profile=pathlib.Path(profile)
    with zipfile.ZipFile(archive) as z:
        if z.testzip():raise ValueError('Source template CRC mismatch')
        for entry in z.infolist():
            check_archive_name(entry.filename)
            if (entry.external_attr>>16)&0o170000==0o120000:raise ValueError('Template symlink')
        stamp=f'msl/b-{chain}/inputs.tsv'
        lines=set(z.read(APP+stamp).decode().splitlines())
        if f'game\t{TITLE}' not in lines or f'inputs\t{inputs}' not in lines:raise ValueError('Cached shader identity differs')
        table=z.read(APP+'dm/c1_full.tsv')
        if not table.splitlines()[0].startswith(f'# chain b-{chain} inputs {inputs} '.encode()):raise ValueError('Cached c1 table differs')
        profile.mkdir(parents=True,exist_ok=True)
        for name in ('c1_full.tsv','cb_extent.tsv'):
            (profile/name).write_bytes(z.read(APP+'dm/'+name))
        libraries=0
        for entry in z.infolist():
            if entry.is_dir():continue
            relative=entry.filename.removeprefix(APP)
            if relative.startswith((f'msl/b-{chain}/','aoc/')):
                target=dest/relative;target.parent.mkdir(parents=True,exist_ok=True)
                with z.open(entry) as src,target.open('xb') as out:shutil.copyfileobj(src,out)
                libraries+=relative.endswith('_b.metallib')
        if not libraries:raise ValueError('No compiled iOS libraries')
    return dict(title_id=TITLE,main_build=BUILD,shader_chain=chain,shader_inputs=inputs)

def main(repo,work,download,source_run):
    repo=pathlib.Path(repo).resolve();work=pathlib.Path(work).resolve()
    archive,previous=reconstruct(download)
    if previous.get('shader_total')!=73496 or len(previous.get('shader_failed',[]))>11:raise ValueError('Source shader build was incomplete')
    from apply_runtime import apply
    apply(repo)
    sys.path.insert(0,str(repo/'dm/games'));import game
    g=game.load(TITLE)
    spec=importlib.util.spec_from_file_location('nsp_build',repo/'scripts/build_ipa_from_nsp.py')
    b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
    logs=work/'logs';logs.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ,DM_GAME=TITLE,GAME=TITLE,DM_ROOT=str(work),WORK=str(work/'tmp'),J='3',PYTHONUTF8='1')
    os.environ.update(DM_GAME=TITLE,GAME=TITLE);b.configure_dotnet(env)
    b.PROG.mode='lines';b.PROG.plan(4)
    b.chain_header(sys.executable,repo,env,logs)
    chain=b.chain_of(repo)
    inputs=subprocess.check_output([sys.executable,repo/'dm/gfx/tools/dmsh_chain.py','--inputs'],env=env,text=True).strip()
    resources=work/'reused';profile=repo/'dm/games'/TITLE
    identity=restore_tables(archive,resources,profile,chain,inputs)
    from cache_layout import verify_geometry
    geometry={fields[3]:'geometry' for line in g.table('shader_map.tsv').read_text().splitlines() if len(fields:=line.split('\t'))==5 and fields[2]=='geometry'}
    verify_geometry(geometry,None,resources/'msl'/('b-'+chain),chain)
    ex=work/'extract/v1';patched=work/'patched_v1'
    if b.build_mismatch(ex,'v1',g) or BUILD not in (patched/'main.fixups.tsv').read_text():raise ValueError('Unexpected rewritten modules')
    ie=dict(env,W=str(work/'ipa'),PATCHED=str(patched),ROMFS=str(ex/'RomFS'),MSL_IOS=str(resources/'msl'),GFXAPI='nvn',FONT_PY=sys.executable,
        DM_DISPLAY_NAME='FINAL FANTASY RESONANCE',DM_BUNDLE_ID='org.nxnative.'+TITLE.lower(),DM_APP_VERSION='1.0.1',
        AOC=str(resources/'aoc'),DM_XCODE_DERIVED_DATA=str(work/'xcode-dd'),DM_LANG='zh-Hans',DM_SHOW_FPS='1',DM_PSO_GPUS='none',DM_ENTITLEMENTS='')
    if (ex/'icon.jpg').is_file():ie['DM_ICON']=str(ex/'icon.jpg')
    b.PROG.stage('Prepare external-folder launcher with reused libraries')
    from private_io import progress
    progress(work,'preparing-xcode')
    b.run(['bash',repo/'dm/ios/tools/build_ipa.sh','--prepare-xcode'],logs/'prepare_xcode.log',env=ie)
    plist=work/'ipa/xcode/Gen/Info.plist'
    info=plistlib.loads(plist.read_bytes())
    info.update(DMExternalGameData=True,DMExternalDataVersion=1,DMExternalDataIdentity=identity,DMExternalRomFSMarker=g.get('romfs_marker'),
                LSSupportsOpeningDocumentsInPlace=True,UIFileSharingEnabled=True)
    plist.write_bytes(plistlib.dumps(info))
    b.PROG.stage('Compile unsigned external-folder launcher; no shader recompilation')
    progress(work,'compiling-app')
    dd=work/'xcode-dd'
    b.run(['xcodebuild','-project',work/'ipa/xcode/DmIOS.xcodeproj','-scheme',f'FINAL FANTASY RESONANCE ({TITLE})','-configuration','Release',
        '-destination','generic/platform=iOS','-derivedDataPath',dd,'CODE_SIGNING_ALLOWED=NO','CODE_SIGNING_REQUIRED=NO','CODE_SIGN_IDENTITY=',
        'DM_COPY_GAME_RESOURCES=NO','DM_XCODE_OUTPUT_ROOT='+str(dd),'SYMROOT='+str(dd/'Build/Products'),'OBJROOT='+str(dd/'Build/Intermediates.noindex'),'build'],logs/'xcodebuild.log',env=ie)
    out=work/'output';out.mkdir(exist_ok=True);template=out/'FFR-external-template.ipa'
    app=dd/'Build/Products/Release-iphoneos/DmIOS.app';arc=APP.rstrip('/')
    progress(work,'packing-template')
    cmd=[sys.executable,repo/'dm/ios/tools/pack_ipa.py',template,'--store',g.get('zip_store')]
    for name in ('_CodeSignature','embedded.mobileprovision','romfs','msl','aoc'):cmd+=['--skip',f'{arc}/{name}']
    cmd += [f'{arc}={app}',f'{arc}/msl/b-{chain}={resources}/msl/b-{chain}',f'{arc}/aoc={resources}/aoc']
    b.run(cmd,logs/'pack_template.log',env=ie)
    report=dict(previous,external_data_runtime=True,resource_only=False,geometry_validation='passed',external_data_identity=identity,source_shader_run=int(source_run),
                template_sha256=sha256(template),template_bytes=template.stat().st_size,parts=split_file(template,out,'template'),
                romfs_packaging='Export as separate data folder on Windows',signed=False,runtime_tested=False)
    (out/'result-manifest.json').write_text(json.dumps(report,indent=2))
    progress(work,'template-ready')
    b.PROG.close();print('External-folder launcher template ready; shaders reused unchanged.',flush=True)

if __name__=='__main__':main(*sys.argv[1:])

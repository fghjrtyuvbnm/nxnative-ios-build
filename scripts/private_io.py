"""Keep every data transfer in the fixed private repository, even from a public runner."""
import json
import os
import pathlib
import subprocess
import sys
import datetime

DATA_REPOSITORY='fghjrtyuvbnm/ffr-nxnative-private-build'
PROGRESS_STAGES={'downloading-caches','verifying-caches','cached-shader-pass','saving-shader-resources','preparing-xcode','compiling-app','packing-template','template-ready'}

def progress(work,stage,current=0,total=0):
    if stage not in PROGRESS_STAGES:raise ValueError('Unknown build progress stage')
    run=os.environ['GITHUB_RUN_ID']
    if not run.isdigit():raise ValueError('Invalid execution run')
    path=pathlib.Path(work)/('build-progress-'+run+'.json')
    value={'run':int(run),'stage':stage,'current':current,'total':total,'updated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value));tmp.replace(path)
    p=gh('release','upload','progress-'+data_run(),'--repo',DATA_REPOSITORY,'--clobber',path,check=False)
    if p.returncode:print('Private progress upload deferred; build continues',flush=True)

def shader_live(work):
    work=pathlib.Path(work);run=os.environ['GITHUB_RUN_ID']
    report=json.loads((work/'shard-merge-verification.json').read_text())
    value={'run':int(run),'base_libraries_ready':sum(1 for _ in (work/'shader/ios').glob('b-*/*_b.metallib')),
           'expected_libraries':report['keys']-len(report.get('geometry_pending_full_pass',[])),
           'updated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    path=work/('shader-live-'+run+'.json');path.write_text(json.dumps(value))
    gh('release','upload','progress-'+data_run(),'--repo',DATA_REPOSITORY,'--clobber',path,check=False)

def data_repository():return DATA_REPOSITORY

def checkpoint_manifest(tag,kind,optional=False):
    from contracts import SOURCE,check_identity
    p=gh('release','download',tag,'--repo',DATA_REPOSITORY,'--pattern','bundle-manifest.json','--output','-',check=False)
    if p.returncode:
        if optional and ('not found' in p.stderr.lower() or '404' in p.stderr):return None
        raise RuntimeError('Cannot inspect private checkpoint manifest')
    m=json.loads(p.stdout);check_identity(m)
    if m.get('source')!=SOURCE or m.get('kind')!=kind:raise ValueError('Checkpoint source or kind differs')
    return m

def cache_plan():
    identity=checkpoint_manifest('prepared-'+data_run(),'prepared')['metadata']['identity']
    missing=[]
    for index in range(16):
        m=checkpoint_manifest(f'cache-{data_run()}-{index:02}','cache',optional=True)
        if m is None or not m['metadata'].get('complete'):missing.append(index);continue
        meta=m['metadata']
        if meta['identity']!=identity or meta['index']!=index or meta['count']!=16 or not m.get('files') or not m.get('parts'):raise ValueError('Completed checkpoint metadata differs')
    return missing

def data_run():
    value=os.environ.get('DATA_BUILD_ID',os.environ.get('GITHUB_RUN_ID',''))
    if not value.isdigit():raise ValueError('Data build ID must be numeric')
    return value

def gh(*args,check=True):
    args=list(map(str,args))
    if '--repo' in args and args[args.index('--repo')+1]!=DATA_REPOSITORY:raise ValueError('Data transfer cannot target a public repository')
    if args and args[0]=='api' and not args[1].startswith('repos/'+DATA_REPOSITORY):raise ValueError('Unexpected data API target')
    env=dict(os.environ)
    if env.get('PRIVATE_DATA_TOKEN'):env['GH_TOKEN']=env['PRIVATE_DATA_TOKEN']
    elif env.get('GITHUB_REPOSITORY') not in (None,DATA_REPOSITORY):raise ValueError('Set PRIVATE_DATA_TOKEN for the fixed private data repository')
    p=subprocess.run(['gh',*args],env=env,text=True,capture_output=True)
    if check and p.returncode:raise RuntimeError('Private data API failed; inspect private diagnostics')
    return p

def assert_private():
    info=json.loads(gh('api','repos/'+DATA_REPOSITORY).stdout)
    if info.get('private') is not True:raise ValueError('Data repository must remain private')

def download_input(work):
    from transfer import restore
    work=pathlib.Path(work);download=work.parent/'input-download';download.mkdir(parents=True,exist_ok=True)
    gh('release','download','windows-input-v1','--repo',DATA_REPOSITORY,'--dir',download,'--pattern','input.part*','--pattern','input-manifest.json')
    restore(download,work)

def publish_template(work):
    work=pathlib.Path(work);tag='unsigned-template-'+os.environ['GITHUB_RUN_ID']
    gh('release','create',tag,'--repo',DATA_REPOSITORY,'--title','Unsigned external-folder launcher template','--notes','Private output; no physical USB or gameplay validation.','--prerelease')
    gh('release','upload',tag,'--repo',DATA_REPOSITORY,*sorted((work/'output').glob('template.part*')),work/'output/result-manifest.json')
    if (work/'shard-merge-verification.json').is_file():gh('release','upload',tag,'--repo',DATA_REPOSITORY,work/'shard-merge-verification.json')

def publish_resources(work):
    work=pathlib.Path(work);tag='compiled-resources-'+os.environ['GITHUB_RUN_ID'];out=work/'compiled-resources'
    gh('release','create',tag,'--repo',DATA_REPOSITORY,'--title','Compiled resources checkpoint (not an application)','--notes','Private resources and real upstream shader tables; reuse for launcher-only builds.','--prerelease')
    gh('release','upload',tag,'--repo',DATA_REPOSITORY,*sorted(out.glob('template.part*')),out/'result-manifest.json',out/'geometry-descriptors.json')

def publish_ios18(work):
    from contracts import sha256
    from external_pack import resource_name
    import zipfile
    assert_private();out=pathlib.Path(work)/'output';m=json.loads((out/'result-manifest.json').read_text())
    if m.get('minimum_ios')!='18.0' or m.get('strong_metal4_imports')!=0 or m.get('weak_metal4_imports')!=0 or m.get('data_resources_embedded') is not False:raise ValueError('iOS 18 native validation is incomplete')
    source=out/'FFR-external-template.ipa'
    if sha256(source)!=m['template_sha256']:raise ValueError('Final IPA changed after verification')
    with zipfile.ZipFile(source) as z:
        if z.testzip() or any(resource_name(name) is not None for name in z.namelist()):raise ValueError('Final launcher CRC or resource split failed')
    filename='FINAL-FANTASY-RESONANCE-HK-1.0.1-ios18-packed-unsigned.ipa' if m.get('shader_pack_version')==1 else 'FINAL-FANTASY-RESONANCE-HK-1.0.1-ios18-unsigned.ipa'
    if m.get('memory_diagnostics'):filename='FINAL-FANTASY-RESONANCE-HK-1.0.1-ios18-memory-diagnostic-unsigned.ipa'
    ipa=out/filename;source.rename(ipa)
    report={k:v for k,v in m.items() if k not in ('parts','resource_only')}
    report.update(launcher_sha256=m['template_sha256'],launcher_bytes=ipa.stat().st_size,zip_crc_verified=True,data_separate=True,physical_usb_runtime_tested=False,gameplay_tested=False)
    check=ipa.with_suffix('.verification.json');check.write_text(json.dumps(report,indent=2))
    tag='ios18-launcher-'+os.environ['GITHUB_RUN_ID']
    gh('release','create',tag,'--repo',DATA_REPOSITORY,'--title','Unsigned iOS 18 launcher for iPad mini 7','--notes','Private iOS 18 ARM64 Metal 3 launcher. Reuses the original complete external FFRS-Data directory. Device gameplay and physical USB access remain unverified.','--prerelease')
    gh('release','upload',tag,'--repo',DATA_REPOSITORY,ipa,check)
    if m.get('memory_diagnostics'):
        request=pathlib.Path(__file__).resolve().parents[1]/'runtime/MemoryRequirements.entitlements'
        gh('release','upload',tag,'--repo',DATA_REPOSITORY,request)

def download_resources(work,source_run):
    if not str(source_run).isdigit():raise ValueError('Resource run must be numeric')
    dest=pathlib.Path(work)/'resource-download';dest.mkdir()
    gh('release','download','compiled-resources-'+str(source_run),'--repo',DATA_REPOSITORY,'--dir',dest,'--pattern','template.part*','--pattern','result-manifest.json')
    return dest

def save_logs(work):
    import tarfile
    work=pathlib.Path(work)
    if not (work/'logs').exists():return
    archive=work.parent/('diagnostics-'+work.name+'.tar.gz')
    with tarfile.open(archive,'w:gz') as t:t.add(work/'logs',arcname='logs')
    tag='public-diagnostics-'+os.environ['GITHUB_RUN_ID']+'-'+work.name+'-'+os.environ.get('GITHUB_RUN_ATTEMPT','1')
    gh('release','create',tag,'--repo',DATA_REPOSITORY,'--title','Private build diagnostics','--notes','Raw logs retained privately.','--prerelease')
    gh('release','upload',tag,'--repo',DATA_REPOSITORY,archive)

if __name__=='__main__':
    assert_private()
    if sys.argv[1]=='check':print('Private data repository and credential verified')
    elif sys.argv[1]=='plan':
        planned=json.dumps(cache_plan(),separators=(',',':'))
        with open(os.environ['GITHUB_OUTPUT'],'a') as out:out.write('shards='+planned+'\n')
        print('Missing shader partitions: '+planned)
    elif sys.argv[1]=='input':download_input(sys.argv[2])
    elif sys.argv[1]=='publish':publish_template(sys.argv[2])
    elif sys.argv[1]=='logs':save_logs(sys.argv[2])
    else:raise ValueError('Unknown private data operation')

"""Checkpointed partial builds; the final pass is still the upstream full build."""
import collections
import hashlib
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
import shards
from contracts import TITLE, SOURCE, sha256
from private_io import gh, data_repository, data_run

COUNT=16


def release_exists(tag):
    p=gh('release','view',tag,'--repo',data_repository(),check=False)
    if p.returncode and 'not found' not in p.stderr.lower() and '404' not in p.stderr:raise RuntimeError(p.stderr)
    return not p.returncode

def ensure_release(tag,title):
    if not release_exists(tag):gh('release','create',tag,'--repo',data_repository(),'--title',title,'--notes','Private, hash-checked build checkpoint. No keys or original NSPs.','--prerelease')

def upload_bundle(tag,out):
    ensure_release(tag,'Private shader build checkpoint')
    paths=[out/'bundle-manifest.json',*sorted(out.glob('bundle.part*'))]
    gh('release','upload',tag,'--repo',data_repository(),'--clobber',*paths)

def download_bundle(tag,dest):
    dest.mkdir(parents=True,exist_ok=True)
    gh('release','download',tag,'--repo',data_repository(),'--dir',dest,'--pattern','bundle-manifest.json','--pattern','bundle.part*')

def load(repo,work):
    repo=pathlib.Path(repo).resolve();work=pathlib.Path(work).resolve()
    os.environ.update(DM_GAME=TITLE,GAME=TITLE)
    sys.path.insert(0,str(repo/'dm/games'));import game
    spec=importlib.util.spec_from_file_location('nsp_pipeline',repo/'scripts/build_ipa_from_nsp.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
    env=dict(os.environ,DM_GAME=TITLE,GAME=TITLE,DM_ROOT=str(work),WORK=str(work/'tmp'),J='3',PYTHONUTF8='1')
    b.configure_dotnet(env);(work/'tmp').mkdir(parents=True,exist_ok=True);(work/'logs').mkdir(parents=True,exist_ok=True)
    b.PROG.mode='lines';b.PROG.plan(3)
    g=game.load(TITLE);b.chain_header(sys.executable,repo,env,work/'logs')
    return repo,work,b,g,env

def identity(repo,work,b,g):
    sys.path.insert(0,str(repo/'dm/gfx/tools'));import dmsh_chain,dmsh_mtlcache
    cross=subprocess.run(['spirv-cross','--version'],capture_output=True,text=True)
    pso=work/'shader/pso_pairs.tsv'
    return {'source':SOURCE,'chain':b.chain_of(repo),'inputs':dmsh_chain.inputs(g),'package':b.package_key(work/'shader/pkg'),
            'pso_pairs':sha256(pso) if pso.is_file() else None,'metal_mac':dmsh_mtlcache.compiler_id('macosx'),
            'metal_ios':dmsh_mtlcache.compiler_id('iphoneos'),'spirv_cross':cross.stdout+cross.stderr}

def key_map(g,work):
    keys={};pairs=collections.defaultdict(set)
    for line in g.table('shader_map.tsv').read_text().splitlines():
        if line and not line.startswith('#'):
            fields=line.split('\t')
            if fields==['package','index','stage','dm_ctl_sha16','source']:continue
            if len(fields)!=5 or not re.fullmatch('[0-9a-f]{16}',fields[3]):raise ValueError('Malformed shader map row')
            keys[fields[3]]=fields[2]
    for path in (g.table('shader_pairs.tsv'),g.table('pso_pairs.tsv') if g.table('pso_pairs.tsv').is_file() else work/'shader/pso_pairs.tsv'):
        if path.is_file():
            for line in path.read_text().splitlines():
                if line and not line.startswith('#'):
                    v,p=line.split();pairs[v].add(p)
    if len(keys)!=73496:raise ValueError('Unexpected shader key count')
    return keys,pairs

def prepare(repo,work):
    repo,work,b,g,env=load(repo,work);ex=work/'extract/v1';logs=work/'logs';patched=work/'patched_v1'
    if b.build_mismatch(ex,'v1',g):raise ValueError('Wrong modules')
    b.decode_ue_shaders(repo,{'v1':ex},'v1',patched,work,env,logs,g)
    b.split_shaders(sys.executable,repo,[ex/'RomFS'],[ex/'ExeFS/main'],work/'shader/pkg',env,logs,g,dlc_roms=list((work/'aoc').glob('*')))
    meta={'identity':identity(repo,work,b,g),'count':COUNT,'keys':len(key_map(g,work)[0])}
    out=work/'prepared-transfer';shards.pack(work,['shader/pkg','shader/pso_pairs.tsv'],out,'prepared',meta)
    run=data_run();upload_bundle('prepared-'+run,out);ensure_release('progress-'+run,'Private shader compilation progress')
    b.PROG.close();print('Prepared the shader package once for all shards',flush=True)

def restore_prepared(repo,work,label='input'):
    repo,work,b,g,env=load(repo,work);run=data_run()
    download=work/('prepared-download-'+label);download_bundle('prepared-'+run,download)
    meta=shards.restore(download,work,'prepared')['metadata']
    if meta['identity']!=identity(repo,work,b,g):raise ValueError('Shader toolchain or input fingerprint mismatch')
    return repo,work,b,g,env,meta

def compile_subset(repo,work,b,g,env,keys,logname,progress_index=None):
    env=dict(env,IOSOUT=str(work/'shader/ios'),XLATE=str(repo/'dm/gfx/tools/dmsh_xlate_bin/dmsh_xlate'))
    log=work/'logs'/logname;cmd=[sys.executable,repo/'dm/gfx/tools/own_compilers.py',work/'shader/pkg',work/'shader/cache',*sorted(keys)]
    start=time.monotonic();last=-1000
    with log.open('w',encoding='utf-8') as f:
        p=subprocess.Popen(list(map(str,cmd)),env=env,stdout=f,stderr=subprocess.STDOUT)
        while p.poll() is None:
            elapsed=time.monotonic()-start
            cached=sum(1 for path in (work/'shader/cache/cas/index').glob('*.json') if path.stem in keys)
            print(f'Shard {progress_index}: {cached}/{len(keys)} fully cached; elapsed {elapsed:.0f}s',flush=True)
            if progress_index is not None and elapsed-last>=120:
                path=work/f'progress-{progress_index:02}.json'
                path.write_text(json.dumps({'index':progress_index,'requested':len(keys),'cached':cached,'elapsed_seconds':round(elapsed),'status':'compiling'}))
                result=gh('release','upload','progress-'+data_run(),'--repo',data_repository(),'--clobber',path,check=False)
                if result.returncode:print('Progress upload warning: '+result.stderr[-200:],flush=True)
                last=elapsed
            if elapsed>95*60:
                p.terminate();p.wait(timeout=30);raise TimeoutError('Shader shard exceeded its 95 minute limit; completed cache will be saved')
            time.sleep(30)
        if p.returncode:raise RuntimeError(f'Shader subset failed ({p.returncode}); see {log}')
    records=json.loads((work/'shader/cache'/('b-'+b.chain_of(repo))/'_b_build.json').read_text())
    if {r['key'] for r in records}!=set(keys):raise ValueError('Partial build did not report every requested shader')
    return records

def library_hashes(work):
    out={}
    for prefix in ('shader/cache','shader/ios'):
        for p in (work/prefix).glob('b-*/*.metallib'):out[p.relative_to(work).as_posix()]=sha256(p)
    return out

def probe(repo,work):
    repo,work,b,g,env,meta=restore_prepared(repo,work)
    keys,pairs=key_map(g,work)
    wanted=set(sorted(k for k,v in keys.items() if v=='vertex')[:2])|{'7fca874daf10dddd','c254eaa40e0c4f1e'}
    wanted=shards.close_dependencies(wanted,pairs,set(keys))
    records=compile_subset(repo,work,b,g,env,wanted,'probe-cold.log')
    if any(r['st']!='ok' for r in records):raise ValueError('Representative shader probe did not compile')
    cold=library_hashes(work)
    other=work.parent/'probe-independent';other_ctx=restore_prepared(repo,other,'independent')
    compile_subset(*other_ctx[:5],wanted,'probe-independent.log')
    if library_hashes(other)!=cold:raise ValueError('Metal output differs between independent paths; cannot safely merge shard caches')
    bundle=work/'probe-cache';shards.pack(work,['shader/cache/cas'],bundle,'cache',meta)
    warm=work.parent/'probe-restored';warm_ctx=restore_prepared(repo,warm,'restored');shards.restore(bundle,warm,'cache')
    compile_subset(*warm_ctx[:5],wanted,'probe-restored.log')
    text=(warm/'logs/probe-restored.log').read_text()
    if f'shader cache: hit {len(wanted)}, rebuilt 0' not in text or library_hashes(warm)!=cold:raise ValueError('Restored shader cache did not reproduce the cold build')
    (work/'probe-verification.json').write_text(json.dumps({'shaders':len(wanted),'libraries':len(cold),'library_hashes':cold,'independent_cold_paths_identical':True,'cache_roundtrip_identical':True,'identity':meta['identity']},indent=2))
    tag='probe-'+data_run();ensure_release(tag,'Shader cache equivalence probe passed')
    gh('release','upload',tag,'--repo',data_repository(),'--clobber',work/'probe-verification.json')
    print('Independent cold builds and restored-cache build have identical Metal libraries',flush=True)

def shard(repo,work,index):
    index=int(index)
    if not 0<=index<COUNT:raise ValueError('Invalid shader shard')
    repo,work,b,g,env,prepared=restore_prepared(repo,work)
    keys,pairs=key_map(g,work);base=set(shards.partition(list(keys),COUNT)[index]);wanted=shards.close_dependencies(base,pairs,set(keys))
    tag=f'cache-{data_run()}-{index:02}'
    if release_exists(tag):
        saved=work/'previous-cache';download_bundle(tag,saved)
        prior=shards.restore(saved,work,'cache')['metadata']
        if prior['identity']!=prepared['identity']:raise ValueError('Previous shard cache has different inputs')
        if prior.get('complete'):
            if prior['index']!=index or prior['count']!=COUNT or prior['base_keys']!=sorted(base) or prior['requested_keys']!=sorted(wanted):raise ValueError('Previous shard coverage differs')
            print(f'Shard {index}: verified completed private cache reused; no recompilation',flush=True)
            return
    meta={'identity':prepared['identity'],'index':index,'count':COUNT,'base_keys':sorted(base),'requested_keys':sorted(wanted),'complete':False}
    try:
        records=compile_subset(repo,work,b,g,env,wanted,f'shard-{index:02}.log',index)
        meta.update(complete=True,results=records)
    finally:
        out=work/'cache-transfer';shards.pack(work,['shader/cache/cas'],out,'cache',meta);upload_bundle(tag,out)
    print(f'Shard {index}: {len(base)} assigned keys completed and checkpointed',flush=True)

def assemble(repo,work):
    repo,work,b,g,env,prepared=restore_prepared(repo,work)
    keys,pairs=key_map(g,work);expected=shards.partition(list(keys),COUNT);seen=set();failed={}
    for index in range(COUNT):
        download=work/f'cache-download-{index:02}';download_bundle(f'cache-{data_run()}-{index:02}',download)
        meta=shards.restore(download,work,'cache')['metadata']
        if meta['identity']!=prepared['identity'] or not meta['complete'] or meta['index']!=index or meta['count']!=COUNT or meta['base_keys']!=expected[index]:raise ValueError('Incomplete or incompatible shader shard')
        if seen & set(meta['base_keys']):raise ValueError('Overlapping base shader partitions')
        seen.update(meta['base_keys'])
        for r in meta['results']:
            if r['st']!='ok':failed[r['key']]=r
    if seen!=set(keys) or len(failed)>11:raise ValueError(f'Incomplete shader coverage or unexpected failures: {len(failed)}')
    cas=work/'shader/cache/cas';code_fps=set()
    for key in set(keys)-set(failed):
        index=json.loads((cas/'index'/f'{key}.json').read_text());digest=index['digest']
        if not re.fullmatch('[0-9a-f]{64}',digest):raise ValueError('Unsafe shader cache digest')
        code_fps.add(index['code_fp']);directory=cas/'shader'/digest
        for name in ('mac/'+key+'_b.metal','mac/'+key+'_b.json','mac/'+key+'_b.metallib','ios/'+key+'_b.json','ios/'+key+'_b.metallib'):
            if not (directory/name).is_file():raise ValueError('Incomplete successful shader cache entry')
    if len(code_fps)!=1:raise ValueError('Shard cache source fingerprints differ')
    (work/'shard-merge-verification.json').write_text(json.dumps({'keys':len(seen),'shards':COUNT,'failed':list(failed.values()),'identity':prepared['identity']},indent=2))
    # Upstream's full pass verifies/reuses each shader cache entry and writes the real stamp and c1 tables.
    import cloud_build
    if os.environ.get('EXTERNAL_LAUNCHER')=='1':
        from apply_runtime import apply
        apply(repo)
    cloud_build.main(repo,work,'prepared')

if __name__=='__main__':
    mode,repo,work,*args=sys.argv[1:]
    {'prepare':prepare,'probe':probe,'shard':shard,'assemble':assemble}[mode](repo,work,*args)

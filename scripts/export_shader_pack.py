"""Export an independent packed data directory; never modify the source directory."""
import hashlib,json,pathlib,shutil,sys,time
from shader_pack import pack,Reader
from contracts import sha256
from external_pack import safe_data_path

def export(source,target):
    source=pathlib.Path(source).resolve();target=pathlib.Path(target).resolve()
    if target.exists() or target==source or source in target.parents:raise ValueError('Choose a new independent output directory')
    stage=target.with_name(target.name+'.preparing')
    if stage.exists():raise FileExistsError(stage)
    original=json.loads((source/'game-data.json').read_text());chain='msl/b-'+original['identity']['shader_chain']
    stage.mkdir();packed=stage/chain;packed.parent.mkdir(parents=True)
    print('Packing shader files; original data remain unchanged',flush=True)
    entries=pack(source/chain,packed)
    expected={pathlib.PurePosixPath(r['path']).name:r for r in original['files'] if r['path'].startswith(chain+'/') and pathlib.PurePosixPath(r['path']).suffix in ('.json','.metallib')}
    if set(entries)!=set(expected):raise ValueError('Source shader manifest coverage differs')
    reader=Reader(packed)
    try:
        for i,(name,row) in enumerate(expected.items(),1):
            data=reader.read(name)
            if len(data)!=row['size'] or hashlib.sha256(data).hexdigest()!=row['sha256']:raise ValueError('Packed data differ from original manifest')
            if i%10000==0:print(f'Verified {i}/{len(expected)} shader entries',flush=True)
    finally:reader.close()
    files=[]
    for r in original['files']:
        name=r['path'];safe_data_path(name)
        if name.startswith(chain+'/') and pathlib.PurePosixPath(name).name in entries:continue
        src=source/name;dst=stage/name
        if src.is_symlink() or not src.resolve().is_relative_to(source):raise ValueError('Invalid source path')
        dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
        if dst.stat().st_size!=r['size'] or sha256(dst)!=r['sha256']:raise ValueError('Copied data mismatch')
        files.append(r)
    for name in ('shaders.pack','shaders.index.json'):
        p=packed/name;files.append(dict(path=chain+'/'+name,size=p.stat().st_size,sha256=sha256(p)))
    manifest=dict(format_version=1,identity=original['identity'],files=sorted(files,key=lambda r:r['path']),shader_storage='pack-v1')
    (stage/'game-data.json').write_text(json.dumps(manifest,separators=(',',':')))
    report=dict(shader_entries=len(entries),data_files=len(files),original_files=len(original['files']),original_bytes=sum(r['size'] for r in original['files']),packed_bytes=sum(r['size'] for r in files),all_entry_sha256_verified=True,all_other_file_sha256_verified=True,original_preserved=True)
    stage.rename(target)
    target.with_suffix('.verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)

if __name__=='__main__':export(*sys.argv[1:])

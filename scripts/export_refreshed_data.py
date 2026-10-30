"""Export regenerated shader resources into a new independent data directory on Windows."""
import hashlib,json,pathlib,shutil,stat,sys,zipfile
from contracts import sha256
from external_pack import APP,check_archive_name,safe_data_path
from shader_pack import valid_name,Reader

def export(archive,source,target):
    source=pathlib.Path(source).resolve();target=pathlib.Path(target).resolve()
    if target==source or source in target.parents or target.exists():raise ValueError('Choose a new independent data directory')
    stage=target.with_name(target.name+'.preparing')
    if stage.exists():raise FileExistsError(stage)
    old=json.loads((source/'game-data.json').read_text());identity=dict(old['identity'])
    with zipfile.ZipFile(archive) as z:
        names=set()
        for item in z.infolist():
            check_archive_name(item.filename)
            if item.filename.casefold() in names or stat.S_ISLNK(item.external_attr>>16) or item.flag_bits&1:raise ValueError('Duplicate, encrypted or linked resource')
            names.add(item.filename.casefold())
            if item.filename.startswith(APP+'romfs/'):raise ValueError('Resource archive must not carry partial RomFS')
        stamps=[n for n in z.namelist() if n.startswith(APP+'msl/b-') and n.endswith('/inputs.tsv')]
        if len(stamps)!=1:raise ValueError('Exactly one shader identity stamp required')
        prefix=stamps[0].removeprefix(APP).removesuffix('inputs.tsv')
        stamp=dict(line.split('\t',1) for line in z.read(stamps[0]).decode().splitlines() if line and not line.startswith('#'))
        if stamp.get('game')!=identity['title_id'] or not stamp.get('inputs'):raise ValueError('Wrong resource game identity')
        if stamp['inputs']==identity['shader_inputs']:raise ValueError('Resources were not regenerated for new profile inputs')
        identity.update(shader_chain=prefix.split('/')[1][2:],shader_inputs=stamp['inputs'])
        c1=z.read(APP+'dm/c1_full.tsv').splitlines()[0]
        if not c1.startswith(f"# chain b-{identity['shader_chain']} inputs {identity['shader_inputs']} ".encode()):raise ValueError('Generated c1 table and resource stamp differ')
        entries=[i for i in z.infolist() if not i.is_dir() and i.filename.startswith(APP+prefix) and pathlib.PurePosixPath(i.filename).suffix in ('.json','.metallib')]
        entries.sort(key=lambda i:pathlib.PurePosixPath(i.filename).name)
        stage.mkdir();directory=stage/prefix;directory.mkdir(parents=True)
        index={};offset=0
        with (directory/'shaders.pack').open('xb') as output:
            for count,item in enumerate(entries,1):
                name=pathlib.PurePosixPath(item.filename).name
                if not valid_name(name) or name in index or item.filename!=APP+prefix+name or not 0<item.file_size<=64*1024*1024:raise ValueError('Invalid shader resource entry')
                h=hashlib.sha256();size=0
                with z.open(item) as src:
                    for block in iter(lambda:src.read(1024*1024),b''):output.write(block);h.update(block);size+=len(block)
                if size!=item.file_size:raise ValueError('Truncated compiled shader entry')
                index[name]=[offset,size,h.hexdigest()];offset+=size
                if count%10000==0:print(f'Exported {count}/{len(entries)} regenerated shader entries',flush=True)
        (directory/'shaders.index.json').write_text(json.dumps({'version':1,'bytes':offset,'entries':index},separators=(',',':')),encoding='utf-8')
        (directory/'inputs.tsv').write_bytes(z.read(stamps[0]))
    files=[]
    for row in old['files']:
        name=row['path'];safe_data_path(name)
        if name.startswith('msl/'):continue
        src=source/name;dst=stage/name
        if src.is_symlink() or not src.resolve().is_relative_to(source):raise ValueError('Source data escaped its directory')
        dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
        if dst.stat().st_size!=row['size'] or sha256(dst)!=row['sha256']:raise ValueError('Complete original resource failed verification')
        files.append(row)
    for name in ('shaders.pack','shaders.index.json','inputs.tsv'):
        p=directory/name;files.append({'path':prefix+name,'size':p.stat().st_size,'sha256':sha256(p)})
    manifest={'format_version':1,'identity':identity,'files':sorted(files,key=lambda r:r['path']),'shader_storage':'pack-v1'}
    (stage/'game-data.json').write_text(json.dumps(manifest,separators=(',',':')),encoding='utf-8')
    reader=Reader(directory)
    try:
        for count,name in enumerate(index,1):
            reader.read(name)
            if count%20000==0:print(f'Read back {count}/{len(index)} shader entries',flush=True)
    finally:reader.close()
    report={'identity':identity,'shader_entries':len(index),'all_entry_sha256_verified':True,'all_other_file_sha256_verified':True,'original_preserved':True,'gameplay_verified':False}
    stage.rename(target);target.with_suffix('.verification.json').write_text(json.dumps(report,indent=2))
    return report

if __name__=='__main__':print(json.dumps(export(*sys.argv[1:]),indent=2),flush=True)

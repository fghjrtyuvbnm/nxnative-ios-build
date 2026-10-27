"""Deterministic shader partitions and integrity-checked private cache archives."""
import gzip
import hashlib
import json
import pathlib
import re
import shutil
import tarfile
from contracts import TITLE, BUILD, SOURCE, check_identity, sha256
from transfer import split_file

VARIANT_BINARY=re.compile(r'^shader/cache/cas/variant/[0-9a-f]{64}/(?:mac|ios)\.metallib$')
METAL_BINARY=re.compile(r'^shader/cache/cas/metallib/(?:mac|ios)/[0-9a-f]{2}/[0-9a-f]{64}\.metallib$')
VARIANT_FILE=re.compile(r'^shader/cache/cas/variant/[0-9a-f]{64}/(?:metal|fetch\.json|mac\.metallib|ios\.metallib)$')

def derived_conflicts(manifests):
    """Never choose between differing compiled derivatives; regenerate only those entries."""
    seen={};groups=set();discard=set();all_names=set()
    for manifest in manifests:
        names=set()
        for row in manifest['files']:
            name=row['path'];safe_name(name)
            if name in names:raise ValueError('Duplicate shader manifest entries')
            names.add(name);all_names.add(name)
            old=seen.setdefault(name,row['sha256'])
            if old==row['sha256']:continue
            if VARIANT_BINARY.fullmatch(name):groups.add(name.rsplit('/',1)[0])
            elif METAL_BINARY.fullmatch(name):discard.add(name)
            else:raise ValueError('Source, reflection or base cache conflict: '+name)
    discard.update(name for name in all_names if name.rsplit('/',1)[0] in groups)
    return discard

def partition(keys,count):
    if count<1 or len(keys)!=len(set(keys)):raise ValueError('Invalid partition input')
    keys=sorted(keys)
    return [keys[i::count] for i in range(count)]

def close_dependencies(keys,pairs,known):
    result=set(keys);todo=list(keys)
    while todo:
        k=todo.pop()
        if k not in known:raise ValueError('Shader dependency absent from the map')
        for p in pairs.get(k,()):
            if p not in result:result.add(p);todo.append(p)
    return result

def safe_name(name):
    p=pathlib.PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name or not p.parts or p.parts[0]!='shader':raise ValueError('Unsafe shader archive path')
    if p.suffix.lower() in ('.keys','.nsp','.xci','.tik'):raise ValueError('Forbidden shader archive file')
    return p

def pack(root,prefixes,out,kind,metadata):
    root=pathlib.Path(root);out=pathlib.Path(out);out.mkdir(parents=True,exist_ok=True)
    files=[]
    for prefix in prefixes:
        p=root/prefix
        paths=sorted(p.rglob('*')) if p.is_dir() else [p] if p.is_file() else []
        for p in paths:
            if p.is_symlink():raise ValueError('Shader archive symlink')
            if p.is_file() and '.tmp-' not in p.name:
                rel=p.relative_to(root).as_posix();safe_name(rel)
                files.append({'path':rel,'bytes':p.stat().st_size,'sha256':sha256(p)})
    archive=out/'bundle.tar.gz'
    with archive.open('xb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',compresslevel=1,mtime=0) as gz,tarfile.open(fileobj=gz,mode='w|') as t:
        for row in files:t.add(root/row['path'],arcname=row['path'],recursive=False)
    m={'title_id':TITLE,'main_build':BUILD,'source':SOURCE,'kind':kind,'metadata':metadata,'files':files,'parts':split_file(archive,out,'bundle')}
    (out/'bundle-manifest.json').write_text(json.dumps(m,indent=2),encoding='utf-8')
    return m

def restore(src,root,kind,exclude=None):
    exclude=set(exclude or ())
    if any(not (VARIANT_FILE.fullmatch(name) or METAL_BINARY.fullmatch(name)) for name in exclude):raise ValueError('Only disposable derived cache entries can be excluded')
    src=pathlib.Path(src);root=pathlib.Path(root)
    m=json.loads((src/'bundle-manifest.json').read_text());check_identity(m)
    if m.get('source')!=SOURCE or m.get('kind')!=kind:raise ValueError('Wrong shader archive provenance')
    archive=src/'restore.tar.gz'
    with archive.open('wb') as out:
        for i,row in enumerate(m['parts']):
            if row['path']!=f'bundle.part{i:03}':raise ValueError('Bad shader archive part name')
            p=src/row['path']
            if p.stat().st_size!=row['bytes'] or sha256(p)!=row['sha256']:raise ValueError('Shader archive part mismatch')
            with p.open('rb') as f:shutil.copyfileobj(f,out,8*1024*1024)
    expected={r['path']:r for r in m['files']};seen=set()
    if len(expected)!=len(m['files']):raise ValueError('Duplicate shader manifest entries')
    with tarfile.open(archive,'r|gz') as t:
        for entry in t:
            safe_name(entry.name)
            if not entry.isfile() or entry.name not in expected or entry.name in seen:raise ValueError('Unexpected shader archive member')
            row=expected[entry.name];seen.add(entry.name)
            if entry.size!=row['bytes']:raise ValueError('Shader archive entry length mismatch')
            if entry.name in exclude:
                digest=hashlib.sha256()
                with t.extractfile(entry) as f:
                    for block in iter(lambda:f.read(8*1024*1024),b''):digest.update(block)
                if digest.hexdigest()!=row['sha256']:raise ValueError('Discarded derivative failed integrity verification')
                continue
            p=root/entry.name;p.parent.mkdir(parents=True,exist_ok=True)
            if p.is_symlink():raise ValueError('Shader merge target symlink')
            tmp=p.with_name(p.name+'.restore-tmp')
            with t.extractfile(entry) as f,tmp.open('xb') as out:shutil.copyfileobj(f,out,8*1024*1024)
            if sha256(tmp)!=row['sha256']:tmp.unlink();raise ValueError('Shader archive file mismatch')
            if p.exists():
                if sha256(p)!=row['sha256']:tmp.unlink();raise ValueError('Conflicting shader cache entry: '+entry.name)
                tmp.unlink()
            else:tmp.rename(p)
    if seen!=set(expected):raise ValueError('Shader archive missing manifest members')
    archive.unlink()
    return m

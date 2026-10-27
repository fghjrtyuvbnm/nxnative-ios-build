"""Private build input validation; never includes keys or original NSPs."""
import hashlib
import json
import pathlib
import tarfile

TITLE = '0100B8A026F14000'
BUILD = 'b7f965b9d7227db8e29f04e84ea7331b'
SOURCE = 'cdc6cef6b0250fcb54a061e4c55d56382b5d18ad'

def sha256(path):
    h=hashlib.sha256()
    with pathlib.Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''): h.update(b)
    return h.hexdigest()

def check_name(name):
    p=pathlib.PurePosixPath(name)
    if '\\' in name or ':' in name or p.is_absolute() or '..' in p.parts:
        raise ValueError('Unsafe input path')
    if not p.parts or p.parts[0] not in ('extract','patched_v1','aoc'):
        raise ValueError('Unexpected input root')
    if p.suffix.lower() in ('.keys','.nsp','.xci','.tik'):
        raise ValueError('Keys and original containers must remain local')
    return p

def check_identity(m):
    if m.get('title_id') != TITLE or m.get('main_build') != BUILD:
        raise ValueError('Input is not the registered HK 1.0.1 build')

def make_manifest(root):
    root=pathlib.Path(root); files=[]
    for folder in ('extract/v1','patched_v1','aoc'):
        for p in sorted((root/folder).rglob('*')):
            if p.is_symlink(): raise ValueError('Symlink in input')
            if p.is_file():
                name=p.relative_to(root).as_posix(); check_name(name)
                files.append({'path':name,'bytes':p.stat().st_size,'sha256':sha256(p)})
    return {'schema':1,'title_id':TITLE,'main_build':BUILD,'source':SOURCE,'files':files}

def verify(root,m):
    check_identity(m)
    if m.get('source') != SOURCE: raise ValueError('Wrong source revision')
    root=pathlib.Path(root)
    for row in m['files']:
        p=root/str(check_name(row['path']))
        if not p.is_file() or p.is_symlink() or p.stat().st_size != row['bytes'] or sha256(p) != row['sha256']:
            raise ValueError('Input integrity mismatch: '+row['path'])

def unpack(archive,dest):
    dest=pathlib.Path(dest); dest.mkdir(parents=True,exist_ok=True)
    with tarfile.open(archive,'r|gz' if str(archive).endswith('.gz') else 'r|') as t:
        for m in t:
            check_name(m.name)
            if not (m.isfile() or m.isdir()): raise ValueError('Archive links are forbidden')
            p=dest/m.name
            if m.isdir(): p.mkdir(parents=True,exist_ok=True)
            else:
                p.parent.mkdir(parents=True,exist_ok=True)
                import shutil
                with t.extractfile(m) as src,p.open('xb') as out: shutil.copyfileobj(src,out,8*1024*1024)

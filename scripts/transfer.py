"""Hash-checked split archives for private release assets."""
import argparse
import gzip
import json
import pathlib
import shutil
import tarfile
import time
from contracts import make_manifest, verify, sha256, unpack

def split_file(path,out,prefix,chunk=1024**3):
    path=pathlib.Path(path); out=pathlib.Path(out);out.mkdir(parents=True,exist_ok=True)
    parts=[]
    with path.open('rb') as src:
        i=0
        while src.tell()<path.stat().st_size:
            p=out/f'{prefix}.part{i:03}'; left=chunk
            with p.open('xb') as dst:
                while left:
                    b=src.read(min(left,8*1024*1024))
                    if not b: break
                    dst.write(b);left-=len(b)
            parts.append({'path':p.name,'bytes':p.stat().st_size,'sha256':sha256(p)})
            print(f'Prepared {p.name}: {p.stat().st_size:,} bytes',flush=True); i+=1
    return parts

def pack(root,out,wait_rewrite=False):
    root=pathlib.Path(root); out=pathlib.Path(out);out.mkdir(parents=True,exist_ok=True)
    m=make_manifest(root)
    report=root/'shader-input-verification.json'
    if report.is_file():
        m['input_kind']='shader-only'
        m['shader_input']={k:v for k,v in json.loads(report.read_text()).items() if k!='blocks'}
    archive=out/'input.tar.gz'
    with archive.open('xb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',compresslevel=1,mtime=0) as gz,tarfile.open(fileobj=gz,mode='w|') as t:
        for row in m['files']:
            print('Packing '+row['path'],flush=True)
            t.add(root/row['path'],arcname=row['path'],recursive=False)
        if wait_rewrite and not (root/'patched_v1/main.patched.bin').exists():
            deadline=time.monotonic()+3600
            while not (root/'patched_v1/main.patched.bin').exists():
                if time.monotonic()>deadline:raise TimeoutError('Rewrite has not completed within one hour')
                print('Game data compressed; waiting for the local module rewrite',flush=True)
                time.sleep(30)
            patched=make_manifest(root)
            known={row['path'] for row in m['files']}
            for row in patched['files']:
                if row['path'] not in known:
                    print('Packing '+row['path'],flush=True)
                    t.add(root/row['path'],arcname=row['path'],recursive=False)
            m=patched
    m['parts']=split_file(archive,out,'input')
    m['archive_bytes']=archive.stat().st_size
    (out/'input-manifest.json').write_text(json.dumps(m,indent=2),encoding='utf-8')
    print('Input archive ready; no keys or NSPs included',flush=True)

def restore(src,dest):
    src=pathlib.Path(src);dest=pathlib.Path(dest)
    m=json.loads((src/'input-manifest.json').read_text())
    from contracts import check_identity
    check_identity(m)
    archive=src/'input.tar.gz'
    with archive.open('xb') as out:
        for i,row in enumerate(m['parts']):
            if row['path']!=f'input.part{i:03}': raise ValueError('Unexpected archive part name')
            p=src/row['path']
            if p.stat().st_size!=row['bytes'] or sha256(p)!=row['sha256']: raise ValueError('Damaged upload part')
            with p.open('rb') as f:shutil.copyfileobj(f,out,8*1024*1024)
            p.unlink()  # Only these verified disposable downloads; keep local originals.
    unpack(archive,dest);archive.unlink()
    verify(dest,m)
    (dest/'input-manifest.json').write_text(json.dumps(m,indent=2),encoding='utf-8')
    print('Restored and verified every input file',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['pack','restore']);p.add_argument('src');p.add_argument('dest');p.add_argument('--wait-rewrite',action='store_true');a=p.parse_args()
    if a.mode=='pack':pack(a.src,a.dest,a.wait_rewrite)
    else:restore(a.src,a.dest)

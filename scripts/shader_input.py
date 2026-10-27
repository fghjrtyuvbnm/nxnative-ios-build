"""Compact a private, shader-only IoStore input. Never use it as game RomFS."""
import hashlib
import json
import pathlib
import shutil
import struct
import sys

def compact(toc,src,dst):
    """Retain original compressed shader blocks byte for byte, relocating physical offsets only."""
    src=pathlib.Path(src);dst=pathlib.Path(dst)
    b=bytearray(src.read_bytes())
    if toc.encrypted or b[80]&4:raise ValueError('Encrypted or signed IoStore compaction is unsupported')
    if toc.version<5:raise ValueError('This path requires a modern IoStore TOC')
    hsz,n,nblk,bsz=struct.unpack_from('<4I',b,20)
    if bsz!=12 or nblk!=len(toc.blocks):raise ValueError('Unsupported block table')
    seeds=struct.unpack_from('<I',b,84)[0];over=struct.unpack_from('<I',b,96)[0]
    table=hsz+22*n+4*(seeds+over)
    selected=set()
    indices=toc.of_type(8)+toc.of_type(9)
    if not toc.of_type(8):raise ValueError('No shader library')
    for i in indices:
        off,size=toc.ranges[i]
        selected.update(range(off//toc.block_size,(off+size+toc.block_size-1)//toc.block_size))
    dst.parent.mkdir(parents=True,exist_ok=True)
    out=dst.with_suffix('.ucas');records=[]
    with out.open('xb') as f:
        for k in sorted(selected):
            at,size,raw,method=toc.blocks[k]
            handle=toc.ucas(at//toc.part_size);handle.seek(at%toc.part_size);data=handle.read(size)
            if len(data)!=size:raise ValueError('Source shader block is truncated')
            new=f.tell();f.write(data)
            b[table+12*k:table+12*k+5]=new.to_bytes(5,'little')
            records.append({'index':k,'source_offset':at,'compact_offset':new,'bytes':size,'sha256':hashlib.sha256(data).hexdigest()})
        end=f.tell()
    # Non-shader reads point outside the compact data, never at another block.
    for k in set(range(nblk))-selected:b[table+12*k:table+12*k+5]=(end+16).to_bytes(5,'little')
    # Compacted data are one partition, regardless of the original partition count.
    struct.pack_into('<I',b,52,1)
    dst.write_bytes(b)
    with out.open('rb') as f:
        for r in records:
            f.seek(r['compact_offset'])
            if hashlib.sha256(f.read(r['bytes'])).hexdigest()!=r['sha256']:raise ValueError('Compacted block readback differs')
    return {'purpose':'Shader decoding only. Not runnable game data.','libraries':len(toc.of_type(8)),'code_chunks':len(toc.of_type(9)),
            'compressed_bytes':end,'blocks_verified':len(records),'blocks':records}

def prepare(repo,work,dest):
    repo=pathlib.Path(repo).resolve();work=pathlib.Path(work).resolve();dest=pathlib.Path(dest).resolve()
    sys.path.insert(0,str(repo/'dm/gfx/tools'));import uepak
    ex=work/'extract/v1';out=dest/'extract/v1';out.mkdir(parents=True,exist_ok=True)
    shutil.copytree(ex/'ExeFS',out/'ExeFS')
    for n in ('icon.jpg','control.nacp'):shutil.copyfile(ex/n,out/n)
    rf=ex/'RomFS';orf=out/'RomFS';orf.mkdir()
    for p in rf.glob('Manifest_*.txt'):shutil.copyfile(p,orf/p.name)
    src=rf/'FFRS/Content/Paks/FFRS-Switch.utoc'
    report=compact(uepak.Toc(str(src)),src,orf/src.relative_to(rf))
    if report['libraries']!=2 or report['code_chunks']!=5919:raise ValueError('Unexpected HK shader library layout')
    shutil.copytree(work/'aoc',dest/'aoc')
    (dest/'shader-input-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(f"Shader-only input: {report['compressed_bytes']:,} bytes; {report['blocks_verified']:,} blocks verified byte for byte",flush=True)

if __name__=='__main__':prepare(*sys.argv[1:])

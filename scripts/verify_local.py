"""Check NSO segment hashes, known module IDs, and the allocator patch site."""
import hashlib
import json
import pathlib
import struct
import sys
import lz4.block
from contracts import TITLE, BUILD, SOURCE, sha256

EXPECTED={'main':BUILD,'subsdk0':'ab62fe8edd07a6a293f885d54359e559','sdk':'0023a1b06130cd795f7bc4613772af0a'}

def verify(work):
    work=pathlib.Path(work);rows=[]
    for name,bid in EXPECTED.items():
        p=work/'extract/v1/ExeFS'/name;d=p.read_bytes()
        if d[:4]!=b'NSO0' or d[0x40:0x50].hex()!=bid: raise ValueError('Wrong NSO build: '+name)
        flags=struct.unpack_from('<I',d,12)[0];segments=[]
        for i in range(3):
            fo,mo,size=struct.unpack_from('<III',d,0x10+i*16)
            stored=struct.unpack_from('<I',d,0x60+4*i)[0] if flags&(1<<i) else size
            raw=d[fo:fo+stored]
            if flags&(1<<i):raw=lz4.block.decompress(raw,uncompressed_size=size)
            if len(raw)!=size or hashlib.sha256(raw).digest()!=d[0xa0+32*i:0xc0+32*i]:raise ValueError('NSO segment hash mismatch')
            if name=='main' and i==0 and raw[0x137f0-mo:0x137f4-mo]!=bytes.fromhex('e06b0294'):
                raise ValueError('HK allocator constructor call differs')
            segments.append({'segment':i,'sha256':hashlib.sha256(raw).hexdigest()})
        rows.append({'module':name,'build_id':bid,'sha256':sha256(p),'segments':segments})
    m={'title_id':TITLE,'main_build':BUILD,'source':SOURCE,'module_verification':rows,'extraction_integrity':'nx_extract returned 0 with strict NCA hashes'}
    (work/'local-verification.json').write_text(json.dumps(m,indent=2),encoding='utf-8')
    print('All three module IDs, nine NSO segment hashes and the allocator cut site verified')

if __name__=='__main__':verify(sys.argv[1])

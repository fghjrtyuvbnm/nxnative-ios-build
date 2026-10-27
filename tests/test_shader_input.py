import hashlib
import pathlib
import struct
import sys
import tempfile
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from shader_input import compact

class TocFixture:
    encrypted=False;version=8;block_size=16;part_size=2**64
    blocks=[(0,4,4,0),(8,3,3,0),(16,4,4,0)]
    ranges=[(0,4),(16,3),(32,4)]
    def of_type(self,t):return {8:[0],9:[1]}.get(t,[])
    def ucas(self,part):return self.handle

class ShaderInput(unittest.TestCase):
    def test_compaction_preserves_selected_bytes_and_logical_ranges(self):
        with tempfile.TemporaryDirectory() as td:
            r=pathlib.Path(td);toc=TocFixture();hdr=bytearray(144)
            hdr[16]=8;struct.pack_into('<9I',hdr,20,144,3,3,12,0,32,16,0,1)
            ids=b'0'*11+b'\x08'+b'1'*11+b'\x09'+b'2'*11+b'\x01'
            ranges=b''.join(o.to_bytes(5,'big')+s.to_bytes(5,'big') for o,s in toc.ranges)
            blocks=b''.join(o.to_bytes(5,'little')+s.to_bytes(3,'little')+raw.to_bytes(3,'little')+bytes([m]) for o,s,raw,m in toc.blocks)
            source=r/'original.utoc';source.write_bytes(hdr+ids+ranges+blocks)
            data=r/'original.ucas';data.write_bytes(b'ABCD----EFG-----HIJK')
            with data.open('rb') as toc.handle:report=compact(toc,source,r/'compact.utoc')
            self.assertEqual((r/'compact.ucas').read_bytes(),b'ABCDEFG')
            result=(r/'compact.utoc').read_bytes();table=144+66
            self.assertEqual(result[144:table],(hdr+ids+ranges)[144:table])
            self.assertEqual(int.from_bytes(result[table:table+5],'little'),0)
            self.assertEqual(int.from_bytes(result[table+12:table+17],'little'),4)
            self.assertGreater(int.from_bytes(result[table+24:table+29],'little'),7)
            self.assertEqual(report['blocks_verified'],2)
            self.assertEqual(data.read_bytes(),b'ABCD----EFG-----HIJK')

    def test_encrypted_inputs_refused(self):
        with tempfile.TemporaryDirectory() as td:
            r=pathlib.Path(td);p=r/'x.utoc';p.write_bytes(bytes(144));toc=TocFixture();toc.encrypted=True
            with self.assertRaises(ValueError):compact(toc,p,r/'out.utoc')

if __name__=='__main__':unittest.main()

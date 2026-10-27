import json
import pathlib
import sys
import tempfile
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
import contracts as c
import transfer as t

class Transfer(unittest.TestCase):
    def test_full_pack_restore(self):
        with tempfile.TemporaryDirectory() as td:
            r=pathlib.Path(td);src=r/'src';(src/'patched_v1').mkdir(parents=True)
            (src/'patched_v1/main.patched.bin').write_bytes(bytes(range(256))*128)
            t.pack(src,r/'parts')
            # The sender keeps its archive; the receiver uses a fresh directory.
            (r/'parts/input.tar.gz').rename(r/'sender-copy.tar.gz')
            t.restore(r/'parts',r/'restored')
            self.assertEqual((r/'restored/patched_v1/main.patched.bin').read_bytes(),bytes(range(256))*128)

    def test_tampered_part_refused_before_extraction(self):
        with tempfile.TemporaryDirectory() as td:
            r=pathlib.Path(td);src=r/'src';(src/'aoc/2').mkdir(parents=True)
            (src/'aoc/2/item').write_bytes(b'dlc')
            t.pack(src,r/'parts');(r/'parts/input.tar.gz').unlink()
            (r/'parts/input.part000').write_bytes(b'corrupt')
            with self.assertRaises(ValueError):t.restore(r/'parts',r/'out')
            self.assertFalse((r/'out').exists())

    def test_split_boundaries(self):
        with tempfile.TemporaryDirectory() as td:
            r=pathlib.Path(td);p=r/'a';p.write_bytes(b'abcdefghij')
            rows=t.split_file(p,r/'split','test',chunk=4)
            self.assertEqual([x['bytes'] for x in rows],[4,4,2])
            self.assertEqual(b''.join((r/'split'/x['path']).read_bytes() for x in rows),p.read_bytes())

if __name__=='__main__':unittest.main()

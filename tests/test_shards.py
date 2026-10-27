import io
import json
import pathlib
import os
import sys
import tempfile
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
import shards

class Shards(unittest.TestCase):
    def test_real_map_header_and_complete_partition_coverage(self):
        repo=pathlib.Path(os.environ.get('NXNATIVE_REPO',str(pathlib.Path(__file__).resolve().parents[2]/'nxnative')))
        sys.path.insert(0,str(repo/'dm/games'));import game,pipeline
        keys,pairs=pipeline.key_map(game.load('0100B8A026F14000'),pathlib.Path('.'))
        self.assertEqual(len(keys),73496)
        parts=shards.partition(list(keys),16)
        self.assertEqual(set(k for part in parts for k in part),set(keys))
        self.assertTrue(all(len(shards.close_dependencies(set(part),pairs,set(keys)))<4700 for part in parts))

    def test_partition_exact_coverage_with_dependency_closure(self):
        keys=['a','b','c','d','e'];parts=shards.partition(keys,3)
        self.assertEqual(sorted(k for p in parts for k in p),keys)
        self.assertEqual(len(set(k for p in parts for k in p)),5)
        self.assertEqual(shards.close_dependencies({'a'},{'a':{'b'},'b':{'c'},'c':{'a'}},set(keys)),{'a','b','c'})
        with self.assertRaises(ValueError):shards.close_dependencies({'a'},{'a':{'missing'}},set(keys))

    def test_checked_archive_merge_and_collision(self):
        with tempfile.TemporaryDirectory() as td:
            r=pathlib.Path(td);src=r/'src';p=src/'shader/cache/cas/index/a.json';p.parent.mkdir(parents=True);p.write_text('same')
            shards.pack(src,['shader/cache/cas'],r/'parts','cache',{'identity':'one'})
            m=shards.restore(r/'parts',r/'dst','cache')
            self.assertEqual((r/'dst/shader/cache/cas/index/a.json').read_text(),'same')
            shards.restore(r/'parts',r/'dst','cache')
            (r/'dst/shader/cache/cas/index/a.json').write_text('different')
            with self.assertRaises(ValueError):shards.restore(r/'parts',r/'dst','cache')

    def test_archive_refuses_unknown_roots_and_traversal(self):
        for path in ['../secret','shader/../../secret','prod.keys','/shader/a','shader\\a','shader/cache/prod.keys']:
            with self.subTest(path=path),self.assertRaises(ValueError):shards.safe_name(path)

    def test_bad_part_refused(self):
        with tempfile.TemporaryDirectory() as td:
            r=pathlib.Path(td);src=r/'src';p=src/'shader/pkg/a.bin';p.parent.mkdir(parents=True);p.write_bytes(b'code')
            shards.pack(src,['shader/pkg'],r/'parts','prepared',{})
            (r/'parts/bundle.part000').write_bytes(b'broken')
            with self.assertRaises(ValueError):shards.restore(r/'parts',r/'dst','prepared')

if __name__=='__main__':unittest.main()

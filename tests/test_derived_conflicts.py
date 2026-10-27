import json
import pathlib
import sys
import tempfile
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
import shards

class DerivedConflicts(unittest.TestCase):
    def test_binary_conflicts_are_discarded_as_a_whole_variant_and_base_cache_survives(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td);bundles=[];manifests=[]
            group='shader/cache/cas/variant/'+'a'*64
            for index in range(3):
                source=root/f'source-{index}';variant=source/group;variant.mkdir(parents=True)
                (variant/'metal').write_text('identical generated MSL')
                (variant/'fetch.json').write_text('{"same":"reflection"}')
                (variant/'ios.metallib').write_bytes(bytes([index]))
                (variant/'mac.metallib').write_bytes(b'same Mac library')
                base=source/'shader/cache/cas/index/base.json';base.parent.mkdir(parents=True);base.write_text('same base index')
                bundle=root/f'bundle-{index}';manifests.append(shards.pack(source,['shader/cache/cas'],bundle,'cache',{}));bundles.append(bundle)
            excluded=shards.derived_conflicts(manifests)
            self.assertEqual(len(excluded),4)
            for bundle in bundles:shards.restore(bundle,root/'merged','cache',exclude=excluded)
            self.assertFalse((root/'merged'/group).exists())
            self.assertEqual((root/'merged/shader/cache/cas/index/base.json').read_text(),'same base index')

    def test_source_and_base_conflicts_remain_fatal(self):
        group='shader/cache/cas/variant/'+'a'*64
        for name in (group+'/metal','shader/cache/cas/index/base.json'):
            manifests=[{'files':[{'path':name,'sha256':h}]} for h in ('one','two')]
            with self.assertRaises(ValueError):shards.derived_conflicts(manifests)

    def test_discarded_derivative_still_requires_its_recorded_file_hash(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td);name='shader/cache/cas/variant/'+'a'*64+'/ios.metallib'
            file=root/'source'/name;file.parent.mkdir(parents=True);file.write_bytes(b'compiled derivative')
            manifest=shards.pack(root/'source',['shader/cache/cas'],root/'bundle','cache',{})
            manifest['files'][0]['sha256']='0'*64
            (root/'bundle/bundle-manifest.json').write_text(json.dumps(manifest))
            with self.assertRaises(ValueError):shards.restore(root/'bundle',root/'merged','cache',exclude={name})

    def test_compiled_metal_cache_conflict_is_recompiled_but_cannot_exclude_base(self):
        name='shader/cache/cas/metallib/ios/aa/'+'a'*64+'.metallib'
        manifests=[{'files':[{'path':name,'sha256':h}]} for h in ('one','two')]
        self.assertEqual(shards.derived_conflicts(manifests),{name})
        with self.assertRaises(ValueError):shards.restore('unused','unused','cache',exclude={'shader/cache/cas/index/base.json'})

if __name__=='__main__':unittest.main()

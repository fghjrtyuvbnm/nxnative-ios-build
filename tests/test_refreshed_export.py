import hashlib,json,pathlib,sys,tempfile,unittest,zipfile
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from export_refreshed_data import export
from shader_pack import Reader
from external_pack import APP

class RefreshedExport(unittest.TestCase):
    def test_export_reopen_preserves_romfs_and_replaces_identity_and_shader_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);src=root/'original';(src/'romfs').mkdir(parents=True)
            payload=b'original complete resource';(src/'romfs/test.pak').write_bytes(payload)
            old={'title_id':'test','main_build':'build','shader_chain':'chain','shader_inputs':'old'}
            m={'identity':old,'files':[{'path':'romfs/test.pak','size':len(payload),'sha256':hashlib.sha256(payload).hexdigest()}]}
            (src/'game-data.json').write_text(json.dumps(m));before=(src/'game-data.json').read_bytes()
            archive=root/'resources.zip'
            with zipfile.ZipFile(archive,'w') as z:
                z.writestr(APP+'msl/b-chain/inputs.tsv','game\ttest\ninputs\tnew\n')
                z.writestr(APP+'dm/c1_full.tsv','# chain b-chain inputs new generated\n')
                z.writestr(APP+'msl/b-chain/abc_b.metallib',b'new shader')
                z.writestr(APP+'msl/b-chain/abc_b.json',b'{}')
            target=root/'candidate';r=export(archive,src,target)
            self.assertEqual(r['identity']['shader_inputs'],'new');self.assertEqual(r['shader_entries'],2)
            self.assertEqual((src/'game-data.json').read_bytes(),before)
            self.assertEqual((target/'romfs/test.pak').read_bytes(),payload)
            reader=Reader(target/'msl/b-chain')
            try:self.assertEqual(reader.read('abc_b.metallib'),b'new shader')
            finally:reader.close()
            with self.assertRaises(ValueError):export(archive,src,target)
            with self.assertRaisesRegex(ValueError,'not regenerated'):export(archive,target,root/'another')

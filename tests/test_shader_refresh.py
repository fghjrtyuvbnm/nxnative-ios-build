import pathlib,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from refresh_shader_profile import apply,verify,rows,FACTS
from contracts import TITLE

class RefreshTests(unittest.TestCase):
    def test_old_profile_fails_then_merge_preserves_compute_metadata_and_map(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=pathlib.Path(tmp)/'dm/games'/TITLE;p.mkdir(parents=True)
            wanted=rows(FACTS);key='120e6fbdf2cb9516'
            original='package\tindex\tstage\tdm_ctl_sha16\tsource\n'+''.join('ps.bin\t%d\tcompute\t%s\tfixture\n'%(i,k) for i,k in enumerate(wanted))
            (p/'shader_map.tsv').write_text(original)
            (p/'shader_facts.tsv').write_text(key+'\t{"local":[4,4,4],"shared":0}\n'+'c254eaa40e0c4f1e\t{"fout":{"0":"uint"}}\n')
            with self.assertRaisesRegex(ValueError,'34 fact rows'):verify(p)
            result=apply(tmp);self.assertEqual(len(result['changed_keys']),34)
            self.assertEqual(rows(p/'shader_facts.tsv')[key],{'local':[4,4,4],'shared':0,'img':{'0':'buffer'}})
            self.assertEqual((p/'shader_map.tsv').read_text(),original)
            before=(p/'shader_facts.tsv').read_bytes();self.assertEqual(apply(tmp)['changed_keys'],[])
            self.assertEqual(before,(p/'shader_facts.tsv').read_bytes());verify(p)

    def test_mismatched_map_rejected_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=pathlib.Path(tmp)/'dm/games'/TITLE;p.mkdir(parents=True)
            (p/'shader_facts.tsv').write_text('# empty\n');(p/'shader_map.tsv').write_text('# wrong\n')
            with self.assertRaisesRegex(ValueError,'retained shader map'):apply(tmp)
            self.assertEqual((p/'shader_facts.tsv').read_text(),'# empty\n')

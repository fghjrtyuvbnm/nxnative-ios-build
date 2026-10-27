import pathlib
import sys
import tempfile
import unittest
import zipfile
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from contracts import TITLE
from build_external_launcher import restore_tables

class ReuseTemplate(unittest.TestCase):
    def test_restores_exact_tables_and_rejects_wrong_stamp(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td);archive=root/'template.ipa'
            with zipfile.ZipFile(archive,'w') as z:
                for n,v in {'msl/b-test/inputs.tsv':f'game\t{TITLE}\ninputs\tdigest\n','msl/b-test/a_b.metallib':'library','dm/c1_full.tsv':'# chain b-test inputs digest generated\n','dm/cb_extent.tsv':'exact extent'}.items():z.writestr('Payload/DmIOS.app/'+n,v)
            identity=restore_tables(archive,root/'restored',root/'profile','test','digest')
            self.assertEqual(identity['shader_inputs'],'digest')
            self.assertEqual((root/'profile/cb_extent.tsv').read_text(),'exact extent')
            with self.assertRaises(ValueError):restore_tables(archive,root/'bad',root/'bad-profile','test','different')

if __name__=='__main__':unittest.main()

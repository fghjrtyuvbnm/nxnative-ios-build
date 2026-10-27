"""Integration contract against the installed, pinned nxnative profile."""
import os
import pathlib
import unittest

class Profile(unittest.TestCase):
    def test_hk_keeps_verified_integer_shader_output(self):
        repo=pathlib.Path(os.environ.get('NXNATIVE_REPO',str(pathlib.Path(__file__).resolve().parents[2]/'nxnative')))
        hk=repo/'dm/games/0100B8A026F14000'
        row='c254eaa40e0c4f1e\t{"fout":{"0":"uint"}}'
        self.assertIn('c254eaa40e0c4f1e',(hk/'shader_map.tsv').read_text())
        self.assertTrue(row in (hk/'shader_facts.tsv').read_text(),'HK profile lacks the verified integer fragment output')
        self.assertTrue(row in (hk/'shader_facts_manual.tsv').read_text(),'HK profile cannot reproduce the integer output fact')

if __name__=='__main__':unittest.main()

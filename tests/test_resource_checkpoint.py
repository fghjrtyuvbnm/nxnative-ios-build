import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
import zipfile
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from cloud_build import checkpoint_resources
from contracts import sha256

class ResourceCheckpoint(unittest.TestCase):
    def test_real_upstream_packer_produces_resource_only_archive_and_real_tables(self):
        repo=pathlib.Path(os.environ.get('NXNATIVE_REPO',str(pathlib.Path(__file__).resolve().parents[2]/'nxnative'))).resolve()
        with tempfile.TemporaryDirectory() as td:
            work=pathlib.Path(td);profile=work/'profile';profile.mkdir();logs=work/'logs';logs.mkdir()
            key='a'*16;ios=work/'ios';lib=ios/'b-test';lib.mkdir(parents=True)
            (lib/(key+'_b.json')).write_text(json.dumps({'stage':'gs','gs_slice':{'loc':1,'comp':'x'}}))
            (lib/'inputs.tsv').write_text('real generated stamp fixture')
            (profile/'shader_map.tsv').write_text(f'fixture\t0\tgeometry\t{key}\tsource\n')
            for name in ('c1_full.tsv','cb_extent.tsv'):(profile/name).write_text('# generated table fixture\n')
            (work/'aoc/2').mkdir(parents=True);(work/'aoc/2/content').write_bytes(b'fixture content')
            def run(command,log,env):
                result=subprocess.run(list(map(str,command)),capture_output=True,text=True,env=env)
                if result.returncode:raise RuntimeError(result.stderr)
            b=SimpleNamespace(chain_of=lambda _: 'test',run=run)
            g=SimpleNamespace(get=lambda _:'.pak:.ucas',table=lambda name:profile/name)
            with patch('cloud_build.stage_progress'),patch('private_io.publish_resources') as publish:
                checkpoint_resources(b,repo,work,g,ios,[{'st':'ok'}],dict(os.environ),logs)
                publish.assert_called_once_with(work)
            out=work/'compiled-resources';m=json.loads((out/'result-manifest.json').read_text())
            self.assertTrue(m['resource_only']);self.assertFalse(m['external_data_runtime'])
            self.assertEqual(m['template_sha256'],sha256(out/'compiled-resources.zip'))
            with zipfile.ZipFile(out/'compiled-resources.zip') as z:
                self.assertIsNone(z.testzip())
                self.assertEqual(z.read('Payload/DmIOS.app/dm/c1_full.tsv'),(profile/'c1_full.tsv').read_bytes())
                self.assertNotIn('Payload/DmIOS.app/DmIOS',z.namelist())

if __name__=='__main__':unittest.main()

import os,pathlib,subprocess,sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
import apply_ios18
import apply_shader_pack
from contracts import SOURCE

class IOS18Patch(unittest.TestCase):
    def test_interrupted_patch_repairs_project_and_keeps_shader_cache_contract(self):
        original=pathlib.Path(os.environ.get('NXNATIVE_REPO',''))
        if not (original/'.git').exists():self.skipTest('Set NXNATIVE_REPO to the pinned source checkout')
        paths=['dm/gfx/nvn/nvn_mtl.m','dm/ios/project.yml','dm/gfx/nvn/dmsh_chain.h','dm/ios/tools/ios_metal.py','dm/games/settings.tsv']
        payload={name:subprocess.check_output(['git','-C',str(original),'show',SOURCE+':'+name]) for name in paths}
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td)
            for name,data in payload.items():
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
            with patch.object(apply_ios18.subprocess,'check_output',return_value=SOURCE):
                apply_ios18.apply(root)
                apply_shader_pack.apply(root)
                # Simulate interruption between writing the backend and the project.
                (root/'dm/ios/project.yml').write_bytes(payload['dm/ios/project.yml'])
                apply_ios18.apply(root)
                self.assertIn('iOS: "18.0"',(root/'dm/ios/project.yml').read_text())
                self.assertIn('-mcpu=apple-a17',(root/'dm/ios/project.yml').read_text())
                settings=(root/'dm/games/settings.tsv').read_text()
                self.assertNotIn('DM_PRESENT_UPSCALE\t',settings)
                self.assertNotIn('DM_PSO_MTL4\t',settings)
                self.assertIn('DM_NVN_ENC_THREAD\t',settings)
                before=(root/'dm/gfx/nvn/nvn_mtl.m').read_bytes()
                apply_ios18.apply(root)
                apply_shader_pack.apply(root)
                self.assertEqual(before,(root/'dm/gfx/nvn/nvn_mtl.m').read_bytes())
            for name in paths[2:4]:self.assertEqual(payload[name],(root/name).read_bytes())

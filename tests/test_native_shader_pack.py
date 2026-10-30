import os,pathlib,subprocess,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from contracts import SOURCE
from apply_shader_pack import apply

class NativeShaderPack(unittest.TestCase):
    def test_packed_data_reader_is_included_on_unmodified_native_metal_backend(self):
        repo=pathlib.Path(os.environ.get('NXNATIVE_REPO',pathlib.Path(__file__).resolve().parents[2]/'nxnative'))
        original=subprocess.check_output(['git','-C',str(repo),'show',SOURCE+':dm/gfx/nvn/nvn_mtl.m'])
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp)/'dm/gfx/nvn';root.mkdir(parents=True)
            source=root/'nvn_mtl.m';source.write_bytes(original)
            apply(tmp);s=source.read_text()
            self.assertTrue('#include "shader_pack.h"' in s,'Native backend lacks packed shader reader include')
            self.assertNotIn('ios18_metal.h',s)
            self.assertIn('g_dev = MTLCreateSystemDefaultDevice();',s)
            first=source.read_bytes();apply(tmp);self.assertEqual(source.read_bytes(),first)

import os,pathlib,struct,subprocess,sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from contracts import SOURCE
from native_metal_artifact import check_macho
from apply_native_metal import apply

class NativeMetal(unittest.TestCase):
    def test_production_patch_order_keeps_native_device_and_queue_and_startup_check(self):
        from apply_runtime import apply as external
        from apply_ue_vm import apply as vm
        from apply_memory_diagnostics import apply as memory
        from apply_startup_memory import apply as startup
        from apply_shader_pack import apply as pack
        checkout=pathlib.Path(os.environ.get('NXNATIVE_REPO',pathlib.Path(__file__).resolve().parents[2]/'nxnative'))
        paths=['dm/ios/Sources/main.m','dm/ios/Sources/Launcher.swift','dm/host/hle_uemalloc.c','dm/ios/project.yml','dm/gfx/nvn/nvn_mtl.m']
        with tempfile.TemporaryDirectory() as tmp:
            repo=pathlib.Path(tmp)
            for name in paths:
                p=repo/name;p.parent.mkdir(parents=True,exist_ok=True)
                p.write_bytes(subprocess.check_output(['git','-C',str(checkout),'show',SOURCE+':'+name]))
            with patch('apply_runtime.subprocess.check_output',return_value=SOURCE):external(repo)
            vm(repo);memory(repo);startup(repo);apply(repo);pack(repo)
            source=(repo/'dm/gfx/nvn/nvn_mtl.m').read_text()
            self.assertTrue('g_dev = MTLCreateSystemDefaultDevice();' in source)
            self.assertTrue('newMTL4CommandQueueWithDescriptor' in source)
            self.assertFalse('ios18_metal.h' in source)
            self.assertFalse((repo/'dm/gfx/nvn/ios18_metal.h').exists())
            main=(repo/'dm/ios/Sources/main.m').read_text()
            self.assertTrue('[native-metal4]' in main);self.assertFalse('[classic-lifecycle]' in main)
            self.assertTrue('dm_startup_memory_note("play-before-preload")' in main)
            self.assertTrue('iOS: "26.0"' in (repo/'dm/ios/project.yml').read_text())

    def test_real_binary_contract_rejects_classic_target_or_adapter(self):
        def image(minimum=26,marker=b'[native-metal4]'):
            return struct.pack('<8I',0xfeedfacf,0x0100000c,0,2,1,24,0,0)+struct.pack('<6I',0x32,24,2,minimum<<16,0,0)+marker
        self.assertEqual(check_macho(image())['minimum_ios'],'26.0')
        with self.assertRaises(ValueError):check_macho(image(18))
        with self.assertRaises(ValueError):check_macho(image(marker=b'[native-metal4] DM18Registry'))

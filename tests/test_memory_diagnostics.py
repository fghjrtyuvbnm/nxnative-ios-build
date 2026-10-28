import os,pathlib,subprocess,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from apply_memory_diagnostics import apply
from contracts import SOURCE

class MemoryDiagnosticsTests(unittest.TestCase):
    def test_observation_keeps_allocator_failure_and_is_idempotent(self):
        repo=pathlib.Path(os.environ.get('NXNATIVE_REPO',''))
        if not (repo/'.git').exists():self.skipTest('Pinned source checkout required')
        original=subprocess.check_output(['git','-C',str(repo),'show',SOURCE+':dm/host/hle_uemalloc.c'],text=True)
        main='#include <stdio.h>\n    // Environment switch files\n    if (uses_external_data()) dm_host_preload_start(g_argc, g_argv);\n'
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td)
            for folder in ('dm/host','dm/ios/Sources','dm/gfx/nvn'):(root/folder).mkdir(parents=True)
            allocator=root/'dm/host/hle_uemalloc.c';allocator.write_text(original)
            (root/'dm/ios/Sources/main.m').write_text(main)
            apply(root);before=allocator.read_text();apply(root)
            self.assertEqual(before,allocator.read_text())
            self.assertIn('dm_memory_note("ue-realloc-failed")',before)
            # Every original allocator operation and fatal check is preserved.
            self.assertEqual(before.count('die('),original.count('die('))
            self.assertEqual(before[before.index('static void *realloc_aligned'):before.index('static void *m_Malloc')],original[original.index('static void *realloc_aligned'):original.index('static void *m_Malloc')])

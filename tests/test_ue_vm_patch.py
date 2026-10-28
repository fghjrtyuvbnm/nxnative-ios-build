import os,pathlib,subprocess,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from contracts import SOURCE
from apply_ue_vm import apply
from apply_memory_diagnostics import apply as diagnostics

class VMPatchTests(unittest.TestCase):
    def test_lifecycle_queries_diagnostics_and_idempotence(self):
        checkout=pathlib.Path(os.environ.get('NXNATIVE_REPO',''))
        if not (checkout/'.git').exists():self.skipTest('Pinned source required')
        original=subprocess.check_output(['git','-C',str(checkout),'show',SOURCE+':dm/host/hle_uemalloc.c'],text=True)
        with tempfile.TemporaryDirectory() as td:
            repo=pathlib.Path(td)
            for folder in ('dm/host','dm/ios/Sources','dm/gfx/nvn'):(repo/folder).mkdir(parents=True)
            p=repo/'dm/host/hle_uemalloc.c';p.write_text(original)
            (repo/'dm/ios/Sources/main.m').write_text('#include <stdio.h>\n    // Environment switch files\n    if (uses_external_data()) dm_host_preload_start(g_argc, g_argv);\n')
            apply(repo);before=p.read_text();apply(repo);self.assertEqual(p.read_text(),before)
            self.assertIn('*out = ue_size(p);',before)
            self.assertIn('return n>=UE_VM_THRESHOLD?ue_vm_round(n):malloc_good_size(n);',before)
            self.assertEqual(original[original.index('static const struct'):original.index('enum { NSLOT')],before[before.index('static const struct'):before.index('enum { NSLOT')])
            diagnostics(repo);before=p.read_text();apply(repo);diagnostics(repo);self.assertEqual(before,p.read_text())
            self.assertIn('ue_allocation_failure("realloc",p,n,a,native_error)',before)

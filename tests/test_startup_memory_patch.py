import os,pathlib,subprocess,sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from contracts import SOURCE
from apply_runtime import apply as external
from apply_memory_diagnostics import apply as memory
from apply_startup_memory import apply

class StartupMemoryPatchTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('NXNATIVE_REPO'),'Pinned source checkout required')
    def test_external_launcher_check_runs_before_preload_and_patch_is_idempotent(self):
        checkout=pathlib.Path(os.environ['NXNATIVE_REPO'])
        paths=['dm/ios/Sources/main.m','dm/ios/Sources/Launcher.swift','dm/host/hle_uemalloc.c']
        originals={p:subprocess.check_output(['git','-C',str(checkout),'show',SOURCE+':'+p]) for p in paths}
        with tempfile.TemporaryDirectory() as folder:
            repo=pathlib.Path(folder)
            for p,data in originals.items():
                target=repo/p;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
            (repo/'dm/gfx/nvn').mkdir(parents=True)
            # The source bytes above came from this exact commit; the fixture is not a git checkout.
            with patch('apply_runtime.subprocess.check_output',return_value=SOURCE): external(repo)
            memory(repo);host=(repo/'dm/host/hle_uemalloc.c').read_bytes()
            apply(repo);first={p.relative_to(repo):p.read_bytes() for p in repo.rglob('*') if p.is_file()}
            apply(repo);second={p.relative_to(repo):p.read_bytes() for p in repo.rglob('*') if p.is_file()}
            self.assertEqual(first,second)
            main=(repo/'dm/ios/Sources/main.m').read_text()
            self.assertLess(main.index('dm_startup_memory_note("play-before-preload")'),main.index('if (uses_external_data()) dm_host_preload_start'))
            self.assertEqual((repo/'dm/host/hle_uemalloc.c').read_bytes(),host)
            self.assertEqual((repo/'dm/ios/Sources/Launcher.swift').read_text().count('StartupMemoryView()'),1)

if __name__=='__main__':unittest.main()

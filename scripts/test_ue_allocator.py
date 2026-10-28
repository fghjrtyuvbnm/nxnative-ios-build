"""Run the allocator contract on Windows or macOS using synthetic backends."""
import argparse,pathlib,subprocess,sys,tempfile
from contracts import SOURCE
p=argparse.ArgumentParser();p.add_argument('repo',type=pathlib.Path);p.add_argument('--candidate',action='store_true');args=p.parse_args()
kit=pathlib.Path(__file__).resolve().parents[1]
source=subprocess.check_output(['git','-C',args.repo,'show',SOURCE+':dm/host/hle_uemalloc.c'],text=True)
core=(kit/'runtime/UEAllocatorCore.inc').read_text() if args.candidate else source[source.index('static size_t align_of'):source.index('static void *m_Malloc')]
with tempfile.TemporaryDirectory() as td:
    root=pathlib.Path(td);(root/'core-under-test.inc').write_text(core);binary=root/('test.exe' if sys.platform=='win32' else 'test')
    compiler=['clang'] if sys.platform=='win32' else ['xcrun','clang']
    subprocess.run(compiler+['-O1','-std=c11','-I'+str(root),'-I'+str(kit/'runtime'),kit/'runtime/ue_allocator_test.c','-o',binary],check=True)
    status=subprocess.run([binary],timeout=90).returncode
raise SystemExit(status)

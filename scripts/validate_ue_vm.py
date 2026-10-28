"""Baseline failure under a limited backend, full candidate contract, native GPU sharing."""
import os,pathlib,subprocess,sys
kit=pathlib.Path(__file__).resolve().parents[1];repo=pathlib.Path(sys.argv[1]);root=pathlib.Path(os.environ['RUNNER_TEMP'])/'ue-vm-tests';root.mkdir()
subprocess.run([sys.executable,kit/'scripts/validate_entitlement_diagnostics.py'],check=True)
source=subprocess.check_output(['git','-C',repo,'show','cdc6cef6b0250fcb54a061e4c55d56382b5d18ad:dm/host/hle_uemalloc.c'],text=True)
original=source[source.index('static size_t align_of'):source.index('static void *m_Malloc')]
for label,core in (('original',original),('candidate',(kit/'runtime/UEAllocatorCore.inc').read_text())):
    (root/'core-under-test.inc').write_text(core);binary=root/label
    subprocess.run(['xcrun','clang','-O1','-std=c11','-I'+str(root),'-I'+str(kit/'runtime'),kit/'runtime/ue_allocator_test.c','-o',binary],check=True)
    result=subprocess.run([binary],capture_output=True,text=True,timeout=90)
    if label=='original':
        if result.returncode!=1 or 'large!=NULL' not in result.stderr:raise ValueError('Expected limited-backend baseline failure was not observed')
        print('Original UE malloc-only policy: expected limited-backend contract failure observed',flush=True)
    else:
        if result.returncode:raise RuntimeError(result.stderr)
        print(result.stdout.strip(),flush=True)
binary=root/'metal-sharing'
subprocess.run(['xcrun','clang','-fobjc-arc','-O1','-I'+str(kit/'runtime'),kit/'runtime/ue_vm_metal_test.m','-framework','Foundation','-framework','Metal','-o',binary],check=True)
subprocess.run([binary],check=True,timeout=60,env=dict(os.environ,MTL_DEBUG_LAYER='1'))

"""Compile and run synthetic classic-GPU checks, then the current NVN geometry tests."""
import os,pathlib,shutil,subprocess,sys
repo=pathlib.Path(sys.argv[1]);kit=pathlib.Path(__file__).resolve().parents[1]
from apply_ios18 import apply
apply(repo)
base=pathlib.Path(os.environ['RUNNER_TEMP'])/'ios18-validation';base.mkdir()
binary=base/'gpu-check'
subprocess.run(['xcrun','clang','-fobjc-arc','-O1','-w','-mmacosx-version-min=15.0','-I'+str(kit/'runtime'),str(kit/'runtime/ios18_gpu_test.m'),'-framework','Metal','-framework','Foundation','-framework','QuartzCore','-o',str(binary)],check=True)
subprocess.run([str(binary)],env=dict(os.environ,MTL_DEBUG_LAYER='1'),check=True,timeout=90)
print('Standalone classic Metal GPU checks passed',flush=True)
tests=repo/'dm/gfx/tests'
subprocess.run(['make','-C',str(tests),'GAME=0100B8A026F14000','t_geometry'],check=True,stdout=subprocess.DEVNULL)
from ios18_artifact import check_imports
check_imports(subprocess.check_output(['xcrun','nm','-m',tests/'t_geometry'],text=True))
print('Current NVN classic executable has no Metal 4 imports',flush=True)
subprocess.run([str(tests/'t_geometry')],env=dict(os.environ,MTL_DEBUG_LAYER='1',DM_TEST_NO_METAL4='1'),check=True,timeout=180)
print('Current NVN geometry GPU tests passed through classic Metal',flush=True)
subprocess.run(['make','-C',str(tests),'GAME=0100B8A026F14000','t_present_crop'],check=True,stdout=subprocess.DEVNULL)
subprocess.run([str(tests/'t_present_crop')],env=dict(os.environ,MTL_DEBUG_LAYER='1'),check=True,timeout=120)
print('Current NVN presentation pixel tests passed through classic Metal',flush=True)

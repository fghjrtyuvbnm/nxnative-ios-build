"""Compile and run synthetic classic-GPU checks, then the current NVN geometry tests."""
import os,pathlib,shutil,subprocess,sys
repo=pathlib.Path(sys.argv[1]);kit=pathlib.Path(__file__).resolve().parents[1]
subprocess.run([sys.executable,kit/'scripts/validate_ios18_lifecycle.py',pathlib.Path(os.environ['RUNNER_TEMP'])/'classic-lifecycle'],check=True)
from apply_ios18 import apply
apply(repo)
from apply_ue_vm import apply as apply_vm
apply_vm(repo)
subprocess.run([sys.executable,kit/'scripts/validate_ue_vm.py',repo],check=True)
from apply_shader_pack import apply as apply_pack
apply_pack(repo)
subprocess.run([sys.executable,kit/'scripts/validate_shader_pack.py'],check=True)
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
present_test=tests/'t_present_crop.m';text=present_test.read_text()
if 'CLASSIC_SRGB_REGRESSION' not in text:
    anchor='    if([MTLFXSpatialScalerDescriptor supportsMetal4FX:g_dev]) {'
    if text.count(anchor)!=1:raise ValueError('Presentation regression insertion point changed')
    text=text.replace(anchor,(kit/'runtime/ios18_srgb_present.inc').read_text()+'\n'+anchor,1)
    present_test.write_text(text)
if 'CLASSIC_TEMPORAL_REGRESSION' not in text:
    if text.count('int main(')!=1:raise ValueError('Presentation main insertion point changed')
    text=text.replace('int main(',(kit/'runtime/ios18_temporal_present.inc').read_text()+'\nint main(',1)
    anchor='    if([MTLFXSpatialScalerDescriptor supportsMetal4FX:g_dev]) {'
    text=text.replace(anchor,'    classic_temporal_test();\n'+anchor,1)
    present_test.write_text(text)
subprocess.run(['make','-C',str(tests),'GAME=0100B8A026F14000','t_present_crop'],check=True,stdout=subprocess.DEVNULL)
subprocess.run([str(tests/'t_present_crop')],env=dict(os.environ,MTL_DEBUG_LAYER='1'),check=True,timeout=120)
print('Current NVN presentation pixel tests passed through classic Metal',flush=True)

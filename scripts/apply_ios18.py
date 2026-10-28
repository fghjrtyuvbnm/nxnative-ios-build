"""Adapt only host execution APIs; keep the completed iOS-18 shader ABI intact."""
import pathlib,shutil,subprocess,sys
from contracts import SOURCE

def once(text,old,new):
    if text.count(old)!=1:raise ValueError('Pinned Metal source anchor changed')
    return text.replace(old,new,1)

def apply(repo):
    repo=pathlib.Path(repo)
    if subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()!=SOURCE:raise ValueError('Unexpected source revision')
    source=repo/'dm/gfx/nvn/nvn_mtl.m';text=source.read_text(encoding='utf-8')
    if '#include "ios18_metal.h"' in text:return
    shutil.copyfile(pathlib.Path(__file__).resolve().parents[1]/'runtime/ios18_metal.h',source.parent/'ios18_metal.h')
    text=once(text,'#pragma clang attribute push(', '#include "ios18_metal.h"\n#pragma clang attribute push(')
    text=once(text,'g_dev = MTLCreateSystemDefaultDevice();','g_dev = dm18_device();')
    text=once(text,'if (!allocation) return;','if (!allocation) return;\n    dm18_register(g_dev, (id)allocation);')
    text=once(text,'if (getenv("DM_TEST_NO_METAL4")) no4 = "DM_TEST_NO_METAL4";',
              'if (g_dev.argumentBuffersSupport != MTLArgumentBuffersTier2) no4 = "classic Metal requires tier-2 argument buffers";')
    text=once(text,'else if (![g_dev supportsFamily:MTLGPUFamilyMetal4]) no4 = "no Metal 4 GPU family";',
              '/* Classic Metal performs no Metal-4 family check. */')
    text=once(text,'    [g_q addResidencySet:g_res];','    /* Explicit classic-encoder resource declarations replace queue residency. */')
    text=once(text,'static int pso4_on(void) {','static int pso4_on(void) {\n    return 0; // Classic render pipelines use MTLDevice, with their concrete formats.')
    text=once(text,'static int fx_mode(void) {','static int fx_mode(void) {\n    return 0; // Metal-4 MetalFX is unavailable; retain the normal bilinear present.')
    text=once(text,'if (g_present_layer_resident != layer) { [g_q4 addResidencySet:layer.residencySet]; g_present_layer_resident = layer; }',
              '/* CAMetalLayer residency sets require iOS 26; classic drawable ownership is automatic. */')
    text=text.replace('[dr presentAfterMinimumDuration:period];','(void)period;').replace('[dr present];','(void)dr;')
    text=once(text,'return (__bridge void *)g_dev;','return (__bridge void *)dm18_native(g_dev);')
    source.write_text(text,encoding='utf-8',newline='\n')
    project=repo/'dm/ios/project.yml';text=project.read_text()
    text=once(text,'iOS: "26.0"','iOS: "18.0"').replace('-mcpu=apple-a18','-mcpu=apple-a17')
    project.write_text(text,encoding='utf-8',newline='\n')

if __name__=='__main__':apply(sys.argv[1])

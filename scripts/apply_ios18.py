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
    shutil.copyfile(pathlib.Path(__file__).resolve().parents[1]/'runtime/ios18_metal.h',source.parent/'ios18_metal.h')
    project=repo/'dm/ios/project.yml';config=project.read_text()
    if 'iOS: "26.0"' in config:config=once(config,'iOS: "26.0"','iOS: "18.0"')
    elif 'iOS: "18.0"' not in config:raise ValueError('Unexpected deployment target')
    config=config.replace('-mcpu=apple-a18','-mcpu=apple-a17').replace('# Graphics replay uses Metal 4 (MTL4CommandQueue etc., from iOS 26)','# Classic Metal compatibility target')
    project.write_text(config,encoding='utf-8',newline='\n')
    settings=repo/'dm/games/settings.tsv'
    rows=settings.read_text(encoding='utf-8').splitlines()
    rows=[row for row in rows if row.split('\t',1)[0] not in ('DM_PRESENT_UPSCALE','DM_PSO_MTL4')]
    settings.write_text('\n'.join(rows)+'\n',encoding='utf-8',newline='\n')
    if '#include "ios18_metal.h"' in text:return
    text=once(text,'#pragma clang attribute push(', '#include "ios18_metal.h"\n#pragma clang attribute push(')
    text=once(text,'g_dev = MTLCreateSystemDefaultDevice();','g_dev = dm18_device();')
    text=once(text,'if (!allocation) return;','if (!allocation) return;\n    dm18_register(g_dev, (id)allocation);')
    text=once(text,'if (getenv("DM_TEST_NO_METAL4")) no4 = "DM_TEST_NO_METAL4";',
              'if (g_dev.argumentBuffersSupport != MTLArgumentBuffersTier2) no4 = "classic Metal requires tier-2 argument buffers";')
    text=once(text,'else if (![g_dev supportsFamily:MTLGPUFamilyMetal4]) no4 = "no Metal 4 GPU family";',
              '/* Classic Metal performs no Metal-4 family check. */')
    text=once(text,'    [g_q addResidencySet:g_res];','    /* Explicit classic-encoder resource declarations replace queue residency. */')
    text=once(text,'static int pso4_on(void) {','static int pso4_on(void) {\n    return 0; // Classic render pipelines use MTLDevice, with their concrete formats.')
    text=once(text,'static id<MTLFunction> fn4_note(id<MTLFunction> f, id<MTLLibrary> lib, NSString *name, MTLFunctionConstantValues *cv) {',
              '''static id<MTLFunction> fn4_note(id<MTLFunction> f, id<MTLLibrary> lib, NSString *name, MTLFunctionConstantValues *cv) {
    // Keep function identity alive as before, without constructing Metal 4 descriptors.
    if (!f || !lib || !name) return f;
    static NSHashTable *classic_functions;
    os_unfair_lock_lock(&g_fn4_lock);
    if (!classic_functions) classic_functions=[[NSHashTable alloc] initWithOptions:NSPointerFunctionsStrongMemory|NSPointerFunctionsObjectPointerPersonality capacity:0];
    [classic_functions addObject:f];
    os_unfair_lock_unlock(&g_fn4_lock);
    return f;
''')
    text=once(text,'static int fx_mode(void) {','static int fx_mode(void) {\n    return 0; // Metal-4 MetalFX is unavailable; retain the normal bilinear present.')
    text=once(text,'static int gp_active(void) {','static int gp_active(void) {\n    if (getenv("DM_NVN_GPUPROF")) { static int warned; if (!warned++) MLOG("Per-encoder GPU timing requires Metal 4 and is unavailable on the classic backend"); }\n    return 0; // Never report synthetic Metal 4 counter-heap samples.')
    text=once(text,'if (g_present_layer_resident != layer) { [g_q4 addResidencySet:layer.residencySet]; g_present_layer_resident = layer; }',
              '/* CAMetalLayer residency sets require iOS 26; classic drawable ownership is automatic. */')
    text=text.replace('[dr presentAfterMinimumDuration:period];','(void)period;').replace('[dr present];','(void)dr;')
    text=once(text,'return (__bridge void *)g_dev;','return (__bridge void *)dm18_native(g_dev);')
    source.write_text(text,encoding='utf-8',newline='\n')

if __name__=='__main__':apply(sys.argv[1])

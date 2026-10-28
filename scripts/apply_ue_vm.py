"""Separate large UE allocations from the host malloc-zone address range."""
import pathlib,shutil
def apply(repo):
    root=pathlib.Path(repo)/'dm/host';runtime=pathlib.Path(__file__).resolve().parents[1]/'runtime'
    shutil.copyfile(runtime/'UELargeVM.h',root/'UELargeVM.h')
    path=root/'hle_uemalloc.c';text=path.read_text()
    if 'UE_LARGE_VM_POLICY' in text:return
    if '#include "MemoryDiagnostics.h"' in text:raise ValueError('Apply VM policy before diagnostic instrumentation')
    first=text.index('static size_t align_of(');last=text.index('static void *m_Malloc',first)
    text=text[:first]+(runtime/'UEAllocatorCore.inc').read_text()+text[last:]
    old='return malloc_good_size(n);'
    if text.count(old)!=1:raise ValueError('UE quantization anchor changed')
    text=text.replace(old,'return n>=UE_VM_THRESHOLD?ue_vm_round(n):malloc_good_size(n);')
    old='*out = malloc_size(p);'
    if text.count(old)!=1:raise ValueError('UE size-query anchor changed')
    text=text.replace(old,'*out = ue_size(p);')
    old='malloc_set_zone_name(g_zone, "guest Unreal heap");'
    if text.count(old)!=1:raise ValueError('UE allocator log anchor changed')
    text=text.replace(old,old+' LOG("UE allocation policy: VM backing for blocks at least 1 MiB");')
    path.write_text(text,encoding='utf-8',newline='\n')

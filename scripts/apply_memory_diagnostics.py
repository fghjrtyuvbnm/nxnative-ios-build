"""Record real process memory at startup and allocator failure; do not change limits."""
import pathlib,shutil
def apply(repo):
    repo=pathlib.Path(repo);runtime=pathlib.Path(__file__).resolve().parents[1]/'runtime'
    for folder in ('dm/host','dm/ios/Sources','dm/gfx/nvn'):
        shutil.copyfile(runtime/'MemoryDiagnostics.h',repo/folder/'MemoryDiagnostics.h')
    shutil.copyfile(runtime/'UEAllocationDiagnostics.inc',repo/'dm/host/UEAllocationDiagnostics.inc')
    shutil.copyfile(runtime/'EntitlementDiagnostics.h',repo/'dm/ios/Sources/EntitlementDiagnostics.h')
    p=repo/'dm/host/hle_uemalloc.c';s=p.read_text()
    if '#include "MemoryDiagnostics.h"' not in s:
        s=s.replace('#include "hle.h"','#include "hle.h"\n#include "MemoryDiagnostics.h"',1)
        old='if (!p) die("Unreal heap: out of memory (%zu bytes, alignment %u, %.2f GB in use)", n, a, atomic_load(&g_used) / 1073741824.0);'
        if s.count(old)!=1:raise ValueError('Malloc failure anchor changed')
        s=s.replace(old,'if (!p) { dm_memory_note("ue-malloc-failed"); '+old.removeprefix('if (!p) ')+' }')
        old='if (!q && n) die("Unreal heap: out of memory in Realloc (%zu bytes, alignment %u, %.2f GB in use)", n, a, atomic_load(&g_used) / 1073741824.0);'
        if s.count(old)!=1:raise ValueError('Realloc failure anchor changed')
        s=s.replace(old,'if (!q && n) { dm_memory_note("ue-realloc-failed"); '+old.removeprefix('if (!q && n) ')+' }')
        old='g_zone = malloc_create_zone(0, 0);'
        if s.count(old)!=1:raise ValueError('Zone creation anchor changed')
        s=s.replace(old,'dm_memory_note("ue-install"); '+old)
    if '#include "UEAllocationDiagnostics.inc"' not in s:
        s=s.replace('static void *m_Malloc(void *self, size_t n, uint32_t a) {','#include "UEAllocationDiagnostics.inc"\nstatic void *m_Malloc(void *self, size_t n, uint32_t a) {',1)
        s=s.replace('dm_memory_note("ue-malloc-failed");','int native_error=errno; dm_memory_note("ue-malloc-failed"); ue_allocation_failure("malloc",NULL,n,a,native_error);',1)
        s=s.replace('dm_memory_note("ue-realloc-failed");','int native_error=errno; dm_memory_note("ue-realloc-failed"); ue_allocation_failure("realloc",p,n,a,native_error);',1)
    p.write_text(s,encoding='utf-8',newline='\n')
    p=repo/'dm/ios/Sources/main.m';s=p.read_text()
    if '#include "MemoryDiagnostics.h"' not in s:
        s=s.replace('#include <stdio.h>','#include <stdio.h>\n#include "MemoryDiagnostics.h"',1)
        old='    // Environment switch files'
        if s.count(old)!=1:raise ValueError('Boot logging anchor changed')
        s=s.replace(old,'    dm_memory_note("app-boot");\n'+old,1)
        old='    if (uses_external_data()) dm_host_preload_start(g_argc, g_argv);'
        if s.count(old)!=1:raise ValueError('External play anchor changed')
        s=s.replace(old,'    dm_memory_note("play-before-preload");\n'+old,1)
        p.write_text(s,encoding='utf-8',newline='\n')
    s=p.read_text()
    if '#include "EntitlementDiagnostics.h"' not in s:
        s=s.replace('#include "MemoryDiagnostics.h"','#include "MemoryDiagnostics.h"\n#include "EntitlementDiagnostics.h"',1)
        s=s.replace('dm_memory_note("app-boot");','dm_memory_note("app-boot"); dm_signing_memory_note();',1)
        p.write_text(s,encoding='utf-8',newline='\n')

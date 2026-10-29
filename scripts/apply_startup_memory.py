"""Visible, read-only installed-signing and advisory-memory checks before gameplay."""
import pathlib, shutil
from apply_runtime import replace_once

def apply(repo):
    repo=pathlib.Path(repo);kit=pathlib.Path(__file__).resolve().parents[1]
    sources=repo/'dm/ios/Sources'
    for name in ('StartupMemoryState.swift','StartupMemoryView.swift','StartupMemoryCheck.h'):
        shutil.copyfile(kit/'runtime'/name,sources/name)
    main=sources/'main.m';text=main.read_text()
    if '#include "StartupMemoryCheck.h"' not in text:
        text=replace_once(text,'#include "EntitlementDiagnostics.h"','#include "EntitlementDiagnostics.h"\n#include "StartupMemoryCheck.h"')
        text=replace_once(text,'dm_signing_memory_note();','dm_signing_memory_note(); dm_startup_memory_note("app-boot");')
        text=replace_once(text,'dm_memory_note("play-before-preload");','dm_memory_note("play-before-preload"); dm_startup_memory_note("play-before-preload");')
        main.write_text(text,encoding='utf-8',newline='\n')
    launcher=sources/'Launcher.swift';text=launcher.read_text()
    if 'StartupMemoryView()' not in text:
        text=replace_once(text,'                List {','                List {\n                    StartupMemoryView()')
        launcher.write_text(text,encoding='utf-8',newline='\n')

if __name__=='__main__':
    import sys
    apply(sys.argv[1])

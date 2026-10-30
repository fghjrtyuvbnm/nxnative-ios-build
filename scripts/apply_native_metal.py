"""Preserve the upstream native Metal 4 backend for iPadOS 27 devices."""
import pathlib

def apply(repo):
    repo=pathlib.Path(repo)
    source=(repo/'dm/gfx/nvn/nvn_mtl.m').read_text()
    if 'ios18_metal.h' in source or 'dm18_device()' in source:raise ValueError('Native build must start without the classic adapter')
    if 'g_dev = MTLCreateSystemDefaultDevice();' not in source:raise ValueError('Expected native Metal device initialization')
    project=repo/'dm/ios/project.yml';s=project.read_text()
    if 'iOS: "26.0"' not in s:raise ValueError('Native Metal requires the upstream iOS 26 deployment target')
    s=s.replace('-mcpu=apple-a18','-mcpu=apple-a17');project.write_text(s,encoding='utf-8',newline='\n')
    main=repo/'dm/ios/Sources/main.m';s=main.read_text()
    s=s.replace('[classic-lifecycle] independent helper queues; bounded weak registry pools; wait ledger enabled','[native-metal4] upstream device, queues and resource residency; wait ledger enabled')
    main.write_text(s,encoding='utf-8',newline='\n')

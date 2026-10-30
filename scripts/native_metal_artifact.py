"""Audit an unsigned native Metal 4 executable, independent of its file name."""
import pathlib,plistlib,struct,subprocess

def check_macho(binary):
    if len(binary)<32:raise ValueError('Truncated executable')
    magic,cpu,subtype,kind,count,size,flags,reserved=struct.unpack_from('<8I',binary)
    if (magic,cpu,kind)!=(0xfeedfacf,0x0100000c,2) or size>len(binary)-32:raise ValueError('Expected ARM64 device executable')
    pos=32;targets=[]
    for _ in range(count):
        if pos+8>32+size:raise ValueError('Truncated command')
        command,length=struct.unpack_from('<II',binary,pos)
        if length<8 or pos+length>32+size:raise ValueError('Invalid command')
        if command==0x1d:raise ValueError('Expected unsigned executable')
        if command==0x32:
            if length<24:raise ValueError('Truncated platform command')
            targets.append(struct.unpack_from('<II',binary,pos+8))
        pos+=length
    if pos!=32+size or targets!=[(2,26<<16)]:raise ValueError('Expected native iOS-device minimum 26.0')
    if b'DM18Registry' in binary or b'[classic-lifecycle]' in binary:raise ValueError('Classic adapter remains')
    if b'[native-metal4]' not in binary:raise ValueError('Native backend diagnostic missing')
    return {'macho':'arm64-ios','minimum_ios':'26.0','signed':False,'classic_adapter_present':False}

def audit_app(app):
    app=pathlib.Path(app);info=plistlib.loads((app/'Info.plist').read_bytes())
    if info.get('MinimumOSVersion')!='26.0' or info.get('DMGraphicsCompatibility')!='native-metal4' or info.get('DMExternalGameData') is not True:raise ValueError('Wrong native application metadata')
    binary=app/info['CFBundleExecutable'];result=check_macho(binary.read_bytes())
    imports=subprocess.check_output(['xcrun','nm','-m',binary],text=True)
    lines=[line for line in imports.splitlines() if '(undefined)' in line and 'MTL4' in line]
    if not lines:raise ValueError('Native Metal 4 imports absent')
    result.update(metal4_imports=len(lines))
    if (app/'embedded.mobileprovision').exists() or (app/'_CodeSignature').exists():raise ValueError('Unexpected signing resources')
    return result

"""Validate the real device executable's deployment target, independently of Info.plist."""
import pathlib,plistlib,struct,subprocess

def check_imports(imports):
    unavailable=[line for line in imports.splitlines() if '(undefined)' in line and 'MTL4' in line]
    if unavailable:raise ValueError('Classic executable still imports Metal 4 objects: '+', '.join(line.split()[-1] for line in unavailable))
    return {'strong_metal4_imports':0,'weak_metal4_imports':0}

def check_macho(binary):
    if len(binary)<32:raise ValueError('Truncated executable')
    magic,cpu,subtype,filetype,ncmds,size,flags,reserved=struct.unpack_from('<8I',binary)
    if magic!=0xfeedfacf or cpu!=0x0100000c or filetype!=2:raise ValueError('Expected an arm64 device executable')
    if size>len(binary)-32:raise ValueError('Invalid command region')
    offset=32;targets=[]
    for _ in range(ncmds):
        if offset+8>32+size:raise ValueError('Truncated load command')
        command,length=struct.unpack_from('<II',binary,offset)
        if length<8 or offset+length>32+size:raise ValueError('Invalid load command size')
        if command==0x1d:raise ValueError('Unexpected embedded code signature')
        if command==0x32:
            if length<24:raise ValueError('Truncated platform command')
            platform,minimum=struct.unpack_from('<II',binary,offset+8);targets.append((platform,minimum))
        offset+=length
    if offset!=32+size or targets!=[(2,18<<16)]:raise ValueError('Executable is not iOS-device minimum 18.0')
    return {'macho':'arm64-ios','minimum_ios':'18.0','signed':False}

def audit_app(app):
    app=pathlib.Path(app);info=plistlib.loads((app/'Info.plist').read_bytes())
    if info.get('MinimumOSVersion')!='18.0' or info.get('DMExternalGameData') is not True:raise ValueError('Wrong app deployment or data mode')
    binary=app/info['CFBundleExecutable'];result=check_macho(binary.read_bytes())
    imports=subprocess.check_output(['xcrun','nm','-m',binary],text=True)
    result.update(check_imports(imports))
    return result

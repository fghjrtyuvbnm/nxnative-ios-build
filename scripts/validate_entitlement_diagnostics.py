"""Synthetic signature/profile fixtures; never read an account or real profile."""
import os,pathlib,plistlib,struct,subprocess
kit=pathlib.Path(__file__).resolve().parents[1];root=pathlib.Path(os.environ['RUNNER_TEMP'])/'signing-observation-tests';root.mkdir()
memory='com.apple.developer.kernel.increased-memory-limit';address='com.apple.developer.kernel.extended-virtual-addressing'
marker='SYNTHETIC_PRIVATE_MARKER'
xml=plistlib.dumps({memory:True,address:False,'application-identifier':marker})
blob=struct.pack('>II',0xfade7171,len(xml)+8)+xml
signature=struct.pack('>IIIII',0xfade0cc0,len(blob)+20,1,5,20)+blob
def macho(sig):
    return struct.pack('<8I',0xfeedfacf,0x100000c,0,2,1,16,0,0)+struct.pack('<4I',0x1d,16,256,len(sig))+b'\0'*(256-48)+sig
(root/'app').write_bytes(macho(signature))
(root/'unsigned').write_bytes(struct.pack('<8I',0xfeedfacf,0x100000c,0,2,0,0,0,0))
(root/'truncated').write_bytes(macho(signature)[:-10])
bad=bytearray(signature);struct.pack_into('>I',bad,16,0xffffffff);(root/'invalid').write_bytes(macho(bad))
(root/'der-only').write_bytes(macho(struct.pack('>IIIII',0xfade0cc0,28,1,7,20)+struct.pack('>II',0xfade7172,8)))
profile=plistlib.dumps({'Entitlements':{memory:False,address:True,'application-identifier':marker}})
(root/'profile').write_bytes(b'synthetic-cms-prefix'+profile+b'synthetic-cms-suffix')
(root/'bad-profile').write_bytes(b'not a profile')
binary=root/'check'
subprocess.run(['xcrun','clang','-fobjc-arc','-O1','-I'+str(kit/'runtime'),kit/'runtime/entitlement_diagnostics_test.m','-framework','Foundation','-o',binary],check=True)
result=subprocess.run([binary,root],capture_output=True,text=True,check=True,timeout=30)
if marker in result.stdout+result.stderr:raise ValueError('Private synthetic field leaked into output')
if 'signed_memory_request=1 signed_extended_va_request=0 profile_memory_permission=0 profile_extended_va_permission=1' not in result.stderr:raise ValueError('Signing layers were not distinguished')
print(result.stdout.strip(),flush=True)

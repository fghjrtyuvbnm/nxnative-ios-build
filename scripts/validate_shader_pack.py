"""Synthetic cross-language and GPU checks, no game inputs or private credentials."""
import json,os,pathlib,shutil,subprocess,sys
from shader_pack import pack
kit=pathlib.Path(__file__).resolve().parents[1]
root=pathlib.Path(os.environ['RUNNER_TEMP'])/'shader-pack-tests';root.mkdir()
loose=root/'loose';loose.mkdir()
source=root/'test.metal';source.write_text('#include <metal_stdlib>\nusing namespace metal;\nkernel void main0(device uint *out [[buffer(0)]]){out[0]=0x1234abcd;}\n')
subprocess.run(['xcrun','-sdk','macosx','metal','-c',source,'-o',root/'test.air'],check=True)
subprocess.run(['xcrun','-sdk','macosx','metallib',root/'test.air','-o',loose/'fixture_b.metallib'],check=True)
(loose/'fixture_b.json').write_text('{"entry":"main0"}')
pack(loose,root/'packed')
for name in ('corrupt','truncated','invalid'):shutil.copytree(root/'packed',root/name)
p=root/'corrupt/shaders.pack';data=bytearray(p.read_bytes());data[-1]^=1;p.write_bytes(data)
p=root/'truncated/shaders.pack';p.write_bytes(p.read_bytes()[:-1])
p=root/'invalid/shaders.index.json';m=json.loads(p.read_text());m['entries']['fixture_b.metallib'][0]=-1;p.write_text(json.dumps(m))
binary=root/'native-check'
subprocess.run(['xcrun','clang','-fobjc-arc','-O1','-I'+str(kit/'runtime'),kit/'runtime/shader_pack_test.m','-framework','Foundation','-framework','Metal','-o',binary],check=True)
subprocess.run([binary,root],check=True,timeout=60,env=dict(os.environ,MTL_DEBUG_LAYER='1'))

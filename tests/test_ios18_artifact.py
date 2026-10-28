import pathlib,plistlib,struct,sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from ios18_artifact import check_macho,audit_app

def executable(platform=2,minimum=18,command=0x32):
    return struct.pack('<8I',0xfeedfacf,0x0100000c,0,2,1,24,0,0)+struct.pack('<6I',command,24,platform,minimum<<16,26<<16,0)

class IOS18Artifact(unittest.TestCase):
    def test_even_weak_metal4_descriptors_are_rejected_from_classic_build(self):
        with tempfile.TemporaryDirectory() as td:
            app=pathlib.Path(td);(app/'Info.plist').write_bytes(plistlib.dumps({'MinimumOSVersion':'18.0','DMExternalGameData':True,'CFBundleExecutable':'Game'}));(app/'Game').write_bytes(executable())
            imports='                 (undefined) weak external _OBJC_CLASS_$_MTL4LibraryFunctionDescriptor\n'
            with patch('ios18_artifact.subprocess.check_output',return_value=imports):
                with self.assertRaises(ValueError):audit_app(app)
    def test_device_binary_is_checked_independently_of_plist(self):
        self.assertEqual(check_macho(executable())['minimum_ios'],'18.0')
        for data in (executable(minimum=26),executable(platform=7),executable(command=0x1d),executable()[:-1]):
            with self.assertRaises(ValueError):check_macho(data)

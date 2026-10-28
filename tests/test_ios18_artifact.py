import pathlib,struct,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from ios18_artifact import check_macho

def executable(platform=2,minimum=18,command=0x32):
    return struct.pack('<8I',0xfeedfacf,0x0100000c,0,2,1,24,0,0)+struct.pack('<6I',command,24,platform,minimum<<16,26<<16,0)

class IOS18Artifact(unittest.TestCase):
    def test_device_binary_is_checked_independently_of_plist(self):
        self.assertEqual(check_macho(executable())['minimum_ios'],'18.0')
        for data in (executable(minimum=26),executable(platform=7),executable(command=0x1d),executable()[:-1]):
            with self.assertRaises(ValueError):check_macho(data)

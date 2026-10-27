import json
import pathlib
import plistlib
import sys
import tempfile
import unittest
import zipfile
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from contracts import TITLE,BUILD,sha256
from transfer import split_file
from finish_windows import finish

class Finish(unittest.TestCase):
    def setup_input(self,root,signed=False):
        d=root/'download';d.mkdir();zpath=root/'source.ipa'
        with zipfile.ZipFile(zpath,'w') as z:
            z.writestr('Payload/DmIOS.app/Info.plist',plistlib.dumps({'CFBundleIdentifier':'org.nxnative.'+TITLE.lower(),'CFBundleExecutable':'DmIOS'}))
            i=zipfile.ZipInfo('Payload/DmIOS.app/DmIOS');i.create_system=3;i.external_attr=0o100755<<16
            z.writestr(i,b'fixture executable')
            z.writestr('Payload/DmIOS.app/msl/b-test/a.metallib',b'shader')
            if signed:z.writestr('Payload/DmIOS.app/_CodeSignature/CodeResources',b'signature')
        m={'title_id':TITLE,'main_build':BUILD,'template_sha256':sha256(zpath),'parts':split_file(zpath,d,'template',chunk=512)}
        (d/'result-manifest.json').write_text(json.dumps(m))
        w=root/'game';p=w/'extract/v1/RomFS/FFRS/Content/Paks/FFRS-Switch.ucas';p.parent.mkdir(parents=True);p.write_bytes(b'fixture romfs')
        return d,w

    def test_full_local_pack_preserves_code_modes_and_romfs(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td);d,w=self.setup_input(root);out=root/'final.ipa'
            finish(d,w,out)
            with zipfile.ZipFile(out) as z:
                self.assertEqual(z.getinfo('Payload/DmIOS.app/DmIOS').external_attr>>16 & 0o777,0o755)
                self.assertEqual(z.read('Payload/DmIOS.app/romfs/FFRS/Content/Paks/FFRS-Switch.ucas'),b'fixture romfs')
                self.assertEqual(z.getinfo('Payload/DmIOS.app/romfs/FFRS/Content/Paks/FFRS-Switch.ucas').compress_type,zipfile.ZIP_STORED)
            self.assertTrue(json.loads(out.with_suffix('.verification.json').read_text())['zip_crc_verified'])

    def test_signed_template_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td);d,w=self.setup_input(root,True)
            with self.assertRaises(ValueError):finish(d,w,root/'final.ipa')
            self.assertFalse((root/'final.ipa').exists())

if __name__=='__main__':unittest.main()

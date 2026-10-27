import hashlib
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
import external_pack as e

class ExternalPack(unittest.TestCase):
    def fixture(self,root,external=True):
        download=root/'download';download.mkdir();source=root/'source.ipa'
        identity={'title_id':TITLE,'main_build':BUILD,'shader_chain':'test','shader_inputs':'input'}
        info={'CFBundleIdentifier':'org.nxnative.'+TITLE.lower(),'CFBundleExecutable':'DmIOS','DMExternalGameData':external,'DMExternalDataVersion':1,'DMExternalDataIdentity':identity}
        with zipfile.ZipFile(source,'w') as z:
            z.writestr('Payload/DmIOS.app/Info.plist',plistlib.dumps(info))
            executable=zipfile.ZipInfo('Payload/DmIOS.app/DmIOS');executable.create_system=3;executable.external_attr=0o100755<<16
            z.writestr(executable,b'fixture code')
            z.writestr('Payload/DmIOS.app/msl/b-test/inputs.tsv',f'game\t{TITLE}\ninputs\tinput\n')
            z.writestr('Payload/DmIOS.app/msl/b-test/a_b.metallib',b'fixture library')
            z.writestr('Payload/DmIOS.app/aoc/2/content',b'dlc')
        m={'title_id':TITLE,'main_build':BUILD,'external_data_runtime':external,'template_sha256':sha256(source),'parts':split_file(source,download,'template',chunk=512)}
        (download/'result-manifest.json').write_text(json.dumps(m))
        work=root/'game';romfs=work/'extract/v1/RomFS/FFRS/Content/Paks';romfs.mkdir(parents=True)
        (romfs/'FFRS-Switch.ucas').write_bytes(b'fixture game assets')
        return download,work,identity

    def test_split_output_reopen_and_data_reuse(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td);d,w,identity=self.fixture(root);out=root/'launcher.ipa'
            report=e.finish_external(d,w,out)
            data=root/'FFRS-Data'
            self.assertEqual(json.loads((data/'game-data.json').read_text())['identity'],identity)
            self.assertEqual((data/'romfs/FFRS/Content/Paks/FFRS-Switch.ucas').read_bytes(),b'fixture game assets')
            self.assertEqual((data/'msl/b-test/a_b.metallib').read_bytes(),b'fixture library')
            with zipfile.ZipFile(out) as z:
                self.assertFalse(any(n.startswith(('Payload/DmIOS.app/msl/','Payload/DmIOS.app/romfs/','Payload/DmIOS.app/aoc/')) for n in z.namelist()))
                self.assertEqual(z.getinfo('Payload/DmIOS.app/DmIOS').external_attr>>16 & 0o777,0o755)
            e.verify_data(data,identity)
            e.finish_external(d,w,root/'launcher-updated.ipa')
            self.assertTrue(report['data_separate'])
            self.assertFalse(list(data.rglob('*.keys')))

    def test_existing_corrupt_data_not_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td);d,w,identity=self.fixture(root);e.finish_external(d,w,root/'a.ipa')
            p=root/'FFRS-Data/msl/b-test/a_b.metallib';p.write_bytes(b'changed')
            with self.assertRaises(ValueError):e.finish_external(d,w,root/'b.ipa')
            self.assertEqual(p.read_bytes(),b'changed')

    def test_legacy_template_is_not_shipped_as_external_launcher(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td);d,w,_=self.fixture(root,False)
            with self.assertRaises(ValueError):e.finish_external(d,w,root/'bad.ipa')
            self.assertFalse((root/'bad.ipa').exists())

    def test_archive_paths_cannot_escape(self):
        for name in ['Payload/DmIOS.app/../../secret','/Payload/DmIOS.app/a','Payload\\DmIOS.app\\a','Other/a']:
            with self.subTest(name=name),self.assertRaises(ValueError):e.check_archive_name(name)

if __name__=='__main__':unittest.main()

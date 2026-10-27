import json,pathlib,tempfile,unittest
import test_external_pack as fixtures
import external_pack
import cloud_publish_launcher as cloud
from contracts import sha256

class CloudPublish(unittest.TestCase):
    def test_same_bytes_as_verified_windows_export_and_reject_wrong_hash(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td);download,work,_=fixtures.ExternalPack().fixture(root)
            local=root/'windows.ipa';report=external_pack.finish_external(download,work,local)
            out=cloud.export(download,report,root/'cloud.ipa')
            self.assertEqual(out.read_bytes(),local.read_bytes())
            report['launcher_sha256']='0'*64
            with self.assertRaises(ValueError):cloud.export(download,report,root/'wrong.ipa')
            self.assertFalse((root/'wrong.ipa').exists())

    def test_unverified_windows_data_cannot_be_published(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td);download,work,_=fixtures.ExternalPack().fixture(root)
            report=external_pack.finish_external(download,work,root/'windows.ipa')
            report['data_sha256_verified']=False
            with self.assertRaises(ValueError):cloud.export(download,report,root/'cloud.ipa')

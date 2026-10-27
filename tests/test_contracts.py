import hashlib
import io
import json
import pathlib
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import contracts as c

class Contracts(unittest.TestCase):
    def test_reject_unsafe_archive_names(self):
        for name in ['../keys', '/etc/keys', 'extract/../../keys', 'C:/keys', 'extract\\keys', 'prod.keys', 'extract/v1/prod.keys']:
            with self.subTest(name=name), self.assertRaises(ValueError): c.check_name(name)

    def test_accept_only_expected_roots(self):
        for name in ['extract/v1/ExeFS/main', 'extract/v1/RomFS/a', 'patched_v1/main.patched.bin', 'aoc/2/a']:
            c.check_name(name)

    def test_archive_rejects_symlinks(self):
        with tempfile.TemporaryDirectory() as td:
            p=pathlib.Path(td)/'bad.tar'
            with tarfile.open(p,'w') as t:
                i=tarfile.TarInfo('extract/v1/link'); i.type=tarfile.SYMTYPE; i.linkname='/etc/passwd'; t.addfile(i)
            with self.assertRaises(ValueError): c.unpack(p,pathlib.Path(td)/'out')

    def test_round_trip_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td); src=root/'src'; (src/'patched_v1').mkdir(parents=True)
            (src/'patched_v1/main.patched.bin').write_bytes(b'game-code')
            manifest=c.make_manifest(src)
            c.verify(src,manifest)
            (src/'patched_v1/main.patched.bin').write_bytes(b'tampered')
            with self.assertRaises(ValueError): c.verify(src,manifest)

    def test_manifest_rejects_wrong_build(self):
        with self.assertRaises(ValueError): c.check_identity({'title_id':'0100606026F12000','main_build':'wrong'})

    def test_manifest_accepts_hk_build(self):
        c.check_identity({'title_id':c.TITLE,'main_build':c.BUILD})

if __name__=='__main__': unittest.main()

import os
import pathlib
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
import pipeline

class PrivateBoundary(unittest.TestCase):
    def test_public_runner_never_reads_release_from_public_code_repository(self):
        calls=[]
        class Result:
            returncode=0
        with patch.dict(os.environ,{'GITHUB_REPOSITORY':'fghjrtyuvbnm/nxnative-ios-build'}),patch.object(pipeline,'gh',side_effect=lambda *a,**kw: calls.append(a) or Result()):
            pipeline.release_exists('private-cache')
        self.assertEqual(calls[0][calls[0].index('--repo')+1],'fghjrtyuvbnm/ffr-nxnative-private-build')

if __name__=='__main__':unittest.main()

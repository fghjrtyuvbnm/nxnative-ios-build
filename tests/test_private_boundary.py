import os
import pathlib
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
import pipeline
import private_io

class PrivateBoundary(unittest.TestCase):
    def test_public_runner_never_reads_release_from_public_code_repository(self):
        calls=[]
        class Result:
            returncode=0
        with patch.dict(os.environ,{'GITHUB_REPOSITORY':'fghjrtyuvbnm/nxnative-ios-build'}),patch.object(pipeline,'gh',side_effect=lambda *a,**kw: calls.append(a) or Result()):
            pipeline.release_exists('private-cache')
        self.assertEqual(calls[0][calls[0].index('--repo')+1],'fghjrtyuvbnm/ffr-nxnative-private-build')

    def test_public_destination_and_missing_private_credential_fail_before_network(self):
        with patch.dict(os.environ,{'GITHUB_REPOSITORY':'fghjrtyuvbnm/nxnative-ios-build'},clear=True),patch('private_io.subprocess.run') as run:
            with self.assertRaises(ValueError):private_io.gh('release','upload','x','--repo','fghjrtyuvbnm/nxnative-ios-build','x.ipa')
            with self.assertRaises(ValueError):private_io.gh('release','view','x','--repo',private_io.DATA_REPOSITORY)
            run.assert_not_called()

    def test_data_calls_use_separate_credential_and_private_destination_is_checked(self):
        with patch.dict(os.environ,{'GITHUB_REPOSITORY':'fghjrtyuvbnm/nxnative-ios-build','GH_TOKEN':'public-fixture','PRIVATE_DATA_TOKEN':'private-fixture'},clear=True),patch('private_io.subprocess.run') as run:
            run.return_value.returncode=0;run.return_value.stdout='{"private":false}'
            with self.assertRaises(ValueError):private_io.assert_private()
            self.assertEqual(run.call_args.kwargs['env']['GH_TOKEN'],'private-fixture')
            self.assertEqual(run.call_args.args[0][2],'repos/'+private_io.DATA_REPOSITORY)

if __name__=='__main__':unittest.main()

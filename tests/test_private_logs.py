"""Real child processes must not send private tool output to public job logs."""
import contextlib
import io
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
import private_job

class PrivateLogs(unittest.TestCase):
    def test_success_and_failure_both_capture_raw_child_output_privately(self):
        original_popen=subprocess.Popen;original_sleep=time.sleep
        marker='fixture-private-game-payload'
        for status in (0,7):
            with self.subTest(status=status),tempfile.TemporaryDirectory() as td:
                work=pathlib.Path(td);public=io.StringIO()
                def launch(command,**kwargs):
                    return original_popen([sys.executable,'-c',f'import sys;print({marker!r});print({marker!r},file=sys.stderr);sys.exit({status})'],**kwargs)
                with patch('private_job.assert_private'),patch('private_job.save_logs') as saved,patch('private_job.subprocess.Popen',side_effect=launch),patch('private_job.time.sleep',side_effect=lambda _:original_sleep(0.01)),contextlib.redirect_stdout(public):
                    if status:
                        with self.assertRaises(SystemExit) as error:private_job.main('shard','fixture-engine',work,'0')
                        self.assertEqual(error.exception.code,status)
                    else:private_job.main('shard','fixture-engine',work,'0')
                    saved.assert_called_once_with(work.resolve())
                self.assertNotIn(marker,public.getvalue())
                self.assertEqual((work/'logs/private-job.log').read_text().count(marker),2)

if __name__=='__main__':unittest.main()

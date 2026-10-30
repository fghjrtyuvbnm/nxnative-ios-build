import os,pathlib,sys,tempfile,unittest
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
import private_job

class ResourceOnlyJob(unittest.TestCase):
    def test_resource_only_success_does_not_publish_missing_ipa(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'RESOURCE_ONLY':'1'}),patch.object(private_job,'assert_private'),patch.object(private_job,'save_logs'),patch.object(private_job,'publish_template') as publish,patch.object(private_job.subprocess,'run',return_value=SimpleNamespace(returncode=0)),patch.object(private_job.subprocess,'Popen',return_value=SimpleNamespace(returncode=0,poll=lambda:0)):
            private_job.main('assemble',tmp,tmp)
            publish.assert_not_called()

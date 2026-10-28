"""Reproduce the current NVN contract failure on a device without Metal 4."""
import json,os,pathlib,subprocess,sys
repo=pathlib.Path(sys.argv[1]);tests=repo/'dm/gfx/tests'
subprocess.run(['make','-C',str(tests),'GAME=0100B8A026F14000','t_nvn'],check=True,stdout=subprocess.DEVNULL)
p=subprocess.run([str(tests/'t_nvn')],env=dict(os.environ,DM_TEST_NO_METAL4='1'),capture_output=True,text=True,timeout=60)
expected=p.returncode!=0 and 'which the NVN layer needs' in p.stderr and 'DM_TEST_NO_METAL4' in p.stderr
print(json.dumps({'unmodified_backend':True,'expected_behavioral_failure_observed':expected,'exit_code':p.returncode}),flush=True)
if not expected:
    print(p.stderr[-2000:]);raise SystemExit('The expected backend failure was not reproduced')

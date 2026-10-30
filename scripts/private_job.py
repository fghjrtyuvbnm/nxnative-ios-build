"""Run data-bearing tools without sending their raw output to public Actions logs."""
import os
import pathlib
import subprocess
import sys
import time
import json
from private_io import assert_private, download_input, download_resources, publish_template, save_logs, shader_live, PROGRESS_STAGES

def main(mode,repo,work,*args):
    assert_private()
    work=pathlib.Path(work).resolve();logs=work/'logs';logs.mkdir(parents=True,exist_ok=True)
    start=time.monotonic();status=1;live_at=0
    try:
        with (logs/'private-job.log').open('w') as log:
            if mode in ('assemble','launcher','launcher18','launcher-native'):
                # Also suppress transfer diagnostics in the public job.
                p=subprocess.run([sys.executable,pathlib.Path(__file__).with_name('private_io.py'),'input',work],stdout=log,stderr=subprocess.STDOUT)
                if p.returncode:raise RuntimeError('Private input restore failed')
            if mode in ('launcher','launcher18','launcher-native'):
                resources=download_resources(work,args[0])
                command=[sys.executable,'-u',pathlib.Path(__file__).with_name('build_external_launcher.py'),repo,work,resources,args[0]]
            else:command=[sys.executable,'-u',pathlib.Path(__file__).with_name('pipeline.py'),mode,repo,work,*args]
            child=subprocess.Popen(list(map(str,command)),stdout=log,stderr=subprocess.STDOUT)
            while child.poll() is None:
                stage='running'
                try:
                    value=json.loads((work/('build-progress-'+os.environ['GITHUB_RUN_ID']+'.json')).read_text())
                    if value['stage'] in PROGRESS_STAGES:stage=f"{value['stage']} {int(value['current'])}/{int(value['total'])}"
                    if value['stage']=='cached-shader-pass' and time.monotonic()-live_at>=120:
                        shader_live(work);live_at=time.monotonic()
                except (OSError,ValueError,KeyError):pass
                print(f'{mode}: {stage}; elapsed {round(time.monotonic()-start)}s; raw diagnostics remain private',flush=True)
                time.sleep(30)
            status=child.returncode
        if status==0 and mode in ('assemble','launcher') and os.environ.get('RESOURCE_ONLY')!='1':publish_template(work)
        if status==0 and mode in ('launcher18','launcher-native'):
            from private_io import publish_ios18
            publish_ios18(work)
    finally:
        save_logs(work)
    if status:raise SystemExit(status)
    print(f'{mode}: completed; data and output remain in the private repository',flush=True)

if __name__=='__main__':main(*sys.argv[1:])

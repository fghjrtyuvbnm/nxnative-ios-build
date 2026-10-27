"""Keep every data transfer in the fixed private repository, even from a public runner."""
import json
import os
import pathlib
import subprocess
import sys

DATA_REPOSITORY='fghjrtyuvbnm/ffr-nxnative-private-build'

def data_repository():return DATA_REPOSITORY

def data_run():
    value=os.environ.get('DATA_BUILD_ID',os.environ.get('GITHUB_RUN_ID',''))
    if not value.isdigit():raise ValueError('Data build ID must be numeric')
    return value

def gh(*args,check=True):
    args=list(map(str,args))
    if '--repo' in args and args[args.index('--repo')+1]!=DATA_REPOSITORY:raise ValueError('Data transfer cannot target a public repository')
    if args and args[0]=='api' and not args[1].startswith('repos/'+DATA_REPOSITORY):raise ValueError('Unexpected data API target')
    env=dict(os.environ)
    if env.get('PRIVATE_DATA_TOKEN'):env['GH_TOKEN']=env['PRIVATE_DATA_TOKEN']
    elif env.get('GITHUB_REPOSITORY') not in (None,DATA_REPOSITORY):raise ValueError('Set PRIVATE_DATA_TOKEN for the fixed private data repository')
    p=subprocess.run(['gh',*args],env=env,text=True,capture_output=True)
    if check and p.returncode:raise RuntimeError('Private data API failed; inspect private diagnostics')
    return p

def assert_private():
    info=json.loads(gh('api','repos/'+DATA_REPOSITORY).stdout)
    if info.get('private') is not True:raise ValueError('Data repository must remain private')

def download_input(work):
    from transfer import restore
    work=pathlib.Path(work);download=work.parent/'input-download';download.mkdir(parents=True,exist_ok=True)
    gh('release','download','windows-input-v1','--repo',DATA_REPOSITORY,'--dir',download,'--pattern','input.part*','--pattern','input-manifest.json')
    restore(download,work)

def publish_template(work):
    work=pathlib.Path(work);tag='unsigned-template-'+os.environ['GITHUB_RUN_ID']
    gh('release','create',tag,'--repo',DATA_REPOSITORY,'--title','Unsigned external-folder launcher template','--notes','Private output; no physical USB or gameplay validation.','--prerelease')
    gh('release','upload',tag,'--repo',DATA_REPOSITORY,*sorted((work/'output').glob('template.part*')),work/'output/result-manifest.json')

def save_logs(work):
    import tarfile
    work=pathlib.Path(work)
    if not (work/'logs').exists():return
    archive=work.parent/('diagnostics-'+work.name+'.tar.gz')
    with tarfile.open(archive,'w:gz') as t:t.add(work/'logs',arcname='logs')
    tag='public-diagnostics-'+os.environ['GITHUB_RUN_ID']+'-'+work.name+'-'+os.environ.get('GITHUB_RUN_ATTEMPT','1')
    gh('release','create',tag,'--repo',DATA_REPOSITORY,'--title','Private build diagnostics','--notes','Raw logs retained privately.','--prerelease')
    gh('release','upload',tag,'--repo',DATA_REPOSITORY,archive)

if __name__=='__main__':
    assert_private()
    if sys.argv[1]=='check':print('Private data repository and credential verified')
    elif sys.argv[1]=='input':download_input(sys.argv[2])
    elif sys.argv[1]=='publish':publish_template(sys.argv[2])
    elif sys.argv[1]=='logs':save_logs(sys.argv[2])
    else:raise ValueError('Unknown private data operation')

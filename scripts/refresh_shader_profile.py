"""Merge the public regional shader facts without changing package/index ordering."""
import hashlib,json,pathlib,sys
from contracts import TITLE

UPSTREAM='c692ba056c891e55381a1e443ac976210dc4d7e2'
FACTS_SHA='89e112f4672c5589e7dbb40a87ba6b623ab86fd0f6b20f078b3a6e2212c27239'
FACTS=pathlib.Path(__file__).resolve().parents[1]/'runtime/ShaderFacts35.tsv'

def rows(path):
    return {k:json.loads(v) for line in pathlib.Path(path).read_text().splitlines()
            if line and not line.startswith('#') for k,v in [line.split('\t',1)]}

def verify(profile):
    profile=pathlib.Path(profile)
    if hashlib.sha256(FACTS.read_bytes()).hexdigest()!=FACTS_SHA:raise ValueError('Public facts provenance changed')
    wanted=rows(FACTS);actual=rows(profile/'shader_facts.tsv')
    missing=[k for k,v in wanted.items() if any(actual.get(k,{}).get(t)!=f for t,f in v.items())]
    if missing:raise ValueError(f'Shader profile needs regeneration: {len(missing)} fact rows differ')
    return wanted

def apply(repo):
    profile=pathlib.Path(repo)/'dm/games'/TITLE
    if hashlib.sha256(FACTS.read_bytes()).hexdigest()!=FACTS_SHA:raise ValueError('Public facts provenance changed')
    wanted=rows(FACTS);existing=rows(profile/'shader_facts.tsv')
    keys={v[3] for line in (profile/'shader_map.tsv').read_text().splitlines()
          if len(v:=line.split('\t'))==5 and v[2] in ('vertex','pixel','compute','geometry')}
    if len(wanted)!=35 or not set(wanted)<=keys:raise ValueError('Facts do not match the retained shader map')
    changed=[k for k,v in wanted.items() if any(existing.get(k,{}).get(t)!=f for t,f in v.items())]
    for k,v in wanted.items():existing.setdefault(k,{}).update(v)
    target=profile/'shader_facts.tsv'
    header='# Generated facts plus the public regional manual facts; package/index ordering is unchanged.\n'
    target.write_text(header+''.join(k+'\t'+json.dumps(v,sort_keys=True,separators=(',',':'))+'\n' for k,v in sorted(existing.items())),encoding='utf-8',newline='\n')
    (profile/'shader_facts_manual.tsv').write_bytes(FACTS.read_bytes())
    verify(profile)
    return {'upstream':UPSTREAM,'manual_facts_sha256':FACTS_SHA,'manual_facts':35,'changed_keys':sorted(changed)}

if __name__=='__main__':
    if sys.argv[1]=='check':verify(sys.argv[2])
    else:print(json.dumps(apply(sys.argv[2]),indent=2))

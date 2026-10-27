"""Cache presence and final geometry contracts follow the pinned upstream output formats."""
import json
import pathlib

def cache_layout(keys,manifests,successful):
    # A gs_slice fold emits only JSON. Upstream intentionally does not publish
    # it into the ordinary CAS, whose contract requires a metallib.
    paths={row['path'] for m in manifests for row in m['files']}
    indexed={pathlib.PurePosixPath(p).stem for p in paths if p.startswith('shader/cache/cas/index/')}
    missing=set(successful)-indexed
    if any(keys[key]!='geometry' for key in missing):raise ValueError('Successful non-geometry shader has no cache index')
    expected={key:set() for key in set(successful)-missing}
    for path in paths:
        fields=path.split('/')
        if len(fields)!=7 or fields[:4]!=['shader','cache','cas','shader']:continue
        name=fields[-1];key=name[:16]
        if key in expected:expected[key].add(fields[-2]+'/'+name[16:])
    required={'mac/_b.metal','mac/_b.json','mac/_b.metallib','ios/_b.json','ios/_b.metallib'}
    for key,files in expected.items():
        if not required<=files:raise ValueError('Incomplete successful shader cache: '+key)
    return sorted(missing)

def verify_geometry(keys,mac,ios,chain):
    targets=(pathlib.Path(ios),) if mac is None else (pathlib.Path(mac),pathlib.Path(ios))
    for key,stage in keys.items():
        if stage!='geometry':continue
        for directory in targets:
            path=directory/(key+'_b.json')
            if not path.is_file():raise ValueError('Geometry descriptor was not regenerated')
            meta=json.loads(path.read_text())
            if meta.get('chain')!=chain or meta.get('dm_ctl')!=key or meta.get('stage')!='gs':raise ValueError('Geometry output identity differs')
            if 'gs_slice' in meta:
                value=meta['gs_slice']
                if not isinstance(value,dict) or type(value.get('loc')) is not int or value['loc']<0 or value.get('comp') not in ('x','y','z','w') or meta.get('bindings')!=[]:raise ValueError('Invalid layer-selection geometry descriptor')
            else:
                if 'geometry' not in meta or meta.get('msl_entry_kind')!='kernel':raise ValueError('Geometry lowering was not generated')
                for suffix in ('_b','_bg0','_bg1','_bg2','_bg3','_bg4','_bgv'):
                    for ext in ('.json','.metallib'):
                        if not (directory/(key+suffix+ext)).is_file():raise ValueError('Incomplete geometry topology outputs')

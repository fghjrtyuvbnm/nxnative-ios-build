import json
import pathlib
import sys
import tempfile
import unittest
import ast
import os
import re
from types import SimpleNamespace
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from cache_layout import cache_layout,verify_geometry

class CacheLayout(unittest.TestCase):
    def test_slice_shape_matches_the_pinned_upstream_parser(self):
        repo=pathlib.Path(os.environ.get('NXNATIVE_REPO',str(pathlib.Path(__file__).resolve().parents[2]/'nxnative')))
        tree=ast.parse((repo/'dm/gfx/tools/dmsh_build.py').read_text())
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='gs_slice')
        glsl='layout(triangles) in;\nlayout(max_vertices = 3, triangle_strip) out;\nlayout(location = 1) in vec4 layers[3];\nvoid main() {\n'+''.join(f'float a{i} = layers[{i}].x;\ngl_Layer = floatBitsToInt(a{i});\nEmitVertex();\n' for i in range(3))+'}'
        namespace={'re':re,'subprocess':SimpleNamespace(run=lambda *a,**kw:SimpleNamespace(returncode=0,stdout=glsl))}
        exec(compile(ast.Module(body=[function],type_ignores=[]),'pinned-gs-slice','exec'),namespace)
        value=namespace['gs_slice']('fixture.spv')
        self.assertEqual(value,{'loc':1,'comp':'x'})
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td);key='a'*16
            (root/(key+'_b.json')).write_text(json.dumps({'chain':'test','dm_ctl':key,'stage':'gs','gs_slice':value,'bindings':[]}))
            verify_geometry({key:'geometry'},root,root,'test')
            verify_geometry({key:'geometry'},None,root,'test')
            (root/(key+'_b.json')).write_text(json.dumps({'chain':'test','dm_ctl':key,'stage':'gs','gs_slice':{'loc':1,'comp':0},'bindings':[]}))
            with self.assertRaises(ValueError):verify_geometry({key:'geometry'},None,root,'test')
    def test_geometry_without_a_library_is_pending_regeneration_not_a_complete_cache(self):
        key='a'*16
        self.assertEqual(cache_layout({key:'geometry'},[{'files':[]}],{key}),[key])
        with self.assertRaises(ValueError):cache_layout({key:'fragment'},[{'files':[]}],{key})

    def test_regular_cached_shader_needs_all_base_outputs(self):
        key='a'*16;digest='b'*64;prefix='shader/cache/cas/'
        rows=[{'path':prefix+'index/'+key+'.json'}]+[{'path':prefix+'shader/'+digest+'/'+name} for name in (
            'mac/'+key+'_b.metal','mac/'+key+'_b.json','mac/'+key+'_b.metallib','ios/'+key+'_b.json','ios/'+key+'_b.metallib')]
        self.assertEqual(cache_layout({key:'vertex'},[{'files':rows}],{key}),[])
        with self.assertRaises(ValueError):cache_layout({key:'vertex'},[{'files':rows[:-1]}],{key})

    def test_regenerated_slice_descriptor_requires_real_geometry_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td);key='a'*16
            for target in ('mac','ios'):
                d=root/target;d.mkdir()
                (d/(key+'_b.json')).write_text(json.dumps({'chain':'test','dm_ctl':key,'stage':'gs','gs_slice':{'loc':1,'comp':'z'},'bindings':[]}))
            verify_geometry({key:'geometry'},root/'mac',root/'ios','test')
            (root/'ios'/(key+'_b.json')).write_text('{}')
            with self.assertRaises(ValueError):verify_geometry({key:'geometry'},root/'mac',root/'ios','test')

    def test_compute_geometry_requires_every_topology_and_reader_library(self):
        with tempfile.TemporaryDirectory() as td:
            root=pathlib.Path(td);key='a'*16
            for target in ('mac','ios'):
                d=root/target;d.mkdir()
                for suffix in ('_b','_bg0','_bg1','_bg2','_bg3','_bg4','_bgv'):
                    (d/(key+suffix+'.json')).write_text('{}')
                    (d/(key+suffix+'.metallib')).write_bytes(b'compiled fixture')
                (d/(key+'_b.json')).write_text(json.dumps({'chain':'test','dm_ctl':key,'stage':'gs','geometry':{},'msl_entry_kind':'kernel'}))
            verify_geometry({key:'geometry'},root/'mac',root/'ios','test')
            (root/'ios'/(key+'_bg4.metallib')).unlink()
            with self.assertRaises(ValueError):verify_geometry({key:'geometry'},root/'mac',root/'ios','test')

if __name__=='__main__':unittest.main()

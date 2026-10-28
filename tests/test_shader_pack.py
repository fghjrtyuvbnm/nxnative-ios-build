import concurrent.futures,hashlib,json,pathlib,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'scripts'))
from shader_pack import pack,Reader
from export_shader_pack import export

class ShaderPackTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=pathlib.Path(self.temp.name);self.src=self.root/'src';self.src.mkdir()
        self.files={'a_b.json':b'{"entry":"main0"}','a_b.metallib':bytes(range(256))*8,'a_bp.metallib':b'pull'*91}
        for name,data in self.files.items():(self.src/name).write_bytes(data)
        self.out=self.root/'packed';pack(self.src,self.out)
    def reader(self):
        r=Reader(self.out);self.addCleanup(r.close);return r
    def test_random_and_concurrent_reads_missing_and_reopen(self):
        r=self.reader();names=list(self.files)*100
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(list(pool.map(r.read,names)),[self.files[n] for n in names])
        self.assertIsNone(r.read('absent.metallib'))
        r.close();self.assertEqual(self.reader().read('a_b.json'),self.files['a_b.json'])
    def test_corrupted_content_is_rejected(self):
        p=self.out/'shaders.pack';data=bytearray(p.read_bytes());data[0]^=1;p.write_bytes(data)
        with self.assertRaises(ValueError):self.reader().read('a_b.json')
    def test_invalid_offsets_sizes_paths_versions_and_hashes(self):
        p=self.out/'shaders.index.json';original=json.loads(p.read_text())
        for field,value in ((0,-1),(0,2**64),(1,0),(1,2**64),(2,'invalid')):
            m=json.loads(json.dumps(original));m['entries']['a_b.json'][field]=value;p.write_text(json.dumps(m))
            with self.assertRaises(ValueError):self.reader()
        m=json.loads(json.dumps(original));m['entries']['../escape.json']=m['entries'].pop('a_b.json');p.write_text(json.dumps(m))
        with self.assertRaises(ValueError):self.reader()
        m=json.loads(json.dumps(original));m['version']=2;p.write_text(json.dumps(m))
        with self.assertRaises(ValueError):self.reader()
    def test_truncation_after_open_is_rejected(self):
        r=self.reader()
        with (self.out/'shaders.pack').open('wb') as f:f.write(b'x')
        with self.assertRaises(ValueError):r.read('a_bp.metallib')
    def test_existing_destination_never_overwritten(self):
        with self.assertRaises(FileExistsError):pack(self.src,self.out)
    def test_export_preserves_original_and_updates_only_shader_storage(self):
        data=self.root/'original';chain=data/'msl/b-test';chain.parent.mkdir(parents=True);self.src.rename(chain)
        (chain/'inputs.tsv').write_bytes(b'identity')
        marker=data/'romfs/game.bin';marker.parent.mkdir();marker.write_bytes(b'game bytes')
        files=[]
        for p in data.rglob('*'):
            if p.is_file():files.append(dict(path=p.relative_to(data).as_posix(),size=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
        manifest=dict(format_version=1,identity=dict(shader_chain='test'),files=files)
        (data/'game-data.json').write_text(json.dumps(manifest))
        target=self.root/'exported';export(data,target)
        self.assertEqual(json.loads((data/'game-data.json').read_text()),manifest)
        for r in files:self.assertEqual(hashlib.sha256((data/r['path']).read_bytes()).hexdigest(),r['sha256'])
        r=Reader(target/'msl/b-test')
        try:self.assertEqual(r.read('a_b.metallib'),self.files['a_b.metallib'])
        finally:r.close()
        self.assertEqual((target/'romfs/game.bin').read_bytes(),b'game bytes')
        self.assertEqual(len(json.loads((target/'game-data.json').read_text())['files']),4)

"""Versioned, uncompressed shader pack; offsets are relative to the data file."""
import hashlib,json,pathlib,threading,re,stat,concurrent.futures

def valid_name(name):return isinstance(name,str) and re.fullmatch(r'[0-9a-zA-Z_-]+\.(json|metallib)',name) is not None

def unique(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('Duplicate index key')
        result[key]=value
    return result

def pack(directory,output):
    directory=pathlib.Path(directory);output=pathlib.Path(output);output.mkdir(parents=True,exist_ok=False)
    entries={};offset=0
    def read(source):
        st=source.lstat()
        if not valid_name(source.name) or not stat.S_ISREG(st.st_mode) or not 0<st.st_size<=64*1024*1024:raise ValueError('Invalid shader input')
        data=source.read_bytes()
        if len(data)!=st.st_size:raise ValueError('Source changed while packing')
        return source.name,data,hashlib.sha256(data).hexdigest()
    sources=[p for p in sorted(directory.iterdir()) if p.suffix in ('.json','.metallib')]
    with (output/'shaders.pack').open('xb') as dst,concurrent.futures.ThreadPoolExecutor(max_workers=16) as pool:
        # Bounded batches avoid accumulating all shader contents in memory.
        for first in range(0,len(sources),64):
            for name,data,digest in pool.map(read,sources[first:first+64]):
                dst.write(data);entries[name]=[offset,len(data),digest];offset+=len(data)
            if first//64%157==0:print(f'Packed {min(first+64,len(sources))}/{len(sources)} shader files',flush=True)
    (output/'shaders.index.json').write_text(json.dumps(dict(version=1,bytes=offset,entries=entries),separators=(',',':')),encoding='utf-8')
    return entries

class Reader:
    def __init__(self,directory):
        self.directory=pathlib.Path(directory)
        index=self.directory/'shaders.index.json';data=self.directory/'shaders.pack'
        if index.is_symlink() or data.is_symlink() or not 0<index.stat().st_size<=64*1024*1024:raise ValueError('Invalid pack path')
        self.index=json.loads(index.read_text(),object_pairs_hook=unique)
        m=self.index
        if m.get('version')!=1 or type(m.get('bytes')) is not int or not isinstance(m.get('entries'),dict) or not 0<len(m['entries'])<=200000:raise ValueError('Invalid pack header')
        offset=0
        for name,row in sorted(m['entries'].items()):
            if not valid_name(name) or not isinstance(row,list) or len(row)!=3 or type(row[0]) is not int or type(row[1]) is not int or row[0]!=offset or not 0<row[1]<=64*1024*1024 or not isinstance(row[2],str) or re.fullmatch('[0-9a-f]{64}',row[2]) is None:raise ValueError('Invalid pack entry')
            offset+=row[1]
        if offset!=m['bytes'] or data.stat().st_size!=offset:raise ValueError('Invalid pack extent')
        self.file=data.open('rb');self.lock=threading.Lock()
    def close(self):self.file.close()
    def read(self,name):
        row=self.index['entries'].get(name)
        if row is None:return None
        with self.lock:
            self.file.seek(row[0]);data=self.file.read(row[1])
        if len(data)!=row[1] or hashlib.sha256(data).hexdigest()!=row[2]:raise ValueError('Shader pack content mismatch')
        return data

"""Complete the unsigned IPA locally, retaining the cloud executable's ZIP modes."""
import argparse
import copy
import json
import pathlib
import plistlib
import shutil
import zipfile
from contracts import TITLE, BUILD, check_identity, sha256

def finish(download,work,out):
    download=pathlib.Path(download);work=pathlib.Path(work);out=pathlib.Path(out)
    m=json.loads((download/'result-manifest.json').read_text());check_identity(m)
    template=download/'FFR-HK-unsigned-template.ipa'
    with template.open('xb') as dst:
        for i,row in enumerate(m['parts']):
            if row['path']!=f'template.part{i:03}': raise ValueError('Unexpected result part')
            p=download/row['path']
            if p.stat().st_size!=row['bytes'] or sha256(p)!=row['sha256']: raise ValueError('Result part integrity mismatch')
            with p.open('rb') as f:shutil.copyfileobj(f,dst,8*1024*1024)
    if sha256(template)!=m['template_sha256']: raise ValueError('Template integrity mismatch')
    with zipfile.ZipFile(template) as z:
        names=z.namelist();info=plistlib.loads(z.read('Payload/DmIOS.app/Info.plist'))
        if info['CFBundleIdentifier']!='org.nxnative.'+TITLE.lower(): raise ValueError('Wrong application identity')
        if any('/_CodeSignature/' in n or n.endswith('/embedded.mobileprovision') for n in names): raise ValueError('Unexpected signing files')
        if 'Payload/DmIOS.app/'+info['CFBundleExecutable'] not in names: raise ValueError('Missing application executable')
        if z.testzip(): raise ValueError('Template CRC mismatch')
        tmp=out.with_suffix('.ipa.partial')
        with zipfile.ZipFile(tmp,'x',allowZip64=True,compression=zipfile.ZIP_DEFLATED,compresslevel=1) as dst:
            for entry in z.infolist():
                if entry.filename.startswith('Payload/DmIOS.app/romfs/'): raise ValueError('Template already has RomFS')
                with z.open(entry) as src,dst.open(copy.copy(entry),'w',force_zip64=True) as target:
                    shutil.copyfileobj(src,target,8*1024*1024)
            romfs=work/'extract/v1/RomFS'
            for p in sorted(romfs.rglob('*')):
                if not p.is_file(): continue
                arc='Payload/DmIOS.app/romfs/'+p.relative_to(romfs).as_posix()
                method=zipfile.ZIP_STORED if p.suffix.lower() in ('.pak','.ucas','.utoc','.ttf','.txt','.metallib') else zipfile.ZIP_DEFLATED
                print('Packing local RomFS: '+p.name,flush=True)
                dst.write(p,arc,compress_type=method)
        with zipfile.ZipFile(tmp) as result:
            if result.testzip(): raise ValueError('Final IPA CRC mismatch')
            if 'Payload/DmIOS.app/romfs/FFRS/Content/Paks/FFRS-Switch.ucas' not in result.namelist(): raise ValueError('Missing game data')
        if out.exists(): raise FileExistsError(out)
        tmp.rename(out)
    report={'title_id':TITLE,'main_build':BUILD,'bytes':out.stat().st_size,'sha256':sha256(out),'signed':False,'zip_crc_verified':True,'runtime_tested':False}
    out.with_suffix('.verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('Completed unsigned IPA: '+str(out),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('download');p.add_argument('work');p.add_argument('out');a=p.parse_args()
    control=pathlib.Path(__file__).resolve().parents[2]/'external-data-mode.json'
    m=json.loads((pathlib.Path(a.download)/'result-manifest.json').read_text())
    if m.get('external_data_runtime'):
        from external_pack import finish_external
        finish_external(a.download,a.work,a.out)
    elif control.is_file():
        raise SystemExit('Compiled shaders are ready. This earlier template needs the external-folder launcher rebuild before final packaging; embedded-data packaging is disabled.')
    else:finish(a.download,a.work,a.out)

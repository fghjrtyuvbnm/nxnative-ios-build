"""Publish the exact Windows-verified launcher from a private compiled template."""
import copy,json,pathlib,shutil,sys,zipfile
from contracts import check_identity,sha256
from external_pack import reconstruct,resource_name,check_archive_name

def export(download,expected,out):
    out=pathlib.Path(out)
    if out.exists():raise FileExistsError(out)
    check_identity(expected)
    if not expected.get('data_sha256_verified') or not expected.get('zip_crc_verified') or not expected.get('external_data_runtime'):raise ValueError('A verified Windows export is required')
    template,result=reconstruct(download)
    if result.get('resource_only') or not result.get('external_data_runtime'):raise ValueError('External application template required')
    temp=out.with_suffix('.partial')
    with zipfile.ZipFile(template) as source,zipfile.ZipFile(temp,'x',allowZip64=True,compression=zipfile.ZIP_DEFLATED,compresslevel=1) as destination:
        seen=set()
        for entry in source.infolist():
            check_archive_name(entry.filename)
            if entry.filename.casefold() in seen:raise ValueError('Duplicate archive entry')
            seen.add(entry.filename.casefold())
            if resource_name(entry.filename) is not None:continue
            with source.open(entry) as src,destination.open(copy.copy(entry),'w',force_zip64=True) as dst:shutil.copyfileobj(src,dst,8*1024*1024)
    # This is deliberately strict across platforms: no alternative bytes ship.
    if temp.stat().st_size!=expected['launcher_bytes'] or sha256(temp)!=expected['launcher_sha256']:
        temp.unlink();raise ValueError('Cloud output differs from the verified Windows IPA')
    with zipfile.ZipFile(temp) as z:
        if z.testzip():raise ValueError('Launcher CRC mismatch')
    temp.rename(out)
    return out

def main(run,base):
    from private_io import assert_private,gh,DATA_REPOSITORY
    if not run.isdigit():raise ValueError('Numeric source run required')
    assert_private();base=pathlib.Path(base);download=base/'download';download.mkdir(parents=True)
    expected_dir=base/'verification';expected_dir.mkdir()
    print('Downloading the completed private template',flush=True)
    gh('release','download','unsigned-template-'+run,'--repo',DATA_REPOSITORY,'--dir',download,'--pattern','template.part*','--pattern','result-manifest.json')
    tag='external-launcher-'+run
    gh('release','download',tag,'--repo',DATA_REPOSITORY,'--dir',expected_dir,'--pattern','*.verification.json')
    reports=list(expected_dir.glob('*.verification.json'))
    if len(reports)!=1:raise ValueError('One Windows verification report required')
    expected=json.loads(reports[0].read_text())
    print('Recreating and checking the exact Windows-verified IPA',flush=True)
    out=export(download,expected,base/'FINAL-FANTASY-RESONANCE-HK-1.0.1-launcher-unsigned-cloud.ipa')
    assert_private()
    gh('release','upload',tag,'--repo',DATA_REPOSITORY,out)
    print('Exact verified IPA published privately',flush=True)

if __name__=='__main__':
    try:main(*sys.argv[1:])
    except Exception:
        print('Private publication failed; no unverified IPA was published.',flush=True)
        raise SystemExit(1)

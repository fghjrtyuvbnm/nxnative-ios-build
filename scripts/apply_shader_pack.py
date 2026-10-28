"""Route every runtime shader/reflection read through the optional pack reader."""
import pathlib,shutil
def apply(repo):
    root=pathlib.Path(repo)/'dm/gfx/nvn';source=root/'nvn_mtl.m';text=source.read_text()
    shutil.copyfile(pathlib.Path(__file__).resolve().parents[1]/'runtime/shader_pack.h',root/'shader_pack.h')
    shutil.copyfile(pathlib.Path(__file__).resolve().parents[1]/'runtime/MemoryDiagnostics.h',root/'MemoryDiagnostics.h')
    if '#include "shader_pack.h"' in text:return
    text=text.replace('#include "ios18_metal.h"','#include "ios18_metal.h"\n#include "shader_pack.h"',1)
    start=text.index('    int fd = open(path.fileSystemRepresentation, O_RDONLY);',text.index('static id<MTLLibrary> lib_from_file('))
    end=text.index('\n}',start)
    text=text[:start]+'''    NSData *bytes=dm_shader_data(path,err);
    if (!bytes || !bytes.length)return nil;
    t_lib_layer=memmem(bytes.bytes,bytes.length,"render_target_array_index",25)!=NULL;
    dispatch_data_t data=dispatch_data_create(bytes.bytes,bytes.length,dispatch_get_global_queue(QOS_CLASS_UTILITY,0), ^{ (void)bytes; });
    return [g_dev newLibraryWithData:data error:err];'''+text[end:]
    old='[NSData dataWithContentsOfFile:[NSString stringWithFormat:@"%@/%@.json", g_msl_dir, pc]]'
    if text.count(old)!=1:raise ValueError('Shader reflection read anchor changed')
    text=text.replace(old,'dm_shader_data([NSString stringWithFormat:@"%@/%@.json", g_msl_dir, pc],NULL)')
    old='[NSData dataWithContentsOfFile:[NSString stringWithFormat:@"%@/%@_b.json", g_msl_dir, key]]'
    if text.count(old)!=1:raise ValueError('Prewarm reflection read anchor changed')
    text=text.replace(old,'dm_shader_data([NSString stringWithFormat:@"%@/%@_b.json", g_msl_dir, key],NULL)')
    source.write_text(text,encoding='utf-8',newline='\n')

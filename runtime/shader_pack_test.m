#import <Metal/Metal.h>
#include "shader_pack.h"
static int checks=0;
#define CHECK(x) do{checks++;if(!(x)){fprintf(stderr,"Pack check failed line %d\n",__LINE__);return 1;}}while(0)
int main(int argc,char **argv){@autoreleasepool{
    CHECK(argc==2);NSString *root=@(argv[1]),*packed=[root stringByAppendingPathComponent:@"packed"];
    NSString *path=[packed stringByAppendingPathComponent:@"fixture_b.metallib"];
    NSError *error=nil;NSData *data=dm_shader_data(path,&error);
    CHECK(data&& !error);CHECK([dm_shader_data([packed stringByAppendingPathComponent:@"fixture_b.json"],NULL) isEqualToData:[@"{\"entry\":\"main0\"}" dataUsingEncoding:NSUTF8StringEncoding]]);
    CHECK(dm_shader_data([packed stringByAppendingPathComponent:@"absent.metallib"],NULL)==nil);
    __block int failures=0;
    dispatch_apply(100,dispatch_get_global_queue(QOS_CLASS_USER_INITIATED,0),^(size_t i){@autoreleasepool{if(![dm_shader_data(path,NULL) isEqualToData:data])__sync_fetch_and_add(&failures,1);}});
    CHECK(failures==0);
    CHECK([dm_shader_data([root stringByAppendingPathComponent:@"loose/fixture_b.metallib"],NULL) isEqualToData:data]);
    for(NSString *folder in @[@"corrupt",@"truncated",@"invalid"]){error=nil;CHECK(dm_shader_data([[root stringByAppendingPathComponent:folder] stringByAppendingPathComponent:@"fixture_b.metallib"],&error)==nil&&error!=nil);}
    // Keep the backing NSData alive solely through the dispatch-data destructor.
    dispatch_data_t payload;
    @autoreleasepool{NSData *temporary=dm_shader_data(path,NULL);payload=dispatch_data_create(temporary.bytes,temporary.length,dispatch_get_global_queue(QOS_CLASS_UTILITY,0),^{(void)temporary;});}
    id<MTLDevice> device=MTLCreateSystemDefaultDevice();CHECK(device!=nil);
    id<MTLLibrary> library=[device newLibraryWithData:payload error:&error];CHECK(library!=nil);
    id<MTLComputePipelineState> pso=[device newComputePipelineStateWithFunction:[library newFunctionWithName:@"main0"] error:&error];CHECK(pso!=nil);
    id<MTLBuffer> output=[device newBufferWithLength:4 options:MTLResourceStorageModeShared];
    id<MTLCommandBuffer> cb=[[device newCommandQueue] commandBuffer];id<MTLComputeCommandEncoder> encoder=[cb computeCommandEncoder];
    [encoder setComputePipelineState:pso];[encoder setBuffer:output offset:0 atIndex:0];[encoder dispatchThreadgroups:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];[encoder endEncoding];[cb commit];[cb waitUntilCompleted];
    CHECK(cb.status==MTLCommandBufferStatusCompleted&&!cb.error);CHECK(*(uint32_t *)output.contents==0x1234abcd);
    printf("{\"shader_pack_native_checks\":%d,\"concurrent_reads\":100,\"gpu_value_verified\":true}\n",checks);
    return 0;
}}

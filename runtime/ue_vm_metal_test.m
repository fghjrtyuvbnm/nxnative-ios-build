#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include "UELargeVM.h"
#include <string.h>
#define VERIFY(x) do{if(!(x)){fprintf(stderr,"VM Metal contract failed line %d\n",__LINE__);return 1;}}while(0)
int main(void){
    void *memory=ue_vm_alloc(2*1024*1024+123,65536);VERIFY(memory);
    size_t length=ue_vm_size(memory);VERIFY(length>=2*1024*1024+123&&((uintptr_t)memory%65536)==0);
    memset(memory,0,length);uint32_t count=(uint32_t)(length/4);
    @autoreleasepool{
        id<MTLDevice> device=MTLCreateSystemDefaultDevice();VERIFY(device);
        NSError *error=nil;
        id<MTLLibrary> library=[device newLibraryWithSource:@"#include <metal_stdlib>\nusing namespace metal; kernel void check(device uint *p [[buffer(0)]],constant uint &n [[buffer(1)]]){p[0]=0x12345678;p[n-1]=0xabcdef01;}" options:nil error:&error];VERIFY(library);
        id<MTLComputePipelineState> pso=[device newComputePipelineStateWithFunction:[library newFunctionWithName:@"check"] error:&error];VERIFY(pso);
        id<MTLBuffer> buffer=[device newBufferWithBytesNoCopy:memory length:length options:MTLResourceStorageModeShared deallocator:nil];VERIFY(buffer);
        id<MTLCommandQueue> queue=[device newCommandQueue];id<MTLCommandBuffer> cb=[queue commandBuffer];id<MTLComputeCommandEncoder> encoder=[cb computeCommandEncoder];
        [encoder setComputePipelineState:pso];[encoder setBuffer:buffer offset:0 atIndex:0];[encoder setBytes:&count length:sizeof count atIndex:1];
        [encoder dispatchThreadgroups:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(1,1,1)];[encoder endEncoding];[cb commit];[cb waitUntilCompleted];
        VERIFY(cb.status==MTLCommandBufferStatusCompleted&&!cb.error);
        VERIFY(((uint32_t *)memory)[0]==0x12345678&&((uint32_t *)memory)[count-1]==0xabcdef01);
    }
    size_t released=0;VERIFY(ue_vm_free(memory,&released)==1&&released==length&&ue_vm_size(memory)==0);
    puts("UE VM native Metal shared-buffer commitment and GPU readback passed");return 0;
}

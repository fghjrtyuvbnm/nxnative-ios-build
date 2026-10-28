// Synthetic GPU readback tests, with no game files or proprietary inputs.
#import <Foundation/Foundation.h>
#include "ios18_metal.h"
#include <stdio.h>
static unsigned checks;
#define CHECK(x) do { checks++; if (!(x)) { fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x); abort(); } } while(0)
@interface SyntheticBufferRange : NSObject <MTLBuffer>
@property uint64_t gpuAddress;
@property NSUInteger length;
@end
@implementation SyntheticBufferRange
- (MTLStorageMode)storageMode { return MTLStorageModeShared; }
@end
static void overlapping_ranges(void) {
    // Lookup-only objects never enter a real GPU command buffer.
    DM18Registry *ranges=[DM18Registry new];SyntheticBufferRange *large=[SyntheticBufferRange new],*small=[SyntheticBufferRange new];
    large.gpuAddress=small.gpuAddress=0x10000;large.length=8192;small.length=4096;[ranges add:large];[ranges add:small];
    NSUInteger offset=0;id found=nil;@try { found=[ranges buffer:0x11000 offset:&offset]; } @catch(NSException *e) {}
    CHECK(found==large);CHECK(offset==4096);
}
static void finish(id<DM18CommandQueue> q,id<DM18CommandBuffer> cb,id<MTLSharedEvent> event,uint64_t value) {
    [cb endCommandBuffer];[q commit:&cb count:1];[q signalEvent:event value:value];
    NSDate *end=[NSDate dateWithTimeIntervalSinceNow:30];
    while (event.signaledValue<value && end.timeIntervalSinceNow>0) [NSThread sleepForTimeInterval:.001];
    CHECK(event.signaledValue>=value);
    // The GPU event can precede the host completion notification/status update.
    [((DM18CommandBuffer *)cb).native waitUntilCompleted];
    CHECK(((DM18CommandBuffer *)cb).native.status==MTLCommandBufferStatusCompleted);
    CHECK(!((DM18CommandBuffer *)cb).native.error);
}
int main(void) { @autoreleasepool {
    overlapping_ranges();
    id<MTLDevice> d=dm18_device();CHECK(d!=nil);
    DM18QueueDescriptor *qd=[DM18QueueDescriptor new];NSError *error=nil;
    id<DM18CommandQueue> q=(id)[d newMTL4CommandQueueWithDescriptor:(id)qd error:&error];CHECK(q!=nil);
    id<MTLSharedEvent> event=[d newSharedEvent];CHECK(event!=nil);
    NSString *source=@"#include <metal_stdlib>\nusing namespace metal;\n"
    "kernel void fill(device uint *o[[buffer(0)]],constant uint& v[[buffer(1)]],uint i[[thread_position_in_grid]]){if(i<32)o[i]=v+i;}\n"
    "vertex float4 vs(uint i[[vertex_id]]){const float2 p[3]={float2(-1,-1),float2(3,-1),float2(-1,3)};return float4(p[i],0,1);}\n"
    "fragment float4 fs(constant float4& c[[buffer(0)]]){return c;}\n"
    "fragment float4 sampled(texture2d<float> t[[texture(0)]],sampler s[[sampler(0)]]){return t.sample(s,float2(.5));}\n";
    MTLCompileOptions *options=[MTLCompileOptions new];options.languageVersion=MTLLanguageVersion3_1;
    id<MTLLibrary> lib=[d newLibraryWithSource:source options:options error:&error];CHECK(lib!=nil);
    id<MTLComputePipelineState> cp=[d newComputePipelineStateWithFunction:[lib newFunctionWithName:@"fill"] error:&error];CHECK(cp!=nil);
    id<MTLBuffer> values=[d newBufferWithLength:256 options:MTLResourceStorageModeShared];
    ((uint32_t *)values.contents)[0]=10;((uint32_t *)values.contents)[1]=100;
    id<MTLBuffer> output=[d newBufferWithLength:128 options:MTLResourceStorageModePrivate];
    id<MTLBuffer> first=[d newBufferWithLength:128 options:MTLResourceStorageModeShared];
    id<MTLBuffer> second=[d newBufferWithLength:128 options:MTLResourceStorageModeShared];
    DM18Arguments *args=[DM18Arguments new];[args setAddress:output.gpuAddress atIndex:0];[args setAddress:values.gpuAddress atIndex:1];
    id<DM18CommandBuffer> cb=(id)[d newCommandBuffer];[cb beginCommandBufferWithAllocator:nil];
    id<DM18ComputeEncoder> ce=[cb computeCommandEncoder];[ce setComputePipelineState:cp];[ce setArgumentTable:args];
    [ce dispatchThreadgroups:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];
    [ce copyFromBuffer:output sourceOffset:0 toBuffer:first destinationOffset:0 size:128];
    [args setAddress:values.gpuAddress+4 atIndex:1];
    [ce dispatchThreadgroups:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];
    [ce copyFromBuffer:output sourceOffset:0 toBuffer:second destinationOffset:0 size:128];[ce endEncoding];
    finish(q,cb,event,1);
    for (int i=0;i<32;i++) { CHECK(((uint32_t *)first.contents)[i]==10+i);CHECK(((uint32_t *)second.contents)[i]==100+i); }
    MTLRenderPipelineDescriptor *pd=[MTLRenderPipelineDescriptor new];pd.vertexFunction=[lib newFunctionWithName:@"vs"];pd.fragmentFunction=[lib newFunctionWithName:@"fs"];pd.colorAttachments[0].pixelFormat=MTLPixelFormatRGBA8Unorm;
    id<MTLRenderPipelineState> rp=[d newRenderPipelineStateWithDescriptor:pd error:&error];CHECK(rp!=nil);
    float red[4]={1,0,0,1};uint16_t indices[3]={0,1,2};
    id<MTLBuffer> color=[d newBufferWithBytes:red length:sizeof(red) options:MTLResourceStorageModeShared];
    id<MTLBuffer> ib=[d newBufferWithBytes:indices length:sizeof(indices) options:MTLResourceStorageModeShared];
    id<MTLBuffer> pixels=[d newBufferWithLength:4096 options:MTLResourceStorageModeShared];
    MTLTextureDescriptor *td=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:16 height:16 mipmapped:NO];td.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead;td.storageMode=MTLStorageModePrivate;
    id<MTLTexture> texture=[d newTextureWithDescriptor:td];CHECK(texture!=nil);
    MTLRenderPassDescriptor *pass=[MTLRenderPassDescriptor renderPassDescriptor];pass.colorAttachments[0].texture=texture;pass.colorAttachments[0].loadAction=MTLLoadActionClear;pass.colorAttachments[0].storeAction=MTLStoreActionStore;
    DM18Arguments *fargs=[DM18Arguments new];[fargs setAddress:color.gpuAddress atIndex:0];
    cb=(id)[d newCommandBuffer];[cb beginCommandBufferWithAllocator:nil];
    id<DM18RenderEncoder> re=[cb renderCommandEncoderWithDescriptor:pass];[re setRenderPipelineState:rp];[re setArgumentTable:fargs atStages:MTLRenderStageFragment];
    [re drawIndexedPrimitives:MTLPrimitiveTypeTriangle indexCount:3 indexType:MTLIndexTypeUInt16 indexBuffer:ib.gpuAddress indexBufferLength:sizeof(indices) instanceCount:1 baseVertex:0 baseInstance:0];[re endEncoding];
    ce=[cb computeCommandEncoder];[ce copyFromTexture:texture sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(16,16,1) toBuffer:pixels destinationOffset:0 destinationBytesPerRow:256 destinationBytesPerImage:4096];[ce endEncoding];
    finish(q,cb,event,2);
    uint8_t *pixel=(uint8_t *)pixels.contents+8*256+8*4;CHECK(pixel[0]==255);CHECK(pixel[1]==0);CHECK(pixel[2]==0);CHECK(pixel[3]==255);
    // Reuse the command-buffer token and bind a texture/sampler by resource ID.
    pd.fragmentFunction=[lib newFunctionWithName:@"sampled"];
    id<MTLRenderPipelineState> samplePSO=[d newRenderPipelineStateWithDescriptor:pd error:&error];CHECK(samplePSO!=nil);
    MTLSamplerDescriptor *sd=[MTLSamplerDescriptor new];sd.supportArgumentBuffers=YES;
    id<MTLSamplerState> sampler=[d newSamplerStateWithDescriptor:sd];CHECK(sampler!=nil);
    DM18Arguments *sampleArgs=[DM18Arguments new];[sampleArgs setTexture:texture.gpuResourceID atIndex:0];[sampleArgs setSamplerState:sampler.gpuResourceID atIndex:0];
    id<MTLTexture> sampledTarget=[d newTextureWithDescriptor:td];pass.colorAttachments[0].texture=sampledTarget;
    [cb beginCommandBufferWithAllocator:nil];re=[cb renderCommandEncoderWithDescriptor:pass];[re setRenderPipelineState:samplePSO];[re setArgumentTable:sampleArgs atStages:MTLRenderStageFragment];
    [re drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];[re endEncoding];
    ce=[cb computeCommandEncoder];[ce copyFromTexture:sampledTarget sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(16,16,1) toBuffer:pixels destinationOffset:0 destinationBytesPerRow:256 destinationBytesPerImage:4096];[ce endEncoding];finish(q,cb,event,3);
    pixel=(uint8_t *)pixels.contents+8*256+8*4;CHECK(pixel[0]==255);CHECK(pixel[1]==0);CHECK(pixel[2]==0);CHECK(pixel[3]==255);
    // Unknown addresses must fail explicitly rather than silently omit a draw.
    BOOL failed=NO;@try { NSUInteger off; [((DM18Device *)d).registry buffer:1 offset:&off]; } @catch(NSException *e) { failed=YES; }CHECK(failed);
    printf("{\"classic_gpu_readback_checks\":%u,\"passed\":true}\n",checks);
} return 0; }

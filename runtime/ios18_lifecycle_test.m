// Synthetic resources only. Never load a game's modules, textures or measurements.
#import <Foundation/Foundation.h>
#include "adapter-under-test.h"
#include <stdio.h>
static int liveBuffers;
@interface ChurnBuffer : NSObject <MTLBuffer>
@property uint64_t gpuAddress;
@property NSUInteger length;
@end
@implementation ChurnBuffer
- (instancetype)init { if((self=[super init]))liveBuffers++;return self; }
- (void)dealloc { liveBuffers--; }
- (MTLStorageMode)storageMode { return MTLStorageModeShared; }
@end

static NSDictionary *texture_churn(id<MTLDevice> device) {
    BOOL pixelsOK=YES;double start=CACurrentMediaTime();
    id<MTLCommandQueue> queue=[device newCommandQueue];
    id<MTLBuffer> result=[device newBufferWithLength:64*64*4 options:MTLResourceStorageModeShared];
    MTLTextureDescriptor *desc=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:64 height:64 mipmapped:NO];
    desc.storageMode=MTLStorageModeShared;desc.usage=MTLTextureUsageShaderRead;
    unsigned char bytes[64*64*4];
    @autoreleasepool {
        // One worker pool spans the run. Native command buffers retain resources
        // until their GPU copies finish; registry weak lookups must not extend it.
        for(unsigned frame=0;frame<64;frame++) {
            id<MTLCommandBuffer> cb=[queue commandBuffer];id<MTLBlitCommandEncoder> blit=[cb blitCommandEncoder];
            for(unsigned i=0;i<32;i++) {
                id<MTLTexture> texture=[device newTextureWithDescriptor:desc];
                if(!texture)return @{@"pixels_ok":@NO};
                memset(bytes,(frame+i)%251,sizeof bytes);
                [texture replaceRegion:MTLRegionMake2D(0,0,64,64) mipmapLevel:0 withBytes:bytes bytesPerRow:256];
                DM18Registry *registry=((DM18Device *)device).registry;
                id found=[registry texture:texture.gpuResourceID._impl];pixelsOK &= found==texture;
                [blit copyFromTexture:found sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(64,64,1) toBuffer:result destinationOffset:0 destinationBytesPerRow:256 destinationBytesPerImage:sizeof bytes];
            }
            [blit endEncoding];[cb commit];[cb waitUntilCompleted];
            pixelsOK &= !cb.error && ((unsigned char *)result.contents)[0]==(frame+31)%251;
        }
    }
    return @{@"pixels_ok":@(pixelsOK),@"frames":@64,@"textures":@2048,@"seconds":@(CACurrentMediaTime()-start)};
}

int main(void) { @autoreleasepool {
    int peak=0;BOOL lookupOK=YES;double begin=CACurrentMediaTime();
    @autoreleasepool {
        DM18Registry *registry=[DM18Registry new];
        // The surrounding worker pool deliberately stays alive across frames.
        // Individual host API calls must not prolong weakly indexed resources.
        for(unsigned frame=0;frame<64;frame++) {
            for(unsigned i=0;i<64;i++) {
                ChurnBuffer *buffer=[ChurnBuffer new];
                buffer.gpuAddress=0x100000+(frame*64+i)*4096;buffer.length=1024;
                [registry add:buffer];[registry add:buffer];
                NSUInteger offset=0;id found=[registry buffer:buffer.gpuAddress+128 offset:&offset];
                lookupOK &= found==buffer && offset==128;
                found=nil;buffer=nil;
            }
            NSUInteger epoch;NSArray *snapshot=[registry resources:&epoch];snapshot=nil;
            if(liveBuffers>peak)peak=liveBuffers;
        }
    }
    double elapsed=CACurrentMediaTime()-begin;
    BOOL drained=liveBuffers==0;
    id<MTLDevice> device=dm18_device();if(!device){fprintf(stderr,"No Metal device\n");return 2;}
    id<MTLCommandQueue> first=[device newCommandQueue],second=[device newCommandQueue];
    BOOL independent=first!=second;
    id<MTLSharedEvent> event=[device newSharedEvent];
    id<MTLCommandBuffer> waiting=[first commandBuffer];[waiting encodeWaitForEvent:event value:1];[waiting commit];
    id<MTLCommandBuffer> signaling=[second commandBuffer];[signaling encodeSignalEvent:event value:1];[signaling commit];
    double deadline=CACurrentMediaTime()+1.0;
    while(event.signaledValue<1 && CACurrentMediaTime()<deadline)[NSThread sleepForTimeInterval:.001];
    BOOL crossQueue=event.signaledValue>=1;
    if(!crossQueue)event.signaledValue=1; // Bounded fixture rescue, never a production fallback.
    [waiting waitUntilCompleted];[signaling waitUntilCompleted];
    BOOL gpuOK=!waiting.error&&!signaling.error;
    NSDictionary *textures=texture_churn(device);gpuOK &= [textures[@"pixels_ok"] boolValue];
    NSDictionary *report=@{@"weak_live_peak":@(peak),@"weak_drained_at_worker_end":@(drained),@"lookup_ok":@(lookupOK),@"churn_seconds":@(elapsed),@"independent_classic_queues":@(independent),@"cross_queue_completed_without_rescue":@(crossQueue),@"gpu_ok":@(gpuOK),@"texture_churn":textures};
    NSData *json=[NSJSONSerialization dataWithJSONObject:report options:0 error:nil];
    puts([[NSString alloc]initWithData:json encoding:NSUTF8StringEncoding].UTF8String);
    return lookupOK&&drained&&peak==0&&independent&&crossQueue&&gpuOK?0:42;
}}

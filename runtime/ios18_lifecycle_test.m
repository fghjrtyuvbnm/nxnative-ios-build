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
    NSDictionary *report=@{@"weak_live_peak":@(peak),@"weak_drained_at_worker_end":@(drained),@"lookup_ok":@(lookupOK),@"churn_seconds":@(elapsed),@"independent_classic_queues":@(independent),@"cross_queue_completed_without_rescue":@(crossQueue),@"gpu_ok":@(gpuOK)};
    NSData *json=[NSJSONSerialization dataWithJSONObject:report options:0 error:nil];
    puts([[NSString alloc]initWithData:json encoding:NSUTF8StringEncoding].UTF8String);
    return lookupOK&&drained&&peak==0&&independent&&crossQueue&&gpuOK?0:42;
}}

// Classic Metal execution adapter for the current NVN replay, including GS compute.
// Metal owns classic command-buffer memory; allocator tokens therefore own no GPU memory.
// Resource lookup follows the address-index approach in d2r-mobile's Metal 3 backend.
// The shader ABI and all game replay logic remain those of the pinned nxnative source.
#pragma once
#import <Metal/Metal.h>
#import <QuartzCore/CAMetalLayer.h>
#include <pthread.h>
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wprotocol" // Unchanged Metal methods are forwarded to the real device/encoder.

@interface DM18Registry : NSObject {
    NSLock *_lock;
    NSMapTable<NSNumber *,id> *_buffers, *_textures, *_samplers;
    NSHashTable<id<MTLResource>> *_resources;
    NSMutableArray<NSNumber *> *_addresses;
    NSUInteger _epoch;
}
- (void)add:(id)object;
- (id<MTLBuffer>)buffer:(uint64_t)address offset:(NSUInteger *)offset;
- (id)texture:(uint64_t)rid;
- (id)sampler:(uint64_t)rid;
- (NSArray *)resources:(NSUInteger *)epoch;
@end
@implementation DM18Registry
- (instancetype)init { if ((self=[super init])) { _lock=[NSLock new]; _buffers=[NSMapTable strongToWeakObjectsMapTable]; _textures=[NSMapTable strongToWeakObjectsMapTable]; _samplers=[NSMapTable strongToWeakObjectsMapTable]; _resources=[NSHashTable weakObjectsHashTable]; _addresses=[NSMutableArray array]; } return self; }
- (void)add:(id)object {
    if (!object) return;
    [_lock lock];
    if ([object conformsToProtocol:@protocol(MTLBuffer)]) {
        id<MTLBuffer> b=object; NSNumber *key=@(b.gpuAddress);
        if (![_buffers objectForKey:key]) {
            NSUInteger lo=0,hi=_addresses.count;
            while (lo<hi) { NSUInteger m=(lo+hi)/2; if (_addresses[m].unsignedLongLongValue<b.gpuAddress) lo=m+1; else hi=m; }
            if (lo==_addresses.count || ![_addresses[lo] isEqual:key]) [_addresses insertObject:key atIndex:lo];
        }
        [_buffers setObject:b forKey:key];
    }
    if ([object conformsToProtocol:@protocol(MTLTexture)]) [_textures setObject:object forKey:@(((id<MTLTexture>)object).gpuResourceID._impl)];
    if ([object conformsToProtocol:@protocol(MTLSamplerState)]) [_samplers setObject:object forKey:@(((id<MTLSamplerState>)object).gpuResourceID._impl)];
    if ([object conformsToProtocol:@protocol(MTLResource)] && ((id<MTLResource>)object).storageMode!=MTLStorageModeMemoryless && ![_resources containsObject:object]) { [_resources addObject:object]; _epoch++; }
    [_lock unlock];
}
- (id<MTLBuffer>)buffer:(uint64_t)address offset:(NSUInteger *)offset {
    *offset=0; if (!address) return nil;
    [_lock lock]; NSUInteger lo=0,hi=_addresses.count;
    while (lo<hi) { NSUInteger m=(lo+hi)/2; if (_addresses[m].unsignedLongLongValue<=address) lo=m+1; else hi=m; }
    id<MTLBuffer> b=lo ? [_buffers objectForKey:_addresses[lo-1]] : nil;
    if (b && address-b.gpuAddress<b.length) *offset=(NSUInteger)(address-b.gpuAddress); else b=nil;
    [_lock unlock];
    if (!b) [NSException raise:NSInternalInconsistencyException format:@"Unregistered Metal buffer address"];
    return b;
}
- (id)texture:(uint64_t)rid { [_lock lock]; id t=[_textures objectForKey:@(rid)]; [_lock unlock]; if (rid && !t) [NSException raise:NSInternalInconsistencyException format:@"Unregistered Metal texture ID"]; return t; }
- (id)sampler:(uint64_t)rid { [_lock lock]; id s=[_samplers objectForKey:@(rid)]; [_lock unlock]; if (rid && !s) [NSException raise:NSInternalInconsistencyException format:@"Unregistered Metal sampler ID"]; return s; }
- (NSArray *)resources:(NSUInteger *)epoch { [_lock lock]; *epoch=_epoch; NSArray *a=_resources.allObjects; [_lock unlock]; return a; }
@end

@protocol DM18Arguments <NSObject>
- (void)setAddress:(uint64_t)address atIndex:(NSUInteger)index;
- (void)setTexture:(MTLResourceID)rid atIndex:(NSUInteger)index;
- (void)setSamplerState:(MTLResourceID)rid atIndex:(NSUInteger)index;
@end
@interface DM18Arguments : NSObject <DM18Arguments> { @public uint64_t addresses[31], textures[16], samplers[16]; uint32_t bufferMask,textureMask,samplerMask; }
@end
@implementation DM18Arguments
- (void)setAddress:(uint64_t)a atIndex:(NSUInteger)i { NSCAssert(i<31,@"Buffer binding out of range"); addresses[i]=a; bufferMask|=1u<<i; }
- (void)setTexture:(MTLResourceID)a atIndex:(NSUInteger)i { NSCAssert(i<16,@"Texture binding out of range"); textures[i]=a._impl; textureMask|=1u<<i; }
- (void)setSamplerState:(MTLResourceID)a atIndex:(NSUInteger)i { NSCAssert(i<16,@"Sampler binding out of range"); samplers[i]=a._impl; samplerMask|=1u<<i; }
@end
@interface DM18ArgumentTableDescriptor : NSObject
@property NSUInteger maxBufferBindCount,maxTextureBindCount,maxSamplerStateBindCount;
@end
@implementation DM18ArgumentTableDescriptor @end
@protocol DM18Allocator <NSObject> - (void)reset; @property(readonly) NSUInteger allocatedSize; @end
@interface DM18Allocator : NSObject <DM18Allocator> @end
@implementation DM18Allocator - (void)reset {} - (NSUInteger)allocatedSize { return 0; } @end
@interface DM18AllocatorDescriptor : NSObject @property(copy) NSString *label; @end
@implementation DM18AllocatorDescriptor @end
@interface DM18QueueDescriptor : NSObject @property(strong) dispatch_queue_t feedbackQueue; @end
@implementation DM18QueueDescriptor @end
@interface DM18CommitOptions : NSObject
@property(strong) NSMutableArray *handlers;
- (void)addFeedbackHandler:(void (^)(id<MTLCommandBuffer>))handler;
@end
@implementation DM18CommitOptions
- (instancetype)init { if ((self=[super init])) _handlers=[NSMutableArray array]; return self; }
- (void)addFeedbackHandler:(void (^)(id<MTLCommandBuffer>))handler { [_handlers addObject:[handler copy]]; }
@end

@protocol DM18Encoder <NSObject>
- (void)setLabel:(NSString *)label;
- (void)endEncoding;
- (void)barrierAfterQueueStages:(MTLStages)a beforeStages:(MTLStages)b visibilityOptions:(NSUInteger)v;
- (void)barrierAfterStages:(MTLStages)a beforeQueueStages:(MTLStages)b visibilityOptions:(NSUInteger)v;
- (void)barrierAfterEncoderStages:(MTLStages)a beforeEncoderStages:(MTLStages)b visibilityOptions:(NSUInteger)v;
- (void)writeTimestampWithGranularity:(MTL4TimestampGranularity)g afterStage:(MTLRenderStages)stage intoHeap:(id)heap atIndex:(NSUInteger)index;
- (void)writeTimestampWithGranularity:(MTL4TimestampGranularity)g intoHeap:(id)heap atIndex:(NSUInteger)index;
@end
@protocol DM18RenderEncoder <MTLRenderCommandEncoder,DM18Encoder>
- (void)setArgumentTable:(id<DM18Arguments>)table atStages:(MTLRenderStages)stages;
- (void)setVertexBuffer:(uint64_t)address atIndex:(NSUInteger)index;
- (void)drawPrimitives:(MTLPrimitiveType)p indirectBuffer:(uint64_t)address;
- (void)drawIndexedPrimitives:(MTLPrimitiveType)p indexCount:(NSUInteger)n indexType:(MTLIndexType)t indexBuffer:(uint64_t)address indexBufferLength:(NSUInteger)length instanceCount:(NSUInteger)i baseVertex:(NSInteger)v baseInstance:(NSUInteger)b;
- (void)drawIndexedPrimitives:(MTLPrimitiveType)p indexType:(MTLIndexType)t indexBuffer:(uint64_t)address indexBufferLength:(NSUInteger)length indirectBuffer:(uint64_t)indirect;
@end
@protocol DM18ComputeEncoder <MTLComputeCommandEncoder,MTLBlitCommandEncoder,DM18Encoder>
- (void)setArgumentTable:(id<DM18Arguments>)table;
- (void)dispatchThreadgroupsWithIndirectBuffer:(uint64_t)address threadsPerThreadgroup:(MTLSize)threads;
@end
@interface DM18Encoder : NSObject <DM18RenderEncoder,DM18ComputeEncoder> {
@public id<MTLCommandBuffer> cb; id<MTLRenderCommandEncoder> render; DM18Registry *registry;
    id<MTLComputeCommandEncoder> compute; id<MTLBlitCommandEncoder> blit;
    DM18Arguments *vertexArgs,*fragmentArgs,*computeArgs; id<MTLComputePipelineState> computePSO;
    NSUInteger declaredEpoch; BOOL declared;
}
@end
@implementation DM18Encoder
- (id<MTLComputeCommandEncoder>)compute {
    if (!compute) { if (blit) { [blit endEncoding]; blit=nil; } compute=[cb computeCommandEncoder]; declared=NO; if (computePSO) [compute setComputePipelineState:computePSO]; }
    return compute;
}
- (id<MTLBlitCommandEncoder>)blit {
    if (!blit) { if (compute) { [compute endEncoding]; compute=nil; } blit=[cb blitCommandEncoder]; declared=NO; }
    return blit;
}
- (void)declareResources {
    NSUInteger epoch; NSArray *all=[registry resources:&epoch];
    if (declared && epoch==declaredEpoch) return;
    id<MTLResource> resources[128];
    for (NSUInteger first=0;first<all.count;first+=128) {
        NSUInteger n=MIN((NSUInteger)128,all.count-first);
        for (NSUInteger i=0;i<n;i++) resources[i]=all[first+i];
        if (render) [render useResources:resources count:n usage:MTLResourceUsageRead|MTLResourceUsageWrite stages:MTLRenderStageVertex|MTLRenderStageFragment];
        else [[self compute] useResources:resources count:n usage:MTLResourceUsageRead|MTLResourceUsageWrite];
    }
    declared=YES; declaredEpoch=epoch;
}
- (void)apply:(DM18Arguments *)table stage:(int)stage {
    if (!table) return;
    for (NSUInteger i=0;i<31;i++) if (table->bufferMask&(1u<<i)) {
        NSUInteger offset; id<MTLBuffer> b=[registry buffer:table->addresses[i] offset:&offset];
        if (stage==0) [render setVertexBuffer:b offset:offset atIndex:i];
        else if (stage==1) [render setFragmentBuffer:b offset:offset atIndex:i];
        else [[self compute] setBuffer:b offset:offset atIndex:i];
    }
    for (NSUInteger i=0;i<16;i++) {
        if (table->textureMask&(1u<<i)) { id<MTLTexture> t=[registry texture:table->textures[i]];
            if (stage==0) [render setVertexTexture:t atIndex:i]; else if (stage==1) [render setFragmentTexture:t atIndex:i]; else [[self compute] setTexture:t atIndex:i]; }
        if (table->samplerMask&(1u<<i)) { id<MTLSamplerState> s=[registry sampler:table->samplers[i]];
            if (stage==0) [render setVertexSamplerState:s atIndex:i]; else if (stage==1) [render setFragmentSamplerState:s atIndex:i]; else [[self compute] setSamplerState:s atIndex:i]; }
    }
}
- (void)prepareDraw { [self apply:vertexArgs stage:0]; [self apply:fragmentArgs stage:1]; [self declareResources]; }
- (void)prepareDispatch { (void)[self compute]; [self apply:computeArgs stage:2]; [self declareResources]; }
- (id)forwardingTargetForSelector:(SEL)selector {
    NSString *name=NSStringFromSelector(selector);
    if (render) { if ([name hasPrefix:@"draw"]) [self prepareDraw]; return render; }
    if ([name hasPrefix:@"copy"] || [name hasPrefix:@"fill"]) return [self blit];
    return compute ?: blit ?: [self compute];
}
- (BOOL)respondsToSelector:(SEL)s { return [super respondsToSelector:s] || [render respondsToSelector:s] || [compute respondsToSelector:s] || [blit respondsToSelector:s]; }
- (void)setArgumentTable:(id<DM18Arguments>)table atStages:(MTLRenderStages)stages { if (stages&MTLRenderStageVertex) vertexArgs=(id)table; if (stages&MTLRenderStageFragment) fragmentArgs=(id)table; }
- (void)setArgumentTable:(id<DM18Arguments>)table { computeArgs=(id)table; }
- (void)setComputePipelineState:(id<MTLComputePipelineState>)pso { computePSO=pso; [[self compute] setComputePipelineState:pso]; }
- (void)setVertexBuffer:(uint64_t)address atIndex:(NSUInteger)i { NSUInteger offset; id<MTLBuffer> b=[registry buffer:address offset:&offset]; [render setVertexBuffer:b offset:offset atIndex:i]; }
- (void)drawPrimitives:(MTLPrimitiveType)p indirectBuffer:(uint64_t)address { NSUInteger off; id<MTLBuffer> b=[registry buffer:address offset:&off]; [self prepareDraw]; [render drawPrimitives:p indirectBuffer:b indirectBufferOffset:off]; }
- (void)drawIndexedPrimitives:(MTLPrimitiveType)p indexCount:(NSUInteger)n indexType:(MTLIndexType)t indexBuffer:(uint64_t)address indexBufferLength:(NSUInteger)length instanceCount:(NSUInteger)i baseVertex:(NSInteger)v baseInstance:(NSUInteger)b {
    if (!n) return; NSUInteger off; id<MTLBuffer> buffer=[registry buffer:address offset:&off];
    NSCAssert(length<=buffer.length-off,@"Index buffer exceeds allocation"); [self prepareDraw];
    [render drawIndexedPrimitives:p indexCount:n indexType:t indexBuffer:buffer indexBufferOffset:off instanceCount:i baseVertex:v baseInstance:b];
}
- (void)drawIndexedPrimitives:(MTLPrimitiveType)p indexType:(MTLIndexType)t indexBuffer:(uint64_t)address indexBufferLength:(NSUInteger)length indirectBuffer:(uint64_t)indirect {
    NSUInteger off,ioff; id<MTLBuffer> b=[registry buffer:address offset:&off],ib=[registry buffer:indirect offset:&ioff];
    NSCAssert(length<=b.length-off,@"Index buffer exceeds allocation"); [self prepareDraw];
    [render drawIndexedPrimitives:p indexType:t indexBuffer:b indexBufferOffset:off indirectBuffer:ib indirectBufferOffset:ioff];
}
- (void)dispatchThreadgroups:(MTLSize)n threadsPerThreadgroup:(MTLSize)t { [self prepareDispatch]; [compute dispatchThreadgroups:n threadsPerThreadgroup:t]; }
- (void)dispatchThreadgroupsWithIndirectBuffer:(uint64_t)address threadsPerThreadgroup:(MTLSize)t { NSUInteger off; id<MTLBuffer> b=[registry buffer:address offset:&off]; [self prepareDispatch]; [compute dispatchThreadgroupsWithIndirectBuffer:b indirectBufferOffset:off threadsPerThreadgroup:t]; }
- (void)barrier {
    if (render) [render memoryBarrierWithScope:MTLBarrierScopeBuffers|MTLBarrierScopeTextures afterStages:MTLRenderStageVertex|MTLRenderStageFragment beforeStages:MTLRenderStageVertex|MTLRenderStageFragment];
    else if (compute) [compute memoryBarrierWithScope:MTLBarrierScopeBuffers|MTLBarrierScopeTextures];
    // Classic blit encoders preserve copy order; tracked resources order encoder boundaries.
}
- (void)barrierAfterQueueStages:(MTLStages)a beforeStages:(MTLStages)b visibilityOptions:(NSUInteger)v { (void)a;(void)b;(void)v; [self barrier]; }
- (void)barrierAfterStages:(MTLStages)a beforeQueueStages:(MTLStages)b visibilityOptions:(NSUInteger)v { (void)a;(void)b;(void)v; [self barrier]; }
- (void)barrierAfterEncoderStages:(MTLStages)a beforeEncoderStages:(MTLStages)b visibilityOptions:(NSUInteger)v { (void)a;(void)b;(void)v; [self barrier]; }
- (void)writeTimestampWithGranularity:(MTL4TimestampGranularity)g afterStage:(MTLRenderStages)stage intoHeap:(id)heap atIndex:(NSUInteger)index { (void)g;(void)stage;(void)heap;(void)index;[NSException raise:NSInternalInconsistencyException format:@"Metal 4 counter heaps are unavailable on the classic backend"]; }
- (void)writeTimestampWithGranularity:(MTL4TimestampGranularity)g intoHeap:(id)heap atIndex:(NSUInteger)index { (void)g;(void)heap;(void)index;[NSException raise:NSInternalInconsistencyException format:@"Metal 4 counter heaps are unavailable on the classic backend"]; }
- (void)endEncoding { if (render) [render endEncoding]; if (compute) [compute endEncoding]; if (blit) [blit endEncoding]; render=nil;compute=nil;blit=nil; }
@end

@protocol DM18CommandBuffer <NSObject>
- (void)beginCommandBufferWithAllocator:(id<DM18Allocator>)allocator;
- (void)endCommandBuffer;
- (id<DM18RenderEncoder>)renderCommandEncoderWithDescriptor:(MTLRenderPassDescriptor *)descriptor;
- (id<DM18ComputeEncoder>)computeCommandEncoder;
@end
@interface DM18CommandBuffer : NSObject <DM18CommandBuffer>
@property(strong) id<MTLCommandQueue> queue;
@property(strong) id<MTLCommandBuffer> native;
@property(strong) DM18Registry *registry;
@end
@implementation DM18CommandBuffer
- (void)beginCommandBufferWithAllocator:(id<DM18Allocator>)allocator { (void)allocator; self.native=[self.queue commandBuffer]; }
- (void)endCommandBuffer {} // Classic Metal ends individual encoders, then commits the buffer.
- (id<DM18RenderEncoder>)renderCommandEncoderWithDescriptor:(MTLRenderPassDescriptor *)d { DM18Encoder *e=[DM18Encoder new]; e->cb=self.native; e->registry=self.registry; e->render=[self.native renderCommandEncoderWithDescriptor:d]; return e; }
- (id<DM18ComputeEncoder>)computeCommandEncoder { DM18Encoder *e=[DM18Encoder new]; e->cb=self.native; e->registry=self.registry; return e; }
@end
@protocol DM18CommandQueue <NSObject>
- (void)commit:(id<DM18CommandBuffer> const *)buffers count:(NSUInteger)count;
- (void)commit:(id<DM18CommandBuffer> const *)buffers count:(NSUInteger)count options:(DM18CommitOptions *)options;
- (void)signalEvent:(id<MTLEvent>)event value:(uint64_t)value;
- (void)waitForEvent:(id<MTLEvent>)event value:(uint64_t)value;
- (void)addResidencySet:(id<MTLResidencySet>)set;
- (void)waitForDrawable:(id<CAMetalDrawable>)drawable;
- (void)signalDrawable:(id<CAMetalDrawable>)drawable;
@end
@interface DM18Queue : NSObject <DM18CommandQueue>
@property(strong) id<MTLCommandQueue> native;
@property(strong) dispatch_queue_t feedback;
@property(strong) NSLock *lock;
@property(strong) NSMutableDictionary *drawables;
@end
@implementation DM18Queue
- (instancetype)init { if ((self=[super init])) { _lock=[NSLock new]; _drawables=[NSMutableDictionary dictionary]; } return self; }
- (void)commit:(id<DM18CommandBuffer> const *)buffers count:(NSUInteger)count { [self commit:buffers count:count options:nil]; }
- (void)commit:(id<DM18CommandBuffer> const *)buffers count:(NSUInteger)count options:(DM18CommitOptions *)options {
    [_lock lock]; id<CAMetalDrawable> drawable=_drawables[@((uintptr_t)pthread_self())]; [_drawables removeObjectForKey:@((uintptr_t)pthread_self())]; [_lock unlock];
    for (NSUInteger i=0;i<count;i++) {
        id<MTLCommandBuffer> cb=((DM18CommandBuffer *)buffers[i]).native;
        if (i==count-1 && drawable) [cb presentDrawable:drawable];
        for (void (^handler)(id<MTLCommandBuffer>) in options.handlers) {
            dispatch_queue_t feedback=self.feedback;
            [cb addCompletedHandler:^(id<MTLCommandBuffer> completed) { if (feedback) dispatch_async(feedback,^{ handler(completed); }); else handler(completed); }];
        }
        [cb commit];
    }
}
- (void)signalEvent:(id<MTLEvent>)event value:(uint64_t)value { id<MTLCommandBuffer> cb=[_native commandBuffer]; [cb encodeSignalEvent:event value:value]; [cb commit]; }
- (void)waitForEvent:(id<MTLEvent>)event value:(uint64_t)value { id<MTLCommandBuffer> cb=[_native commandBuffer]; [cb encodeWaitForEvent:event value:value]; [cb commit]; }
- (void)addResidencySet:(id<MTLResidencySet>)set { (void)set; } // Explicit useResource replaces Metal 4 residency submission.
- (void)waitForDrawable:(id<CAMetalDrawable>)drawable { [_lock lock]; _drawables[@((uintptr_t)pthread_self())]=drawable; [_lock unlock]; }
- (void)signalDrawable:(id<CAMetalDrawable>)drawable { (void)drawable; [_lock lock]; [_drawables removeObjectForKey:@((uintptr_t)pthread_self())]; [_lock unlock]; }
@end

// Classic encoders declare resource use explicitly. This set only retains the
// replay's residency ownership bookkeeping, without a Metal 4 queue contract.
@interface DM18Residency : NSObject <MTLResidencySet>
@property(strong) NSMutableSet *objects;
@end
@implementation DM18Residency
- (instancetype)init { if ((self=[super init])) _objects=[NSMutableSet set]; return self; }
- (void)addAllocation:(id<MTLAllocation>)allocation { if (allocation) [_objects addObject:allocation]; }
- (void)removeAllocation:(id<MTLAllocation>)allocation { [_objects removeObject:allocation]; }
- (void)commit {}
@end

@interface DM18Device : NSObject <MTLDevice>
@property(strong) id<MTLDevice> native;
@property(strong) id<MTLCommandQueue> queue;
@property(strong) DM18Registry *registry;
@end
static MTLResourceOptions dm18_tracked(MTLResourceOptions o) { return (o&~(MTLResourceHazardTrackingModeUntracked|MTLResourceHazardTrackingModeTracked))|MTLResourceHazardTrackingModeTracked; }
@implementation DM18Device
- (id)forwardingTargetForSelector:(SEL)s { return self.native; }
- (BOOL)respondsToSelector:(SEL)s { return [super respondsToSelector:s] || [self.native respondsToSelector:s]; }
- (id<MTLCommandQueue>)newCommandQueue { return self.queue; }
- (id)newCommandBuffer { DM18CommandBuffer *b=[DM18CommandBuffer new]; b.queue=self.queue;b.registry=self.registry;return b; }
- (id<MTLResidencySet>)newResidencySetWithDescriptor:(MTLResidencySetDescriptor *)d error:(NSError **)error { (void)d;(void)error;return [DM18Residency new]; }
- (id)newMTL4CommandQueueWithDescriptor:(DM18QueueDescriptor *)d error:(NSError **)error { (void)error;DM18Queue *q=[DM18Queue new];q.native=self.queue;q.feedback=d.feedbackQueue;return q; }
- (id)newCommandAllocator { return [DM18Allocator new]; }
- (id)newCommandAllocatorWithDescriptor:(DM18AllocatorDescriptor *)d error:(NSError **)error { (void)d;(void)error;return [DM18Allocator new]; }
- (id)newArgumentTableWithDescriptor:(DM18ArgumentTableDescriptor *)d error:(NSError **)error { (void)error;NSCAssert(d.maxBufferBindCount<=31 && d.maxTextureBindCount<=16 && d.maxSamplerStateBindCount<=16,@"Argument table capacity exceeded");return [DM18Arguments new]; }
- (id<MTLBuffer>)newBufferWithLength:(NSUInteger)n options:(MTLResourceOptions)o { id b=[self.native newBufferWithLength:n options:dm18_tracked(o)];[self.registry add:b];return b; }
- (id<MTLBuffer>)newBufferWithBytes:(const void *)p length:(NSUInteger)n options:(MTLResourceOptions)o { id b=[self.native newBufferWithBytes:p length:n options:dm18_tracked(o)];[self.registry add:b];return b; }
- (id<MTLBuffer>)newBufferWithBytesNoCopy:(void *)p length:(NSUInteger)n options:(MTLResourceOptions)o deallocator:(void (^)(void *,NSUInteger))deallocator { id b=[self.native newBufferWithBytesNoCopy:p length:n options:dm18_tracked(o) deallocator:deallocator];[self.registry add:b];return b; }
- (id<MTLHeap>)newHeapWithDescriptor:(MTLHeapDescriptor *)d { MTLHeapDescriptor *copy=[d copy];copy.hazardTrackingMode=MTLHazardTrackingModeTracked;return [self.native newHeapWithDescriptor:copy]; }
- (id<MTLTexture>)newTextureWithDescriptor:(MTLTextureDescriptor *)d { MTLTextureDescriptor *copy=[d copy];copy.hazardTrackingMode=MTLHazardTrackingModeTracked;id t=[self.native newTextureWithDescriptor:copy];[self.registry add:t];return t; }
- (id<MTLSamplerState>)newSamplerStateWithDescriptor:(MTLSamplerDescriptor *)d { id s=[self.native newSamplerStateWithDescriptor:d];[self.registry add:s];return s; }
@end
static id<MTLDevice> dm18_device(void) { id<MTLDevice> native=MTLCreateSystemDefaultDevice();if (!native)return nil;DM18Device *d=[DM18Device new];d.native=native;d.queue=[native newCommandQueue];d.registry=[DM18Registry new];return d; }
static id<MTLDevice> dm18_native(id<MTLDevice> d) { return [(id)d isKindOfClass:DM18Device.class] ? ((DM18Device *)d).native : d; }
static void dm18_register(id<MTLDevice> d,id resource) { if ([(id)d isKindOfClass:DM18Device.class]) [((DM18Device *)d).registry add:resource]; }

#define MTL4ArgumentTable DM18Arguments
#define MTL4ArgumentTableDescriptor DM18ArgumentTableDescriptor
#define MTL4CommandAllocator DM18Allocator
#define MTL4CommandAllocatorDescriptor DM18AllocatorDescriptor
#define MTL4CommandQueue DM18CommandQueue
#define MTL4CommandQueueDescriptor DM18QueueDescriptor
#define MTL4CommandBuffer DM18CommandBuffer
#define MTL4CommandEncoder DM18Encoder
#define MTL4RenderCommandEncoder DM18RenderEncoder
#define MTL4ComputeCommandEncoder DM18ComputeEncoder
#define MTL4RenderPassDescriptor MTLRenderPassDescriptor
#define MTL4RenderPassColorAttachmentDescriptor MTLRenderPassColorAttachmentDescriptor
#define MTL4CommitOptions DM18CommitOptions
#define MTL4CommitFeedback MTLCommandBuffer
#pragma clang diagnostic pop

// CLASSIC_TEMPORAL_REGRESSION: closed-form image oracle, not a golden screenshot.
static void temporal_source_pixel(int frame,int x,int y,uint8_t out[4]) {
    static const uint8_t colors[4][3]={{48,112,192},{192,80,40},{64,176,128},{208,144,80}};
    int q=(x>=8)+2*(y>=8),phase=frame/120;
    for(int c=0;c<3;c++)out[c]=phase?16+(colors[q][c]+frame*(7+12*c))%224:colors[q][c];
    out[3]=255;
}
static void temporal_expected(int frame,int x,int y,uint8_t out[4]) {
    int phase=frame/120,cropped=phase==2&&(frame&1),left=cropped?8:0,vw=cropped?16:32,cw=cropped?8:16;
    if(x<left||x>=left+vw){out[0]=out[1]=out[2]=0;out[3]=255;return;}
    double sx=(x-left+.5)*cw/vw-.5,sy=(y+.5)*16/32-.5;
    if(phase==3&&(frame&1))sy=15-sy;
    sx=fmax(0,fmin(cw-1,sx));sy=fmax(0,fmin(15,sy));
    int x0=(int)floor(sx),y0=(int)floor(sy),x1=MIN(cw-1,x0+1),y1=MIN(15,y0+1);double fx=sx-x0,fy=sy-y0;
    uint8_t p00[4],p10[4],p01[4],p11[4];
    temporal_source_pixel(frame,x0,y0,p00);temporal_source_pixel(frame,x1,y0,p10);temporal_source_pixel(frame,x0,y1,p01);temporal_source_pixel(frame,x1,y1,p11);
    for(int c=0;c<3;c++)out[c]=(uint8_t)lrint((p00[c]*(1-fx)+p10[c]*fx)*(1-fy)+(p01[c]*(1-fx)+p11[c]*fx)*fy);
    out[3]=255;
}
static void classic_temporal_test(void) {
    enum{SLOTS=3,FRAMES=480};
    id<MTLTexture> sources[SLOTS][2]={{nil}},targets[SLOTS]={nil};
    id<MTLBuffer> readbacks[SLOTS]={nil},uvs[SLOTS]={nil};
    id<MTL4CommandBuffer> pending[SLOTS]={nil};
    id<MTLSharedEvent> gate=[g_dev newSharedEvent];
    int badFrames=0,blackFrames=0,staleFrames=0,staticDrift=0,commandErrors=0;uint64_t staticHash=0;
    g_fx_mode=0;
    for(int slot=0;slot<SLOTS;slot++) {
        for(int srgb=0;srgb<2;srgb++) {
            MTLTextureDescriptor *d=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:srgb?MTLPixelFormatRGBA8Unorm_sRGB:MTLPixelFormatRGBA8Unorm width:16 height:16 mipmapped:NO];
            d.storageMode=MTLStorageModeShared;d.usage=MTLTextureUsageShaderRead|MTLTextureUsagePixelFormatView;sources[slot][srgb]=[g_dev newTextureWithDescriptor:d];
        }
        MTLTextureDescriptor *d=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:32 height:32 mipmapped:NO];
        d.storageMode=MTLStorageModePrivate;d.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead;targets[slot]=[g_dev newTextureWithDescriptor:d];
        readbacks[slot]=[g_dev newBufferWithLength:8192 options:MTLResourceStorageModeShared];uvs[slot]=[g_dev newBufferWithLength:64 options:MTLResourceStorageModeShared];pending[slot]=[g_dev newCommandBuffer];
    }
    for(int batch=0;batch<FRAMES/SLOTS;batch++) {
        // Prepare and encode the whole batch before submitting any of it: CPU
        // writes never overlap GPU use of the same source or UV ring slot.
        for(int slot=0;slot<SLOTS;slot++) {
            int frame=batch*SLOTS+slot,phase=frame/120,srgb=phase>=2&&(frame&1);
            if(phase>=2&&frame%7==0) {
                MTLTextureDescriptor *d=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:srgb?MTLPixelFormatRGBA8Unorm_sRGB:MTLPixelFormatRGBA8Unorm width:16 height:16 mipmapped:NO];
                d.storageMode=MTLStorageModeShared;d.usage=MTLTextureUsageShaderRead|MTLTextureUsagePixelFormatView;sources[slot][srgb]=[g_dev newTextureWithDescriptor:d];
            }
            uint8_t bytes[16*16*4];for(int y=0;y<16;y++)for(int x=0;x<16;x++)temporal_source_pixel(frame,x,y,bytes+4*(y*16+x));
            [sources[slot][srgb] replaceRegion:MTLRegionMake2D(0,0,16,16) mipmapLevel:0 withBytes:bytes bytesPerRow:64];
            atomic_store(&g_origin_ll,phase==3&&(frame&1));int crop[4]={0};if(phase==2&&(frame&1)){crop[2]=8;crop[3]=16;}
            [pending[slot] beginCommandBufferWithAllocator:nil];
            [((DM18CommandBuffer*)pending[slot]).native encodeWaitForEvent:gate value:batch+1];
            int kind=present_encode(pending[slot],sources[slot][srgb],targets[slot],crop,uvs[slot],NULL);
            if(kind!=PRESENT_STANDARD)commandErrors++;
            id<MTL4ComputeCommandEncoder> bl=[pending[slot] computeCommandEncoder];
            [bl copyFromTexture:targets[slot] sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(32,32,1) toBuffer:readbacks[slot] destinationOffset:0 destinationBytesPerRow:256 destinationBytesPerImage:8192];
            [bl endEncoding];[pending[slot] endCommandBuffer];
        }
        for(int slot=0;slot<SLOTS;slot++){id<MTL4CommandBuffer> cb=pending[slot];[g_q4 commit:&cb count:1];}
        gate.signaledValue=batch+1; // Forces a real three-command-buffer backlog.
        for(int slot=0;slot<SLOTS;slot++) {
            int frame=batch*SLOTS+slot,phase=frame/120;
            id<MTLCommandBuffer> cb=((DM18CommandBuffer*)pending[slot]).native;[cb waitUntilCompleted];
            if(cb.error||cb.status!=MTLCommandBufferStatusCompleted){commandErrors++;continue;}
            uint8_t *pixels=readbacks[slot].contents;BOOL bad=NO,allBlack=YES,oldMatch=phase>0&&frame>=SLOTS;uint64_t hash=14695981039346656037ULL;
            for(int y=0;y<32;y++)for(int x=0;x<32;x++) {
                uint8_t *p=pixels+y*256+x*4,want[4],old[4];temporal_expected(frame,x,y,want);
                if(oldMatch)temporal_expected(frame-SLOTS,x,y,old);
                const int channels[4]={2,1,0,3};
                for(int c=0;c<4;c++) {
                    if(abs((int)p[channels[c]]-want[c])>1)bad=YES;
                    if(oldMatch&&abs((int)p[channels[c]]-old[c])>1)oldMatch=NO;
                    hash^=p[c];hash*=1099511628211ULL;
                }
                if(p[0]||p[1]||p[2])allBlack=NO;
            }
            if(bad){if(badFrames<4)printf("temporal pixel mismatch frame %d phase %d\n",frame,phase);badFrames++;if(oldMatch)staleFrames++;}
            if(allBlack)blackFrames++;
            if(!phase){if(!frame)staticHash=hash;else if(hash!=staticHash)staticDrift++;}
        }
        // Exercise the replay's real retirement path between completed batches.
        mtl_sub_begin();uint64_t fence=mtl_sub_commit();mtl_wait(fence,UINT64_MAX);defer_drain();
    }
    atomic_store(&g_origin_ll,0);
    printf("{\"temporal_frames\":%d,\"inflight_slots\":%d,\"bad_frames\":%d,\"black_frames\":%d,\"stale_frames\":%d,\"static_hash_mismatches\":%d,\"command_errors\":%d}\n",FRAMES,SLOTS,badFrames,blackFrames,staleFrames,staticDrift,commandErrors);
    EXPECT("temporal pixel frames",0,badFrames);EXPECT("temporal black frames",0,blackFrames);EXPECT("temporal stale frames",0,staleFrames);EXPECT("static image drift",0,staticDrift);EXPECT("temporal command errors",0,commandErrors);
}

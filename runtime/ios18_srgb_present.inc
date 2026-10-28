    { // CLASSIC_SRGB_REGRESSION: independent of optional Metal-4 upscaling.
        const int width=16,height=16;g_fx_mode=0;
        MTLTextureDescriptor *sourceDesc=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm_sRGB width:width height:height mipmapped:NO];
        sourceDesc.storageMode=MTLStorageModeShared;sourceDesc.usage=MTLTextureUsageShaderRead|MTLTextureUsagePixelFormatView;
        id<MTLTexture> source=[g_dev newTextureWithDescriptor:sourceDesc];
        uint8_t bytes[16*16*4];for(int i=0;i<width*height;i++){bytes[4*i]=128;bytes[4*i+1]=64;bytes[4*i+2]=192;bytes[4*i+3]=255;}
        [source replaceRegion:MTLRegionMake2D(0,0,width,height) mipmapLevel:0 withBytes:bytes bytesPerRow:width*4];
        MTLTextureDescriptor *targetDesc=[MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:width height:height mipmapped:NO];
        targetDesc.storageMode=MTLStorageModePrivate;targetDesc.usage=MTLTextureUsageRenderTarget|MTLTextureUsageShaderRead;
        id<MTLTexture> target=[g_dev newTextureWithDescriptor:targetDesc];int whole[4]={0};
        EXPECT("classic sRGB present uses the standard path",PRESENT_STANDARD,present_offscreen_wait(source,whole,target));
        id<MTLBuffer> readback=[g_dev newBufferWithLength:4096 options:MTLResourceStorageModeShared];
        id<MTLCommandBuffer> cb=[g_q commandBuffer];id<MTLBlitCommandEncoder> bl=[cb blitCommandEncoder];
        [bl copyFromTexture:target sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(width,height,1) toBuffer:readback destinationOffset:0 destinationBytesPerRow:256 destinationBytesPerImage:4096];
        [bl endEncoding];[cb commit];[cb waitUntilCompleted];uint8_t *p=(uint8_t*)readback.contents+8*256+8*4;
        EXPECT("classic sRGB raw red",128,p[2]);EXPECT("classic sRGB raw green",64,p[1]);EXPECT("classic sRGB raw blue",192,p[0]);EXPECT("classic sRGB raw alpha",255,p[3]);
    }

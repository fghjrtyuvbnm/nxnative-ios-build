"""Prepare a candidate from the exact classic-adapter baseline, for native contracts."""
def candidate(text):
    old='- (id<MTLCommandQueue>)newCommandQueue { return self.queue; }'
    if text.count(old)!=1:raise ValueError('Classic queue source differs')
    text=text.replace(old,'- (id<MTLCommandQueue>)newCommandQueue { return [self.native newCommandQueue]; }')
    implementation=text.index('@implementation DM18Registry')
    for signature in ('- (void)add:', '- (id<MTLBuffer>)buffer:', '- (id)texture:', '- (id)sampler:', '- (NSArray *)resources:'):
        start=text.index(signature,implementation);brace=text.index('{',start);depth=1;end=brace+1
        while depth:
            if text[end]=='{':depth+=1
            elif text[end]=='}':depth-=1
            end+=1
        text=text[:brace+1]+' @autoreleasepool { '+text[brace+1:end-1]+' } '+text[end-1:]
    return text

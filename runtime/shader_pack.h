// Immutable pack-v1 reader. One descriptor per pack, bounded per-entry allocation.
#pragma once
#import <Foundation/Foundation.h>
#import <CommonCrypto/CommonDigest.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>
#include <errno.h>
#include <stdio.h>

static NSError *dm_pack_error(NSString *message) { return [NSError errorWithDomain:@"org.nxnative.shader-pack" code:1 userInfo:@{NSLocalizedDescriptionKey:message}]; }
@interface DMShaderPack : NSObject {
    int _fd;
    NSDictionary *_entries;
    NSError *_failure;
}
- (instancetype)initWithDirectory:(NSString *)directory;
- (instancetype)invalid;
- (NSData *)read:(NSString *)name error:(NSError **)error;
@end
@implementation DMShaderPack
- (instancetype)initWithDirectory:(NSString *)directory {
    if (!(self=[super init]))return nil;
    _fd=-1;
    NSString *indexPath=[directory stringByAppendingPathComponent:@"shaders.index.json"];
    NSDictionary *attrs=[NSFileManager.defaultManager attributesOfItemAtPath:indexPath error:nil];
    unsigned long long indexSize=[attrs[NSFileSize] unsignedLongLongValue];
    if (![attrs[NSFileType] isEqual:NSFileTypeRegular] || !indexSize || indexSize>64*1024*1024)return [self invalid];
    NSData *data=[NSData dataWithContentsOfFile:indexPath options:0 error:nil];
    NSDictionary *index=data?[NSJSONSerialization JSONObjectWithData:data options:0 error:nil]:nil;
    if (![index isKindOfClass:NSDictionary.class] || ![index[@"version"] isEqual:@1] || ![index[@"entries"] isKindOfClass:NSDictionary.class] || ![index[@"bytes"] isKindOfClass:NSNumber.class])return [self invalid];
    _entries=index[@"entries"];
    if (!_entries.count || _entries.count>200000)return [self invalid];
    uint64_t offset=0;
    NSRegularExpression *namePattern=[NSRegularExpression regularExpressionWithPattern:@"^[0-9a-zA-Z_-]+\\.(json|metallib)$" options:0 error:nil];
    NSRegularExpression *hashPattern=[NSRegularExpression regularExpressionWithPattern:@"^[0-9a-f]{64}$" options:0 error:nil];
    for (NSString *name in [[_entries allKeys] sortedArrayUsingSelector:@selector(compare:)]) {
        NSArray *row=_entries[name];
        if (![name isKindOfClass:NSString.class] || [namePattern numberOfMatchesInString:name options:0 range:NSMakeRange(0,name.length)]!=1 || ![row isKindOfClass:NSArray.class] || row.count!=3)return [self invalid];
        if (![row[0] isKindOfClass:NSNumber.class] || ![row[1] isKindOfClass:NSNumber.class] || ![row[2] isKindOfClass:NSString.class])return [self invalid];
        uint64_t start=[row[0] unsignedLongLongValue],length=[row[1] unsignedLongLongValue];
        if (start!=offset || !length || length>64*1024*1024 || [hashPattern numberOfMatchesInString:row[2] options:0 range:NSMakeRange(0,[row[2] length])]!=1)return [self invalid];
        // Numeric values must be nonnegative integral offsets, not rounded JSON floats.
        if (![[NSNumber numberWithUnsignedLongLong:start] isEqual:row[0]] || ![[NSNumber numberWithUnsignedLongLong:length] isEqual:row[1]])return [self invalid];
        offset+=length;
    }
    if (offset!=[index[@"bytes"] unsignedLongLongValue])return [self invalid];
    _fd=open([[directory stringByAppendingPathComponent:@"shaders.pack"] fileSystemRepresentation],O_RDONLY|O_NOFOLLOW);
    struct stat st;
    if (_fd<0 || fstat(_fd,&st) || !S_ISREG(st.st_mode) || st.st_size<0 || (uint64_t)st.st_size!=offset)return [self invalid];
    return self;
}
- (instancetype)invalid {
    _failure=dm_pack_error(@"Invalid or incomplete shader pack");
    if (_fd>=0){close(_fd);_fd=-1;}
    return self;
}
- (void)dealloc { if (_fd>=0)close(_fd); }
- (NSData *)read:(NSString *)name error:(NSError **)error {
    if (_failure){if(error)*error=_failure;return nil;}
    NSArray *row=_entries[name];if (!row)return nil;
    NSUInteger length=[row[1] unsignedIntegerValue];off_t offset=[row[0] longLongValue];
    NSMutableData *data=[NSMutableData dataWithLength:length];
    if (!data){if(error)*error=dm_pack_error(@"Cannot allocate shader entry");return nil;}
    NSUInteger done=0;
    while(done<length){ssize_t n=pread(_fd,(uint8_t *)data.mutableBytes+done,length-done,offset+done);if(n<0&&errno==EINTR)continue;if(n<=0){if(error)*error=dm_pack_error(@"Truncated shader pack");return nil;}done+=(NSUInteger)n;}
    unsigned char hash[CC_SHA256_DIGEST_LENGTH];CC_SHA256(data.bytes,(CC_LONG)data.length,hash);
    char hex[65];for(int i=0;i<32;i++)snprintf(hex+2*i,3,"%02x",hash[i]);
    if (![row[2] isEqualToString:@(hex)]){if(error)*error=dm_pack_error(@"Shader pack content hash mismatch");return nil;}
    return data;
}
@end

static NSData *dm_shader_data(NSString *path,NSError **error) {
    NSString *directory=path.stringByDeletingLastPathComponent;
    static NSLock *lock;static NSMutableDictionary *packs;static dispatch_once_t once;
    dispatch_once(&once,^{lock=[NSLock new];packs=[NSMutableDictionary dictionary];});
    [lock lock];DMShaderPack *pack=packs[directory];
    if (!pack && ([NSFileManager.defaultManager fileExistsAtPath:[directory stringByAppendingPathComponent:@"shaders.index.json"]] || [NSFileManager.defaultManager fileExistsAtPath:[directory stringByAppendingPathComponent:@"shaders.pack"]])) {
        pack=[[DMShaderPack alloc] initWithDirectory:directory];packs[directory]=pack;
    }
    [lock unlock];
    return pack?[pack read:path.lastPathComponent error:error]:[NSData dataWithContentsOfFile:path options:NSDataReadingMappedIfSafe error:error];
}

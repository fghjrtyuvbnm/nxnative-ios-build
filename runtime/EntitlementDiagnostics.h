// Read only the installed app's two memory entitlement flags. Never log profiles.
#pragma once
#import <Foundation/Foundation.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
static uint32_t dm_be32(const uint8_t *p){return ((uint32_t)p[0]<<24)|((uint32_t)p[1]<<16)|((uint32_t)p[2]<<8)|p[3];}
static uint32_t dm_le32(const uint8_t *p){return p[0]|((uint32_t)p[1]<<8)|((uint32_t)p[2]<<16)|((uint32_t)p[3]<<24);}
static NSDictionary *dm_signature_entitlements(NSData *data){
    const uint8_t *p=data.bytes;size_t n=data.length;
    if(n<12||dm_be32(p)!=0xfade0cc0)return nil;
    uint32_t length=dm_be32(p+4),count=dm_be32(p+8);
    if(length>n||count>128||12+(uint64_t)count*8>length)return nil;
    for(uint32_t i=0;i<count;i++)if(dm_be32(p+12+i*8)==5){
        uint32_t offset=dm_be32(p+16+i*8);
        if((uint64_t)offset+8>length)return nil;
        uint32_t size=dm_be32(p+offset+4);
        if(dm_be32(p+offset)!=0xfade7171||size<8||size>1024*1024||(uint64_t)offset+size>length)return nil;
        NSData *xml=[data subdataWithRange:NSMakeRange(offset+8,size-8)];
        id result=[NSPropertyListSerialization propertyListWithData:xml options:NSPropertyListImmutable format:NULL error:nil];
        return [result isKindOfClass:NSDictionary.class]?result:nil;
    }
    return nil; // DER-only or absent XML is unknown, not a false entitlement claim.
}
static NSData *dm_read_region(int fd,off_t offset,size_t size){
    if(size>16*1024*1024)return nil;NSMutableData *data=[NSMutableData dataWithLength:size];size_t done=0;
    while(done<size){ssize_t n=pread(fd,(uint8_t*)data.mutableBytes+done,size-done,offset+done);if(n<=0)return nil;done+=(size_t)n;}
    return data;
}
static NSDictionary *dm_installed_signature(NSString *path){
    int fd=open(path.fileSystemRepresentation,O_RDONLY);if(fd<0)return nil;
    NSDictionary *result=nil;NSData *header=dm_read_region(fd,0,32);const uint8_t *p=header.bytes;
    if(header.length==32&&dm_le32(p)==0xfeedfacf){
        uint32_t count=dm_le32(p+16),size=dm_le32(p+20);
        if(count<=4096&&size<=1024*1024){
            NSData *commands=dm_read_region(fd,32,size);p=commands.bytes;size_t offset=0;
            for(uint32_t i=0;commands&&i<count;i++){
                if(offset+8>size)break;uint32_t command=dm_le32(p+offset),length=dm_le32(p+offset+4);
                if(length<8||offset+length>size)break;
                if(command==0x1d&&length>=16){NSData *signature=dm_read_region(fd,dm_le32(p+offset+8),dm_le32(p+offset+12));if(signature)result=dm_signature_entitlements(signature);break;}
                offset+=length;
            }
        }
    }
    close(fd);return result;
}
static NSDictionary *dm_profile_entitlements(NSString *path){
    NSDictionary *attributes=[NSFileManager.defaultManager attributesOfItemAtPath:path error:nil];
    if(!attributes||[attributes[NSFileSize] unsignedLongLongValue]>16*1024*1024)return nil;
    NSData *data=[NSData dataWithContentsOfFile:path];if(!data)return nil;
    NSData *begin=[@"<plist" dataUsingEncoding:NSUTF8StringEncoding],*end=[@"</plist>" dataUsingEncoding:NSUTF8StringEncoding];
    NSRange a=[data rangeOfData:begin options:0 range:NSMakeRange(0,data.length)];if(a.location==NSNotFound)return nil;
    NSRange b=[data rangeOfData:end options:0 range:NSMakeRange(a.location,data.length-a.location)];if(b.location==NSNotFound)return nil;
    NSData *xml=[data subdataWithRange:NSMakeRange(a.location,b.location+b.length-a.location)];
    id profile=[NSPropertyListSerialization propertyListWithData:xml options:NSPropertyListImmutable format:NULL error:nil];
    id ent=[profile isKindOfClass:NSDictionary.class]?profile[@"Entitlements"]:nil;
    return [ent isKindOfClass:NSDictionary.class]?ent:nil;
}
static int dm_entitlement_flag(NSDictionary *entitlements,NSString *key){if(!entitlements)return -1;id value=entitlements[key];if(!value)return 0;return [value isKindOfClass:NSNumber.class]?[value boolValue]:-1;}
static void dm_signing_memory_note_paths(NSString *executable,NSString *provision){@autoreleasepool{
    NSDictionary *signature=dm_installed_signature(executable);
    NSDictionary *profile=dm_profile_entitlements(provision);
    NSString *memory=@"com.apple.developer.kernel.increased-memory-limit",*address=@"com.apple.developer.kernel.extended-virtual-addressing";
    fprintf(stderr,"[signingdiag] signed_memory_request=%d signed_extended_va_request=%d profile_memory_permission=%d profile_extended_va_permission=%d (-1=unknown)\n",dm_entitlement_flag(signature,memory),dm_entitlement_flag(signature,address),dm_entitlement_flag(profile,memory),dm_entitlement_flag(profile,address));
}}
static void dm_signing_memory_note(void){dm_signing_memory_note_paths(NSBundle.mainBundle.executablePath,[NSBundle.mainBundle.bundlePath stringByAppendingPathComponent:@"embedded.mobileprovision"]);}

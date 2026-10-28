#include "EntitlementDiagnostics.h"
#define REQUIRE(x) do{if(!(x)){fprintf(stderr,"Signing observation fixture failed line %d\n",__LINE__);return 1;}}while(0)
int main(int argc,char **argv){@autoreleasepool{
    REQUIRE(argc==2);NSString *root=@(argv[1]);
    NSString *memory=@"com.apple.developer.kernel.increased-memory-limit",*address=@"com.apple.developer.kernel.extended-virtual-addressing";
    NSDictionary *signature=dm_installed_signature([root stringByAppendingPathComponent:@"app"]);
    REQUIRE(dm_entitlement_flag(signature,memory)==1&&dm_entitlement_flag(signature,address)==0);
    NSDictionary *profile=dm_profile_entitlements([root stringByAppendingPathComponent:@"profile"]);
    REQUIRE(dm_entitlement_flag(profile,memory)==0&&dm_entitlement_flag(profile,address)==1);
    for(NSString *name in @[@"unsigned",@"truncated",@"invalid",@"der-only"]){
        REQUIRE(dm_entitlement_flag(dm_installed_signature([root stringByAppendingPathComponent:name]),memory)==-1);
    }
    REQUIRE(dm_profile_entitlements([root stringByAppendingPathComponent:@"bad-profile"])==nil);
    dm_signing_memory_note_paths([root stringByAppendingPathComponent:@"app"],[root stringByAppendingPathComponent:@"profile"]);
    NSUInteger before=[NSFileManager.defaultManager contentsOfDirectoryAtPath:@"/dev/fd" error:nil].count;
    for(int i=0;i<100;i++)@autoreleasepool{REQUIRE(dm_installed_signature([root stringByAppendingPathComponent:@"app"])!=nil);REQUIRE(dm_installed_signature([root stringByAppendingPathComponent:@"invalid"])==nil);}
    NSUInteger after=[NSFileManager.defaultManager contentsOfDirectoryAtPath:@"/dev/fd" error:nil].count;REQUIRE(after==before);
    puts("Signing flag parser fixtures and descriptor lifetime passed");return 0;
}}

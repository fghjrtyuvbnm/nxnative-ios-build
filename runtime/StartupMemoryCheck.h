#pragma once
#include "EntitlementDiagnostics.h"
#include <mach/mach.h>
#include <os/proc.h>
int32_t dm_startup_memory_flags(void) {
    NSString *key=@"com.apple.developer.kernel.increased-memory-limit";
    int s=dm_entitlement_flag(dm_installed_signature(NSBundle.mainBundle.executablePath),key);
    int p=dm_entitlement_flag(dm_profile_entitlements([NSBundle.mainBundle.bundlePath stringByAppendingPathComponent:@"embedded.mobileprovision"]),key);
    return (s+1)|((p+1)<<2);
}
uint64_t dm_startup_memory_footprint(void) {
    task_vm_info_data_t info={0};mach_msg_type_number_t count=TASK_VM_INFO_COUNT;
    kern_return_t result=task_info(mach_task_self(),TASK_VM_INFO,(task_info_t)&info,&count);
    return result==KERN_SUCCESS&&count>=TASK_VM_INFO_REV1_COUNT?info.phys_footprint:UINT64_MAX;
}
static void dm_startup_memory_note(const char *stage) {
    int flags=dm_startup_memory_flags();uint64_t available=os_proc_available_memory(),footprint=dm_startup_memory_footprint();
    fprintf(stderr,"[memory-check] stage=%s signature_memory=%d profile_memory=%d available_bytes=%llu footprint_bytes=%llu (-1=unknown; footprint UINT64_MAX=unknown; allowance is advisory)\n",stage,(flags&3)-1,((flags>>2)&3)-1,(unsigned long long)available,(unsigned long long)footprint);
}

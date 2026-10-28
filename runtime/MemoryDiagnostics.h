// Observation only: no entitlement claims or allocator policy changes.
#pragma once
#include <stdio.h>
#include <mach/mach.h>
#include <TargetConditionals.h>
#if TARGET_OS_IPHONE
#include <os/proc.h>
#endif
static inline void dm_memory_note(const char *stage) {
    task_vm_info_data_t info={0};mach_msg_type_number_t count=TASK_VM_INFO_COUNT;
    kern_return_t result=task_info(mach_task_self(),TASK_VM_INFO,(task_info_t)&info,&count);
    unsigned long long available=0;
#if TARGET_OS_IPHONE
    available=(unsigned long long)os_proc_available_memory();
#endif
    fprintf(stderr,"[memdiag] stage=%s available_bytes=%llu footprint_bytes=%llu resident_bytes=%llu virtual_bytes=%llu task_info_status=%d\n",stage,available,
        result==KERN_SUCCESS&&count>=TASK_VM_INFO_REV1_COUNT?(unsigned long long)info.phys_footprint:0,
        result==KERN_SUCCESS?(unsigned long long)info.resident_size:0,
        result==KERN_SUCCESS?(unsigned long long)info.virtual_size:0,result);
}

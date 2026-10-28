// Independent VM backing for large UE allocations. No fallback or malloc metadata.
#pragma once
#define UE_LARGE_VM_V1 1
#include <stdint.h>
#include <stddef.h>
#include <errno.h>
#include <stdio.h>
#ifdef _WIN32
#include <windows.h>
static SRWLOCK ue_vm_lock=SRWLOCK_INIT;
#define UE_LOCK() AcquireSRWLockExclusive(&ue_vm_lock)
#define UE_UNLOCK() ReleaseSRWLockExclusive(&ue_vm_lock)
static size_t ue_vm_page(void){SYSTEM_INFO info;GetSystemInfo(&info);return info.dwPageSize;}
#else
#include <pthread.h>
#include <unistd.h>
#include <mach/mach.h>
static pthread_mutex_t ue_vm_lock=PTHREAD_MUTEX_INITIALIZER;
#define UE_LOCK() pthread_mutex_lock(&ue_vm_lock)
#define UE_UNLOCK() pthread_mutex_unlock(&ue_vm_lock)
static size_t ue_vm_page(void){return (size_t)getpagesize();}
#endif
#ifndef UE_VM_ALLOCATE
#ifdef _WIN32
static int ue_vm_native_allocate(uintptr_t *address,size_t size){*address=(uintptr_t)VirtualAlloc(NULL,size,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);return *address?0:-1;}
#define UE_VM_RELEASE(address,size) (VirtualFree((void *)(address),0,MEM_RELEASE)?0:-1)
#else
static int ue_vm_native_allocate(uintptr_t *address,size_t size){vm_address_t at=0;int result=vm_allocate(mach_task_self(),&at,(vm_size_t)size,VM_FLAGS_ANYWHERE);*address=at;return result;}
#define UE_VM_RELEASE(address,size) vm_deallocate(mach_task_self(),(vm_address_t)(address),(vm_size_t)(size))
#endif
#define UE_VM_ALLOCATE(address,size) ue_vm_native_allocate(address,size)
#endif
typedef struct UEVirtualBlock {uintptr_t base,pointer;size_t map_size,usable;struct UEVirtualBlock *next;} UEVirtualBlock;
static UEVirtualBlock *ue_vm_blocks[4096];
static size_t ue_vm_bucket(uintptr_t pointer){return (pointer>>14)%4096;}
static size_t ue_vm_round(size_t size){size_t page=ue_vm_page();if(size>SIZE_MAX-(page-1))return 0;return (size+page-1)&~(page-1);}
static void *ue_vm_alloc(size_t size,size_t alignment){
    if(!size||!alignment||(alignment&(alignment-1))){errno=EINVAL;return NULL;}
    size_t page=ue_vm_page(),usable=ue_vm_round(size);if(alignment<page)alignment=page;
    if(!usable||usable>SIZE_MAX-alignment){errno=ENOMEM;return NULL;}
    size_t total=usable+alignment;uintptr_t base=0;
    int backend_result=UE_VM_ALLOCATE(&base,total);
    if(backend_result!=0){fprintf(stderr,"[ue-vm] allocate_failed requested_bytes=%zu usable_bytes=%zu mapping_bytes=%zu alignment=%zu page_bytes=%zu backend_result=%d\n",size,usable,total,alignment,page,backend_result);errno=ENOMEM;return NULL;}
    // One header page keeps ownership metadata out of the constrained malloc path.
    uintptr_t pointer=(base+page+alignment-1)&~(uintptr_t)(alignment-1);
    UEVirtualBlock *block=(UEVirtualBlock *)base;
    block->base=base;block->pointer=pointer;block->map_size=total;block->usable=usable;
    size_t bucket=ue_vm_bucket(pointer);UE_LOCK();block->next=ue_vm_blocks[bucket];ue_vm_blocks[bucket]=block;UE_UNLOCK();
    return (void *)pointer;
}
static size_t ue_vm_size(const void *pointer){
    size_t size=0;UE_LOCK();for(UEVirtualBlock *block=ue_vm_blocks[ue_vm_bucket((uintptr_t)pointer)];block;block=block->next)if(block->pointer==(uintptr_t)pointer){size=block->usable;break;}UE_UNLOCK();return size;
}
// 0: another allocator owns it; 1: released; -1: kernel refused, record retained.
static int ue_vm_free(void *pointer,size_t *released){
    int result=0;UE_LOCK();UEVirtualBlock **at=&ue_vm_blocks[ue_vm_bucket((uintptr_t)pointer)];
    while(*at&&(*at)->pointer!=(uintptr_t)pointer)at=&(*at)->next;
    if(*at){UEVirtualBlock *block=*at,*next=block->next;size_t usable=block->usable;
        if(UE_VM_RELEASE(block->base,block->map_size)==0){*at=next;*released=usable;result=1;}else result=-1;
    }
    UE_UNLOCK();return result;
}

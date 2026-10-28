// Backend-limited characterization fixture, not a claim to reproduce iOS VM ranges.
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <stdatomic.h>
#ifdef _WIN32
#include <windows.h>
#include <malloc.h>
static SRWLOCK zone_lock=SRWLOCK_INIT;
#define LOCK() AcquireSRWLockExclusive(&zone_lock)
#define UNLOCK() ReleaseSRWLockExclusive(&zone_lock)
#else
#include <pthread.h>
#include <mach/mach.h>
#include <unistd.h>
static pthread_mutex_t zone_lock=PTHREAD_MUTEX_INITIALIZER;
#define LOCK() pthread_mutex_lock(&zone_lock)
#define UNLOCK() pthread_mutex_unlock(&zone_lock)
#endif
typedef struct Record{void *pointer;size_t size;struct Record *next;} Record;
static Record *records;
static _Atomic int deny_large_zone=1,deny_vm=0,deny_vm_release=0;
static _Atomic int64_t live_vm_bytes=0;
static _Atomic int64_t balance=0;
static void *g_zone=(void *)1;
static void used(int64_t n){atomic_fetch_add(&balance,n);}
static void *zone_alloc(size_t size,size_t alignment){
    if(atomic_load(&deny_large_zone)&&size>=1024*1024){errno=ENOMEM;return NULL;}
    if(alignment<sizeof(void *) || (alignment&(alignment-1))){errno=EINVAL;return NULL;}
    void *pointer=NULL;
#ifdef _WIN32
    pointer=_aligned_malloc(size,alignment);
#else
    if(posix_memalign(&pointer,alignment,size))pointer=NULL;
#endif
    if(!pointer)return NULL;
    Record *record=malloc(sizeof *record);if(!record)abort();
    record->pointer=pointer;record->size=size;
    LOCK();record->next=records;records=record;UNLOCK();return pointer;
}
static size_t test_size(void *pointer){size_t size=0;LOCK();for(Record*r=records;r;r=r->next)if(r->pointer==pointer){size=r->size;break;}UNLOCK();return size;}
static void zone_free(void *pointer){LOCK();Record **at=&records;while(*at&&(*at)->pointer!=pointer)at=&(*at)->next;if(!*at)abort();Record*r=*at;*at=r->next;UNLOCK();
#ifdef _WIN32
    _aligned_free(pointer);
#else
    free(pointer);
#endif
    free(r);
}
static void *zone_realloc(void *pointer,size_t size){size_t old=test_size(pointer);if(!old)abort();void *q=zone_alloc(size,16);if(q){memcpy(q,pointer,old<size?old:size);zone_free(pointer);}return q;}
#define malloc_zone_malloc(zone,size) zone_alloc(size,16)
#define malloc_zone_memalign(zone,alignment,size) zone_alloc(size,alignment)
#define malloc_zone_free(zone,pointer) zone_free(pointer)
#define malloc_zone_realloc(zone,pointer,size) zone_realloc(pointer,size)
#define malloc_size(pointer) test_size(pointer)
static int backend_allocate(uintptr_t *address,size_t size){
    if(atomic_load(&deny_vm))return -1;
#ifdef _WIN32
    *address=(uintptr_t)VirtualAlloc(NULL,size,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);if(*address)atomic_fetch_add(&live_vm_bytes,size);return *address?0:-1;
#else
    vm_address_t result=0;int status=vm_allocate(mach_task_self(),&result,size,VM_FLAGS_ANYWHERE);*address=result;if(!status)atomic_fetch_add(&live_vm_bytes,size);return status;
#endif
}
static int backend_release(uintptr_t address,size_t size){
    if(atomic_load(&deny_vm_release))return -1;
#ifdef _WIN32
    int status=VirtualFree((void *)address,0,MEM_RELEASE)?0:-1;
#else
    int status=vm_deallocate(mach_task_self(),address,size);
#endif
    if(!status)atomic_fetch_sub(&live_vm_bytes,size);return status;
}
#define UE_VM_ALLOCATE(address,size) backend_allocate(address,size)
#define UE_VM_RELEASE(address,size) backend_release(address,size)
#include "core-under-test.inc"
static size_t allocation_size(void *p){
#ifdef UE_LARGE_VM_V1
    return ue_size(p);
#else
    return malloc_size(p);
#endif
}
#define REQUIRE(x) do{if(!(x)){fprintf(stderr,"allocator contract failed line %d: %s\n",__LINE__,#x);exit(1);}}while(0)
static void exercise(int id){
    for(int k=0;k<40;k++){
        size_t n=1024*1024+(size_t)id*8192+k*31;unsigned char pattern=(unsigned char)(17+id+k);
        unsigned char*p=alloc(n,65536);REQUIRE(p&&((uintptr_t)p%65536)==0);memset(p,pattern,n);
        unsigned char*q=realloc_aligned(p,n+65537,65536);REQUIRE(q&&((uintptr_t)q%65536)==0);
        for(size_t i=0;i<n;i++)REQUIRE(q[i]==pattern);
        p=realloc_aligned(q,8192,16);REQUIRE(p);for(int i=0;i<8192;i++)REQUIRE(p[i]==pattern);release(p);
    }
}
#ifdef _WIN32
static DWORD WINAPI worker(void*p){exercise((int)(uintptr_t)p);return 0;}
#else
static void *worker(void*p){exercise((int)(uintptr_t)p);return NULL;}
#endif
int main(void){
    uintptr_t probe=0;REQUIRE(backend_allocate(&probe,2*1024*1024)==0);REQUIRE(backend_release(probe,2*1024*1024)==0);
    void *large=alloc(2*1024*1024+137,65536);
    REQUIRE(large!=NULL); // RED on the original malloc-only policy under a limited backend.
    REQUIRE(((uintptr_t)large%65536)==0&&allocation_size(large)>=2*1024*1024+137);
    memset(large,0x81,2*1024*1024+137);size_t old_size=allocation_size(large);atomic_store(&deny_vm,1);
    REQUIRE(realloc_aligned(large,3*1024*1024,65536)==NULL&&allocation_size(large)==old_size);
    for(int i=0;i<2*1024*1024+137;i++)REQUIRE(((unsigned char*)large)[i]==0x81);
    atomic_store(&deny_vm,0);release(large);
    unsigned char*p=alloc(4096,0);REQUIRE(p);memset(p,0x53,4096);
    atomic_store(&deny_vm,1);REQUIRE(realloc_aligned(p,2*1024*1024,0)==NULL);for(int i=0;i<4096;i++)REQUIRE(p[i]==0x53);
    atomic_store(&deny_vm,0);unsigned char*q=realloc_aligned(p,2*1024*1024,0);REQUIRE(q);for(int i=0;i<4096;i++)REQUIRE(q[i]==0x53);release(q);
#ifdef UE_LARGE_VM_V1
    REQUIRE(ue_vm_alloc(SIZE_MAX,16)==NULL);REQUIRE(ue_vm_alloc(2*1024*1024,24)==NULL);
    void *retained=ue_vm_alloc(1024*1024,16);REQUIRE(retained);size_t released=0;atomic_store(&deny_vm_release,1);
    REQUIRE(ue_vm_free(retained,&released)==-1&&ue_vm_size(retained)>=1024*1024);
    atomic_store(&deny_vm_release,0);REQUIRE(ue_vm_free(retained,&released)==1&&ue_vm_size(retained)==0);
    const uint32_t alignments[]={0,1,16,4096,65536,1024*1024};
    for(int j=0;j<6;j++)for(int d=-1;d<=1;d++){size_t n=(size_t)((int)UE_VM_THRESHOLD+d);void *x=alloc(n,alignments[j]);REQUIRE(x&&((uintptr_t)x%align_of(alignments[j]))==0&&allocation_size(x)>=n);release(x);}
#endif
#ifdef _WIN32
    HANDLE threads[4];for(int i=0;i<4;i++)threads[i]=CreateThread(NULL,0,worker,(void *)(uintptr_t)(i+1),0,NULL);
    REQUIRE(WaitForMultipleObjects(4,threads,TRUE,60000)==WAIT_OBJECT_0);for(int i=0;i<4;i++)CloseHandle(threads[i]);
#else
    pthread_t threads[4];for(int i=0;i<4;i++)REQUIRE(pthread_create(&threads[i],NULL,worker,(void *)(uintptr_t)(i+1))==0);for(int i=0;i<4;i++)pthread_join(threads[i],NULL);
#endif
    REQUIRE(atomic_load(&balance)==0&&records==NULL&&atomic_load(&live_vm_bytes)==0);
#ifdef UE_LARGE_VM_V1
    for(int i=0;i<4096;i++)REQUIRE(ue_vm_blocks[i]==NULL);
#endif
    puts("UE allocator contract passed: limited malloc backend, VM commitment, alignment, migration, failed-growth retention, concurrent lifetime and zero balance");return 0;
}

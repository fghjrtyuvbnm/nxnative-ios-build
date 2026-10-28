// UE_LARGE_VM_POLICY: route large allocations directly, never retry a failed malloc.
#include "UELargeVM.h"
#define UE_VM_THRESHOLD ((size_t)1024*1024)
static size_t align_of(uint32_t a){return a>16?a:16;}
static size_t ue_size(void *p){size_t n=ue_vm_size(p);return n?n:malloc_size(p);}
static int ue_valid_alignment(uint32_t a){size_t align=align_of(a);if(align&(align-1)){errno=EINVAL;return 0;}return 1;}
static void *alloc(size_t n,uint32_t a){
    if(!ue_valid_alignment(a))return NULL;
    void *p=n>=UE_VM_THRESHOLD?ue_vm_alloc(n,align_of(a)):(align_of(a)==16?malloc_zone_malloc(g_zone,n?n:1):malloc_zone_memalign(g_zone,align_of(a),n?n:1));
    if(p)used((int64_t)ue_size(p));return p;
}
static void release(void *p){
    if(!p)return;size_t bytes=0;int result=ue_vm_free(p,&bytes);
    if(result<0)abort(); // Never silently lose a live mapping after failed deallocation.
    if(result){used(-(int64_t)bytes);return;}
    used(-(int64_t)malloc_size(p));malloc_zone_free(g_zone,p);
}
static void *realloc_aligned(void *p,size_t n,uint32_t a){
    if(!p)return alloc(n,a);
    if(!n){release(p);return NULL;}
    if(!ue_valid_alignment(a))return NULL;
    size_t virtual_old=ue_vm_size(p),old=virtual_old?virtual_old:malloc_size(p);
    if(!virtual_old&&n<UE_VM_THRESHOLD&&align_of(a)==16){void*q=malloc_zone_realloc(g_zone,p,n);if(q)used((int64_t)malloc_size(q)-(int64_t)old);return q;}
    if((virtual_old?(n>=UE_VM_THRESHOLD):(n<UE_VM_THRESHOLD))&&old>=n&&!((uintptr_t)p&(align_of(a)-1)))return p;
    void*q=alloc(n,a);if(!q)return NULL;
    memcpy(q,p,old<n?old:n);release(p);return q;
}


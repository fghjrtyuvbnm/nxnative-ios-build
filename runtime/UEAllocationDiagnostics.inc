// Failure-only classification probes. They never replace the failed request.
#include <errno.h>
static void ue_allocation_failure(const char *operation,void *pointer,size_t size,uint32_t alignment,int native_error) {
    malloc_zone_t *owner=pointer?malloc_zone_from_ptr(pointer):NULL;
    size_t virtual_size=0;
#ifdef UE_LARGE_VM_V1
    virtual_size=ue_vm_size(pointer);
#endif
    size_t old=virtual_size?virtual_size:(owner?malloc_size(pointer):0);
    fprintf(stderr,"[allocdiag] op=%s request_bytes=%zu alignment=%u old_bytes=%zu owner_known=%d owner_is_unreal=%d native_errno=%d owner_is_vm=%d\n",operation,size,alignment,old,owner!=NULL||virtual_size!=0,owner==g_zone,native_error,virtual_size!=0);
    // Bound diagnostic work independently of the application request size.
    // Probe one at a time, release immediately, do not commit/touch the pages.
    if (!size || size>64*1024*1024){fprintf(stderr,"[allocdiag] probes_skipped=request_size\n");return;}
    size_t align=align_of(alignment);int own_error,default_error;
    errno=0;void *own=align==16?malloc_zone_malloc(g_zone,size):malloc_zone_memalign(g_zone,align,size);own_error=errno;
    int own_ok=own!=NULL;if(own)malloc_zone_free(g_zone,own);
    malloc_zone_t *fallback=malloc_default_zone();
    errno=0;void *other=align==16?malloc_zone_malloc(fallback,size):malloc_zone_memalign(fallback,align,size);default_error=errno;
    int default_ok=other!=NULL;if(other)malloc_zone_free(fallback,other);
    vm_address_t address=0;kern_return_t vm_result=vm_allocate(mach_task_self(),&address,(vm_size_t)size,VM_FLAGS_ANYWHERE);
    kern_return_t release_result=KERN_SUCCESS;
    if(vm_result==KERN_SUCCESS)release_result=vm_deallocate(mach_task_self(),address,(vm_size_t)size);
    fprintf(stderr,"[allocdiag] own_fresh_ok=%d own_errno=%d default_fresh_ok=%d default_errno=%d vm_allocate_result=%d vm_release_result=%d\n",own_ok,own_error,default_ok,default_error,vm_result,release_result);
}

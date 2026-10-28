#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <assert.h>
#include <stdlib.h>
#include <malloc/malloc.h>
#include <mach/mach.h>
#include "MemoryDiagnostics.h"
static malloc_zone_t *g_zone;
static size_t align_of(uint32_t a){return a>16?a:16;}
#include "UEAllocationDiagnostics.inc"
int main(void){
    dm_memory_note("allocation-observer-fixture");
    g_zone=malloc_create_zone(0,0);assert(g_zone);
    void *owned=malloc_zone_malloc(g_zone,1024);assert(owned);memset(owned,0x5a,1024);
    void *foreign=malloc(1024);assert(foreign);
    assert(malloc_zone_from_ptr(owned)==g_zone);
    ue_allocation_failure("owned-fixture",owned,6*1024*1024+123,1,ENOMEM);
    for(int i=0;i<1024;i++)assert(((unsigned char *)owned)[i]==0x5a);
    ue_allocation_failure("foreign-fixture",foreign,8*1024*1024+321,0,ENOMEM);
    ue_allocation_failure("bounded-fixture",NULL,65*1024*1024,0,ENOMEM);
    malloc_zone_free(g_zone,owned);free(foreign);malloc_destroy_zone(g_zone);
    puts("allocation diagnostic observation fixtures passed");return 0;
}

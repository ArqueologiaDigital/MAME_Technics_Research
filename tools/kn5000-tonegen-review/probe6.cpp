// Proves the missing bound in kn5000_state::build_pitch_constants: `ptr_a + 4` is validated,
// but the code reads u8(ptr_a + 4 + u8(ptr_c + key)) -- up to 255 bytes further on.
// Verbatim transcription of the loop body from kn5000.cpp (combined branch).
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <cstdlib>
#include <map>
#include <vector>
#include <algorithm>
using namespace std;
static uint8_t *rom;            // heap, so ASan can see the overflow
static uint32_t nbytes = 0x200000;
#define BIT(x,n) (((x)>>(n))&1)
int main(){
  rom = (uint8_t*)malloc(nbytes); memset(rom,0,nbytes);
  auto put32=[&](uint32_t a,uint32_t v){ rom[a]=v; rom[a+1]=v>>8; rom[a+2]=v>>16; rom[a+3]=v>>24; };
  auto put16=[&](uint32_t a,uint32_t v){ rom[a]=v; rom[a+1]=v>>8; };
  const uint32_t ROOT=0x30000;
  put32(ROOT+0x30,0x10000);                 // set_base = 0x40000
  put32(ROOT+0x24,0x10010); put32(ROOT+0x28,0x10010); put32(ROOT+0x2C,0x10010);
  put16(ROOT+0xEC,0x10);                    // stride 16 -> n_sets = 1
  rom[0x40000]=0x00;                        // flags: zstride 4, bit1 clear
  put32(0x40001,0x1CFFFB);                  // ptr_a = 0x1FFFFB  (ptr_a+4 == 0x1FFFFF, last valid byte)
  put32(0x40005,0x00000000);                // ptr_b = 0x30000
  put32(0x1FFFFB,0x00020000);               // ptr_c = 0x50000
  rom[0x50000]=0xFF;                        // zone index byte = 255

  auto u8 =[&](uint32_t a)->uint32_t{ return rom[a]; };
  auto u16=[&](uint32_t a){ return uint32_t(u8(a))|(uint32_t(u8(a+1))<<8); };
  auto u32=[&](uint32_t a){ return u16(a)|(u16(a+2)<<16); };
  auto rel=[&](uint32_t r){ return ROOT+r; };

  uint32_t set_base=rel(u32(ROOT+0x30)); uint32_t stride=u16(ROOT+0xEC);
  uint32_t limit=u32(ROOT+0x24); limit=min(limit,u32(ROOT+0x28)); limit=min(limit,u32(ROOT+0x2C));
  if(!stride||limit<=u32(ROOT+0x30)){puts("early return");return 0;}
  uint32_t n_sets=(limit-u32(ROOT+0x30))/stride;
  if(!n_sets||n_sets>4096){puts("early return n_sets");return 0;}
  printf("set_base=%08X stride=%u n_sets=%u  region=0x%X\n",set_base,stride,n_sets,nbytes);
  map<uint16_t,map<int32_t,uint32_t>> weights;
  for(uint32_t i=0;i<n_sets;i++){
    uint32_t d=set_base+stride*i;
    if(d+0x0E>=nbytes) return 0;
    uint8_t flags=u8(d); uint32_t zstride=BIT(flags,7)?6:4;
    uint32_t ptr_a=rel(u32(d+1)), ptr_b=rel(u32(d+5));
    if(ptr_a+4>=nbytes||ptr_b>=nbytes) return 0;
    uint32_t ptr_c=rel(u32(ptr_a));
    if(ptr_c+127>=nbytes) return 0;
    printf("set %u passed every check: ptr_a=%08X ptr_b=%08X ptr_c=%08X\n",i,ptr_a,ptr_b,ptr_c);
    int32_t coarse=BIT(flags,1)?0:int32_t(u16(d+0x0C))-((int32_t(u8(d+0x0B))<<8)+0x80);
    for(uint32_t key=0;key<128;key++){
      printf("  about to read rom[0x%X + 4 + rom[0x%X]] = rom[0x%X]  (region ends at 0x%X)\n",
             ptr_a,ptr_c+key,ptr_a+4+u8(ptr_c+key),nbytes);
      fflush(stdout);
      uint32_t rec=ptr_b+zstride*u8(ptr_a+4+u8(ptr_c+key));
      if(rec+zstride>nbytes) return 0;
      int32_t trim=0;
      weights[uint16_t(u16(rec))][coarse+trim]++;
    }
  }
  return 0;
}

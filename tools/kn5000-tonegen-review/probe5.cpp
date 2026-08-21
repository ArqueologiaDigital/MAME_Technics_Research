// Replica of kn5000_state::build_pitch_constants over the REAL table_data region,
// instrumented to report (a) whether it completes, (b) the highest byte address it
// touches, and (c) whether ptr_a+4+u8(ptr_c+key) ever exceeds the validated bound.
#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <vector>
#include <map>
#include <algorithm>
using namespace std;
static vector<uint8_t> rom;
static uint64_t maxtouch=0; static int oob=0; static uint64_t oobmax=0;
static uint32_t u8f(uint32_t a){ if(a>maxtouch)maxtouch=a; if(a>=rom.size()){oob++; if(a>oobmax)oobmax=a; return 0;} return rom[a]; }
int main(int argc,char**argv){
  // region = ROM_REGION16_LE(0x200000, "table_data"): ic3 into even words, ic1 into odd words
  rom.assign(0x200000,0);
  vector<uint8_t> e(0x100000), o(0x100000);
  FILE*f=fopen(argv[1],"rb"); fread(e.data(),1,0x100000,f); fclose(f);
  f=fopen(argv[2],"rb"); fread(o.data(),1,0x100000,f); fclose(f);
  for(uint32_t i=0;i<0x100000/2;i++){ rom[i*4+0]=e[i*2]; rom[i*4+1]=e[i*2+1]; rom[i*4+2]=o[i*2]; rom[i*4+3]=o[i*2+1]; }
  uint32_t bytes=rom.size();
  auto u16=[&](uint32_t a){return u8f(a)|(u8f(a+1)<<8);};
  auto u32=[&](uint32_t a){return u16(a)|(u16(a+2)<<16);};
  const uint32_t ROOT=0x30000; auto rel=[&](uint32_t r){return ROOT+r;};
  uint32_t set_base=rel(u32(ROOT+0x30)), stride=u16(ROOT+0xEC);
  uint32_t limit=u32(ROOT+0x24); limit=min(limit,u32(ROOT+0x28)); limit=min(limit,u32(ROOT+0x2C));
  printf("set_base=%08X stride=%u limit=%08X base_rel=%08X\n",set_base,stride,limit,u32(ROOT+0x30));
  if(!stride||limit<=u32(ROOT+0x30)){printf("EARLY RETURN (stride/limit)\n");return 0;}
  uint32_t n_sets=(limit-u32(ROOT+0x30))/stride;
  printf("n_sets=%u\n",n_sets);
  if(!n_sets||n_sets>4096){printf("EARLY RETURN (n_sets)\n");return 0;}
  map<uint16_t,map<int32_t,uint32_t>> weights;
  int near_end=0; uint32_t worst_slack=0xFFFFFFFF;
  for(uint32_t i=0;i<n_sets;i++){
    uint32_t d=set_base+stride*i;
    if(d+0x0E>=bytes){printf("EARLY RETURN at set %u (d bound)\n",i);break;}
    uint8_t flags=u8f(d); uint32_t zs=(flags&0x80)?6:4;
    uint32_t pa=rel(u32(d+1)), pb=rel(u32(d+5));
    if(pa+4>=bytes||pb>=bytes){printf("EARLY RETURN at set %u (ptr bound) pa=%08X pb=%08X\n",i,pa,pb);break;}
    uint32_t pc=rel(u32(pa));
    if(pc+127>=bytes){printf("EARLY RETURN at set %u (ptr_c bound) pc=%08X\n",i,pc);break;}
    int32_t coarse=(flags&2)?0:int32_t(u16(d+0x0C))-((int32_t(u8f(d+0x0B))<<8)+0x80);
    // slack: how close is pa+4+255 to the end?
    if(pa+4+255>=bytes) near_end++;
    if(bytes-(pa+4)<worst_slack) worst_slack=bytes-(pa+4);
    for(uint32_t key=0;key<128;key++){
      uint32_t idxaddr=pa+4+u8f(pc+key);
      uint32_t rec=pb+zs*u8f(idxaddr);
      if(rec+zs>bytes){printf("EARLY RETURN at set %u key %u (rec bound)\n",i,key);goto done;}
      int32_t trim=0; if(zs==6){trim=int32_t(u16(rec+4)); if(trim>=0x8000)trim-=0x10000;}
      weights[uint16_t(u16(rec))][coarse+trim]++;
    }
  }
done:
  printf("selectors=%zu  highest byte touched=0x%llX (region 0x%X)  OOB reads=%d (max 0x%llX)\n",
         weights.size(),(unsigned long long)maxtouch,bytes,oob,(unsigned long long)oobmax);
  printf("SETs whose ptr_a+4+255 would pass the end: %d ; smallest (bytes - (ptr_a+4)) slack = %u\n",near_end,worst_slack);
  vector<pair<uint16_t,int32_t>> table;
  for(auto&s:weights){auto b=max_element(s.second.begin(),s.second.end(),[](auto&a,auto&b){return a.second<b.second;});
    table.push_back({s.first,b->first});}
  long long sum=0; for(auto&t:table) sum+=int16_t(t.second);
  printf("pitch constants=%zu sum=%lld\n",table.size(),sum);
  // does any C fall outside int16?
  int trunc=0; for(auto&t:table) if(t.second<-32768||t.second>32767) trunc++;
  printf("C values that do not fit int16 (silently truncated by int16_t cast): %d\n",trunc);
  return 0;
}

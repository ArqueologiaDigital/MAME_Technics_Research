// Concrete numbers for the two arithmetic findings, over the real ic307 dump.
#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <cmath>
#include <vector>
#include <algorithm>
using namespace std;
static vector<uint8_t> rom;
static int16_t ws(uint32_t o){ if(o+1>=rom.size())return 0; return int16_t(uint16_t(rom[o])|(uint16_t(rom[o+1])<<8)); }
int main(int argc,char**argv){
  rom.assign(0x400000,0); FILE*f=fopen(argv[1],"rb"); fread(rom.data(),1,0x400000,f); fclose(f);
  const uint32_t PAGE=0x100000;
  // page 0 of ic307 (region offset 0xC00000, file offset 0)
  for (uint32_t pgoff : {0u,0x100000u,0x200000u,0x300000u}) {
    const uint8_t*pg=&rom[pgoff];
    auto u16at=[pg](uint32_t o){return uint32_t(pg[o])|(uint32_t(pg[o+1])<<8);};
    uint32_t n=u16at(0)/4; vector<uint32_t> wave(n);
    for(uint32_t i=0;i<n;i++) wave[i]=u16at(i*4+2);
    vector<uint32_t> s(wave); sort(s.begin(),s.end()); s.erase(unique(s.begin(),s.end()),s.end());
    // find the single worst adjacent pair in the page
    int64_t worst=0; uint32_t wi=0,wk=0;
    for(uint32_t i=0;i<n;i++){
      auto it=upper_bound(s.begin(),s.end(),wave[i]);
      uint32_t eo=(it==s.end())?PAGE:(*it*16), off=wave[i]*16;
      uint32_t len=(eo>off)?((eo-off)/2):0; if(!len)continue;
      uint32_t st=pgoff+off;
      for(uint32_t k=0;k+1<len;k++){ int64_t d=int64_t(ws(st+(k+1)*2))-ws(st+k*2);
        if(llabs(d)>llabs(worst)){worst=d;wi=i;wk=k;} }
    }
    auto it=upper_bound(s.begin(),s.end(),wave[wi]);
    uint32_t eo=(it==s.end())?PAGE:(*it*16), off=wave[wi]*16;
    uint32_t st=pgoff+off;
    int32_t a=ws(st+wk*2), b=ws(st+(wk+1)*2);
    printf("page @%06X: worst adjacent pair chunk %u sample %u : a=%d b=%d (b-a=%d)\n",
           0xC00000+pgoff,wi,wk,a,b,b-a);
    for (uint32_t frac : {16384u,32768u,40000u,49152u,65535u}) {
      int64_t exact = int64_t(a) + ((int64_t(b-a)*int64_t(frac))>>16);
      int32_t prod = int32_t(uint32_t(int32_t(b-a))*uint32_t(frac));   // wrapped product
      int32_t buggy = a + (prod>>16);
      printf("   frac=%5u : correct=%7lld   as written (int32)=%7d %s\n",
             frac,(long long)exact,buggy, (exact!=buggy)?"  <-- WRONG (signed overflow)":"");
    }
  }
  return 0;
}

// Peak/RMS of the real IC307 recordings, to compare against the placeholder's SINE_PEAK=11585.
#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <cmath>
#include <vector>
#include <algorithm>
using namespace std;
int main(int argc,char**argv){
  vector<uint8_t> rom(0x400000); FILE*f=fopen(argv[1],"rb"); fread(rom.data(),1,0x400000,f); fclose(f);
  auto ws=[&](uint32_t o){return int16_t(uint16_t(rom[o])|(uint16_t(rom[o+1])<<8));};
  const uint32_t PAGE=0x100000; int nch=0; double sumrms=0; int peak=0; int above20k=0;
  for(uint32_t pgoff:{0u,0x100000u,0x200000u,0x300000u}){
    auto u16at=[&](uint32_t o){return uint32_t(rom[pgoff+o])|(uint32_t(rom[pgoff+o+1])<<8);};
    uint32_t n=u16at(0)/4; vector<uint32_t> wave(n);
    for(uint32_t i=0;i<n;i++)wave[i]=u16at(i*4+2);
    vector<uint32_t> s(wave); sort(s.begin(),s.end()); s.erase(unique(s.begin(),s.end()),s.end());
    for(uint32_t i=0;i<n;i++){
      auto it=upper_bound(s.begin(),s.end(),wave[i]);
      uint32_t eo=(it==s.end())?PAGE:(*it*16),off=wave[i]*16;
      uint32_t len=(eo>off)?((eo-off)/2):0; if(!len)continue;
      double e=0; int pk=0;
      for(uint32_t k=0;k<len;k++){int v=ws(pgoff+off+k*2); e+=double(v)*v; pk=max(pk,abs(v));}
      sumrms+=sqrt(e/len); peak=max(peak,pk); if(pk>20000)above20k++; nch++;
    }
  }
  printf("IC307: %d chunks, absolute peak sample=%d, mean per-chunk RMS=%.0f, chunks peaking above 20000: %d (%.0f%%)\n",
         nch,peak,sumrms/nch,above20k,100.0*above20k/nch);
  printf("placeholder sine: peak 11585, RMS %.0f\n",11585/sqrt(2.0));
  return 0;
}

#include <cstdio>
#include <cstdint>
#include <cstring>
#include <cstdlib>
#include <cmath>
#include <vector>
#include <algorithm>
using namespace std;
static vector<uint8_t> rom;
static int16_t ws(uint32_t o){ if(o+1>=rom.size())return 0; return int16_t(uint16_t(rom[o])|(uint16_t(rom[o+1])<<8)); }
static uint32_t detect_period(uint32_t bs,uint32_t samples,const char**why){
  *why="ac"; if(samples<32){*why="short";return samples<<16;}
  uint32_t off=samples/3,w=min<uint32_t>(samples-off,4096);
  if(w<64){off=0;w=min<uint32_t>(samples,4096);} const uint32_t ML=4;
  uint32_t maxlag=min<uint32_t>(w/2,2048); if(maxlag<=ML){*why="maxlag";return samples<<16;}
  vector<double> x; x.reserve(w);
  for(uint32_t i=0;i<w;i++){uint32_t bp=bs+(off+i)*2; if(bp+1>=rom.size())break; x.push_back(double(ws(bp)));}
  uint32_t n=x.size(); if(n<=ML*2+4){*why="tiny";return samples<<16;}
  double m=0; for(double v:x)m+=v; m/=n; double e=0; for(double&v:x){v-=m;e+=v*v;}
  if(e<1.0){*why="flat";return samples<<16;}
  uint32_t hi=min<uint32_t>(maxlag,n-1); vector<double> sq(n+1,0.0);
  for(uint32_t i=0;i<n;i++)sq[i+1]=sq[i]+x[i]*x[i];
  vector<double> r(hi+1,-2.0);
  for(uint32_t lag=ML;lag<=hi;lag++){double c=0;for(uint32_t i=0;i+lag<n;i++)c+=x[i]*x[i+lag];
    double den=sqrt(sq[n-lag]*(sq[n]-sq[lag])); r[lag]=(den>1.0)?(c/den):-2.0;}
  uint32_t cr=0; for(uint32_t l=ML;l<=hi;l++)if(r[l]<0.0){cr=l;break;}
  if(!cr){*why="nocross";return (samples<=2048)?(samples<<16):0;}
  uint32_t best=0;double pk=-2.0; for(uint32_t l=cr;l<=hi;l++)if(r[l]>pk){pk=r[l];best=l;}
  if(!best||pk<0.2){*why="nopeak";return samples<<16;}
  double fr=0; if(best>ML&&best+1<=hi){double y0=r[best-1],y1=r[best],y2=r[best+1],d=y0-2*y1+y2;
    if(d<-1e-12||d>1e-12)fr=clamp(0.5*(y0-y2)/d,-0.5,0.5);}
  return uint32_t(max(1.0,double(best)+fr)*65536.0+0.5);
}
int main(int argc,char**argv){
  rom.assign(0x400000,0); FILE*f=fopen(argv[1],"rb"); fread(rom.data(),1,0x400000,f); fclose(f);
  const uint32_t PAGE=0x100000; int tot=0,fb=0,wrap_pl=0,wrap_any=0,zeroper=0;
  double lowest=1e18;
  for(uint32_t pgoff:{0u,0x100000u,0x200000u,0x300000u}){
    const uint8_t*pg=&rom[pgoff];
    auto u16at=[pg](uint32_t o){return uint32_t(pg[o])|(uint32_t(pg[o+1])<<8);};
    uint32_t n=u16at(0)/4; vector<uint32_t> wave(n);
    for(uint32_t i=0;i<n;i++)wave[i]=u16at(i*4+2);
    vector<uint32_t> s(wave); sort(s.begin(),s.end()); s.erase(unique(s.begin(),s.end()),s.end());
    for(uint32_t i=0;i<n;i++){
      auto it=upper_bound(s.begin(),s.end(),wave[i]);
      uint32_t eo=(it==s.end())?PAGE:(*it*16),off=wave[i]*16;
      uint32_t len=(eo>off)?((eo-off)/2):0; tot++;
      const char*why; uint32_t per=detect_period(pgoff+off,len,&why);
      if(strcmp(why,"ac"))fb++;
      if(!per){zeroper++;continue;}
      // lowest frequency at which llround(f*per/48000) exceeds UINT32_MAX
      double fw = 4294967295.5*48000.0/double(per);
      if(fw<lowest)lowest=fw;
      if(fw<=23999.0) wrap_any++;
      if(fw<=4186.0) wrap_pl++;   // C8, top of an 88-key keyboard
    }
  }
  printf("chunks=%d  period fallbacks=%d (%.1f%%)  per==0 (-> sine)=%d\n",tot,fb,100.0*fb/tot,zeroper);
  printf("chunks whose pcm_inc overflows uint32 somewhere below Nyquist-clamp 23999 Hz: %d\n",wrap_any);
  printf("chunks whose pcm_inc overflows uint32 at or below C8 (4186 Hz)             : %d\n",wrap_pl);
  printf("lowest frequency at which any chunk's pcm_inc overflows: %.1f Hz\n",lowest);
  return 0;
}

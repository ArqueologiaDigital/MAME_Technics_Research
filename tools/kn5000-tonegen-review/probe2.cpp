// Standalone replica of kn5000_tonegen_device::parse_page_directories / detect_period /
// voice_sample arithmetic, run over the REAL ic307 dump plus MAME-style fill_random for the
// three NO_DUMP sockets. Answers: does any page validate on random data? how big are the
// accepted chunks (does pcm_samples<<16 overflow uint32)? can (b-a)*frac overflow int32?
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <cstdlib>
#include <cmath>
#include <vector>
#include <algorithm>
using namespace std;

static const uint32_t PAGE_SIZE = 0x100000;
static const int NUM_BANKS = 4, PAGES_PER_BANK = 4;
static vector<uint8_t> rom;

struct page_dir { uint32_t base=0, count=0; vector<uint32_t> pcm_start, pcm_samples, period_q16; };
static page_dir dirs[NUM_BANKS][PAGES_PER_BANK];

static int16_t wsample(uint32_t o){ if (o+1>=rom.size()) return 0; return int16_t(uint16_t(rom[o])|(uint16_t(rom[o+1])<<8)); }

static uint32_t detect_period(uint32_t byte_start, uint32_t samples, const char **why)
{
    *why="ac";
    if (samples < 32) { *why="short"; return samples<<16; }
    uint32_t off = samples/3; uint32_t w = min<uint32_t>(samples-off, 4096);
    if (w<64){ off=0; w=min<uint32_t>(samples,4096); }
    const uint32_t MINLAG=4; uint32_t maxlag=min<uint32_t>(w/2,2048);
    if (maxlag<=MINLAG){ *why="maxlag"; return samples<<16; }
    vector<double> x; x.reserve(w);
    for (uint32_t i=0;i<w;i++){ uint32_t bp=byte_start+(off+i)*2; if (bp+1>=rom.size()) break; x.push_back(double(wsample(bp))); }
    uint32_t n=uint32_t(x.size());
    if (n<=MINLAG*2+4){ *why="tiny"; return samples<<16; }
    double mean=0; for(double v:x) mean+=v; mean/=double(n);
    double energy=0; for(double &v:x){ v-=mean; energy+=v*v; }
    if (energy<1.0){ *why="flat"; return samples<<16; }
    uint32_t hi=min<uint32_t>(maxlag,n-1);
    vector<double> sq(n+1,0.0); for(uint32_t i=0;i<n;i++) sq[i+1]=sq[i]+x[i]*x[i];
    vector<double> r(hi+1,-2.0);
    for(uint32_t lag=MINLAG;lag<=hi;lag++){ double c=0; for(uint32_t i=0;i+lag<n;i++) c+=x[i]*x[i+lag];
        double e0=sq[n-lag], e1=sq[n]-sq[lag], den=sqrt(e0*e1); r[lag]=(den>1.0)?(c/den):-2.0; }
    uint32_t cross=0; for(uint32_t lag=MINLAG;lag<=hi;lag++) if(r[lag]<0.0){cross=lag;break;}
    if(!cross){ *why="nocross"; return (samples<=2048)?(samples<<16):0; }
    uint32_t best=0; double peak=-2.0;
    for(uint32_t lag=cross;lag<=hi;lag++) if(r[lag]>peak){peak=r[lag];best=lag;}
    if(!best||peak<0.2){ *why="nopeak"; return samples<<16; }
    double frac=0;
    if(best>MINLAG&&best+1<=hi){ double y0=r[best-1],y1=r[best],y2=r[best+1],den=y0-2*y1+y2;
        if(den<-1e-12||den>1e-12) frac=clamp(0.5*(y0-y2)/den,-0.5,0.5); }
    return uint32_t(max(1.0,double(best)+frac)*65536.0+0.5);
}

int main(int argc,char**argv)
{
    static const uint32_t BANK_BASE[4]={0x000000,0xC00000,0x400000,0x800000};
    rom.assign(0x1000000,0);
    // MAME fill_random over the three NO_DUMP sockets: *base++ = machine().rand()
    uint32_t seed=0x9d14abd7;
    auto mrand=[&](){ seed = 1664525u*seed + 1013904223u; return (seed>>16)|(seed<<16); };
    for (uint32_t o : {0x000000u,0x400000u,0x800000u})
        for (uint32_t i=0;i<0x400000;i++) rom[o+i]=uint8_t(mrand());
    FILE*f=fopen(argv[1],"rb"); if(!f){perror("ic307");return 1;} fread(&rom[0xC00000],1,0x400000,f); fclose(f);

    for(int b=0;b<4;b++) for(int p=0;p<4;p++){
        page_dir &d=dirs[b][p]; d=page_dir(); d.base=BANK_BASE[b]+uint32_t(p)*PAGE_SIZE;
        const uint8_t*pg=&rom[d.base];
        auto u16at=[pg](uint32_t o)->uint32_t{ return uint32_t(pg[o])|(uint32_t(pg[o+1])<<8); };
        uint32_t head=u16at(0);
        if(!head||(head&3)){ printf("bank %d page %d @%06X REJECT head=%04X\n",b,p,d.base,head); continue; }
        uint32_t n=head/4;
        if(uint64_t(n)*4>PAGE_SIZE-4){ printf("bank %d page %d REJECT n\n",b,p); continue; }
        vector<uint32_t> param(n),wave(n); bool ok=true; uint32_t failat=0; const char*fr="";
        for(uint32_t i=0;i<n&&ok;i++){
            param[i]=u16at(i*4); wave[i]=u16at(i*4+2);
            if(i&&param[i]<param[i-1]){ok=false;fr="mono";}
            else if(param[i]<n*4){ok=false;fr="indir";}
            else if(uint64_t(wave[i])*16>=PAGE_SIZE){ok=false;fr="waveoff";}
            else if(u16at(param[i])!=wave[i]){ok=false;fr="backref";}
            if(!ok) failat=i;
        }
        if(!ok){ printf("bank %d page %d @%06X REJECT head=%04X n=%u at entry %u (%s)\n",b,p,d.base,head,n,failat,fr); continue; }
        vector<uint32_t> sorted(wave); sort(sorted.begin(),sorted.end());
        sorted.erase(unique(sorted.begin(),sorted.end()),sorted.end());
        d.count=n; d.pcm_start.resize(n); d.pcm_samples.resize(n); d.period_q16.assign(n,0);
        for(uint32_t i=0;i<n;i++){
            auto it=upper_bound(sorted.begin(),sorted.end(),wave[i]);
            uint32_t end_off=(it==sorted.end())?PAGE_SIZE:(*it*16); uint32_t off=wave[i]*16;
            d.pcm_start[i]=d.base+off; d.pcm_samples[i]=(end_off>off)?((end_off-off)/2):0;
        }
        // statistics
        uint32_t big=0,zero=0,maxs=0,ov=0,dcstuck=0; int64_t maxdiff=0; uint32_t ovchunk=0;
        for(uint32_t i=0;i<n;i++){
            uint32_t s=d.pcm_samples[i]; if(!s){zero++;continue;} maxs=max(maxs,s);
            if(s>=65536){ big++; if(((uint64_t(s)<<16)&0xFFFFFFFFull)==0) dcstuck++; }
            // adjacent-sample delta, to test (b-a)*frac int32 overflow
            uint32_t lim=min<uint32_t>(s-1,65535);
            for(uint32_t k=0;k<lim;k++){
                int32_t a=wsample(d.pcm_start[i]+k*2), bb=wsample(d.pcm_start[i]+(k+1)*2);
                int64_t diff=int64_t(bb)-a; if(llabs(diff)>llabs(maxdiff)) maxdiff=diff;
                if(llabs(diff)*65535>2147483647LL){ ov++; if(!ovchunk)ovchunk=i; }
            }
        }
        printf("bank %d page %d @%06X ACCEPT n=%u  zero-len=%u  >=65536 samples=%u (of which end==0: %u)  max samples=%u  max adjacent delta=%lld  int32-overflow pairs=%u (first chunk %u)\n",
               b,p,d.base,n,zero,big,dcstuck,maxs,(long long)maxdiff,ov,ovchunk);
        // period-detection census over EVERY chunk
        uint32_t bad=0, worst=0, worstn=0; int fb[6]={0,0,0,0,0,0};
        for(uint32_t i=0;i<n;i++){
            const char*why; uint32_t per=detect_period(d.pcm_start[i],d.pcm_samples[i],&why);
            if(strcmp(why,"ac")){ bad++;
                if(!strcmp(why,"short"))fb[0]++; else if(!strcmp(why,"maxlag"))fb[1]++;
                else if(!strcmp(why,"tiny"))fb[2]++; else if(!strcmp(why,"flat"))fb[3]++;
                else if(!strcmp(why,"nocross"))fb[4]++; else if(!strcmp(why,"nopeak"))fb[5]++; }
            if(per>worst){worst=per;worstn=i;}
        }
        printf("   period fallbacks %u/%u : short=%d maxlag=%d tiny=%d flat=%d nocross=%d nopeak=%d ; max per=%u (=%.1f samples) chunk %u len %u\n",
               bad,n,fb[0],fb[1],fb[2],fb[3],fb[4],fb[5],worst,worst/65536.0,worstn,d.pcm_samples[worstn]);
    }
    return 0;
}

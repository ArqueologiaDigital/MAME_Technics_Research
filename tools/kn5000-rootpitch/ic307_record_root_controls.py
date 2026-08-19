#!/usr/bin/env python3
"""Controls for recprobe.py: is the record's apparent 'signal' about m just positional
autocorrelation of the directory?  A feature that is NOT IN THE RECORD AT ALL
(the chunk's own index) must not out-signal the record if the record carries the root."""
import bisect, collections, json, os, random
ROM = os.path.expanduser('~/compartilhado/kn7000-emulator/roms/kn5000/kn5000_waveform_rom.ic307')
GT  = os.path.expanduser('~/compartilhado/kn7000_mame/tools/kn5000-rootpitch/gt.json')
d=open(ROM,'rb').read(); PAGE=0x100000; rng=random.Random(17)
def page(pg):
    base=pg*PAGE; u16=lambda o: d[base+o]|(d[base+o+1]<<8)
    n=u16(0)//4; param=[u16(i*4) for i in range(n)]; wave=[u16(i*4+2) for i in range(n)]
    psrt=sorted(set(param)); recs=[]
    for i in range(n):
        j=bisect.bisect_right(psrt,param[i]); pend=psrt[j] if j<len(psrt) else min(wave)*16
        raw=d[base+param[i]:base+pend]
        recs.append((raw,[(raw[t],raw[t+1]) for t in range(2,len(raw)-1,2)]))
    return recs, wave
P={p:page(p) for p in range(4)}
gt={tuple(int(x) for x in k.split(',')):v for k,v in json.load(open(GT)).items()}
M={k:v['m'] for k,v in gt.items() if abs(v['res'])<=64}
def purity(f,t):
    g=collections.defaultdict(collections.Counter)
    for k in t: g[f[k]][t[k]]+=1
    return sum(c.most_common(1)[0][1] for c in g.values())/len(t)
def gated(name,fn,draws=400):
    f={k:fn(k) for k in M}; obs=purity(f,M); ks=list(M); nn=[]
    for _ in range(draws):
        vs=[M[k] for k in ks]; rng.shuffle(vs); nn.append(purity(f,dict(zip(ks,vs))))
    mu=sum(nn)/len(nn); sd=(sum((x-mu)**2 for x in nn)/len(nn))**.5 or 1e-9
    print("   %-34s purity %5.1f%%  null %5.1f%%  z=%+6.2f  distinct=%d"%(name,100*obs,100*mu,(obs-mu)/sd,len(set(f.values()))))
print("== CONTROLS: features that are NOT in the parameter record at all ==")
gated("chunk index >>4  (NOT in record)", lambda k: k[1]>>4)
gated("chunk index >>3  (NOT in record)", lambda k: k[1]>>3)
gated("chunk index >>2  (NOT in record)", lambda k: k[1]>>2)
gated("wave_offset >>10 (NOT in record)", lambda k: P[k[0]][1][k[1]]>>10)
print("\n== the sharpest test: byte-identical payloads -> same m? ==")
g=collections.defaultdict(list)
for k in M: g[(k[0],bytes(P[k[0]][0][k[1]][0][2:]))].append(M[k])
multi={kk:v for kk,v in g.items() if len(v)>1}
npair=sum(len(v)*(len(v)-1)//2 for v in multi.values())
agree=sum(sum(1 for i in range(len(v)) for j in range(i+1,len(v)) if v[i]==v[j]) for v in multi.values())
same=sum(1 for v in multi.values() if len(set(v))==1)
print("   %d payload byte-strings shared by >1 chunk (%d chunks, %d pairs)"%(len(multi),sum(len(v) for v in multi.values()),npair))
print("   groups all sharing one m: %d/%d ; PAIRWISE agreement %d/%d = %.1f%%"%(same,len(multi),agree,npair,100*agree/max(npair,1)))
ms=list(M.values()); nn=[]
for _ in range(400):
    rng.shuffle(ms); mm=dict(zip(list(M),ms)); a=t=0
    for kk,v in multi.items():
        ks=[k for k in M if (k[0],bytes(P[k[0]][0][k[1]][0][2:]))==kk]
        for i in range(len(ks)):
            for j in range(i+1,len(ks)): t+=1; a+= (mm[ks[i]]==mm[ks[j]])
    nn.append(a/max(t,1))
print("   NULL (m shuffled): %.1f%%"%(100*sum(nn)/len(nn)))
print("\n== converse test: within one PHYSICAL recording (shared wave_offset), does the key byte vary while m is fixed? ==")
nv=nm=0; tot=0
for pg in range(4):
    recs,wave=P[pg]
    grp=collections.defaultdict(list)
    for i,w in enumerate(wave):
        if (pg,i) in M: grp[w].append(i)
    for w,ix in grp.items():
        if len(ix)<2: continue
        tot+=1
        keys={max([v for v,f in recs[i][1] if f==0],default=None) for i in ix}
        mm={M[(pg,i)] for i in ix}
        if len(keys)>1: nv+=1
        if len(mm)>1: nm+=1
print("   %d shared-recording groups: key byte VARIES in %d (%.0f%%), m varies in %d (%.0f%%)"%(tot,nv,100*nv/tot,nm,100*nm/tot))

import numpy as np, math, pickle, re
from collections import Counter
S="/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/d0e1b1c2-9dd7-40da-b88c-9bcc60bcc85a/scratchpad/"
G=pickle.load(open(S+"G.pkl","rb"))
HXX="/home/fsanches/compartilhado/kn7000_mame/src/mame/matsushita/kn5000_pitch_trim.hxx"
rows=re.findall(r'\{\s*0x([0-9A-Fa-f]{4}),\s*(-?\d+),\s*(\d)\s*\}',open(HXX).read())
allC=[(int(x,16),int(y),int(z)) for x,y,z in rows]
ic307=[c for s,c,a in allC if 4<=(s>>12)<=7]
print("C over ALL 465 IC307 selectors: min %d max %d  span %d units = %.2f octaves"
      %(min(ic307),max(ic307),max(ic307)-min(ic307),(max(ic307)-min(ic307))/3072))
q=np.percentile(ic307,[0,1,5,50,95,99,100])
print("  percentiles 0/1/5/50/95/99/100:", [int(v) for v in q])
print("  nonzero only:",end=" ")
nz=[c for c in ic307 if c!=0]
print("n=%d min %d max %d"%(len(nz),min(nz),max(nz)))
print("  C==0 count:",sum(1 for c in ic307 if c==0))

K=6.2
CMIN,CMAX=min(ic307),max(ic307)
for lab,(lo,hi) in (("full observed range",(CMIN,CMAX)),
                    ("1-99 percentile",(q[1],q[5])),
                    ("[-4096,+1024)",(-4096,1024)),
                    ("[-4096,0]",(-4096,0))):
    uniq=0; two=0; hit=0; n=0
    for r in G:
        L=K+3072*math.log2(r['P'])
        cand=[m for m in range(-20,20) if lo-1e-9 <= L+3072*m <= hi+1e-9]
        if not cand: continue
        n+=1
        if len(cand)==1: uniq+=1
        if len(cand)==2: two+=1
        if r['m'] in cand: hit+=1
    print("  bound %-22s n=%3d  unique %5.1f%%  two-way %5.1f%%  true-m in set %5.1f%%"
          %(lab,n,100*uniq/n,100*two/n,100*hit/n))

# how good is the pitch class?
dev=np.array([r['dev'] for r in G])
print("\npitch-class accuracy on %d clean chunks: median |err| %.1f cents, 90th pct %.1f cents"
      %(len(dev),np.median(abs(dev))/2.56,np.percentile(abs(dev),90)/2.56))

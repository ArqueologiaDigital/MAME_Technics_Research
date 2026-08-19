import numpy as np, re, math
from collections import Counter, defaultdict
S="/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/d0e1b1c2-9dd7-40da-b88c-9bcc60bcc85a/scratchpad/"
a=np.load(S+"per.npy")
per={(int(r[0]),int(r[1])):(r[2],r[3]) for r in a}
HXX="/home/fsanches/compartilhado/kn7000_mame/src/mame/matsushita/kn5000_pitch_trim.hxx"
rows=re.findall(r'\{\s*0x([0-9A-Fa-f]{4}),\s*(-?\d+),\s*(\d)\s*\}',open(HXX).read())
C={int(x,16):(int(y),int(z)) for x,y,z in rows}

recs=[]
for sel,(c,amb) in sorted(C.items()):
    cls=sel>>12
    if cls<4 or cls>7: continue
    page=cls&3; ent=sel&0xFFF
    if (page,ent) not in per: continue
    P,q=per[(page,ent)]
    if P<=0: continue
    NAT=-3072*math.log2(P)
    recs.append((sel,cls,page,ent,c,amb,P,q,NAT+c))
print("selectors on IC307 with a period and a C:",len(recs))
print("of which single-valued C:",sum(1 for r in recs if r[5]==0))

R=np.array([r[8] for r in recs])
# find best global constant K modulo 3072
ph=np.mod(R,3072.0)
# circular mean
ang=ph/3072*2*np.pi
K=(math.atan2(np.sin(ang).mean(),np.cos(ang).mean())/(2*np.pi))*3072 % 3072
dev=(R-K+1536)%3072-1536
print("K (ROOT mod 3072) = %.1f units = %.3f semitones"%(K,K/256))
for tol,name in ((64.0,"+-25 cents"),(128.0,"+-50 cents"),(256.0,"+-100 cents")):
    print("  within %s: %d/%d = %.1f%%"%(name,(abs(dev)<tol).sum(),len(dev),100*(abs(dev)<tol).mean()))
print("  median |dev| = %.2f units = %.1f cents"%(np.median(abs(dev)),np.median(abs(dev))/2.56))

m=np.round((R-K)/3072.0).astype(int)
print("octave residue m histogram:",sorted(Counter(m.tolist()).items()))
np.save(S+"analysed.npy",np.array([[r[0],r[1],r[2],r[3],r[4],r[5],r[6],r[7],r[8]] for r in recs]))

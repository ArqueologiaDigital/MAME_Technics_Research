import math, pickle, collections
import numpy as np
S="/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/d0e1b1c2-9dd7-40da-b88c-9bcc60bcc85a/scratchpad/"
G=pickle.load(open(S+"G.pkl","rb"))
K=6.2
def pred(P,W):
    b=K+3072.0*math.log2(P)
    return b+3072.0*math.floor((W+3072-b)/3072.0)
print("exact-C recovery (|err|<64 units = 25 cents), C = base + 3072*m, m fixed by a window:")
for lab,sub in [("ALL clean chunks",G)]+[("page %d"%p,[r for r in G if r['page']==p]) for p in range(4)]:
    best=max(((W,sum(1 for r in sub if abs(pred(r['P'],W)-r['C'])<64)) for W in range(-6144,3072,8)),key=lambda t:t[1])
    nz=[r for r in sub if r['C']!=0]
    onz=sum(1 for r in nz if abs(pred(r['P'],best[0])-r['C'])<64)
    print("  %-16s n=%3d  best window [%5d,%5d)  ALL %5.1f%%   C!=0 (n=%3d) %5.1f%%"
          %(lab,len(sub),best[0],best[0]+3072,100*best[1]/len(sub),len(nz),100*onz/max(len(nz),1)))
# residual after the mod-3072 step, as an error in the DECODED NOTE
err=np.array([r['dev'] for r in G])/256.0
print("\nnote error from the pitch-class law alone (octave aside): median %.3f st, 90th pct %.3f st"
      %(np.median(abs(err)),np.percentile(abs(err),90)))
print("  |err| < 0.5 st (note rounds correctly): %.1f%%"%(100*(abs(err)<0.5).mean()))

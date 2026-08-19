import numpy as np, math, pickle
from collections import Counter, defaultdict
S="/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/d0e1b1c2-9dd7-40da-b88c-9bcc60bcc85a/scratchpad/"
rec=pickle.load(open(S+"rec.pkl","rb"))
K=6.2
good=[r for r in rec if r['amb']==0 and r['q']<0.30]
seen={}
for r in good: seen.setdefault((r['page'],r['ent']),r)
G=sorted(seen.values(), key=lambda r:(r['page'],r['ent']))
for r in G:
    r['m']=int(round((r['ROOT']-K)/3072.0))
    r['dev']=(r['ROOT']-K)-3072.0*r['m']
G=[r for r in G if abs(r['dev'])<64]
print("clean chunks:",len(G))
m=np.array([r['m'] for r in G]); P=np.array([r['P'] for r in G])
print("m hist:",sorted(Counter(m.tolist()).items()))
print("log2P range %.2f .. %.2f"%(np.log2(P).min(),np.log2(P).max()))
# 1) is m a function of floor(log2 P)?
fl=np.floor(np.log2(P)).astype(int)
print("\n--- m vs floor(log2 P) ---")
tab=defaultdict(Counter)
for a,b in zip(fl,m): tab[a][b]+=1
for k in sorted(tab): print("  floor(log2P)=%2d -> %s"%(k,dict(tab[k])))
# purity of m given floor(log2P)
pur=sum(max(c.values()) for c in tab.values())/len(m)
print("  purity m|floor(log2P) = %.3f"%pur)
# 2) m vs -floor(log2P): does m + floor(log2 P) collapse?
z=m+fl
print("  m+floor(log2P) hist:",sorted(Counter(z.tolist()).items()))
# 3) m vs chunk length
print("\n--- m vs chunk length (log2 ns) ---")
ns=np.array([r['ns'] for r in G]); ln=np.floor(np.log2(np.maximum(ns,1))).astype(int)
tab=defaultdict(Counter)
for a,b in zip(ln,m): tab[a][b]+=1
pur=sum(max(c.values()) for c in tab.values())/len(m)
print("  purity m|floor(log2 ns) = %.3f  (%d bins)"%(pur,len(tab)))
# 4) m vs page
tab=defaultdict(Counter)
for r in G: tab[r['page']][r['m']]+=1
print("\n--- m vs page ---")
for k in sorted(tab): print("  page %d -> %s"%(k,dict(sorted(tab[k].items()))))
pickle.dump(G,open(S+"G.pkl","wb"))

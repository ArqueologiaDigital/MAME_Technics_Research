import numpy as np, math, pickle, random
from collections import Counter, defaultdict
S="/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/d0e1b1c2-9dd7-40da-b88c-9bcc60bcc85a/scratchpad/"
G=pickle.load(open(S+"G.pkl","rb"))
print("clean chunks:",len(G))
def pairs(b):
    body=b[2:]
    return [(body[i],body[i+1]) for i in range(0,len(body)-1,2)]
for r in G:
    p=pairs(r['recb']); r['pairs']=p
    r['npairs']=len(p)
    r['lastflag']=p[-1][1] if p else None
    r['maxR']=max((f>>6) for _,f in p) if p else None
    r['lastR']=(p[-1][1]>>6) if p else None
    r['anyR']=max([(f>>6) for _,f in p]+[0]) if p else 0

def purity(feat,lab):
    t=defaultdict(Counter)
    for f,l in zip(feat,lab): t[f][l]+=1
    return sum(max(c.values()) for c in t.values())/len(lab), len(t)

m=[r['m'] for r in G]
print("\nbaseline: modal m purity = %.3f  (%d classes)"%(max(Counter(m).values())/len(m),len(set(m))))

for name,f in (("lastflag>>6",[r['lastR'] for r in G]),
               ("max flag>>6",[r['maxR'] for r in G]),
               ("lastflag",[r['lastflag'] for r in G]),
               ("npairs",[r['npairs'] for r in G]),
               ("page",[r['page'] for r in G]),
               ("floor(log2 P)",[int(math.floor(math.log2(r['P']))) for r in G]),
               ("(page,lastflag>>6)",[(r['page'],r['lastR']) for r in G])):
    p,k=purity(f,m); print("  %-22s purity=%.3f  bins=%d"%(name,p,k))

# 2-octave-per-R hypothesis: m + 2*R
for nm,R in (("last",[r['lastR'] for r in G]),("max",[r['maxR'] for r in G])):
    for k in (1,2,3):
        z=[a+k*(b if b is not None else 0) for a,b in zip(m,R)]
        print("  m + %d*%sR : %d distinct  %s"%(k,nm,len(set(z)),sorted(Counter(z).items())))

# byte-identical records (excluding the wave_start back-reference) -> same m?
grp=defaultdict(list)
for r in G: grp[r['recb'][2:]].append(r)
multi=[v for v in grp.values() if len(v)>1]
agree=sum(1 for v in multi if len(set(x['m'] for x in v))==1)
tot_pairs=sum(len(v)*(len(v)-1)//2 for v in multi)
same=sum(sum(1 for i in range(len(v)) for j in range(i+1,len(v)) if v[i]['m']==v[j]['m']) for v in multi)
print("\nbyte-identical record bodies: %d groups with >1 member, %d agree on m entirely"%(len(multi),agree))
print("  pairwise agreement %d/%d = %.1f%%"%(same,tot_pairs,100*same/max(tot_pairs,1)))
# null: random pairs from the same page
rnd=[];
for _ in range(20000):
    a,b=random.sample(G,2)
    if a['page']==b['page']: rnd.append(a['m']==b['m'])
print("  null (random same-page pair) = %.1f%%"%(100*np.mean(rnd)))

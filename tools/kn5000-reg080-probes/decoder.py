import numpy as np, math, pickle, re
from collections import Counter, defaultdict
S="/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/d0e1b1c2-9dd7-40da-b88c-9bcc60bcc85a/scratchpad/"
G=pickle.load(open(S+"G.pkl","rb"))
K=6.2
# per-class C distribution over IC307
HXX="/home/fsanches/compartilhado/kn7000_mame/src/mame/matsushita/kn5000_pitch_trim.hxx"
rows=re.findall(r'\{\s*0x([0-9A-Fa-f]{4}),\s*(-?\d+),\s*(\d)\s*\}',open(HXX).read())
byclass=defaultdict(list)
for x,y,z in rows:
    s=int(x,16); c=int(y)
    if 4<=(s>>12)<=7: byclass[s>>12].append(c)
print("per-class C on IC307 (all selectors):")
for cl in sorted(byclass):
    v=np.array(byclass[cl])
    print("  class %d n=%3d  min %6d  med %6d  max %6d  #C==0 %3d"%(cl,len(v),v.min(),int(np.median(v)),v.max(),(v==0).sum()))

def Cpcm(P,off):
    """C predicted from the period, with an octave offset choice."""
    return K + 3072.0*math.log2(P) + 3072.0*off   # = ROOT_lattice - NAT with ROOT=K+3072*off... careful

# C_true = ROOT - NAT = (K + 3072*m) + 3072*log2(P).  So base = K + 3072*log2(P), C = base + 3072*m
rules={}
for r in G:
    r['base']=K+3072.0*math.log2(r['P'])
def evaluate(name,pick):
    ok=0; n=0
    for r in G:
        m=pick(r)
        if m is None: continue
        n+=1
        if abs(r['base']+3072.0*m - r['C'])<64: ok+=1
    print("  %-40s %4d/%4d = %5.1f%%"%(name,ok,n,100*ok/max(n,1)))

print("\nEXACT-C recovery from the PCM, by octave-selection rule (tolerance 25 cents):")
evaluate("oracle octave (upper bound)", lambda r: r['m'])
evaluate("C nearest 0",                 lambda r: int(round(-r['base']/3072.0)))
evaluate("C in [-3072,0)",              lambda r: int(math.floor(-r['base']/3072.0)))
med={cl:np.median(byclass[cl]) for cl in byclass}
evaluate("C nearest class median",      lambda r: int(round((med[4+r['page']]-r['base'])/3072.0)))
allmed=np.median([c for cl in byclass for c in byclass[cl]])
evaluate("C nearest global median (%d)"%allmed, lambda r: int(round((allmed-r['base'])/3072.0)))

# how much of the note does the pitch class alone give?
print("\nwhat the pitch class alone delivers:")
print("  C mod 3072 correct within 25 cents : %.1f%% of 326 quality chunks (303/326)"%(100*303/326))
print("  => decoded MIDI note is exact MODULO 12 for those chunks")

# distribution of true m per page again, and whether m is monotone in entry within a page
print("\nis m monotone in directory order (multisample groups are consecutive)?")
for p in range(4):
    v=[(r['ent'],r['m']) for r in G if r['page']==p]
    v.sort()
    if len(v)<5: continue
    d=[v[i+1][1]-v[i][1] for i in range(len(v)-1)]
    print("  page %d: n=%3d  steps: %s"%(p,len(v),sorted(Counter(d).items())))

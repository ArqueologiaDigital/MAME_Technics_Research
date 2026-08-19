#!/usr/bin/env python3
"""READ-ONLY re-test of the brief's third option: does IC307's own parameter record
carry the per-chunk ROOT (equivalently the 3-bit octave m) for the chunks it describes?

Ground truth m comes from the COMMITTED tools/kn5000-rootpitch/gt.json (not recomputed,
so nothing is written).  Records are parsed straight from the IC307 dump.
Every purity figure is gated against a permutation null (m shuffled, features fixed).
"""
import bisect, collections, json, os, random

ROM = os.path.expanduser('~/compartilhado/kn7000-emulator/roms/kn5000/kn5000_waveform_rom.ic307')
GT  = os.path.expanduser('~/compartilhado/kn7000_mame/tools/kn5000-rootpitch/gt.json')
d = open(ROM, 'rb').read(); PAGE = 0x100000
rng = random.Random(17)

def page(pg):
    base = pg * PAGE
    u16 = lambda o: d[base+o] | (d[base+o+1] << 8)
    n = u16(0)//4
    param=[u16(i*4) for i in range(n)]; wave=[u16(i*4+2) for i in range(n)]
    psrt=sorted(set(param))
    recs=[]
    for i in range(n):
        j=bisect.bisect_right(psrt,param[i]); pend=psrt[j] if j<len(psrt) else min(wave)*16
        raw=d[base+param[i]:base+pend]
        recs.append((raw,[(raw[t],raw[t+1]) for t in range(2,len(raw)-1,2)]))
    return recs
P = {p: page(p) for p in range(4)}

gt = {tuple(int(x) for x in k.split(',')): v for k,v in json.load(open(GT)).items()}
tr = {k:v for k,v in gt.items() if abs(v['res']) <= 64}
M  = {k:v['m'] for k,v in tr.items()}
print("trusted chunks (single firmware C + good period, |res|<=25 cents): %d" % len(M))

def rec(k): return P[k[0]][k[1]]

def purity(f, target):
    g=collections.defaultdict(collections.Counter)
    for k in target: g[f[k]][target[k]] += 1
    return sum(c.most_common(1)[0][1] for c in g.values())/len(target)

def gated(name, fn, draws=400):
    f={k:fn(k) for k in M}
    obs=purity(f,M); ks=list(M); nn=[]
    for _ in range(draws):
        vs=[M[k] for k in ks]; rng.shuffle(vs); nn.append(purity(f,dict(zip(ks,vs))))
    mu=sum(nn)/len(nn); sd=(sum((x-mu)**2 for x in nn)/len(nn))**.5 or 1e-9
    print("   %-30s purity %5.1f%%  null %5.1f%% +-%4.1f  z=%+6.2f  distinct=%d%s"
          % (name, 100*obs, 100*mu, 100*sd, (obs-mu)/sd, len(set(f.values())),
             "   <== SIGNAL" if (obs-mu)/sd > 4 else ""))

mc=collections.Counter(M.values())
print("   NULL (always guess modal m=%d): %.1f%%\n" % (mc.most_common(1)[0][0], 100*mc.most_common(1)[0][1]/len(M)))

splits = lambda k: [v for v,f in rec(k)[1] if f == 0]
gated("record bytes (whole payload)", lambda k: bytes(rec(k)[0][2:]))
gated("has any flag-00 key byte",     lambda k: bool(splits(k)))
gated("top flag-00 key byte",         lambda k: max(splits(k), default=-1))
gated("top flag-00 key byte >>3",     lambda k: max(splits(k), default=-1) >> 3)
gated("1.5*(top-40) -> MIDI, //12",   lambda k: int(1.5*(max(splits(k), default=-1)-40))//12)
gated("n flag-00 key bytes",          lambda k: len(splits(k)))
gated("first payload value",          lambda k: rec(k)[1][0][0] if rec(k)[1] else -1)
gated("first payload flag",           lambda k: rec(k)[1][0][1] if rec(k)[1] else -1)
gated("payload length (bytes)",       lambda k: len(rec(k)[0])-2)

# how many trusted chunks even HAVE a key byte
have=sum(1 for k in M if splits(k))
print("\n   trusted chunks with at least one flag-00 key byte: %d/%d = %.1f%%" % (have,len(M),100*have/len(M)))
print("   trusted chunks with EMPTY payload:                  %d/%d" %
      (sum(1 for k in M if not rec(k)[1]), len(M)))

# Can the key byte give the octave for chunks that SHARE one recording (the fold groups)?
print("\n== fold groups: chunks sharing one wave_offset, do their key bytes step by an octave? ==")
for pg in (0,1,3):
    base=pg*PAGE; u16=lambda o: d[base+o]|(d[base+o+1]<<8)
    n=u16(0)//4; wave=[u16(i*4+2) for i in range(n)]
    grp=collections.defaultdict(list)
    for i,w in enumerate(wave): grp[w].append(i)
    shown=0
    for w,ix in sorted(grp.items()):
        if len(ix)<3: continue
        tops=[max([v for v,f in P[pg][i][1] if f==0], default=None) for i in ix]
        ms=[M.get((pg,i)) for i in ix]
        print("   page %d wave %04X chunks %s  top-key %s   m %s" %
              (pg,w,[hex(i) for i in ix],[('%02x'%t if t is not None else '--') for t in tops],ms))
        shown+=1
        if shown>=4: break

import sys, shutil
sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab")
import numpy as np
from kn7000live import geom as G, recog as R
from kn7000live.simulate import parse_sim_spec
from kn7000live.app import Engine
from kn7000live.store import DumpStore
from kn7000dump.oracle import Oracle
truth = Oracle().page(0x48019000)
shutil.rmtree("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/stC", ignore_errors=True)
src = parse_sim_spec("sim:48019000,px=12,blur=1.1,shake=0")
store = DumpStore("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/stC")
src.read()
rng = np.random.default_rng(4242)
q = G.Quad(np.asarray(src.true_quad, float) + rng.normal(0, 1.0, (4, 2)))
e = Engine(store, G.Registration(q), R.GlyphBank(), seed_base=0x48019000)
for i in range(40):
    e.process(src.read())
d, m = store.page_state(0x48019000)
bad = [i for i in range(256) if m[i] and d[i] != truth[i]]
print("locked=%d wrong=%d conflicts=%d" % (sum(m), len(bad), len(store.conflicts)))
for i in bad:
    print("  %08X  read %02X  truth %02X   (row %d, col %d)" % (0x48019000+i, d[i], truth[i], i//16, i%16))
print()
print("template confusions that matter:")
T = e.bank.templates; S = T @ T.T; np.fill_diagonal(S, -1)
pairs = sorted(((float(S[a,b]), "%X%X"%(a,b)) for a in range(16) for b in range(a+1,16)), reverse=True)
for v, p in pairs[:6]:
    print("   '%s' vs '%s' : %.3f" % (p[0], p[1], v))
print()
print("samples per class:", dict(zip("0123456789ABCDEF", e.bank.n.tolist())))

"""The page-switch requirement: change page, keep everything already read."""
import sys, shutil
sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab")
import numpy as np
from kn7000live import geom as G, recog as R
from kn7000live.simulate import parse_sim_spec
from kn7000live.app import Engine
from kn7000live.store import DumpStore
from kn7000dump.oracle import Oracle
D = "/home/fsanches/.claude/jobs/d0e1b1c2/tmp/pgsw"
shutil.rmtree(D, ignore_errors=True)
src = parse_sim_spec("sim:48019000,px=12,blur=1.1,shake=0,pages=3,page_every=70")
store = DumpStore(D)
src.read()
e = Engine(store, G.Registration(G.Quad(np.asarray(src.true_quad, float).copy())),
           R.GlyphBank(), seed_base=0x48019000)
seen = []
for i in range(210):
    e.process(src.read())
    if i in (69, 139, 209):
        seen.append({("%08X" % p): store.n_locked(p) for p in sorted(store.data)})
store.close()
for k, s in enumerate(seen):
    print("after page %d: %s" % (k + 1, s))
orc = Oracle()
bad = 0
for p in sorted(store.data):
    t = orc.page(p); d, m = store.page_state(p)
    bad += sum(1 for i in range(256) if m[i] and d[i] != t[i])
print("wrong bytes across all pages: %d" % bad)
s2 = DumpStore(D)
print("reload matches:", all(bytes(s2.data[p]) == bytes(store.data[p]) for p in store.data))

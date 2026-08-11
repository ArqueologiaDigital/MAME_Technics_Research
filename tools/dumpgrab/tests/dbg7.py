import sys, shutil
sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab")
import numpy as np
from kn7000live import geom as G, recog as R
from kn7000live.simulate import parse_sim_spec
from kn7000live.app import Engine
from kn7000live.store import DumpStore
shutil.rmtree("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/st8", ignore_errors=True)
src = parse_sim_spec("sim:48019000,px=12,blur=1.1,shake=0.0")
f = src.read()
store = DumpStore("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/st8")
e = Engine(store, G.Registration(G.Quad(np.asarray(src.true_quad, float).copy())),
           R.GlyphBank(), seed_base=0x48019000)
e.prealign = False
G.track_homography = lambda *a, **k: 0.0
for i in range(80):
    rd = e.process(src.read())
print("bank n:", e.bank.n.tolist(), " sep %.3f" % e.bank.separation())
print("rows: (address read, min margin, accepted, reason)")
for r in rd.rows:
    print("   %2d %s  m=%.4f  %-5s %s" % (r.row,
          ("%08X" % r.address) if r.address is not None else "--------",
          r.addr_margin, r.accepted, r.reason))
print("template pairwise NCC matrix max off-diag per class:")
T = e.bank.templates
S = T @ T.T
np.fill_diagonal(S, -1)
for i in range(16):
    j = int(S[i].argmax())
    print("   '%X' closest to '%X' at %.3f" % (i, j, S[i, j]))

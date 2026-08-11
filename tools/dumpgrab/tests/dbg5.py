import sys, shutil
sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab")
import numpy as np
from kn7000live import geom as G, recog as R
from kn7000live.simulate import parse_sim_spec
from kn7000live.app import Engine
from kn7000live.store import DumpStore
shutil.rmtree("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/st6", ignore_errors=True)
src = parse_sim_spec("sim:48019000,px=12,blur=1.1,shake=0.0")
f = src.read()
store = DumpStore("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/st6")
e = Engine(store, G.Registration(G.Quad(np.asarray(src.true_quad, float).copy())),
           R.GlyphBank(), seed_base=0x48019000)
e.prealign = False
real = G.track_homography
def spy(reg, cells, resid, w, gain=0.6, **k):
    before = reg.quad.corners.copy()
    ok = w > 0
    r = real(reg, cells, resid, w, gain=gain, **k)
    step = np.abs(reg.quad.corners - before).max()
    print("   track: n=%4d usable=%4d medresid=(%.3f,%.3f) step=%.2fpx ret=%s"
          % (len(cells), int(ok.sum()), np.median(resid[ok, 0]) if ok.any() else 0,
             np.median(resid[ok, 1]) if ok.any() else 0, step, ("%.3f"%r) if r else r))
    return r
G.track_homography = spy
for i in range(8):
    rd = e.process(src.read())
    print("f%d rows_ok=%d dev=%.2f" % (i, rd.n_rows_ok,
          np.abs(e.reg.quad.corners - src.true_quad).max()))

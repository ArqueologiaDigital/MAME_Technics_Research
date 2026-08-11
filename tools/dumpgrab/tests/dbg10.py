import sys, shutil
sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab")
import numpy as np
from kn7000live import geom as G, recog as R
from kn7000live.simulate import parse_sim_spec
from kn7000live.app import Engine
from kn7000live.store import DumpStore
shutil.rmtree("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/stD", ignore_errors=True)
src = parse_sim_spec("sim:48019000,px=12,blur=1.1,shake=1.0")
store = DumpStore("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/stD")
f0 = src.read()
e = Engine(store, G.Registration(G.Quad(np.asarray(src.true_quad, float).copy())),
           R.GlyphBank(), seed_base=0x48019000)
for i in range(26):
    fr = src.read()
    tq = np.asarray(src.true_quad, float)
    before = np.abs(e.reg.quad.corners - tq).max()
    rd = e.process(fr)
    after = np.abs(e.reg.quad.corners - tq).max()
    print("f%02d ready=%-5s rows=%2d dev %5.2f->%5.2f  settle=%d  mot=%s  %s"
          % (i, e.bank.ready, rd.n_rows_ok, before, after, e._settle,
             ("%.3f"%rd.motion) if rd.motion is not None else "  -  ", e.stats.last_reason))
print("locked", sum(store.page_state(0x48019000)[1]))

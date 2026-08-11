import sys, shutil
sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab")
import numpy as np
from kn7000live import geom as G, recog as R
from kn7000live.simulate import parse_sim_spec
from kn7000live.app import Engine
from kn7000live.store import DumpStore
shutil.rmtree("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/stT", ignore_errors=True)
src = parse_sim_spec("sim:48019000,px=12,blur=1.1,shake=1.0,pages=3,page_every=60")
store = DumpStore("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/stT")
src.read()
e = Engine(store, G.Registration(G.Quad(np.asarray(src.true_quad, float).copy())),
           R.GlyphBank(), seed_base=0x48019000)
for i in range(60):
    rd = e.process(src.read())
    if i < 6 or i % 10 == 0:
        print("f%03d ready=%-5s rows=%2d settle=%d right=%.3f  %s" % (
            i, e.bank.ready, rd.n_rows_ok, e._settle,
            rd.metrics.get("right_margin", -1), e.stats.last_reason))
print("locked:", {("%08X"%p): store.n_locked(p) for p in sorted(store.data)})

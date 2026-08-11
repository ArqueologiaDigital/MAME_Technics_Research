
import sys, shutil
sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab")
import numpy as np
from kn7000live import geom as G, recog as R
from kn7000live.simulate import parse_sim_spec
from kn7000live.app import Engine
from kn7000live.store import DumpStore
shutil.rmtree("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/stW", ignore_errors=True)
src = parse_sim_spec("sim:48019000,px=12,blur=1.1,shake=1.0")
store = DumpStore("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/stW")
src.read()
rng = np.random.default_rng(4242)
q = G.Quad(np.asarray(src.true_quad, float) + rng.normal(0, 1.5, (4, 2)))
e = Engine(store, G.Registration(q), R.GlyphBank(), seed_base=0x48019000)
for i in range(45):
    rd = e.process(src.read())
    if i > 12:
        print("f%02d rows=%2d ladder=%-5s right=%.4f settle=%d vals=%3d %s" % (
            i, rd.n_rows_ok, rd.ladder_ok, rd.metrics.get("right_margin", -1),
            e._settle, len(rd.values), e.stats.last_reason))
print("locked", sum(store.page_state(0x48019000)[1]))


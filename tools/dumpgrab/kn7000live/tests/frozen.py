import sys, shutil
sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab")
import numpy as np
from kn7000live import geom as G, recog as R
from kn7000live.simulate import parse_sim_spec
from kn7000live.app import Engine
from kn7000live.store import DumpStore
from kn7000dump.oracle import Oracle
truth = Oracle().page(0x48019000)
rare = [i for i in range(256) if truth[i] != 0x77]
for shake in (0.0, 1.0, 2.5):
    shutil.rmtree("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/stZ", ignore_errors=True)
    src = parse_sim_spec("sim:48019000,px=12,blur=1.1,shake=%g" % shake)
    store = DumpStore("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/stZ")
    frozen = src.read()
    rng = np.random.default_rng(4242)
    q = G.Quad(np.asarray(src.true_quad, float) + rng.normal(0, 1.5, (4, 2)))
    e = Engine(store, G.Registration(q), R.GlyphBank(), seed_base=0x48019000)
    for i in range(14):                       # operator has the picture frozen
        e.process(frozen, vote=False)
    rows_at_unfreeze = e.last.n_rows_ok if e.last else 0
    for i in range(45):                       # resumed, camera live
        e.process(src.read())
    d, m = store.page_state(0x48019000)
    bad = [i for i in range(256) if m[i] and d[i] != truth[i]]
    print("shake %.1f: at unfreeze %d/16 rows -> locked %3d, WRONG %d, non-77 %d/75"
          % (shake, rows_at_unfreeze, int(sum(m)), len(bad), sum(1 for i in rare if m[i])))

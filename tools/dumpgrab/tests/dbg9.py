import sys, shutil
sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab")
import numpy as np
from kn7000live import geom as G, recog as R
from kn7000live.simulate import parse_sim_spec
from kn7000live.app import Engine
from kn7000live.store import DumpStore

def run(err, shake, drift, frames=40):
    shutil.rmtree("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/stA", ignore_errors=True)
    src = parse_sim_spec("sim:48019000,px=12,blur=1.1,shake=%g" % shake)
    store = DumpStore("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/stA")
    f0 = src.read()
    rng = np.random.default_rng(4242)
    q = G.Quad(np.asarray(src.true_quad, float) + rng.normal(0, err, (4, 2)))
    e = Engine(store, G.Registration(q), R.GlyphBank(), seed_base=0x48019000)
    ok = []
    for i in range(frames):
        fr = src.read()
        if drift:                     # simulate the operator's hand walking
            src.tilt = min(0.25, i * drift)
        rd = e.process(fr)
        ok.append(rd.n_rows_ok)
    return np.mean(ok[-10:]), sum(store.page_state(0x48019000)[1])

print("%-10s %-8s %-8s %6s %7s" % ("corner err", "shake", "drift", "rows", "locked"))
for err in (0.0, 1.0, 2.0, 3.0, 4.0, 6.0):
    r, l = run(err, 0.0, 0.0)
    print("%-10.1f %-8s %-8s %6.1f %7d" % (err, "0", "0", r, l))
for shake in (1.0, 2.0, 3.0):
    r, l = run(1.0, shake, 0.0)
    print("%-10.1f %-8.1f %-8s %6.1f %7d" % (1.0, shake, "0", r, l))
r, l = run(1.0, 1.0, 0.004)
print("%-10.1f %-8.1f %-8s %6.1f %7d" % (1.0, 1.0, "tilt", r, l))

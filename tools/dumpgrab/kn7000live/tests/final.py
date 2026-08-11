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

def run(err=1.5, shake=0.0, px=12.0, blur=1.1, tilt=0.0, noise=3.0, frames=60):
    shutil.rmtree("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/stF", ignore_errors=True)
    src = parse_sim_spec("sim:48019000,px=%g,blur=%g,shake=%g,tilt=%g,noise=%g" % (px, blur, shake, tilt, noise))
    store = DumpStore("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/stF")
    src.read()
    rng = np.random.default_rng(4242)
    q = G.Quad(np.asarray(src.true_quad, float) + rng.normal(0, err, (4, 2)))
    e = Engine(store, G.Registration(q), R.GlyphBank(), seed_base=0x48019000)
    for i in range(frames):
        e.process(src.read())
    d, m = store.page_state(0x48019000)
    bad = [i for i in range(256) if m[i] and d[i] != truth[i]]
    return int(sum(m)), len(bad), sum(1 for i in rare if m[i]), len(store.conflicts)

print("%-32s %7s %6s %8s %5s" % ("condition", "locked", "WRONG", "non-77", "conf"))
for tag, kw in [("still", {}),
                ("hand shake 1.0", dict(shake=1.0)),
                ("hand shake 2.5", dict(shake=2.5)),
                ("shake 1.0 + tilt", dict(shake=1.0, tilt=0.12)),
                ("shake 1.0, px=9", dict(shake=1.0, px=9.0)),
                ("shake 1.0, blur 2.0", dict(shake=1.0, blur=2.0)),
                ("shake 1.0, noise 10", dict(shake=1.0, noise=10.0))]:
    n, b, nr, cf = run(**kw)
    print("%-32s %7d %6d %8s %5d" % (tag, n, b, "%d/75" % nr, cf))

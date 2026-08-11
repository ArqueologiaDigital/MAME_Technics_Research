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

def run(jit, shake, frames=45):
    shutil.rmtree("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/stJ", ignore_errors=True)
    src = parse_sim_spec("sim:48019000,px=12,blur=1.1,shake=%g" % shake)
    store = DumpStore("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/stJ")
    src.read()
    rng = np.random.default_rng(4242)
    q = G.Quad(np.asarray(src.true_quad, float) + rng.normal(0, 1.0, (4, 2)))
    e = Engine(store, G.Registration(q), R.GlyphBank(), seed_base=0x48019000)
    e.reader.jitter = jit
    for i in range(frames):
        e.process(src.read())
    d, m = store.page_state(0x48019000)
    bad = [i for i in range(256) if m[i] and d[i] != truth[i]]
    return int(sum(m)), len(bad), sum(1 for i in rare if m[i])

print("%-26s %-7s %7s %6s %8s" % ("jitter (cells)", "shake", "locked", "WRONG", "non-77"))
for name, jit in [("none", None),
                  ("+-0.05,0.03", [(0.05,0.03),(-0.05,-0.03)]),
                  ("+-0.07,0.04", [(0.07,0.04),(-0.07,-0.04)]),
                  ("+-0.09,0.05", [(0.09,0.05),(-0.09,-0.05)]),
                  ("+-0.12,0.08", [(0.12,0.08),(-0.12,-0.08)])]:
    for shake in (0.0, 1.0):
        n, b, nr = run(jit, shake)
        print("%-26s %-7.1f %7d %6d %8s" % (name, shake, n, b, "%d/75"%nr))

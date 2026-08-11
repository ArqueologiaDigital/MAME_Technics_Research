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

def run(err=1.0, shake=0.0, px=12.0, blur=1.1, tilt=0.0, frames=40, noise=3.0):
    shutil.rmtree("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/stB", ignore_errors=True)
    src = parse_sim_spec("sim:48019000,px=%g,blur=%g,shake=%g,tilt=%g,noise=%g" % (px, blur, shake, tilt, noise))
    store = DumpStore("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/stB")
    src.read()
    rng = np.random.default_rng(4242)
    q = G.Quad(np.asarray(src.true_quad, float) + rng.normal(0, err, (4, 2)))
    e = Engine(store, G.Registration(q), R.GlyphBank(), seed_base=0x48019000)
    ok = []
    for i in range(frames):
        ok.append(e.process(src.read()).n_rows_ok)
    d, m = store.page_state(0x48019000)
    nl = int(sum(m))
    bad = [i for i in range(256) if m[i] and d[i] != truth[i]]
    nr = sum(1 for i in rare if m[i])
    return np.mean(ok[-8:]), nl, len(bad), nr, len(store.conflicts)

print("%-34s %5s %7s %6s %9s %5s" % ("condition", "rows", "locked", "WRONG", "non-77", "conf"))
for tag, kw in [
    ("still, well placed",        dict(err=1.0)),
    ("hand shake 1.0",            dict(err=1.0, shake=1.0)),
    ("hand shake 2.5",            dict(err=1.0, shake=2.5)),
    ("hand shake 5.0",            dict(err=1.0, shake=5.0)),
    ("shake 2.5 + 12deg tilt",    dict(err=1.0, shake=2.5, tilt=0.12)),
    ("shake 2.5, px=9 (further)", dict(err=1.0, shake=2.5, px=9.0)),
    ("shake 2.5, px=7 (further)", dict(err=1.0, shake=2.5, px=7.0)),
    ("shake 2.5, blur 2.0",       dict(err=1.0, shake=2.5, blur=2.0)),
    ("shake 2.5, blur 3.0",       dict(err=1.0, shake=2.5, blur=3.0)),
    ("shake 2.5, noise 10",       dict(err=1.0, shake=2.5, noise=10.0)),
]:
    r, nl, bad, nr, cf = run(**kw)
    print("%-34s %5.1f %7d %6d %9s %5d" % (tag, r, nl, bad, "%d/75"%nr, cf))

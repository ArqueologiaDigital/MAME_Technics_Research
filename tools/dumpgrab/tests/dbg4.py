import sys, shutil
sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab")
import numpy as np
from kn7000live import geom as G, recog as R
from kn7000live.simulate import parse_sim_spec
from kn7000live.app import Engine
from kn7000live.store import DumpStore

def run(tag, err, shake, track_on, frames=20):
    shutil.rmtree("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/st5", ignore_errors=True)
    src = parse_sim_spec("sim:48019000,px=12,blur=1.1,shake=%g" % shake)
    f = src.read()
    store = DumpStore("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/st5")
    rng = np.random.default_rng(4242)
    q = G.Quad(np.asarray(src.true_quad, float) + rng.normal(0, err, (4, 2)))
    e = Engine(store, G.Registration(q), R.GlyphBank(), seed_base=0x48019000)
    if not track_on:
        e.prealign = False
        G_track = G.track_homography
    
    hist = []
    for i in range(frames):
        fr = src.read()
        rd = e.process(fr)
        hist.append(rd.n_rows_ok)
    if not track_on:
        G.track_homography = G_track
    dev = np.abs(e.reg.quad.corners - src.true_quad).max()
    print("%-28s rows_ok %s  final|dev|=%.1fpx  locked=%d" % (tag, hist, dev,
          sum(store.page_state(0x48019000)[1])))

run("true quad, no shake, notrack", 0.0, 0.0, False)
run("true quad, no shake, track",   0.0, 0.0, True)
run("6px err,  no shake, track",    6.0, 0.0, True)
run("6px err,  shake1.5, track",    6.0, 1.5, True)

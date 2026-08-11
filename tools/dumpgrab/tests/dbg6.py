import sys, shutil, time
sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab")
import numpy as np
from kn7000live import geom as G, recog as R
from kn7000live.simulate import parse_sim_spec
from kn7000live.app import Engine
from kn7000live.store import DumpStore

def objective(e, ink, origin):
    rd = e.reader.read(e.reg, ink, wanted={}, train=False, origin=origin)
    return rd.n_rows_ok / 16.0 + 0.5 * float(np.median(rd.cell_margin)), rd

def deform(q0, dx, dy, s, sx, k):
    c = q0.corners.copy()
    ctr = c.mean(0)
    c = ctr + (c - ctr) * np.array([s * sx, s])
    # keystone: top edge scaled about the centre in x
    c[0, 0] = ctr[0] + (c[0, 0] - ctr[0]) * (1 + k)
    c[1, 0] = ctr[0] + (c[1, 0] - ctr[0]) * (1 + k)
    c[2, 0] = ctr[0] + (c[2, 0] - ctr[0]) * (1 - k)
    c[3, 0] = ctr[0] + (c[3, 0] - ctr[0]) * (1 - k)
    c = c + np.array([dx, dy])
    return G.Quad(c)

def search(e, ink, origin, cw, ch):
    best_q = G.Quad(e.reg.quad.corners.copy())
    e.reg = G.Registration(best_q, ncols=e.reg.ncols)
    best, _ = objective(e, ink, origin)
    p = [0.0, 0.0, 1.0, 1.0, 0.0]
    steps = [0.35 * cw, 0.35 * ch, 0.010, 0.010, 0.010]
    for it in range(3):
        improved = False
        for i in range(5):
            for sgn in (+1, -1):
                q = list(p); q[i] += sgn * steps[i]
                cand = deform(best_q, q[0], q[1], q[2], q[3], q[4])
                e.reg = G.Registration(cand, ncols=e.reg.ncols)
                sc, _ = objective(e, ink, origin)
                if sc > best + 1e-6:
                    best, p, improved = sc, q, True
        if not improved:
            steps = [s * 0.5 for s in steps]
    e.reg = G.Registration(deform(best_q, *p), ncols=e.reg.ncols)
    return best

def run(tag, err, shake, frames=20):
    shutil.rmtree("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/st7", ignore_errors=True)
    src = parse_sim_spec("sim:48019000,px=12,blur=1.1,shake=%g" % shake)
    f = src.read()
    store = DumpStore("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/st7")
    rng = np.random.default_rng(4242)
    q = G.Quad(np.asarray(src.true_quad, float) + rng.normal(0, err, (4, 2)))
    e = Engine(store, G.Registration(q), R.GlyphBank(), seed_base=0x48019000)
    e.prealign = False
    G.track_homography = lambda *a, **k: 0.0
    hist = []; t0 = time.time()
    for i in range(frames):
        fr = src.read()
        ink, origin = e._ink(fr)
        if e.bank.ready:
            cw, ch = e.reg.quad.cell_pitch()
            search(e, ink, origin, cw, ch)
        rd = e.process(fr)
        hist.append(rd.n_rows_ok)
    dev = np.abs(e.reg.quad.corners - src.true_quad).max()
    print("%-24s rows_ok %s dev=%.1fpx locked=%d  %.0fms/f" % (
        tag, hist, dev, sum(store.page_state(0x48019000)[1]), 1000*(time.time()-t0)/frames))

run("true quad, no shake", 0.0, 0.0)
run("6px err,  no shake", 6.0, 0.0)
run("6px err,  shake 1.5", 6.0, 1.5)
run("3px err,  shake 3.0", 3.0, 3.0)

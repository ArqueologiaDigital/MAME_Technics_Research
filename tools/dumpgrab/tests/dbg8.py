import sys, shutil, itertools
sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab")
import numpy as np
from kn7000live import geom as G, recog as R
from kn7000live.simulate import parse_sim_spec
from kn7000live.app import Engine
from kn7000live.store import DumpStore
G.track_homography = lambda *a, **k: 0.0

src = parse_sim_spec("sim:48019000,px=12,blur=1.1,shake=0.0")
frames = [src.read() for _ in range(40)]
print("%-14s %-9s %5s %6s %7s %7s" % ("aperture", "patch", "rows", "sep", "margin", "locked"))
for ox, oy in [(0.20,0.10),(0.0,0.0),(0.10,0.0),(0.0,0.10),(0.30,0.20),(0.10,0.05)]:
    for gh, gw in [(18,12),(24,12)]:
        R.OVER_X, R.OVER_Y = ox, oy
        shutil.rmtree("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/st9", ignore_errors=True)
        store = DumpStore("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/st9")
        e = Engine(store, G.Registration(G.Quad(np.asarray(src.true_quad, float).copy())),
                   R.GlyphBank(gh, gw), seed_base=0x48019000)
        e.prealign = False
        rows = []
        for f in frames:
            rd = e.process(f)
            rows.append(rd.n_rows_ok)
        m = np.mean([r.addr_margin for r in rd.rows]) if rd.rows else 0
        print("%-14s %-9s %5.1f %6.3f %7.4f %7d" % ("ox=%.2f oy=%.2f"%(ox,oy), "%dx%d"%(gh,gw),
              np.mean(rows[-10:]), e.bank.separation(), m, sum(store.page_state(0x48019000)[1])))

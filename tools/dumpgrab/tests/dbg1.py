import sys, time
sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab")
import numpy as np
from kn7000live import geom as G, recog as R
from kn7000live.simulate import parse_sim_spec
from kn7000live.app import Engine
from kn7000live.store import DumpStore

src = parse_sim_spec("sim:48019000,px=12,blur=1.1,shake=0.0")
f = src.read()
print("frame", f.shape, "true quad:\n", np.round(src.true_quad, 1))
seed = G.auto_seed(f)
print("auto_seed quad:\n", np.round(seed.corners, 1))
print("bright bbox:", G.largest_bright_bbox(G.to_gray(f)))

import shutil; shutil.rmtree("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/st2", ignore_errors=True)
store = DumpStore("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/st2")
for tag, quad in (("auto", seed), ("TRUE", G.Quad(src.true_quad.copy()))):
    e = Engine(store, G.Registration(G.Quad(quad.corners.copy())), R.GlyphBank(), seed_base=0x48019000)
    ink, origin = e._ink(f)
    ok, why = e.reader.bootstrap(e.reg, ink, 0x48019000, origin)
    print("%-5s bootstrap: %s  (%s)   ink shape %s origin %s" % (tag, ok, why, ink.shape, origin))

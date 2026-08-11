import sys, shutil, time
sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab")
import numpy as np
from kn7000live import geom as G, recog as R
from kn7000live.app import Engine
from kn7000live.store import DumpStore
from kn7000live.simulate import parse_sim_spec

rng = np.random.default_rng(1)
# what the camera actually sees for the first few seconds: a room, no screen
room = np.clip(rng.normal(70, 25, (720, 1280, 3)), 0, 255).astype(np.uint8)
room[300:500, 200:600] = np.clip(rng.normal(140, 30, (200, 400, 3)), 0, 255)

src = parse_sim_spec("sim:48019000,px=12,blur=1.1,shake=0")
good = src.read()

for tag, frame in (("no screen in view", room), ("screen, quad wrong", good)):
    shutil.rmtree("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/stCB", ignore_errors=True)
    store = DumpStore("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/stCB")
    e = Engine(store, G.Registration(G.auto_seed(room)), R.GlyphBank(), seed_base=0x48019000)
    ts = []
    for i in range(5):
        t = time.time(); e.process(frame); ts.append(time.time() - t)
    print("%-20s  %s ms   (%s)" % (tag, " ".join("%.0f" % (1000*x) for x in ts),
                                   e.stats.last_reason[:46]))

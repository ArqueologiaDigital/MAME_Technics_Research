import sys, shutil, cProfile, pstats, io
sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab")
import numpy as np
from kn7000live import geom as G, recog as R
from kn7000live.simulate import parse_sim_spec
from kn7000live.app import Engine
from kn7000live.store import DumpStore
shutil.rmtree("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/stQ", ignore_errors=True)
src = parse_sim_spec("sim:48019000,px=12,blur=1.1,shake=1.0")
store = DumpStore("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/stQ")
src.read()
e = Engine(store, G.Registration(G.Quad(np.asarray(src.true_quad, float).copy())),
           R.GlyphBank(), seed_base=0x48019000)
frames = [src.read() for _ in range(25)]
for f in frames[:10]:
    e.process(f)
pr = cProfile.Profile(); pr.enable()
for f in frames[10:]:
    e.process(f)
pr.disable()
s = io.StringIO(); ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
ps.print_stats(14)
print(s.getvalue()[:2600])
print("locked", sum(store.page_state(0x48019000)[1]))

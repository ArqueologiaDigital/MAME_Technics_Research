import sys, shutil
sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab")
import numpy as np
from kn7000live import geom as G, recog as R
from kn7000live.simulate import parse_sim_spec
from kn7000live.app import Engine
from kn7000live.store import DumpStore
from kn7000dump.oracle import Oracle
truth = Oracle().page(0x48019000)
shutil.rmtree("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/stY", ignore_errors=True)
src = parse_sim_spec("sim:48019000,px=12,blur=1.1,shake=0")
store = DumpStore("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/stY")
frozen = src.read()
rng = np.random.default_rng(4242)
q = G.Quad(np.asarray(src.true_quad, float) + rng.normal(0, 1.5, (4, 2)))
e = Engine(store, G.Registration(q), R.GlyphBank(), seed_base=0x48019000)
for i in range(14):
    e.process(frozen, vote=False)
for i in range(45):
    e.process(src.read())
d, m = store.page_state(0x48019000)
bad = [i for i in range(256) if m[i] and d[i] != truth[i]]
print("locked %d  wrong %d" % (int(sum(m)), len(bad)))
for i in bad:
    print("  %08X row %2d col %2d : read %02X truth %02X" % (0x48019000+i, i//16, i%16, d[i], truth[i]))
unread = [i for i in range(256) if not m[i]]
rows_unread = {}
for i in unread: rows_unread[i//16] = rows_unread.get(i//16, 0) + 1
print("unread by row:", dict(sorted(rows_unread.items())))
print("wrong rows are edge rows?", [i//16 for i in bad])

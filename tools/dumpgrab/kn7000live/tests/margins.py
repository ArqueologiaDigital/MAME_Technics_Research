"""What margin do WRONG committed bytes have, compared with right ones?"""
import sys, shutil
sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab")
import numpy as np
from kn7000live import geom as G, recog as R
from kn7000live.simulate import parse_sim_spec
from kn7000live.app import Engine
from kn7000live.store import DumpStore
from kn7000dump.oracle import Oracle
truth = Oracle().page(0x48019000)

rec = {}
orig = DumpStore.observe
def spy(self, addr, value, weight, frame_id):
    rec.setdefault(addr, []).append((value, weight))
    return orig(self, addr, value, weight, frame_id)
DumpStore.observe = spy

for margin_min in (0.02, 0.04, 0.06, 0.08):
    rec.clear()
    shutil.rmtree("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/stM", ignore_errors=True)
    src = parse_sim_spec("sim:48019000,px=12,blur=1.1,shake=0")
    store = DumpStore("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/stM")
    src.read()
    rng = np.random.default_rng(4242)
    q = G.Quad(np.asarray(src.true_quad, float) + rng.normal(0, 1.0, (4, 2)))
    e = Engine(store, G.Registration(q), R.GlyphBank(), seed_base=0x48019000)
    e.reader.byte_margin_min = margin_min
    for i in range(40):
        e.process(src.read())
    d, m = store.page_state(0x48019000)
    bad = [i for i in range(256) if m[i] and d[i] != truth[i]]
    wg = [np.mean([w for v, w in rec.get(0x48019000+i, [(0,0)])]) for i in bad]
    okw = [np.mean([w for v, w in rec.get(0x48019000+i, [(0,0)])])
           for i in range(256) if m[i] and d[i] == truth[i]]
    print("byte_margin_min=%.2f -> locked %3d  wrong %d   mean weight: right %.3f  wrong %s"
          % (margin_min, int(sum(m)), len(bad), np.mean(okw) if okw else 0,
             ("%.3f" % np.mean(wg)) if wg else "-"))

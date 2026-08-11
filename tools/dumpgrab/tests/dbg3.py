import sys, shutil
sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab")
import numpy as np
from kn7000live import geom as G, recog as R
from kn7000live.simulate import parse_sim_spec
from kn7000live.app import Engine
from kn7000live.store import DumpStore
shutil.rmtree("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/st4", ignore_errors=True)

src = parse_sim_spec("sim:48019000,px=12,blur=1.1,shake=1.5")
f = src.read()
store = DumpStore("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/st4")
rng = np.random.default_rng(4242)
q = G.Quad(np.asarray(src.true_quad, float) + rng.normal(0, 6.0, (4, 2)))
e = Engine(store, G.Registration(q), R.GlyphBank(), seed_base=0x48019000)
for i in range(30):
    fr = src.read()
    rd = e.process(fr)
    if i % 5 == 0 or i > 25:
        addrs = ["%08X" % r.address if r.address is not None else "--------" for r in rd.rows[:4]]
        print("f%02d rows_ok=%2d base=%s mot=%s marg=%.3f ncc=%.3f | %s | %s" % (
            i, rd.n_rows_ok, ("%08X"%rd.base) if rd.base else "None",
            ("%.2f"%rd.motion) if rd.motion is not None else "-",
            rd.metrics.get("addr_margin",0), rd.metrics.get("addr_ncc",0),
            " ".join(addrs), e.stats.last_reason))
print("bank n:", e.bank.n, "sep %.3f" % e.bank.separation())
print("true quad:\n", np.round(src.true_quad,1))
print("fitted quad:\n", np.round(e.reg.quad.corners,1))

import sys
sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab")
import numpy as np
from kn7000live import geom as G, recog as R
from kn7000live.simulate import parse_sim_spec
from kn7000live.app import Engine
from kn7000live.store import DumpStore
import shutil
shutil.rmtree("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/st3", ignore_errors=True)

src = parse_sim_spec("sim:48019000,px=12,blur=1.1,shake=0.0")
f = src.read()
store = DumpStore("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/st3")
print("cell pitch of true quad: %.2f x %.2f px" % G.Quad(src.true_quad.copy()).cell_pitch())
for err in (0.0, 1.0, 2.0, 3.0, 4.0, 6.0, 9.0):
    rng = np.random.default_rng(4242)
    q = G.Quad(np.asarray(src.true_quad, float) + rng.normal(0, err, (4, 2)))
    e = Engine(store, G.Registration(q), R.GlyphBank(), seed_base=0x48019000)
    ink, origin = e._ink(f)
    s, ok, why, _ = e.reader.ladder_geometry(e.reg, ink, origin)
    print("corner err %.1f px : score %.3f  ok=%-5s  %s" % (err, s, ok, why))
# pure translation error, which is what a search CAN undo
for dx in (0.0, 2.0, 4.0, 6.0, 8.0):
    q = G.Quad(np.asarray(src.true_quad, float)); q.translate(dx, 0)
    e = Engine(store, G.Registration(q), R.GlyphBank(), seed_base=0x48019000)
    ink, origin = e._ink(f)
    s, ok, why, _ = e.reader.ladder_geometry(e.reg, ink, origin)
    print("translate %.1f px  : score %.3f  ok=%-5s  %s" % (dx, s, ok, why))

import os, sys, shutil
os.environ["SDL_VIDEODRIVER"] = "dummy"
sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab")
import numpy as np, pygame
from kn7000live import geom as G, recog as R
from kn7000live.simulate import parse_sim_spec
from kn7000live.app import Engine, LiveApp
from kn7000live.store import DumpStore

src = parse_sim_spec("sim:48019000,px=12,blur=1.1,shake=1.5")
store = DumpStore("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/gui")
f = src.read()
e = Engine(store, G.Registration(G.Quad(np.asarray(src.true_quad, float).copy())),
           R.GlyphBank(), seed_base=0x48019000)
app = LiveApp(e, src, calib_path="/home/fsanches/.claude/jobs/d0e1b1c2/tmp/gui/calib.json")
for i in range(12):
    app.frame = src.read()
    e.process(app.frame)
    app._draw()
# exercise the key handlers
class Ev:
    def __init__(s, **kw): s.__dict__.update(kw)
for k in (pygame.K_SPACE, pygame.K_1, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP,
          pygame.K_DOWN, pygame.K_EQUALS, pygame.K_MINUS, pygame.K_LEFTBRACKET,
          pygame.K_RIGHTBRACKET, pygame.K_g, pygame.K_h, pygame.K_a, pygame.K_r,
          pygame.K_s, pygame.K_x, pygame.K_0, pygame.K_t):
    assert app._handle(Ev(type=pygame.KEYDOWN, key=k)) is True, k
app._draw()
app._handle(Ev(type=pygame.MOUSEBUTTONDOWN, button=1, pos=(200, 200)))
app._handle(Ev(type=pygame.MOUSEMOTION, pos=(210, 205)))
app._handle(Ev(type=pygame.MOUSEBUTTONUP, button=1, pos=(210, 205)))
app._draw()
assert app._handle(Ev(type=pygame.KEYDOWN, key=pygame.K_q)) is False
e.store.close()
print("GUI smoke test OK -- %d frames drawn, %d bytes in store" %
      (12, sum(sum(m) for m in store.mask.values())))

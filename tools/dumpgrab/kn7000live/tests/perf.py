import sys, shutil, time
sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab")
import numpy as np
from kn7000live import geom as G, recog as R
from kn7000live.simulate import parse_sim_spec
from kn7000live.app import Engine
from kn7000live.store import DumpStore
for (w, h, px) in ((1280, 720, 12.0), (1920, 1080, 18.0)):
    shutil.rmtree("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/stP", ignore_errors=True)
    src = parse_sim_spec("sim:48019000,px=%g,blur=1.1,shake=1.0" % px, width=w, height=h)
    store = DumpStore("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/stP")
    src.read()
    e = Engine(store, G.Registration(G.Quad(np.asarray(src.true_quad, float).copy())),
               R.GlyphBank(), seed_base=0x48019000)
    frames = [src.read() for _ in range(30)]
    for f in frames[:10]:
        e.process(f)
    ms = []
    for f in frames[10:]:
        t = time.time(); e.process(f); ms.append(1000*(time.time()-t))
    print("%4dx%-4d px/char=%4.1f  decoder %5.1f ms/frame  -> %4.1f fps   locked=%d"
          % (w, h, px, np.mean(ms), 1000/np.mean(ms), sum(store.page_state(0x48019000)[1])))

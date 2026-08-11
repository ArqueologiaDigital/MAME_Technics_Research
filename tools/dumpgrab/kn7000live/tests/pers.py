import sys, shutil, os, json
sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab")
import numpy as np
from kn7000live import geom as G, recog as R
from kn7000live.simulate import parse_sim_spec
from kn7000live.app import Engine
from kn7000live.store import DumpStore
D = "/home/fsanches/.claude/jobs/d0e1b1c2/tmp/pers"

# two pages, switching mid-run -- the page-change requirement
src = parse_sim_spec("sim:48019000,px=12,blur=1.1,shake=1.0,pages=3,page_every=60")
store = DumpStore(D)
src.read()
e = Engine(store, G.Registration(G.Quad(np.asarray(src.true_quad, float).copy())),
           R.GlyphBank(), seed_base=0x48019000)
for i in range(180):
    e.process(src.read())
store.close()
print("pages touched: %s" % ["%08X (%d/256)" % (p, store.n_locked(p)) for p in sorted(store.data)])

# reload from disk
s2 = DumpStore(D)
print("reloaded:      %s" % ["%08X (%d/256)" % (p, s2.n_locked(p)) for p in sorted(s2.data)])
assert {p: bytes(s2.data[p]) for p in s2.data} == {p: bytes(store.data[p]) for p in store.data}

# rebuild purely from the journal
os.remove(os.path.join(D, "snapshot.npz")); os.remove(os.path.join(D, "snapshot.pos"))
s3 = DumpStore(D)
n = s3.rebuild()
print("journal replay: %d records -> %s" % (n, ["%08X (%d/256)" % (p, s3.n_locked(p)) for p in sorted(s3.data)]))
assert {p: bytes(s3.data[p]) for p in s3.data} == {p: bytes(store.data[p]) for p in store.data}, "journal != snapshot"

got, tot = s3.export(0x48000000, 0x48000000 + 0x1000, "/home/fsanches/.claude/jobs/d0e1b1c2/tmp/ex.bin")
print("export: %d/%d known; mask sums to %d" % (got, tot,
      sum(open("/home/fsanches/.claude/jobs/d0e1b1c2/tmp/ex.bin.mask","rb").read())))
print("journal head:", open(os.path.join(D,"journal.jsonl")).readline().strip()[:110])

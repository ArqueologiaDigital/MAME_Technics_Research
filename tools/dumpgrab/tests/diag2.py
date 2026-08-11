import sys, os
sys.path.insert(0, "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab")
import numpy as np
from kn7000dump.geometry import fit_grid, texture_map
from kn7000dump.imageutil import load_rgb
from kn7000dump.extract import _cut_patches, refine_grid_by_centroids
from kn7000dump.atlas import AtlasBuilder
from kn7000dump import layout as L
from kn7000dump.oracle import Oracle

D = "/home/fsanches/compartilhado/kn7000_mame/tools/dumpgrab"
truth = Oracle().page(0x48019000)
f = "real-NTSC-48019000.png"
rgb = load_rgb(os.path.join(D, f))
g = fit_grid(rgb); ink = g.ink; tex = texture_map(ink)
g = refine_grid_by_centroids(ink, g, tex=tex)
lay = g.lay

# Build atlas from the FULL known page (oracle-labelled) -- the ceiling for this frame
b = AtlasBuilder()
cells, chars = [], []
for r in range(16):
    s = "%08X" % (0x48019000 + 16*r)
    for j, c in enumerate(lay.addr_idx):
        cells.append((r, c)); chars.append(s[j])
    for k, (hi, lo) in enumerate(lay.byte_idx):
        v = truth[r*16+k]
        cells.append((r, hi)); chars.append("%X" % (v >> 4))
        cells.append((r, lo)); chars.append("%X" % (v & 15))
P = _cut_patches(ink, g, cells, 18, 12, tex=tex)
b.add_many(chars, P)
at = b.finish()
print("oracle atlas classes=%s counts=%s" % ("".join(at.labels), list(at.counts)))
hex_idx = list(range(len(at.labels)))
idx, ncc, mrg = at.classify(P, allowed=hex_idx)
pred = [at.labels[i] for i in idx]
acc = sum(1 for p, c in zip(pred, chars) if p == c) / len(chars)
print("TRAINING accuracy on its own frame: %.1f%%  (%d chars)  mean ncc=%.3f mean margin=%.4f"
      % (100*acc, len(chars), ncc.mean(), mrg.mean()))
# per-class confusion for the worst classes
from collections import Counter
bad = Counter()
for p, c in zip(pred, chars):
    if p != c: bad[(c, p)] += 1
print("worst confusions:", bad.most_common(10))

# how separable are the 16 class templates from each other?
T = at.flat
S = T @ T.T
off = S[~np.eye(len(at.labels), dtype=bool)]
print("template pairwise NCC: mean=%.3f max=%.3f" % (off.mean(), off.max()))
i, j = np.unravel_index(np.argmax(S - np.eye(len(at.labels))*9), S.shape)
print("closest pair: '%s' vs '%s' = %.3f" % (at.labels[i], at.labels[j], S[i, j]))

# ink amplitude inside cells
byte_cells = [(r, c) for r in range(16) for (hi, lo) in lay.byte_idx for c in (hi, lo)]
Pb = _cut_patches(ink, g, byte_cells, 18, 12, tex=tex)
print("byte-cell patch std: mean=%.4f  (address cells: %.4f)"
      % (Pb.std(axis=(1,2)).mean(),
         _cut_patches(ink, g, [(r,c) for r in range(16) for c in lay.addr_idx], 18,12, tex=tex).std(axis=(1,2)).mean()))

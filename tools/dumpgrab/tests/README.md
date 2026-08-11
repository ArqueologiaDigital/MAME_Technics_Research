# kn7000dump measurement + development harness

Counterpart to `../kn7000live/tests/`, which covers the live-camera tool. These cover the **offline**
decoder (`kn7000dump`) and the development of the live one. Rescued from session scratch on
2026-08-11; paths are absolute to this machine — adjust the `sys.path.insert` if moved.

Verified to run from here: `measure1.py`, `ladder.py` (+ its `locate.py` dependency).
The rest were saved wholesale under time pressure and are **not individually re-verified** —
triage them before trusting any output.

## Load-bearing — these back a published claim

| script | question it answers |
|---|---|
| `measure1.py` | offline decoder accuracy on the two real reference photos, scored against the Oracle, both overall and over the 75 non-`0x77` cells. **Source of the blog's "31 % of a page"** — reproduces as `all=31.6 % / non77=1.3 %` (native atlas, NTSC). |
| `ladder.py` | can the address ladder alone referee a candidate grid? Evidence for the documented "the referee cannot be the ladder alone": `prefixok=48/96` while `col7ok=1/16` — the ladder is the left eighth of the block and cannot see the far end sliding off. **Imports `crop_panel` from `locate.py`.** |
| `locate.py` | finds the screen panel inside a full photo (largest bright component) and crops to it. Dependency of `ladder.py`; the only copy of that algorithm. |

## Probably worth keeping

| script | question |
|---|---|
| `selftrain.py` | self-supervised atlas quality, per frame and as a joint atlas over two frames |
| `photos.py` | self-supervised atlas built from the real photo corpus |
| `geom1.py` | geometry stats per photo: slope, row pitch, glyph self-similarity, ink/texture percentiles |

## Single-shot development probes — likely disposable

`dbg1.py`–`dbg10.py`, `diag2.py`–`diag6.py`, `why.py`, `trace3.py`. Each was written to inspect one
piece of intermediate state while chasing one bug during the kn7000live build (DLT conditioning,
the training feedback loop, the ink-map crop margin, tracker bias). The bugs they found are fixed
and covered by the committed `../kn7000live/tests/`. Kept only because the cost of keeping them is
near zero and the cost of having been wrong about that is high.

⚠ Report accuracy **twice** — overall and over the non-`0x77` cells. The calibration page is 71 %
one byte, so a decoder that always guesses `0x77` scores 71 % and is useless.

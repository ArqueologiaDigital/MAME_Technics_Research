# kn7000live measurement harness

Every number in `../README.md` came from one of these. They print numbers; no image ever reaches
a model. Paths are absolute to this machine — adjust the `sys.path.insert` and store dirs if moved.

| script | question it answers |
|---|---|
| `final.py` | the seven-condition matrix: committed / wrong / non-0x77 coverage |
| `frozen.py` | the freeze-place-resume workflow, per shake amplitude |
| `sweep.py` | earlier form of the conditions matrix |
| `jit.py` | jitter amplitude vs coverage and wrong bytes |
| `wrong.py` | which bytes were committed wrongly, and the template confusions |
| `margins.py` | do wrong bytes have separable confidence? (no: 0.91 vs 0.99) |
| `perf.py`, `prof.py` | frame rate and cProfile of the decode loop |
| `coldbench.py` | cost per frame with no screen in view |
| `gui_smoke.py` | headless pygame smoke test, exercises every key handler |
| `pers.py`, `pages.py` | store persistence, journal rebuild, page switching |
| `which.py` | locate wrongly committed bytes in a store |

⚠ Report accuracy **twice** on the calibration page: overall and over the 75 non-`0x77` cells. It
is 71 % one byte, so a decoder that always guessed `0x77` scores 71 % and is useless.

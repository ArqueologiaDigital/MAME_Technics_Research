# KN5000 control-panel-serial repros (deterministic, byte-identical across runs)

These are the press schedules that reproduce the `kn5000-30` mid-byte gate-close wedge. They were
found and cross-checked by three independent verification passes on 2026-07-21 and are kept here
because they had been living in an ephemeral session scratchpad. Every one of them is
**deterministic**: a repeat run produces byte-identical snapshot PNGs.

| lua | what it does | on the shipped build (kn5000-30) |
|---|---|---|
| `a1.lua` | 90 presses at 0.15 s from t=30 s, sound-group buttons only, no boot presses | **strands at t=31.141644, rx_count=5, LINK DEAD** |
| `b1.lua` (= `ph000.lua`) | 6 presses during boot + 33 presses at 2 Hz — **ordinary playing** | **strands at rx_count=7, LINK DEAD** |
| `b3.lua` | 220 presses on a drifting interval (sweeps many phases in one run) | **strands at rx_count=4, LINK DEAD** |
| `ph007.lua` | boot-window press phase +0.07 s | **strands at rx_count=6, LINK DEAD** |
| `ph017.lua` / `ph033.lua` / `ph050.lua` | phase +0.17 / +0.33 / +0.50 s | clean — `ph033` is the **bit-identity control** |
| `soak.lua` | 444 presses over 223 emulated s | clean, zero strands (rules out press count/rate as the trigger) |
| `a1soak.lua` | a1 followed by a long idle | never resynchronises on its own |

`gen.py` generated the phase-sweep variants.

### Added 2026-07-21 by the option-A pass (these are the *candidate-killers*)

The five below were written to test option A (the sender-side handshake). Two of them are the
reason A was rejected: they are configurations the **shipped build handles correctly and option A
breaks**, so keep them in the gate for anything that touches this link.

| lua | what it does | shipped build | option-A candidate |
|---|---|---|---|
| `x_sim2.lua` | **two buttons pressed at the same instant** (PIANO + ORCHESTRAL PAD), 20× at 0.6 s | LIVE, all presses correct | **DEAD** + false ENTERTAINER/VOCAL REVERB dispatch |
| `pfx3.lua` | **three presses from a cold boot**: SPLIT POINT / AUTO PLAY CHORD / SPLIT POINT | `RIGHT1 Piano` | **`RIGHT1 Sound Name Error`** (kn5000-29 regression) |
| `x_multi.lua` | 8 buttons in 8 segments pressed together, 30× at 0.6 s | LIVE | DEAD, `tmr_dead` 1.5 M, `cp_qmax` 466 |
| `bootwin.lua` | the 6 boot-window presses of `b1` **and nothing else**, then settle + liveness | presses take effect, clean | identical to shipped |
| `s4.lua` | the S4 shape: 4 boot-window presses + 33 late | — | LIVE |

`x_sim2.lua` and `x_multi.lua` press several buttons at the same instant, so they `table.sort`
their action list: without that the second and later buttons of a simultaneous group get pressed
and released inside one dispatch, i.e. invisibly to the panel's 2-scan / 14 ms confirmation filter.
Copy that pattern in any new simultaneous-press schedule.

## How to run one

```
./run.sh a1 a1.lua /home/fsanches/compartilhado/kn7000_mame_build/kn7000
```

Output lands in `$OUTBASE` (default `/tmp/kn5000-cpserial-repros/<name>/`): `out.log`, an empty
private `nvram/`, and `snap/kn5000/*.png`.

## How to read the result — the rule that has burned this project twice

**Liveness is a PIXEL DIFF.** Each lua takes snapshots around four "liveness" presses at the end.
If those PNGs are byte-identical, the panel is dead, no matter what any counter says. Read the PNGs
with an image viewer / the Read tool; never infer screen state from the log. And before reporting
that some instrumented event did *not* happen, prove the instrument can SEE it happen in a
configuration where it does — a blind probe's zero looks exactly like a real one. That mistake is
what let `kn5000-30` ship as a cure, and it is what nearly landed option C.

**A counter can also be a tautology.** Option A's headline acceptance number — "zero dropped
panel-clocked edges" — could not increment under option A at all: the panel only emitted an edge
when the gate was open, tested in the same callback, so `drop_ext = 0` was enforced by
construction. It read a clean 0 in runs where the panel was dead and dispatching presses nobody
made, and a clean `strand_entry = 0 / PHASE_HIST 7:152 / cp_qmax 21` accompanied the `pfx3`
regression. Prefer `strand_entry`, `strand_exit_mid`, the `PHASE_HIST` bucket count, `tmr_dead`,
`cp_qmax` and `max_rearm` — and above all, the pixel diff.

## Gotchas

* Always `-skip_gameinfo`, always a visible `-window` on `:0` (never `-video none`), always an
  EMPTY private nvram directory, always `timeout`-wrapped.
* Boot completes at ~20 emulated s; a settled fresh boot shows **no transpose box**.
* Run them sequentially; this box has 8 cores and fanning out MAME instances makes it unusable.

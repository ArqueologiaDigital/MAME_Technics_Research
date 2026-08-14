# IC307 page 2 — what it is, and why its 48 % period "failure" is not a defect

*2026-08-14. Five-agent investigation plus an adversarial adjudication that re-derived every
load-bearing number. Probes staged in `notes/ic307-page2-probes/` (un-triaged).*

## The question

`detect_period()` returns its `P = N` fallback for 543 of IC307's 1495 chunks, and **500 of
those are on page 2** (against 11/198, 32/168, 0/57 elsewhere). Page 2 is 1050 chunks — 70 % of
the chip. Task-queue item P11 proposed lowering the acceptance gate from `peak >= 0.5` to fix it.

## What page 2 actually is

**One well-formed directory, two different materials.**

| entries | what | share of page bytes |
|---|---|---|
| `0x000`–`~0x03F` | 38–39 long multi-cycle recordings, up to 26,832 samples — the **orchestral string-ensemble multisamples** | **82.6 %** |
| above `~0x040` | ~1030 tiny, synthetic, exactly-periodic **wavetable** chunks (median 64 samples) | ~17 % |

The wavetable half is unmistakable: **92.8 % of page 2's chunks have exact power-of-two lengths**
(585×64, 310×128, 71×256) against 9.6 % / 1.8 % / 8.8 % on pages 0/1/3; 960 of 1072 have DC
exactly zero; 964 start on a sample of exactly zero against a 3.23 % background.

⚠ The tone generator's source calls page 2 "drawbar footage". The *wavetable* character is
measured; the *drawbar* label is interpretation, and the discriminating test for it **failed**
(half-wave antisymmetry residual 2.01 against a null of 2.11). Grade it accordingly — and note
the driver comment predates the measurement, so agreeing with it is partly confirming a prior.

## What references it — my earlier claim was wrong

I reported that nothing named page 2. That came from a one-character bug in my own tool
(`split(",")` where the field also uses `;`), fixed in `ac11f7c`.

**23 named patches** reach page 2 through 12 of 487 SET descriptors: Concert / Unison / Heavenly /
Dreamy Strings, Violin / Viola / Cello / Bass Ensemble, Chamber Orch, Springtime Orch, Orchestral
Sweep, Piano & Strings, Strings & Horns, Strings & Flutes, Dark Movie Scene, Accomp Drawbars,
Pop / Soul / Rock / Perc Organ, Organ Bass, Bright E.Bass. So page 2 holds material the
instrument genuinely plays — the organ family *and* the string ensembles.

But only **49 of 1072 entries** are addressable, all `<= 0x096`. Nothing can reach the ~1020
above: the sole writer of the wave-select word is the sub-CPU zone-record emitter (12 references
to `0x0451CE`), and an exhaustive 487×128 walk finds no entry `>= 0x097`.

## The verdict on P11: narrow it, do not land the gate change

**All 11 referenced page-2 fallbacks are 16–144-sample chunks whose true period *is* N.** `P = N`
is arithmetically the only answer available: `detect_period`'s `maxlag` is ≈ N/3 for N ≥ 96, so a
period equal to N is unreachable **by construction**. Page 2 is exonerated.

The genuine errors on page 2 — 42 two-cycle 128-sample chunks that would play an octave sharp,
and 4 long tonal chunks — are **all unreferenced**. Net audible page-2 period defect: **zero**.

**Gate-lowering is falsified on ground truth.** On four chunks whose true period is provably 64,
gate 0.30 returns **31.53** — the second harmonic, an octave wrong in the other direction. And the
42-chunk error is a **search-range** defect, not a gate defect: at N=128 `maxlag` is 43, so period
64 is unreachable at *any* threshold.

**Land instead the narrow piece:** when the gate rejects and **N > 256**, return `0` rather than
`N<<16`. Code-verified loop-neutral (`compute_loop` maps both P=0 and P=N to `(0, N)`,
kn5000_tonegen.cpp:2296-2309). Reaches 43 chunks, 35 referenced, 3 audible.

**★ The real fallback damage is on PAGES 1 AND 0**, not page 2. Re-verified here
(`notes/ic307-page2-probes/page1.py`):

| page | referenced fallbacks | of which ≥512 samples | lengths |
|---|---|---|---|
| 0 | 10 | **6** | 968–2016 |
| 1 | 29 | **23** | 608–1816 |
| 2 | 11 | **0** | max 144 |
| 3 | 0 | 0 | — |

A fallback on a chunk of ≥512 samples is a real defect: `P = N` makes it stretch, audibly. So the
target is **29 long referenced fallbacks across pages 0 and 1**, not the 543 the raw count
suggested — and none of them on page 2.

⚠ **Use the ROM, not the TSV, for "referenced".** The reference set must come from walking the
487 SET descriptors in the table-data ROM and reading the real `+0x040` words
(`tools/kn5000_referenced_fallbacks.py`). Using the derived
`notes/data/kn5000-multisample-sets.tsv` zone column instead is a *narrower* view, and it made a
first pass of this check report **zero** referenced chunks where the ROM walk finds 29 — nearly
causing the fix to be dismissed as unreachable. Note also that the table-data image is the two
halves interleaved as **16-bit words**, even half first; byte-wise interleaving yields a
different image (md5 `55a92199…` against the correct `57d838b3…`) that parses into nonsense.

Independent confirmation from the emulator's own source: `kn5000_tonegen.cpp` (~L310) already
blames audible "extreme noise" on `+040 = 0x505B` and `0x5046`. Both decode to **page 1**, entries
`0x05B` and `0x046`, lengths 1496 and 1568 — and both fall back today. The code named two
offenders before anyone counted them, and they sit exactly where this analysis points.

## The falsification test, run

The verdict rests on the ~1020 tail entries being unreachable. `WaveSel_StageB_Store_Reg040`
doubles the class nibble when `ToneGen_GlobalFlags` (sub-CPU `0x041343`) **bit 2** is set, which
would remap class 3's 415 entries onto class 6 and make the tail reachable.

Measured with `tools/rigs/kn5000_tgflags.lua` (2,066 samples over 40 s, fresh cfg, nvram1
deleted): the byte is `0x00` until t=3.98 s, then `0x08`, and **bit 2 is never set**. The verdict
stands. Caveat stated by the rig itself: one boot at the home screen is weaker than a proof —
exercising an organ/drawbar patch would strengthen it.

## Two retractions this forces

1. **`notes/kn5000-firmware-sample-tables.md` §8** says class 6 is reached "mostly through the
   610-record footage table rather than through patch partials". The opposite is true: **10 of 12**
   class-6 SETs come from patch partials, **1** from the named table.
2. **`notes/kn5000-ic307-content-map.md` §2.3** calls page 2's directory a "rising-audio artifact /
   coincidental". Refuted: page 0's undisputed directory reads *louder* as s16le than page 2's
   (rms 11370 vs 8448), so the discriminator that condemned page 2 acquits nothing. A sliding
   window over all 2,097,150 candidate bases accepts only 4 with n≥20, and 0 in shuffled or
   random data.

## Acceptance test for whatever is landed

The zone-slope oracle **cannot** be it — 94 chunks change, 321 are referenced, overlap zero. A
criterion that cannot fire is not a test. Required instead:

1. **Invariance half:** the K-law cluster and zone-slope oracle must not move (321/377 in cluster,
   median |dev| 9.9), proving no melodic regression.
2. **Firing half:** the LOG_GLITCH + spectrum A/B, repeated on p1c44 and p1c72.
3. **Pre-declared refutation:** if the high-band drop arrives *with* a level drop, it is removing
   signal, not aliasing — reject.
4. **Fix the selection first:** `b0p1c35` is a *bank-0* selection, i.e. the BAD_DUMP copy of
   IC307. Re-run on a bank-1 selection or the A/B measures the substitution, not the fix.
5. **Negative control:** a chunk accepted with peak 0.9979 (p1c4) must be bit-identical after.

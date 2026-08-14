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


---

## ⚠ RETRACTED — the A/B below was VACUOUS (corrected 2026-08-15)

**Both captures are pure silence.** rms 0.00 and peak 0 across all 90 s, in both arms. The
"bit-identical" result was therefore guaranteed and means nothing: two silent files are
identical trivially. It is **not** evidence of no regression, and I wrote it up as if it were.

Measured afterwards, which is the wrong order:

| window | rms | peak |
|---|---|---|
| boot, t=0-20 | 0.00 | 0 |
| t=35-50 | 0.00 | 0 |
| t=50-70 | 0.00 | 0 |
| t=70-89 | 0.00 | 0 |

Corroborated independently by `tools/rigs/kn5000_waveselect_log.lua`: across the same 90 s the
machine issues only **2 distinct wave-select words** (`0x0000` and `0x0002`, both bank 0 page 0)
in 2,343 tone-generator writes. Essentially nothing is being played.

Two checks were skipped and either would have caught it: **verify the stimulus actually fired**
(there is no evidence the demo ever started), and **verify the capture is non-silent before
comparing it**. The project's own rules say both — "a difference from SILENCE is not a signal"
and "a test with no notes playing is not a test".

The A/B section is kept below, struck through, because the mistake is more instructive than a
clean deletion.

## ~~A/B against the real emulator (2026-08-14/15)~~ (VACUOUS — see above)

Two full builds, differing only in the `detect_period` bound (2048 vs 256), each capturing 90 s
of the Feature Presentation demo — sequencer, accompaniment and drum parts, one button press,
`nvram1` deleted, fresh cfg (`tools/rigs/kn5000_demo_capture.lua`, compared with
`tools/kn5000_wav_ab.py`).

**Result: the two captures are BIT-IDENTICAL** (4,320,001 frames, 3 ch, 48 kHz).

What that does and does not establish:

* ✅ **No regression.** The strongest invariance evidence available short of a full corpus: 90 s
  of the instrument playing itself, unchanged to the sample.
* ❌ **The benefit is still unproven in-emulator.** The demo never selects any of the 35 affected
  chunks, so this A/B cannot speak to whether the fix improves anything. A negative that the
  comparison tool reports explicitly rather than hunting for a difference that is not there.

**Why the demo is the wrong stimulus:** the two chunks the tone-generator source itself blames
for "extreme noise" are `+040 = 0x505B` (**Brush Slap**, SET 375) and `0x5046` (**Rock Rim**,
SET 376) — drum-kit sounds reached through the percussion table. **No melodic patch references
them** (checked against `kn5000-patch-partials.tsv`), and the demo's styles evidently do not
either.

**What would exercise it:** a stimulus that plays those specific drums — a rhythm style that uses
them, a DRUM KITS patch played from the keybed, or MIDI note-ons on the drum channel. Identifying
which factory style uses SET 375/376 means decoding the rhythm patterns in IC14, so the MIDI or
keybed route is likely cheaper.

Until then the honest status of the fix is: **argued from code and arithmetic, verified not to
regress, not yet heard.**


---

## The A/B, done properly (2026-08-15)

After the retraction above, both faults were fixed — the demo is now started with its real
navigation (`DEMO → LEFT 4 → LEFT 2`, confirmed by `transport=0x04`, `accmode=0x03`, sub-tick
cycling), and the analysis reads **channels 1 and 2** rather than the permanently-silent
channel 0.

**The stimulus does reach the change.** `tools/rigs/kn5000_waveselect_log.lua` logs 90,960 TG
writes and **151 distinct wave-select words** over 90 s, of which **9 are chunks this change
affects**, two of them heavily:

| `+040` | bank | page | chunk | samples | times selected |
|---|---|---|---|---|---|
| `0x5049` | 1 | 1 | `0x049` | 1120 | **306** |
| `0x507D` | 1 | 1 | `0x07D` | 1344 | **140** |
| `0x409D` | 1 | 0 | `0x09D` | 352 | 109 |
| `0x1023` | 0 | 1 | `0x023` | 1496 | 8 |
| `0x1048` | 0 | 1 | `0x048` | 736 | 7 |
| `0x605F` / `0x605E` | 1 | 2 | | 1544 | 4 / 2 |
| `0x1049` | 0 | 1 | `0x049` | 1120 | 2 |
| `0x1046` | 0 | 1 | `0x046` | 1568 | 1 |

Note several are on **bank 0** — the substituted socket, which carries a copy of IC307 — so the
same chunks are reachable through the undumped banks too.

**Result of two builds differing only in the bound:**

| measure | value |
|---|---|
| samples differing | **586,492 of 12,960,003 (4.53 %)** |
| peak sample delta | 871 |
| rms of the difference | 5.3 |
| overall rms ch1 | 455.25 → **455.27** |
| overall rms ch2 | 499.78 → **499.79** |

Differences begin at t≈27 s, when the demo starts playing, and recur throughout; per-second
rms-of-difference peaks around 18 against a signal rms of 300–700.

**What this establishes.** The change is real, bounded, and **level-preserving** — which is the
adjudicator's pre-declared refutation criterion, run in the direction that could have failed: if
the high-band content had dropped *together with* the level, the change would be removing signal
rather than removing aliasing, and it would have to be rejected. Overall rms moves by 0.02 and
0.01 counts on a signal of 455 and 500.

**What it still does not establish** is that the result is *better*. That rests on the arithmetic:
a 1120-sample recording selected 306 times now plays at its own rate instead of `step = freq × N /
48000` ≈ 6–8× too fast. The A/B proves the code path is live and does not damage the mix; it
cannot by itself adjudicate taste. Felipe's ear on the Feature Presentation demo is the remaining
check, and it is cheap — the two captures exist.

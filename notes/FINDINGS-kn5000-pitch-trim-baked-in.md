# Demo/rhythm pitch now decodes from the firmware's own per-selector constant

2026-08-06. Commits `549b6cf` (the change) and `c5c2fde` (tooling + the captured kon.log).
Verdict: **CONFIRMED**. Binary published. Keybed audio byte-identical.

## The change

In `update_pitch()`, ONLY in the `true_note < 0 && regs[8] != 0` branch (demo / rhythm /
sequencer — everything the old `0x3524` anchor served):

    note_f = (double(int(v.regs[8])) - 128.0 - double(c)) / 256.0;
    freq   = 440.0 * pow(2.0, (note_f - 69.0) / 12.0);

`c` comes from a four-rung ladder, and which rung fired is recorded per voice:

| rung | meaning |
|---|---|
| `ANCHOR_FIRMWARE` | table hit, selector carries exactly one C |
| `ANCHOR_FIRMWARE_AMBIG` | table hit, >1 C, key-weighted MODAL value used |
| `ANCHOR_LEARNED` | no table entry, but the chunk's runtime trim was pinned by an untransposed keybed press |
| `ANCHOR_CONSTANT` | nothing placed it: `c = -1884`, which is ALGEBRAICALLY the old anchor |

`pitch_offset` is deliberately NOT added here — it is already inside `regs[8]`, and
`resolve_note_group()` only runs on `true_note >= 0` voices, so it is 0 in this branch anyway.

The table is a GENERATED HEADER compiled in (`src/mame/matsushita/kn5000_pitch_trim.hxx`, 1444
entries, ~5.8 KB rodata, `lower_bound`), not a file read at runtime — a MAME device must not
depend on a file outside its ROM regions. `tools/gen_kn5000_pitch_trim.py --check` fails if the
header is stale w.r.t. `notes/data/kn5000-pitch-trim-table.tsv`, and it transcribes the tsv's
`C_modal` column VERBATIM so the device and the offline predictions use bit-identical constants.

## ⚠ TWO OF THE AGREED PREDICTIONS COULD NOT FAIL. Recorded so the mistake is not repeated.

**Prediction 1 as written was not a test of the patch.** `parts.py` computes
`(pit - 128 - C)/256` in PYTHON from a captured log, so it returns byte-identical numbers before
and after the build — it grades the TABLE, which was already established. Worse, note attribution
itself requires `|decoded - MIDI| <= 0.5`, so the metric is structurally guaranteed once the
device renders the decoded note. **Prediction 2 (`hit_own`) collapses onto the same tautology.**

This is the same failure mode as the earlier "sine mode has 0 clicks" null. **A criterion that
cannot fail is not a pass** — and it was written into the brief twice by the same author (me).

## What was measured INSTEAD, and could have failed

**Device-level integrality.** Read the note the DEVICE itself chose, from its own `LOG_VOICE`
output, and ask how often it is a whole MIDI note:

| | rate |
|---|---|
| patched device, 5327 covered note-ons | **69.2%** |
| C-permuted null | 18.2 +/- 3.9% |
| the old 0x3524 anchor | 1.0% |
| | **z = +13.1** |

And the device provably implements the table rather than something that merely correlates:
`max |device note - (regs[8]-0x80-C)/256| = 0.0074 st` over 5327 note-ons — the resolution of the
2-dp frequency print.

**Independent AUDIO evidence** (the oracle, sine captures, fixed bpm 90.000 / t0 17.419):

| part | argmax shift before | after | z before | z after |
|---|---|---|---|---|
| Part 2 | +0 | **+0** | +3.36 | **+7.16** |
| Part 7 | +2 | **+0** | +13.75 | **+16.63** |
| Part 8 | +7 | **+0** | +9.64 | **+18.07** |
| Part 11 | +7 | **+0** | +12.39 | **+17.04** |
| Part 6 | +0 | +0 | 0.462 -> 0.769 hit@0 | |
| Part 12 | +5 | **+0** | 0.415 -> 0.610 | |

**Global histogram, audio, melodic n=2111, window 18-132.5 s:** baseline argmax **k=+7**
(0.3842); patched argmax **k=0** (0.3747), now the UNIQUE maximum, standing 0.11 above both
neighbours (k=+/-1 = 0.2620). +7 is exactly the mode the register analysis predicted.
Pitch-specific information `hit@0 - NULL-P`: **+0.012 -> +0.078** against a positive control of
+0.483, i.e. recovery of the control's absolute-pitch information **2.5% -> 16%**.

**Baseline reproducibility:** the register histogram on a FRESH capture reproduces the published
one to the decimal — +7 38.6% (was 39.2), +18 11.5% (11.4), +19 11.0% (10.9), bin 0 = 0.8%.

## Regression gate — passed in its strongest form

Separate PCM run (TGMODE verified 0x00 every emulated second), no demo, chromatic run over all
60 keys MIDI 36..95 plus six four-note chords:

* 772 keybed `LOG_VOICE` lines covering every key are **md5-identical** between baseline and
  patched.
* The ENTIRE 52 s capture is **BYTE-identical**: 14,976,050 bytes, `cmp` clean.
* **POSITIVE CONTROL** that the comparison can see a pitch change: the same byte comparison on
  the DEMO captures reports 72.2% of 6,960,001 frames differing, first difference at t=19.263 s.

## Coverage — demo-weighted, 5956 note-ons

| rung | share |
|---|---|
| firmware-C | 66.6% |
| firmware-C (ambiguous, modal) | 23.8% |
| learned trim | 0.0% (predicted inert during pure demo playback; confirmed) |
| **CONSTANT (old anchor)** | **8.5%** |
| none | 1.1% |
| **placed** | **90.4%** (decode.py independently: 91.4%) |

`device_stop()` prints this census UNCONDITIONALLY, plus the top 24 selectors that fell through to
`ANCHOR_CONSTANT` with their class/entry and hit counts — that list is the work queue for
extending the table.

## Honest limits

* **16% recovery, not 100%.** One fault fixed, not the pitch problem solved.
* **60 of the 77 ambiguous selectors are TIES** — no candidate has a majority, so the winner is
  Python `Counter` insertion order (SET-descriptor file order). Deterministic and byte-reproducible
  via the tsv, but ARBITRARY. An integrality-based tie-break (prefer the C decoding to a whole
  MIDI note) is visibly better for at least `0x3086` and is the obvious next refinement.
* 8.5% of demo note-ons still use the old constant.

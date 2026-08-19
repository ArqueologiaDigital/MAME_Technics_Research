# KN5000 root-pitch probes

The KN5000 tone generator HLE must recover the true note behind register `+0x400`, which the
sub-CPU writes as `(note << 8) + 0x80 + C + 2*fine + detune`. `C` is a per-recording constant.
These scripts test where `C` -- or the recording root it stands for -- can be obtained from.

| script | question it answers | run it |
|---|---|---|
| `lowbyte.py` | How much of `C` is readable from the register stream itself? | `python3 lowbyte.py` |
| `ic307_record_root_probe.py` | Does IC307's own parameter record carry the per-chunk root (the 3-bit octave `m`) for the chunks it describes? Purity gated against a permutation null. | `python3 ic307_record_root_probe.py` |
| `ic307_record_root_controls.py` | Is that apparent signal just positional autocorrelation of the directory? Compares against features **not in the record at all**. | `python3 ic307_record_root_controls.py` |

Inputs: the committed `gt.json` ground truth and `kon.log` capture in this directory, plus the
IC307 dump from the emulator's rompath. Nothing is written.

## What they established (2026-08-19)

**`C` cannot be recovered from the register stream.** The sub-CPU folds it into `+0x400` before any
bus cycle: one equation, two unknowns. Worse, `Pitch_Fold_Octaves_Into_Range` runs BEFORE wave
selection and folds out-of-range notes by whole octaves, so two notes an octave apart can produce a
bit-identical register burst. The real IC303 cannot distinguish them either -- this is information
destroyed by design, not an undecoded field.

**The sub-semitone part IS recoverable.** True notes are integers, so `C mod 0x100` shows up in the
low byte of `+0x400`: 83.8% integer-note hit rate on single-C selectors against a 22.0% `C = 0`
control, over the committed 5956-event capture.

**IC307's parameter records do not carry the root.** The candidate field scores at or below controls
built from features that are not in the record at all -- and the converse test is the clearest:
across 13 groups of chunks sharing one physical recording, the key byte varies in 13 of 13 while `m`
varies in 0 of 13. The field tracks the key split, not the recording's pitch.

⚠ **Distinguish "could separate" from "did separate".** 57 of the 77 ambiguous selectors have
candidate `C` values with distinct low bytes, but only 16 appear in the capture at all and only 1 is
fully resolved by what was observed. The first number is an upper bound on the payoff, not the
payoff; an earlier write-up conflated them.

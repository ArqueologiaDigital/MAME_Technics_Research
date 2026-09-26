# Documentation sweep, 2026-09-26

The overlay had accumulated statements that upstream had overtaken — work described
as unsubmitted that was merged, a build-file inventory naming two files where the
script symlinks fifty-eight, and a measurement used as evidence for a conclusion it
was derived from. This is the sweep that fixed them and the ledger of what it did.

## Files

| file | what it is |
|---|---|
| `edits.json` | all 63 reviewed proposals — `file`, `line`, `old`, `new`, `why`, `severity`, plus `replacement_present`: whether that proposal's replacement text is in the tree now |
| `apply_edits.py` | the applier, which is also the gate: anchors must match byte-for-byte or the edit is dropped |

## How the proposals were produced

Four audit lanes (the 488 Hz figure, work wrongly described as pending, the
build/integration documents, `wsa1.cpp` against what actually merged as #16204),
each followed by an adversarial refuter whose brief was to check that every anchor
resolved, that the current text really was wrong, and that the replacement was true.
The refuters kept 63 of the 61 originally proposed — they added some the first pass
missed and dropped others.

## What the applier did

    applied 56   dropped 7

Seven were dropped: two whose anchor no longer existed (that region had been
rewritten earlier the same day) and five that overlapped a rival edit at the same
site.

**That run is the authoritative count, not `replacement_present`.** The flag counts
63 minus 5 = 58 true, which is two more than the applier changed: for two proposals
the replacement text was already in the file, because the auditor read that region
after it had been rewritten that morning and proposed what was largely already
there. The flag answers "is this text in the tree?", which is the useful question
when re-reading the ledger; it is not a count of what this script did. All five concerns were re-checked afterwards by hand and found already covered
by the winning edit. One further correction was made by hand after a residue sweep
(`wsa1_cpanel.h`, which claimed "no databook is in these trees" — untrue since the
TMP95C061 databook was located). **57 changes over 23 files in total.**

## Re-running it

    python3 notes/overlay-upstream-sync/doc-audit-2026-09-26/apply_edits.py edits.json --dry-run

Against the current tree this prints `would apply 0   dropped 63`, every anchor
having been consumed. That is the correct post-application state and the check that
the sweep cannot be applied twice.

## The one distinction that mattered most

`488.28 Hz` is the correct rate of the SX-WSA1R's RAM 0x0080 tick, and passages that
merely state it were **left alone**. It is wrong only where it was used to ARGUE that
the databook tap scale is right, because it is `fc/2048/TREG1` with that tap assumed
and every Technics firmware sets TREG1 to fc-in-MHz, so it collapses to `1e6/2048`
whatever the crystal. Ten passages did that; they were corrected without losing a
single measurement. Deleting every occurrence would have destroyed accurate
documentation, which is the failure this sweep was most at risk of.

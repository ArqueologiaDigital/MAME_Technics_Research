# Round 8 adjudication — APPLIED SIDE

Companion to `~/compartilhado/kn5000-roms-disasm/dsp/analysis/adjudication-round8.md`.

## What changed in this repo

**Nothing behavioural. No forcing survived adjudication.** All four round-7
passes reported an empty FORCED list for Apply and the audit confirms it.

Two files, comments only:

- `src/devices/cpu/upd6383/upd6383d.h` — the `LO_ACT_CAP_TA2` block
- `src/devices/cpu/upd6383/upd6383.cpp` — the `LO_ACT_CAP_TA2` case in `exec_alu`

**The diff is provably semantics-free.** Every added and removed line is a
comment except the enumerator line itself, whose **value `0x19` is unchanged** —
only its trailing comment differs:

```
-  LO_ACT_CAP_TA2 = 0x19   // tempA <- bus, the second capture pair
+  LO_ACT_CAP_TA2 = 0x19   // tempA <- ??? : DESTINATION measured (74/89, ...
```

Reproduce the check:

```bash
git diff -U0 src/devices/cpu/upd6383/ | grep '^[+-]' | grep -vE '^(\+\+\+|---)' \
  | sed 's/^.//' | grep -vE '^\s*(//|\*|/\*)' | grep -vE '^\s*$'
```

## Why the comments had to change

Three shipped comment sites stated as fact things now measured to be false.

1. **"What re-derives it is a TWO-ADDRESS delay line … which no tool in
   dsp/tools has yet. That is round 6's rank-1 experiment."** (both mirrors)
   **False on both halves.** The line exists (`dsp/tools/delayline.py`, audited
   independently in `dsp/tools/adjudicate8.py harness`) and it **does not**
   re-derive the forcing and cannot: at the FORCED polarity both of SINGLE
   DELAY's loops cross `w21..w24` (ACTIONs `0x0D`/`0x0E`, undecoded), so no
   executable window contains a delay loop. Every cell of the enumeration is
   `-- NONE --` — **an absence of a search, not a zero.**

2. **"0x13 and 0x19 are ONE OPERATION IN TWO ENCODINGS"** (`upd6383.cpp`)
   **Unsupported, and no longer asserted.** Their consumer lags are disjoint —
   `0x13`'s tempA reader sits at lag **exactly 8** (one 8-word motif
   repetition) in **35 of 40** sites against a **5.1 %** base rate, `0x19`'s at
   lag **1** — and **9 of 38** distinct body images use **both**, so it is not a
   per-program assembler convention. Not refuted; unsupported.

3. **The `0 of 5832` blamed on the one-cell `Line`.** **Wrong diagnosis.** On a
   genuine two-address line the published-polarity window still scores **108 —
   the same 108 machines, set-identical.** It was a **polarity** artefact, not a
   memory artefact. `dsp/analysis/adjudication-round6.md` §3.5 is corrected.

## `LO_ACT_CAP_TA2` — the explicit deliverable

**It keeps shipping**, under the owner's 2026-07-27 decision.

- **DESTINATION = tempA: MEASURED.** ACTION `0x19` is followed by a word
  sourcing tempA in **74 of 89** distinct-image sites, base rate **16.0 %**,
  best-of-2000 ACTION-shuffled null **42.7 %**.
- ⚠ **NOT** the `401 of 402 / 99.8 %` of `adjudication-round7.md`. That
  denominator counts one word position once per **algorithm** sharing a
  byte-identical image — a **4.79×** replication. Use **74 of 89**.
- **SOURCE (`←bus` vs `←acc`): OPEN.** No experiment in any round has addressed
  it. The shipped label overstates what is known and the comment now says so.

## Re-measurement — live, `DSPCFG` On, `-str 32 -nothrottle`, visible video

| | round 6 | this build |
|---|---|---|
| words executing something / FULLY / addressing-only / nothing, of 285 | 199 / 107 / 92 / 86 | **199 / 107 / 92 / 86** |
| ★ frames COMPLETED | **0** | ★ **0** of 1 536 001 |
| frames that TRAPPED | 100.00 % | **100.00 %** |
| ★ operand-pointer closure residue, last frame | **+0** | ★ **+0** |
| residue min/max, entry pointer X | −1 / +116, `0xFF` 97.93 % | **identical** |
| input-stage audit | 0 MISMATCHED | **0 MISMATCHED** |
| descriptor-cursor residue | NOT TESTABLE | **still NOT TESTABLE** |
| distinct undecoded words / families | 443 / 133 | **443 / 133** |
| frame floor (216 w) | 38.0 % / 60.6 % | **38.0 % / 60.6 %** |
| reverb image (133 w) | 51.9 % / 75.9 % | **51.9 % / 75.9 %** |
| 38 body images (2974 w) | 41.5 % / 52.6 % | **41.5 % / 52.6 %** |

Frame counts differ by 348 (1 536 001 vs 1 536 349) because the scripted run
ends at a marginally different point. Every structural invariant is identical,
as a comment-only change requires.

## Safety

- `build.sh` log: **0** occurrences of `error:`; binary **74 405 928 bytes**,
  fresh mtime. (`build.sh` returns 0 even on failure — both checks done.)
- `tools/publish-binary.sh` run.
- `./kn7000 -validate kn5000` → exit **0**, **0 bytes** of output.
- `tools/upd6383d_diff.sh` → **MIRRORS AGREE — 3057/3057 words render
  identically in C++ and Python**, text *and* the three execution predicates.
- `dsp/verify.py` → **BYTE-MATCH OK**.
- `porth_read().set_constant(0x01)` **untouched**.

## ⚠ The audio check is VACUOUS and is not counted

`DSPCFG` Off and On captures (4 608 003 samples each) are byte-identical — **but
both are silent, non-zero count 0, peak 0.** Comparing two silent files is a
control that cannot fail, so it earns nothing. Cause is the test rig, not the
driver: the note-triggering Lua in the tree targets KN7000 ports and my KN5000
substitute did not register a press either. Anyone re-running this needs a
working KN5000 keybed programme first — and note that the DSP contributes **no**
audio regardless (0 frames complete), so `DSPCFG` Off vs On is identical by
construction until the delay-DRAM slots stop trapping.

## Highest-ranked blocker now

**ACTION `0x0D` (370 words) and `0x0E` (376) — 746 of 5894, 12.7 %.** They are
what close SINGLE DELAY's loops; until they decode, every forced-polarity ALU
cell is an absence of a search. Highest slot leverage, and **the host firmware
does not name them**, so it is a pure-corpus job.

Cheapest unblock, by contrast, is the **reverbs' cursor→C-RAM map** (the twelve
133-word reverbs resolve 0 of 33 coefficient words) — and there **the host
firmware does name the targets**, op-0x66 ER.LEVEL being already anchored to
C-RAM `0xA9..0xB0`.

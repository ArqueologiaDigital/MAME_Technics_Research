# Probes behind the 2026-09-23 KN7000 PR review

Twelve measurements taken while settling the last open questions on the MAME
pull request. Each answers one question and each carries the number it produced,
so the PR's claims can be re-derived rather than believed.

Where a count is quoted, a **null** was computed for it. That is not ceremony:
this project has twice published a figure that meant nothing because nobody
measured what a clean result looks like.

## The memory window

| probe | question | answer |
|---|---|---|
| `alias_census.py` | is `+0x40000000` a systematic second view of the same address space, or a coincidence? | Systematic. The firmware uses write-uncached / execute-cached three times: library written at `0x8C000000` and run at `0x4C000000`; KN2400 library written at `0x90120000`, run at `0x50120000`; vector thunk written at `0x90000000`, run at `0x50000000`. |

The decisive line is the thunk builder's own arithmetic: it computes the jump
displacement against `0x50000001`, which is correct at exactly one execution
address. The firmware itself asserts that `0x90000000` and `0x50000000` are the
same storage.

Consequences, all corrections to what the driver says today:

- `0x90000000` is **not** an LCD window. Across all five images the only values
  in `0x90000000-0x903FFFFF` a real instruction dereferences are five: the two
  thunks, a `0x5AA5` warm-boot flag at `+0x0E`, and a clear of work RAM's exact
  4 MiB extent from `+0x10`. The other 26 `0x90`-topped values — bit-identical
  across three unrelated firmwares — are loaded into data registers and passed
  as call arguments, i.e. ID constants, never dereferenced.
- The KN2400/KN2600-only aliasing is an **artefact**. The builder is
  byte-identical in all five firmwares. What differs is only where each
  firmware's handler happens to live.
- The `.share("vram")` entry allocates 128 MiB nothing reads, and swallows the
  picture flash at `0x97800000` that the driver's own comment says is left
  unmapped.

## The tone generator

| probe | question | answer |
|---|---|---|
| `tg_voice_shadow_classes.py` | do the discarded register classes `0x1000`-`0x2000` name the sample, so the voice-record reads could go? | see the PR notes — this is the one dependency that could not be removed |

## The SHARC multiplier

| probe | question | answer |
|---|---|---|
| `count_mult.py` | does the effects kernel ever read MV/MU? | **No** — 0 uses in 6499 PM words, against a positive control that finds `IF MS` ×20, `IF AV` ×7, `IF GE` ×40, `IF LT` ×34 |

So the flags are unobservable *for the KN7000*. The reason to emit them anyway
is other drivers: op bytes `0x70`/`0xb0`/`0xb2` were already live upstream with
the DRC emitting no multiplier flags at all against an interpreter that computed
them, so this closes a pre-existing divergence for Model 2/3, Hornet and Taito JC.

## Device naming

| probe | question | answer |
|---|---|---|
| `cpu_device_type_census.sh` | across `src/devices/cpu/*`, is a lone device named for a part or a family? | the precedent, and the whole argument |
| `ddt_token_vs_class.sh` | how often does a `DEFINE_DEVICE_TYPE` token differ from its class? | — |
| `mk_split.py` | cost in lines of the full abstract-base + concrete split | — |
| `mk_rename.py` | cost in lines of the cheap rename only | — |

## Comment density

| probe | question | answer |
|---|---|---|
| `cdens.py` | comment-line density per header | the measurement the reviewer used on #15919 and #16204 |
| `null.py` | what does that figure look like on comparable merged code? | the null, without which the density number means nothing |

**The null, measured with `cdens.py` itself, 2026-09-23.** Every
`src/devices/cpu/*/*.h` of 150+ lines in `upstream/master`, n=238, column
`pct_nobanner` (comment-only lines as a fraction of non-blank lines, excluding
the mandatory licence banner):

| median | p75 | p90 | p95 | p99 | max |
|---|---|---|---|---|---|
| 6.1% | 12.4% | 18.3% | 24.3% | 46.0% | 73.8% |

`mn10300.h` sat at **27.6%** — the 95th percentile — and is now **19.7%**, the
92nd. Reproduce with:

```sh
git archive upstream/master src/devices/cpu | tar -x -C <scratch>
python3 cdens.py <scratch>/src/devices/cpu/*/*.h    # then filter to >=150 lines
```

⚠ An earlier pass in the same session quoted median 6.3 / p75 10.3 / p90 14.4 /
p95 19.3 and put the header at 17.6%. Those came from a different definition of
a comment line (every line whose first non-space characters are `//`, `/*` or
`*`, over ALL lines including blanks) and are not comparable to the table above.
The conclusion — the file was in the extreme tail and no longer is — holds under
both. The figures to quote are `cdens.py`'s, because that is the probe that is
committed.

### The driver's own density, and why it is not trimmed

The header measurement above is for `src/devices/cpu/*/*.h`. The driver belongs to a
different population. Measured the same way, `cdens.py` over every
`src/mame/*/*.cpp` of 1000+ lines in `upstream/master`, **n=857**:

| | median | p75 | p90 | p95 | p99 | max |
|---|---|---|---|---|---|---|
| `pct_all` | 19.8% | 27.7% | 36.1% | 42.7% | 56.8% | 82.4% |
| `pct_nobanner` | 13.1% | 19.6% | 26.2% | 32.4% | 46.6% | 65.2% |

`kn7000.cpp` is at **33.7% / 31.5%** — the 86th percentile including the licence
banner, the **94th** excluding it. High, and it is the exact metric a maintainer
raised on #15919 and #16204.

`comment_run_profile.py` answers what to do about it, and the answer is nothing.
The remedy that worked for `mn10300.h` was relocating multi-page peripheral
documentation beside the handlers it describes. This file has no such blocks:

```
423 comment-only lines in 177 runs
  runs of 1-3 lines   159 runs = 326 lines = 77% of all comment lines
  runs of 4-7 lines    17 runs =  83 lines
  runs of 8+           1 run   =  14 lines
```

One block of 14 lines, one of 7. The density is one to three lines of explanation
next to the code they explain, throughout — which is what annotating an
instrument with no datasheet looks like. Reaching the median would mean deleting
roughly 230 short comments: the blanket trim that, earlier in this project,
removed already-merged upstream documentation and left 48 sentences cut off
mid-clause. Measured and left alone, deliberately.

## Pre-submission checks upstream will run anyway

Two that found real things, and two nulls, all 2026-09-23.

**`srcclean`.** MAME ships the normaliser as `src/tools/srcclean.cpp` and the
maintainers run it; a PR with unnormalised whitespace collects a comment. Run it
over every file the branch touches, on COPIES, and diff:

```sh
for f in $(git diff --name-only upstream/master..<branch>); do
    mkdir -p "$SCRATCH/$(dirname $f)"; git show <branch>:"$f" > "$SCRATCH/$f"
done
find "$SCRATCH" -type f -print0 | xargs -0 -n 20 ./srcclean
```

It found **7 files**: six with comment-continuation alignment in spaces where
MAME uses tabs (`kn6000_cpanel.cpp`, `kn6000_tonegen.cpp`, `kn7000_cpanel.cpp`,
`kn7000_tonegen.cpp`, `kn_tonegen.h`, `mn10300.cpp`) and the layout, where three
tabs needed expanding to spaces because MAME's XML convention is the opposite of
its C++ one. Applied; a second pass reports nothing, which is the convergence
check.

⚠ I missed `mn10300.cpp` on the first pass by piping srcclean through `head -20`
— two `xargs` batches, and the truncation hid the second. Don't truncate the
output of a check.

**A clang build.** `-Wunused-private-field` is a hard error under clang and GCC
never emits it; MAME builds under both.

```sh
OVERRIDE_CC=clang OVERRIDE_CXX=clang++ OVERRIDE_LD=clang++ \
    make SUBTARGET=kn SOURCES=<driver> REGENIE=1 -j8
```

It uses its own `build/linux_clang` tree, so it does not disturb the GCC build.

**Null: layout licence headers.** Of 2025 `.lay` files in `upstream/master`,
1399 carry `license:` and only **232** carry `copyright-holders:`. Of the 1376
CC0-licensed ones, 211 (15%) also name a copyright holder — so a CC0 layout
without one is the majority convention, not an omission.

```sh
git archive upstream/master src/mame/layout | tar -x -C <scratch>
grep -rl "license:" <scratch> --include="*.lay" | wc -l
grep -rl "copyright-holders:" <scratch> --include="*.lay" | wc -l
```

**Null: TODO markers.** The branch adds 15. `upstream/master` carries 1810 across
326 files in `src/devices/cpu` alone, so the count is unremarkable — what matters
is whether any is false. Two were, naming work the same file had since gained;
both corrected.

## ROM-definition nulls, and the three changes they prevented

A second-pass adversarial review filed three findings against the KN7000 ROM
definitions. Its own subagent then measured whether each shape is unusual in
MAME. All three are ordinary, so nothing was changed:

| probe | question | null over upstream `src/mame` |
|---|---|---|
| `rom_name_split_across_regions.py` | several files sharing one chip's `.icNN` suffix in a set | **1275 sets** |
| `rom_region_erase_no_entries.py` | `ROM_REGION` with an ERASE flag and no entries | **2447 of 108045** (2.3%) |
| `rom_file_in_multiple_regions.py` | one file loaded into more than one region in a set | **420 sets** |

```sh
git archive upstream/master src/mame | tar -x -C <scratch>
cd <scratch> && python3 <probe>.py
```

So `kn7000_program_even.ic17` and `kn7000_table_even.ic17` being two files for one
32 Mbit device is how MAME routinely represents a part whose halves serve
different buses, and kn2400's empty `ROMREGION_ERASEFF table_data` is one of
2447 such regions.

These were written by a review subagent and kept because they **changed what I
did** — without them all three would have been "fixed" into non-conformance.

## Include order

| probe | question | answer |
|---|---|---|
| `incorder.py` | adherence to MAME's documented include-group order across `src/mame` | — |
| `inc_lh_stdlib.py` | where `.lh` and stdlib headers actually sit | two more nulls |
| `incsort.py` | within a group, are includes sorted? | companion null |

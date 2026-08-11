# PR draft — kn5000: correct the IC14 ROM, and make the Feature Demo run

★ **2026-08-11: this PR grew from 1 commit to 3, on measurement.** The ROM fix alone revives the
accompaniment transport but does not make the Feature Demo play. Bisected on the branch itself,
three changes are needed and each does a distinct job:

| commit | what it fixes | measured effect |
|---|---|---|
| `40ce9f1` IC14 dump | style data read from the wrong 512 KiB block | transport `0x0420` 0C (terminal STOP) -> **04**, watchdog `0x32ed` 20 -> **00** |
| `ab6f4fa` IC21 NVRAM | backup SRAM invalid at every boot, so the firmware skips the sub-CPU payload | AccPlayMode `0x22FC` 00 -> **03**: the demo actually starts |
| `df00b73` tmp94c241 timer | INTTR5, the sequencer clock, never fires | sub-tick `0x0417` frozen at 00 -> **cycling continuously** (49, 1A, 4A, 1B, 4B, 19 over 60 s) |

**Result: the Feature Demo runs.** Screen snapshots every 5 s: **7 distinct of 9**, against 3 of 17
(a two-state blink) with the ROM fix alone. No tone generator is involved — there is no sound
upstream yet, and none is needed for this.

⚠ Each ingredient was verified necessary, not merely sufficient: the timer fix *without* the NVRAM
makes things strictly worse (every signal flat at 00), and the NVRAM without the timer starts the
demo but never clocks it.

⚠ Unexplained residual: SSF state `0x251D8` stays 00 and `0x8D38` reaches E4 rather than the E1 our
notes call "playing", yet the picture demonstrably advances. Either those addresses differ upstream
or the slides advance by another path. Not chased; recorded so nobody claims full understanding.

⚠ The NVRAM initialiser reads factory defaults from **program ROM offset 0x0A0150**, established
on the v10 image. Whether that offset holds for the v5-v9 BIOS options is untested.

---

## Original single-commit draft (the ROM fix)


**Branch:** `kn5000_ic14_transposed_dump` (worktree `~/compartilhado/mame-pr-ic14`, off
`upstream/master` @ `a4f77431604`)
**Commit:** `40ce9f12b5e`, authored as Felipe
**Diff:** 2 lines in `src/mame/matsushita/kn5000.cpp`
**Corrected ROM set for testing:** `~/compartilhado/kn5000_corrected_roms/`

---

## Suggested PR description

### kn5000: correct the IC14 rhythm data ROM dump

The KN5000's rhythm data ROM (IC14, `QSIGX3C23011`, 32 Mbit mask ROM) is currently in MAME with a
dump that was read with **address lines A19 and A21 transposed**. The chip's data is intact in
that file — only the order of its eight 512 KiB blocks is wrong — so this is a re-ordering of the
existing dump, not a different read of different silicon.

| | size | CRC32 | SHA1 |
|---|---|---|---|
| current in MAME | 4,194,304 | `76d11a5e` | `e4b572d318c9fe7ba00e5b44ea783e89da9c68bd` |
| corrected | 4,194,304 | `aa4917ce` | `fef7f1927935d8fdada2afbdbfac29aac56e1c3c` |

Swapping A19 and A21 permutes the block index by exchanging its bits 0 and 2:
`0,1,2,3,4,5,6,7 → 0,4,2,6,1,5,3,7` (an involution). Verified mechanically: the multiset of
512 KiB block hashes is identical before and after, so **no byte was altered**.

#### Why this is the dumping rig and not the board

This matters, because board-level address scrambling should be modelled in the driver, while a
dumping error should be corrected in the file. The service manual settles it.

Page 32 ("CPU SECTION (A) P.C. Diagram") shows IC14 wired straight:

```
AD20 <- pin 44 <- net A21
AD19 <- pin 43 <- net A20
AD18 <- pin  2 <- net A19
AD17 <- pin  3 <- net A18
AD16 <- pin 34 <- net A17
```

i.e. AD*k* ← net A(*k*+1) throughout, exactly like IC19 next to it. There is no transposition on
the PCB. Note also that AD18 and AD20 are pins 2 and 44 — adjacent across the NC at pin 1, which is
the neighbourhood where a socket adapter configured for a different 44-pin part mis-maps.

#### How the correction was verified

Independently of any reference image, using only the ROM's own internal structure: every style
record's lane pointers must land 6 bytes past a cell header `80 FF FF FF FF 87`.

| | lane pointers landing correctly |
|---|---|
| as currently dumped | 3,439 of 9,696 |
| corrected | **9,696 of 9,696** |

#### User-visible effect

With the current dump the accompaniment engine reads style data from the wrong 512 KiB block, hits
an invalid opcode, and the bad-opcode watchdog stops the transport. Roughly **two thirds of the
factory rhythms are silent**, and the built-in Feature Demo stops early. With the corrected dump
the transport runs.

(The KN5000 has no sound in MAME yet — the tone generator is not emulated — so the audible part of
this is not yet observable upstream. The transport, the style engine and the Feature Demo's
progress are.)

---

## Notes for our own review, not for the PR

### Provenance — the one weak point, and the fix

The corrected file is derived from the existing dump by permuting blocks; it is **not** a second
physical read. The derivation is sound and the verification is strong, but a maintainer is entitled
to ask who has read these bytes off the chip in this order, and the answer today is nobody.

**Recommended before submitting:** re-dump IC14 on Felipe's unit with correct wiring and confirm it
produces `aa4917ce`. That converts the reconstruction into first-hand provenance, removes the
objection entirely, and independently validates the analysis. If it does not match, we learn
something important instead of shipping it.

If the PR goes out before that, say plainly in the description that the file was derived by
correcting the transposition and state the verification — do not let it read as a fresh dump.

### On `BAD_DUMP`

Not used, deliberately. `BAD_DUMP` marks data known or suspected to be incorrect or incomplete;
this data is neither — it is the chip's content in the chip's order, recovered from a read whose
addressing was wrong. Flagging it would misdescribe it.

(An earlier position in our notes argued for keeping `BAD_DUMP` and de-scrambling at load time with
`ROM_CONTINUE`. That is the wrong shape for a dumping-rig error and it leaves the ROM set wrong for
everyone; it is kept only as a fallback if a maintainer insists on it.)

### Fallback if the hash change is rejected

Our overlay's form: keep the original file and hashes, mark `BAD_DUMP`, and de-scramble at load:

```
ROM_LOAD("kn5000_rhythm_data_rom.ic14", 0x000000, 0x080000, BAD_DUMP CRC(76d11a5e) SHA1(e4b572d3...))
ROM_CONTINUE(                           0x200000, 0x080000)
ROM_CONTINUE(                           0x100000, 0x080000)
ROM_CONTINUE(                           0x300000, 0x080000)
ROM_CONTINUE(                           0x080000, 0x080000)
ROM_CONTINUE(                           0x280000, 0x080000)
ROM_CONTINUE(                           0x180000, 0x080000)
ROM_CONTINUE(                           0x380000, 0x080000)
```

Honest, but it fixes the emulation without fixing the ROM set, and eight lines say what one hash
should.

### Testing

The branch needs its own build — the worktree starts empty, and no existing binary carries the new
hash (a binary built before this change will reject the corrected file as a bad ROM, and vice
versa).

```
cd ~/compartilhado/mame-pr-ic14
./build_kn5000.sh                     # SUBTARGET=kn5000, ccache shared across worktrees
./kn5000 kn5000 -rompath ~/compartilhado/kn5000_corrected_roms
```

⚠ The main tree's `build_mame.sh` **cannot** be used on an upstream branch: its curated `SOURCES`
list names fork-only drivers (`src/mame/itautec/i7000.cpp` and others) that do not exist on
`upstream/master`, and genie aborts before compiling anything. `build_kn5000.sh` in the worktree
builds the single driver instead, and passes `USE_QTDEBUG=0` because this host has no Qt `moc`.
Both failures report zero `error:` lines, so grepping the log for `error:` is not sufficient here
— check the exit status and that a binary actually appeared.

The ROM set there is the corrected IC14 plus symlinks to the rest of Felipe's originals.

Note that the *behaviour* this PR restores is already observable in our overlay build, which
reaches the same memory contents by de-scrambling at load with `ROM_CONTINUE`. Building the branch
tests the PR's own form: that MAME accepts the corrected file under the new hash and the driver
loads it flat.

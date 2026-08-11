# PR draft — kn5000: four fixes, and the Feature Presentation demo runs

**SUBMITTED: https://github.com/mamedev/mame/pull/15878** — open, not merged as of 2026-08-11.

**Branch:** `kn5000_make_feature_presentation_demo_run` (worktree `~/compartilhado/mame-pr-ic14`),
off `upstream/master` @ `a4f77431604`. Four commits, 37 insertions, two files.
**ROM set for testing:** `~/compartilhado/kn5000_corrected_roms/`

---

## The PR message

### kn5000: get the Feature Presentation demo running

Four small independent fixes. Together they make the instrument's built-in Feature Presentation
demo run for the first time. It runs **silently** — the tone generator is not emulated yet.

**kn5000: correct the IC14 rhythm data ROM dump.** The dump in MAME was read with address lines
A19 and A21 transposed, which permutes the chip's eight 512 KiB blocks. No byte differs, only
their order. The service manual (page 32) shows IC14 wired straight, so the transposition was in
the dumping rig rather than on the board. Verified from the ROM's own structure: every style
record's lane pointers must land 6 bytes past a cell header `80 FF FF FF FF 87` — 3,439 of 9,696
as dumped, 9,696 of 9,696 corrected. Left uncorrected, the bad-opcode watchdog stops the
accompaniment transport and roughly two thirds of the factory rhythms are silent.
CRC32 `76d11a5e` → `aa4917ce`, SHA1 `e4b572d3…` → `fef7f192…`.

**tmp94c241: fix 16-bit timer interrupt generation and flip-flop gating.** A TREG_HIGH match set
the lower interrupt flag instead of the upper one, and the flip-flop control bits gated the match
itself rather than just the flip-flop toggle. INTTR5 — the KN5000's sequencer clock — therefore
never fired.

**kn5000: model the IC21 backup SRAM as NVRAM.** It is battery-backed; declared as plain RAM it
was invalid at every boot, so the firmware failed its checksum check and skipped the sub-CPU
payload transfer.

**tmp94c241: do not re-assert INT0 while micro-DMA owns it.** The level-detect re-assertion should
apply only to the ISR-driven path: when a micro-DMA channel is armed on the INT0 start vector the
DMA engine consumes each request and manages the flag itself, so re-asserting made it read stale
latch data.

A partial tone-generator implementation already exists and will follow in a later PR — it is a lot
of code and is better reviewed on its own.

---

## Notes for us, not for the PR

### Measured effect of each commit

| commit | signal |
|---|---|
| `aa74557` IC14 dump | transport `0x0420` 0C (terminal STOP) → **04**; watchdog `0x32ed` 20 → **00** |
| `4444ec5` 16-bit timer | sub-tick `0x0417` frozen at 00 → **cycling** (49, 1A, 4A, 1B, 4B, 19 over 60 s) |
| `8eab8d0` IC21 NVRAM | AccPlayMode `0x22FC` 00 → **03** — the demo starts |
| `3c118c1` INT0 guard | no regression; the panel-corruption claim is **unverified**, see Open |

Demo screen: **7 distinct snapshots of 9**, against 3 of 17 (a two-state blink) with the ROM fix
alone. `-validate` clean, `-verifyroms` OK. Each ingredient was shown *necessary*, not merely
present.

The NVRAM is a bare declaration. A version seeding IC21 with factory defaults from program-ROM
offset `0x0A0150` plus a synthesised checksum measured **identical in effect** — the firmware
initialises the SRAM itself, so only persistence was ever missing. Dropped, which also removes a
dependency on a v10-only ROM offset.

### Provenance of the corrected ROM — the one weak point

The corrected file is derived by permuting blocks; it is **not** a second physical read. Before
submitting, re-dump IC14 and confirm it produces `aa4917ce`. That turns a reconstruction into
first-hand provenance and independently validates the analysis. If the PR goes out first, say
plainly that the file was derived.

`BAD_DUMP` deliberately not used: the data is the chip's content in the chip's order, recovered
from a read whose *addressing* was wrong. Fallback if a maintainer insists — keep the old file and
hashes, mark `BAD_DUMP`, and de-scramble at load with eight `ROM_CONTINUE` lines (the form our
overlay used).

### Do not add these

Both were ported, built and measured on this branch, and both regress it:

- **the timer fix without the NVRAM commit** — every signal flat at 00, worse than the ROM fix alone;
- **`3fd44f3` + `e6b4cf7`** (drop the re-assertion entirely, add `clear_int0_level()` and call it
  from the latch reads) — **kills the running demo**, reproduced twice. Its root cause is sound,
  but our version leans on a latch path upstream does not have (patches 26-28, MSTAT/SSTAT
  tracking, misframe detection). The **guarded** form now in this PR is the 2026-02-17 known-good
  behaviour and is self-contained; the *removal* form is not.

### Open

- Felipe reports wrong LEDs/buttons and `Sound Name Error` on this branch after minutes of use.
  Not reproduced automatically; the INT0 guard is aimed at it but is unproven. Next lead: February
  `f8cd34a8` was measurably good on the `b3` repro — diff it against upstream.
- SSF state `0x251D8` stays 00 and `0x8D38` reaches E4 rather than the E1 our notes call
  "playing", yet the picture advances. Unexplained.

### Building this branch

```
cd ~/compartilhado/mame-pr-ic14
./build_kn5000.sh                 # SUBTARGET=kn5000, USE_QTDEBUG=0, shared ccache
./kn5000 kn5000 -rompath ~/compartilhado/kn5000_corrected_roms
```

⚠ The main tree's `build_mame.sh` cannot be used on an upstream branch — its `SOURCES` list names
fork-only drivers absent from `upstream/master` and genie aborts. ⚠ Both that failure and a missing
Qt `moc` exit non-zero with **zero `error:` lines**, so grepping for `error:` is not enough; check
the exit status and that a binary appeared.

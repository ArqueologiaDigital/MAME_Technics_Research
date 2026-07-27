# APPLIED — round 5: the delay-DRAM direction, and it ships REVERSED

**Source:** `kn5000-roms-disasm/dsp/analysis/adjudication-round5.md`
(tool `dsp/tools/adjudicate5.py`). Date **2026-07-27**.

**What changed:** the two disassembler mirrors, and only them.
**What did NOT change:** the device. No file under
`src/devices/cpu/upd6383/upd6383.cpp` was touched, no executable predicate
(`decoded()`, `addressing_only()`, `has_addressing()`, `is_dram()`) was touched,
and **the 42 delay-DRAM slots still trap**.

---

## 1. The finding, in one paragraph

The three concurrent round-5 passes disagreed about the delay-DRAM. Target 1
(`dram-matching.md`) forced the cell↔word map at phase `δ = −1` and read
`addr8 0x60` as the READ; Target 2 (`dram-direction.md`) forced `addr8` bit 6 as
the direction *field*, found its own oracle perfect only at `δ = 0`, and left the
polarity open on a 2–1 vote. **Those were not two disputes.** Under a cyclic map
a shift of δ by one swaps which member of an alternating read/write pair takes
which word, so **the phase and the polarity are one parameter** — and Target 1
scanned δ with a polarity pinned, which is method rule 2.

Settling the phase with three oracles that *cannot see a polarity* gives
**δ = 0, the identity map**, uniquely among thirteen phases. Two independent
structural arguments then fix the polarity, and it is the reverse of what this
repository shipped:

```
   addr8 bit 6 == 0   (addr8 0x20 / 0x30)  ->  delay-DRAM READ
   addr8 bit 6 == 1   (addr8 0x60)         ->  delay-DRAM WRITE
```

* **MULTI TAP DELAY, counting.** Four `op-0x67` taps share ONE line base
  (`BASE24 = 2` ×4 ⇒ base address 0). A multi-tap delay is one write and N
  reads. The four taps carry `addr8 0x20/0x30`; the shared base carries `0x60`.
* **Read-before-write at a shared boundary, host-free.** `A[k]` is the read end
  of ladder segment `k` and the write end of segment `k+1`; both hit one physical
  word in one frame, so the read must take the aged content first. The earlier
  access of **133 of 133** opposite-bit pairs carries bit 6 = 0.

`r1-allpass-motif.md` F1 said the opposite. It is **falsified as stated, not
outvoted**: its acceptance test 2 (*"DR at exit == N — the fresh read has
landed"*) and F6 (`land ∈ [2,5]`) bound the DRAM read latency to inside one
8-word repetition, and the descriptor addresses need **twenty** words.
`read_slot = 4` was never in the searched option set.

★ And the sentence this file used to print — *"DIRECTION UNKNOWN: `addr8` does
NOT select it — MULTI TAP DELAY's tap READS land on `880.1.20.2C7` and its line
WRITE on `880.1.60.000` (R3 §6.3 falsifies the old `addr8` rule)"* — was
**carrying the correct measurement as a refutation of the correct hypothesis**.
R3 §6.3 refutes only the old *polarity*. Its MULTI TAP observation is now the
rule.

---

## 2. The diff

`kn5000-roms-disasm/dsp/tools/dsp_disasm.py`

```
-  DRAM_FORCED = {(0x60, 0x2D4): "READ", (0x20, 0x655): "WRITE"}
+  def dram_dir(w):
+      ad = addr8(w)
+      if ad in (0x20, 0x30): return "READ"
+      if ad == 0x60:         return "WRITE"
+      return None                 # outside the validated set -- keeps trapping
```

`src/devices/cpu/upd6383/upd6383d.h` — the same as a `static constexpr char
dram_dir(u64)`, plus a DIRECTION paragraph on `is_dram()`.

`src/devices/cpu/upd6383/upd6383d.cpp` — the annotation rewritten with the full
provenance **including the r1 conflict**, and the false
*"DIRECTION UNKNOWN / addr8 does NOT select it"* text removed.

**SCOPE, deliberately narrow.** The rule is applied only over
`addr8 ∈ {0x20, 0x30, 0x60}` — the values it was validated on. `C40.1.80.000`
(`addr8 0x80`, 48 of the 829 aligned descriptor cells) is the word Target 2
**proved** no instruction rule can reach, and it keeps trapping. Method rule 6.

---

## 3. RE-MEASUREMENT

Live, cold boot, fresh `nvram` per run, identical `cfg`, identical 32 s keybed
programme (three chords at 20.0 / 23.5 / 27.0 s), `DSPCFG` Off and On, before and
after. `-str 32`, `-nothrottle`, visible video.

REPRODUCE:

```bash
scratch/run.sh <binary> <tag> <cfgdir>     # -skip_gameinfo -nothrottle -log -str 32
                                          # -autoboot_script audio.lua -wavwrite <tag>.wav
grep -A34 'FRAME REPORT' <tag>.error.log
```

| | before | after |
|---|---|---|
| frames run | 1 536 349 | **1 536 349** |
| words executing **something** of 285 | 199 | **199** |
| words executing **FULLY** | 107 | **107** |
| words executing **addressing only** | 92 | **92** |
| words executing **nothing** | 86 | **86** |
| ★ **frames COMPLETED** | **0** of 1 536 349 | ★ **0** of 1 536 349 |
| frames that TRAPPED | 1 536 349 (100.00 %) | **1 536 349 (100.00 %)** |
| ended on wait word / CAP / OVERRUN | 1 299 228 / 210 241 / 26 880 | **identical** |
| ★ **operand-pointer closure residue, last frame** | **+0** | ★ **+0** |
| complete frames that CLOSED | 1 273 307 of 1 299 228 | **identical** |
| residue min / max, entry pointer X | −1 / +116, `0xFF` 97.93 % | **identical** |
| input-stage audit | 1 309 788 both-reads, **0 MISMATCHED** | **identical** |
| ★ frames carrying a NON-ZERO sample into the chip | **438 663**, peak `0x542500` | **identical** |
| descriptor-cursor residue | NOT TESTABLE (its 42 consumers trap) | **still NOT TESTABLE** |
| distinct undecoded words | 443 | **443** |
| frame floor tier 1 | 82 of 216, 38.0 % | **82, 38.0 %** |
| frame floor tier 1 + 2 | 60.6 % | **60.6 %** |
| 38 body images, 2974 words | 1234 tier 1, 41.5 % / 52.6 % | **identical** |
| ★ frame-floor tier-2 `DETERMINED` | 18 | ★ **32** |
| ★ frame-floor tier-2 `MEASURED` | 20 | ★ **6** |
| frame-floor tier-2 `PARTIAL` | 11 | **11** |

The two FRAME REPORTs are **identical line for line**, and this programme really
does drive the chip: **438 663 frames carried a non-zero sample** into the input
stage (peak `0x542500`) against **zero** in the first attempt — see §4.

**The only number that moves is the DETERMINED/MEASURED split inside tier 2, and
that is the honest shape of the result**: fourteen more frame-floor words now
have a determined *operation* (read or write) while their *operand encoding* —
which cell, and where the data goes — is still open, so they stay on the
worklist. **Nothing was promoted into `decoded()`.**

★ **The descriptor-cursor residue is STILL not testable**, and Target 1's claim
that its own result made it testable does not survive: `|R| ≥ 2` was derived from
`δ = −1`, and `δ = −1` is falsified. What replaces it: under `δ = 0` a
**pre-increment** cursor loaded with `0x25` (I-RAM 44, `801.0.25.825`) delivers
cell `0x26` to the unit-0 body's first consumer exactly — which is why Target 1's
item I cannot choose the phase either (it is degenerate with post-increment at
`δ = −1`).

---

## 4. SAFETY

* Build clean — **0** `error:`, **0** `Error [0-9]`; binary **74 405 928** bytes,
  mtime advanced; `tools/publish-binary.sh` run.
* `-validate kn5000` — **exit 0, zero bytes of output**.
* `dsp/verify.py` — **BYTE-MATCH OK**; 39 `.dsm` listings regenerated
  (`make dsp`) and the raw word column round-trips to the ROM exactly.
* `tools/upd6383d_diff.sh` — **MIRRORS AGREE, 3057/3057**, text *and* the three
  execution predicates D/A/K.
* ★ **Audio bit-identical, on a capture that DEMONSTRABLY CAN FAIL.**
  All four WAVs — `DSPCFG` Off and On, before and after — are
  `f57115a26a55fcfed68fb6eab0769ea8`: **1 536 001 frames, 876 696 non-zero
  samples, peak 21 541.**
  ★ **AND THE CONTROL IS SHOWN FAILING, because my first attempt at it was
  worthless.** The first capture programme pressed each key with a single
  `set_value(1)` at machine-frame 600 and produced **peak 0, zero non-zero
  samples in 1 440 001 frames** — a capture that cannot fail, which is exactly
  the defect method rule 1 exists for. Two causes, both already written down in
  `play_c4.lua` and neither read first: **a keybed field must be RE-ASSERTED
  every tick** or the port is cleared between scans, and the machine needs
  **~20 emulated seconds** before a key sounds. The rebuilt programme drives real
  audio, and the silent one is reported here rather than deleted.
* The D/A/K predicates being identical across all 3057 corpus words is the
  constructive half of the same statement: no word's execution changed, so no
  sample can. `DSPCFG` Off and On produce the same WAV either way, because a
  frame that traps contributes exactly zero — measured, not argued.

---

## 5. The comb prediction — and why it still cannot be tested

The round-5 brief asks for an impulse test *if the delay line executes*. It does
not. What the brief's own constants say must be corrected first (method rule 8):

```
   ROOM REVERB 1   pre-delay 800 samples (18.14 ms)
                   ladder    83 172 356 513 739 240 119 247 428 616 360
                   TOTAL     3873 samples = 87.82 ms
   ==> an impulse test needs a few times 4673 samples, NOT 4 x 8905 = 35620.
   `long head 8905' is an i+1 artefact of a pairing already retracted.
```

★ **And the topology is not decided by the addresses.** A tightly-packed
*parallel comb bank* has exactly the same shared-boundary address structure as a
*series all-pass chain*, so *"the reverb core is a comb network"* is neither
confirmed nor refuted here. The polarity argument in §1 does **not** depend on
the topology — it needs only that two accesses hit one physical word.

---

## 6. What the next pass should pick up, ranked

1. **The bounds question, and the host firmware already names it.** Cells holding
   `0`, `32767`, `32768` and the per-unit ceiling are handed to consumers exactly
   like addresses and produce fake "lines" (SINGLE DELAY's `897`, PLATE REVERB's
   `32767`). They are written through the same tag-0x4C path, so
   `host_side.py regmap` can be asked **which opcode writes them and what the UI
   calls them**. If a bound cell has no UI name while every address cell has one,
   the split falls out for free. This is the same lever that solved this round.
2. **Re-run `r1_allpass_solve.py` with `land ∈ [6,24]`, `read_slot` free, and the
   descriptor addresses supplied as constraints.** §1 makes it decisive rather
   than confirmatory, and it is what would give the delay-DRAM words a
   **datapath** — the last thing between them and execution.
3. **The unit-1 cursor reload.** Unit 0's first consumer takes cell `0x26`, which
   a pre-increment cursor loaded with `0x25` delivers. Unit 1 needs `0x00` and
   I-RAM 52 loads the same `0x25`.
4. **Model M5 — two cursors, one per direction** — is the one alternative to the
   identity map this round did *not* refute, because the corpus's strict
   read/write alternation makes M5 and M2 indistinguishable. Break it on an
   algorithm with unequal read and write counts.
5. `kn5000.cpp`'s `porth_read().set_constant(0x01)` still makes the DSP READY
   line unfailable (Target 3's finding, untouched here): the firmware has an
   8000-poll timeout and two error paths the emulator cannot exercise.

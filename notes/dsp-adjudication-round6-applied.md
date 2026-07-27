# APPLIED — round 6: three FORCED assertions withdrawn, and nothing else

**Source:** `kn5000-roms-disasm/dsp/analysis/adjudication-round6.md`
(tool `dsp/tools/adjudicate6.py`). Date **2026-07-27**.

**What changed:** three **labels**, in the device and in both disassembler
mirrors.
**What did NOT change:** anything executable. No predicate (`decoded()`,
`addressing_only()`, `has_addressing()`, `is_dram()`), no ALU semantic, no
enum value. **The 42 delay-DRAM slots still trap and 0 of 1 536 349 frames
complete.**

★ **The rebuilt binary is BYTE-IDENTICAL to the previously published one** —
`md5 965976f50bbfa11299d1449caca7d336` — after a full recompile of
`upd6383.cpp` and a relink, although the edit adds about sixty lines. That is
the inertness proof; the audio capture below is the second one.

---

## 1. The finding, in one paragraph

`adjudication-round5` FORCED the delay-DRAM direction and **reversed** what the
tree shipped (`addr8 0x20/0x30 → READ`, `0x60 → WRITE`). Its applied note says
*"no executable semantic changed"*, which is true of the edit it made — it
touched only the two disassembler annotations. **Nobody audited the semantics
that had already shipped.** Round 6 did:

```python
# dsp/tools/action00_discriminate.py  sd_run()     -- and
# dsp/tools/acc_adjudicate.py         sd_run()     -- verbatim, both:
        def dram(w, bus, s):
            if (DIS.addr8(w) & 0xf0) == 0x20:
                ln.write(bus)                       # addr8 0x20 = WRITE
            else:
                s.dr = int(ln.read()) & MASK24      # addr8 0x60 = READ
```

**The delay line in every SINGLE DELAY ALU search is wired backwards**, and
SINGLE DELAY is the only published ALU context that touches the delay port: of
the 94 corpus `ACTION 0x19` sites, 92 sit in images carrying delay-DRAM words
and the only DRAM-free one is algo 88, which `second-dsp-and-ready.md` showed is
an **IC310 (MN19413)** stream and not an IC311 program at all. It is also the
only context that constrains `ACTION 0x19` — the biquad carries no `0x19` word
and the LFO section does not enumerate it.

Re-run with the polarity **enumerated instead of fixed** — same space (5832
machines), same reference `v[n] = x[n] + fb·v[n−D]`, same tolerance, same seeds:

```
   polarity = published (addr8 0x20 = WRITE) : 108 of 5832   <- reproduces the published number
       act19  FORCED  tA<-bus x108
       src00  FORCED  mem     x108
   polarity = round-5 FORCED                  :   0 of 5832
   polarity = round-5 FORCED, dr carried      :   0 of 5832
```

★ **And the zero is a harness artefact too, demonstrated rather than argued.**
The harness's `Line` reads and writes ONE cell and advances once per frame, so
it silently requires READ-before-WRITE in program order. Corrected, SINGLE
DELAY's `w5` (`0x60`) **writes** and `w9` (`0x20`) **reads**:

```
   published polarity : port order per frame RW   READ returns 0,0,0,0,0        (a real D-frame delay)
   FORCED   polarity  : port order per frame WR   READ returns 1000,1001,1002…  (the value written THIS frame)
```

**Both numbers are void. The determination is UNFORCED, not refuted.**

---

## 2. The diff

`src/devices/cpu/upd6383/upd6383d.h`

* `LO_ACT_CAP_TA2` (0x19): *"FORCED 72/72 by SINGLE DELAY (108/108 in the wider
  space)"* and the *"★★ IT SURVIVED A CHALLENGE … AND THE CHALLENGE IS
  WITHDRAWN"* narrative are replaced by the provenance above, ending in **the
  semantic is retained, is CONSISTENT, and must not be cited as FORCED**. The
  `schroeder-topology.md` §0-C conditional challenge is recorded as **RE-OPENED**
  — its withdrawal in `blocking-read.md` item D had no support other than the
  blocking read.
* `LO_ACT_ACC_BUS` (0x00): the ADDER's *"FORCED"* keeps its label and gains the
  caveat that it is a **reconciliation of the LFO with SINGLE DELAY** and that
  SINGLE DELAY's leg is void — retained because the LFO leg is untouched and the
  adder is the plurality (27 of 33) even in the reversed model, but no longer a
  two-context forcing.

`src/devices/cpu/upd6383/upd6383.cpp`

* the `LO_ACT_CAP_TA2` case in `exec_alu()`: same withdrawal, pointing at
  `upd6383d.h`.
* the `LO_SRC_TB` `tbsh` comment: its two **blocking-read** rows (`3206/3206`,
  `2310/2310`) are marked **void**; the `112/112` PUBLISHED row survives, so the
  biquad-vs-reverb tension it records is unchanged in kind and narrower in
  width.

`kn5000-roms-disasm/dsp/tools/dsp_disasm.py` — the mirror of both.

⚠ **THE OPEN DECISION.** Method rule 6 says only FORCED results reach the
device. `LO_ACT_CAP_TA2` shipped as FORCED and its forcing is gone. It was
**not** withdrawn, because the only instrument that could withdraw it is a
harness that provably cannot model the corrected machine — reverting on that
authority is the method-rule-1 defect pointing the other way, and losing ~100
executing words to an artefact is not the conservative act. **This is a live
exposure and it needs either the rank-1 experiment (§5) or an explicit
decision.**

---

## 3. RE-MEASUREMENT

Live, cold boot, fresh `nvram` per run, identical `cfg`, identical 32 s keybed
programme (three chords at 20.0 / 23.5 / 27.0 s), `DSPCFG` Off and On, before
and after. `-str 32`, `-nothrottle`, visible video.

```bash
run.sh <binary> <tag> <cfgdir>     # -skip_gameinfo -nothrottle -log -str 32
                                   # -autoboot_script audio.lua -wavwrite <tag>.wav
grep -A32 'FRAME REPORT' <tag>.error.log
```

| | before | after |
|---|---|---|
| frames run | 1 536 349 | **1 536 349** |
| words executing **something** of 285 | 199 | **199** |
| words executing **FULLY** | 107 | **107** |
| words executing **addressing only** | 92 | **92** |
| words executing **nothing** | 86 | **86** |
| ★ **frames COMPLETED** | **0** of 1 536 349 | ★ **0** of 1 536 349 |
| frames that TRAPPED | 1 536 349 (100.00 %) | **identical** |
| ended on wait word / CAP / OVERRUN | 1 299 228 / 210 241 / 26 880 | **identical** |
| ★ **operand-pointer closure residue, last frame** | **+0** | ★ **+0** |
| complete frames that CLOSED | 1 273 307 of 1 299 228 | **identical** |
| residue min / max, entry pointer X | −1 / +116, `0xFF` 97.93 % | **identical** |
| input-stage audit | 1 309 788 both-reads, **0 MISMATCHED** | **identical** |
| frames carrying a NON-ZERO sample into the chip | **438 663**, peak `0x542500` | **identical** |
| **descriptor-cursor residue** | NOT TESTABLE (its 42 consumers trap) | **still NOT TESTABLE** |
| distinct undecoded words / families | 443 / 133 | **443 / 133** |
| frame floor tier 1 | 82 of 216, **38.0 %** | **38.0 %** |
| frame floor tier 1 + 2 | **60.6 %** | **60.6 %** |
| reverb image (algo 16), 133 words | **51.9 % / 75.9 %** | **identical** |
| 38 distinct body images, 2974 words | 1234 tier 1, **41.5 % / 52.6 %** | **identical** |
| frame-floor tier-2 DETERMINED / MEASURED / PARTIAL | 32 / 6 / 11 | **32 / 6 / 11** |

**The two FRAME REPORTs are identical line for line** (`diff` clean), which they
must be: the binary is byte-identical.

★ **The descriptor-cursor residue is STILL not testable**, and neither T2 nor T3
made it testable. Their results say *which cell* and *which direction*; the 42
consumers still trap, so the cursor has no live consequence to measure.

★ **Rule 5 — the impulse test was not run because the delay line does not
execute.** What it would need, re-derived from the descriptor images (rule 8):
ROOM REVERB 1's pre-delay is **800 samples**, its ladder
`83 172 356 513 739 240 119 247 428 616 360` = **3873 samples = 87.82 ms**, its
early reflections **650** and **540**, longest path **4673 samples = 105.96 ms**.
`8905` stays retracted; so does r1 §3's `127 435 489 183 522`. ★ **And the
ladder is CONSISTENT, not MEASURED** — ROOM REVERB 1 carries exactly ONE host
`op-0x67` tap, so only the 800-sample pre-delay is host-anchored and all eleven
segments are allocation-model output.

---

## 4. SAFETY

* Build clean — **0** `error:`; binary **74 405 928** bytes, mtime advanced
  (12:18), `tools/publish-binary.sh` run.
* ★ **Byte-identical binary**, `md5 965976f50bbfa11299d1449caca7d336`, against
  the previously published one. An artefact control that **could** have failed.
* `-validate kn5000` — **exit 0, zero bytes of output**.
* `dsp/verify.py` — **BYTE-MATCH OK** (kernel + epilogue + 91 valid algorithm
  streams, 38 distinct images).
* `tools/upd6383d_diff.sh` — **MIRRORS AGREE, 3057/3057**, text *and* the three
  execution predicates D/A/K.
* ★ **Audio bit-identical on a capture verified to carry audio**: all four WAVs
  (`DSPCFG` Off/On × before/after) are `f57115a26a55fcfed68fb6eab0769ea8` —
  **1 536 001 frames, 876 696 non-zero samples, peak 21 541**. The non-zero count
  and peak are checked *before* anything is concluded, because round 5's first
  attempt produced peak 0 over 1 440 001 frames.

---

## 5. What the next pass should pick up, ranked

1. ★ **BUILD THE TWO-ADDRESS DELAY-LINE HARNESS.** Read cell and write cell come
   from `dram-bounds.md`'s 324-line set; the rotation `G` is a free parameter;
   the write trails the read by `+3` port slots (`dram-datapath.md` §5, and
   `adjudication-round6.md` §5: exceptionless on the 17 host-anchored
   one-read-one-write lines). It is the same machinery `dram-datapath.md` named
   for its own stage B, and it now blocks **three** published determinations
   (`ACTION 0x19`, `SRC 0x00`, the adder's second leg) as well as the reverb
   topology search.
2. **The C-format direction** for the 48 trapping cells — and *the host firmware
   already names them*: `T1[0x67]` of all twelve reverbs reserves
   `0x19 0x1A 0x1B 0x1C 0x1D 0x1E`, and four of those cells are the trapping
   words, sitting `975 / 1082 / 1084 / 1625` samples off the pre-delay base.
   That is early-reflection shaped, and the host-naming lever is what solved the
   bounds question and the phase.
3. **The write-data source** for a WRITE word, and one member of the read
   latency for a READ word (which is now **OPEN** again — see
   `adjudication-round6.md` §6: `land ∈ [1,4]`'s two ends are stated in
   different units).
4. `kn5000.cpp`'s `porth_read().set_constant(0x01)` — **still do not touch it**;
   its live bit is PH.3 (`second-dsp-and-ready.md` A3).

# NEC uPD6383GF — decoding the COMMON HEADER: control flow, the frame loop, the I/O path

KN5000 IC311 effects DSP (NEC uPD6383GF-3BA). Date: 2026-07-22.
Follows `kn5000-dsp-pointer.md`, which found the pointer origins inside the common header and
falsified "bit 10 = END OF PROGRAM". Reproduce:

```
python3 tools/kn5000_dsp_headerdecode.py \
    notes/data/kn5000_dsp1_upload_coldboot.txt \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom
```

Claims are tagged **MEASURED**, **PROVEN BY CONSTRUCTION**, **INFERRED** or **SPECULATIVE**.
§7 is misses and corrections. §8 is what the instrument is blind to. **No audio path was added, the
core is still instantiated DISABLED, and nothing in the KN5000 driver was touched.**

---

## Headline

1. **★★★ CALL AND RETURN ARE PROVED — by register reuse, not by pattern matching.** The header
   loads the *same three registers twice*: `0x821/0x827/0x825 <- #$70/#$6C/#$25` at I-RAM 42–44,
   then `#$50/#$64/#$25` at I-RAM 50–52. No body contains a pointer load (0 of 2974 words,
   `-pointer.md` §1), so each body reads what the header last wrote; the second load destroys the
   first. Both units run every frame. **Therefore unit 0's body must execute between I-RAM 44 and
   I-RAM 50, and control must come back.** The only word in between that can transfer is I-RAM 49.
   This is **PROVEN BY CONSTRUCTION**, and it is the first control-flow fact in this series that is
   not an inference from co-occurrence. (§2)
2. **★★★ BIT 10 IS "END OF BLOCK", AND ITS DEFAULT ACTION IS FALL-THROUGH.** The transfer is not
   carried by bit 10 — it is carried by the **unit tag** (`class4 == 1 && addr8 ∈ {0x0E, 0x0F}`)
   that rides on two of the fourteen header end-of-block words. Proof that bit 10 is not a branch:
   I-RAM 42–44 must execute (headline 1 depends on it) and is reachable only by falling through
   I-RAM 41, which is itself an end-of-block word. **PROVEN BY CONSTRUCTION.** So the three
   candidate readings resolve as: *end-of-segment* ✔, *call/return sharing one encoding* ✔ **but
   only for the tagged form**, *commit/output-write* ✘ (§2.4). (§2)
3. **★★ THE FRAME LOOP: THERE IS NONE IN SOFTWARE.** Fourteen blocks in the 60-word header, one
   block per body (38/38, always the last word) — and the block at I-RAM 60..82 contains **no
   end-of-block word at all**. A block that never ends is a block closed by hardware. With the
   `Fs-RST` / `PC-RST` pins this reads directly: the PC is restarted by the sample clock, and the
   last word of the frame, `C00.A.47.407` at I-RAM 82, is the wait/halt (`hi12 == 0xC00` occurs
   **zero** times in 2974 body words). The per-frame dispatch model of `-pointer.md` §2 is
   **confirmed and completed**. (§3)
4. **★★ I-RAM 60..82 IS NOT AN "ALGORITHM-CHANGE STUB" — IT IS THE FRAME EPILOGUE, AND IT IS THE
   OUTPUT STAGE.** Unit 1's call is the header's last word (59), so its return lands on word 60.
   The two words the host patches at run time, I-RAM **64** and **71**, carry the unit tags `0x0E`
   and `0x0F` in their default form (`011.9.0E.445` / `011.9.0F.446`) and keep an **invariant
   `lo12` per slot** (`0x445`, `0x446`) while `hi12`/`class4`/`addr8` change with every effect
   selection. Two per-unit words, patched on effect change, in the epilogue, after both units have
   run: these are the **effect-return / wet-level** words. **INFERRED (strong).** (§4)
5. **★ THE HEADER RUNS ON ITS OWN COEFFICIENT BANK.** The header has 23 cursor-fetching words. If
   they drew from the algorithm's bank, every algorithm would ship 23 extra coefficients. Measured
   over all 38 images, (coefficients uploaded − body cursor-fetching words) is **+1 in 18 images
   and lies in −3..+9 in 35 of 38** — never near +23. **MEASURED.** (§5)
6. **★ A CORRECTION I OWE THE PREVIOUS NOTE: THE FALSIFICATION OF `0x825` RESTS ON A PREMISE THAT
   IS NOW FALSE.** `-pointer.md` §3 killed `0x825` as the body pointer because it is loaded with
   `#$25` for *both* units and "both effect units are resident and running in the same frame", so
   they would alias. They are resident simultaneously but they **do not run simultaneously** — the
   dispatch is time-multiplexed, which headline 1 proves. `0x825` is therefore **un-falsified**.
   This does not make it the pointer (`0x821` still wins on the host-map evidence) but the argument
   that excluded it is void and must not be cited again. (§7.1)
7. **★ `hi12[9:8]` HAS ARITY 3, NOT 4.** Over the body corpus the values split 1713 / 493 / 766 / **2**,
   and all 2 occurrences of value 3 are the *same* word, `302.A.00.655`. "All four values
   exercised" (`-hi12.md`) is literally true and analytically misleading. **MEASURED.** (§6)
8. **★ COVERAGE, RECOMPUTED THE SAME SCOPED WAY: 18.3 % (545/2974), UNCHANGED.** This pass decoded
   no body word — by construction, it worked on the 83 words the coverage denominator excludes.
   Saying so is the point; the honest scoped figure does not move. (§9)

---

## 1. The header is fourteen blocks

`is_eob(w) = (hi12 & 0xC00) == 0x400` — bit 10 set, bit 11 (format escape) clear. This is the
series definition; words such as `0xC64` and `0xC00` have bit 10 set but are escape-format and are
**not** end-of-block. Under it (**MEASURED**):

| region | words | end-of-block words |
|---|---|---|
| header, I-RAM 0..59 | 60 | **14** (indices 6, 11, 14, 19, 21, 23, 24, 28, 33, 36, 39, 41, 49, 59) |
| bodies, 38 images | 2974 | **38** — exactly one per image, and always the **last** word (38/38) |
| I-RAM 60..82 | 23 | **0** |

Block lengths in the header: `7 5 3 5 2 2 1 4 5 3 3 2 8 10`. Mean 4.3 words against a body's 78.
That disparity is itself evidence: whatever a block is, a body is one of them and the header is a
string of small ones.

The last two blocks, the ones that matter:

```
   block 12  I-RAM 40..41                      block 13  I-RAM 50..59
       40  C4A.1.C0.820                            50  801.0.50.821   ldreg 821,#$50
       41  400.A.00.21A  <== END OF BLOCK          51  801.0.64.827   ldreg 827,#$64
                                                   52  801.0.25.825   ldreg 825,#$25
   block 12b I-RAM 42..49                          53  010.9.D0.20C
       42  801.0.70.821   ldreg 821,#$70           54  800.1.60.00B
       43  801.0.6C.827   ldreg 827,#$6C           55  000.2.01.007
       44  801.0.25.825   ldreg 825,#$25           56  C64.6.A2.007
       45  010.A.00.20C                            57  000.2.01.000
       46  800.1.60.00B                            58  000.1.8A.007
       47  800.8.0C.000                            59  400.1.0F.007  <== END + unit tag 0x0F
       48  C64.5.A2.000
       49  400.1.0E.000  <== END + unit tag 0x0E
```

## 2. Control flow

### 2.1 The register-reuse proof (**PROVEN BY CONSTRUCTION**)

```
   reg 0x820 : I-RAM 15 <- #$92   22 <- #$12   29 <- #$57   31 <- #$B1   40 <- #$C0
   reg 0x821 : I-RAM 42 <- #$70   50 <- #$50
   reg 0x825 : I-RAM 44 <- #$25   52 <- #$25
   reg 0x827 : I-RAM 43 <- #$6C   51 <- #$64
```

Premises, each already established and each cited: (a) neither body contains a pointer load —
0 of 2974 words, `-pointer.md` §1, MEASURED; (b) both effect units are loaded and both run every
frame, `-header.md` §0, MEASURED; (c) each unit's body walks its own state cells, or the two units
would share state (`-pointer.md` §3, and the reason `0x825` was doubted in the first place).

From (a) a body's pointer can only be what the header last wrote. From (b)+(c) unit 0's body needs
`0x821 == 0x70`, which is true only between I-RAM 42 and I-RAM 50. **Unit 0's body executes inside
that window and control returns into it**, because I-RAM 50–59 (unit 1's setup) still has to run
afterwards. I-RAM 49 is the only candidate transfer in the window. ∎

This is the same conclusion `-pointer.md` §2 reached as a *reading*; it is now a deduction, and it
survives without any appeal to the CDJ-500 stack depth.

### 2.2 The call word and the return word

```
   header 49:  400.1.0E.000   <- byte-identical to the terminator of several unit-0 bodies
   header 59:  400.1.0F.007      (unit-1 body terminator is 612.1.0F.000 — same class4+addr8)
   unit-0 body terminators, 36 images:  hi12 varies, always  .1.0E.000  or  .1.0E.407
   unit-1 body terminator,   1 image :  612.1.0F.000
```

So **call and return share one encoding** and are distinguished only by context, as hypothesised.
The invariant part is `class4 == 1 && addr8 == unit tag`; `hi12` and `lo12` are free, which is what
you expect of a horizontal microword — the transfer bit rides along with whatever datapath work the
word also does.

### 2.3 bit 10 is not the branch (**PROVEN BY CONSTRUCTION**)

I-RAM 42–44 must execute. They are reachable only by falling through I-RAM 41, `400.A.00.21A`,
which is an end-of-block word. Therefore the default action after an end-of-block word is
**fall through**, and the twelve untagged end-of-block words in the header are not transfers.
A `COND`-gated conditional branch is not needed to explain them and is not evidenced.

### 2.4 The three candidate readings, resolved

| reading | verdict | why |
|---|---|---|
| **end of segment / block** | **✔ SURVIVES** — this is what bit 10 is | uniform over header (14), bodies (38, all terminal) and epilogue (0) |
| **call/return sharing one encoding** | **✔ but only for the tagged form** | proved for I-RAM 49; the tag, not bit 10, carries the transfer |
| **commit / output-write flag** | **✘ FALSIFIED** | a body performs many stores (bit 4) and many sums of products, yet carries bit 10 exactly once, at the very end. No per-computation meaning can be once-per-body. |
| **end of program / halt** | **✘ already falsified**, not resurrected | 14× in a 60-word header, first at word 6 |

The task's suggested discriminator — do the interior bit-10 words end coherent runs, or cluster
around audio I/O? — comes out on the side of *runs*: e.g. block 3 is `C0A.2.92.820` (load) followed
by three consecutive cursor-fetching words `192.A / 292.A / 182.A`, closed by `512.2.00.44D`; block
9 is `000.A.FF.407 / 012.A.00.1C0 / 400.A.00.000`. They end short computations. They do **not** sit
next to the I/O candidates of §4.

## 3. The per-sample loop: hardware, not software (**INFERRED, strong**)

```
   Fs edge -> PC := 0
     0..48    per-frame preamble: input stage, LFOs, mixes, then unit 0's registers
       49     CALL unit 0        -> 84..     body       -> RETURN to 50
    50..58    unit 1's registers
       59     CALL unit 1        -> 200..    body       -> RETURN to 60
    60..82    EPILOGUE: per-unit returns (64, 71 = the host's patch slots), output stage
       82     C00.A.47.407  -> wait for Fs        (hi12 0xC00: 0 occurrences in 2974 body words)
```

Evidence that the frame is closed by hardware and not by a backward branch:

* no end-of-block word anywhere in I-RAM 60..82 (**MEASURED**) — a block that never ends;
* no field anywhere in the corpus carries a backward target; two exhaustive bitfield scans
  (`-necfamily.md` §6) found none, and this model says there is none to find;
* the pins are named `Fs-RST` and `PC-RST` (CDJ-500 manual);
* the pointer registers are reloaded from the header every frame rather than restored by the
  bodies — the header *is* the reset, which is only sensible if the header is re-entered every
  sample (`-pointer.md` §2, and it needed exactly this to be true).

**Prediction, to check when the core runs:** the total word count on the frame path is
60 + (unit-0 body) + (unit-1 body) + 23. For the observed pair (algo 1 at 84 = 70 words, the
reverb at 200 = 133 words) that is **286 instruction slots per sample**. At 44,100 Hz that demands
≥ 12.6 MHz of issue rate, comfortably inside the 25 MHz crystal on IC311 (a 2:1 or 4:1 internal
divide both fit). The largest pair in the corpus (110 + 133) gives 326 slots ⇒ 14.4 MHz. **The
I-RAM's 384-word capacity and the 25 MHz clock are consistent with one pass per sample** — an
independent, if weak, corroboration.

## 4. The audio I/O path

Nothing here is proved. The candidates, ranked, with the body corpus as control.

### 4.1 The output stage: I-RAM 64 and 71, the host's per-unit patch slots (**INFERRED, strong**)

```
   default in the uploaded epilogue     I-RAM 64  011.9.0E.445      I-RAM 71  011.9.0F.446
   host writes observed in the capture            C40.5.40.445                C40.6.40.446
                                                  C40.A.80.445                C41.9.00.446
```

Four separately-recorded facts point one way: these are the only two words the host ever patches;
they sit in the epilogue, after both units have run; their default forms carry the **unit tags**
`0x0E` / `0x0F`; and their `lo12` is **invariant per slot** while everything else tracks the effect
selection. A per-unit route with a host-controlled operand, applied after the unit produced its
result, is an **effect-return level**. If that is right, `lo12 0x445 / 0x446` names the two
effect-return buses and the varying `class4` + `addr8` names where the level comes from.

⚠ This puts a question mark over `-effect-map.md`'s `hi12 == 0xC40 = envelope detector`: three of
the four host-patched values are `0xC40`, and a wet-level slot is not an envelope detector. One of
the two identifications is wrong, or `0xC40` is a shared enable pattern rather than a role. **Not
resolved here — flagged.**

### 4.2 The input stage: the two parallel opening blocks (**SPECULATIVE**)

```
   block 0, I-RAM 0..6                     block 1, I-RAM 7..11
       0  092.2.01.20D
       1  C0A.0.E0.000
       2  084.2.02.680                         8  084.2.01.1C0
       3  012.2.FF.1CE                         9  012.2.FF.1D5
       4  204.2.02.1CE                         7  090.A.01.1C8
       5  202.A.00.448                        10  282.A.01.417
       6  400.A.00.419  END                   11  400.2.01.447  END
```

Two near-parallel blocks at the very top of the frame, distinguished by `addr8` **0x02 vs 0x01**,
each closed by an end-of-block word whose `lo12` is in the `0x4xx` route family (`0x419`, `0x447`)
— the same family as the epilogue's `0x445`/`0x446`. `addr8 == 0x03` **never occurs in the header**,
so this is a **two-channel (stereo) structure**, not a three-way `DI1/DI2/DI3` sweep: the chip has
three ports, this board uses one stereo pair. `addr8 == 0xFF` at words 3 and 9 is the signed −1
post-decrement already established for the pointer.

> ⚠ **CONCLUSION UPHELD, REASON FALSIFIED — banner added 2026-07-26**
> (`analysis/retraction-sweep.md` P6). The sentence *"the chip has three ports, this
> board uses one stereo pair"* is **wrong about the board**: `dsp-audiopath-wiring.md`
> §1.1/§2 MEASURED from the service manual that **all three DI and all three DO are
> wired** (`SDOA/SDOB/SDO1` → `DI1/DI2/DI3`; `DO1/DO2` → `SDIA/SDIB`). And the
> supporting step is a category error: **`addr8` is a pointer delta**, so it could
> never have carried a port index — "`addr8 == 0x03` never occurs" says nothing about
> DI3.
>
> **The two-channel conclusion nevertheless SURVIVES**, re-derived by K6 on
> independent evidence (`dsp-k6-input-stage.md` finding 6): exactly two D-RAM cells are
> supplied from outside the instruction stream, one PC sweep runs per LRCK period, and
> the reverb's MEASURED mirrored L/R output tails prove the result is stereo — so the
> two blocks are the **L and R channels**, and this board's microcode reads **one** of
> its three wired ports. **Which** port is not decidable from the microcode (the
> latch→cell map is a chip property); DI1 is an assumption, labelled as one.

### 4.3 The per-unit send: the class-5 / class-6 twin (**INFERRED**)

```
   I-RAM 48, in unit 0's block, immediately before the call:  C64.5.A2.000
   I-RAM 56, in unit 1's block, immediately before the call:  C64.6.A2.007
```

Identical `hi12` and `addr8`, same position in each unit's block, differing **only in `class4`**,
5 for unit 0 and 6 for unit 1. Read with §4.1 this is the **send** and §4.1 is the **return**.
class 5 occurs once in 2974 body words and class 6 only inside the table-lookup idiom, so this pair
is not a body idiom leaking in.

### 4.4 Classes that exist ONLY outside the bodies (**MEASURED**)

```
   class      bodies  header  epilogue
       9           0       1         5   <- absent from all 2974 body words
       C           0       0         1   <- absent
       D           0       0         1   <- absent
```

Since the bodies provably contain no I/O and classes 9/C/D are provably not used by the bodies,
classes 9, C and D are the strongest *class-level* I/O candidates in the whole corpus. Five of the
seven are in the epilogue, including both host patch slots (`class 9` in their default form).
Against this: the one class-9 word in the header, `010.9.D0.20C` at I-RAM 53, sits at exactly the
position where unit 0's block has `010.A.00.20C` (class A) — the same word in a different space —
so class 9 is at least sometimes a *space variant* of class A, not an I/O opcode. **Reported as a
lead with its own counter-evidence.**

## 5. The header does not share the algorithm's coefficient bank (**MEASURED**)

23 of the header's 60 words have `class4` bit 3 set (cursor-fetching). Over all 38 images,
(coefficients uploaded for the algorithm) − (cursor-fetching words in its body):

```
   -39 x1   -3 x2   -1 x7   0 x2   +1 x18   +3 x2   +4 x1   +5 x2   +7 x2   +9 x1
```

Centred on +1, never near +23. The header therefore reads a **separate, fixed coefficient bank**,
loaded once at boot — which is also why the header's constants never varied across the three
identical uploads in the cold-boot capture. The −39 outlier is algo 39 (70 cursor words, 31
coefficients), already known to be the corpus's odd one out.

> ★★★★ **CONFIRMED AND LOCATED — banner added 2026-07-31 (`kn5000-roms-disasm` register §226,
> `dsp/analysis/HEADER-BANK_findings.md`).** The bank is **`C-RAM[0x90..0xB4]`** and the header
> consumes **`0x90..0xA3`** (20 cursor-advancing words before `w42`'s `ldptr #$70`; `w30/w32/w33`
> are offsets `+0x0B/+0x0C/+0x0D`, which is why `§S2` measures `0x9B`). The base is set by an
> **instruction** — the epilogue's own `iw69 = 801.0.90.821 ldptr #$90`, the last pointer load of
> the frame — and the **epilogue contains ZERO cursor-advancing words**, so the next frame's `w0`
> starts at **exactly `0x90`, every frame**.
> **22 of the 37 cells in `0x90..0xB4` are written by NO algorithm's parameter map** (`91..9D`,
> `A1..A5`, `AD AE B3 B4`), and `0x9B/0x9C/0x9D` are identical in the cold-boot capture, in the
> PARAMETRIC-EQ capture **and** in a live 30-second run.
> ⛔ **It is NOT `0x00`.** `C-RAM[0x00..0x13]` is the **unit-0 effect's own parameter bank**:
> selecting PARAMETRIC EQ rewrites `0x00..0x1E` wholesale (twelve `cmd 0x02` runs) and moves
> **every one of `0x00..0x13`**, and the boot run's length there tracks the algorithm (20 cells for
> CHORUS's `classA 19`, **31** for PARAMETRIC EQ — this section's own −39 outlier).
> Reproduce: `python3 dsp/tools/hdrbase.py` in the disassembly repo.
>
> ⛔⛔ **RETRACTED IN PART — banner added 2026-07-31 (register §227).** The bank is **NOT
> boot-fixed and this section's §5 prediction is NOT confirmed.** §226's invariance was measured
> on **one capture pair carrying the same reverb**. §227 took the missing capture: a preset change
> **CONCERT REVERB 1 → ROOM REVERB 1** rewrites **23 cells, every one inside `0x90..0xB4` and
> NOTHING else in the 256-cell C-RAM** — `[00..4F]` **0 of 80**, `[50..8F]` **0 of 64**, the
> header's own walk `[90..A3]` **13 of 20**, and the ladder cells `[9B..9D]` **2 of 3** (`0x9B`,
> `0x9C`).
> ⇒ **`C-RAM[0x90..0xB4]` IS UNIT 1's (THE REVERB's) PER-ALGORITHM PARAMETER BANK.** The "22 cells
> written by no algorithm" measured a **gap in the ROM's T1 map** — **15 of those 22 move** under a
> preset change. In Q1.22 the cells read as reverb gains (CONCERT `1.200/1.000/1.000`, ROOM
> `1.000/0.800/1.000`).
> ★ **The control:** an independent 45 s panel run landing on CONCERT REVERB 1 reproduces the
> archived cold-boot capture on **all 256 cells, 0 differ** ⇒ **the cold-boot default reverb is
> CONCERT REVERB 1**, not ROOM REVERB 1.
> ✔ **Still true:** the base is `0x90` and it is set by `iw69`; it is **not** `0x00` (unit 0's
> bank); the upload is the `cmd 0x02` runs at `0x90` + `0xAE`.
> Reproduce: `python3 dsp/tools/hdrbase.py --score notes/data/kn5000_dsp1_upload_concertreverb1.txt notes/data/kn5000_dsp1_upload_roomreverb1.txt`

## 6. `hi12[9:8]` (**MEASURED**)

```
   bodies : {0: 1713, 1: 493, 2: 766, 3: 2}      value 3 = one distinct word, 302.A.00.655
   header : {0: 49,   1: 4,   2: 7}
```

The field's **arity is 3**, not 4. `-hi12.md`'s "all four values exercised on the `..02` base" is
literally true and analytically misleading: the fourth value is a singleton in 2974 words. A 3-way
operand-source selector is consistent with the solved biquad, which needs three operand sources; a
4-way mode selector is not supported. Bits `[3:1]` were not advanced this pass.

## 7. Misses, corrections and things I did not get

1. **CORRECTION to `-pointer.md` §3.** The falsification of `0x825` ("both units resident ⇒ they
   would alias") assumed the units run *simultaneously*. §2.1 proves the dispatch is
   **time-multiplexed**, so a register loaded with the same value for both units aliases nothing.
   `0x825` is un-falsified. `0x821` remains the better candidate, on the host-map evidence alone.
2. **PARTIAL MISS against the lead I was given.** The lead proposed that `bit10 | class 1 | addr8 =
   unit` is a call/return pair sharing one encoding. That is confirmed. But the lead also carried
   the implication that bit 10 is the transfer; it is not (§2.3). Twelve of the fourteen header
   end-of-block words fall through, and any model that treats bit 10 as a branch stops the machine
   before it reaches the pointer loads the same model depends on.
3. **The audio I/O is NOT identified.** §4 gives ranked candidates and one strong inference about
   the *return* stage; no word is decoded. The honest statement is that the output stage has been
   **located** (I-RAM 64 and 71, in the epilogue) without being **decoded**.
4. **`COND` and `BRAKST` remain unfound.** This pass makes the negative *expected* rather than
   merely recorded: with a hardware-restarted PC, unrolled bodies and a fall-through block
   terminator, the KN5000's firmware may simply never emit a conditional branch. That is not proof
   that the field does not exist — the pin table says it does — only an explanation of the silence.
5. **Task D (the pointer-delta rule) and the `hi12[3:1]` bits were not attempted.** §6 is the only
   `hi12` result. I chose depth on A–C over breadth; the phaser's `0x76` vs `0x7B` discrepancy is
   untouched and is still the single binding unknown for addressing.
6. **The 23 header cursor-fetch words have no coefficients to point at.** §5 says the bank is
   separate; I did not find the upload that fills it. The cold-boot capture's early `cmd 0x0C`
   / short `cmd 0x02` transfers are the place to look, and I did not look.

   > ★★★★ **ANSWERED 2026-07-31 (register §226).** The upload is the **boot-time `cmd 0x02` runs
   > at base `0x90` (30 values) and `0xAE` (7)** — 37 cells, `0x90..0xB4`, **byte-identical in
   > both archived captures**. ⚠ **§227:** byte-identical because both captures carried the **same
   > reverb**; those 37 cells are the **cold-boot reverb's coefficients**, not a fixed bank. The
   > *upload* answer stands; the *fixed* adjective does not.
   > ★ **Why looking at the `cmd 0x02` transfers alone would not have found it:** a `cmd 0x02`
   > packet is a bare stream of 3-byte coefficients and **carries no destination address**. The
   > host sets the destination by writing an **`ldptr` word** (`hi12 0x801`, `lo12 0x821`) into a
   > scratch I-RAM slot (I-RAM 352 in the capture) with a `cmd 0x01`, *then* streams. Replaying
   > that rule over the cold-boot capture gives, in order:
   > `#$50→30, #$6E→30` (the two ramps, `0x50..0x8B`), `#$90→30, #$AE→7` (**the header's bank**),
   > `#$00→20` (the unit-0 effect's bank) — and `30+30+30+7+20 = 117`, the emulator's own
   > *"117 coefficients routed"*.
   > ⚠ The count is **20**, not 23: only `class4 == 0xA` non-`c_format` words advance the cursor,
   > and 20 of them run before `w42`'s `ldptr #$70` re-aims it. §5's "23" counts `class4` bit 3.

## 8. What this instrument is blind to

* **Everything here is static.** Not one claim in §2–§4 was checked by running the core. The
  register-reuse proof is a proof about the *program*, not an observation of the *machine*; if the
  chip has shadow register banks per unit — which would be a perfectly normal thing for a
  two-unit audio DSP to have — the proof's premise (b)+(c) still holds but the *conclusion about
  where the body runs* weakens to "unit 0's body runs while `0x821 == 0x70`", which the header can
  also arrange by banking. **The falsifier is cheap:** run the core with the pointer trace and see
  whether the address stream from the body at 84 starts near `0x70` when entered at word 49.
* **The frame model rests on one capture of one boot with one effect pair.** A second effect
  selection that changes the *epilogue* rather than just patching two words would break it.
* **83 words over-fit trivially.** Every pattern in §1–§4 was re-measured against the 2974-word
  body corpus as a control, and the ones that survive are reported with both counts — but a
  two-block parallelism in a 60-word program is a weak signal by construction, and §4.2 is
  labelled SPECULATIVE for that reason and no other.
* **The "epilogue" naming is a hypothesis about a block I have only ever seen uploaded once.** The
  previous notes call I-RAM 60..82 the *algorithm-change stub*; the only evidence that changed is
  that unit 1's return lands on word 60 and that the host's two patch slots are inside it. If the
  block turns out to be host-invoked rather than fallen-into, §3 loses its ending and §4.1 loses
  its "after both units have run".

## 9. Coverage

Recomputed the same scoped way as `-axes.md` §6.1, `-hi12.md` §6 and `-pointer.md` §9:
**18.3 % (545 / 2974)** — **unchanged**. This pass decoded no body word, because it worked entirely
on the 83 words the denominator excludes by construction. What it bought instead: one proof by
construction (call/return), one falsification (bit 10 as commit), one correction to a previous note
(`0x825`), a completed frame model, and the *location* of the output stage. Counting any of those
as vocabulary would be the over-claim the last three notes all refused, and this one refuses too.

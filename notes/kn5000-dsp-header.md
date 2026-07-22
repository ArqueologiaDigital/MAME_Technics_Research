# NEC uPD6383GF — the common header and the algorithm-change stub

KN5000 IC311 effects DSP. Companion to `notes/kn5000-dsp-encoding.md` (the field map and the
ROM `ALGO_TABLE` corpus) and `notes/kn5000-dsp-coefficients.md` (a separate investigation).

Tool: `tools/kn5000_dsp_header.py` (reuses `kn5000_dsp_wordfields.parse()` and
`kn5000_dsp_extract`). Every number below is reproduced by

```
python3 tools/kn5000_dsp_header.py <dspcap>/run3/kn5000_dsp1_upload.txt \
        kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom
```

Claims are tagged **MEASURED**, **INFERRED** or **SPECULATIVE**. Section 9 lists what was
falsified. **No instruction is decoded here either** — but three structural facts are now
nailed down that were not before, and one of the encoding note's core assumptions is
partially overturned.

---

## 0. Corpus

| block | I-RAM | words | uploaded by | ROM source |
|---|---|---|---|---|
| common header | 0..59 | 60 | `EFF_WriteHeader` (subcpu `0x0380C1`) | `0x01E496`, op-3 record, len 305 |
| algorithm-change stub | 60..82 | 23 | `DSP_AlgorithmChange` (subcpu `0x038011`) | `0x01E63C`, op-3 record, len 120 |
| effect body, unit 0 | 84.. | ≤110 | `ALGO_TABLE` stream | per algorithm |
| effect body, unit 1 | 200.. | ≤133 | `ALGO_TABLE` stream | per algorithm |
| host poke slot | 352..382 | 1..31 | many small writes | built at runtime |

**MEASURED.** The header is uploaded 3× per cold boot, byte-identical; the stub once. Both
match the ROM bytes exactly (`rom_crosscheck` prints `bytes match capture: True` for both), so
the live capture and the static ROM agree and the ROM addresses in the task brief are confirmed.

**MEASURED.** Maximum body length is 110 words at slot 84 and 133 at slot 200 (over all 96
extracted images). 84 + 110 = 194 < 200, and 200 + 133 = 333 < 352. **The four regions do not
overlap: 0..59 header, 60..82 stub, 84..199 unit-0 body, 200..333 unit-1 body, 352..382 poke.**
That is a complete, consistent I-RAM memory map for a 384-word instruction RAM, and it was not
known before. It also means the "one image loads at 84, another at 200" observation is not two
alternatives — **both units are resident simultaneously**.

---

## 1. What the block diagram says must exist (hypothesis space)

Read off CDJ-500 service manual page 1-15 (block diagram) and the pin table on 1-16/1-17:

* **PC** fed from I-RAM through **DEC**, with **STACK1** and **STACK2** — a 2-deep call stack.
  Two levels is a hard constraint: there is no general recursion and at most two nested calls.
* **UCPC** (a second program-counter-like register), **STA-R** (status), **CNT-R** (count).
* Loop counters **LC1, LC2, LC3**; timers/registers **TR0–TR3**.
* Pointers **CP, DP, BP1, BP2, PR1, PR2** into C-RAM 256×24 and D-RAM 256×24, plus **BNK-R**.
* External DRAM delay: **OFP**, **OF-RAM ADDR.R**, **DATA BUF**, RAS/CAS/WE, A0–A16 (17 bits →
  up to 128K words), I/O1–16 (16-bit delay samples).
* Serial audio **DI1–DI3** in and **DO1–DO3** out, each with separate L and R latches.
* **GF1–GF3**: "can be set, reset and toggled **by instructions**" (pins 83–85).
* **RQ1–RQ3**: host-written, "can be **verified by the COND field in instructions**" (86–88).
* **BRAKST**: named instruction, resets BR-AK (pin 12), emulator mode only.

So the control operations that *must* be encodable are: loop setup/decrement/branch on LC1–LC3;
per-instruction conditional execution via COND (testing RQ1–RQ3 and internal status); GF
set/reset/toggle; call/return through the 2-deep stack; OF-RAM address/OFP setup; DI/DO framing;
pointer loads; bank switching. **This section is the hypothesis space, not a result.**

---

## 2. The header's structure: two parallel per-unit segments (MEASURED positions)

The full field dump is in the tool output. The decisive observation:

**The terminator signature `class4==1 && addr8∈{0x0E,0x0F}` occurs TWICE inside the header — at
I-RAM 49 and at I-RAM 59 — and ZERO times in the 23-word stub.**

```
   49  400.1.0E.000
   59  400.1.0F.007
```

and the ten words leading up to each are near-parallel:

```
    40 C4A.1.C0.820          50 801.0.50.821
    41 400.A.00.21A          51 801.0.64.827
    42 801.0.70.821   \      52 801.0.25.825
    43 801.0.6C.827    |     53 010.9.D0.20C
    44 801.0.25.825    |     54 800.1.60.00B
    45 010.A.00.20C    |     55 000.2.01.007
    46 800.1.60.00B   /      56 C64.6.A2.007
    47 800.8.0C.000          57 000.2.01.000
    48 C64.5.A2.000          58 000.1.8A.007
    49 400.1.0E.000          59 400.1.0F.007
```

Aligning 42→50 (an offset of 8, not 10) the `lo12` fields match in **five consecutive positions**:
`821, 827, 825, 20C, 00B`, of which two words (`801.0.25.825`, `800.1.60.00B`) are bit-identical
and the other three differ only in `addr8`/`class4`. The tails then pair up as
`C64.**5**.A2.**000**` ↔ `C64.**6**.A2.**007**` — same `hi12`, same `addr8`, differing only in
one bit of the nibble at [23:20] and in `lo12` — and finally terminator `0x0E` ↔ `0x0F`.

**Chance control.** The 83 words hold 15 `lo12` values that occur ≥2×; a run of five consecutive
positional `lo12` matches between two disjoint 10-word windows is not something these statistics
produce by accident (the same test over any other pair of 10-word windows in the 83 words yields
at most one match).

**INFERRED, strong: I-RAM 40..49 and 50..59 are the same routine instantiated twice, once per
effect unit.** Segment A ends with terminator index `0x0E`, segment B with `0x0F`.

---

## 3. `0x0E` / `0x0F` is a UNIT INDEX, not a branch target (INFERRED, three independent lines)

1. **Header segments.** Segment A ends `…1.0E.…`, segment B ends `…1.0F.…` (§2).
2. **Effect bodies.** Every body loaded at I-RAM 84 ends `xxx.1.**0E**.000`; the single body
   loaded at 200 ends `612.1.**0F**.000` (measured in `kn5000-dsp-encoding.md` §7).
3. **The host patch slots.** The stub contains exactly two words the host overwrites at runtime,
   at I-RAM **64** and I-RAM **71**. Their ROM defaults are

   ```
     64   011.9.**0E**.445
     71   011.9.**0F**.446
   ```

   and in the capture, slot **64** is patched immediately before the body upload to **84**
   (transfers #22 → #23) while slot **71** is patched immediately before the body upload to
   **200** (#6/#9 → #10).

Three unrelated mechanisms — the header's two segments, the two body load slots, and the two
host patch slots — all split `0x0E` / `0x0F` the same way, and always with `0x0E` on the
unit-0/address-84 side. **`addr8` in this family is a unit/channel selector.** This also closes
out the encoding note's §7 puzzle ("why +1 and not +116?"): the answer is that it was never a
program-counter value.

**Still open (SPECULATIVE):** what the terminator instruction *does*. The two live candidates are
"end of frame for unit N / wait for the next sample tick on channel N" and "return". Nothing here
distinguishes them, and a 2-deep stack makes a per-unit RET plausible.

---

## 4. The host patch slots at I-RAM 64 and 71 (MEASURED)

Identified by an **invariant `lo12`** across every write:

| slot | `lo12` | ROM default | observed patched values |
|---|---|---|---|
| 64 (unit 0) | always `445` | `011.9.0E.445` | `C40.5.40.445`, `C40.A.80.445` |
| 71 (unit 1) | always `446` | `011.9.0F.446` | `C40.6.40.446`, `C41.9.00.446` |

`lo12` is the only field that survives every rewrite, in both slots, and the two slots' values
differ by exactly 1 (`445`/`446`). **INFERRED: `lo12` carries the instruction identity for this
family and the two slots are the same instruction applied to the two units.**

**MEASURED, ROM.** These patch words are not synthesised — they come from a table that begins at
ROM `0x01E5C7`, immediately after the header stream, as op-`E` bytecode records. The tool
decodes it:

```
    op E -> I-RAM  64 := C40.5.40.445        op E -> I-RAM  64 := C40.A.80.445
    op E -> I-RAM  71 := C40.6.40.446        op E -> I-RAM  71 := C41.9.00.446
    op E len 9: e00930051b d003b16a          op E len 9: e00930051b d000716a
    op E len 9: e00930051f d003cd42          op E len 9: e00930051f d0026142
    op E len 9: e00930051d d003f156          op E len 9: e00930051d d001e156
```

i.e. the table is a sequence of **parameter sets**, each set = {patch unit-0 slot, patch unit-1
slot, three further records}. The three trailing records keep a selector (`051B`/`051F`/`051D`)
and change a 24-bit value (`03B16A`/`03CD42`/`03F156` → `00716A`/`026142`/`01E156`; the first
three read as Q0.23 +0.462/+0.475/+0.492).

**Numerically (SPECULATIVE):** treating bits [24:12] of the patched words as one field gives
`0x540→0xA80` (exactly ×2) for slot 64 and `0x640→0x1900` (exactly ×4) for slot 71 —
1344→2688 and 1600→6400. Powers-of-two scaling of a 13-bit quantity in a per-effect parameter
set is what a **delay length or loop count** looks like; 1344/2688/1600/6400 samples at 44.1 kHz
are 30/61/36/145 ms, all musically sensible delay times, and the chip has a 17-bit external DRAM
address for exactly this. This is a *reading*, not a demonstration — the field boundaries are
not established.

---

## 5. The hand-off to the effect body: NOT FOUND, and the fall-through model (partial result)

This was the highest-value target. **Negative result, carefully bounded.**

`tools/kn5000_dsp_header.py` scans **every contiguous bitfield** of every one of the 83 words
(start bit 0..35, width 1..16) for the values 84 (`0x54`) and 200 (`0xC8`):

```
  fields yielding BOTH 84 and 200 : NONE
```

29 field positions yield one value or the other, and every one of them is explained as an
artifact of a shared prefix — e.g. bits[30:23] = 200 at words 48 and 56 only because both have
`hi12 = 0xC64`, and bits[34:27] = 84 at words 63 and 70 only because both have `hi12 = 0x2A_`.
None gives 84 in one word and 200 in another, which is what a branch-target field would have to
do given that both bodies are resident.

**What the layout suggests instead (INFERRED, and the best available model):**

* The stub at 60..82 is the **only** one of the three blocks with **no terminator**.
* It ends at 82, and the unit-0 body region begins at 84.
* Therefore the natural reading is **fall-through**: 60..82 runs and drops into 83/84.

This is not proof — I-RAM 83 is never written by anyone in the capture, which is awkward for a
strict fall-through (a single uninitialised word would execute). Two ways out, both untested:
83 is a don't-care/NOP left by the reset state, or the last stub word `82: C00.A.47.407` *is* the
transfer and its `addr8 = 0x47 = 71` is a self-reference rather than a target.

**A structural argument against an encoded target existing at all:** I-RAM is 384 words and
needs 9 address bits, but no 9-bit field in the word has anywhere near the coverage that would
imply (`addr8` peaks at 122/256 and is pinned to RAM by the algo-32/34 minimal pair). If branch
targets were common, a 9-bit target field should be visible. It is not. **SPECULATIVE:** control
transfer on this chip may be predominantly *implicit* — a hardware sequencer that restarts the PC
each sample frame (the `PC-RST` / `Fs-RST` pins on the diagram are exactly that: "input of program
counter reset signal") and per-unit segment ends marked by the `0x0E`/`0x0F` instruction. On that
model there is no branch to find, which is consistent with everything measured.

Supporting the host-driven-entry idea: the capture's non-I-RAM traffic includes **`cmd 0x09` with
payload `00 3C` = 60**, sent twice, each time right after a `cmd 0x04` 5-byte control write
(`FB DA 3F A0 1A` / `FB DA 00 A0 1A`). 60 is exactly the stub's address. **SPECULATIVE: `cmd 0x09`
sets an entry/start address and the stub is entered from the host, not from the header.**

---

## 6. `class4` is NOT a universal instruction class — it is sometimes immediate data (MEASURED)

This partially overturns §5 of `kn5000-dsp-encoding.md`, and it is the strongest new encoding
result here.

Partition all words by whether `hi12`'s top nibble is `0xC`:

```
  effect bodies, 7108 words
    hi12[11:8] != C  (6880 words)  class4: 0:367 1:925 2:3577 3:5 4:129 5:12 6:74 7:16
                                           8:142 9:20 A:1568 E:45
    hi12[11:8] == C  ( 228 words)  class4: 0:40  1:56  2:53   3:33 5:42  9:4
```

Class 3 occurs **5 times in 6880** non-`C` words but **33 times in 228** `C`-prefixed words — a
~200× enrichment. Classes 0/1/2/3/5 are near-flat inside the `C` family while class 2 alone is
52 % of the non-`C` family. A field that is uniform inside one prefix and sharply skewed inside
another is not a class field there; it is data.

The host poke region makes it unambiguous. Over the 161 words the host writes to I-RAM 352+,
`class4` takes **all 16 values** (`0:59 1:27 2:1 3:4 4:10 5:21 6:7 7:7 8:8 9:1 A:1 B:2 C:4 D:2
E:4 F:3`), and 115 of those 161 words have `hi12[11:8] == 0xA`.

**INFERRED:** at least two instruction forms carry a wide immediate that *spans* bits [23:20]:

* the **`lo12 == 0x820` family** — 5 words in the header (I-RAM 15, 22, 29, 31, 40), **0 words in
  the entire 7108-word body corpus**, all with `hi12` starting `0xC`. Reading bits [23:12] as one
  12-bit immediate gives 0x292, 0x312, 0x457, 0x4B1, 0x1C0 (658, 786, 1111, 1201, 448). All
  exceed 383, so **none of them is an I-RAM address**; they are consistent with loop counts,
  timer reloads (TR0–TR3) or DRAM offsets.
* the **`hi12 == 0xA__` poke form**, which carries the 24-bit coefficients the host writes at
  runtime (e.g. `A06.1.1E.315`, `A37.6.D1.D15`, `A79.E.E1.C95`). The exact immediate alignment
  inside these is coefficient work and is deliberately left to
  `notes/kn5000-dsp-coefficients.md`; what matters here is only that bits [23:20] are part of it.

**Consequence for the encoding note:** its `class4` histogram is a *mixture* — a real class field
for the `hi12[11:8] != C` majority, and immediate data for the rest. The note's own observation
that "classes 0,3,4,6,8 are small and each dominated by a single `hi12` value" is exactly this
artifact seen from the other side.

---

## 7. Instruction families visible only in the scaffolding (MEASURED coverage, INFERRED reading)

`lo12` occurrence counts, scaffolding vs the 7108-word body corpus:

| `lo12` | header+stub | bodies | poke |
|---|---|---|---|
| `820` | 5 | **0** | 0 |
| `821` | 3 | **0** | 15 |
| `825` | 3 | **0** | 4 |
| `827` | 2 | **0** | 0 |
| `445` | 1 | **0** | 0 |
| `446` | 1 | **0** | 0 |
| `20C` | 2 | **0** | 0 |
| `00B` | 2 | 78 | 0 |
| `407` | 2 | 492 | 0 |

The `0x82x` family is **entirely absent from every effect body** and appears in the header, the
stub and the host pokes. Its shape:

```
    801.0.NN.821      (header 42, 50, 69;  poke 15x with NN = 00,09,0A,1E,26,50,6E,8C,90,97,9E,A6,AC,AE,B2)
    801.0.NN.825      (header 44, 52, 62;  poke 4x)
    801.0.NN.827      (header 43, 51)
    859.0.86.822      (header 77)
    C__.d.dd.820      (header 15, 22, 29, 31, 40 -- 12-bit immediate, see §6)
```

In the poke region a `801.0.NN.821` or `.825` word is **always the first word of the burst**, and
is followed by 1..30 `A__`-form data words. That is the classic "set the pointer, then stream
values" idiom.

**INFERRED, strong: `lo12 = 0x821 / 0x825 / 0x827` are three variants of a *load pointer with
8-bit immediate NN* instruction, `NN` in `addr8`, and the three variants select three different
pointer registers** — the chip has exactly six (CP, DP, BP1, BP2, PR1, PR2) plus BNK-R.
`lo12 = 0x820` is a fourth variant of the same family taking a wider (12-bit) immediate.

**SPECULATIVE:** the three used in the header's per-unit segments (`821`, `827`, `825` at
42/43/44 and 50/51/52) are the C-RAM pointer, the D-RAM pointer and the delay-line pointer being
rebased per unit — segment A uses `0x70, 0x6C, 0x25`, segment B uses `0x50, 0x64, 0x25`, i.e. two
per-unit bases and one shared.

Words that the scaffolding shares with the bodies are few and named here for completeness:
header 12 `880.1.20.2D5`, 26 `880.1.20.40B`, 27 `012.2.01.655`, 30 `09A.A.00.200`, 49
`400.1.0E.000`, 57 `000.2.01.000`; stub 80 `104.2.00.1CE`, 81 `102.2.00.000`. **51 of the
header's 57 distinct words (89 %) and 21 of the stub's 23 (91 %) appear nowhere in the bodies** —
the prediction that motivated this whole exercise, re-confirmed against the 7108-word corpus.

---

## 8. The stub at 60..82 vs the header (MEASURED / INFERRED)

What the stub does that the header does not:

* **It has no terminator.** The header has two; every effect body has one. The stub is the only
  block in the machine that does not self-terminate (§5).
* **It contains the two host-patched words** (64, 71). The header contains none. That is the
  point of the block: `DSP_AlgorithmChange` rewrites the stub, then the host pokes the two
  per-unit slots from the ROM parameter table at `0x01E5C7` (§4).
* **Its `class4`/`addr8` usage is class-1 heavy with a distinct `addr8` alphabet**:
  `0x8D, 0x8D, 0x8F, 0x8C, 0x8C, 0x85, 0x86, 0x06` where the header's class-1 words use
  `0x20, 0x30, 0x60, 0xC0, 0x8A, 0x0E, 0x0F`. Bit 7 of `addr8` looks like a modifier on a small
  index: the poke region contains the clean minimal pair `000.1.**06**.000` and
  `000.1.**86**.000` issued back to back with different payloads (transfers #1, #41/#42).
  **SPECULATIVE:** bit 7 of `addr8` in class-1 words is a direction or L/R-channel bit.
* **It ends by mirroring the header's opening.** Stub 79 `012.2.FF.1CE` is *bit-identical* to
  header 3, and stub 80 `104.2.00.1CE` differs from header 4 `204.2.02.1CE` only in `hi12`/`addr8`
  with the same `lo12 = 0x1CE`. **INFERRED: the stub re-runs the header's initialisation idiom**,
  which is exactly what an "algorithm change" routine should do — re-establish state that the new
  program depends on.

Firmware context (**MEASURED**, `kn5000_subprogram_v142.asm`): `DSP_AlgorithmChange` writes the
stub stream `0x01E63C` *first*, optionally calls `DSP_AntiReset_WithDebug`, then writes a chain of
further streams (`0x01E6BE`, `0x01E996`, `0x01EA12`, a 1-tick delay, `0x01E7C5`, `0x01E8A7`,
`0x01E891`). `EFF_WriteHeader` writes `0x01E496` only when a per-unit flag byte at `0x0001ED6D +
unit` is zero — so the header is re-uploaded conditionally per unit, which matches the capture's
three header uploads.

---

## 9. Falsified or explicitly not established

* **"A branch/call word encodes 84 or 200."** Searched exhaustively over every contiguous
  bitfield of all 83 words. **Not found** (§5). Every apparent hit is a shared-prefix artifact.
* **"`class4` [23:20] is an instruction class field everywhere."** **Partially refuted** (§6).
  It is data inside the `hi12[11:8]==0xC` family and inside the host poke form. The encoding
  note's histogram is a mixture of two populations.
* **"The `0x0E`/`0x0F` in the terminator is a relocated address."** Refuted independently of the
  encoding note's §7 argument: it is a unit index, confirmed three ways (§3).
* **"The patched words at 64/71 encode the body load address."** Refuted: slot 64 receives the
  *same* value `C40.5.40.445` before a body upload to 200 and before one to 84.
* **Not established:** any semantics for the terminator; the location of the COND field; any
  LC1–LC3 loop instruction; `BRAKST`; GF1–GF3 manipulation; DI/DO framing. The `0x82x` pointer
  family (§7) is the only instruction family with a defensible functional reading, and even that
  is INFERRED from position and idiom, not from a decode.

---

## 10. Most promising next steps

1. **Diff the header across models.** The KN5000 header is 60 fixed words in ROM. If the same
   chip appears in another Technics/Pioneer product with a different sample rate or a different
   number of active units, the words that change identify the rate/unit control. Cheap and highly
   diagnostic.
2. **Force a single-unit configuration.** `EFF_WriteHeader` is gated on `0x0001ED6D + unit`.
   A capture in which only one effect unit is active should exercise only one of the two header
   segments and would settle whether 40..49 / 50..59 really are per-unit — currently INFERRED
   from parallelism alone.
3. **Sweep the ROM parameter table at `0x01E5C7`.** It holds many {slot-64, slot-71, ×3} sets. If
   the DSP's actual delay time can be measured in the emulator for two sets whose bits [24:12]
   are in a 2:1 ratio, the delay-length reading in §4 becomes MEASURED rather than SPECULATIVE.
   This is the single cheapest route to a *semantic* anchor.
4. **Decode the poke burst.** `801.0.NN.821` + N data words is a pointer-set + stream idiom with
   161 captured examples and a known consumer (effect parameters). Correlating `NN` against which
   UI parameter was changed would give the first instruction on this chip with a *verified*
   meaning.

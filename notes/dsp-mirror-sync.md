# The SYNC pass — draining the adjudication queue into the code, and re-joining the two mirrors

NEC **uPD6383GF-3BA** (Technics SX-KN5000, IC311). Date: **2026-07-26**.
No hardware. Static analysis, the ROM corpus and the live emulator only.

Five decode passes (K3 pointers, K4 cursor, R2 result routing, R3 delay-DRAM, the
ALU) plus an adjudication landed within hours of each other. Each relayed
constraints to the others, and **several corrections were never applied to the
code** — `dsp/analysis/isa-adjudication.md` §9 is thirteen queued items, and the
two disassemblers that are supposed to be identical had been diverging all day.
This pass drains that queue on **both** sides and then measures what changed.

Labels used throughout: **MEASURED** / **PROVEN BY CONSTRUCTION** / **FORCED** /
**INFERRED** / **OPEN**. Nothing here is a recording.

---

## 0. Result in one page

| # | what | label |
|---|---|---|
| **A** | ★ **A LIVE MIS-DECODE FOUND AND FIXED.** `C00.A.47.407` — the frame terminator at I-RAM 82, the last word of every frame — passed `alu_decoded()` and was rendered *and executed* as an ordinary class-A multiply-and-store. It is **C-format**: bits [24:12] are one 13-bit immediate, so there is no `class4` to read. 1 word of 3057. | **MEASURED** |
| **B** | ★ **THREE MORE FALSIFIED LABELS WERE FIRING ON LIVE I-RAM**, not just on the ROM corpus. The four host-written call-vector words were labelled **"envelope / level detector"** (3 of 4) and one of them printed `cur+`, i.e. it was counted as advancing the coefficient cursor. They are `setvec`. | **MEASURED** |
| **C** | ★ **THE TWO MIRRORS NOW AGREE, AND IT IS CHECKED RATHER THAN ASSERTED.** `tools/upd6383d_diff.sh` runs both over all 3057 corpus words: **3057/3057 identical**. Before this pass they could not even be compared — nothing had ever run them side by side. | **MEASURED** |
| **D** | `hi12 == 0x801` is not an ALU opcode; the family is now a named predicate (`is_regload`) keyed on the **selector** `lo12[7:0]` and the **modifier** bit 11, not on two unrelated 12-bit constants. 10 corpus words. | **PROVEN BY CONSTRUCTION** |
| **E** | ★ **`ldptr` NO LONGER LOADS THE D-RAM OPERAND POINTER.** K3 withdrew that assignment; the executor was still performing it. Consequence, measured and reported rather than hidden: **nothing now loads `m_dp`**, and the frame's pointer walk no longer closes. | **FORCED** (the withdrawal) |
| **F** | ★ **THAT EXPOSED A NEW CONVERGENCE CRITERION.** Net D-RAM pointer displacement per frame is **−3** and must be **0**. It is falsifiable, it fails today, and it goes to zero exactly when the pointer walk is complete. | **INFERRED** (strong) |
| **G** | 6 of 123 distinct words moved from TRAP to DECODED and **none moved the other way**; words executed per frame **87 → 92**. | **MEASURED** |
| **H** | The safety property holds: with `DSPCFG` OFF the audio is **BIT-IDENTICAL** to the published pre-change binary. So is gate ON — every frame still traps. | **MEASURED** |

---

## 1. The corrections, and what each one cost or bought

### 1.1 ★ The C-format guard — the defect that was actually executing

`alu_decoded()` had a class guard, a routing guard and an operation guard, and no
**format** guard. But in `hi12[11:8] == 0xC` there is no `class4` and no `addr8` at
all — bits [24:12] are one 13-bit immediate. The frame terminator reads, through
the wrong window, as:

```
   C00.A.47.407   class4 = A      -> "a coefficient consumer"
                  lo12[10:6] = 10 -> LO_SRC_ACC   (anchored)
                  lo12[4:0]  = 07 -> LO_ACT_ST_BUS (anchored)
                  hi12[3:1]  = 0  -> HI_ACC_LOAD
```

— every guard satisfied. It was printed as `ld.st acc,c+` and, in
`execute_run()`, executed: a C-RAM read, a multiply, a **cursor advance** and a
D-RAM write, all invented. `run_frame()` was shielded only by a positional
`FRAME_WAIT_WORD` test that happens to sit above the decode.

MEASURED: exactly **one** corpus word leaves the executable set (1030 → 1029),
and it is that one.

This also closes an "open contradiction" the device's own comments carried: *is
the terminator a cursor consumer (class A) or immediate data (C-format)?* The
adjudication settles it — C-format wins, and the immediate is `2631 = 82*32 + 7`,
i.e. **A = 82 is the word's own I-RAM address**, which is what a self-addressing
wait looks like (2/2 for the machine's two `C00` words).

**The general rule, and it is the one that matters:** any predicate that selects
words by `class4` alone is wrong. The deciding argument in `isa-adjudication.md`
§1 is identity, not counting — `C40.1.80.000` and `C40.2.C0.000` are the *same
instruction on the same destination register*, differing only in the immediate,
and they read `class4` 1 vs 2 only because bit 8 of that immediate differs. The
guard is now in `alu_decoded()`, `is_dram()`, `cursor_fetch()`, `coeff_consumer()`
and `exec_addressing_only()`.

### 1.2 ★ FETCH IS NOT ADVANCE (K4, FORCED)

`bit 23` says a coefficient is fetched; **only `class4 == 0xA` moves the cursor
on**. The evidence is the PARAMETRIC EQ's ten class-8 words inside a cursor map
proven to the bit at 6 cells per band: if class 8 advanced, band *k* would start
at cell 7*k* and all 60 named roles would shift.

Three places were wrong:

* `exec_addressing_only()` did `if (cl & 8) m_cursor++`, i.e. it advanced on
  classes 8, 9, A, B, C, D, E **and** F. MEASURED that this changed nothing for
  the twelve input-stage words (four class-A, no class 8/9) — which is exactly
  why it had to be fixed before something else leant on it;
* both disassemblers printed `cur+` on every bit-23 word. They now print `cur+`
  where the cursor advances and `cur` where it merely fetches;
* a **decoded** class-8 word printed nothing at all about its fetch. It now
  renders `,c` (35 sites of `804.8.16.415`).

The split by region matters for a core and is now in the header comments:
bodies are exactly `8 -> 42, A -> 822` and nothing else, but the **kernel** also
has classes 9, C and D with bit 23 set. `bit 23 ⇒ class 8 or A` is a body-scoped
statement and must not be generalised.

### 1.3 ★ `hi12 == 0x801` and the bit-11 modifier

PROVEN BY CONSTRUCTION (K3 §1.1): the Sub CPU writer assembles the low byte of
`lo12` and then does a literal **`INC 8, WA`** into byte 3's low nibble — it
builds `0x800 | 0x021`, not the constant `0x821`. So `lo12[7:0]` is a register
**SELECTOR** and bit 11 is a **MODIFIER**, and `0x021`/`0x821` are one route plus
a flag. Both mirrors now model it that way (`lo_sel()` / `lo_imm()` /
`is_regload()`), and so does the executor's pointer trace, which used to match
three literal `lo12` constants.

`hi12` is deliberately **not** in the predicate — it cannot be, because
`859.0.86.822` is the same register-write form with other microword bits set.

**A residual tension, stated rather than smoothed over.** Selector `0x21`
*without* the modifier is the cursor rewind (MEASURED on algo 39). Selector
`0x21` *with* the modifier loads a pointer that is FORCED **not** to be that
cursor. Two readings survive and neither is picked:

* **(a)** `0x21` names the C-RAM addressing *unit*, and the modifier chooses
  "load the payload into the pointer" vs "rewind the cursor";
* **(b)** in this family bit 11 really is part of the selector, and the
  `INC 8, WA` construction is only how the assembler spells it.

Settled either way: they are not two unrelated codes, and they write different
registers.

**And a second conflict, also reported not resolved.** K3 §5.2 says
`859.0.86.822` "both names a register AND carries the store", because `hi12`
bit 4 is set. But bit 11 — the FORMAT ESCAPE — is set too, and this decoder's own
escape rule says bits[10:0] mean something else inside the escape, which is why
`hi12_text()` does not print `ST` there. Both cannot be right; the word is the
only site, so neither reading has a second data point. The annotation now says
so. The word keeps trapping.

### 1.4 The store target, gated on mode 2

R2 falsified `hi12 == 0x212 → writes mem[ptr], class-independent`: bit 4's target
is **mode-dependent** and `mem[ptr]` is the **mode-2** target, and the universal
reading manufactures four dead stores in the 23-word output stage.
`alu_decoded()` now refuses any bit-4 word outside mode 2.

**PREDICT-THEN-CHECK, and it hit:** predicted 0 words would leave the executable
set, because no class-8 corpus word carries bit 4. MEASURED **0**. A hole closed
before it opened, at zero cost.

### 1.5 The rest of the queue

Applied on **both** sides: the guarded delay-DRAM family with R3's address model;
`ldptr.d #$NN`; `setvec unitN,#A`; the `C00` wait rendering with the
self-address check; the internal register-file annotation with bit 7 = the unit
and the named cells `0x06`/`0x86`/`0x50`/`0xD0`; `(hi12 & 0xFFE)` family
predicates; the C-format **payload rule kept family-local** (`A = imm13 >> 5`
only inside `0xC40` — 57/57 in, 2/11 out); and the C-format test moved to the
**top** of `annotate()`, where its precedence is load-bearing.

Withdrawn from the C++ side (each had been emitted for months):
`hi12 == 0xC40 → envelope / level detector` (wrong at **all 61 sites**);
`880.1.60/20 → bracket OPEN/CLOSE` (they are a READ and a WRITE);
`880.1.30 → framing word, no DRAM information` (it is the body's **first** DRAM
access, 37/38); the settled-looking all-pass readings of `012.2.00.680` /
`000.2.00.419` (two assignments survive); `hi12 == 0x212` class-independent; and
`hi12[11:8] == 0xA → host-poke` (it fired on genuine in-program words).

---

## 2. ★ The two mirrors — from "assumed identical" to "checked identical"

They had genuinely diverged. For most of 2026-07-26 the **C++** side carried the
ALU decode and the K6 input stage; the **Python** side carried `ldptr.d`,
`setvec`, the C-format split, the guarded DRAM family and the register-file
annotation. Neither had the other's, and nothing noticed, because the two had
never been run side by side.

Both now carry the union. The Python additionally **retires** the three
hi12-specific forms the ALU decode supersedes (`202.A.dd.1D5 mac`,
`202.A.dd.1D4 mac.lb`, `212.A.dd.407 mulst`) — they are the same instruction seen
through a narrower window. Decoded corpus words go **273 → 1098**.

```
   tools/upd6383d_diff.sh
   MIRRORS AGREE -- 3057/3057 words render identically in C++ and Python
```

`tools/upd6383d_dump.cpp` is a ~50-line harness that lifts
`upd6383_disassembler::text()` out of MAME and prints it for a word list; the
script builds it, extracts the corpus and diffs. **Run it after touching either
file.** `dsp/verify.py`: **BYTE-MATCH OK** after regenerating all 40 listings.

One deliberate asymmetry, checked and harmless: `dsp_coverage.form_of()` no
longer has its own copy of the form table (it drifted once already — it mapped
every `hi12 == 0x801` word that was not `ldptr` to `rstcur`, which would have
mis-tallied `ldptr.d`). It is now `= dsp_disasm.form_of`.

**One rendering loss was found and repaired.** A decoded word prints no
`[annotation]`, and MEASURED that costs nothing on **381 of the 384** decoded
words that carry one: "writes mem[ptr] (bit 4)", "P-consumer stores latch A/B",
"read into carry latch A/B", "gain multiply" and "class 8 post-sum step" are all
things the field decode now says *properly* — and the two **agree** (`lo12`
`0x1D4` = source `mem[p]` + action CAP_TB really is "read into carry latch B",
which corroborates both readings). The remaining **three** are END-OF-BLOCK
words, and that is a control-flow fact orthogonal to the ALU. The decoded
rendering now keeps it.

---

## 3. What the executor does differently, MEASURED on the live machine

A/B: same harness, same isolated pre-init nvram, same Lua programme (boot, hold
C4 at frame 900, release at 1500, exit at 1740), 1,608,960 DSP frames.

| | pre | post |
|---|---:|---:|
| words executed per frame (of 285 slots) | **87** | **92** |
| ...of which addressing-only (K6) | 12 | 12 |
| distinct words trapping over the run | **123** | **117** |
| frames that trapped | 100.00 % | 100.00 % |
| input-stage audit: read back == latched | 1,383,360 / 0 mismatched | 1,383,360 / 0 mismatched |

**Six words moved from TRAP to DECODED and none moved the other way:**

```
   0801025825   801.0.25.825   was "pointer-load family sibling, target UNKNOWN"
   0801026825   801.0.26.825   ->  ldptr.d #$25 / #$26
   0C40540445   C40.5.40.445   was "envelope / level detector (INFERRED)"
   0C40640446   C40.6.40.446   was "envelope / level detector (INFERRED)"
   0C40A80445   C40.A.80.445   was "envelope / level detector (INFERRED)"  + cur+
   0C41900446   C41.9.00.446   was a generic C-format note                 + cur+
```

★ **This is a live confirmation of K5's call-vector result, seen for the first
time in the running machine.** The four decode to exactly the four values K5
DETERMINED from the host stream — `A = 42` and `84` on `lo12 = 0x445` (unit 0
disconnect / link) and `50` and `200` on `0x446` (unit 1) — and they are
host-written into I-RAM 64/71, so they never appear in the ROM corpus at all.
Two of them were being counted as coefficient-cursor advances.

### 3.1 ★ The pointer no longer closes — and that is the useful part

K3 FORCED that `lo12 = 0x821` addresses the **coefficient** space and is neither
the cursor nor the D-RAM operand pointer. The executor was still doing
`m_dp = addr8`. Removing it means **no decoded word loads the operand pointer**,
because the D-RAM origin is OPEN again (K3's `0x827` candidate was falsified at
**0 of 85** streams).

The visible consequence, reported rather than hidden: the input window used to
sit at a fixed `X = 0x8F` every frame and now walks `1E, 1B, 18, 15, …`.

```
   FRAME CLOSURE: net D-RAM pointer displacement, last frame -3 (must reach 0);
                  frames that closed 204480 of 1608960
```

The fixed `X` was an artefact of executing a withdrawn semantic. The drift is the
truth, and it is worth more, because it is a **criterion that can fail**: a
complete frame must leave the pointer where it found it — the host addresses
D-RAM state by *absolute* index (its tag-0x15 zero-fill is a contiguous block
based at `0x50`/`0xD0` in 87 of 91 parameter streams), so a body drifting a net
non-zero amount per sample would walk off its own state block within seconds.
**INFERRED (strong)**; it rests on the mode-1 register file and the mode-2 D-RAM
being one 256-cell RAM, which `isa-adjudication.md` §5.1 leaves **OPEN**.

Every word we cannot execute is a pointer move we do not make, so **−3 → 0** is a
direct progress metric for the decode. The input-stage audit still matches on
**all** 1,383,360 frames, so nothing about the sample path regressed.

---

## 4. Must-not-regress

| check | result |
|---|---|
| `-validate kn5000` | **clean**, exit 0, zero bytes of output |
| boots to the play screen | **yes** — `PMEM: 1-`, `16 Beat 1`, ♩=120, RIGHT1 Piano / RIGHT2 Bigband Brass / LEFT Modern E.P.1 |
| **`DSPCFG` OFF: audio bit-identical to the published pre-change binary** | **YES** — 1,609,921 frames × 3 ch = **4,829,763 samples, 0 differing**, reproduced twice (intermediate and final binaries) |
| `DSPCFG` ON vs OFF | **bit-identical** — every frame still traps, so every return is still discarded |
| the capture is capable of failing | **yes** — peak 10,129, 536,679 non-zero samples of 1,609,921 on ch1. A bit-identity test on silence proves nothing |
| `dsp/verify.py` | **BYTE-MATCH OK** — kernel + epilogue + 91 valid algorithm streams, 38 distinct images |
| two disassemblers | **3057/3057 identical** |
| build | 0 `error:` / `Error N`; binary mtime advanced, 74,397,336 bytes |

Cost: MAME average speed 89.70 % gate OFF, 70.29 % gate ON, same 33 s capture.

---

## 5. What is still OPEN, and what to do next

1. **The frame does not close (−3).** The single most useful number now
   available. Chase the pointer moves owed by the 193 trapping words.
2. **The D-RAM origin.** Nothing loads `m_dp`. `0x50`/`0xD0` is the
   better-supported candidate (47 of 85 streams vs 0 of 85 for `0x827`) but is
   **not** a pin, and the walk model behind that 47 is naive.
3. **The call sequencer still uses its OBSERVED target table** (`0x0E → 84`,
   `0x0F → 200`) even though `setvec` now writes real vector registers holding
   exactly those values. Wiring the sequencer to `m_vec[]` is the faithful
   mechanism and would make DISCONNECT (`42`/`50`) behave — but it changes the PC
   order of every frame, so it is a separate, measurable change and is
   deliberately **not** smuggled into a sync pass.
4. **The per-unit COEFFICIENT-BASE register.** K4 FORCED that the `0x00`→`0x90`
   rebase cannot be an instruction immediate. `rstcur` resets to 0, which is
   unit 0's value and a labelled placeholder.
5. `859.0.86.822`'s escape-vs-bit-4 conflict; the `0x20`/`0x22`/`0x27` selectors;
   `lo12 = 0x839`; and the DRAM direction field, which is in `lo12`/`hi12` and
   not in `addr8`.

---

## 6. Reproducing

```
tools/upd6383d_diff.sh                       # 3057/3057 mirror agreement
python3 dsp/tools/gen_dsp_disasm.py          # regenerate the listings
python3 dsp/tools/gen_dsp_flowcharts.py
python3 dsp/verify.py                        # BYTE-MATCH OK
python3 dsp/tools/dsp_coverage.py            # the coverage table
./build.sh                                   # grep the log for error: / Error N
```

# The biggest CPU-core gap: the AM33 `udf` instruction family is unimplemented

Diagnosed this tick by capturing the MN10300 core's "unimplemented opcode" logerrors
over a 20s boot. The core **skips an entire AM33 instruction family** — the `udf` /
`udfu` ops — and it does so **millions of times** on real, aligned firmware code.
This is almost certainly the root cause of several emulation bugs (the rhythm-menu
"all 8 Beat 1" display, and likely others), and is the #1 CPU-core item.

## The hits (20s boot, -seconds_to_run 20)
```
4,732,876  unimplemented opcode FB   (udf/udfu imm16, Dn)   -- spread across many PCs
  762,090  unimplemented F6 71       (udf07 d0,d1) @ 0x4840FBB9
  183,334  unimplemented opcode F9   (udf/udfu imm8, Dn)    @ 0x48486B18..3D
  ~5.68M    TOTAL unimplemented-opcode executions
```
The core (mn10300.cpp ~line 505) mislabels `0xF9/0xFB/0xFD` as "udf imm ... not
needed yet" and its `default:` case advances PC by the correct length + logs, so the
instruction is a **silent no-op** — the destination register keeps its stale value.

## These are REAL instructions, not a decode desync
Disassembly around a hot cluster (0x48486B00, a `setlb` AM33 hardware loop) shows
perfectly aligned code flowing INTO the udf ops:
```
48486b0a: mov 0x3f, d1
48486b0c: setlb                 ; AM33 loop-buffer
48486b0d: movbu (a2), d3
48486b0f: movbu (a1), d2
48486b13: add -0x80, d3
48486b15: add -0x80, d2
48486b17: mov d3, d1
48486b18: fb 01 ba 59  udf00 0x59ba, d1    ; <- real; result feeds...
48486b1c: fa c1 00 20  add 0x2000, d1      ;    ...the next op
```
`udf00 imm,Dn` writes Dn; skipping it corrupts the running computation.

## Encoding (from MAME's mn103dasm.cpp — decode is known, semantics are NOT)
| opcode | form | length | fields (op2 = byte after opcode) |
|--------|------|--------|----------------------------------|
| F5 op2 | `udf(20+op2>>4)  Dm,Dn` | 2 | Dm=`bits2-3`, Dn=`bits0-1` |
| F6 op2 | `udf(op2>>4)     Dm,Dn` | 2 | Dm=`bits2-3`, Dn=`bits0-1` |
| F9 op2 i8  | `udf/udfu i8, Dn`  | 3 | u=`bit2`, num=`(bit3?20:0)+op2>>4`, Dn=`bits0-1` |
| FB op2 i16 | `udf/udfu i16,Dn`  | 4 | same |
| FD op2 i32 | `udf/udfu i32,Dn`  | 6 | same |
So there are up to ~32 distinct operations (`udf00..udf35`, plus `udfu` variants),
each `<op> <imm-or-reg-src>, Dn`.

## The gap: udf SEMANTICS are unknown
- No upstream MAME **execution** core for MN10300 exists (only the disassembler),
  and the disassembler emits the placeholder name `udfNN` — it does not define what
  each op computes. So the semantics are a genuine RE gap (need the Panasonic
  MN103E/AM33 programming manual, or reverse-engineering from usage).
- Likely candidates (AM33 extended-ALU / DSP): multiply, multiply-accumulate,
  saturating ops, bit-field ops — but which `udfNN` is which is unconfirmed.

## Next steps (highest-value CPU-core work)
1. Obtain the AM33 `udf` semantics (manual) OR reverse-engineer the most-common ops
   (udf00 imm16/imm8, udf07 reg-reg) from their firmware usage contexts.
2. Implement them in mn10300.cpp (the decode/length is already correct; only the
   ALU effect is missing) starting with udf00/udf07.
3. Regression-test against the rhythm-menu names ("8 Beat 1" bug) — if a name
   computation runs through udf, implementing it should make the names distinct.
   Note: some udf usage is inside audio-DSP loops (setlb), so not every hit relates
   to the name bug; confirm the name-lookup path uses udf before assuming a fix.

## UPDATE: only TWO udf operations are actually used (udf00 + udf07)
Added op2 to the core's unimplemented-opcode log and re-captured a 20s boot. The
FB/F9/FD (imm) hits ALL have `op2>>4 == 0` → they are all **udf00**; the reg-reg
(F6) hits are **udf07** (op2=0x71) and **udf00** (op2=0x08). Distinct executed ops:
```
FB op2=02 udf00 imm16,d2  1,792,985
FB op2=01 udf00 imm16,d1  1,105,472
FB op2=03 udf00 imm16,d3    761,816
FB op2=00 udf00 imm16,d0    176,472
F9 op2=03 udf00 imm8, d3    148,608
F6 op2=71 udf07 d0,d1       617,844
F6 op2=08 udf00 d2,d0       (seen at 0x4840FB90; fewer hits)
```
So implementing **just udf00 and udf07** covers all 5.68M skipped executions.

### Context clues (semantics still TBD — need AM33 manual or deeper RE)
- **udf00** (0x48486B18, a `setlb` loop over two byte streams):
  `mov d3,d1 ; udf00 0x59ba,d1 ; add 0x2000,d1` — d1 (a signed byte) is combined
  with the imm16, so udf00 is a **binary op Dn=f(Dn,imm)** (NOT a plain move; the
  prior `mov d3,d1` would be dead otherwise). Looks arithmetic (multiply / fixed-
  point-scale candidate; 0x59ba≈0.70 in Q15).
- **udf07** (0x4840FBB9): `mov 0x10,d1 ; not d0 ; udf07 d0,d1 ; sub d1,d2 (d2=15-d1)`
  — looks like a bit-count / normalize (clz/ffs candidate).
- **udf00 reg-reg** (0x4840FB90): `udf00 d2,d0 ; mov d0,(d1,a3) ; cmp 0x40,d3 ; blt`
  — a 64-iteration data-transform loop; Dn=f(Dn,Dm).

### Next
Determine udf00/udf07 semantics (Panasonic MN103E/AM33 manual, or reverse-engineer
by tracing how the results are consumed / an emulator hypothesis-test), then
implement the two ops in mn10300.cpp and regression-test the rhythm-name bug.
The core's log now includes op2 (small diagnostic improvement, kept).


## IMPLEMENTED: udf00 = signed multiply-by-immediate (F9/FB/FD)
RE-confirmed and implemented. The F6 `op2>>4==0` form is the core's existing
**mulq** (signed 64-bit multiply, low->Dn, high->MDRQ) -- so the imm forms
(F9=imm8, FB=imm16, FD=imm32) with `op2>>4==0` are the same signed multiply with an
immediate source. Confirmed by the firmware's fixed-point usage:
`mov d3,d1 ; udf00 0x59ba,d1 ; add 0x2000,d1 ; asr 14,d1` = `(d3 * 0x59ba + 0x2000) >> 14`
(Q14 coefficient-multiply; immediates are signed filter coeffs 0x59ba/0xe9fa/0xd24f).
Implemented in mn10300.cpp's default case (Dn = low32(Dn*sx(imm)), MDRQ=high32, set
NZ, clear CF/VF). Result: the 5.68M unimplemented-opcode executions/boot dropped to
**979K (only udf07 F6-71 remains)**; boot + display unaffected.

## STILL OPEN: udf07 (F6 op2>>4==7, 979K hits) + the rhythm-name bug
Implementing udf00 did NOT fix the "all 8 Beat 1" rhythm-menu bug, so that bug does
not run through udf00. udf07 is the only remaining unimplemented op (an AM33 F6/MAC-
unit variant; context `mov 0x10,d1 ; not d0 ; udf07 d0,d1 ; sub d1,d2(=15-d1)` looks
like a bit-count / normalize). NEXT: RE udf07 across more usages, implement, and
re-test the rhythm names; if still broken, the name bug is a separate (non-udf) issue.


## udf07 characterized (normalize/bit-search) -- NOT implemented (too risky to guess)
udf07 is a SINGLE hot site: 0x4840FBB9, hit 979K/boot, inside one function
(0x4840FB9C). That function is a **fixed-point normalize**:
```
d0 = *(sp+0x10)          ; a value computed by call 0x4840FC3A
not d0                   ; d0 = ~d0
udf07 d0, d1(=16)        ; d1 = udf07(~d0, 16)  -- a bit-position (0..15)
d2 = 15 - d1             ; exponent
d3 = d2 ; asl 1,d3 ; movbu (d3,a2),d1   ; table lookup by exponent
d2 += 0x11 ; asl d2,d0                    ; shift by the exponent
```
So udf07 returns a bit position (MSB/normalize count of ~d0 within a 16-bit field;
the `16` in d1 is a field-width/start parameter) and the result drives a
table-based normalize (log/reciprocal/sqrt-style). It belongs to the AM33 F6/MAC
family (op2>>4==7, alongside mulq=0, mulqu=1, sat16=4, sat24=5, getMACregs=C/D/F).
The exact bit-search semantics (inclusive/exclusive, the role of the 16) need the
AM33 manual; a wrong guess would corrupt a 979K-hits/boot function, so it is left
skipped for now (its result currently degenerates to d3 = 15-16 = -1).

## Rhythm-name bug ("all 8 Beat 1") is NOT a udf bug
Implementing udf00 did not change it, and udf07 is an isolated fixed-point-math
function (unrelated to text/name lookup). So the rhythm-name-list bug is a SEPARATE
issue (candidate: the style list is not populated from its source / a data-table or
device gap), to be investigated independently of the udf work.

## SOLVED (2026-07-06): udf07 = BSCH (bit-search); fixes the boot-splash JPEG decode
The software JPEG decoder produces the boot splash. It was decoding to pure noise. Diagnosis:
- The splash frames ARE standard JPEGs in the table ROM (music-notes-over-Earth @0x480566E8,
  KN7000 logo @0x48066517); a reference PIL decode shows the real images. So the decoder was
  broken, not the data.
- Captured the unimplemented ops hit during the splash decode (dedup'd fprintf(stderr) at the
  core's skip sites, run WITHOUT -log to avoid the I/O-log flood that starves the emulation):
  **exactly one** -- `F6 op2=71` = **udf07 d0,d1** @0x4840FBB9 (the Huffman leading-run step).
- Traced the block: `not d0; udf07 d0,d1; d2=15-d1; W=table[a2+(15-d1)*2]; d0=(~x<<(32-d1))>>(32-W)`
  -- a table-driven variable-length (Huffman) decode. Tried clz32, clz16, leading-ones (all
  still noise), then **bit-search** -> the splash decodes PIXEL-CLEAN.

**udf07 Dm,Dn = BSCH: Dn = bit position (0..15) of the most-significant set bit in Dm's low 16
bits (0 if none).** Implemented in execute_f6 case 0x7 (mn10300.cpp). Verified: both splash
frames render exactly like the reference JPEG decode. commit 457ec48.

Lesson / method for the remaining udf ops: (1) dedup'd stderr capture finds WHICH op and WHERE;
(2) disassemble the using-block to get the algorithm; (3) if a reference exists (here: PIL on
the same JPEG), the visual/quantitative match confirms the semantics. The other udf variants
(udf01..06, 08..35) are still unknown but can be RE'd the same way as they surface.

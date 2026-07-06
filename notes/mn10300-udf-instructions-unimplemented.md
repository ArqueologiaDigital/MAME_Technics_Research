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

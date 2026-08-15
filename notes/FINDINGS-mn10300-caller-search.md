# MN10300 caller search: an off-by-two that manufactures "dead code"

*2026-08-15. Tool: `tools/mn10300_callers.py`.*

## The defect

MN10300's call instruction carries a register-save list:

```
4849fe30: cd 70 ff c0 08   call 0x4849fda0, [d2,d3], 8
```

The **call itself** saves `d2`/`d3`, so the compiler emits callers that enter **two bytes past
the callee's entry**, skipping its own `movm` prologue:

```
4849fd9e: cf c0   movm [d2,d3], (sp)   <- the function entry
4849fda0: 0c      clr  d3              <- where callers actually land
```

A caller search on the entry address therefore finds nothing, and a routine with real callers
looks unreachable. Combined with this project's already-recorded rule that *static caller search
does not work in these ROMs* (routines entered by `calr` and jump tables), it is easy to arrive
at a confident "dead code" verdict that is simply wrong.

## What it already cost

`notes/FINDINGS-expansion-buses-and-code-exec.md` recorded the `0x97800000` checksum stub at
`0x4849FD9E` as having *"0 callers and 0 stored pointers — unreachable"*, and built an argument
on it: that HD-SX3/XAPR support *"once existed in this codebase and was cut"* rather than being
left dead.

**It has two callers**, both at entry+2:

```
0x4849FE30  ->  0x4849FDA0   (MainRomTestFunc)
0x484A501C  ->  0x4849FDA0
```

The stub is not dead code; it is a service-mode test, reachable only through the factory test
menu — which is a different and much weaker claim than "unreachable". The broader XAPR argument
in that note does **not** rest on this stub alone (it rests on 0 pointer-loads, 0 `"XAPR"`
strings and 0 thunks against a positive control of 20/21 on the KN6000), so that conclusion
stands; only the "fossil" sentence is corrected.

## What it did NOT cost — a claim that survives re-checking

The driver comment in `kn7000.cpp` calls the parallel-FDC engine at `0x484A4FBA` unreachable dead
code, and uses that to justify "bit15 of the `0x98070000` strap gates nothing observable".
Re-run with the corrected decoding, **that holds**:

| address | direct callers (skew 0 and +2) | stored pointers |
|---|---|---|
| `0x484A4FBA` (FDC engine) | **0** | 0 |
| `0x4854D835` (FDC init) | 1 — `0x484A4FE3`, *inside* the dead engine | 0 |

Exactly what the comment says. The scanner confirms it independently rather than overturning it.

## Honest limits

* The image contains **596 indirect `calls (An)` sites**. Their targets are registers, so no
  static scan can resolve them: **"0 direct callers" is never proof of dead code**, only absence
  of one kind of evidence.
* The scanner decodes the byte stream linearly and cannot tell code from data, so a table can
  contain a byte sequence that looks like a call. Hits are candidates; confirm with `tools/dis.sh`.
* Displacements are taken PC-relative from the opcode byte. That matches the disassembler on
  every case checked here, including the two-byte-skewed ones.

## The sweep: every MN10300 reachability claim in the notes, re-checked

Having found one wrong, the rest were re-run with the corrected decoding (skews 0 and +2).
**One correction, six confirmations** — the defect was not systemic:

| address | claim | re-check |
|---|---|---|
| `0x4849FD9E` | "0 callers — unreachable" | ❌ **wrong** — 2 callers at +2 |
| `0x484A4FBA` | FDC engine, dead code | ✅ 0 callers |
| `0x4854D835` | FDC init, only called from inside the dead engine | ✅ exactly 1 caller, `0x484A4FE3` |
| `0x484057D6` | unreachable | ✅ 0 callers |
| `0x484A5075` | unreachable | ✅ 0 callers |
| `0x484A50A9` | unreachable | ✅ 0 callers |
| `0x484D7490` | unreachable | ✅ 0 callers |

⚠ `0x4854BF60` also appeared in the sweep but is **not** a dead-code claim — it is the real
serial disk transport, reached through *runtime driver-method pointers*. "0 direct callers" is
the expected result there and means nothing on its own, which is the whole caveat above in one
example.

## Reproduce

```
python3 tools/mn10300_callers.py 0x4849FD9E     # 2 callers, both at +2
python3 tools/mn10300_callers.py 0x484A4FBA     # 0 -- the dead-code claim survives
```

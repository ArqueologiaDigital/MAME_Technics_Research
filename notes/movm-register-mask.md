# MN10300 `movm` register-mask — empirical findings

The `movm`/`call`/`ret` instructions carry an 8-bit register-list mask. Getting
its bit→register mapping and stack layout right is critical for the CPU core (a
wrong length or SP delta corrupts every stack frame). This note records what the
KN7000 program ROM actually uses, so the core can be correct where it matters and
honest about the rest.

## Bit → register mapping

From the MN10300 disassembler's `f_reg_spec` (mn103dasm.cpp) and the ISA:

| mask bit | register(s) |
|----------|-------------|
| 7 | D2 |
| 6 | D3 |
| 5 | A2 |
| 4 | A3 |
| 1 | the group **{D0, D1, A0, A1, MDR, LIR, LAR}** (7 registers, 28 bytes) |
| 0, 2, 3 | AM33 extended-register groups the disassembler does not resolve |

## What the firmware actually uses

Method: disassemble both code regions of `kn7000_program.rom` with MAME `unidasm`
and tabulate the register list of every `movm`/`ret`/`retf`, plus walk each of the
443 known functions from its entry with the validated length decoder.

Results:

* **22,771 of 22,808** `movm`/`ret` instructions (**99.84%**) use **only** bits
  4-7 — i.e. the standard callee-saved set **D2/D3/A2/A3**.
* Token counts across all `movm`/`ret`: `d2` 16924, `a2` 12487, `d3` 12069,
  `a3` 8562; the bit-1 group ("other") 6, and the AM33 groups
  ("other0/2/3") 41 — and those 47 are essentially all inside data that the
  linear disassembly swept as code.
* **Function prologues use bits 4-7 exclusively** (322 of 448 known entries start
  with `movm [subset of d2/d3/a2/a3],(sp)`; the other 126 are leaf functions with
  no register save).
* **Prologue mask == epilogue `ret` mask in all 320 checked functions
  (0 mismatches)** — save and restore are symmetric, so SP round-trips regardless
  of the intra-frame byte order.

## Consequence for the emulator

The core implements bits 4-7 (D2/D3/A2/A3) fully — this covers **all real code** —
and bit 1 (the 7-register group) for completeness. The three AM33 extended bits
(0, 2, 3) are logged and left unmodelled; they never occur in real KN7000 code and
would need the AM33 programming manual (and the E0..E7 register file) to implement.

This also tells us something about the build: the KN7000 firmware was compiled for
the **base MN10300** register model (no AM33 extended registers in the calling
convention), consistent with the disassembler not needing to decode them.

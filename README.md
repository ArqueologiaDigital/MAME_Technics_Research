# KN7000 MAME driver (work in progress)

A **draft** MAME driver for the Technics SX-KN7000, plus the beginnings of a
**Panasonic MN10300 CPU execution core** that the driver needs. It is laid out as
an *overlay* on the MAME source tree: every file sits at the path it would occupy
inside MAME, so integrating it is a matter of copying the files in and adding two
build-registration lines (see [`INTEGRATION.md`](INTEGRATION.md)).

It lives in its own repository — separate from the user's MAME checkouts, which
are on unrelated WIP branches — so this early, non-building work never disturbs
them.

## Why a new CPU core is needed

The KN7000's main CPU is a **Panasonic MN10300/AM33**. MAME today ships only an
MN10300 *disassembler* (`src/devices/cpu/mn10300/mn103dasm.cpp`) — there is **no
execution core**. So a driver cannot run until such a core exists. The closest
existing template is MAME's MN10200 core (`src/devices/cpu/mn10200/`), and the
existing MN10300 disassembler gives us the full instruction decode as a
reference.

## Contents

```
src/devices/cpu/mn10300/mn10300.h     MN10300 CPU device — declaration
src/devices/cpu/mn10300/mn10300.cpp   MN10300 CPU device — execution core (partial)
src/mame/matsushita/kn7000.cpp        KN7000 machine driver
INTEGRATION.md                        how to drop these into a MAME tree + build
```

The existing `src/devices/cpu/mn10300/mn103dasm.{cpp,h}` (the disassembler) stays
in MAME; the core reuses it for the debugger.

## Status — this is an early draft, not a working emulator

A full MN10300 core and a complete KN7000 machine are a large, multi-stage
effort. What this repo aims to establish first:

- [x] Repository / overlay layout and build-integration recipe ([`INTEGRATION.md`](INTEGRATION.md))
- [x] MN10300 CPU device scaffold (MAME `cpu_device` boilerplate, 32-bit memory
      space, state registration for the debugger, save-state, disassembler hookup)
- [x] MN10300 execute loop with a fetch/decode/execute structure
- [x] A first batch of MN10300 instructions: the single-byte group (clr, ext*,
      inc, mov/cmp/add reg&imm8, mov (aM)/(disp8,sp), branches, `bra`, `nop`,
      `jmp` disp16/disp32, `call`, `ret`, `movm`) plus the `0xFC` 32-bit-immediate
      family (`mov`/`add`/`sub`/`cmp`/`and`/`or`/`xor` imm32) and `add imm8,sp`
- [x] KN7000 machine driver: memory map, ROM regions (real CRC/SHA1), LCD placeholder
- [x] **Instruction-length decoder validated** against MAME unidasm over the real
      ROM — 656,050 legal instructions, 0 mismatches (see [`tests/`](tests/)). The
      core uses it to stay aligned/steppable over unimplemented opcodes.
- [x] The prefixed groups `0xF0` (reg-indirect moves + call/jmp/ret `(aM)`),
      `0xF1` (cross-type reg-reg arith), `0xF2` (logical / mul / div / shift /
      special-reg moves), `0xF3`/`0xF4` (indexed load/store), the `0xFA` 16-bit
      family, and `0xFE` (bit ops on abs) — each consuming the validated length
- [ ] **Verify by building MAME** (not yet done — see caveat below) and stepping boot
- [x] **`movm`/`call`/`ret` register mask resolved** — empirically, 99.84% of real
      KN7000 code uses only D2/D3/A2/A3 (bits 4-7); prologue mask == epilogue mask
      in all 320 checked functions. Bits 4-7 + the bit-1 group are implemented;
      the AM33 bits (never used here) are logged. See [`notes/movm-register-mask.md`](notes/movm-register-mask.md)
- [x] `0xF8` disp8 moves/shifts/logic/ext-branches and `0xFC` (disp32,sp)/(abs32)
      load-stores implemented
- [x] `setlb` + `Lcc` loop cache — **~99.94% of all real instructions now
      implemented** (measured against unidasm over both code regions). The
      remaining 0.06% are unused `udf*` coprocessor opcodes (data swept as code)
      and the rare `lra`.
- [ ] `F0` rti/trap and div-by-zero traps
- [ ] Interrupts / exceptions, cycle timing
- [ ] Peripherals (LCD controller, tone generators, DSP, FDC, panel sub-CPUs,
      SD/USB) and sound

> **Caveat — not yet build-tested.** These files have not been compiled against
> MAME in this environment (a full MAME build is heavy). They are written to
> MAME conventions and internally consistency-checked (every method defined is
> declared; the instruction semantics follow the spec derived from the existing
> disassembler), but expect to iterate on compile errors and, especially, to
> confirm the `movm`/`ret` register-list handling before the core runs real code.

The extracted flash images the driver loads (`kn7000_program.rom`,
`kn7000_table.rom`) are produced by the sibling `kn7000_extraction` repo, and the
[`kn7000_disassembly`](../kn7000_disassembly) repo's recovered symbols
(`kn7000.sym`, 444 named functions) are the reference for what the code does.

## License

The MAME-derived files follow MAME's licensing (BSD-3-Clause for the CPU core, to
match the existing MN10300 disassembler; GPL2+ for the driver, to match the
KN5000 driver). (c) 2026 Felipe Correa da Silva Sanches.

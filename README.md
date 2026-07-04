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

- [x] Repository / overlay layout and build-integration recipe
- [ ] MN10300 CPU device scaffold (MAME `cpu_device` boilerplate, memory space,
      state registration, disassembler hookup)
- [ ] MN10300 execute loop with a fetch/decode/execute skeleton
- [ ] A meaningful subset of MN10300 instructions (the ones the KN7000 boot code
      uses: `mov` immediates, `movbu`/`movhu`, `add`/`sub`/`cmp`, branches,
      `call`/`ret`, `jmp`, `movm`, `nop`)
- [ ] KN7000 machine driver: memory map, ROM regions, LCD screen placeholder
- [ ] The long tail: full instruction set, interrupts, peripherals (LCD, tone
      generators, FDC, panel sub-CPUs, SD/USB), sound

The extracted flash images the driver loads (`kn7000_program.rom`,
`kn7000_table.rom`) are produced by the sibling `kn7000_extraction` repo, and the
[`kn7000_disassembly`](../kn7000_disassembly) repo's recovered symbols
(`kn7000.sym`, 444 named functions) are the reference for what the code does.

## License

The MAME-derived files follow MAME's licensing (BSD-3-Clause for the CPU core, to
match the existing MN10300 disassembler; GPL2+ for the driver, to match the
KN5000 driver). (c) 2026 Felipe Correa da Silva Sanches.

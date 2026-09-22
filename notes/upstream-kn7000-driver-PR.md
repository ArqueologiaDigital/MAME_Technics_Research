# Upstream PR: the KN7000 driver

Branch `technics-kn7000-driver`, worktree `~/compartilhado/mame-pr-kn7000drv`, cut from
`upstream/master`.

## Where the RE archaeology lives

The upstream copies are **stripped**: comments cut from 42.8 % of lines to the band the
merged Technics drivers sit in (`kn5000.cpp` 22.8 %, `wsa1.cpp` 28.6 %). Nothing is lost —
every stripped comment is in this overlay, which is the permanent home:

| upstream file | full annotated source here |
|---|---|
| `src/mame/matsushita/kn7000.cpp` | `kn7000_mame/src/mame/matsushita/kn7000.cpp` |
| `kn7000_cpanel.*`, `kn6000_cpanel.*`, `kn_cpanel.*` | same paths in this overlay |
| `kn7000_tonegen.*`, `kn6000_tonegen.*`, `kn_tonegen.*` | same paths in this overlay |
| `src/devices/cpu/mn10300/mn10300.*` | same path in this overlay |

Overlay state the PR was cut from: **`5e8e20d`**. To read the derivation behind any line
in the PR, open the same file here at that commit.

The deeper narrative — clock-tree derivation, capture logs, address archaeology — is in
`notes/` and the blog, not in either copy of the code.

## What is deliberately NOT in the PR

Three things, all for the same reason: they are data the emulator invents, and upstream's
already-merged `kn7000.cpp` is honest about not having them.

1. **`wavepack` region** (`kn7000_waves_synthetic.rom`, 16 MiB). Donor samples from the
   KN5000 IC307 dump, reshaped for the KN7000. The real wave ROMs IC203/204/207/208 are
   undumped, and upstream carries them as `NO_DUMP`, which is correct.

2. **`rhythms` region** (`kn7000_rhythms_synthetic.rom`, 4 MiB). A built container standing
   in for a style-name resource that lives on the undumped data flash.

3. **KN6000/KN6500 `table` regions** loading `kn7000_table_*.rom` as `BAD_DUMP`. That is
   one model's ROM standing in for another's; upstream has `qsigx3c16008.ic13` /
   `qsigx3c16007.ic14` as `NO_DUMP`.

`BAD_DUMP` marks a real dump believed faulty. It does not mean "a file we constructed", and
using it that way would put a CRC and a filename on something that never existed as a chip.
These stay in the overlay, where they are useful for listening and are labelled as what they
are.

**Consequence, stated so it is not a surprise:** without the wavepack the tone generator
plays its fabricated default sine — which is what its MAME name already says, *"KN7000 Tone
Generator (firmware-driven, placeholder timbre)"* — and without the rhythms region every
style row reads `8 Beat 1`.

## The DSP question

The KN7000's effects DSP is **IC306, an ADSP-21065L SHARC**, which MAME already emulates;
the driver instantiates it at 66 MHz and runs it. It is not a placeholder and needs none.

The `uPD6383GF` skeleton device belongs to the **WSA1R** (IC5/IC6/IC30) and to the
KN5000/KN1500 family. `grep -c 6383` over every KN7000 source returns 0. The two products
do not share the part, so there is no WSA1R placeholder to reuse here.

What the KN7000 does have unresearched is the pair of custom tone generators IC201/IC205,
whose wave ROMs are undumped — see the exclusions above.

## Dependency

Upstream has only the MN10300 **disassembler**. The driver needs the execution core
(`src/devices/cpu/mn10300/mn10300.*`, ~2000 lines) plus its `scripts/src/cpu.lua`
promotion, so that goes first and the driver PR sits on top of it.

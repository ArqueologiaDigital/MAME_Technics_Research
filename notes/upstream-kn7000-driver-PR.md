# Upstream PR: the KN7000 driver

Worktree `~/compartilhado/mame-pr-kn7000drv`, cut from `upstream/master` `ae30b778cae`.

## Final state — the DSP is a placeholder

| branch | files | +/- | state |
|---|---:|---|---|
| `technics-mn10300-core` | 4 | +2023/-1 | builds; validates |
| `technics-kn7000-driver-skel` | 19 | +8113/-96 | builds; five machines validate; **boots to the play screen** |
| `technics-cpulua-drc-token` | 1 | +1/-1 | independent bug fix, not needed by the driver |
| `technics-sharc-21065l` | 5 | +931/-86 | **parked** — see below |

### Why the SHARC work is parked

The instruction was that the DSP chips stay as placeholders while research continues.
An earlier cut of this PR shipped a full ADSP-21065L implementation instead, which is the
opposite. The driver now carries **IC306 as a skeleton**, in exactly the shape the merged
`wsa1.cpp` uses for its uPD6383GF DSPs:

    DEFINE_DEVICE_TYPE(KN7000_DSP, kn7000_dsp_device, "kn7000_dsp", "ADSP-21065L (skeleton)")

That is the part of the WSA1R that is genuinely reusable here — the *pattern*, not the
device. The chips differ: the KN7000's effects DSP is an ADSP-21065L, the WSA1R's are
uPD6383GF, and `grep -c 6383` over every KN7000 source returns 0.

What the skeleton keeps is the host-port upload protocol, which is the driver's own decode
of how the MN10300 talks to the DSP: the block framing, the PM/DM modes and the word
counting all still run, they simply do not deliver into a core. What went with the DSP is
the audio bridge that existed only to exchange frames with it; the tone generator now
routes to the speakers directly, with the front-panel volume applied through
`set_output_gain`.

Dropping the DSP also dropped two dependencies. The driver no longer needs the ADSP-21065L
device, and therefore no longer needs the `DRC_CPUS` fix that a SHARC-only build requires.
Both stay as separate branches for when the DSP research lands.

Boot check: `./kn kn7000 -str 45` reaches `PMEM: A-`, `8 Beat 1`, tempo 120, the three part
names and the panel layout — the same screen as with the DSP running, since the effects were
never audible in a still frame.

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

## Dependencies — four PRs, not one

Building the driver against `upstream/master` surfaced three prerequisites, two of them
missing devices and one a real build-script bug.

| # | PR | files | state |
|---|---|---|---|
| 1 | `scripts/src/cpu.lua: DRC_CPUS names a CPU token that does not exist` | 1 | one token |
| 2 | `cpu/mn10300: add an execution core` | 4 | builds, `-validate kn7000` exits 0 |
| 3 | `cpu/sharc: add the ADSP-21065L` | 5 | ~1000 lines |
| 4 | `matsushita/kn7000: the driver` | 15 | needs 1-3 |

**1 is a bug we can now prove.** `DRC_CPUS` lists `"ADSP21062"`; the SHARC's actual token,
declared at `cpu.lua:252` and tested at `:255`, is `"ADSP2106X"`. No CPU named `ADSP21062`
exists, so a SHARC never sets `CPU_INCLUDE_DRC`, and any build whose only DRC-using CPU is
the SHARC fails to link with ~1700 undefined references into `drcuml`/`uml`. A full MAME
build hides it because MIPS3, POWERPC and friends pull the DRC in anyway. Reproduce:

    make SUBTARGET=kn SOURCES=src/mame/matsushita/kn7000.cpp REGENIE=1

The 2026-09-19 plan already listed this at position 5 from a static reading. This is the
first time it has been made to fail.

**3 is not just a new device type.** The ADSP-21065L has its internal RAM at 0x8000 rather
than 0x20000, does not populate `m_blocks`, and therefore needs its own memory maps and DRC
memory routing — which is most of the ~550 changed lines in `sharcdrc.cpp`.

Upstream has only the MN10300 **disassembler**, so 2 ships the execution core plus its
`cpu.lua` promotion.

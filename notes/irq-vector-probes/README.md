# How a maskable interrupt reaches its handler on the MN10300 Technics machines

**The question:** the MAME driver used to carry a `namespace fw` block of firmware
addresses, including two KN7000 interrupt handlers, on the belief that the KN7000
"installs two handlers in its self-loaded library and splits the levels between
them" while its siblings use a trampoline. A driver that knows one firmware
revision's internals will not be accepted upstream, so: what does the hardware
actually do?

**The answer.** The MN10300 vectors a maskable interrupt of level L to
`base + IVAR[L]`, where IVAR0..IVAR6 are seven 16-bit registers at
`0x20000000 + L*4` holding the *low 16 bits* of that level's entry point. Every
one of the five firmwares writes `IVAR0..IVAR6 = 0` once at boot and never
touches them again, then builds a six-byte `nop ; jmp <handler>` thunk at the
base of work RAM — writing it through the uncachable `0x90000000` view and
computing the jump displacement against the thunk's own execution address in the
cachable `0x50000000` one. So **one vector serves all seven levels on every
machine**, and the handler address is the firmware's business, not the driver's.

The KN7000 was never special. `0x4C03DDA0` — the "quick dispatcher" the driver
named — is referenced by nothing in the whole 4 MB image: no literal, no branch.
It is a dead alternate build of the same handler.

**Naming:** the registers are **IVAR**, per the manufacturer. Earlier revisions of
this note and of the driver called them IVR, which is what GNU's simulator calls
its member variable.

## Where the architecture comes from

Two independent sources, neither of them this project's inference:

* **Matsushita, *MN1030/MN103S Series Instruction Manual*.**
  * Memory Layout: "One assignment that is common throughout, however, is the
    location of the reset vector. **It is always at 0x40000000.**"
  * Boiler Plate Code Sequences, interrupt-handler example:
    `IVAR0 equ 0x20000000` … `IVAR6 equ 0x20000018`, each written with `movhu`
    under the comment *"Set to lower 16 bits of entry point for level interrupt
    handler"*; the nonmaskable handler assembled at `org 0x40000008`;
    `IAGR equ 0x34000200`, `G01CR equ 0x34000100` — the same INTC addresses the
    CPU core already models.
  * AM32 memory map (p.13, rendered — the figure does not survive `pdftotext`):
    on-chip peripherals at `0x20000000-0x3FFFFFFF`, external memory
    `0x40000000-0x7FFFFFFF` **cachable** and the same memory
    `0x80000000-0xBFFFFFFF` **uncachable**. That is exactly the `+0x40000000`
    window pairing these machines use throughout — `0x50`/`0x90`, `0x4C`/`0x8C`,
    `0x44`/`0x84` — so it is architecture, not a board quirk.
* **GNU binutils/gdb, `sim/mn10300/dv-mn103cpu.c`.** Models the same block as
  `unsigned16 interrupt_vector[7]` decoded at offsets `0x000`…`0x018` of a
  register block based at `0x20000000` (with IMCR at `0x020` and CPUM at
  `0x040`), and delivers a level interrupt to
  `0x40000000 + interrupt_vector[pending_level]` (line 250), a nonmaskable one
  to `0x40000008`.

A copy of the manual is at `~/compartilhado/kn7000_scratchpad_snapshot/mn103s_manual.pdf`;
it is text-searchable, but every memory-map figure must be **rendered**
(`pdftoppm -f 27 -l 27 -r 130 -png`) because `pdftotext` interleaves the columns
of the three core variants into one unreadable stream.

## Run it

```sh
python3 notes/irq-vector-probes/irq_vector_mechanism.py  ~/compartilhado/technics_romsets
python3 notes/irq-vector-probes/vector_table_layout.py   ~/compartilhado/technics_romsets
python3 notes/irq-vector-probes/vector_table_layout.py   --selftest
python3 notes/irq-vector-probes/peripheral_page_probe.py ~/compartilhado/technics_romsets
python3 notes/irq-vector-probes/peripheral_page_probe.py --selftest
python3 notes/irq-vector-probes/io_window_offset0_alias.py
```

`extract_for_unidasm.py` produces every disassembly quoted here — it
de-interleaves a romset and writes one address window to a file, because unidasm
does not seek and neither ROM half disassembles alone:

```sh
python3 notes/irq-vector-probes/extract_for_unidasm.py \
        ~/compartilhado/technics_romsets/kn7000.zip 0x484100A0 0x30 /tmp/w.bin
~/compartilhado/mame/unidasm /tmp/w.bin -arch mn10300 -basepc 0x484100A0
```

Both de-interleave each romset the way `ROM_LOAD32_WORD` does (even half supplies
bytes 0,1 of each 32-bit word, odd half bytes 2,3; the image loads at
`0x48400000`).

`irq_vector_mechanism.py` checks two things per image: exactly two thunk builders,
and each of the seven IVARs written exactly once. **PASS on all five, 2026-09-23:**

| romset | thunk 0 handler | thunk 1 handler | builder | IVAR writes |
|---|---|---|---|---|
| kn7000 | `0x4C03DE26` | `0x484D77CF` | `0x48410070` | `0x484100A4`-`0x484100C8` |
| kn6000 | `0x4C3F7942` | `0x4C07B19D` | `0x484003AB` | `0x484003DF`-`0x48400403` |
| kn6500 | `0x4C3815A2` | `0x4C07B331` | `0x484003AB` | `0x484003DF`-`0x48400403` |
| kn2400 | `0x5018DF0B` | `0x48705624` | `0x48705CCF` | `0x48705D03`-`0x48705D27` |
| kn2600 | `0x5018DF0B` | `0x48705624` | `0x48705CCF` | `0x48705D03`-`0x48705D27` |

`vector_table_layout.py` checks the architecture instead, and reports per image:

* **the program ROM begins with the documented vector table** — a `jmp` to the
  reset routine at offset 0, `nop` padding, and a second `jmp` positioned so that
  *entering at offset 8* executes it. kn6000/kn6500 reach it with a 3-byte
  `jmp disp16` and put the second `jmp` exactly at +8; kn7000/kn2400/kn2600 use a
  5-byte `jmp disp32` and pad to +0x0A, which entering at +8 crosses as two
  `nop`s. Either way the ROM was linked for a vector base of `0x40000000`.
* **IVAR0..IVAR6 are written zero, once, from a just-cleared register**, and the
  block is never reachable another way: the only address in the CPU's on-chip
  peripheral page any of these images loads into a pointer register is
  `0x20000070`, so no pointer-relative write can be hiding.
* **two work-RAM thunks, at offsets 0 and 6**, the second jumping to the same
  routine the ROM table's offset-8 entry does (kn6000/kn6500 via the library's
  self-loaded copy of the flash, `+0x03C00000`). RAM+6 is loaded into an address
  register nowhere in the image; RAM+0 only by the routine that walks work RAM
  with `0x5A5A5A5A`/`0xA5A5` patterns, which is a memory test, not a dispatch.

**PASS on all five, 2026-09-23.** `--selftest` is the positive control: it
re-runs every check against images mutated one at a time — an IVAR store no
longer preceded by its `clr`, the offset-8 entry overwritten, a third thunk
planted — and requires each to be reported. All three are.

## Runtime control

Asserting the mechanism is not the same as showing MAME uses it. With the CPU
taking its vector from the IVAR registers it now decodes itself:

```sh
./kn kn7000 -rompath ~/compartilhado/technics_romsets -str 60 -nothrottle \
    -autoboot_script count.lua -window -resolution 800x400
```

where `count.lua` counts non-black pixels of `:screen` at frame 700.

| build | lit pixels of 153,600 |
|---|---|
| `set_vector_base(0x50000000)` | **27,411** |
| `set_vector_base(0x50000100)` — one constant changed, same build | **0** |

So the vector is load-bearing and the machine really does reach its handler
through memory the firmware wrote. All five machines boot (kn6000 77,809,
kn6500 77,132, kn2400/kn2600 72,521 of 76,800) and `-validate` passes.

## Is the decode live? (and what it was hiding)

"The machine still boots" does not show the CPU is reading its own IVARs: the
firmware writes zero, so a vector of `base + IVAR[L]` and a vector of `base`
are the same number. The discriminating measurement is where the writes land.

```sh
./kn kn7000 -rompath <roms> -str 20 -nothrottle -log
grep -cE '\(484100(A5|AB|B1|B7|BD|C3|C9)\): io_w' error.log   # IVAR stores in the driver's logger
grep -cE '\(4841009F|484100A3\)' error.log                    # the 0x20000070 accesses beside them
```

(The PC in a MAME log is the instruction address **+1**, which is why grepping
for the instruction addresses themselves finds nothing.)

| build | IVAR stores logged by the driver | 0x20000070 accesses logged |
|---|---|---|
| core decodes `0x20000000-0x1B` | **0** | 4 |
| same build, that one `map()` line commented out | **6** | 4 |

The second row is the control: with the decode removed the stores appear, so the
zero in the first row means the core took them, not that the log is blind. The
0x20000070 column is the in-run control — an address in the same window that the
core does *not* decode, logged either way.

Six, not seven: **IVAR0's write was never logged even without the decode**,
because the driver hangs five address windows off one `io_r`/`io_w` pair and
dispatches on an offset MAME measures from each window's own base, so
`case 0x00000` — the effects DSP's host register index at `0x98000000` — also
swallowed offset 0 of `0x20000000`. The firmware's write of IVAR0 was being
taken as a DSP register index.

`io_window_offset0_alias.py` measures how far that reached: across all five
images the only addresses ever accessed at offset 0 of any of the five windows
are `0x20000000` (one site each) and `0x98000000` (one to five sites, which is
what the case is for). `0x32000000`, `0x34000000` and `0x36008000` are never
touched there, so moving IVAR into the CPU closes the whole of it.

## The reset stack pointer, same block

`find_reset_sp_idiom.py` answers the neighbouring question: does each firmware set
SP itself, so the CPU needs no `set_reset_sp()`?

```sh
python3 notes/irq-vector-probes/find_reset_sp_idiom.py <prog.bin> [<prog.bin> ...]
```

It finds the `mov imm32,a0 / mov a0,sp / add -0xc,sp` idiom in the reset path.
Measured 2026-09-23:

| image | reset vector | sets SP at | to |
|---|---|---|---|
| kn7000 | `0x4840FF7E` | `0x4840FFF9` | `0x50021CF8` |
| kn6000 | `0x484002E3` | `0x48400350` | `0x5000778C` |
| kn2400 | `0x48705BDF` | `0x48705C5A` | `0x5006908C` |

All three set it before their first push or call, so the driver's
`set_reset_sp()` was unnecessary — and note the three values DIFFER, so the single
constant the driver carried was the KN7000's applied to all five machines. The
manual says the same in as many words: "A reset start leaves all registers with
indeterminate contents, so always start by initiating registers. The Stack
Pointer (SP) is particularly important."

## What this does NOT settle

**Which address the board decodes to the work-RAM copy at run time**, and how it
gets there. Three measurements now constrain it and cannot all hold at once
without a change of decode between reset and run:

1. The flash answers the CPU's `0x40000000` vector region at reset — its first
   sixteen bytes are that region's table, laid out for it.
2. `IVAR ≡ 0`, so the maskable vector is the base exactly, with no offset.
3. The work-RAM thunk is a hardware entry point — built with a displacement
   computed for execution there, and called from nowhere.

The candidate mechanism is in these images and is not decoded: a 16-bit register
at **`0x20000070`** — inside the on-chip peripheral page but past the block GNU's
model covers. `peripheral_page_probe.py` reports what every firmware does to it,
and also establishes the boundary the single-vector model needs: **`0x20000070`
is the only address in `0x20000000-0x200000FF` that any of the five images ever
loads into a pointer register**, so no pointer-relative write to IVAR can be
hiding from the absolute-addressing scan. On the KN7000, nine sites:

```
4840FFA0  write 0x30; write 0x3                  <- early in reset
48410098  SET bits 0x80   ** the IVAR0..IVAR6 run starts here **
4841015B  CLEAR bits 0x0001; setlb loop
48410182  CLEAR bits 0x0002; setlb loop          <- and five more of the same
```

That shape — a bit set immediately before the vectors are installed, and bits
cleared one at a time each inside a short delay loop — fits a cache or
memory-mode control. Naming it needs hardware or a part-specific manual; the
instruction manual covers the core, not the MN103002A's peripheral complement.

Nothing here blocks the driver: only thunk 0 — offset 0 — is the maskable vector,
and offset 0 is invariant under any base. The driver states the base once, in
`set_vector_base()`, instead of the seven-entry table it used to hand the CPU.

One loose end worth recording: the RAM copy packs its second entry at **+6** where
the ROM table and the documented nonmaskable entry are at **+8**. If the base were
ever remapped to work RAM with a nonmaskable source live, that entry would be
entered two bytes into its own displacement. Observed, not explained.

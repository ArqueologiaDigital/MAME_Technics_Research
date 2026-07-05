# The KN7000 "library ROM" at 0x4C000000 is self-loaded, not undumped

**Headline:** the code the firmware runs at `0x4C000000` — long treated as an
undumped ~6 MB "library/kernel ROM" that blocked emulation — is **not a separate
chip at all**. The boot **loads it at runtime from the program flash**. Once you
know this, no dump and no HLE are needed to boot past kernel init: you only have
to model the memory aliasing the hardware does. Proven by tracing the boot in
`mn10300_sim` and confirmed in the MAME driver.

## What actually happens

1. Early in kernel init, `InitializeObjectTable` (`0x4842A5EB`) calls the loader
   **`InitializeBlock27` (`0x484D7BBD`)**.
2. The loader copies **~253,720 bytes** from **program-ROM `0x487B8FD1`** onward
   (file offset `0x3B8FD1..0x3F6EE8`) into a logical destination of
   **`0x4C000000`**. Its copy loop (`0x484D7BAA`) does:

   ```
   cmp 0x80000000, a1 ; bcc ... ; add 0x40000000, a1
   ```

   so a logical destination below `0x80000000` gets `+0x40000000` added — the
   bytes physically land at **`0x8C000000`**. The destination range is exactly
   `0x8C000000..0x8C03FFF2`.
3. The code is later **executed at the alias `0x4C000000`** (e.g. the first
   library call `call 0x4C03CC4E` from kernel PC `0x487B8D52`, at boot
   instruction ~4,589,920). Two `jmp` trampolines the boot writes into the low 12
   bytes of the `0x90000000` LCD-controller window also target `0x4C03DE26`.

So `0x4C000000` and `0x8C000000` are **the same physical RAM**, differing only by
bit 30 (`0x40000000`). All 298 library entry points the firmware calls (max
`0x4C03DE26`) fall inside the copied 256 KB, and the loaded bytes disassemble as
valid MN10300 code (e.g. `0x4C001A48` = the varargs printf/sprintf helper, the
hottest entry with ~1201 calls; `0x4C000005` loads the IEEE-754 hi-word of 1.0 —
the C float runtime).

## What the MAME driver does

`maincpu_mem()` maps **both** ranges to one RAM share:

```cpp
map(0x4c000000, 0x4cffffff).ram().share("libram");
map(0x8c000000, 0x8cffffff).ram().share("libram");
```

With this alone the boot runs real library code and proceeds far past the old
frontier (PC reaches `0x4C03xxxx` library code and `0x4854xxxx` deeper init),
with **no ROM dump and no HLE**.

## Consequence for the roadmap

`notes/library-rom-api.md` and the docs previously called this ROM "undumped,
≥ ~6 MiB, blocked on a hardware dump." That is **wrong**: the used range is
~253 KB and it is **already present** inside `kn7000_program.rom`. The
reconstructed image (`img8c.bin` in the investigation scratchpad) disassembles as
code. The library ROM is therefore **not** a blocker.

## Current frontier (after the fix)

The boot no longer hits any unmapped code region. It reaches new device windows —
`0x44000000` (a ~1 MB heavily read/written block, mapped as RAM) and `0x9CC00000`
(an unidentified peripheral) — and then parks in a tight loop at `0x484A4F09`
toggling the **panel GPIO `0x36008004`**. The framebuffer (`0x500D4080`, 640×240
8bpp) stays cleared to black: the MILK RTOS cannot switch to the display task,
and the panel handshake cannot complete, without **MN10300 timer/SIO interrupts**.
Interrupt support in the CPU core is therefore the single next enabler for both a
visible UI and functional panel/MIDI receive.

## Provenance

Discovered by an execution trace of `kn7000_disassembly/tools/mn10300_sim.py`
(instrumented copies: `trace_fb.py`, `trace_src.py` proving the `0x8C` copy
source is the program ROM byte-for-byte, and `experiment_alias.py` proving the
boot runs real library code once `0x4C`↔`0x8C` are aliased) and reproduced in the
MAME driver.

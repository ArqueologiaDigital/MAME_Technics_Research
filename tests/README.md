# Tests

Standalone checks that run **without a full MAME build**, so the MN10300 core can
be validated incrementally as it is written.

## `mn10300_length.cpp` — instruction-length validation

The most error-prone part of a variable-length CPU core is advancing the PC by
exactly the right number of bytes per instruction; one wrong length desyncs the
whole fetch stream. This test proves the length decoder
([`mn10300_insn_length.h`](../src/devices/cpu/mn10300/mn10300_insn_length.h),
shared with the core) is correct by comparing it, instruction-by-instruction,
against MAME `unidasm` over the real KN7000 program ROM.

Run it:

```
ROM=/path/kn7000_program.rom UNIDASM=/path/unidasm ./validate_lengths.sh
```

### Result

Over **both** executable regions of `kn7000_program.rom`:

| Region | legal instructions checked | mismatches |
|--------|----------------------------|------------|
| code region 1 (`0x80`–`0x186000`) | 550,328 | **0** |
| code region 2 (`0x3B8000`–`0x3F6F01`, MILK kernel + zlib) | 105,722 | **0** |

**656,050 legal instructions, zero length mismatches.** The core's PC advancement
rests on a decoder that is byte-exact against the reference disassembler for every
real instruction in the firmware.

Two categories of `unidasm` output are deliberately excluded, and the validator
reports their counts:

* **`0xF4` (movbu/movhu indexed)** — `unidasm`'s `disassemble_f4` returns length 1,
  but the instruction is really 2 bytes (a documented MAME disassembler bug). Our
  decoder returns the correct 2, so these lines are skipped rather than counted as
  mismatches.
* **illegal opcodes** — where `unidasm` prints `?` and returns length 1 for a
  sub-opcode it does not decode (mostly non-code bytes swept as instructions). A
  CPU core traps on these, so their "length" is irrelevant.

The core uses the same length table to advance the PC over *not-yet-implemented*
opcodes, so the machine stays aligned and steppable during bring-up.

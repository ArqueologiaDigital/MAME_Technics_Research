# The WSA1R SysEx debug monitor — build log

**Design: `HARDWARE-CUSTOM-DSP-PROGRAMS-WSA1R.md` §A5. Code: `tools/wsa1r-sysex-monitor/`.**
Authorised by Felipe 2026-09-14 ("implement the custom rom"), reversing that file's earlier
do-not-build decision.

Purpose: a bidirectional debug channel over MIDI, so µPD6383 probe microcode can be loaded and
its results read back as exact integers rather than inferred from audio. Decode coverage stands
at **1397 undecoded of 7273 pooled words (80.8 %)**, and this is the instrument meant to turn the
remaining ~321 distinct shapes into an automatable sweep.

---

## Status

| step | state |
|---|---|
| Toolchain — assemble TLCS-900 | ✅ `llvm-mc -triple=tlcs900` from the project's own backend |
| Target identified | ✅ `prom_a` = `qsigcwsa1ax.ic12`, CPU 1 (`tmp95c061`), mapped `0xF80000` |
| Free space found and verified | ✅ 2506 bytes of `0x0E` at `0xFBA236`, 2423 still spare |
| Hook point found | ✅ one 4-byte instruction at `0xFA586E` |
| Monitor written and assembled | ✅ 83 bytes, milestone 1 (IDENT), **zero RAM used** |
| Patcher with refusal gates | ✅ 4 gates, all passing |
| Cross-checked, second toolchain | ✅ MAME's own `unidasm` reads back the intended code |
| Patch live in the running machine | ✅ read out of CPU 1's address space by Lua |
| Patched ROM boots | ✅ `wsa1r` runs (expected WRONG CHECKSUMS notice) |
| **End-to-end over MIDI** | ✅ **PASS** — file on `-midiin` → UART at 31250 baud → firmware ISR → monitor → reply |
| **Milestone 2: PEEK** | ✅ **PASS** — reads CPU-1 memory back over MIDI, self-verified |
| **Reply captured OFF the machine, MIDI only** | ✅ **PASS** — `aseqdump` on ALSA, no Lua, negative control included |
| Transmit-from-ISR safety | ✅ proven in the emulator — see below |

## What was built

**83 bytes**, milestone 1 only: `F0 7E 7D 01 F7` → `F0 7E 7D 7F 01 00 F7`.

The three findings that made it small and safe:

1. **A same-width hook.** `MIDI_RX_SysExData` (`0xFA586E`) is called for every data byte of an
   accepted SysEx. Its first four bytes `f0 a9 c9 66` become `jp 0xFBA246` — and `jp abs24` is
   exactly four bytes. The routine has one caller (`MIDI_RX_DataByte`, `0xFA576D`) and is only
   ever entered at its first byte, so nothing after the patch is reachable; the remaining original
   bytes stay in place as documentation. **Restoring the ROM is a four-byte write.**
2. **A free state bit.** `(0xA9)` is the firmware's SysEx state byte, and **bit 5 is tested by
   `MIDI_RX_SysExData` and set nowhere in the firmware** (`FINDINGS-midi-port.md`). Its lifecycle
   is exactly right: `MIDI_RX_SysExStart` does `ld (0xa9),0x01`, clearing it at every `F0`. The
   monitor uses it as "this message is mine", which also makes the firmware skip our bytes.
3. **A constant reply.** The IDENT response is a ROM table, so milestone 1 needs **no RAM
   allocation anywhere** — the only state is that one borrowed bit.

## Verification

* ★ **Two independent toolchains agree.** `llvm-mc` assembles it; MAME's own disassembler reads
  the patched image back as exactly the intended instructions, all four branch targets correct.
  The `call 0xf41e3c` inside the monitor is **byte-identical** to the ROM's own at `0xFA587D`,
  which is the strongest single check that the assembler and the machine agree.
* ★ **Live in the machine**, not merely on disk: `verify_in_emu.lua` reads `0xFA586E` =
  `1B 46 A2 FB`, `0xFBA246` = `F2 A9 00 00 C8`, and the reply table = `F0 7E 7D 7F 01 00 F7` out
  of CPU 1's own program space while the firmware runs.
* ⚠ The claim-path unit test initially failed on **my** error, not the monitor's: MAME exposes
  TLCS-900 registers **bank-qualified** (`XDE0`…`XDE3`), so `cpu.state["DE"]` is a nil index.
  Fixed by setting all four banks, since which is live depends on RFP.

## ⛔ The blocker that had to be fixed first, and it was not mine

`wsa1r` **segfaulted on every start** — `l7a1429_device`'s constructor, a `rep stos` running off
the object. It reproduced identically on the **stock** ROM, so the patch was never implicated
(the control was run before interpreting). Cause: `WSA1R_ENABLE_ACOUSTIC_HLE` changes
`sizeof(l7a1429_device)` from **8952 to 2112880** bytes, and MAME's build system does not treat
`-D` flags as a dependency, so two object files built days apart disagreed. Fixed, and made
self-diagnosing — see the ABI GUARD note in `acoustic_modeling.h` and commit `5b32b3a`.

⚠ Worth keeping in mind: an incremental tree will re-create this whenever the macro is toggled.
The guard now says so in words instead of crashing.

## Milestone 2 — PEEK, and it works

`F0 7E 7D 02 <6 address nibbles> F7` → `F0 7E 7D 7E <8 bytes as 16 nibbles> F7`.

MIDI data bytes carry only 7 bits, so every payload byte travels as two bytes of one nibble each —
wasteful and completely unambiguous, the right trade for a debug channel.

**Self-verifying test**: the monitor was asked to read 8 bytes at `0xFBA236`, which is *its own
reply table*, so the right answer was known in advance.

```
   MST_ADDR = 36 A2 FB 00          -> 0x00FBA236, exactly as sent
   MST_BUF  = F0 7E 7D 7E 0F 00 07 0E 07 0D 07 0F 00 01 00 00 0F 07 00 00 F7
   expected = F0 7E 7D 7E 0F 00 07 0E 07 0D 07 0F 00 01 00 00 0F 07 00 00 F7
   source   = F0 7E 7D 7F 01 00 F7 00
```

Byte for byte. **CPU 1's memory is now readable over MIDI.**

⚠ Two things caught by reading the code rather than by a wrong answer: only six address nibbles
arrive, so byte `+3` of the 32-bit accumulator had to be cleared explicitly (`ld xde,(MST_ADDR)`
reads all four); and the per-message state reset rides on `(0xA9)` bit 5 being cleared by
`MIDI_RX_SysExStart` at every `F0`, so `.Lclaim` is the natural place to do it.

### The RAM, and how it was chosen

Milestone 1 used none. PEEK needs a little, and the address is **measured, not assumed**: a
write-tap census over a full 12-second boot (`ramscan.lua`) found

```
   0x007F00..0x007FFF   227 writes
   0x640000..0x6400FF     6
   0x660000..0x6600FF     6
   0x67F000..0x67F0FF     0      <- UNTOUCHED
   0x67FF00..0x67FFFF     0      <- UNTOUCHED
```

so the monitor's state block sits at `0x67FF00`. ⚠ **Twelve seconds of boot is not the machine's
whole life** — loading a disk or entering an unvisited mode could touch it. Re-run the census under
more activity before trusting this on hardware.

---

## ⛔ The reply went to the WRONG CHIP for two days — `0xF40ED4` is not MIDI

Felipe, 2026-09-14: *"the results must be read via midi as well. The real device does not let us
inspect its internals as easily as we do with lua scripting."* Fair, and the moment that constraint
was applied the monitor stopped working: `aseqdump` saw the firmware's own Active Sensing, Pitch
bend and Control changes on `mdout`, and **not one byte of ours**.

The cause was a misidentified primitive, and it was mine. `0xF40ED4` is a prom_b directory slot
whose body is prom_a **`Link_SendBlockIn32ByteChunks` (`0xF8E02C`)**: it chops a buffer into
0x20-byte pieces and hands each to `Link_SendCountedBlock`, which writes a header byte to
**`0x007C0000`** — the CPU1↔CPU2 link port — and micro-DMAs the body there. The argument I had
been calling a *port selector*, and had spent a round flipping between `0x02` and `0x00`, is the
**three-bit field that goes into bits 7..5 of that link header**. Every reply the monitor ever
sent went to CPU 2, correctly and invisibly.

⚠ The tell was there to be read: the routine's own header in the disassembly says
*"the block sender that carries port B's stream to the other CPU"*. I had read the call sites
instead of the callee.

### What actually puts a byte on MIDI OUT

`MIDI_TX_Ready` (`0xFA542F`) is the INTTX0 handler. After the five System Real Time request bits
in `(0xA0)` it calls **`Ring601432_Get`** (`0xF41DF0`) and writes anything that is not `0xFFFF`
straight into **SC0BUF** at `0xFA547E`. So the MIDI OUT queue is the 256-byte ring at `0x601432`,
and the send sequence is `MIDI_SendBankAndProgram`'s own bit-4-clear arm (`0xFA5BC6`–`0xFA5BD5`),
the one prom_a's header calls *"port A"*:

| | |
|---|---|
| `Ring601432_PutBlock` | **`0xF41DF8`** — `push <buffer:4>`, `pushw <count:2>`, call, clean 6 |
| `MIDI_PostSendWork` | **`0xFA590F`** — no arguments; sets the `(0x77)` mailbox to `0xDD`, which restarts a transmitter that has already run dry |

The critical section is `push sr` / `ei 6` / … / `pop sr` — the **save-and-restore** form, not the
`ei 0x00` the ROM's own main-loop caller uses. We are inside INTRX0; forcing the mask to 0 would
unmask a re-entrant MIDI receive. Level 6 masks INTTX0, the ring's other writer.

★ **That also settles the transmit-from-ISR question** that this file listed as unproven: the ISR
does not transmit at all. It appends to a ring under a mask the ROM itself uses for that ring, and
the transmit happens later in INTTX0. Nothing re-entrant is called.

---

## ✅ Read off the wire by a program that knows nothing about MAME

`tools/wsa1r-sysex-monitor/midi_roundtrip.sh` — **no Lua, no taps, no debugger**, exactly the
instrument that will exist when the EPROM is in the real machine.

```
   $ ./midi_roundtrip.sh
   === 3. drive it over MIDI and read the answers back over MIDI
     ✅ ident  F0 7E 7D 7F 01 00 F7
     ✅ peek   F0 7E 7D 7E 0F 00 07 0E 07 0D 07 0F 00 01 00 00 0F 07 00 00 F7
   === 4. negative control: the same stimulus against the STOCK prom_a
     ✅ stock  (control: no SysEx, as required)
```

* **in** a Standard MIDI File on `-midiin` (deterministic, replays identically)
* **out** ALSA `Midi Through Port-0` on `-midiout`, captured by `aseqdump`
* the PEEK payload nibble-decodes to `F0 7E 7D 7F 01 00 F7 00` — the eight bytes at `0xFBA236`,
  which is the monitor's **own reply table**, so the right answer was known before the run

Three things make the ✅s mean something:

1. **The negative control.** The same stimulus against the unpatched ROM must produce no SysEx —
   and `0x7E` *is* an identifier the stock parser accepts, so "the firmware answered by itself" was
   a live alternative, not a straw man.
2. **The instrument is checked before it is read.** An empty capture is not a result; the machine
   emits Active Sensing continuously, so the harness fails the run outright if the capture contains
   none. Otherwise a disconnected `aseqdump` would make the control pass for the wrong reason.
3. **It has been seen to fail.** The first run of this harness reported ❌❌ — see the timing note
   below — which is what a criterion that can fail looks like.

⚠ **`midiin`'s ten seconds is an OFFSET, not a deadline.** `m_sequence_start =
std::max(machine().time(), attotime(10,0))`, then the file plays *from there*: a timestamp of T
seconds arrives at 10 + T. Placing the SysEx at T = 12 s in a 16-second run plays nothing, and
looks exactly like a run that is too short. The harness uses T = 1 s.

## Next, in order

1. **End-to-end over MIDI.** MAME's `midiin` image device either parses its argument as a
   Standard MIDI File or hands the name to the OSD MIDI layer as a live port. Both routes exist
   here: MAME enumerates ALSA's "Midi Through Port-0", and the host has `amidi`/`aconnect`.
   * a **`.mid` file** carrying the SysEx is deterministic and needs no daemon — best for
     automated regression.
   * a **live ALSA port** is how an external program talks to it interactively.
   * ⚠ **A PTY will not work for `midiin`**: MAME does support PTYs (`/dev/pts` prefix,
     `posixptty.cpp`), but `midiin_device::call_load` tries to *parse* its file as a Standard MIDI
     File before falling back to a named port, so a raw byte stream never reaches it. Raw PTY
     access would need the UART bridged to an rs232-style image instead — a driver change.
2. ~~Settle the transmit-from-ISR question.~~ ✅ Done, and the answer was that the premise was
   wrong: see the `0xF40ED4` section above.
3. **Milestone 3**: `LOAD`, `POKE`, `RUN`, `DUMP`, and the `RQ`/`GF` commands that §A5 argues
   could locate the chip's COND field and its GF-setting instruction.
   ⚠ **The blocker is known and is not MIDI.** The µPD6383 host port belongs to **CPU 2**, so every
   one of those commands has to cross the inter-processor link — the very link `0xF40ED4` drives.
   PEEK needed none of it, which is why PEEK came first.
4. **A variable read length.** PEEK returns a fixed 8 bytes; a DSP sweep wants a count argument.

⚠ Nothing here has been near the hardware yet.

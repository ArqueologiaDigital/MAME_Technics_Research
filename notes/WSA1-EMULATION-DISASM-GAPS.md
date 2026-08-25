# SX-WSA1R: what the emulator needs the disassembly to answer next

Written 2026-08-25 from the emulation side, after reading the 29 findings notes in
`wsa1-roms-disasm/notes/` and rewriting `src/mame/matsushita/wsa1.cpp` against them.

This is a **request list**, not a summary. Every entry is a question a disassembly wave could
answer, with what the driver does instead today and where to start looking. It is deliberately
short: only gaps that change what the emulator can *do*.

> This file lives in `kn7000_mame/notes/` because `wsa1-roms-disasm` was locked by another
> workflow when it was written. Mirror it into `wsa1-roms-disasm/notes/` when convenient.

Conventions: a bare hex number is a CPU address in the image named beside it. "CPU 1" is the
processor that fetches prom_a+prom_b, "CPU 2" the one that fetches prom_c, matching the driver's
tags. `notes/X.md` means `wsa1-roms-disasm/notes/X.md`.

---

## The three that would change the most

**1. What any 0x0010C000 register MEANS (gap A).** It is the difference between "the firmware
programs a device" and "the emulator makes a sound". Everything else in the audio chain --
the six undumped wave ROMs, the DACs, the DSPs -- is downstream of knowing which register is
pitch, which is a sample address and which is a level. Today the driver stores 4096 words and
synthesises nothing, and it cannot do better, because no note anywhere names one register.

**2. What the 0x7B0004/0x7B0005 + 0x7A0000 subsystem is (gap B).** One command/status pair, one
micro-DMA'd bulk port, INT5 and INT7, and ten direction codes. It is the only unclaimed
subsystem on CPU 1 big enough to be the floppy controller or the control-panel link, and the
machine has neither. Today both addresses are mapped inert and neither interrupt is ever
asserted.

**3. Why CPU 1 never releases the link's receiver-busy line (gap C).** The emulated CPU 2 sends
exactly ONE packet per boot and is then locked out for good. That is measured, not suspected,
and it is what stands between "the keybed model is read by the firmware" -- which is now
demonstrated -- and "a key press reaches the tone generator". It is also the narrowest of the
three: one interrupt handler on one side.

Runner-up: **whether prom_d is the content of the flash at 0xE80000, tied to one instruction
(gap D)**. prom_d is 512 KiB of tone data already in hand and mapped nowhere; CPU 1 reads remote
banks 0xE8-0xEC over the link, so closing the tie makes the voice data path reachable end to end
without dumping anything new.

---

## The list

### A. What does a 0x0010C000 register do? -- PRIORITY 1, blocks audio entirely

**Question.** For at least one register block of the device at CPU 2's `0x0010C000`: what
physical quantity does it carry? Concretely -- which block holds a pitch/phase increment, which
holds a wave start address, which holds an envelope level, and what are the units?

**Why it matters.** The driver models this port as an address latch plus a 4096-word register
file that stores and never acts (`tg_addr_w` / `tg_data_w` in `wsa1.cpp`). That is all it can
honestly do. A sound device needs one identified register to start from; with pitch and level
alone a first audible note becomes possible even with placeholder waveforms.

**Where to look.**
* `notes/FINDINGS-prom_c-tone-generator.md` sec.10 names the unconverted fillers of the staging
  struct at RAM `0x00D75E`: **`0xFA8347`** and **`0xFA83CC`**. The drivers below them only move
  words; these are where a value is computed.
* `notes/FINDINGS-prom_c-voice-module.md` sec.5: `VoiceParams_Compute_{A,B,C,D}` and the 17-26
  small helpers each `VoiceRegs_Stage_*` calls, contiguous in **`0xFA81xx-0xFAB7xx`**, "the
  obvious next target and every routine in it now has a named caller".
* The float library is already decoded (`notes/FINDINGS-prom_c-eeprom-and-runtime.md` sec.2), so
  a compute routine's arithmetic can be read rather than guessed -- and note `Float32_Multiply`
  is really `a / (1/b)`, two roundings, which any re-implementation has to copy.
* A note number reaches this path through `MidiNote_Dispatch` (`0xFB3F36`); the per-voice record
  array is at RAM `0x00003BCF`, stride `0x44`, index == hardware channel.

---

### B. What is the device at 0x7B0004/0x7B0005 and 0x7A0000 on CPU 1? -- PRIORITY 1

**Question.** What is on the other side of that command/status pair? And what do the ten
direction codes `0x4D 0xC9 0xC5` (RAM -> device) and `0xDD 0xD9 0xD1 0x4A 0x42 0xCC 0xC6`
(device -> RAM) that `Dev7A_StartDma` (`0xFE596A`) selects on `(0x605A18)` mean?

**Why it matters.** The SX-WSA1R has a uPD72070 floppy controller and an M37471M2196S panel
microcontroller, and the driver models neither. This subsystem is the right shape for either.
Today `0x7B0004`/`0x7B0005` and `0x7A0000` are mapped `.noprw()` -- deliberately inert, because
`INT5_Dev7B_Receive` (`0xFE6866`) contains an **unbounded** poll (`spin until
status & 0xF0 == 0x80`) that a guessed status byte would either hang on or satisfy dishonestly.
INT5 and INT7 are never asserted, so the handler is never entered and nothing hangs; but the
machine also has no disk and no front panel.

**Where to look.** `notes/FINDINGS-dev7b-and-int5.md` throughout, and the three routines it lists
as still `.incbin`: **`0xFE5A41`** (status classifier, masks `0xE0`, compares `0x80`/`0xC0`),
**`0xFE5B5E`** (where a received packet is consumed -- this is the one that would name the
device), **`0xFE5E84`** (called with a small integer from the timeout paths). Also `0xFE680F` /
`0xFE682B`, the programmed-I/O half of `0x7A0000`, both still `.incbin`.

---

### C. Why does CPU 1 stop releasing the link's receiver-busy line? -- PRIORITY 1

**Question.** After CPU 2 sends its first packet, CPU 1 leaves P7 bit 1 low forever. Which arm
of `INT0_LinkByte` (prom_a `0xF8E47F`) drops it, which arm is supposed to raise it, and what
does `INTTC3_LinkDmaDone` (`0xF8E54F`) require before it runs?

**Why it matters.** `Link_SendChunk` (prom_c `0xF999BE`) will not write a header until PA bit 3
reads 1, and under the driver's cross-wiring PA bit 3 is CPU 1's P7 bit 1. So the whole
CPU 2 -> CPU 1 direction is dead after one packet, and the keybed's `{0x90, note, velocity}` on
channel 5 -- the one thing in this machine a user can now cause -- is dropped 20000 spins later.
The driver's one-byte INT0 latch model is a candidate cause, but the handler is not converted,
so there is nothing to check it against.

**Measured, so a fix has a target to hit** (`notes/wsa1-probes/wsa1_link_handshake.lua`):

```
t=68  tx=0  CPU 1 last wrote P7 = 0xE7 (bit 1 SET)    PA reads 0xFD
t=72  tx=2  CPU 1 last wrote P7 = 0xE1                PA reads 0xF5 x40013
t=82  tx=2  CPU 1 last wrote P7 = 0xC5 (bit 1 CLEAR)  PA reads 0xF5 x60051, 0xF7 x20027
```

CPU 1 -> CPU 2 is fine: 56 bytes over a boot.

**Where to look.** `notes/FINDINGS-interprocessor-link.md` for the protocol;
`notes/FINDINGS-interrupt-vectors.md` places INT0 at `0xF40EDC -> 0xF8E47F` and INTTC3 at
`0xF40EE8 -> 0xF8E54F`. `0xF8E4CA`, `0xF8E4E9` and `0xF8E51F` all write `DMA3V = 0x0A`, and
MAME **clears** a micro-DMA vector at end of count (`tmp95c061.cpp:450`) -- the same trap
`notes/FINDINGS-dev7b-and-int5.md:129-135` had to retract a claim over, for channel 0. The
packet CPU 2 does get through is a channel-6 one, header `0xC0`, length 1, sent by
`MIDI_Watchdogs_And_TransportSwitch` (`0xF99543`); whether CPU 1 has a channel-6 receive arm at
all is worth checking first.

---

### D. Tie prom_d to an instruction -- PRIORITY 1

**Question.** Does any instruction in prom_a/prom_b index prom_d's 44-entry offset header at
file `0x000000`, or its 274-entry pointer directory at file `0x000B80`, with an address that
comes back over the link from CPU 2's flash?

**Why it matters.** `notes/FINDINGS-memory-map.md` sec.5 grades prom_d "strongly supported, one
link short" as the flash image. The driver therefore declares `prom_d` as a region and maps it
**nowhere**, and leaves `0xE80000-0xEFFFFF` on CPU 2 unmapped, because mapping an undumped part
from an inferred image would put invented bytes on the bus. Close the tie and the flash can be
mapped (as `BAD_DUMP`, from the redistributed image), which makes 512 KiB of tone data reachable
by the running firmware for the first time.

**Where to look.** The remote-read packet builder is `0xF8E0FE` on CPU 1; the caller that names
the flash is **`0xFB24D3`** (dest `0x60A000`, remote `0xE80000`). What prom_a does with the
bytes at `0x60A000` afterwards is the thread. `notes/FINDINGS-memory-map.md` sec.3 and sec.5.

---

### E. What is at the other end of serial channel 1 on CPU 1? -- PRIORITY 2

**Question.** Three sub-questions, in order of usefulness to the driver:
1. What immediate do the **twelve** `ld (0x57),#8` (BR1CR) writes carry? `notes/FINDINGS-prom_b-sc1-link.md:74-79`
   establishes the instruction form and explicitly does not give the value, so the bit rate is
   unknown.
2. What do the `SC1MOD` writes carry -- is SC1 in UART mode or clocked I/O-interface mode?
3. What does prom_a `0xF89800` (reached through thunk `0xF405F0`) do with a received byte? Its
   carry result decides whether the byte is kept, and it is the module's only call out of itself.

**Why it matters.** The module is half duplex with INT6 as a peer request line and emits a
32-group change mask -- `notes/FINDINGS-prom_b-sc1-link.md:206-212` calls that "the shape of a
scanner with a small return channel" and refuses to name it. If it is the control panel, wiring
it gives this machine its front panel, which is the largest single missing piece of user-facing
behaviour after sound. The driver models nothing here, and cannot: MAME's `tmp95c061` has no
serial engine at all (see the appendix), so even a fully identified SC1 needs core work first --
but the identification is what decides whether that core work is worth doing.

**Where to look.** `notes/FINDINGS-prom_b-sc1-link.md`; the module is prom_b `0xF5A800-0xF5B7FF`.
The seven command bytes it sends first are `0xDD 0xDE 0xDF 0xE0 0xE2 0xE3 0xEF` with arguments
`0xD2 0x1A 0x03 0x80 0x00 0x08 0x10`, meanings not established.

★ One cross-note lead nobody has followed: `notes/FINDINGS-prom_a-ring-buffers.md:279` says the
six analogue controls report through directory slot `T_F405F0` -- **the same slot** the SC1
receive decoder calls out through (`FINDINGS-prom_b-sc1-link.md:203-204`). Neither note connects
them. If it is one slot, the analogue controls and the SC1 peer are the same board.

---

### F. What does the 0x10C004 read-back actually return? -- PRIORITY 2

**Question.** Register block `0x0180 + channel` is read at `0xFA69B1` and kept as
`(value & 0x3FFF) >> 5`; register `0x0000 + n` for n = 0..3 is read at `0xFA690A` and OR-ed into
a shadow at `0x0087C7`. Is the first really a per-voice envelope level, and is the second really
an active-voice bitmap of 16 channels per bank? What writes them on the device side?

**Why it matters.** These are the **two most load-bearing stubs left in the driver**. Both answer
0, which means "no voice is sounding" and "every voice is free", and `tg_status_r()` says so in
as many words: answering 0 is a decision, safe only because nothing in prom_c waits for a voice
to become busy. If the allocator would in fact behave differently -- steal a voice, wait for a
release -- then every note-on path in the emulator is running on a false premise.

**Where to look.** The whole reader is prom_c `0xFA68E0-0xFA69DE`; `0x0087CF` is the 0..3 bank
counter it increments, `0x0087BF` and `0x0087C7` the two shadow arrays.
`notes/FINDINGS-prom_c-tone-generator.md` sec.10 lists `0xFA68FC` as "the only READ located so
far" -- it is one routine with two reads, which is worth correcting there.

---

### G. What does the DSP microcode upload do, and what answers READY? -- PRIORITY 2

**Question.** CPU 2 polls **P9 bit 3** at eighteen sites (`0xF9A19F ld C,(0x19) / and C,0x08`)
during a microcode upload. Which port do the microcode *bytes* leave by -- `0x00E00000`, or
something not yet reached? And what is P9 bit 0, polled at `0xFB050B`?

**Why it matters.** Pure boot time, but a lot of it. Measured: CPU 2's PC sits in
`0xF9A347-0xF9A399` -- that poll's timeout loop -- for most of the first 70 seconds of emulated
boot. The driver refuses to answer `0x08` on P9 because that would be a fabricated ready signal
on a pin nobody has read (the refusal is written out in the machine config). If the byte path
were identified, a device could be modelled that asserts READY *because it consumed a byte*,
which is a real handshake rather than a constant, and boot would drop by most of a minute.

**Where to look.** prom_c `0xF9A100-0xF9A400`; `DSP_ChannelRegs_Write8` and
`DSP_WriteChans0to3_FromE29D` (`0xFC8719`) are the only converted writers of `0x00E00000`, and
they write 32 registers, not a microcode stream -- so the stream is elsewhere.

---

### H. What do the 64 write pairs to the key-scan port configure? -- PRIORITY 3

**Question.** `Dev108000_Preload_80toBF` (`0xF99125`) writes `0x0080 + i` to `0x108002` and then
`0x8000` to `0x108000`, 64 times, from RESET (`0xFFF081`) and from NMI (`0xFFF0AE`). What is
being programmed -- one per key? A threshold table? And note the order is +2 first, which is the
opposite of the address-then-data order the neighbouring devices use.

**Why it matters.** The driver now has a 61-key model the firmware demonstrably reads, and it
**ignores these writes** (`keybed_status_w` / `keybed_data_w` log and drop them). If they carry
per-key calibration or a scan configuration, the model is right by luck rather than by
construction. It also matters for the NMI path, which runs this sweep and then spins forever.

**Where to look.** `notes/FINDINGS-prom_c-keyboard-and-touch.md` sec.7, last bullet; the routine
is converted in `prom_c/wsa1_prom_c.s`.

---

### I. What does status word value 2 mean at the key-scan port? -- PRIORITY 3

**Question.** `KeyScan_ReadEvent` compares the whole status word against **2** at `0xF9979A`,
and treats that exactly like a touch byte of `0xFF`: a note-on is dropped and `(0x008517) |= 3`,
a note-off is decoded with velocity forced to 0. What is state 2, and who reads `0x008517`?

**Why it matters.** The driver's status handler never returns 2, and says so. That is safe but
incomplete: if 2 means "queue overflowed" or "scan error", a real machine reaches it and the
emulator never will.

**Where to look.** `notes/FINDINGS-prom_c-keyboard-and-touch.md` sec.3. `0x008517` has exactly
one literal reference in the whole image, the `or` that sets it -- so its reader, if any, is
through a pointer.

---

### J. What is the device at 0x7E0008 on CPU 1? -- PRIORITY 3

**Question.** The accessor at `0xFE4CE0` forms `0x7E0000 + ((n & 7) | 0x08)` or `| 0x10` -- two
banks of eight 16-bit registers -- but the only traced caller (`0xFE50A0`) passes zero for both
indices in all 256 iterations, so only `0x7E0008` is known to be reached. Are there really two
banks, and what is transferred? The transfer is bracketed by a CS0 timing change
(`0xFE509B ldio B0CS,0x10` ... `0xFE50D5 ldio B0CS,0x14`), which is a slow device.

**Why it matters.** Two bytes of the driver's map are inert. Small, but it is a 512-byte bulk
read at boot from a device that needs relaxed bus timing -- that is a real peripheral, not glue.

**Where to look.** `notes/FINDINGS-memory-map.md` CPU 1 table, the `0x7E0008-0x7E0017` row. No
findings note has anything else on it: I checked all ten prom_a/prom_b notes and the address does
not appear.

---

### K. What is CPU 2's P8 bit 2 wired to? -- PRIORITY 3

**Question.** `MIDI_Watchdogs_And_TransportSwitch` (`0xF99543`) does `res 2,(P8)`, reads P8, and
on a change of bit 2 sends MIDI **START** (`0xFA`) or **STOP** (`0xFB`) on link channel 6. A
footswitch? A transport button on the panel? A sync input?

**Why it matters.** The driver returns it low, with a comment saying that this is what MAME's
unbound port read already did and therefore is not a new claim. If it is a pedal it should be an
input port the player can operate; a sequencer that cannot be started is a sequencer nobody can
test.

**Where to look.** `prom_c/wsa1_prom_c.s`, the `MIDI_Watchdogs_And_TransportSwitch` header, which
flags this as not established. The bytes sent are at `0xFCC5C3`/`0xFCC5C4`.

---

### L. What is CPU 1's P5 bit 4? -- PRIORITY 4

**Question.** `0xF95137` reads P5, tests bit 4, and returns at once if it is 1; if it is 0 it
blinks an 8-bit diagnostic code on P5 bit 3 as two nibbles. Is bit 4 a service jumper, a test
connector, a "panel present" strap?

**Why it matters.** 3.13 seconds of every boot, measured. The driver refuses to force it high for
exactly the reason in gap G: no net has been read. Low value, cheap to answer if a schematic net
is ever recovered -- this one may not be answerable from the ROMs at all.

**Where to look.** `0xF826BB`-`0xF826C1` (P5 = 0xFF, P5FC = 0x24, P5CR = 0x2C), `0xF95137`,
`0xF95158`, reached from `0xF827D1` through prom_b thunk `0xF40144`.

---

### M. What does CPU 1 do with link channel 5? -- PRIORITY 4

**Question.** CPU 2 sends `{0x90, note, velocity}` triples to CPU 1 on link channel 5
(`KeyEvents_ToLink`, `0xF98CB9`). What on CPU 1 receives them, and what does it send back on
channel 0 -- which is the ring `MidiIn_ParseRingAndDispatch` drains, and therefore what actually
decides part, tone and mode?

**Why it matters.** The emulator now drives this loop end to end from a PC keyboard, so the
behaviour is observable -- but it cannot be *explained*, and the part-record fields
(`part_record[0x10] & 0xC0` picks one of four staging paths) are unnamed. This is the natural
companion to gap A, and it is blocked behind gap C until the link forwards
anything at all.

**Where to look.** `notes/FINDINGS-prom_c-voice-module.md` sec.1 and sec.4 for CPU 2's half;
CPU 1's half is whatever handler its own link dispatcher gives channel 5, in prom_a/prom_b.
`notes/FINDINGS-prom_c-keyboard-and-touch.md` sec.6 ends with exactly this as an open question.

---

## Gaps I could not frame sharply

Recorded as vague on purpose, rather than dressed up as questions with false precision.

* **The audio path.** Not one note in the set describes how a sample gets from a wave ROM to the
  four PCM1702U DACs, or what the three uPD6383GF DSPs process. I cannot even say whether the
  DSPs sit in the main mix. The only handle I have is negative: `0x00E00000` and `0x007F0000`
  carry a 4x32 register file whose driver is byte-identical to the KN5000's, and on the KN5000
  the standing correction is that it is **not** the DSP host interface. So the DSP host interface
  on this machine has not been located at all, on either processor.
* **Which of IC1 "MAIN" and IC2 "SUB" fetches which ROM pair.** Affects only naming today.
* **Whether CPU 1's `0x7F0000` and CPU 2's `0x00E00000` are one dual-ported chip or two.** The
  driver models two, which is the assumption that fails loudly if it is wrong (values written by
  one processor never appear to the other).
* **The six analogue controls** read through `ADREG0`-`ADREG3` plus `(0x600000)`/`(0x600001)`
  (`notes/FINDINGS-prom_a-ring-buffers.md:274-282`). Six pots or sliders on an instrument with no
  identified panel. I do not know enough to ask which.
* **What `0x00E2E1` is for.** It starts at 1000 (ROM `0xFCB4EC`), and while it is positive
  `KeyEvents_ToLink` throws every key event away. So the keybed is deaf for the first 1000 MAIN
  passes after power-on -- harmless, and measured to clear in well under a second of emulated
  time. Nothing converted writes it. If something re-arms it at runtime, the keyboard would go
  deaf again and the emulator would look broken.

---

## Appendix: gaps that are MAME's, not the disassembly's

Listed so a disassembly wave does not spend effort on something the emulator could not use yet.

1. **`tmp95c061` has no serial engine.** `sc0buf_r()` returns 0 and `sc0buf_w()` only sets the
   "transmit complete" interrupt flag (`tmp95c061.cpp:1131-1140`). MIDI IN/OUT and SC1 cannot be
   wired to anything until a serial implementation exists -- the overlay already has one for the
   sibling part, `tmp94c241_serial.cpp`.
2. **`tmp95c061`'s 8-bit timer prescaler taps are 16x slow**, and its 16-bit timers 4-7 do not
   count at all, so `INTTR4` -- this machine's musical clock -- cannot fire. Boot takes ~90 s of
   emulated time instead of ~6 s and the sequencer cannot run.
3. **`tmp95c061` dispatched writes to P6 (internal address 0x12) to the PORT_7 callback.** Fixed
   in this overlay's copy; without it the EEPROM never sees chip select.

Item 3 also **closes** a disassembly-side unknown found while doing this work, recorded here so
it is not asked again: `Timer1_SetPeriodAndStart`'s header and
`notes/FINDINGS-prom_c-scheduler.md` both say CPU 2's timer-1 clock source is unknown because "no
write to T01MOD has been located". There is one: **`0xFFF06C  08 24 0d  ldio T01MOD,0x0D`**, in
RESET, between `ld XIX,0x00100000` (`0xFFF067`) and `ldio P8CR,0x19` (`0xFFF06F`). `0x0D` selects
**phiT256** for timer 1 and phiT1 for timer 0 -- the same taps CPU 1 programs at `0xF826EB` -- so
CPU 2's tick is the same 488.28 Hz, and the scheduler's 250- and 1000-tick gates are 0.5 s and
2.0 s of real time. Verified live: the counter at `(0x00F2F3)` advances and the key scanner arms
(`notes/wsa1-probes/wsa1_cpu2_tick_and_keyscan.lua`).

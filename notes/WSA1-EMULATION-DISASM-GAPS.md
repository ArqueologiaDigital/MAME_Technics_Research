# SX-WSA1R: what the emulator needs the disassembly to answer next

Written 2026-08-25 from the emulation side, after reading the 29 findings notes in
`wsa1-roms-disasm/notes/` and rewriting `src/mame/matsushita/wsa1.cpp` against them.

**Revised later the same day**, after the model-variant survey, its adversarial re-check, and the
driver work that followed. **Gaps B, E and L are CLOSED**, gap C's leading hypothesis is REFUTED,
six new gaps (N to S) are added, and a section on the variant hypothesis records exactly what was
and was not established so nobody repeats the search.

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

**2. ~~What the 0x7B0004/0x7B0005 + 0x7A0000 subsystem is (gap B).~~ CLOSED: it is the FLOPPY
CONTROLLER.** All ten direction codes are legal uPD765 command bytes carrying exactly the MT/MFM
flags each command may take, and only 59 of the 256 byte values are legal commands, so ten
arbitrary bytes all landing legal has probability ~4.2e-7. The control panel turned out to be
somewhere else entirely -- serial channel 1, gap E, also now closed. See gap B below for what is
still open inside it.

**2 (replacement). Which panel button is which bit (gap O).** The panel protocol is decoded and the
device is wired, so the machine now HAS a front panel -- but the map from a legend to a
(segment, bit) pair is not established, so the user can only press positions.

**3. Why CPU 1 never releases the link's receiver-busy line (gap C).** The emulated CPU 2 sends
exactly ONE packet per boot and is then locked out for good. That is measured, not suspected,
and it is what stands between "the keybed model is read by the firmware" -- which is now
demonstrated -- and "a key press reaches the tone generator". It is also the narrowest of the
three: one interrupt handler on one side. ⚠ The tempting explanation -- "CPU 1 knows it is a rack
and is refusing keybed traffic" -- is REFUTED; see the variant section below.

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

### B. ~~What is the device at 0x7B0004/0x7B0005 and 0x7A0000 on CPU 1?~~ -- CLOSED 2026-08-25

**It is the FLOPPY CONTROLLER, the uPD72070GF3BE in the parts list.** Closed by its own evidence,
not by elimination:

* `Dev7A_StartDma` (`0xFE596A`) selects on ten command bytes, and every one is a legal uPD765
  command carrying exactly the MT/MFM flags that command may take -- `0x4D` FORMAT|MFM, `0xC5`/`0xC9`
  WRITE / WRITE-DELETED |MT|MFM, `0xC6`/`0xCC` READ / READ-DELETED |MT|MFM, `0x42` READ TRACK|MFM,
  `0x4A` READ ID|MFM, `0xD1`/`0xD9`/`0xDD` SCAN EQ / LE / HE |MT|MFM. **Only 59 of the 256 byte
  values are legal uPD765 commands**, so ten arbitrary bytes all landing legal has probability
  ~4.2e-7.
* `0xFE6891`: `and L,0xF0 / cp L,0x80` -- RQM=1, DIO=0, EXM=0, CB=0 -- then `push 0x08` and a call
  to `Dev7B_WriteData`. That is SENSE INTERRUPT STATUS, and the result byte is then polled until
  `(0x605A51) == 0x80`, ST0 = invalid command: the textbook post-reset result drain.
* INT7 drives micro-DMA channel 0 for the data phase (`uDMA0_ArmOnINT7`, `0xFE5964`, sets
  `DMA0V = 0x0E` and `(0x0E & 0x1F) << 2 = 0x38` = INT7), and PB bit 3 is pulsed at every channel-0
  completion (`PortB3_Pulse`, `0xFE594C`) -- the shape of a terminal-count or acknowledge strobe.

⚠ **Two things inside it are still open, and they are what a disassembly wave should take.**
1. **Direction: 7 of 10, not 10 of 10.** The three SCAN commands (`0xD1`, `0xD9`, `0xDD`) need a
   CPU -> FDC data phase and sit in the device -> RAM group. Recorded, not explained.
2. **The status classifier and the packet consumer are still `.incbin`**: `0xFE5A41` (masks `0xE0`,
   compares `0x80`/`0xC0`) and `0xFE5B5E`. Until they are converted the driver cannot answer a
   status byte honestly, so `0x7B0004`/`0x7B0005` and `0x7A0000` stay mapped `.noprw()` and INT5 and
   INT7 stay unasserted -- `INT5_Dev7B_Receive` (`0xFE6866`) contains an UNBOUNDED poll that a
   guessed status byte would either hang on or satisfy dishonestly.

**Where to look.** `notes/FINDINGS-dev7b-and-int5.md` throughout, and lines 107-109 of it for the
argument that `0x7A0000` and `0x7B0004/5` are one device -- which the decode above assumes and does
not itself establish.

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

**Two corrections, both from the variant survey's adversarial re-check:**

1. **P7 bit 1 has SIX `set` sites, not four, and two of them are TIMEOUTS.** The four that were
   listed are `INTTC3_LinkDmaDone`'s `0xF8E5A8` / `0xF8E5D6` / `0xF8E5EB` and `Link_ServiceTask`'s
   abort at `0xF8E663`. The two that were missed are deadline loops on the 488 Hz tick at `(0x80)`:
   ```
   F8E23C  bit 6,(0x00008a)          F8E671  bit 7,(0x00008a)
   F8E243  ld BC,(0x80)              F8E678  ld BC,(0x80)
   F8E249  cp BC,0x09c4   (2500)     F8E67D  cp BC,0x01f4   (500)
   F8E24D  jr LE,0xf8e23c            F8E681  jr LE,0xf8e671
   F8E24F  ld (0x7f),0x00  DMA3V     ...
   F8E258  set 1,(0x13)    RELEASED
   ```
   2500 ticks is 5.12 s and 500 ticks is 1.02 s. So "it stays low iff INTTC3 never completes" is
   too strong: **the real question is why the code never reaches a wait whose expiry would release
   the line within ~5 s**, and both loops are gated on bits 6 and 7 of `(0x008A)`.
2. **The "CPU 1 has decided it is a rack and is refusing keybed traffic" explanation is REFUTED.**
   P7 bit 1 is an OUTPUT (`P7CR = 0x33`), so it cannot be a strap; and there is not one
   `cp (0xC4)` -- the model-variant flag -- anywhere in `0xF8E000-0xF8FFFF`. The whole transmit
   block, `INT0_LinkByte`, `INTTC3` and `Link_ServiceTask` are variant-blind.

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

### E. ~~What is at the other end of serial channel 1 on CPU 1?~~ -- CLOSED 2026-08-25

**It is the CONTROL PANEL**, the Mitsubishi M37471M2196S on CONTROL PANEL 1 -- the same part number
as the two panel microcontrollers `kn5000_cpanel.cpp` emulates. All three sub-questions are answered
and the panel is now an HLE device in the driver (`src/mame/matsushita/wsa1_cpanel.{h,cpp}`), which
carries the full evidence in its header.

**How it was settled -- a bijection, not a resemblance.** List every common substring of >= 16 bytes
between the SC1 module (prom_b `0xF5A800-0xF5B44D`) and the whole 2 MiB KN5000 v10 main ROM: eight
runs, 154 bytes, and **all eight land inside the KN5000's control-panel driver**, `0xFC3E65`-
`0xFC4C33`, which is 3,535 bytes or 0.169% of that ROM. Run the same scan over the WHOLE 512 KiB of
prom_b and there are 4,399 runs -- of which exactly eight land in the panel driver, and all eight
are the SC1 module's.
(`notes/wsa1-probes/wsa1_kn5000_panel_bytediff.py`, `wsa1_panel_report_refutation.py --selftest`.)

The two packet dispatchers are the same ten-byte instruction differing only in the three low bytes
of the table pointer, and the tables have identical grouping -- which names three of the four WSA1
receive handlers and both transmit handlers from the KN5000's symbols.

**The three sub-questions:**
1. **BR1CR takes 0x22, 0x24 and 0x28** (4, 5 and 3 writes; no other value anywhere).
2. **SC1MOD = 0x00** at `0xF5A8AF`, once: SM = 00 = **I/O-interface (synchronous) mode**, not UART.
3. **`0xF89800` is the analogue CURVE dispatcher**, 32 entries at `0xF89825` indexed
   `((a & 0xC0) >> 1) | ((a & 7) << 2)`; carry set = keep the value, clear = drop it. ★ And it
   answers the cross-note lead this entry flagged as unfollowed: the six on-CPU A/D controls DO
   report through the same slot -- thunk `0xF405F0` has eight prom_a callers, each preceded by
   `ld W,0x00`..`0x05`. Bits 7:6 of the address byte select the SOURCE BANK (00 = the on-chip A/D,
   11 = the panel link); they are **not** a panel identity, and neither ROM ever compares them
   against a constant.

**The frame**, from the firmware's own length rule (`0xF5ADD7` transmit, `0xF5AF33` receive):
`len = ((first & 0x3F) >= 0x30) ? (first & 0x0F) + 3 : 2`. Buttons are `[0xC0|segment][bitmask]`,
analogue controls `[0xD0|sub][value]`, LEDs `[wire][bits]` over eight registers, and types 3/4/5 are
sync packets the receiver discards. The link will not transmit unless **P8 bit 5 reads HIGH and PB
bit 4 reads LOW** (`0xF5AB7B`).

★ **It also corrects `notes/FINDINGS-prom_b-sc1-link.md` sec.6**, which warned that the two run
codecs do not obviously agree. They do, at **n+3 bytes**, with three independent witnesses:
`SC1_TxOp3_Run` emits n+3, `SC1_RxOp6_Run` requires n+3 pending, and `(0x2A81)` is set to
`(n & 0x0F) + 3`.

**What is still open** is now gaps **N** (which pin carries INT6), **O** (which button is which
bit), **P** (what the seven command bytes mean) and **R** (what states 0x04 / 0x0C / 0x14 are for).

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

### L. ~~What is CPU 1's P5 bit 4?~~ -- CLOSED 2026-08-25

**It is the service CHECKING DEVICE's switch, and P5 bit 3 is that device's LED.** The SX-WSA1R
service manual says so in as many words (OCR lines 793-801):

> "Connect the CHECKING DEVICE ... to CN4 on the MAIN P.C.B., and turn on the CHECKING DEVICE
> switch. ... the LED of the CHECKING DEVICE flashes 8 times. The first 4 flashes are for the RAM
> check, and the latter 4 flashes are for the ROM check. ... If an IC is defective, the
> corresponding flash time is longer."

and the ROM matches it exactly: `0xF95137` returns at once if P5 bit 4 reads 1; otherwise it calls
`0xF95158` twice (`0xF95149`, `0xF95153`), and `0xF95158` begins `ld E,0x04` -- four flashes per
call, eight in all, first four then latter four -- writing P5 bit 3 with `stcf 3,(P5)` around a
delay of `0x4000` or `0xC000` outer counts chosen by bit 0 of `(XIZ+0x08)`: a short or a long flash.
`(XIZ+0x08)` bit 0 also picks `HL = 0x4000` against `0xC000`, the two RAM banks the check covers.

**Now in the driver**, as a `PORT_CONFNAME` defaulting to OFF with the LED on the `check_led`
output. That is a behaviour change: MAME's unbound port read returned 0, so the emulated machine
behaved as though a service jig were plugged into CN4 with its switch on, and spent the first
3.13 s of every boot blinking a code at nobody.

⚠ Still unanswered, and cheap for a wave that is in there anyway: **the manual's second procedure**
-- switch OFF, hold the `2` key on the number pad, power on, four flashes = the CPU (IC1) check.
That names one panel button (gap O) if the chord can be found in the boot block.

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

### N. Which pin carries INT6, and which carries INT7? -- PRIORITY 2

**Question.** CPU 1 uses both external interrupts and this tree cannot say which package pins they
arrive on. INT6 is the control panel's request line: the SC1 module writes `INTE67 = 0x85` (INT6 at
level 5) while it is idle and `0x8F` (level 7, which `tlcs900_check_irqs` never dispatches) while it
transmits, at eighteen sites, and vector `0x34` reaches `INT6_SC1_PeerRequest` (prom_b `0xF5AC0A`).
INT7 is the floppy's data request: `uDMA0_ArmOnINT7` (prom_a `0xFE5964`) sets `DMA0V = 0x0E`, and
`(0x0E & 0x1F) << 2 = 0x38` is INT7's vector.

**Why it matters.** MAME's `tmp95c061.h` says port B carries `TI4/INT4, TI5/INT5, TI6/INT6,
TI7/INT7`, and it gates INT4 and INT5 on PBCR bits 0 and 1 being INPUTS. **That cannot be right for
this machine**: RESET writes `PBCR = 0x0C` (`0xF826E5`), making PB2 and PB3 OUTPUTS, and prom_a
`0xFE594C` (`PortB3_Pulse`) genuinely drives PB3 as an output strobe on every micro-DMA channel-0
completion -- while the same firmware uses INT6 and INT7 as inputs. So either the header's pin
table is wrong for INT6/INT7, or they are elsewhere on this part. The overlay's `tmp95c061.cpp` now
implements both lines UNGATED and says so at the code; copying INT4/INT5's PBCR gate would have
modelled a guess, and would have made the control panel impossible.

**Where to look.** A TMP95C061 databook, or a legible schematic sheet for the panel connector.
`notes/FINDINGS-prom_b-sc1-link.md` ends its INT6 header with "Unknown: which pin drives INT6", and
`notes/FINDINGS-dev7b-and-int5.md` has the same hole for INT7. This one may not be answerable from
the ROMs at all.

---

### O. Which panel button is which bit, and which LED is which bit? -- PRIORITY 2

**Question.** The wire protocol is settled (gap E, closed). What is not settled is the map from a
legend on the front panel to a (segment, bit) pair, and from an LED register bit to a lamp.

**Why it matters.** `wsa1_cpanel.cpp` declares the matrix POSITIONALLY -- "Panel SEG3 SW5" -- and
its 64 LED outputs are named `led0`..`led63` for the same reason. Every one of those names is a
claim about the WIRE, which the ROM does establish, and about nothing else. Until the legends are
attached, a user cannot press DISK or SYSTEM; they can only press bits until something happens, and
no layout can be drawn.

**What IS known**, and is marked in the ioports: three power-on chords, all read from the panel's
own change-mask shadow at RAM `0x2B20 + ((wire & 0x0F) | ((wire & 0x40) >> 2))`.

| chord | variant 1 | variant 2 | what it does |
|---|---|---|---|
| ROM version display | seg 2 bits 0-2 (`0xF82952`) | seg 0 bits 4-6 (`0xF8295F`) | shows the version on the LEDs |
| FACTORY CLEAR | seg 8, `(0x2B38) == 7` exactly (`0xF828DF`) | seg 8 bits 0-1 (`0xF828E9`) | zeroes RAM, writes `0x5AA5` at `0x7FCA`, jumps to RESET |
| third service entry | seg 10 bits 5-7 (`0xF82A0A`) | seg 3 bits 5-7 (`0xF82A18`) | not identified |

**Where to look.** The service manual's self-diagnostic section maps six wave-ROM tests onto six
buttons and the OCR loses the circled digits; a better scan of those pages would give six
(legend, bit) pairs at once. Failing that, the display-list interpreter in prom_b consumes panel
events by group id, so a converted display list that reacts to one group would name it.

---

### P. What do the seven SC1 command bytes mean, and what does the panel answer? -- PRIORITY 2

**Question.** CPU 1 opens the link with `(0xDF,0xD2) (0xDF,0x1A) (0xDD,0x03) (0xDE,0x80)`
(`SC1_ConfigurePort`, prom_b `0xF5A8ED`-`0xF5A92C`) and later sends `(0xE0,0x00)`,
`(0xE3,0x00) (0xE2,0x08) (0xE3,0x10)` and `(0xEF,0x00)`. What do they configure, and what does a
real M37471M2196S send back?

**Why it matters.** `wsa1_cpanel.cpp` answers all seven with the same invented two-byte packet,
`(0xD8,0x00)`, and the header says so in as many words. The only thing the firmware is known to
measure is whether the panel answered at all -- `SC1_Cmd_E0_ReadStatus` (`0xF5AAA9`) zeroes both rx
ring indices, sends `(0xE0,0x00)`, waits six ticks and sets bit 3 of `(0x2A85)` if the WRITE index
moved -- and a type-3 packet satisfies that and is then discarded by `SC1_RxOp3_Discard`
(`0xF5B226`). ⚠ The 0xD8 is a CHOICE: type 3 with bits 7:6 = 11, where the KN5000's panel sends
`0x18`, the same type with bits 7:6 = 00. If any of the seven commands actually asks for something
-- a key-repeat rate, an LED brightness, a firmware version -- the emulated panel is answering the
wrong thing and nobody will notice.

**Where to look.** The KN5000 panel MCU's own firmware is undumped, but `kn5000_cpanel.cpp` is an
HLE of the *same part number* and answers a similar opening sequence; a byte-level comparison of
what the KN5000's main ROM sends at open time against these seven is the cheapest next step.

---

### Q. What is on the wire for the DATA ENTRY DIAL (wire 0xD7)? -- PRIORITY 3

**Question.** The analogue curve dispatcher's slot for `0xD7` (prom_a `0xF89825` entry 31 ->
`0xF89AAD`) is a bare `scf`: no curve lookup, no compare against the previous value, every packet
accepted. What does the byte after the address mean -- a signed step count, an absolute position, a
direction flag?

**Why it matters.** `wsa1_cpanel.cpp` sends a SIGNED STEP, clamped to -64..63, and marks that as
inference. It is inference from two facts: a control that must never be de-duplicated is a relative
encoder, and the KN5000's twin protocol uses the same wire address `0xD7` for its endless wheel as
`[0xD7, signed detent]` (`kn5000_cpanel.cpp:269-271`). If the WSA1's consumer reads it as an
absolute position instead, the dial will move menus the wrong way or not at all.

**Where to look.** The consumer is whatever prom_a does with group id `0x0F` -- the group the
wire-address table (`0xF8A109` / `0xF8A189`) assigns to `0xD7` in both variants. Nothing in
`notes/FINDINGS-prom_a-ring-buffers.md` follows the group ids into their readers.

---

### R. What distinguishes SC1 states 0x04, 0x0C and 0x14? -- PRIORITY 3

**Question.** `notes/FINDINGS-prom_b-sc1-link.md` names these three POSITIONALLY and says the
difference is "one SC1BUF write and which of P8CR/P8FC bits 3 and 5 are cleared, and that is not
enough to name a role". What are the three sequences for?

**Why it matters.** It is now partly answered from the emulation side and the answer changed the
CPU model, so the rest is worth finishing. Every SC1BUF write in these three states is a DUMMY: the
routine writes whatever it last had in `A`, which is its own P8CR or P8FC shadow, and does it with
SCLK1's pin function DESELECTED -- so no clock leaves the chip and no data reaches the peer. Only
`SC1_State08_TxFromRing` (`0xF5ADC2`) and `SC1_State10_TxFromRing` (`0xF5AE27`) load a byte from the
tx ring, and both do `or (0x2A87),0x28` -- assign TXD1 and SCLK1 -- immediately before. The overlay
`tmp95c061.cpp` now gates its SC1 transmit callback on exactly that. What is still unexplained is
why the sequence needs three differently-shaped pin dances rather than one.

**Where to look.** `SC1_State04_TxByte1` `0xF5ACE3`, `SC1_State0C` `0xF5AD2E`, `SC1_State14`
`0xF5AD5D`, and the state table at `0xF5AC67`. Note `SC1_State04_TxByte1` also samples P8 bit 5 at
`0xF5AD09` and ABORTS the whole transfer if it reads low -- so at least one of the three is a
bus-collision check.

---

### S. Does an SX-WSA1R carry the key-scan device at 0x108000 at all? -- PRIORITY 4

**Question.** prom_c polls `0x108002` about 34,500 times a second whichever variant the machine is,
and prom_c contains no PB read, so the keybed path is not strap-gated in software. On a rack with no
keybed, what answers -- a scanner IC with nothing attached, a pull-down, or nothing at all?

**Why it matters.** The driver models a 61-key scanner on both variants and gates only the KEY
INPUT PORTS on the model switch, which is a statement about the box rather than about the firmware
and is labelled as one in `keybed_scan()`. If a real rack has no scanner IC, the honest model is an
unmapped read, and `Dev108000_Preload_80toBF`'s 64 write pairs (gap H) go nowhere on that variant.

**Where to look.** The SX-WSA1R parts list and block diagram (manual page II-1); a keybed assembly
or a key-scan PCB would appear in one or the other. Nothing in the ROMs can answer this.

---

## The model-variant hypothesis: SX-WSA1 vs SX-WSA1R -- SETTLED ENOUGH TO IMPLEMENT, and here is exactly how far

Added 2026-08-25 after a survey, an adversarial re-check of that survey, and the driver work that
followed. Recorded in full so a later wave does not repeat the search.

### ESTABLISHED, and now in the driver

* **The detection exists and it is PB bit 0.** prom_a `0xF82882` is
  `ld A,0x01 / bit 0,(PB) / jr NZ,+2 / ld A,0x02 / ld (0xC4),A / ret`, called once from RESET at
  `0xF827D8`, and it is the **only write to RAM `(0x0000C4)` in 512 KiB**. PB bit 0 is an input:
  RESET writes `PBCR = 0x0C` at `0xF826E5`, making only bits 2 and 3 outputs, and PBCR is written
  exactly once in either image (`08 2e 79` at `0xFB1AB9` is a stride table, not an instruction --
  the preceding real instruction is a `reti` at `0xFB1AB3`).
* **The extent: 111 well-formed `cp (0xC4),#imm / jr cc` sites in 27 distinct 4 KiB blocks** --
  109 in prom_a, 2 in prom_b (`0xF440C4` and `0xF44582`, both confirmed against the byte-exact
  assembly at `prom_b/wsa1_prom_b.s:24979` and `:25506`). Every one compares against 1 or 2 and
  nothing else.
* **The shape is unique.** No other CPU-1 direct-page byte has >= 20 tests and <= 1 producer. The
  runner-up `(0xC6)` has 212 tests but 43 producers and is a bit-0 lock flag; `(0x133E)` has 46
  tests and one write, but that write is `and (0x133e),0xfc`, a clear rather than an assignment,
  and two different bits are tested. prom_c has no mode flag at all.
* **What the two arms do**, each disassembled rather than inferred: `0xF8DC25` -- `(0xC4)=2`
  skips all four A/D channel scans (first skipped call `0xF8DC3E ld WA,(0x60)`, SFR `0x60` =
  ADREG0L); `0xFF42EE` -- two display lists, `0xF580B0` with MIDI FILE LOAD / MIDI FILE SAVE /
  LOAD SINGLE SOUND / LOAD SINGLE COMBI. against `0xF58127` with only the last two; `0xF8A109` /
  `0xF8A189` -- the panel's wire-address to group map, eleven button segments and four pots for
  variant 1 against nine segments and one pot for variant 2; `0xF8C8AC` / `0xF8C8B7` -- the
  panel's LED map; `0xF898AD` and six more -- variant 2 forces a controller value to `0x40`.
* **The neighbour that validates the decode.** `(0xC5)` is the expansion-board flag, written 0 at
  `0xF8288F` and `0x5A` at `0xF828C3` after comparing ten bytes read from `0x00C00000` against the
  ROM string `WSA1 EXTBD` at `0xF828C7`, and tested once at `0xFC009E`. Same idiom, known meaning,
  five instructions away.

### CORROBORATED BUT NOT DECODED: which arm is which model

**No string in any of the four images names either model.** The assignment `(0xC4)=2` = rack rests
entirely on two readings of the SX-WSA1R service manual, and **there is no SX-WSA1 document here
to check the other arm against at all**:

1. the specification page's disk menu is "DISK LOAD, DISK SAVE, MIDI FILE DIRECT PLAY, DISK
   FORMAT, LOAD SINGLE SOUND, LOAD SINGLE COMBINATION" -- **no MIDI FILE LOAD, no MIDI FILE SAVE**,
   matching the shorter of the two display lists;
2. the mechanical parts list has **one VOLUME KNOB and one DIAL WHEEL and no bender**, matching the
   one pot (wire `0xD3`) and one encoder (wire `0xD7`) variant 2 keeps -- where variant 1 also has
   `0xD0`, `0xD1` and `0xD2`, and two of those three curves are centre-detented (18 x `0x80` at
   index 120 of 256 in the table at `0xF89CB4`; 13 x `0x40` at index 58 of 128 at `0xF89B34`).

⚠ **A third "match" was claimed and is withdrawn.** The specification line "OTHERS VOLUME, DATA
ENTRY DIAL/KEYS, COMPARE" is an *others* row, not a count of continuous controls, and reading it
as "two, not six" was arithmetic coincidence. It is not evidence.

⚠ And the surviving evidence only establishes "the `(0xC4)=2` machine reads none of CPU 1's own
A/D channels, carries one pot and one encoder on the panel link, and has a shorter disk menu".
That is *consistent* with a rack and does not by itself exclude any other build without that panel
board. Note also that the two *software* analogue channels variant 2 keeps in the `0xF8DC25` scan
are not controls at all: `sub_F8DD4D` / `sub_F8DD62` read RAM `(0x600000)` / `(0x600001)`, parked
at `0x80` by `AnalogScan_InitSoftChannels` and written by the display-list interpreter at prom_b
`0xF57C87`.

**What would settle it:** an SX-WSA1 (keyboard) service manual or its parts list; a photograph of
either machine's CN-numbered panel connector; or a v1/v3 ROM set whose display lists differ.

### REFUTED

* **"CPU 1 has decided it is a rack and is therefore refusing keybed traffic" (the P7-bit-1
  anomaly of gap C) is wrong.** There is not one `cp (0xC4)` anywhere in `0xF8E000-0xF8FFFF` --
  the whole transmit block, `INT0_LinkByte`, `INTTC3` and `Link_ServiceTask` are variant-blind --
  and prom_c, the processor that owns the keybed, contains **no PB read at all**. P7 bit 1 is also
  an **output** (`P7CR = 0x33`), so it cannot be a strap in the first place.
* **The strap does not gate the keybed anywhere.** The rack's firmware scans a keybed
  unconditionally; on the real thing it simply finds none. The driver's keybed gate is therefore a
  statement about the BOX and is labelled as one in `keybed_scan()`.
* **P5 bit 4 is not a model strap** -- see gap L, now closed: it is the service checking device's
  switch.

### UNVERIFIED

* **Whether CPU 1 ever tells CPU 2 which variant it is.** `(0xC4)` has exactly one producer and no
  reader inside the link block, but a *copy* of it could reach a transmitted field, and nobody has
  looked.
* **What the two prom_b strap sites do.** `0xF440C4` and `0xF44582` zero `(0x60341E)` and
  `(0x3000)` and call `0xF45B0A` / `0xF45975`; both are reached through the thunk table
  (`T_F4400C`, `T_F409C8`). Unconverted.
* **Whether an SX-WSA1R even carries the key-scan device at `0x108000`.** The driver models one on
  CPU 2 either way, because prom_c polls its status port ~34,500 times a second and something has
  to answer.

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
* ~~**The six analogue controls** read through `ADREG0`-`ADREG3` plus
  `(0x600000)`/`(0x600001)`.~~ **PARTLY ANSWERED.** They report through the same 32-entry curve
  dispatcher (`0xF89800`, thunk `0xF405F0`) as the panel's own analogue wires, with bits 7:6 of the
  address selecting the source: bank 00 for these six -- eight prom_a callers at `0xF8DC63`,
  `0xF8DC96`, `0xF8DCC9`, `0xF8DCFC`, `0xF8DD54`, `0xF8DD69`, `0xF8DDC3`, `0xF8DDD8`, each preceded
  by `ld W,0x00`..`0x05` -- and bank 11 for the panel link. **`(0xC4)=2` reads none of them**: the
  scan at `0xF8DC25` skips all four ADREG channels, and the two software channels are parked at
  `0x80` by `AnalogScan_InitSoftChannels` and written by the display-list interpreter at prom_b
  `0xF57C87`. What each of the six IS, on the variant that has them, is still unknown.
* **What `0x00E2E1` is for.** It starts at 1000 (ROM `0xFCB4EC`), and while it is positive
  `KeyEvents_ToLink` throws every key event away. So the keybed is deaf for the first 1000 MAIN
  passes after power-on -- harmless, and measured to clear in well under a second of emulated
  time. Nothing converted writes it. If something re-arms it at runtime, the keyboard would go
  deaf again and the emulator would look broken.

---

## Appendix: gaps that are MAME's, not the disassembly's

Listed so a disassembly wave does not spend effort on something the emulator could not use yet.

1. **`tmp95c061` has no serial engine.** `sc0buf_r()` returns 0 and `sc0buf_w()` only sets the
   "transmit complete" interrupt flag (`tmp95c061.cpp:1131-1140`). MIDI IN/OUT cannot be wired to
   anything until a serial implementation exists -- the overlay already has one for the sibling
   part, `tmp94c241_serial.cpp`.
   **PARTLY FIXED for CHANNEL 1 in this overlay (2026-08-25)**, because the control panel needed
   it. `tmp95c061.h` is now overlaid too, and the three additions are `sc1_txd()` (every byte the
   CPU writes to SC1BUF, gated on SCLK1's pin function being selected in synchronous mode -- see
   gap R for why that gate is load-bearing rather than pedantic), `sc1_mod()` (every SC1MOD write,
   so a peer can see RXE) and `sc1_rxd()` (hand the CPU a byte and raise INTRX1). INTRX1 could not
   be raised from outside at all before: `inte_w()` PRESERVES INTES1 bit 3 when a 1 is written to
   it, so a driver could clear the request flag but never set it, and INTRX1 is not a `TLCS900_*`
   input line. Channel 0 and both channels' bit timing are still unimplemented.
4. **`tmp95c061::execute_set_input()` implemented neither INT6 nor INT7**, so
   `set_input_line(TLCS900_INT6, ...)` was silently a no-op even though the enum value exists. Both
   are added in this overlay, rising-edge and UNGATED -- see gap N for why they are not gated on a
   port-B control bit the way INT4 and INT5 are.
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

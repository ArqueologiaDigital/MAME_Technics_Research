# SX-WSA1R: what the emulator needs the disassembly to answer next

Written 2026-08-25 from the emulation side, after reading the 29 findings notes in
`wsa1-roms-disasm/notes/` and rewriting `src/mame/matsushita/wsa1.cpp` against them.

**Revised later the same day**, after the model-variant survey, its adversarial re-check, and the
driver work that followed. **Gaps B, E and L are CLOSED**, gap C's leading hypothesis is REFUTED,
six new gaps (N to S) are added, and a section on the variant hypothesis records exactly what was
and was not established so nobody repeats the search.

**Revised again 2026-08-25 (evening), after the FLOPPY CONTROLLER WAS IMPLEMENTED.** `wsa1.cpp`
now instantiates a `upd765a_device` with a 3.5 inch drive on it and wires INT5, INT7 and TC.
Changes in this revision: **gap B is fully closed and gap J with it**; **gap A is HALF closed** and
this file now says exactly which half; **gap D's question is answered NO, with a reason**, so it
has to be re-asked differently; gap C gains one located caller; gap F gains a two-routine shortest
path; and **six new gaps, T to Y, come out of the driver work itself** -- one of which (T) is now
the single thing standing between "the floppy controller is emulated" and "the machine can read a
disk".

**Revised again 2026-08-25 (late evening), after CONTROL REGISTER 0x3C WAS IMPLEMENTED.** The
TLCS-900 interrupt nesting counter now exists as a real register in the CPU core (appendix item 5),
so prom_a's kernel is entered, the draw task runs, and the machine reaches its **SOUND MODE**
screen instead of sitting on `ALL INITIAL SETTING!`. Every gap below that was blocked on "the UI
never repaints" is now testable on a live UI; nothing in the list is CLOSED by it, but gaps O, P, Q
and R can finally be worked against a screen that answers.

**Revised again 2026-08-25 (night), after THE TMP95C061 TIMERS WERE FIXED AND THE DATABOOK WAS
FOUND.** Every note in these trees said no TLCS-900 databook was available, so the prescaler scale,
the 16-bit timer semantics and control register 0x3C had all been derived from firmware, each with a
residual caveat. **The databook is on bitsavers with an intact text layer**
(`notes/wsa1-probes/tlcs900_datasheet_quotes.py` re-checks 13 quotes and prints the six register
bit-maps that are scanned figures). It closes appendix item 2 outright, retires the "residual x2"
worry on the tap scale, and -- the one nobody could establish from any ROM -- states that INTNEST is
decremented by RETI, which appendix item 5 had implemented on inference alone. Three further defects
it exposed are fixed in the same pass (T4MOD/T5MOD `<CLE>`, two independent comparators instead of
an else-if chain, and TRUN's "Stop & Clear"). **Appendix item 2 is CLOSED.** Nothing in the A-Y list
closes with it, but gap C's numbers all move (its 500-tick deadlines are 1.02 s now, not 16.4 s) and
**three new MAME-side gaps, items 6 to 8, are added** -- one of which, the SX-KN1500's half-blank
IC15 dump, is that machine's entire boot blocker.

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

**2. What drives the floppy drive's MOTOR -- i.e. what is CPU 1's PA bit 3 (gap T, NEW).** The
floppy controller is now a real `upd765a_device` in the driver and it answers the firmware's own
reset/SENSE-INTERRUPT/SPECIFY sequence correctly
(`notes/wsa1-probes/wsa1_fdc_selftest.lua`, 5 checks, 0 failures). What it cannot do is READ
anything: MAME's `floppy_image_device` only reports READY once its motor line has been driven, and
the one output the FDC module owns outside its two device windows -- PA bit 3, set by operation 7
and cleared by operation 6 -- is marked NOT ESTABLISHED, so the driver logs it and refuses to act
on it. Consequence, measured: `SENSE DRIVE STATUS -> ST3 = 0x18`, RY clear, which is the firmware's
error 0x31 "drive not ready". **One pin, and the whole disk subsystem turns on.**

~~**What the 0x7B0004/0x7B0005 + 0x7A0000 subsystem is (gap B).**~~ **CLOSED AND IMPLEMENTED.** It
is the floppy controller; see gap B below, which now has nothing open in it that a disassembly wave
can take.

**3. Which panel button is which bit (gap O), which is now load-bearing twice over.** It was "the
user can only press positions". It is now also **the only way anything in this machine can be made
to use its disk drive**: measured, a 200-second boot of either variant never touches the FDC's
registers at all, and a sweep that pressed all 88 declared panel positions one at a time, for half
a second each, produced ZERO accesses to `0x7B0004`/`0x7B0005`/`0x7A0000`
(`notes/wsa1-probes/wsa1_fdc_probe.lua`, `wsa1_fdc_button_sweep.lua`). `Fdc_Request` has eight call
sites and none of them is on the boot path or one panel press away.

Runner-up, and unchanged in substance: **why CPU 1 never releases the link's receiver-busy line
(gap C).** The emulated CPU 2 sends
exactly ONE packet per boot and is then locked out for good. That is measured, not suspected,
and it is what stands between "the keybed model is read by the firmware" -- which is now
demonstrated -- and "a key press reaches the tone generator". It is also the narrowest of the
three: one interrupt handler on one side. ⚠ The tempting explanation -- "CPU 1 knows it is a rack
and is refusing keybed traffic" -- is REFUTED; see the variant section below.

⚠ The old runner-up, **gap D**, has to be re-asked: the specific test it named was run and the
answer is NO. See gap D below.

---

## The list

### A. What does a 0x0010C000 register do? -- PRIORITY 1, HALF CLOSED, still blocks audio

**HALF CLOSED 2026-08-25** by `notes/FINDINGS-prom_c-dev10c-producers.md`, and the half that is
closed is worth stating precisely because the note itself had to correct its own title over it.

**WHAT IS NOW SETTLED.** All twenty-one routines this entry used to name as "still `.incbin`, so
which staged word is which parameter is not established" -- `0xFA8347`, `0xFA83CC` and the rest --
**are converted**, and there is now a per-register producer index:
`python3 notes/prom_c_dev10c_field_sources.py`. `Dev10C_WriteAllChanRegs` (`0xFB713A`) moves 22
words out of the staging struct at RAM `0x00D75E` into 22 register blocks of one channel, and
**21 of the 22 words have a LOCATED producer**, 70 write sites in all. Word 0 has none, because
block 0 is written with the literal `0x8100` inside the device writer itself.

The word -> block map is now in the driver too, in `tg_data_w()`'s log line: blocks 0-6, 0x10-0x14
and 0x20-0x29 carry staging words 0-6, 7-11 and 12-21. So a trace can be joined to a producer list
instead of being a bare register number. That is a DECODE improvement and nothing more.

**WHAT IS STILL OPEN, and it is the whole original question.** *"Located, not named."* Every
producer in that index is a bare `sub_XXXXXX` label. **Not one register in this device is called
pitch, level, wave address or anything else, here, in the source, or in the driver.** No
synthesis is possible on this, and the driver still stores 4096 words and acts on none of them.

**So the next ask is NAMING, not locating**, and it is three concrete questions:
1. **Which block is the PITCH / phase increment**, and in what units -- a phase increment per
   sample, a semitone-and-fraction, a divisor?
2. **Which block carries a WAVE START ADDRESS** (and is there a second for the loop point)? The
   six wave mask ROMs are undumped, but an address-shaped register is recognisable by its width
   and by arithmetic that shifts rather than adds.
3. **Which block is a LEVEL / envelope target**, and is it linear or logarithmic?

**Where to look, in the order the producer index makes cheapest.**
* **Word 6 -> block `0x0180 + channel` first**, because it is the ONE register the firmware reads
  back (gap F) and it has exactly **two** producers: `sub_FA96F7__FA9801` and `sub_FA9C60__FA9F06`.
  Two routines, one register, and an emulator stub already waiting for the answer.
* **Eleven of the 22 words have exactly two write sites** -- words 2, 3, 6, 10, 11 and 16-21. A
  register with two producers is one routine-read away from a meaning.
* Word 1 -> block `0x0040 + channel` has the most (nine sites, six routines), four of which are the
  same shape stepping record arrays of stride 8, 6, 6 and 4 through the shared 28-byte callee
  `sub_FC4D85` -- the strongest structural signal in the subsystem.
* ⚠ **Do not import the `0x00104000` formula into this gap.** `FINDINGS-prom_c-dev10c-producers.md`
  sec.3 derives `SAT(P[+0x0A] + P[+0x12] +/- delta)` for registers `0x0040`/`0x0080 + chan`, and
  says in as many words that **those are `0x00104000` registers, not `0x0010C000` ones**. Both
  devices have a block `0x0040 + chan`; the note has already had to retract one confusion of the
  two peripheral bases.
* The float library is decoded (`notes/FINDINGS-prom_c-eeprom-and-runtime.md` sec.2), so a compute
  routine's arithmetic can be read rather than guessed -- and note `Float32_Multiply` is really
  `a / (1/b)`, two roundings, which any re-implementation has to copy.
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

★ **AND IT IS NOW IMPLEMENTED (2026-08-25 evening).** The whole 4,794-byte driver module was
converted (`notes/FINDINGS-prom_a-fdc.md`, 138 checks in `notes/prom_a_fdc_checks.py`), and
`wsa1.cpp` now carries:

* `UPD765A(config, m_fdc, 8'000'000, true, true)` with a `FLOPPY_35_HD` on `fdc:0` and the PC
  format set. **Why upd765a and not one of the upd7206x**: the firmware's own validator
  (`Fdc_ClassifyCommandOpcode`, `0xFE5CE8`) accepts exactly the 15 of 32 five-bit opcode values
  that `upd765_family_device::check_command()` accepts, i.e. the BASE command map; the
  `ps2_fdc_device` line that `upd72065/6/7/9` derive from additionally accepts CONFIGURE, VERSION,
  LOCK, PERPENDICULAR and DUMPREG. MAME has **no uPD72070 device**, and no firmware in this ROM
  set can tell the two apart anyway, because the only CONFIGURE the ROM contains is unreachable
  (`FINDINGS-prom_a-fdc.md` sec.8.2).
* `0x7B0004` read -> `msr_r`, `0x7B0005` -> `fifo_r`/`fifo_w`, `0x7A0000` -> `dma_r`/`dma_w`.
* `intrq` -> `TLCS900_INT5`, `drq` -> `TLCS900_INT7`. Both are the firmware's own statement:
  `Fdc_EnableInterrupts` (`0xFE5C03`) arms INTE45 and INTETC01 and nothing else, and
  `uDMA0_ArmOnINT7` (`0xFE5966`) sets `DMA0V = 0x0E`, `(0x0E & 0x1F) << 2 = 0x38` = INT7.
* **PB bit 3 -> TC.** ⚠ This is the one INFERENCE the implementation costs, and it is written up as
  such at the code and as gap U below.

**The two things this entry used to list as open are both answered:**
1. **The three SCANs in the device -> RAM group is not an anomaly after all.** A uPD765 SCAN
   command's data phase moves bytes in BOTH directions -- the host supplies the pattern and the
   controller compares -- and the DMA setup that matters for MAME is the one this driver picked,
   because `dma_r()`/`dma_w()` are two ends of the same FIFO. It remains an oddity of the ROM's
   own direction table, not of the model. *(Recorded as reconciled, not as proven: nothing was
   measured, because the firmware never issues a SCAN.)*
2. **Both routines are converted.** `0xFE5A41` is `Fdc_WaitRqm` and `0xFE5B5E` is
   `Fdc_ClassifyResultStatus`, and the classifier tests ST0 bits 3 and 4 and all six DEFINED ST1
   bits and neither undefined one -- which is a large part of why the identification stands.

**Verified after wiring** (`notes/wsa1-probes/wsa1_fdc_selftest.lua`, which replays
`Fdc_ResetAndIdentifyMedia`'s exact byte sequence through CPU 1's address space): MSR reads `0x80`
and not `0xFF` (so the firmware's own "no controller" test, error `0xFC`, passes); the post-reset
SENSE INTERRUPT STATUS drain terminates on `ST0 = 0x80` exactly as `0xFE563A` requires; SPECIFY
consumes its two parameter bytes; SENSE DRIVE STATUS returns one byte. 0 checks failed.

**What is NOT demonstrated, and it is not a disassembly gap:** the FIRMWARE has never been seen to
drive it -- see the top-three list, gap O and gap V.

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

⚠ **RE-MEASURE THIS ONE.** The numbers below were taken with the 16x-slow prescaler (appendix
item 2), so every wall-clock figure in them is meaningless now and the 500-tick deadlines they
race against are 1.02 s of emulated time rather than 16.4 s. The *shape* of the failure survived
the fix -- CPU 1 still burns a 0x4E20-spin wait on P7 bit 3 at `0xF8E086` -- but the timing changed
by a factor of 16, which is exactly the sort of change that can turn a timeout race one way or the
other. Nothing here should be quoted until the script is re-run.

**Measured with the OLD timer model, so a fix has a target to hit**
(`notes/wsa1-probes/wsa1_link_handshake.lua`):

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

★ **ONE CALLER LOCATED, 2026-08-25** (`notes/FINDINGS-prom_a-remote-flash.md` sec.4).
`Link_WaitBlockDone` (`0xF8E66D`) -- the second of the two deadline loops below, the ~1 s one that
ends in `set 1,(0x13)`, i.e. the one that WOULD release the line -- is called from exactly two
places in converted prom_a, `0xFB24D7` and `0xFB256E`, and both are immediately after a
remote-flash read request. So that release path is on the REMOTE-FLASH READ path specifically, and
a machine that never runs one never reaches it. That is consistent with the measurement below and
narrows the question to: **what releases the line for ORDINARY traffic?** `INTTC3_LinkDmaDone`'s
three `set` sites remain the only other candidates.

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

### D. Tie prom_d to an instruction -- ★ THE QUESTION AS ASKED IS ANSWERED **NO**; RE-ASK IT

**The old question was:** does any instruction in prom_a/prom_b index prom_d's 44-entry offset
header at file `0x000000`, or its 274-entry pointer directory at file `0x000B80`, with an address
that comes back over the link from CPU 2's flash?

**Answered 2026-08-25 by `notes/FINDINGS-prom_a-remote-flash.md` sec.3, and the answer is NO with a
reason: nothing on that path indexes the remote image at all, because the firmware STREAMS it.**
`Remote_E80000_Read32Blocks` (`0xFB24EC`) walks `XIX = 0x00E80000` in 32 fixed 8 KiB blocks through
one staging buffer at RAM `0x60A000` -- 31 loop iterations plus one more block after the loop,
`32 x 0x2000 = 0x40000`, i.e. remote **`0xE80000-0xEBFFFF`, 256 KiB, HALF the prom_d image**. No
directory is consulted on CPU 1's side, so no directory reference can ever be found there.

**What this changes for the driver.** Nothing yet, and that is the point. `prom_d` is still a
region mapped **nowhere** and `0xE80000-0xEFFFFF` on CPU 2 is still unmapped, because a streamed
read is satisfied by any 256 KiB of bytes: it is evidence about the READER, not about the CONTENT.
Mapping an undumped flash from an inferred image would still put invented bytes on the bus, and
now we also know the reader could not tell.

**RE-ASKED, three ways, in decreasing cheapness:**
1. **What CONSUMES a block?** `0xFB7649` and `0xFB6FB2` are converted but still `sub_`. If either
   parses a structure whose shape matches prom_d's -- a 16-byte printable name at the head of every
   record, say -- that is the tie, and it is a content argument rather than an address one.
2. **What is in the OTHER 256 KiB?** The streamer covers `0xE80000-0xEBFFFF`; prom_d is 512 KiB and
   its payload runs to file `0x050B08`. Does any other path read `0xEC0000-0xEFFFFF`?
3. **The single-block sibling at `0xFB248A` passes count `0x0000`** and carries no label; a
   zero-length read, a `0x10000` wrap and a position probe all fit the byte.

**Where to look.** `notes/FINDINGS-prom_a-remote-flash.md` sec.3 throughout;
`notes/FINDINGS-memory-map.md` sec.3 and sec.5 for the grading this supersedes.

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

★ **THE SHORTEST PATH IS NOW TWO ROUTINES LONG.** Register block `0x0180 + channel` is staging
word 6, and `notes/FINDINGS-prom_c-dev10c-producers.md` sec.2 gives word 6 exactly **two**
producers: `sub_FA96F7__FA9801` and `sub_FA9C60__FA9F06`. Read those two and this stub can be
replaced with something true, or shown to need more. That note's own "what the next pass should do"
puts the same pair first.

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

### J. What is the device at 0x7E0008 on CPU 1? -- ROLE FOUND 2026-08-25, PART STILL UNKNOWN

★ **It is the machine's SECOND STORAGE UNIT**, driven by the same block-device layer as the floppy.
`Fdc_Request` (`0xFE66C7`) takes a `unit` field at request+`0x02`; every one of its twelve
operations begins `cp (0x605A32),1`; and **all seven** unit-1 arms in `0xFE4CE0-0xFE544D` reach the
four accessors of this port, which are the only `add Xrr,0x007E0000` instructions in the converted
text of either image (`notes/FINDINGS-prom_a-fdc.md` sec.6, checked by
`notes/prom_a_unit1_backend_check.py`).

**So the entry that used to read "two bytes of the driver's map are inert" now reads: two bytes of
the driver's map are a storage device whose PART is unknown**, and it stays `.noprw()` for exactly
that reason -- no part name, no register meaning, and "two banks of eight 16-bit registers" is read
off the accessor's index construction alone, never off a sweep.

**Re-asked, and now much sharper because the twelve operations are named:**
1. **Which of the twelve operations does the unit-1 back end actually implement?** The seven arms
   are `0xFE4CE0-0xFE544D`; a per-operation table of "which registers does this arm touch" would
   say whether it is a block device with tracks and sectors (a second FDD? a memory card?) or
   something addressed flat.
2. **Is `| 0x08` versus `| 0x10` two banks, or a command/data split?** In the only traced caller
   both indices are zero for all 256 iterations, so `0x7E0008` is the only address known to be
   reached and the `| 0x10` bank has never been observed at all.
3. The transfer is bracketed by a CS0 timing change (`0xFE509B ldio B0CS,0x10` ...
   `0xFE50D5 ldio B0CS,0x14`), i.e. a device that needs relaxed bus timing. Which is it?

**Where to look.** `notes/FINDINGS-prom_a-fdc.md` sec.6; `notes/FINDINGS-memory-map.md` CPU 1
table, the `0x7E0008-0x7E0017` row.

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

### T. What does CPU 1's PA bit 3 drive? -- PRIORITY 1 (NEW), blocks every disk read

**Question.** `Fdc_Op7_PortA3_On` (`0xFE661F`) sets PA bit 3; `Fdc_Op6_PortA3_Off` (`0xFE65EF`)
clears it and then waits 5 ticks. They are its only writers in either image, and it is the floppy
module's only output outside its two device windows. Is it the drive MOTOR, drive SELECT, drive
POWER, or something else -- and is it active high or active low?

**Why it matters.** This is now the single thing between "the floppy controller is emulated" and
"the machine can read a disk". MAME's `floppy_image_device` reports READY only after its motor line
has been driven (`mon_w()` off->on starts a spin-up counter and only then calls `set_ready(false)`),
and `upd765a_device` does not drive that line itself -- a device with no DOR has nothing to drive it
with, so a board pin must. The driver therefore LOGS PA bit 3 and refuses to act on it, and the
measured consequence is `SENSE DRIVE STATUS -> ST3 = 0x18`: RY clear, which the firmware turns into
its error `0x31`, "drive not ready", for any request whatever
(`notes/wsa1-probes/wsa1_fdc_selftest.lua`).

⚠ **And the obvious answer does not fit as neatly as it looks.** RESET writes `ldio PA,0xF9` with
`PACR = 0x0E`, so PA bit 3 comes up **HIGH**, and operation 7 -- the one a caller issues *before* a
transfer -- sets it high again. An active-high motor enable would then be asserted from power-on,
which is not how a floppy drive is driven. Active low, or not a motor, both survive that; the
disassembly's own verdict is "a drive-motor or drive-select line is the obvious reading and is NOT
claimed here", and the driver keeps that refusal.

**Where to look.** `notes/FINDINGS-prom_a-fdc.md` sec.5 and sec.9; the two operations in
`prom_a/wsa1_prom_a.s`. The ROM may not be able to settle it -- the eight `Fdc_Request` call sites
in the `0xFE3000` module are the only callers, so what the SEQUENCE of operations is around a real
disk access (7 then 0 then 3? 6 after?) is the one thing the ROM *can* say, and it would decide
between "motor" (asserted only around a transfer) and "drive power/select" (asserted permanently).
Failing that, a legible schematic sheet for the FDD connector.

---

### U. Is PB bit 3 the floppy controller's TC? -- PRIORITY 2 (NEW), confirm or refute an inference

**Question.** `PortB3_Pulse` (`0xFE594C`) drives PB bit 3 high for five NOPs and low again, from
`INTTC0_uDMA0Done` (`0xFE6858`) and from nowhere else, and the programmed-I/O path
`Fdc_ServiceDataByte` ends its transfer with the same pair. Is that pin the FDC's TC input?

**Why it matters.** The driver **assumes it is** -- `cpu1_pb_w()` calls `m_fdc->tc_w()` -- and says
so at the code as the one inference the floppy implementation costs. It is not idle: a uPD765
multi-sector transfer runs to EOT unless TC ends it, so if the firmware ever asks for fewer sectors
than the track holds, TC is what stops the data phase and lets the result phase start. Without it
that request would hang until the firmware's own 500-tick INT5 timeout (error `0x09`).

**What supports it, so a refutation knows what it has to beat:** it is pulsed exactly at
micro-DMA channel 0's end of count and at no other time; two independent data paths pulse it at the
same instant; RESET's `ldio PB,0xF3` leaves it idling LOW so the pulse is a real low-high-low,
which is TC's active-high shape; and on a uPD765-family part no other input pin means "the transfer
is over".

**Where to look.** A schematic sheet, or any prom_a code outside the floppy module that touches PB
bit 3 -- `notes/prom_a_addr_census.py` over SFR `0x1F` would settle whether the floppy module is
really its only writer. If something else pulses it, the inference is wrong.

---

### V. How does a user reach `Fdc_Request` at all? -- PRIORITY 2 (NEW)

**Question.** `Fdc_Request` (`0xFE66C7`) has exactly eight call sites -- `0xFE3034`, `0xFE30B2`,
`0xFE3639`, `0xFE37B3`, `0xFE37E2`, `0xFE3868`, `0xFE444A`, `0xFE446E`. What reaches each of them,
and from which UI action?

**Why it matters.** Purely so the emulated machine can be MADE to use its disk drive. Measured, and
this is a negative with the search named: a 200-second boot of `wsa1r` and of `wsa1` touches
`0x7B0004`, `0x7B0005` and `0x7A0000` **zero** times
(`notes/wsa1-probes/wsa1_fdc_probe.lua`), and a sweep that pressed each of the 88 declared panel
positions on its own for half a second, after boot, produced **zero** accesses as well
(`notes/wsa1-probes/wsa1_fdc_button_sweep.lua`). So the disk path is not one press away; it needs
either a menu sequence, or a chord, or a machine that has got past `ALL INITIAL SETTING!`.

**Where to look.** The `0xFE3000` module's entry directory, and whichever display list in prom_b
carries the disk menu -- `0xF58127` for variant 2 and `0xF580B0` for variant 1, from the strap
survey. This is the natural companion to gap O.

---

### W. Is the write side of 0x7B0004 the uPD765 DSR? -- PRIORITY 3 (NEW), an emulation-side ANSWER to check

★ **This one is a proposed ANSWER, not a question, and it should be checked rather than
re-derived.** `notes/FINDINGS-prom_a-fdc.md` sec.5 and sec.9 record the write side of `0x7B0004` as
"a control register ... written with `0x80`, `0x02` and `0x00` ... ⚠ Which bit does what is NOT
established." Reading it as the uPD765-family **Data Rate Select Register** accounts for all three
values and for the register's offset at once:

* the device is decoded at **base+4** (status / control) and **base+5** (data), which is exactly
  MSR/DSR and the FIFO in the standard uPD765-family register layout;
* `0x80` is DSR bit 7, **software reset**, and it must be self-clearing: `Fdc_ResetAndIdentifyMedia`
  writes it at `0xFE55C5`, waits two ticks and then issues SENSE INTERRUPT STATUS and SPECIFY --
  commands a part held in reset could not accept;
* `0x00` and `0x02` are the **data rate**, and the ROM says which is which by WHICH GEOMETRY gets
  it. After `Fdc_MediaTypeJumpTable` (`0xFE6E3A`) dispatches the media nibble: geometry 2 (1.2 MB,
  1024 B x 8) and geometry 3 (1.44 MB, 512 B x 18) take `0xFE5690`, which pushes **`0x00`**;
  geometries 0, 4 and 5 (720 KB, 512 B x 9) take `0xFE56B2`, which pushes **`0x02`**. The
  uPD765-family rate table is `{500000, 300000, 250000, 1000000}`, so that is **500 kbps for both
  high-density geometries and 250 kbps for the double-density one** -- two values, two correct
  answers, and no other reading of a two-bit field produces that pairing.

**Why it matters.** The driver acts on it (`fdc_ctrl_w` -> `dsr_w`), so if it is wrong the emulated
data rate is wrong and any future disk read fails in a way that will look like a format problem.

**What would refute it:** any fourth value ever written to `0x7B0004`, or a write of `0x00`/`0x02`
on a path that has nothing to do with choosing a geometry. `notes/prom_a_fdc_checks.py` already
parses these constants out of the ROM and is the place to add the assertion.

---

### X. Why are the three SCAN opcodes in the device -> RAM group? -- PRIORITY 4 (NEW, was inside gap B)

**Question.** `Dev7A_StartDma` (`0xFE596A`) puts `0xD1`/`0xD9`/`0xDD` -- SCAN EQUAL, SCAN LOW OR
EQUAL, SCAN HIGH OR EQUAL -- in the *device -> RAM* arm, but a SCAN's data phase needs the HOST to
supply the pattern bytes. Is the direction table simply wrong for commands the firmware never
issues, or does this controller's SCAN work the other way round?

**Why it matters.** Almost not at all, which is why it is priority 4: the firmware has no reachable
caller that issues a SCAN, and MAME's `dma_r`/`dma_w` are two ends of one FIFO so the model does not
care. It is recorded because it is the one line of the identification that was never reconciled.

**Where to look.** `Fdc_SendSectorIdParams` (`0xFE5DB6`) special-cases exactly these three opcodes
to send STP instead of DTL, so the driver clearly knows they are SCANs; whatever sets `(0x605A18)`
to one of them, if anything does, is the thread.

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
* **What a disk written by this machine LOOKS like.** The firmware programmes three standard
  geometries and formats with the conventional `0xE5` filler, so a disk it writes should be
  readable by ordinary tools -- but no SX-WSA1 or SX-WSA1R disk image exists in these trees, and the
  driver's floppy support has therefore never been tested against real media. I cannot frame this
  as a ROM question at all; it needs a disk.
* **Whether the SX-WSA1R has a SECOND drive fitted, or only the port for one.** Gap J establishes
  that `Fdc_Request`'s unit 1 goes to `0x7E0008`, which is *not* the floppy controller. Whether that
  is a second storage device on the board, an option, or a port that is empty on every machine ever
  built, nothing here can say -- and the boot path never issues a unit-1 request, so the firmware
  does not say either.
* **Whether the floppy subsystem works at all on a machine stuck at `ALL INITIAL SETTING!`.** Both
  variants sit on that message with the battery-RAM checksums failed. It is not known whether the
  disk menu is even reachable from that state on real hardware, so gap V's negative measurement may
  be measuring the wrong machine state rather than the wrong button.
* **What `0x00E2E1` is for.** It starts at 1000 (ROM `0xFCB4EC`), and while it is positive
  `KeyEvents_ToLink` throws every key event away. So the keybed is deaf for the first 1000 MAIN
  passes after power-on -- harmless, and measured to clear in well under a second of emulated
  time. Nothing converted writes it. If something re-arms it at runtime, the keyboard would go
  deaf again and the emulator would look broken.

---

## Appendix: gaps that are MAME's, not the disassembly's

Listed so a disassembly wave does not spend effort on something the emulator could not use yet.

5. **~~`tmp95c061` has no control register 0x3C~~ -- IMPLEMENTED IN THIS OVERLAY 2026-08-25.**
   This was the single biggest MAME-side gap on this machine: it is the difference between a splash
   screen and a working UI. Control register 0x3C on the TLCS-900/H (0x7C on the /H1) is **INTNEST**,
   the interrupt NESTING COUNTER -- the CPU increments it when it accepts an interrupt and decrements
   it on RETI. MAME had no such register: `900tbl.hxx`'s `p_CR16` decoded only the DMA counters and
   sent every other control-register number to `&m_dummy.w.l`, the scratch word that ALSO absorbs
   every other undecoded control-register reference, and nothing ever counted. prom_a's whole RTOS
   hangs off it -- `IRQ_Epilogue` (0xF857B7) enters the scheduler only when it reads exactly 1,
   `Kernel_Dispatch` (0xF85715) refuses to reschedule unless it reads 0, `Kernel_ServiceSoftTimers`
   brackets its callbacks with depth++/depth--, and `SWI7_ServiceCall_Dispatch` zeroes it at
   0xF8E9A8 -- so the kernel was never entered.
   Now implemented properly, in both halves: real 16-bit storage in `tlcs900.h` (registered in save
   state, cleared in BOTH `device_reset()` bodies -- `tlcs900h_device`'s does not chain to the base
   one), decoded at 0x3C and 0x7C in both `p_CR16` operand positions, incremented at each device's
   interrupt-acceptance site through `tlcs900_intnest_accept()`, and decremented in `op_RETI`.
   Both ends saturate rather than wrap. 16-bit only: no firmware in these trees uses an 8- or
   32-bit `ldc` on it, and the 8/32-bit CR paths deliberately do not decode it.
   ★ **The half of this that was inference is now primary-sourced (2026-08-25).** The ROM evidence
   only ever showed the INCREMENT -- prom_a reads the counter, and biases it across an `ei 0x00`
   window at 0xF8576C -- and an adversarial pass named "cr 0x3C is auto-DECREMENTED by RETI" as the
   single claim most likely to be wrong, since a wrong decrement would underflow on the firmware's
   own leave-without-RETI paths. The databook settles it, section 3.3.1 p.11, verbatim: step "(4)
   The CPU increments the INTNEST (Interrupt Nesting Counter)", and "Executing this instruction
   [RETI] restores the contents of the program counter and the status registers and decements the
   INTNEST (Interrupt Nesting Counter)" (sic). What the databook does NOT give is the
   control-register NUMBER -- its CPU-control-register figure on p.15 lists only DMAS/DMAD/DMAC/DMAM
   -- so 0x3C/0x7C still come from what these ROMs address, and only the mechanism is sourced.
   ⚠ `tlcs900.h`, `tlcs900.cpp`, `900tbl.hxx` and `tmp95c063.cpp` are now overlaid for this, and
   they are shared with every tlcs900 driver in MAME. See
   `notes/wsa1-probes/README.md` for the measurement and for what it means for the KN5000.

0. **MAME has no uPD72070 device.** The parts list gives the floppy controller as a NEC
   D72070GF3BE; `src/devices/machine/upd765.h` declares uPD765A/B, uPD7265, i8272A, i82072,
   uPD72065/6/7/9, FDC9266 and a dozen PC super-I/O parts, and nothing in that family is a
   uPD72070. The driver instantiates `upd765a_device` and argues at the code why that is the right
   member (the firmware's own validator implements the BASE command map, and the one enhanced
   command the ROM contains -- CONFIGURE -- is unreachable). ⚠ This is a SUBSTITUTION and it is the
   thing a MAME reviewer should push back on first. Nothing in this firmware can distinguish the
   two, so it is not currently a defect; it would become one the moment a uPD72070-specific command
   is found.

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
2. **~~`tmp95c061`'s 8-bit timer prescaler taps are 16x slow, and its 16-bit timers 4-7 do not
   count~~ -- CLOSED AND IMPLEMENTED 2026-08-25.** Six defects, all in the overlay's
   `src/devices/cpu/tlcs900/tmp95c061.cpp`, each commented at the line with its databook page:

   | # | defect | what the databook says |
   |---|---|---|
   | 1 | prescaler taps `>>7 >>9 >>11 >>15` = fc/128 … fc/32768 | Table 3.8 (1) p.81: `oT1 (8/fc) · oT4 (32/fc) · oT16 (128/fc) · oT256 (2048/fc)` -> shifts 3/5/7/11 |
   | 2 | the 16-bit up-counters were never counted; `m_t16_reg` had no reader and nothing ever set `INTET54`/`INTET76` | 3.9 (5) p.103 for the compare behaviour, Table 3.3 (1) p.12 for `INTTR4 = 16-bit timer4 (TREG4)` at vector 0050H |
   | 3 | `T4MOD`/`T5MOD` bit 2 `<CLE>` ignored, so a counter always cleared on the high match | Figure 3.9 (3) p.95: "0 Clear disable / 1 Clear by match with TREG5". The SX-WSA1R writes `T5MOD = 0x02` at 0xF82718, CLE = 0, and RUNS timer 5 -- UC5 free-runs on real hardware |
   | 4 | the two compares chained with an `else if`, so an equal pair could raise only one interrupt | 3.9 (5) p.103: "These are 16-bit comparators … the comparators generate an interrupt (INTTR4, INTTR5 / INTTR6, INTTR7), respectively" -- two of them. The SX-WSA1R writes TREG6 == TREG7 == 0x3A98 |
   | 5 | `trun_w` cleared `m_timer_8[4]`/`[5]`, two unused 8-bit slots, instead of the 16-bit counters | Figure 3.9 (10) p.101: TRUN b4/b5 are "0: Stop & Clear" |
   | 6 | an 8-bit timer match set its request flag without setting `m_check_irqs`, so the interrupt waited for an unrelated EI/RETI | `tmp94c241.cpp` already does it; this file was the odd one out |

   **Measured, same source tree, timers reverted vs fixed.**
   `notes/wsa1-probes/tlcs900_timer_control.sh {null|fixed}` switches between the two builds and
   `wsa1_inttr4_dispatch.lua` / `wsa1_boot_milestones.lua` do the counting:

   | signal | reverted (upstream) | fixed | what the firmware asks for |
   |---|---|---|---|
   | INTT1, RAM 0x0080 tick | 30.5 Hz | **488.27 Hz** | 28e6/2048/28 = 488.281 |
   | INTT1 dispatch | 30.5 Hz into 0xF82D0B | 488.3 Hz into 0xF82D0B | |
   | INTT3, the RTOS tick | never dispatched in 45 s | first at t = 19.65 s, into 0xF42D64 | |
   | **INTTR4, the musical clock** | **never dispatched** | **192.00 Hz into 0xF82EA2** | 3.5 MHz / TREG5 = 18229 = 96 PPQN at exactly 120.00 BPM |
   | INTTR5/6/7 dispatches | 0 | 0 | must stay 0 -- their vectors are `jr T,self` hang loops at 0xF82D09 |
   | SED1330 first write | t = 7.2095 s | **t = 0.5003 s** | |
   | SWI7 text drawing | t = 72.2382 s | **t = 19.6181 s** | |
   | `INTET76` readback | 0x80 | **0x88** | defect 4: INTTR6's request flag exists now |

   ⚠ **224 Hz WAS A BOOT TRANSIENT and the earlier note saying INTTR4 "runs at 224 Hz" is
   corrected.** The boot value TREG5 = 15625 gives 224 Hz = 140 BPM for about twelve seconds; prom_a
   then stores 18229 (`0xFA5559 ld WA,0x4735`) and the steady state is 192.00 Hz.

   **Per-machine regression, all nine systems, same binary.** `-validate` exits 0 with no output;
   `-listfull` shows all nine; `tools/gate.sh` passes **17 / 0 / 1** with every liveness hash equal
   to its recorded baseline (kn7000 `316cd785`, kn5000 `b1a48d45`, kn6000 `9e0b3785`, kn6500
   `82075785`, kn2400/kn2600 `571e1a45`), the KN7000 audio oracle at `780de131…` and the KN5000 demo
   oracle at `4c8671b6…` (rms 499.8).

   | machine | CPU | what was checked | result |
   |---|---|---|---|
   | `wsa1r` | TMP95C061 x2 | the whole table above, plus a t = 45 s snapshot | reaches **SOUND MODE** with its parameter row |
   | `wsa1` | TMP95C061 x2 | 25 s launch | runs at 99.10%, the three NO_DUMP warnings and nothing else |
   | `kn1500` | TMP95C061 | `kn1500_timer_regression.lua`, 30 s, both builds | **unchanged**: same crt0 RAM test at 0xFA047F-0xFA04A3, same speed (99.4% vs 99.5%). Its INTTR4 now dispatches into 0xFE6515, the sequencer routine its own ROM names |
   | `kn5000` | TMP94C241 | gate liveness + demo audio oracle + snapshot | play screen, both hashes unchanged. **This is the machine that could have been broken** -- it runs the sibling device off the same shared `tlcs900.{h,cpp}` / `900tbl.hxx` |
   | `kn6000` `kn6500` `kn2400` `kn2600` `kn7000` | MN10300 | gate liveness + snapshots | unchanged; they share nothing with this work |

   ⚠ **SHARED DEVICE, for the review Felipe asked to defer.** Defects 1 and 6 change behaviour for
   every TMP95C061 machine in MAME -- `snk/ngp.cpp`, `namco/namcos10.cpp` (+ `namcos10_exio`),
   `samsung/dvd-n5xx.cpp` and `skeleton/kkcount.cpp`. Defects 2-5 are additive: they do nothing
   unless firmware sets TRUN bits 4/5. `ngp` is the one to A/B and it is evidence *for* the change
   -- SNK's own NGP developer manual says "T16 is 128/fc. 6144000/128 = 48000hz", which is this
   scale and not upstream's. **`ngp` is not in this binary** (`-listfull` shows nine Technics
   systems and nothing else), so that A/B cannot be run here. `tmp95c063.cpp` carries the identical
   wrong shifts and is deliberately NOT changed.
3. **`tmp95c061` dispatched writes to P6 (internal address 0x12) to the PORT_7 callback.** Fixed
   in this overlay's copy; without it the EEPROM never sees chip select.

6. **The SX-KN1500's IC15 program dump is HALF BLANK, and that is its whole boot blocker (NEW
   2026-08-25).** Not a WSA1 gap, but it is on this list because kn1500 is the other TMP95C061
   machine and `tools/gate.sh` SKIPS it ("no screen device"), so nothing was watching it. Split the
   2 MiB image into eight 256 KiB blocks: four of them -- 0xE00000, 0xE40000, 0xF00000, 0xF40000 --
   have **0xFF in every odd-offset byte**, and each one's even stream is **exactly** the odd stream
   of the block 512 KiB above it, 131072 of 131072 bytes, all four pairs. Re-measure with
   `notes/wsa1-probes/kn1500_ic15_dump_defect.py` (4 PASS / 0 FAIL).
   It is load-bearing: the crt0 memory test at 0xFA0460 reads 10-byte region descriptors from a
   table at **0xF38B24, inside a damaged block**, gets `start = 0xFFDEFFF2 / length = 0xFFF2FF00`,
   and walks the entire 24-bit space -- which is how it ends up writing its 0xA5/0x5A pattern over
   the CPU's own internal I/O registers (`tlcs900_16bit_unmodelled_use.lua` caught it scribbling on
   T4MOD, T4FFCR and T45CR). The machine never leaves that loop.
   The obvious repair does **not** work: treating the four undamaged blocks as the real 1 MiB ROM
   leaves 0xF38B24 pointing at instrument-name ASCII. **IC15 needs a re-dump**; nothing should be
   invented in the meantime, and `kn1500.cpp`'s ROM comment now says so instead of calling its
   BAD_DUMP "conservative".

7. **The 16-bit timers' capture path is still fabricated, and one machine already asks for it
   (NEW).** `m_t16_cap[4]` is never written, so `cap12_r`/`cap34_r` (internal I/O 0x34-0x37 and
   0x44-0x47) return zero forever -- a made-up value, not an unimplemented one. Measured with
   `notes/wsa1-probes/tlcs900_16bit_unmodelled_use.lua` over a 60 s boot of both TMP95C061 machines:

   | request | SX-WSA1R (cpu1) | SX-KN1500 |
   |---|---|---|
   | CAP1/CAP2 read | 0 | 24 (all from the runaway RAM test, pc = 0xFA0481) |
   | CAP3/CAP4 read | 0 | 24 (same) |
   | software capture (`T4MOD`/`T5MOD` bit 5 written 0) | **3** | 8 |
   | external clock select (bits 1:0 = 00) | 0 | 0 |
   | pin capture mode (bits 4:3 non-zero) | 0 | 6 (RAM test writing 0x5A) |
   | `T4FFCR`/`T5FFCR` non-zero | 0 | 12 (RAM test writing 0xA5) |
   | `T45CR` non-zero | 0 | 3 (RAM test writing 0x5A) |

   So on the SX-WSA1R every gap is genuinely unreachable except the software capture, which its boot
   issues three times as a side effect of `ldio T4MOD,0x05` / `ldio T5MOD,0x02` (databook Figure
   3.9 (4) p.96: bit 5 always reads as 1, and writing 0 loads the up-counter into CAP1/CAP3) and
   then never reads back. Every KN1500 column is the memory test of item 6, not real use.
   **Documented rather than implemented, deliberately**: implementing capture would mean choosing
   what CAP1 contains at a moment no firmware here observes. Re-run the probe on any new TMP95C061
   machine before assuming that still holds.

8. **`T45CR` is stored and never decoded, and that is now known to be exact rather than lucky
   (NEW).** Figure 3.9 (9) p.101 gives it as b0 `DB4EN` / b1 `DB6EN` -- the TREG4/TREG6 double-buffer
   enables -- and b2 `PG0T` / b3 `PG1T`, the pattern-generator shift-trigger widths. It is not an
   operating-mode register, which is what the earlier note feared. Both Technics firmwares write
   0x00, i.e. every field at its reset default, so ignoring it is correct here. It stops being
   correct the moment a driver enables a double buffer: the databook says the buffer is transferred
   into TREG4 at the TREG5 match, and nothing models that.

Item 3 also **closes** a disassembly-side unknown found while doing this work, recorded here so
it is not asked again: `Timer1_SetPeriodAndStart`'s header and
`notes/FINDINGS-prom_c-scheduler.md` both say CPU 2's timer-1 clock source is unknown because "no
write to T01MOD has been located". There is one: **`0xFFF06C  08 24 0d  ldio T01MOD,0x0D`**, in
RESET, between `ld XIX,0x00100000` (`0xFFF067`) and `ldio P8CR,0x19` (`0xFFF06F`). `0x0D` selects
**phiT256** for timer 1 and phiT1 for timer 0 -- the same taps CPU 1 programs at `0xF826EB` -- so
CPU 2's tick is the same 488.28 Hz, and the scheduler's 250- and 1000-tick gates are 0.5 s and
2.0 s of real time. Verified live: the counter at `(0x00F2F3)` advances and the key scanner arms
(`notes/wsa1-probes/wsa1_cpu2_tick_and_keyscan.lua`).

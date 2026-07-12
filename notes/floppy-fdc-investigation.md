# Floppy drive (FDC IC103) — investigation groundwork (2026-07-11)

Felipe's list includes "emulate the floppy disk drive." The KN7000 has a 3.5" FDD (service manual
Part VI Disk Drive p122-137; DISK MENU = Load/Save/DIRECT PLAY/Medley/Tools). FDC = **IC103** (named
in the service-test IC map; not yet mapped in the driver).

## What was found
- The disk stack is HEAVILY abstracted, so the FDC I/O address is a RUNTIME value, not a static one:
  - FAT read: `0x485335FF` (works on RAM FS structs at 0x50071xxx) -> calls `0x48532468`.
  - `0x48532468` = a disk-driver DISPATCHER: it indexes `0x5007125a` (the "disk type" selector, 0/1/2)
    into a function-pointer table and `calls (a1)`.
  - **Driver table @0x486646f0 (read) / @0x486646fc (write), 3 entries each** (floppy/SD/USB):
    read = {0x4853282e, 0x48565af6, 0x48584212}; write = {0x485328b5, 0x48565b84, 0x48584370}.
    Driver [0] (0x4853282e) is the primary/floppy; it walks a device struct at 0x50071254 and calls
    `0x4846da31` (block read).
  - `0x4846da31` reads a DEVICE REGISTER via an indirect pointer `(a1)` (movbu (a1),d0; btst 0x01/0x02),
    updates status 0x500ad390, and `calls (a2)` (a device method). So the real FDC register base is in
    the device struct (a1 / a2), set up by a disk-init routine -- NOT a literal in the read path.
- The FDC is NOT touched during a plain boot (verified: a -verbose boot's unmapped accesses are only
  0x41000000/0x41800000 [an EXPANSION/data-header region: a struct with a self-check
  base+[base]==base+0x200 and a byte-table scan vs 0x485b8518 -- likely SOUND EW EXPANSION or a config
  ID, NOT the FDC] and flash writes to 0x480Fxxxx/0x4813xxxx). So the FDC I/O only appears once a disk
  operation actually runs.

## To locate the FDC (next dedicated effort)
1. Find the disk-device INIT that fills the 0x50071254 struct's register pointer (a1) -- search for
   writes to 0x50071254 + the device-struct setup; that literal is the FDC base address.
   OR
2. Set a debugger breakpoint at 0x4846da39 (the `movbu (a1),d0`) and read a1 -- but that path only
   runs on a disk op, so drive the DISK MENU (Load) with a floppy image attached first.
   OR
3. Find the low-level FDC reset/SPECIFY at boot if any (uPD765-family FDCs get a SPECIFY 0x03 +
   RECALIBRATE 0x07 at init) -- search for those command bytes written to a fixed I/O address.
3. Identify the chip (uPD765/uPD72065/SMC37c?) from the command set, then use MAME's upd765 family +
   a floppy_image_device, model the KN7000 disk format, and wire the 3 driver slots.

## Assessment
A genuine multi-tick task (FDC model + disk format + wiring the abstracted driver layer). Not startable
to completion in one tick. Groundwork above; deprioritised in favour of completable work.

## UPDATE: the device config @0x4866476c = "A:\" (drive-letter FS descriptor)
The 128-byte config the disk init (0x48532643) feeds to the device-create (0x4846d800) is
mostly zero with +0x00 = 0x005c3a41 = the ASCII string "A:\\". So 0x4846d800 creates a FAT/FS
DEVICE (drive "A:"), and 0x4846da31's block reads sit BELOW it on a block device whose FDC
register base is a runtime pointer. The FDC hardware address is therefore a further layer down
(FS -> block device -> FDC). Confirmed: locating it needs a live disk op (drive DISK MENU with a
floppy image) + a breakpoint on 0x4846da39, not static tracing. Deferred to a dedicated tick.

## 2026-07-12: exploration with the new register-read-at-tap capability -- FDC still not reached
Tried to reach the FDC via the DISK MENU using the new tracing capability (read cpu.state A0-A3/PC at a
data-access tap; scratchpad/retcap/fdchunt.lua). Findings:
- Pressing SEG0D 0x40 ("DISK MENU") did NOT open a disk menu -- the LCD stayed on the HOME/PMEM screen.
  So either that bit isn't the DISK-MENU event in this context, or the menu needs more.
- It DID trigger a heavy copy from **0x84000000** (via lib PC 0x4C0234E2 / 0x4C01F23B into RAM 0x50014Bxx,
  660k+ reads). FALSE LEAD: 0x84000000 is MODELED RAM (alias of 0x44000000, driver `map(0x84000000,
  0x84ffffff).ram().share("ram44")`) -- NOT the FDC. Disasm at 0x4C01F220 confirms it's RAM offset math
  (`sub 0x84000000,d1; movbu (a1)...`), a RAM read/modify, not device I/O.
- Candidate external-bus regions (0x30/0x32/0x38-0x3F/0x42-0x47/0x60-0x8F/0xA0-0xBF) showed only a boot
  peripheral-controller config at **0x32000000** (0x32000010-0x44, PCs 0x4840FFxx/0x484D71xx -- a
  bus/DRAM/chip-select controller, NOT the FDC) and a boot upload at 0x8C000000. None disk-triggered.
CONCLUSION: the FDC (IC103) is still NOT reached -- it only appears on an actual disk Load/dir op deep in
the DISK menu, which I could not open with SEG0D 0x40 alone. Confirms this is a genuine multi-tick task
(open the DISK menu reliably -> trigger a disk op -> catch the FDC base via the register-read tap ->
identify the chip -> model FDC + disk format + wire the 3 driver slots). The register-read-at-tap
capability IS the right tool for the FDC-base step once a disk op runs; the blocker now is UI navigation
into a working DISK menu + likely a floppy image. Deferred; groundwork saved so the next attempt skips
the 0x84000000 false lead.

## 2026-07-12 (2): FDC chip + address region NARROWED from the service manual + live elimination
Service manual (technics_sx-kn7000_keyboard.pdf, 160pp) findings:
- **IC103 = FDC**, custom part **C1DB00000607**. Signal set = **FDC.CS / FDC.DACK / FDC.TC / FDC.DRQ**
  = a classic **uPD765-family** DMA-driven floppy controller (MAME `upd765` / `upd72065`). (IC104 =
  C0HBA0000117 = LCD controller, for reference.)
- FDC.CS is a decoder output SIBLING of **TGCS/TGCS2** (tone gen 0x98040000/0x98050000) and **ADSPAB**
  (DSP 0x98000000) -- the A16-A18 chip-select decoder for the 0x98xxxxxx window. So the **FDC is in
  0x98000000-0x9807ffff** (the driver's io_r/io_w catch-all), at one of the CS-decoder slots.
LIVE ELIMINATION (fdcaddr.lua, tapping the unassigned 0x98 slots): **0x98060000 = SOUND CONTROL** (a
periodic 0xEA write from PC 0x4854D1A8; matches the driver's "0x98060000 more sound control" comment) --
RULED OUT as the FDC. 0x98010000 and 0x98030000 showed NO periodic access -> the FDC is most likely one
of those two (only touched on a disk op). Known 0x98 slots: +0=DSP(ADSPAB), +2=sound ctrl, +4/+5=TG
(TGCS/TGCS2), +6=sound ctrl, +7=strap. Free slots for FDC: **+1 (0x98010000) or +3 (0x98030000)**.
CHICKEN-AND-EGG confirmed: pressing DISK MENU (SEG0D 0x40) does NOT reach the FDC -- it bails at an early
"drive present/ready" gate (last tick: only a 0x84000000 RAM copy, screen stays HOME). So a live disk op
can't reveal the exact FDC slot until that gate is satisfied. To finish (dedicated effort): either (a)
model a STUB uPD765 at 0x98010000 AND 0x98030000, watch which the firmware polls + how, then satisfy the
drive-present gate (a status bit / GPIO) so the DISK menu opens; or (b) read the main-board CS-decoder
schematic page to pin FDC.CS's exact A16-18 code. Then wire MAME's upd765 + a floppy_image_device +
model the KN7000 disk format + the 3 driver slots (floppy=0x4853282e). BIG multi-tick, but now: chip
family known (uPD765), address narrowed to 0x98010000/0x98030000, gate identified.

## 2026-07-12 (3): uPD765 STUB experiment -- menu doesn't open; the gate is deeper than the FDC
Per Felipe: stubbed a uPD765 MSR (RQM ready) at 0x98010000 AND 0x98030000 in io_r/io_w + logging.
RESULT: DISK MENU (SEG0D 0x40) still does NOT open, and the FDC stub is NEVER accessed (0 hits). So the
DISK-MENU handler BAILS at an earlier "drive present" gate BEFORE reaching the FDC. Traced the handler:
- DISK press -> disk driver at 0x48582CF0: calls 0x4842b30c, checks `cmp 0x11,d0` -> if !=0x11 jmp
  0x485831b5 (bail). 0x11 = an expected device-type/status code.
- higher frame 0x484A593E: calls 0x4849fbd8, checks `cmp 0xfb,d0` / `cmp 0xfc,d0` (0xfb/0xfc = error
  status codes, e.g. no-disk/no-drive).
- (The GPIO reads 0x36008024/0x36008064 I first suspected are PANEL-SCAN bset/bclr RMW outputs gated on
  RAM 0x5006bda1 -- NOT the disk gate.)
So the drive-present gate is a STATUS returned by 0x4842b30c / 0x4849fbd8 (deeper in the layered disk
stack: FS -> block device -> FDC). NEXT: disassemble 0x4842b30c and 0x4849fbd8 to find what they read
(a drive-detect GPIO bit or a device-struct status) and return; satisfy it so the DISK menu opens, which
would then reach the FDC stub and reveal its exact register offsets. The uPD765 stub scaffold is in place
(0x98010000/0x98030000, audio-harmless, bit-identical reverb). This is the concrete next step for the
floppy -- a bounded multi-step trace, no longer a mystery.

## 2026-07-12 (4): FDC address NARROWED to 0x98010000 (0x98030000 eliminated)
Firmware literal search (kn7000_program_decompressed.bin):
- **0x98030000: 0 references** -> the FDC is NOT at 0x98030000 (removed from the stub).
- **0x98010000: referenced as a chip-select BASE** in the boot bus-controller setup
  (0x484009D0: `mov 0x98010000,d0; mov d0,(0x32000804)` -- programs the 0x32000000 bus/CS controller).
  So 0x98010000 is a valid CS region; combined with the free-slot analysis (+0=DSP, +2/+6=sound ctrl,
  +4/+5=TG, +7=strap) it is the STRONG FDC candidate. But it is NOT accessed at boot or during normal
  operation (0 hits on the stub) -- the FDC is only touched on an actual disk op, which the device-gated
  DISK menu doesn't reach. So 0x98010000 stays a strong-but-unverified candidate.
- device struct 0x50071254 (holds the FDC-base runtime pointer) is set up entirely in the disk driver
  region 0x4853xxxx (16 refs) -- but the FDC base there is computed at runtime, not a code literal, so a
  literal search can't extract it.
STATE: FDC = uPD765-family @ ~0x98010000 (best candidate), stub scaffold in place, DISK menu deeply
device-gated. The remaining work (open the DISK menu by satisfying the layered drive-present/device gate,
then confirm the FDC slot + register offsets, then wire upd765 + floppy_image + disk format) is a
dedicated multi-tick effort. Groundwork is thorough; the mystery is gone.

## 2026-07-12 (5): the disk-driver/FDC path is only initialized on a FILE OP (SD menu bypasses it via SPI)
Decisive RAM evidence (fdcram.lua, after opening SD MENU + pressing DISK MENU):
- 0x98010000 appears NOWHERE in RAM (scanned 0x50000000-0x50010000, 0x5006B000-0x5007C000,
  0x500A0000-0x500E0000, 0x50070000-0x50080000). The FDC base is NOT stored yet.
- The disk device struct **0x50071250 is ALL ZEROS** -> the disk-driver abstraction (FS->block device
  ->FDC, device-create 0x4846d800) is NOT initialized. It only runs on an actual FILE operation.
- The device table 0x5000097c = UI-OBJECT descriptors (0x000E0000/0x000E0018/0x000E0001...), NOT
  hardware device types -- the earlier "type==0x11" check is a UI focused-object check, unrelated to the
  drive.
- KEY: the **SD MENU works because it drives the SD card via the SD-SPI transport (0x9805000C) DIRECTLY**,
  bypassing the disk-driver/FDC abstraction. The FLOPPY path (driver[0]=0x4853282e -> block-read
  0x4846da31 -> FDC) is only entered on a Load/Save file op that selects drive A:.
CONCLUSION: to reach/confirm the FDC (and its exact register offsets at 0x98010000), a FILE OP on the
floppy must run -- deep menu navigation (open a Load/Save screen, pick drive A:) + a modelled floppy
drive. The RE groundwork is now thorough: chip=uPD765-family, address candidate=0x98010000 (0x98030000
eliminated), path = file-op -> disk-init 0x4846d800 -> device struct 0x50071254 -> block-read 0x4846da31
-> FDC(a1). The MODELING phase (wire MAME upd765 + a floppy_image_device at 0x98010000, drive the file-op
path, RE the KN7000 disk format) is a dedicated multi-tick effort -- best done with a real floppy image
to insert + interactive nav testing. The uPD765 stub scaffold is in place.

## 2026-07-12 (6): FDC + HD floppy MODELED; DISK menu OPENS (button was mislabeled); format tool reached
Big session. The floppy is now WIRED and the DISK menu + FLOPPY DISK FORMAT tool are REACHABLE.

**Modeling shipped (commit a936d5a + follow-ups):**
- Real `upd72067_device` (m_fdc) + `floppy_connector` at the 0x98010000 CS candidate (io_r/io_w
  offset 0x8000-0xffff -> fdc_r/fdc_w; reg0->msr_r, reg2->fifo_r/fifo_w). GUESSED offsets, unverified.
- Drive = **FLOPPY_35_HD** (not the KN5000's 35dd): firmware has "1.44M Byte format : 2HD" @0x25D160
  and reads 720K 2DD too, so the KN5000's 35dd is CORRECTED to 35hd here. FDC clock 32MHz (matches
  KN5000 sibling; unverified for the custom C1DB00000607).
- Formats = **default_pc_floppy_formats** (adds FLOPPY_PC_FORMAT: raw .img/.ima round-trip) -- the
  KN5000's default_mfm_floppy_formats can't load a raw PC image. KN7000 disks are FAT12/PC-interchangeable.
- Blank test images: /home/fsanches/compartilhado/kn7000_mame_build/floptest_blank.img (1.44MB zeros)
  and floptest_fat12.img. Media slot = `-floppydisk` (accepts .img now).

**KEY CORRECTION (rule g): the DISK MENU button was MISLABELED.**
- **SEG0D 0x04 ("DISK") OPENS the DISK MENU** (DISK TOOLS/PREFERENCES/STYLE CONVERT/CUSTOM STYLE ;
  LOAD/SAVE/DIRECT PLAY/SONG MEDLEY). Verified live (snapshot).
- SEG0D 0x40 ("DISK MENU") does NOTHING from HOME -- the earlier ticks pressed THIS wrong bit and
  wrongly concluded "the DISK menu is floppy-device-gated." It is NOT gated: the menu opens fine via
  0x04. The prior "chicken-and-egg / drive-present gate" conclusion is RETRACTED -- it was a wrong button.
- The disk-state struct 0x5006ba20 (0x205 bytes, base from 0x4849fb5f) is zero-inited at boot (initA=1);
  its status byte @+0x1f9=0x5006bc19 reads 0x00 (passes the 0xfb/0xfc error gate). Not the blocker.

**From the DISK MENU, SEG11 0x10 reaches the FLOPPY DISK FORMAT screen** ("Select the FORMAT type:
1.44M Byte 2HD / 720K Byte 2DD", PAGE 2/2). So Felipe's "disk menu floppy formatting tool" IS reachable.

**REMAINING BLOCKER = the LCD-right soft-keys (2HD/2DD, marked with the on-screen right arrows) are
UNMAPPED.** Their normSeg.bit is the hard "full-scramble" panel problem (panel-matrix-service-manual.md:
physical SEG.SW -> normSeg is a scramble in the undumped sub-CPU, only derivable by empirical sweep).
Swept SEG11/SEG0C/SEG0E/SEG10/SEG0B bits from the format screen: none select a format type (SEG0C 0x10 =
STRINGS&VOCAL sound-group jump; SEG11 0x40 = tempo/PANEL MEMORY 3; SEG0D 0x80 = SD MENU jump). So the
format-execute soft-key is elsewhere.

**FDC still shows 0 accesses at 0x98010000 AND 0x98030000** across boot/idle/DISK-menu/FORMAT-screen/
audio. So the FDC address remains UNCONFIRMED -- no disk op has executed yet (no format/dir/save ran,
because the soft-key to trigger it isn't mapped). Widened taps on both free CS slots: still 0.

**NEXT (well-scoped):**
1. Find the LCD-right soft-key normSegs by a FULL empirical sweep (drive every SEGnn.bit from the format
   screen, EXIT-recover between presses, watch for the screen changing to "formatting/confirm"). This is
   the panel-completion-plan method. Once the 2HD soft-key is found -> format executes -> FDC accesses
   appear -> CONFIRM the 0x98010000 slot + the real register offsets (correct reg0/reg2 guesses).
2. If format executes but STILL 0 FDC hits, the FDC is at neither candidate OR disk-present is gated on a
   separate drive-status GPIO (disk-in/ready/wpt) the firmware reads before issuing FDC commands -- trace
   where 0x5006bc19 (status byte) is SET from.
3. Then: dir/LOAD (read), SAVE panel memory to floppy, and the same on SD.
Tools: tools/floppy_diskmenu_probe.lua, floppy_gate_probe.lua, floppy_load_probe.lua, floppy_format_probe.lua.
GOTCHA: register_frame_done fires reliably; add_machine_frame_notifier did NOT in these runs. Use integer
mach.time.seconds (attoseconds threw). -log floods error.log (every io_r/io_w) and stalls the emulator --
use Lua taps + stdout instead. Narrow taps (16 bytes) are cheap; do NOT tap the hot TG/sound io ranges.

## 2026-07-12 (7): FORMAT EXECUTES (full nav mapped) but FDC is NOT in the 0x98 window
Save-state soft-key sweeps (tools/floppy_softkey_sweep.lua, floppy_yes_sweep.lua) cracked the nav:
- **DISK menu**  = SEG0D 0x04.
- **FLOPPY DISK FORMAT** (page 2/2, "Select FORMAT type: 1.44M 2HD / 720K 2DD") = SEG11 0x10 from the
  DISK menu.
- **ATTENTION confirm** (page 1/2, "Using DISK FORMAT will erase any current data. Are You Sure? YES/NO")
  = PAGE UP (SEG0B 0x10) from the format screen (it is a 2-page screen; page 1 = confirm, page 2 = type).
- **YES = SEG13 0x01** on the ATTENTION screen -> the format EXECUTES: the screen shows "ERASE WAIT!.."
  (found by md5/orange-cluster analysis of the 155-button save-state sweep from the ATTENTION screen).
  (NO / cancel / page-back = SEG12 0x01.)
The LCD soft-keys are a SCRAMBLE (panel-matrix-service-manual.md) -- these bits (SEG11 0x10, SEG12 0x01,
SEG13 0x01, SEG0B 0x10) act as menu soft-keys in this context, unrelated to their bank-A names.

**KEY NEGATIVE RESULT: the FDC is NOT in 0x98000000-0x9807ffff.** During the executing format ("ERASE
WAIT!"), a unique-write-address tracker over the entire 0x98 window (tools -> /tmp/fdcfind.lua) logged
ONLY the normal peripherals: 98000000 (DSP), 98020004/08 (sound), 98040000/04/10 + 98050000/04/0C/10
(TG + SD-SPI), 98060000 (sound ctrl). NO writes to 0x98010000 or 0x98030000 (the old FDC candidates) --
those were WRONG. And the floppy image md5 is UNCHANGED after "ERASE WAIT", i.e. the format never writes
real disk data. So the disk-format path talks to the FDC at an address OUTSIDE 0x98 (or the format hangs
polling an FDC status read that returns garbage because the FDC isn't modeled there).

IMPLICATION: the UPD72067 wired at 0x98010000 (io_r/io_w 0x8000-0xffff -> fdc_r/fdc_w) is at the WRONG
address and is never hit -- it is harmless (0 accesses, audio verified identical) but does nothing. The
real FDC base must be found by tracing the disk-driver's `calls (a2)` chain (block-read 0x4846da31 ->
[struct+0x14]+4) during a live format, OR by a broad READ tap (the format likely spins polling the FDC
MSR). NEXT: debugger breakpoints on the disk driver funcs during the SEG13-0x01 format (/tmp/fdctrace2.lua)
to dump the FDC register base, then re-map the UPD72067 there + wire IRQ/DMA + drive-status so the format
actually writes the image. The full nav to reach/execute format is now known and reproducible.

## 2026-07-12 (8): format COMPLETES (returns to DISK menu); FDC path bypasses the block device
Debugger trace of the real format (SEG13 0x01 = YES) with breakpoints on every disk-driver/FAT/block
function (0x4853282e flpRd, 0x485328b5 flpWr, 0x4846da31 blockRd, 0x485335ff fatRd, 0x48532468 diskDisp,
0x48532643 diskInit, 0x4846d800 fopen): **ZERO of them fire.** So the FLOPPY FORMAT does NOT use the
FAT/block-device abstraction at all -- it is a low-level format-track path straight to the FDC. After
"ERASE WAIT!.." the screen returns cleanly to the DISK MENU (does NOT hang), yet the image is unchanged
and no device outside the normal TG/sound set is written -> the format's FDC writes land on an
unmodelled address (silently discarded) and the firmware does not verify.
NEXT LEAD (symbol table): **FdIoFunc @0x48607900** (name string; the low-level Floppy-Disk I/O function),
plus TestDiskFunc @0x48607A90, FDCstopBitmapCheck @0x486079B5 -- all in the service/test-mode symbol
block 0x486079xx-0x48607Axx. Resolve FdIoFunc's code address (via the reflection address table paired
with these name strings) and disassemble it for the FDC register base literal; OR breakpoint the format
handler (find it via the "Using DISK FORMAT" strings 0x48661F48/0x48662037 and the ATTENTION-YES event)
and single-step to the first device access. That base is where the UPD72067 must be re-mapped; then wire
IRQ/DMA + drive-status so the format/save actually writes the mounted image.

## 2026-07-12 (9): the format ABORTS at a software/state check -- it never touches any FDC hardware
Exhaustive live tap of the executing format (SEG13 0x01 = YES):
- WRITE tap over ext-bus 0x30-0x33 / 0x38-0x3F / 0x40-0x47: only boot-time 0x32000xxx bus-controller
  writes; NOTHING during the format.
- READ tap over 0x30-0x33 / 0x38-0x47 / 0x36-0x37(GPIO) / 0x9C-0x9F(phantom btns): during the format,
  only the NORMAL panel-scan GPIO (0x36008004/24/44/64/84) + boot bus-controller + 0x9CC00000 phantom
  buttons. NO unusual/FDC-looking address is read or written.
CONCLUSION: the FLOPPY FORMAT path **aborts at an early SOFTWARE/state check and never reaches the FDC
at all** (consistent with: "ERASE WAIT!.." shows briefly, then it returns cleanly to the DISK menu with
the image unchanged). So there is no live FDC access to trace yet -- the blocker is the pre-FDC gate
(likely a "disk present / drive ready" software flag that is never set because no disk-change/insert
event is modelled). To finish the floppy: find the FORMAT-execute handler (via the ATTENTION-YES event
or the "Using DISK FORMAT" strings 0x48661F48/0x48662037), single-step from YES to the abort branch,
identify the state/flag it checks, and model whatever sets "disk inserted + drive ready" (a drive-status
signal). Only then does the format reach the FDC and reveal its address. This is a dedicated multi-tick
RE task; the full UI nav to reach + trigger the format is now known and reproducible.

## 2026-07-12 (10): CORRECTION -- 0x98010000 is UNCONFIRMED, not disproven; format aborts pre-FDC
Earlier entries (6)-(9) said "the FDC is NOT in 0x98 / 0x98010000 disproven" based on the live FORMAT not
writing 0x98010000. That was TOO STRONG: the FORMAT aborts at a pre-FDC software gate and never reaches
ANY FDC address, so its 0x98-write trace is silent about 0x98010000. Re-examination of the boot
bus-controller (0x484009D0) shows **0x32000804 = 0x98010000 is a chip-select BASE**, and no other 0x98
peripheral claims that sub-slot -- so 0x98010000 remains the STRONGEST FDC candidate, just unconfirmed by
a live access (boot: 0 hits; format: aborts early; dir/LOAD: unreachable + would fail device-not-ready).
Driver comments + fdc-architecture.md corrected to "unconfirmed candidate". CONCRETE NEXT EXPERIMENT: the
format's pre-gate likely polls a "disk present / drive ready" status that (on real HW) the FDC answers via
SENSE DRIVE STATUS. Model the UPD72067 status correctly at 0x98010000 (ready + disk-in) and re-test the
format: if the pre-gate then advances to a real FDC access, 0x98010000 is CONFIRMED and the register
layout is revealed. This breaks the chicken-and-egg (can't capture the runtime FDC ptr live until the FDC
answers the ready poll).

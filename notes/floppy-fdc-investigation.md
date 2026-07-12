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

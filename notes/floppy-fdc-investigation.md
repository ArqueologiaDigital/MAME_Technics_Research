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

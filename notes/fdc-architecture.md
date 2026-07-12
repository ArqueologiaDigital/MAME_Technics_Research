# KN7000 FDC (floppy) architecture — from disassembly (2026-07-12)

Felipe: "inspect the disassembly to understand how the FDC works." This is the recovered structure of
the floppy-disk subsystem (FDC = IC103, custom uPD765-family C1DB00000607, DMA-driven per the service
manual: signals FDC.CS / FDC.DACK / FDC.TC / FDC.DRQ). Addresses are firmware-space (base 0x48400000;
library self-loaded at 0x4C000000). Disassembled with `mame-sony-video/unidasm -arch mn10300`.

## Layering (three stacked abstractions + a separate test path)

```
  application (Load/Save/dir)                     service/TEST mode
        |                                                |
   FS driver table  @0x486646F0(read)/F0FC(write)   FdIoFunc 0x484A1766
     [0]=floppy 0x4853282E / 0x485328B5             FdTestRunFunc 0x484A14B6
     [1]=? 0x48565AF6 / 0x48565B84                  FdTestStopFunc 0x484A170D
     [2]=? 0x48584212 / 0x48584370                       |  (post class-5/6 msgs
        |                                                |   via 0x484298A0 ->
   block read/write  0x4846DA31 / 0x4846DA7A             |   dispatcher 0x484285E4
     dev struct ptr cached @0x50071254                   |   -> RTOS task @0x5000757C)
        |  mov (0x14,a0),a1 ; mov (4,a1),a2 ; calls (a2) v
   registered device driver METHOD (a2)  <---- THE FDC low-level access lives here
        |
   VFS device table  @0x500079F8  (0x28-byte entries, count @0x50007A48, names @0x50007A14)
     resolves drive letter "A:" (descriptor 0x4866476C = the string "A:\") to the floppy driver
```

## Open / mount path (verified)
- `0x48532643` = **disk-open("A:")**: copies the 128-byte descriptor from **0x4866476C** (just the ASCII
  path `A:\`, rest zero) to a stack buffer, then calls the VFS open **0x4846D800** and caches the
  returned device-struct pointer at **0x50071254** (`mov a0,(0x50071254)` @0x4853267B). Status word at
  0x50071258 (−2/−1/−0xB/−3 error codes for the drive-letter/`w`-mode/0x1F cases).
- `0x4846D800` = VFS open. Parses the fopen MODE string (chars r/w/a/+/b/~/d), then (0x4846D8EF+) walks
  the **device table 0x500079F8** comparing the drive letter (`cmp 0x3a` = ':') against each registered
  device name (0x50007A14) via lib strcmp 0x4C003311; entries are 0x28 bytes (`add 0x28,a3`).
- `0x4853282E` / `0x485328B5` = FS driver[0] (floppy) read/write: clamp the length to 0x7FFF, load the
  device struct from 0x50071254, and call block read `0x4846DA31` / block write `0x4846DA7A`.
- `0x4846DA31` (block read): reads the device status byte `(a1)`, sets 0x500AD390 error code on a null/
  not-ready device (0x11 = "no device", 0x0D = "not ready"), then `mov (0x14,a0),a1 ; mov (4,a1),a2 ;
  calls (a2)` -- **a2 is the registered device method that does the actual FDC I/O** (a runtime pointer
  set at device-create, not a code literal).

## Service/TEST-mode path (verified)
- Reflection table (name array @file 0x34AF1C, parallel func array @0x34AF90) pairs these test funcs:
  RomTestRunFunc 0x4849FDF8, RamTestRunFunc 0x484A018E, DspTestFunc 0x484A062A, **FdTestRunFunc
  0x484A14B6**, **FdTestStopFunc 0x484A170D**, **FdIoFunc 0x484A1766**, ...
- These do NOT touch the FDC directly. They post RTOS command messages (class<<16 | cmd, e.g. 0x0005000E,
  0x0005002F, 0x00060023, 0x00050001) via **0x484298A0** -> task dispatcher **0x484285E4** (task table
  @0x5000757C, 0x38-byte entries; uses lib 0x4C03C5AF). The FDC hardware is touched inside the disk TASK
  that consumes these messages. State machine uses the disk-state struct 0x5006BA20 (base from 0x4849FB5F;
  retry counter @+0x1F7 = 0x5006BC17, status @+0x1F9 = 0x5006BC19). 0x484AE29B is only a status/LED-bit
  dispatcher (jump table 0x48614E38, bits in 0x5006BF9C/9E) -- NOT the FDC.

## FORMAT path (verified live, not the block path)
Full UI nav (reversed via save-state soft-key sweeps): DISK menu = SEG0D 0x04; FLOPPY DISK FORMAT (type
select) = SEG11 0x10; ATTENTION "Are You Sure? YES/NO" = PAGE UP (SEG0B 0x10); **YES = SEG13 0x01** ->
the format EXECUTES ("ERASE WAIT!.." then returns to the DISK menu). BUT: a live trace shows the format
**bypasses the whole block/VFS layer** (breakpoints on 0x4853282E/0x485328B5/0x4846DA31/0x485335FF/
0x48532468/0x48532643/0x4846D800 all fire ZERO times) and **aborts at an early software/state check
without touching any FDC hardware** (exhaustive read+write taps over 0x30-0x47/0x36 GPIO/0x98/0x9C during
the format show only normal TG/sound/DSP/SD + panel-scan traffic; the floppy image is unchanged). So the
format has its own low-level format-track routine gated on a "disk present/ready" state that is never set.

## The open question: the FDC's physical I/O address
- **NOT in the 0x98 window** (disproven live) and **not reached via the block layer during FORMAT**.
- It is the runtime pointer inside the registered device method (a2 at 0x4846DA31's `calls`). To capture
  it, a live VFS file-op must run (dir/LOAD/SAVE) so 0x50071254 is populated and the method is called --
  then read a2 / the method's FDC base. The UI LOAD button on the DISK menu has not yet been found (SEG11
  0x10 goes to FORMAT, not file-LOAD); a save-state sweep for the device-create button is the way in.
- Static alternative: resolve the floppy entry in the device table 0x500079F8 registration (its read fn
  = the FDC method) -- the registration writer wasn't found via the 0x50007A48 literal (only reads there).

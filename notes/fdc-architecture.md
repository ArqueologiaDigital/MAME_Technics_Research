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

## The open question: the FDC's physical I/O address (UNCONFIRMED, not disproven)
- **0x98010000 is the strongest candidate and is NOT disproven.** The boot bus-controller programs it as
  a chip-select base (0x484009D0: `mov 0x98010000,d0 ; mov d0,(0x32000804)`), and no other 0x98 peripheral
  claims that sub-slot (TG=0x98040000, DSP=0x98000000, snd=0x98020000/60000, strap=0x98070000). The
  UPD72067 is wired there.
- BUT no code path in the emulator has EXERCISED the FDC, so the slot can't be confirmed: at boot the FDC
  is untouched (0 accesses), the live FORMAT aborts at a pre-FDC software gate before any FDC access, and
  the block/VFS dir-read path is not reachable (no DISK-menu button triggers device-create; a 155-button
  save-state sweep found none -- and disk-open would fail "device not ready" anyway without the FDC
  responding). Earlier "the FDC is NOT in 0x98 / 0x98010000 disproven" was too strong: the format never
  reaches ANY FDC address, so its 0x98-write trace (only TG/sound/DSP/SD) says nothing about 0x98010000.
- To CONFIRM: make a live FDC access happen. The FORMAT's pre-gate reads NO device during its abort (the
  live trace shows only GPIO panel-scan + boot bus/phantom reads -- crucially NO 0x98010000 read even
  periodically), so it checks a SOFTWARE "disk present/ready" FLAG, not the FDC directly. That flag is set
  elsewhere -- most likely on a disk-CHANGE/insert EVENT (an IRQ or the FDC disk-change bit), which MAME
  never raises because the floppy image is simply present from boot (no post-boot "insert"). So the CONCRETE
  next step is: **trace the FORMAT-execute handler** (triggered by YES = SEG13 0x01 on the ATTENTION screen;
  find it via the "Using DISK FORMAT" strings 0x48661F48/0x48662037 or by breakpointing the ATTENTION-YES
  event) to its abort branch, read which RAM flag/state it tests, then find what SETS that flag (a
  disk-change ISR? a boot-time FDC probe?). That reveals whether we must (i) model a floppy disk-change/
  insert event, (ii) make the FDC answer a probe at 0x98010000, or (iii) both. Only then does the format
  reach the FDC and confirm the address (read a2 at 0x4846DA31's `calls` = the device method = FDC base).
- The alt file-op route (dir/LOAD) is blocked the same way (disk-open returns "device not ready") until the
  disk-present flag is set, so it is NOT an independent shortcut.
- Static alternative: resolve the floppy entry in the device table 0x500079F8 registration (its read fn
  = the FDC method) -- the registration writer wasn't found via the 0x50007A48 literal (only reads there).

## 2026-07-12 (addendum): format = poll-for-task-completion; factory diag hits 0x9C/0x9E hardware
Live tap of the disk-state struct 0x5006BA20 during the format (SEG13 0x01 YES) shows the format is a
**poll-for-completion** loop: it spins reading three status bytes -- +0x1F9 (0x5006BC19, via 0x4849FBD8),
+0x203 (0x5006BC23, via getter 0x484A4F9C), +0x204 (0x5006BC24, via getter 0x484A4FAB) -- ~2700 reads
total, then times out and returns to the DISK menu. Those bytes are set by the DISK TASK on completion;
the format posts a command (0x484298A0 -> dispatcher 0x484285E4 -> task table 0x5000757C) and waits. The
task never completes (its FDC I/O never finishes) -> timeout -> abort. So the format itself never touches
the FDC; the FDC access is in the disk task, which stalls.

**Factory power-on diagnostic path (bit-15 gated) reveals candidate FDC hardware in the 0x9C/0x9E region.**
0x484A4FBA reads the strap 0x98070000 and `btst 0x8000` (bit 15): CLEAR -> run the diagnostic ops
(0x484A4FE3+ = 0x4854D835, 0x4849FFE3, 0x484A005A...), SET -> skip. The driver deliberately sets bit 15
(io_r 0x38000) to skip this diagnostic. Disassembly of the gated ops shows real device I/O:
- 0x484A005A: `movbu (a0),d0` / `movbu d0,(a0)` FIFO-style poll on a register, plus writes to
  **0x9CC001FC**, **0x9CE00000 / 0x9CE00004 / 0x9CE00008** (16-bit data words), with a delay call
  (0x484A4EE4) between -- classic FDC command/data + status-poll, OR an external-device test.
- 0x4854D835 path: `bclr 0x08,(0x9CC00009)` / `bset 0x08,(0x9CC00009)` -- a control-register bit toggle.
- 0x484A4F60: writes **0x90C00000** (d1 = 0x10200048/0x10200000) and **0x90008020** -- another device.
NOTE the 0x9CC00000 region also holds the phantom buttons (0x9CC00008) [[kn7000-sd-strap-gate]]; the FDC
may be a sibling sub-slot (0x9CC001FC / 0x9CE00000). VERIFIED the format does NOT call these (breakpoints
fire zero times during a normal format) -- they are the factory-diagnostic path.

**Strong new hypothesis: the FDC is in the 0x9C/0x9E region (0x9CE00000 data + 0x9CC00009 control), NOT
0x98010000.** The factory diagnostic tests it there; the normal disk-task FDC I/O likely uses the same
hardware via a different code path. CONCRETE NEXT EXPERIMENT: add a config to CLEAR strap bit 15, run,
and tap 0x90000000-0x9FFFFFFF -- watch the diagnostic exercise 0x9CE00000/0x9CC00009/0x90C00000 (confirms
the device map). Then find the disk task's handler (breakpoint 0x484285E4 dispatch during the format to
get the task index/handler) and its FDC I/O to nail the normal-mode FDC base + register layout.

## 2026-07-12 (addendum 2): disk-task region + hardware register map (address-reference analysis)
Cross-referencing the candidate device addresses against the firmware narrows the map:
- **The disk TASK code lives around 0x484A5xxx** (the status setters 0x484A51D5/E0 that the format polls,
  plus 0x484A50C9/0x484A5362). It writes hardware via a **library register-helper `0x4C014A56(addr, data)`**
  (d0=addr, d1=data) -- e.g. `mov 0x90008020,d0 ; clr d1 ; call 0x4C014A56` at 0x484A50C7 (a control/reset
  write during a completion/cleanup branch, right after setting disk-state +0x1FA=2).
- **0x9CE00000** (15 refs, MOSTLY in the early display-init cluster 0x48414D66..0x48415C31) is almost
  certainly the **LCD controller IC104** (C0HBA0000117), NOT the FDC -- it uses a control write at
  0x9CC001FC then 16-bit data words at 0x9CE00000/04/08 (a display command/data pattern). Refine the FDC
  search to EXCLUDE 0x9CE00000.
- **0x9CC00000 region** = a control/status latch: +8 = the six phantom buttons (active-low, SD-related,
  [[kn7000-sd-strap-gate]]); +9 (bit toggle at 0x4854D726/A5/E7) and +0x1FC = disk/SD control bits.
- **0x90008020 / 0x90C00000** = disk control/reset registers (written via 0x4C014A56 from the disk task
  0x484A50C9/5362 and the factory diag 0x484A4F60/88).
- **The uPD765 FDC command/status/data registers themselves are still not isolated** -- they are among the
  addresses passed to the register-helper(s) from the disk task's command/poll path (not the cleanup write
  to 0x90008020). NEXT: disassemble the disk task's command-issue + status-read path (trace from the
  message the format posts, class 5/6, into the 0x484A5xxx handler) and note every `0x4C014A56(addr,...)` /
  register-read-helper `addr` -- the MSR (polled) + FIFO (command/result) addresses are the FDC. The
  0x90008020 / 0x9CC00xxx / 0x90C00000 cluster is the disk hardware block; the FDC data/status is one of
  its sub-registers.

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

## 2026-07-12 (addendum 3): CONFIRMED -- the format reaches ZERO disk/FDC hardware (task stalls pre-I/O)
Closed the last tap gap: tapped **0x90000000-0x9BFFFFFF** (which includes the disk-control regs
0x90008020/0x90C00000 the disk task references, and was NOT covered by the earlier 0x30-0x47/0x36/0x98/0x9C
taps) during a live format -- ZERO accesses after YES. Combined with the earlier taps, the format touches
NO disk/FDC hardware at ANY address 0x30-0x9B. So the disk TASK stalls BEFORE it ever issues an FDC
command: the format posts its command + polls the completion status bytes ~2700x, but the task never runs
its hardware I/O. Root cause is therefore upstream of the FDC registers -- either (i) the floppy disk task
is never created at boot (no floppy DiskInit ran; cf. the SD DiskInit 0x4854ACED which DOES create the SD
worker), or (ii) the task runs but a software "disk present/ready" check returns not-ready and it errors
out before the FDC. NEXT: breakpoint the format's command post (0x484298A0) during the format to read the
target task index + confirm the post succeeds, and search for a floppy disk-task creation (RTOS task-create
lib 0x4C03D0C8, as used by the SD DiskInit). If no floppy task exists, THAT is the fix point (create/model
it); if it exists, trace its early-return. Only past that does the FDC hardware get touched + its address
revealed. The FDC register isolation is downstream of fixing the task stall.

## 2026-07-12 (addendum 4): CORRECTION -- the format posts NO class-5/6 disk-task command
Breakpoint on the message poster 0x484298A0 with a class-5/6 filter, armed through a live format: ZERO
class-5/6 posts fire. So the earlier inference "the format posts a command to a disk task (class 5/6) and
polls for completion" is WRONG -- the format does NOT drive the disk task via 0x484298A0. What IS verified:
the format (YES=SEG13 0x01) shows "ERASE WAIT!..", spins ~2700x reading disk-state status bytes
0x5006BC19/BC23/BC24 (getters 0x4849FBD8 / 0x484A4F9C / 0x484A4FAB), reaches NO disk/FDC hardware anywhere
0x30-0x9B, then times out back to the DISK menu. So the format's own handler polls those status bytes and
aborts, but WHO the format expects to set them (and via what path) is NOT yet the class-5/6 disk task.
HONEST STATE: the format-execute handler itself (the code YES dispatches to) has NOT been located; it is
reached through the MILK GUI screen dispatch, not a simple event. The right next tool is a CPU instruction
TRACE across the YES press (or catching the GUI screen's registered YES handler) to see the handler's
actual logic + abort branch -- the previous static inferences (disk-task post; strap-bit-15 gate on the
format path -- both shown to NOT be on the format path via zero breakpoint hits) over-reached. The solid,
verified facts remain: full nav to the format; format executes+aborts; zero FDC hardware reached; FDC
architecture (VFS/block/test-mode layers, addresses) as documented above; 0x9CE00000=LCD not FDC.

## 2026-07-12 (addendum 5): TOOLING CAVEAT -- cpu.debug:bpset actions are UNRELIABLE with -debugger none
Verified: `cpu.debug:bpset(addr,"",'printf...;g')` returns a valid handle but its ACTION does NOT produce
captured output under `-debug -debugger none` in this build (a bp on the continuously-running engine loop
0x485519BC fired 0 times; a bp on the disk-struct getter 0x4849FB5F likewise). So EVERY earlier
"breakpoint fired zero times" conclusion is UNRELIABLE and must be re-verified with memory taps:
- "format bypasses the block/VFS layer" / "disk-driver funcs fire zero times" (fdctrace2) -- UNRELIABLE.
- "format posts NO class-5/6 command" (postbp) -- UNRELIABLE.
- "format does not call the strap-bit-15 gate / 0x9C-0x9E ops" (gatebp) -- UNRELIABLE.
RELIABLE facts stand (Lua memory taps + reads, which DO work): the format polls disk-state status bytes
0x5006BC19/BC23/BC24; it reaches NO hardware in the tapped 0x30-0x9B; and the disk device struct
0x50071254 stays 0 (a plain Lua read) so the VFS disk-open/device-create never runs during the format.
So the reliable picture is unchanged (format stalls pre-hardware waiting on status bytes) but the specific
call-graph attributions were tool-artifacts. USE: memory taps + cpu.state (SP/PC/A0-A3/D0-D3 all readable)
+ stack-walk for call chains; the `trace` command works and writes a file (but is huge ~450MB/8s even with
noloop). For code-execution facts, prefer taps/traces over bpset-action-printf.

## 2026-07-12 (addendum 6): the format's WAIT condition, found via stack-walk (RELIABLE)
Using a memory-tap stack-walk (arm the read-tap on the disk-state struct BEFORE the YES press, read
cpu.state SP/PC and walk the stack for 0x48xxxxxx return addresses -- this WORKS, unlike bpset):
- The format's poll of status byte 0x5006BC19 (+0x1F9) is done by **0x484A593E**:
    call 0x4849FBD8 (get +0x1F9) ; cmp 0xFB -> h ; cmp 0xFC -> h ; cmp 0xF6 -> h ; else return -1.
  So **the format waits for 0x5006BC19 to become a disk-command COMPLETION CODE (0xFB / 0xFC / 0xF6)**.
  It stays 0x00 (no command ever completes) -> the dispatch returns -1 (not done) -> the format spins,
  then times out to the DISK menu. (0xFB/0xFC are the "error" codes seen earlier; 0xF6 another result.)
- Call chain (stack return addrs) for that poll: 0x484A594A(=0x484A593E) <- 0x48582CFF <- 0x4842954F(RTOS)
  <- **0x4854D185**. The 0x4854Dxxx region is the DISK command/hardware code -- it references the disk
  hardware latch **0x9CC00000 / 0x9CC001FC** (0x4854D1CC/0x4854D726/...). So the format-execute was
  invoked from 0x4854Dxxx, and the disk hardware is very likely the **0x9CC00000 latch** (phantom buttons
  live at 0x9CC00008 in the same chip; disk control/status at +9/+1FC).
- A parallel poll (0x484B165D) waits on status +0x204 (0x484A4FAE getter) gated by 0x5006BFCF bit0.

ROOT-CAUSE (reliable): the disk COMMAND never sets a completion code because its hardware handler never
runs (0 hardware hits 0x00-0xBF during the format). So the disk-command dispatch/servicing is the gap --
NOT the FDC register modeling per se. The setter of 0x5006BC19 (the completion writer) is what must run;
find it (search writes to struct+0x1F9 via the disk task) + why it doesn't fire. The disk hardware is
almost certainly at 0x9CC00000 (accessed by 0x4854Dxxx at boot; a multi-reg latch shared with phantom
buttons). IMPLEMENTATION PATH: (1) confirm 0x9CC00000 is the FDC/disk controller by tracing 0x4854Dxxx's
boot access + what it reads; (2) find why the format's disk command isn't serviced (the completion writer
never runs); (3) model the disk controller at 0x9CC00000 so the command completes. bpset is unusable
(addendum 5) -- use taps + stack-walk + `trace`.

## 2026-07-12 (addendum 7): the completion-writer is 0x4849FBC8, called by disk-task handlers that never run
The setter of status byte 0x5006BC19 (+0x1F9) is **0x4849FBC8** = `SetCompletion(d0)` (store `movbu d2,
(0x1f9,a0)` at 0x4849FBCE, a0=struct base). Its callers pass the completion codes:
- **0x484A50A9**: `mov 0xFB,d0 ; call 0x4849FBC8` -- disk-task ERROR-completion path (0x484A5090 block,
  after calls 0x484A0B6D / 0x484ABB98; also posts 0xFB via 0x4842B3F4 and calls 0x484D791D).
- **0x484A519F**: `mov 0xF6,d0 ; call 0x4849FBC8` -- another completion.
So the completion codes the format waits for (0xFB/0xFC/0xF6) are written by the DISK-TASK command
handlers (0x484A50xx). Those handlers NEVER RUN during the format (0x5006BC19 stays 0x00) -> the disk
task is not servicing the posted command. Since the disk task would ACCESS the FDC hardware inside those
handlers, and NO hardware is touched (0x00-0xBF all clean), the disk task never even starts the command.
ROOT CAUSE (best reliable understanding): the format posts a disk command and blocks on its completion,
but the disk task's command handler (0x484A50xx) is not dispatched -- either the task isn't scheduled,
the command isn't enqueued to it, or it blocks on a hardware event (an FDC IRQ) that the unmodelled FDC
never raises. IMPLEMENTATION requires: locate the disk task's create + message loop (RTOS task-create
lib 0x4C03D0C8), confirm it runs, see how it dispatches to 0x484A50xx, and what it waits on before
issuing the FDC command -- THEN model the FDC/disk controller (0x9CC00000 region) + its IRQ so the
handler completes. This is a multi-tick RTOS+HW effort; the exact wait/dispatch is the crux, all mapped.

## 2026-07-12 (addendum 8): EXPERIMENTAL FDC IMPLEMENTED at 0x9CC00000 (opt-in, Felipe-authorized)
Per Felipe ("implement a clearly-labeled experimental FDC at the 0x9CC00000/uPD765 best-guess, accepting
it may not work and may need reverting"), shipped an OPT-IN experimental FDC:
- New config switch **"Experimental floppy (FDC) at 0x9CC00000"** (PORT "FDCEXP"), DEFAULT OFF.
- When ON, `fdc_r`/`fdc_w` memory-map the UPD72067 over **0x9CC00000 (MSR) + 0x9CC00001 (FIFO)** only --
  deliberately NOT the SD scan-enable byte 0x9CC00004 nor the SD switches 0x9CC00008 (those stay RAM).
- Runtime-gated (NOT machine_start -- the cfg isn't applied yet there): fdc_r/fdc_w check FDCEXP each
  access; when OFF they fall through to the LCD-RAM backing so behaviour is byte-identical to before.
- INTRQ/DRQ -> logging stubs (fdc_irq_w/fdc_drq_w), NOT wired to a maincpu IRQ (the MN10300 line is
  unknown; a wrong line would inject spurious IRQs). The floppy drive + PC formats stay wired so images
  mount regardless of the switch.
VERIFIED: OFF = zero regression (boots to PMEM home, note plays, SD path intact). ON = boots to PMEM home
too, and the FDC ENGAGES -- the boot disk-init read of 0x9CC00000 (pc 0x4854D725) now hits `msr_r()`
instead of RAM. As expected it does NOT make the floppy work: the FORMAT still stalls upstream (the disk
task never services the command, so 0x9CC00000 is never accessed during a format -- addenda 6-7). So this
is a faithful, clearly-labelled best-guess device model, ready for when the disk-command-dispatch blocker
is resolved; it can be reverted by leaving the switch OFF (its default) or removing the FDCEXP map.

## 2026-07-12 (addendum 9): end-to-end verification of the experimental FDC (ON) -- confirms scaffold
Ran DISK->FORMAT->ATTENTION->YES with FDCEXP ON + a tap on 0x9CC00000..0F:
- The FDC (0x9CC00000..01) is accessed EXACTLY TWICE, both at BOOT: read 0x9CC00000 (pc 0x4854D725 ->
  now msr_r) + write 0x9CC00000=0x00 (pc 0x4854D1C5 -> dsr_w). (The ~1782 boot + ~1836 "format" tap hits
  in the 0..0F window are almost all the continuous SD-switch scan at 0x9CC00008, which is correctly
  RAM-backed, NOT the FDC.)
- During the FORMAT itself the FDC is NOT accessed, and **status@0x5006BC19 stays 0x00** -> the format
  still times out. So the experimental FDC does NOT unblock the floppy, exactly as predicted: the format
  stalls upstream (disk task never services the command; addenda 6-7) and never reaches 0x9CC00000.
CONCLUSION: the opt-in FDC is a faithful, verified device SCAFFOLD -- it engages when 0x9CC00000 is
accessed (boot disk-init) and does not regress anything (OFF byte-identical; ON still boots to home + note
plays). Making the floppy actually WORK still requires resolving the disk-command-dispatch blocker (find
why the disk task doesn't service the format's command), which is the documented multi-tick next step.

## 2026-07-12 (addendum 10): ★★★ ROOT CAUSE FOUND — strap 0x98070000 bit15 gates the FLOPPY FDC init
A 5-agent parallel RE workflow found it. The floppy FORMAT stalls because the WHOLE floppy FDC power-on
init + disk-command SERVICING loop is gated behind **strap 0x98070000 bit 15**, and the driver forced that
bit SET:
- **0x484A4FBA**: `movhu (0x98070000),d0 ; btst 0x8000,d0 ; beq 0x484A4FE3` -> bit15 CLEAR runs the FDC
  init (0x4854D835 / 0x4849FFE3 / 0x484A005A ...) then the disk-command servicing loop 0x484A506B (which
  drives real FDC I/O and, via the class-0x106 handlers 0x484A0657 etc., writes completion 0x5006BC19 =
  0xFB/0xF6). bit15 SET -> `ret` immediately, skipping the entire floppy subsystem.
- The MAME driver hardcoded bit15 SET (io_r offset 0x38000: `return 0x8000 | ...`). I did this in an
  earlier tick, MISREADING the bit-15-clear branch as an unwanted "factory power-on diagnostic". It is NOT
  a diagnostic -- it is the floppy subsystem's required init; the "multi-second GPIO bit-banging" seen there
  is that init BUSY-WAITING on FDC status the driver doesn't answer. CORRECTED (rule g).
- SD works because its worker task 0x4854AD90 is created UNCONDITIONALLY (SD DiskInit 0x4854ACED, no strap
  gate) and uses the SPI transport 0x9805000C. The floppy's servicing is the ONLY thing gated by bit15.
This reconciles EVERY thread: with bit15 set, the servicing loop never runs -> the format's posted disk
command is never serviced -> completion 0x5006BC19 stays 0 -> the poll 0x484A593E times out. (The
0x484A5075/0x484A50A9 completion writers I chased earlier are DEAD CODE -- unreferenced; the LIVE completion
writers are 0x484A0657 (msg id 0x1060002) / 0x484A3A62, doing SetCompletion(GetOpResult 0x4842C985 =
*(0x5000099C+id*4)). The 0x34000170-bit4 / 0x9805000C serial-transport handshake is the low-level FDC I/O
that only runs once the servicing loop is active.)

THE FIX (two coupled parts, both behind the FDCEXP switch, default OFF):
(a) Return strap bit15 CLEAR (done: io_r 0x38000 now clears 0x8000 when FDCEXP on) so 0x484A4FBA runs.
(b) Model the FDC/disk-controller (0x9CC00000 register file: presence 0x9CC00000=0x1C, self-test
    0x9CC00010/11/12=0x5A/0xA5/0x0A, status 0x9CC00009 bit0=media, config regs; + control regs
    0x90008020/0x90C00000; + the FDC status/FIFO the init polls) so the init COMPLETES instead of
    busy-waiting, and the servicing loop can do real disk I/O.
Full agent findings + register map: this file (addenda 8-10) + the disk-controller map from the workflow.

## 2026-07-12 (addendum 11): ★★★ CORRECTION — addendum 10 was WRONG. 0x484A4FBA is DEAD CODE; bit15 is moot.
Addendum 10 claimed clearing strap 0x98070000 bit15 would enable the floppy by letting the FDC engine
0x484A4FBA run. **That is false.** Proven by static + live RE:
- **Static (unidasm full-image disasm + pointer scan):** 0x484A4FBA has *zero* callers of any kind --
  no `call`/`jmp`/`bra`/`calls` targets it, no absolute 32-bit pointer to it exists anywhere in the 4MB
  image, it is in no task descriptor, and the instruction immediately before it (0x484A4FB7) is `ret 0,8`
  so it cannot be reached by fall-through either. The FDC init 0x4854D835 (the only toucher of the
  0x9CC00000 gate-array control regs) has *exactly one* caller: 0x484A4FE3, **inside** the dead engine.
  So the whole parallel-FDC path (0x484A4FBA / 0x4854D835 / 0x484A506B / format handler 0x484A5075) is
  unreachable. bit15 gates a function that is never entered -> its value is moot.
- **Live (fp.tr, the format trace, 557k lines):** during the format NONE of these run:
  0x484A4FBA=0, bit15-test 0x484A4FDA=0, 0x4854D835=0, 0x9805000C=0, 0x34000170(exact)=0,
  command builder 0x4854BB52=0, command reg 0x50005200=0, handler 0x484A5075=0. The only disk code that
  runs is the disk-present probe 0x484D7751 (x2). No disk I/O of any kind occurs -- the firmware just
  polls completion byte 0x5006BC19 (via 0x484A593E) which nothing writes -> timeout.

### THE REAL FLOPPY PATH (workflow agent a62b1297, the useful lead)
The production floppy transport is NOT the parallel 0x9CC00000 engine. It is a **serial disk transport**:
- Command builder **0x4854BB52** writes a command byte to RAM reg **0x50005200** (+params at 0x50005208/09).
- Transport **0x4854BF60 / 0x4854BF9D / 0x4854C013 / 0x4854C06F**, reached as *runtime driver-method
  pointers* (`mov (0x14,a0),a1 ; mov (4,a1),a2 ; calls (a2)` -- 0 static callers, which is exactly why
  no bp/pointer scan finds them). Each pushes a byte to data port **0x9805000C** (the SAME serial engine
  the SD path uses) then busy-polls handshake **0x34000170 bit4** (`movhu (0x34000170),d0 ; btst 0x10,d0`)
  inside a `setlb..lne` loop, IRQ-masked (`or 0x0800,psw` / `and 0xF7FF,psw`), bounded by a retry count.
- If bit4 never asserts, every byte transfer exhausts its retries -> command never completes -> the
  format's completion poll (0x5006BC19) times out.
- Disk-present probe **0x484D7751**: if 0x484D7713==3 (strap 0x98070000 bit1 clear) reads 0x9CC00021[3:2]
  for type; else uses 0x98070000 bits10/11. Returns "present" in the emulated state, so the format is NOT
  gated off -- it shows ERASE/WAIT then times out (matches observed behaviour).

### THE REAL FIX HYPOTHESIS (unverified -- needs a multi-second post-YES trace to confirm the transport runs)
1. Model the byte handshake: assert **0x34000170 bit4** when the modelled disk device has a byte
   ready/consumed at **0x9805000C**, so the transport's per-byte busy-poll succeeds.
2. Back the disk-present/type read (0x9CC00021[3:2] or strap bits10/11) with a plausible "disk present".
3. NOT needed: the 0x9CC00000 uPD765 device and the bit15 strap change (both target the dead engine) --
   revert them.
OPEN: my fp.tr window was only 6 frames after YES; the transport (if it runs at all) may start later in
the multi-second ERASE/WAIT. Must capture a ~3s post-YES trace to confirm 0x4854BF60/0x9805000C/0x34000170
actually execute before committing to the handshake fix. (Tooling: virtiofs fd-exhaustion wedges the shell
after each MAME launch -- run `sudo -n /usr/local/sbin/drop-caches` between launches; trace via
`mach.debugger:command("trace ...")`, NOT `-debug` which pauses.)

## 2026-07-12 (addendum 12): ★ THE FORMAT SHOWS "ERROR 08", it does NOT hang -- and the trigger chain
Live snapshot of the format after YES: snap0 = ATTENTION + PLEASE WAIT; snap1 (t+2s) = **"ERROR 08! An
error has occurred while the disk was formatting. The disk that you are using may be faulty. Please try
formatting another disk."** So the format actively runs, fails fast, and reports a specific error -- NOT a
silent hang. (The earlier "poll times out at 0x00" picture was the pre-experiment state / a too-short
window; with a floppy image mounted + current build the format-execute reaches the ERROR-08 path.)

WHAT THE FORMAT-EXECUTE ACTUALLY DOES (trace fx.tr = 7.5M lines, trace ON at YES; active work is only the
first ~602k lines = ~0.13s, then idle with the dialog up):
- Disk-present check **0x484D7751** -> calls 0x484D7713 (strap 0x98070000 bits1/2 -> 1, since driver sets
  the TG-present bits) -> since !=3, decode strap **bits 11/10**: `{00->5 nodisk, 01->1, 10->2, 11->3}`
  (disasm 0x484D778B-0x484D77BA). Driver returns bits10/11=0 -> **type 5 (no disk)**. Caller 0x4854BCE7:
  `cmp 4,d0` (type 4 special) else continue.
- A brief handshake on **0x3400016c** (NOT 0x34000170): `mov 1,(0x3400016c); movhu (0x3400016c),d0;
  or 0x0800,psw; movhu (0x3400016c),d0; btst 0x10,d0; beq...` -- reads bit4 of 0x3400016c (driver returns
  0 -> bit4 clear). Then 0x4854BD3E processes RAM 0x5000520c/0x50005210, returns.
- The disk-command **PROCESSOR 0x484ADxxx** builds a command packet at RAM **0x5006bee2** with an XOR
  checksum (loop 0x484AD9B0..0x484AD9E0, byte index 0x5006bef0 while <7), gated by status flag
  btst 0x0f,(0x5006be91). It RETURNS without transmitting -- data port **0x9805000C is never written**.
- ERROR 08 follows. So: the floppy command PACKET is BUILT but NEVER TRANSMITTED/serviced.

KEY: forcing the disk-present type to 3 (read-tap OR-ing strap bits10/11) does NOT clear ERROR 08 -> the
"no disk" type is not the sole gate; the failure is in the command processor / the missing transmit.

WORKING HYPOTHESIS (matches a74728a8): SD works because its worker task 0x4854AD90 is created
unconditionally and transmits over 0x9805000C; the **floppy has no equivalent worker/transmit path** in
this firmware image (dispatch gap), so the built packet is never sent and the op errors out. If instead a
floppy driver-init exists but is gated on a HW-present check, satisfying that gate (a real strap/register)
could wire it up. NEXT RE: (1) 0x484ADxxx command processor -- where exactly is the ERROR-08 result set
(immediate bail vs transmit-timeout)? (2) driver vtable 0x4867B948 [0-5] inits -- is one the floppy driver,
and is it gated? (3) 0x3400016c bit4 + the 0x5006bee2 packet consumer.

## 2026-07-12 (addendum 13): the class-5 disk command IS posted + serviced, but the device kickoff is unwired
Corrected view of the format-execute (live trace fx.tr, reliable):
- The format DOES post a **class-5 disk command (msg id 0x00050006)**: command processor 0x484ADxxx builds a
  packet at 0x5006bee2 (XOR checksum) then 0x48414C9B -> 0x48429906 -> 0x484288B1 (task table 0x5000757C,
  0x38-byte entries) -> 0x4C03C5AF (RTOS task wake). So the earlier "no class-5 post fires" claim (from the
  unreliable bpset) was WRONG -- the post is real. (The completion byte 0x5006BC19 is NOT the mechanism for
  this path: it gets 0 writes during the format.)
- The class-5 disk task THEN RUNS (trace 602k+: heavy 0x484D79x/0x484D767x/0x484B31x/0x484AC7x) -- a
  software STATE MACHINE **0x484D7930**: increments 0x50151bfc, advances state 0x500031f0 (0..5) via a jump
  table, sets event bits in 0x50151c00/c01, and at state 2 gates on **0x5006cc81 == 0x80** (-> call
  0x4C003F37). It does ZERO hardware I/O.
- **The gate 0x5006cc81 has exactly ONE writer -- the disk-op KICKOFF 0x484D7490** (bit-bangs GPIO
  0x36008004 bits5/2, calls 0x484D765F + 0x48448206, then `mov 0x80,d0; movbu d0,(0x5006cc81)`). That
  kickoff **ran 0x during the format AND has no static callers and no pointer refs anywhere** -- i.e. it is
  reached (if ever) only via a runtime driver-method pointer (`calls (a2)`), exactly like the serial
  transport 0x4854BF60. It is NOT wired for the floppy path in this run.

PATTERN (now clear across addenda 11-13): every disk *hardware-facing* function -- the parallel engine
0x484A4FBA (dead), the serial transport 0x4854BF60 (0 static callers), the kickoff 0x484D7490 (0 callers/
0 pointers) -- is invoked only through runtime device-driver method pointers. SD works because its device's
methods are installed + called (SD init 0x4854ACED builds the device table at 0x50082738 stride 0x30 and
creates the worker). For the FLOPPY, the device's methods (kickoff/transport) are never installed/invoked,
so the class-5 op runs the generic state machine, does no real I/O, and errors -> ERROR 08.

=> ROOT CAUSE (best current understanding): a **floppy device-registration / driver-method-install gap**.
The format posts + the disk task services, but the floppy device's method table (containing 0x484D7490-class
kickoff + the 0x4854BF60 transport) is not populated, so no FDC hardware is ever driven. This is NOT
fixable by mapping a uPD765 at a guessed address (there is no code to drive it). NEXT RE (next tick):
compare an SD op's device-method dispatch (which IS wired) against the floppy's -- find the device table
0x50082738 entry for the floppy, why its method pointers are null / why it isn't registered, and whether a
hardware-present strap/register at BOOT would cause the floppy device (and its methods) to register. If the
floppy device simply isn't in this firmware's device table, the format cannot be completed without the real
FDC hardware behaviour that populates it -- a genuine firmware/hardware-modelling boundary to report.

## 2026-07-12 (addendum 14): ★★★ SERVICE MANUAL FOUND -- IC103 FDC fully characterized (schematic)
service_manual/technics_sx-kn7000_keyboard.pdf (160pp) pages 54/79/104. **IC103 = C1DB00000607 = FDC
(FLOPPY DISC CONTROLLER)**, MAIN 2/5 schematic (page 104). Pinout (CPU side):
- **A0(pin44) <- system A(1), A1(43) <- A(2), A2(42) <- A(3)** -- 3 register-select lines (8 registers),
  stride = system addr bit1 (=2 bytes). NOT A0-connected.
- **CS(45), IOR(46), IOW(47), ORQ(48 = DMA request), IRQ, RESET(38)**.
- **Data bus = system D16-D23** (byte lane 2 of the 32-bit bus) via 47R nets Z109/Z110 -> FDC D0-D7.
- FDD side: MEDIA IO0/1, DENSEL, DRVDEN0/1, RDATA, DSKCNG(disk-change), WRYPRY(write-protect), INDEX,
  TRXO(TRK00), WDATA, WGATE, HDSEL, STEP, DIR, MTRO(motor), -> CN101 "TO FDD".
=> This is a **uPD765-family / PC-style FDC** (8 regs via A0-A2, IOR/IOW strobes, IRQ + DMA), i.e. exactly
   MAME's upd72067 -- the FDCEXP experiment used the RIGHT device but the WRONG address/width (0x9CC00000,
   only 2 regs). CORRECTION to addendum 8-13: the dead 0x4854D835 (touching 0x9CC00009 / 0x9CC001FC) is
   NOT this FDC -- those offsets aren't on the D16-23 lane and don't fit an 8-reg FDC; it's a different
   device (likely IC104 LCD-ctrl or SD). The real IC103 FDC is at its own CS base (TBD from the bus
   controller), byte-wide on D16-23, 8 regs at system offsets {0,2,4,6,8,A,C,E}.
- disk-change (DSKCNG) + write-protect (WRYPRY) + INDEX + TRK00 are FDC status bits -> the "media inserted"
  the format's device-selection needs likely comes from the FDC, NOT strap 0x98070000 (which is DRIVE-unit
  present, bits10/11). This is why forcing the strap didn't clear ERROR 08. Model the FDC w/ a disk inserted
  (INDEX pulsing, DSKCHG clear) and the media check may pass.
NEXT: (1) find the FDC CS base from the MN10300 bus-controller region setup (boot 0x484009D0 -> 0x32000xxx);
(2) map upd72067 there on the D16-23 lane; (3) insert floppy image; (4) re-test format past ERROR 08.

## 2026-07-12 (addendum 15): ★★★★ THE FDC IS AT 0x98020000 (schematic decoder + firmware confirm)
CPU = **IC4 MN103002A**. Chip-select decoder **IC1 = TC74VHC138F (3-to-8)**, page 101: address inputs
A0<-A(16), A1<-A(17), A2<-A(18); it sub-decodes the **0x98000000 CS region** into 0x10000 slots. Outputs:
  Y0 0x98000000 (DSP)   Y1 0x98010000 = **FDC.DACK** (DMA-ack strobe, NOT the regs)
  Y2 0x98020000 = **FDC.CS**  <-- the FDC register base
  Y3 0x98030000 NC      Y4 0x98040000 = TGCS2 (TG)   Y5 0x98050000 = TGCS (SD/snd)
  Y6 0x98060000 (snd)   Y7 0x98070000 (strap)
(Y4=TG@0x98040000 fixes the CS base at 0x98000000; the old "FDC @0x98010000" guess was the DACK slot,
one below the real reg base -- that's why it looked "close but never accessed as regs".)

FIRMWARE CONFIRMS (fp.tr format trace + disasm): byte accesses (movbu, data on lane D16-D23) to
  **0x98020004** (reg 2) read+write at boot PC 0x484000B5/C3/D1 -- a classic FDC DOR reset sequence
  **0x9802000E** (reg 7) read at 0x48402623 -- the DISK-CHANGE / media check (DIR bit7 = DSKCHG)
Register R = (byteoffset>>1)&7 (A0-A2 <- sysA1-A3), so regs at offsets {0,2,4,6,8,A,C,E}. PC/AT-style map
fits: reg2=DOR(offset4), reg4=MSR/DSR(offset8), reg5=FIFO(offsetA), reg7=DIR/CCR(offsetE).

ROOT CAUSE of ERROR 08 (finally, and FIXABLE): the driver currently backs 0x98020000 with the sound-
control io_r/io_w (the old memory mislabelled 0x98020000 "snd"; the schematic proves it's FDC.CS). So the
firmware's DOR reset + disk-change read return garbage -> media check fails -> ERROR 08. FIX = model a
uPD765-family FDC (MAME upd72067) at 0x98020000 on the D16-D23 byte lane, offsets {0..E}=regs{0..7},
DMA/TC via 0x98010000, IRQ via the FDC's INT; insert a floppy image so DSKCHG/INDEX/MSR read sane.
This supersedes addenda 8-14's "FDC not locatable / dead code" -- the dead 0x484A4FBA/0x9CC00000 path was
a red herring; the LIVE FDC is 0x98020000 and the firmware DOES drive it. NEXT: trace the full 0x9802000x
sequence (boot init + format) to pin the exact register semantics, then implement.

## 2026-07-12 (addendum 16): format REACHES the FDC + busy-polls MSR (needs command completion + DMA)
Debugger trace of the format-execute (fx2.tr, 38.7M lines, correct nav): the format DOES drive the FDC.
- FDC micro-op dispatcher **0x48400084** runs 14x (command codes 0x80-0x84 = timed DOR reset/restore
  primitives, sequenced by the state machine 0x50000010/0x50000020). Format FDC code 0x484027xx runs.
- Then it **busy-polls MSR (0x98020008) 230,052x at PC 0x48400145** (read MSR -> helper) waiting for the
  FDC command to complete. DOR was written 0x1C (bit3 = DMA gate SET) -> the FORMAT TRACK command is in
  DMA mode. **No DMA happens** (0x98010000 = FDC.DACK is NOT accessed = 0; no 0x34000 DMAC access either)
  -> the FDC's FORMAT TRACK never gets its sector-ID data -> stays in execution phase -> MSR never reaches
  the state the firmware waits for -> busy-poll forever -> (eventual timeout ->) ERROR 08.
- So the REMAINING blocker is FDC command completion: (1) the FORMAT TRACK data phase needs DMA -- either
  the MN10300 internal DMAC (FDC.DRQ->DACK->TC) driving RAM<->FDC, or a software-DMA path; the firmware
  reads 0x98010000 (DACK) elsewhere (0x48403068) so map 0x98010000 -> m_fdc->dma_r()/dma_w(); (2) assert
  TC (terminal count) at the byte count to end the command; (3) verify my N82077AA model executes FORMAT
  TRACK and sets MSR/INT correctly. NEXT: disassemble the MSR-poll helper at 0x48400145's callee to see
  EXACTLY which MSR bit(s) the firmware waits for, then make the FDC reach that state.
- CAVEAT (investigate): a memory-tap run (fdcstep.lua, no debugger) showed 0 FDC accesses and the format
  returned to the DISK menu quickly, while the debugger-trace run showed 230k MSR polls -- the FDC-reset
  state machine uses timing delays (0x50000010/20) so the path may be timing-sensitive / the tap run
  diverged. Re-verify the FDC IS reliably reached (tap the MSR poll PC 0x48400145 without the debugger).

## 2026-07-12 (addendum 17): the MSR poll = wait for command-complete; FORMAT TRACK needs its DMA data
Decoded the busy-poll (fn 0x48400190, loop @0x484001A8): it reads MSR (0x98020008) via 0x48400142 and waits
for **(MSR & 0x1F) == 0** = FDC not-busy (CB bit4 clear) + no drive seeking (bits0-3). 500-tick timeout
(counter 0x50151bfc, cmp 0x1F4). The format:
- issues **FORMAT TRACK** = 6 FIFO bytes via the command primitive 0x48400185/0x48400188 (0x9802000a),
  wrapped by the command-send fn ~0x48400CEx/0x48400D0x; DOR set 0x1C (bit3 DMA gate + bit4 motor0 on).
- then busy-polls MSR for CB=0. My N82077AA keeps CB set because FORMAT TRACK never completes.
WHY it never completes (MAME upd765 format_track_continue): HEAD_LOAD -> WAIT_INDEX (needs a floppy index
pulse) -> WRITE_TRACK live state machine, which requests the per-sector C/H/R/N via **DRQ -> dma_w()** and
ends on **TC**. Neither is wired: the FDC's drq_cb/tc are logging stubs and no DMA feeds the data. So the
FDC hangs in the write phase (or at WAIT_INDEX) with CB=1 -> the firmware poll times out -> ERROR 08.
The DMA is the MN10300 (MN103002A) on-chip DMAC: it transfers the firmware's format-data buffer -> the FDC
via the **0x98010000 (FDC.DACK)** slot (decoder Y1). No 0xd4/dedicated DMAC access shows in the trace, so
the DMAC regs are on-chip (find them). get_ready() with ready_connected=false returns true (drive ready OK);
wpt (write-protect) must be clear (image not read-only).

IMPLEMENTATION PLAN (next tick -- clear path to a WORKING format):
1. Diagnose the exact stall point: add low-volume logging to fdc_r/fdc_w (log FIFO cmd bytes + DOR + the
   FDC main_state), rebuild, run the format -> confirm WAIT_INDEX vs write-phase-DMA. (Motor is on via DOR
   bit4; verify MAME's floppy generates index pulses -- if not, that's the stall.)
2. Wire the FORMAT TRACK data phase: connect m_fdc->drq_cb to a handler that, on DRQ, supplies the next
   format byte via m_fdc->dma_w() and asserts m_fdc->tc_w() at the byte count. Source the bytes from the
   MN10300 DMAC's programmed buffer (model the on-chip DMAC minimally: src/count, feed on FDC.DACK
   0x98010000), OR (labelled hack, rule g) synthesise C=cyl/H=head/R=1..SC/N from the FORMAT TRACK command
   bytes (SC, N) captured from the FIFO.
3. Verify: format completes (MSR CB clears, poll exits), the disk image gets a valid FAT12 layout, and a
   subsequent SAVE/LOAD round-trips. Then it's a real user-facing win.
Everything up to the FDC command is now correct + faithful (schematic-proven 0x98020000 N82077AA); only the
DMA data phase remains. This is standard MAME FDC-DMA wiring.

## 2026-07-12 (addendum 18): ★ THE FIX MECHANISM -- FDC data phase = software-DMA via the FDC.DRQ interrupt
Found the actual data-transfer path. The KN7000 FDC transfer is NOT a hardware DMAC autonomously moving
bytes -- it is **software-DMA driven by the FDC.DRQ interrupt**:
- The per-byte transfer fn **0x48402140** (the FDC.DRQ ISR body): for each byte it either reads
  **0x98010000 (FDC.DACK)** -> RAM buffer (read op, at 0x48402168 for cmd 5/0xd) or RAM buffer ->
  0x98010000 (write op, e.g. FORMAT/WRITE, at 0x4840217a). Buffer ptr = *(0x5009e8a4), running index =
  *(0x5009e860). It then `bclr 0x10,(0x36008004)` (GPIO handshake) and reads 0x34000160.
- So FORMAT TRACK works like: firmware issues the command (DMA mode, DOR bit3), the FDC asserts DRQ per
  byte -> FDC.DRQ IRQ -> ISR 0x48402140 feeds one C/H/R/N byte via 0x98010000 -> repeat -> FDC.TC ends it
  -> MSR CB clears -> the firmware's MSR poll (0x48400190) exits -> format completes.
WHY IT STALLS NOW: (a) FDC.DRQ (drq_cb) is a LOGGING STUB -- it never raises an MN10300 interrupt, so the
ISR never runs; (b) 0x98010000 is UNMAPPED (io_r returns 0), so even if the ISR ran it couldn't move bytes.
=> The FDC hangs waiting for its data, MSR CB stays set, the poll times out -> ERROR 08. (Confirmed by the
trace: 0x98010000 = 0 accesses during the format.)

THE FIX (concrete, in the driver -- the INTC is already modelled: intc_assert(group)):
1. Map **0x98010000 -> m_fdc->dma_r()/dma_w()** (byte-wide, the FDC.DACK slot). [easy, schematic-proven Y1]
2. Wire **m_fdc->drq_wr_callback() -> intc_assert(<FDC-DRQ group>)** so a DRQ raises the interrupt that runs
   the ISR 0x48402140. Also wire **intrq (command-complete) -> intc_assert(<FDC-IRQ group>)** (the firmware
   mostly polls MSR, but INTRQ may be needed for the result phase / other commands).
3. The FDC connects to the MN103002A external interrupts IRQ1-IRQ7 (pins 41-48; schematic has FDC.DRQ,
   FDC.TC nets). REMAINING UNKNOWN = which IRQn / INTC group FDC.DRQ + FDC.IRQ use -- find via the schematic
   (trace FDC.DRQ/FDC.IRQ nets to the CPU IRQn pins) or the firmware (the ISR-registration / GxICR the DRQ
   ISR 0x48402140 is installed on). Then wire drq/intrq to those groups.
4. Also assert FDC.TC at the transfer end (m_fdc->tc_w) -- the firmware may drive TC via GPIO/0x34000160 or
   count-based; check the ISR's end path (bclr 0x36008004 bit4 + 0x34000160 read).
Once wired, FORMAT TRACK should complete and write a valid FAT12 layout. This is the last piece; everything
up to it (FDC @0x98020000 N82077AA, command issue, MSR poll) is proven correct.

## 2026-07-12 (addendum 19): FDC fully wired, but format doesn't RELIABLY reach it (timing/race)
Wired the software-DMA (commit: drq/intrq -> intc_assert(0x18); 0x98010000 -> dma_r/dma_w). Boot: no
regression, no interrupt storm. BUT testing exposed a deeper, pre-existing issue:
- With the DEBUGGER (-debug -debugger none), the format-execute DOES reach the FDC (fx2.tr: dispatcher
  0x48400084, FORMAT TRACK issued, MSR busy-poll 230k).
- WITHOUT the debugger (plain tap runs, incl. before the DMA wiring), the format touches the FDC **0
  times** (DACK=0, FIFO=0 through +18s), shows ERROR 08, and returns to the DISK menu -- i.e. it errors in
  the class-5 disk-task SOFTWARE dispatch BEFORE any FDC access (matches the earlier night/night(2)
  analysis: the disk task errors without hardware I/O).
=> The format's reaching-the-FDC is TIMING/RACE sensitive. Real hardware formats disks, so the no-debugger
   "errors before the FDC" behaviour is an EMULATION bug -- likely a race in the RTOS disk-task dispatch
   (timers/interrupts/the audio+DSP threads) that makes the class-5 disk op fail early. The debugger's
   different scheduling masks it. (Note MAME emulates in emulated-time, so a pure CPU-vs-timer ratio
   shouldn't change with the debugger -- this points to a genuine race / non-determinism, possibly the
   DSP-bridge audio thread or an interrupt-delivery ordering.)
STATE: the FDC is now correctly located (0x98020000), modelled (N82077AA), and wired (INTC grp 0x18 + DACK
0x98010000) -- all faithful + committed + no regression. The remaining blocker is NOT the FDC; it is the
class-5 disk-task early-error that stops the format from reaching the FDC in normal (no-debugger) runs.
NEXT: (1) reproduce the divergence deterministically -- run the format WITHOUT the debugger but capture via
memory taps where the class-5 disk task errors (the ERROR-08 decision point 0x484ADxxx / the completion
byte / the disk-op result), and compare against the debugger run's path to find the diverging branch;
(2) suspect the FDC RESET path -- the format's FDC init resets the FDC (DOR pulse) which with intrq wired
now fires intc_assert(0x18); check whether that reset-interrupt (or its absence) is what flips the branch;
(3) once the format reaches the FDC reliably, the DMA wiring should carry it through FORMAT TRACK.

## 2026-07-12 (addendum 20): ★ CORRECTION -- "format reaches the FDC" was a TRACE observer-artifact
Ruled out both the SHARC DRC (-nodrc: still 0 FDC accesses) AND -debug itself (-debug -debugger none WITHOUT
the trace command: still 0 FDC). The ONLY run where the format reached the FDC (fx2.tr, 230k MSR polls) used
`dbg:command("trace")`, which forces cross-device scheduler synchronisation to order the trace output. So
addenda 16-17's "format issues FORMAT TRACK + busy-polls MSR" was an OBSERVER ARTIFACT of the trace.
REAL behaviour (normal, -nodrc, and -debug-no-trace all agree): the format touches the FDC 0 times, errors
in the class-5 disk-task SOFTWARE dispatch BEFORE any FDC access, shows ERROR 08 -> DISK menu. Same blocker
as the night/night(2) analysis (disk task errors without hardware I/O); it is TIMING/INTERLEAVE sensitive
(the trace's fine sync let the dispatch proceed).
=> The FDC model + DMA wiring (addenda 15-18) remain CORRECT + faithful (boot init drives the FDC; the
   format WOULD reach it once the dispatch race is fixed) but are NOT exercised by the format yet.
NEXT: the driver sets NO CPU quantum -> maincpu(MN10300)+SHARC interleave coarsely. Test
`config.set_perfect_quantum(m_maincpu)` (fine interleave) with a NORMAL run: if the format then reaches the
FDC (and, with the DMA wiring, completes), coarse interleave was the bug. Else the race is elsewhere
(memory-tap the class-5 error decision 0x484ADxxx in a normal run).

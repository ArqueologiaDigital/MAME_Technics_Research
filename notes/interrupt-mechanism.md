# MN10300/AM33 interrupts on the KN7000 — implementation spec

The MILK RTOS only advances its scheduler — and therefore only draws the UI and
only delivers panel/MIDI receive — when it takes a periodic **timer interrupt**.
The MN10300 MAME core currently stubs interrupts. This is the reverse-engineered,
code-level spec to implement them. It combines a firmware/architecture study with
direct disassembly of the (self-loaded) library ROM.

## 0. The key reconciliation: the faithful path is viable

An earlier analysis concluded the low-level interrupt handler, the `rti`, the
vector setup and the scheduler dispatch core all live in the "undumped" library
ROM at `0x4C000000`, and that MILK's scheduler was therefore blocked on a dump.
**That is resolved.** The library ROM is **not undumped — it is self-loaded from
the program flash** (see [`library-rom-loading.md`](library-rom-loading.md);
mapped in the driver by aliasing `0x4C000000`↔`0x8C000000`). Disassembling the
library region directly (program-flash offset `0x3B8FD1`, running at
`0x4C000000`) confirms the low-level handler **is present in emulation**:

- **3 `rti` (`F0 FD`)** exist in the library, at `0x4C03DE24`, `0x4C03DEE7`,
  `0x4C03DF13` (there are none in the app flash because the app-level ISRs are
  *callbacks* that end in `ret`, not `rti`).
- The **dispatcher** at ~`0x4C03DDC0` reads the pending group, indexes a handler
  table, and `calls` the registered callback:

  ```
  4c03ddc5: mov   0x34000100, a2
  4c03ddcb: movhu (a2), d3            ; read IAGR (pending group) at 0x34000100
  4c03ddcd: cmp   0, d3 ; bne
  4c03ddd1: mov   0x34000104, a2      ; second group register if first is 0
  4c03ddd7: movhu (a2), d3 ; add 8
  4c03dddb: lsr   1, d3               ; -> source index
  4c03ddde: mov   0x50380a6c, a2 ; ... (arg table, work RAM)
  4c03dde7: mov   0x50380b64, a2      ; HANDLER-POINTER TABLE (work RAM)
  4c03ddee: mov   (d3,a2), a2         ; a2 = registered ISR callback
  4c03ddf3: calls (a2)                ; call it (e.g. panel 0x484ACC13)
  4c03ddf8: and   0xf7ff, psw         ; epilogue: crit section, dec nest count
  ...        (0x50380d0c nesting counter) ... -> rti @0x4C03DE24
  ```

So **implementing the CPU-core interrupt primitives + an interrupt controller +
a timer is now sufficient** — the self-loaded library provides the entry,
dispatch, `rti` and scheduler. This is the "faithful path". No HLE needed.

## 1. CPU take/return semantics

- **`PSW.IE = 0x0800`** — CONFIRMED (arch `EPSW_IE`; every firmware ICR update is
  bracketed `and 0xf7ff,psw` / `or 0x0800,psw`). Drop the "provisional" TODO on
  `FLAG_IE` in mn10300.cpp.
- **`PSW.IM = bits[10:8] = 0x0700, shift 8`** — 3-bit priority (arch `EPSW_IM`).
  A maskable interrupt of level L is accepted only if `IE=1` and `L < IM`; on
  accept, `IM ← L`. Initialise `IM=7` so any level 0–6 can be taken once IE set.
  The firmware never writes IM in the app flash — the library ROM does.
- **On accept, hardware pushes PC and EPSW to the stack (`SP`)** and vectors via a
  per-level register **`IVARn`** (AM33 `IVAR0..IVAR6` + `TBR`). The library ROM
  writes IVAR at boot (so no static vector table in the app flash).
- **`rti = F0 FD`**: pop EPSW, then pop PC (restores IE/IM). Mirror the push order.

### The ISR callbacks (app flash) are called, not vectored
Panel `0x484ACC13`, MIDI-1 `0x484B1E86`, MIDI-2 `0x484B2037` open with
`movm [regs],(sp)` and end with **`ret` (0xDF)**. They are ordinary subroutines
`calls`-ed by the library dispatcher above; the library saves/restores the full
context and executes the single `rti`. The callback acks its own ICR (§2).

## 2. Interrupt controller (on-chip INTC, `0x34000100` block)

- **`0x34000100` = IAGR** (pending-group register; read by the dispatcher).
  `0x34000104` = second group. **Per-source `GxICR(n) = 0x34000108 + …`**, 16-bit
  (`movhu`); observed `0x34000108..0x34000178`.
- **GxICR bit fields** (arch-standard, cross-checked to firmware writes):

  | bit | mask | name | meaning |
  |---|---|---|---|
  | 0 | 0x0001 | DETECT | write 1 = acknowledge handshake |
  | 4 | 0x0010 | REQUEST | pending; HW-set, polled `btst 0x10`, cleared on ack |
  | 8 | 0x0100 | ENABLE | per-source enable (boot disable-all clears via `and 0xfeff`) |
  | 12-14 | 0x7000 | LEVEL | source priority (shift 12) |
  | 15 | 0x8000 | NMI | |

- **Sources:** MIDI-1 RX `0x34000148`, MIDI-2 `0x34000150`, panel RX
  `0x34000168`, **system timer (candidate) `0x34000174`**.
- **Acknowledge sequence** (proven inside `0x484ACC13`): `and 0xf7ff,psw` (clear
  IE) ; `icr = (icr & 0xff00) | 0x01` (preserve ENABLE/LEVEL, clear REQUEST, set
  DETECT) ; `or 0x0800,psw`. **Emulator rule:** on a CPU write to a GxICR whose
  REQUEST bit is 0, clear that source's internal pending flag and de-assert its
  IRQ line. Boot disable-all is at `0x484D74D2` (sweeps `0x108..0x178`).

## 3. The scheduler timer

- Timer HW at `0x32000000` (control `0x20`, prescaler `0x10=0x400`, reload A
  `0x40`, B `0x42`), programmed at `0x4840FFC3` / `0x484D7111`. 16-bit compare
  timer; absolute Hz undetermined (input clock/region strap unknown — pick a
  plausible rate, e.g. 1 kHz, and tune).
- Timer ICR: `0x34000174` (inferred). The tick ISR lives in the library ROM.
- **Scheduler linkage** (proven): the tick advances a software-timer count array
  `0x5011FA8C[]` (parallel to the object table `0x5000757C`, stride 0x38);
  `ApTimer (0x484299F1)` services it and posts wake/dispatch events into the run
  queue driven by `MainTaskControl (0x48414AFA)` / `DispatchEvent (0x4842936F)`.
- **Minimum to get the UI up: exactly one periodic timer interrupt.** Panel + 2
  MIDI interrupts are input-only, not needed for the scheduler to advance.

## 4. Implementation plan (MAME)

### CPU core (mn10300.cpp/.h)
1. Add `FLAG_IM = 0x0700`, `IM_SHIFT = 8`. Keep `FLAG_IE = 0x0800`.
2. **`rti`** (fill the `execute_f0` TODO, beside the working `rets` at op2==0xFC):
   ```cpp
   else if (op2 == 0xFD) { m_psw = pop32(); m_pc = pop32(); m_possible_irq = true; return; }
   ```
3. **`take_irq(level, group)`** (uses the existing `push32`):
   ```cpp
   push32(m_pc); push32(m_psw);
   m_psw = (m_psw & ~FLAG_IM) | (level << IM_SHIFT);
   m_iagr = group;
   m_pc = ivar_vector(level);   // read IVAR[level]  (see OPEN below)
   m_icount -= 7;
   ```
4. **`check_irq()`**: if `!(m_psw & FLAG_IE)` return; ask the INTC for the
   highest-priority ENABLE&REQUEST group with `level < (m_psw&FLAG_IM)>>8`; if
   found, `take_irq(level, group)`.
5. **`execute_run()`**: add at the top of the step loop
   `while (m_possible_irq) { m_possible_irq = false; check_irq(); }` (as MN10200).
6. **`execute_set_input(line, state)`**: latch the line as pending, set
   `m_possible_irq = true`. Replace the placeholder IRQ enum with `TIMER, PANEL,
   MIDI1, MIDI2`.

### Driver devices
- **INTC** decoding `0x34000100..0x34000178`: IAGR at +0x00/+0x04, GxICR array
  from +0x08. `assert_group(n)` sets REQUEST + raises the CPU line; CPU-side ack
  (REQUEST=0 write) clears it; `pending(threshold)` returns lowest-LEVEL
  ENABLE&REQUEST group + its number (for IAGR). (`0x34000100` currently falls in
  the driver's `io_r/io_w` logger range — carve it out like the SIO block.)
- **System timer** on `0x32000000`: an `emu_timer` that on expiry calls
  `intc->assert_group(timer_group)` (the `0x34000174` source).

### Reference templates
Sibling MN10200 core (`kn7000_mame_build/src/devices/cpu/mn10200/mn10200.cpp`):
`take_irq` :292, `check_irq` :304, `execute_set_input` :345, `rti` :788, ICR I/O
:1748/2136, timers :423-461. `push32`/`pop32` already exist in mn10300.cpp (~:208).

## OPEN QUESTIONS (pin before/while coding)
1. **`IVAR` address + the exact push frame.** AM33 `IVAR0..6`/`TBR` are generically
   at `0xC0000000+n*4`; the library ROM writes them at boot. Find that write in the
   library code (search the library region for stores of a `0x4C03DDxx`-class
   handler address, or for `0xC0000000` accesses) to learn the vector address and
   the handler entry, and confirm whether the push frame is `[EPSW][PC]` with
   `SP-=8` (32-bit each) — then `take_irq`/`rti` must match it exactly so the
   library's context save/`rti` line up. For a first bring-up, if IVAR isn't
   written to a modellable location, `take_irq` can jump straight to the observed
   handler entry (~`0x4C03DDxx`, resolve precisely) as a shim.
2. **Timer tick rate** (input clock unknown) — start ~1 kHz and tune by feel.

## IMPLEMENTATION STATUS (2026-07-05)

Implemented and WORKING end-to-end (commits: mn10300 mechanics `da8ca77`, driver
INTC+timer `97c0cda`):
- CPU core: `PSW.IM`, `rti`, `take_irq` (push PC+PSW, clear IE, vector), `check_irq`,
  `execute_set_input`, run-loop gate. `set_irq_vector()` public.
- Driver INTC at `0x34000100` (GxICR array + IAGR read) + a ~1 kHz system-tick
  `emu_timer`. CPU line 0 asserted while any ENABLE&REQUEST group exists.
- **Empirical vector: `0x4C03DDA0`** (the library low-level handler entry; `movm`
  context save → `udf12/13/15` → IAGR dispatch). Confirmed correct: interrupts
  fire, the handler runs and RETURNS via `rti` to the interrupted PC (same PC/SP
  every tick ⇒ context save/restore is symmetric even through the `udf*` ops).
- **Empirical timer group: `0x06`** (GxICR `0x34000118`, the ONLY group the boot
  enables before waiting; ENABLE=1, level 6). NOT `0x1D` as first guessed.

Not yet working — the boot takes the tick but does not advance:
- It parks calling a function at `0x4C03DCF3` (`clr d0 ; ret` — returns 0), i.e. a
  wait loop polling "is a task ready?" that stays 0. The tick handler runs but does
  not wake a task.
- NEXT: trace what the handler does after `0x4C03DDA0` — does it reach the tick
  service `ApTimer (0x484299F1)` and advance `0x5011FA8C[]`? Candidates for the gap:
  (a) IAGR index encoding (I return `group<<1`; confirm the dispatcher's table
  `0x50380A6C`/`0x50380B64` lands on the tick handler for group 0x06); (b) the
  `udf12/13/15` AM33 ops are treated as unimplemented by the core and may corrupt
  the handler's PSW-field extraction; (c) tick rate/behaviour. Implementing the
  `udf*` (F6 extended) ops is the most likely missing piece.

## UPDATE (2026-07-05, cont.): IAGR encoding fixed; blocked on F6/udf ops

Debugging why the tick didn't advance the scheduler:
- The dispatcher (0x4C03DDC0) turns the IAGR at `0x34000100` into a table index via
  `d3 = IAGR; d3 >>= 1; d3 += d3` (i.e. `index_byte = IAGR & ~1`), reads a halfword
  from `0x50380A6C[index]`, then a word handler from `0x50380B64[that*2]`.
- Dumped those tables at runtime: the ONLY registered (non-null) handler is at
  table index `0x18` → **`0x4C02BB05`**, which needs **IAGR = 0x30**. The enabled
  timer is group `0x06` (GxICR `0x34000118`). So the IAGR must encode the pending
  group as **`group << 3`** (`0x06<<3 = 0x30`) — NOT `group<<1`. FIXED in `intc_r`.
  (`0x4C03DEE9` is the null/spurious handler = a bare `rets`.)
- With the correct IAGR the timer dispatches to the real handler `0x4C02BB05`, but
  it CRASHES (PC runs into work RAM). Cause pinned exactly: the ONLY unimplemented
  opcodes hit are the **F6 `udf12/13/15` at `0x4C03DDA7/AB/AF`** (the handler's
  context save: `mov psw,d3 ; udf15 d3,d3 ; mov d3,(0xc,sp) ; udf13 d3,d3 ;
  mov d3,(8,sp) ; udf12 d3,d3`). The core skips F6 as a no-op → the saved context
  is wrong → the later context-switch/return jumps to garbage.

### The real blocker: the AM33 F6 extended-ALU group is unimplemented
`F6 <op2>` is a whole instruction group MAME's disassembler doesn't decode (it
prints `udf<op2>>4>`). It is **heavily used** across the firmware (F6 00 ×216,
F6 FF ×199, F6 06 ×72, F6 63 ×62, F6 DF ×52, …), so it is real AM33 code, not rare
coprocessor ops. The boot only reached it now because it's in the interrupt path.
- NEXT: implement the F6 group in the core using the AM33 instruction semantics
  (binutils `opcodes/mn10300-opc.c` / GCC am33 backend define the encodings). Then
  re-enable the system-tick timer (one commented line in `machine_reset`) — the
  correct IAGR + INTC + CPU mechanics are all already in place, so the tick should
  then advance `ApTimer`/the scheduler.
- STABLE STATE meanwhile: IAGR fixed; timer start commented out so nothing crashes.

## UPDATE 2: the blocker is AM33 extended-state (32-bit EPSW + E-regs + F5/F6 ops)

Full disassembly of the library interrupt handler's context save (0x4C03DDA0) and
restore (epilogue @0x4C03DDF8..0x4C03DE24) shows exactly what's needed:

PROLOGUE (save):
```
movm [d2,d3,a2,a3,other3],(sp)   ; 'other3' (mask bit3) = AM33 EXTENDED-reg group
add  -0xc,sp                      ; 12-byte local frame (slots 0,4,8)
mov  psw,d3 ; udf15 d3,d3 ; mov d3,(0xc,sp)   ; frame[0xc] (1st saved-reg slot) = f15(psw)
            ; udf13 d3,d3 ; mov d3,(8,sp)     ; local[8] = f13(f15(psw))
            ; udf12 d3,d3 ; mov d3,(4,sp)     ; local[4] = f12(...)
mov  psw,d3 ; mov d3,(0,sp)                    ; local[0] = psw
movhu (0x50380d0c),d3 ; add 1,d3 ; ...         ; nest-count++
```
EPILOGUE (restore):
```
mov (0,sp),d2 ; and 0x08,d2 ; mov psw,d3 ; or d2,d3 ; mov d3,psw  ; restore V (bit3) from saved psw
mov (4,sp),d3 ; mov (8,sp),d2 ; udf21 d3,d2 ; ...                 ; udf21 = F5 1E
... ; rti
```

Findings that pin the implementation:
1. **`movm` extended groups.** The mask bits 0/2/3 ("other0"/"other2"/"other3")
   are AM33 extended-register groups that the core's `store_regs`/`load_regs`
   currently SKIP (they log "AM33 ext regs not modelled" and push/pop nothing).
   Because `other3` is skipped, the handler's `mov f15(psw),(0xc,sp)` — meant for
   the first *extended*-reg slot — instead lands on **a3's saved slot**, so a3 is
   restored as garbage → the later use of a3 jumps into work RAM (the crash).
   FIX: model the extended-register groups (add E0-E7 + whatever else they cover)
   and push/pop the correct count so the frame lines up and a3 is preserved.
2. **The `udf` ops are AM33 extended-ALU (F5/F6).** udf12/13/15 (F6 CF/DF/FF) and
   udf21 (F5) transform psw-derived values; the epilogue restores the V flag and
   runs udf21. These manage the AM33 **32-bit EPSW** (the core only models a 16-bit
   `m_psw`). Implementing them needs the AM33 op semantics.
3. So the scheduler-advance needs a cohesive AM33 extended-state feature:
   **32-bit EPSW + E0-E7 (+ any other extended regs) + the F5/F6 op group + the
   `movm` extended groups**. take_irq/rti may also need to route the saved PC/EPSW
   through the extended regs the handler expects (confirm vs the AM33 interrupt
   model). This is well-scoped but needs the AM33 instruction reference (binutils
   `opcodes/mn10300-opc.c`, the sim `sim/mn10300/am33.igen`, GCC am33, or the AM33
   manual) — research is in flight. The `store_regs` group sizes are the first
   concrete thing to get from that source.

## RESOLVED (2026-07-05): the "udf" ops are AM33 DSP instructions

Two research agents + the user's local binutils-gdb clone (~/compartilhado/KN7000/
binutils-gdb) settled it. MAME's disassembler mislabels the whole F5/F6 group as
"udf". They are the AM33 DSP MAC-register ops (semantics from the GDB simulator
sim/mn10300/{mn10300,am33}.igen, cross-checked to the Panasonic manual):
- F6: mulq/mulqu (32x32->64, hi->MDRQ), sat16/sat24, getchx/getclx/getx (read
  MCRH/MCRL/MDRQ). F5: putx (MDRQ<-Dn), putchclx (MCRH/MCRL<-Dm/Dn).
- The interrupt handler saves the DSP accumulator {MDRQ,MCRH,MCRL} around the ISR
  via these ops (movm can't reach them). Added those registers to the core.
Also fixed alongside:
- **retf (0xDE)** was wrongly approximated as ret. It returns via the MDR-cached
  address (set by the paired `call`, which now caches it) and restores regs from
  below SP. Implemented per the sim.
- **movm groups** corrected to the exact sim layout (bit3 = {D0,D1,A0,A1,MDR,LIR,
  LAR}+dummy; bits0-2 = E-regs). MAME's disassembler group labels were wrong.
- **interrupt check made level-triggered** (was edge-only, so it missed the
  pending line if IE was set afterwards).

RESULT: the boot now runs STABLY with the tick timer enabled (was crashing into
low memory). Commits 99ee133 (DSP+retf+movm), e1730a0 (level-trigger).

### Remaining blocker (next)
The tick still doesn't fire because **PSW.IE is never set**: with the corrected
DSP/retf execution the boot now stays in the app-flash **panel-handshake init**
(~0x484A4Fxx, toggling panel GPIO 0x36008004) and never reaches the interrupt-
enable / scheduler start. Investigate whether that handshake needs the panel
sub-CPU to respond (the panel RX is queued but not delivered -- sio_rx_push does
not call intc_assert), or whether an unimplemented op/flow diverts it. Per the
video-path agent, the faithful task-switching vector is 0x4C03DE26 (not the
non-switching 0x4C03DDA0 currently used) with a 2-level INTC (0x34000200 +
per-group bitmask) -- likely needed once the tick fires.

## UPDATE (2026-07-05, cont.): boot now runs a power-on SELF-TEST loop

With the DSP/retf/interrupt fixes the boot executes correctly and now reaches (and
loops in) the **power-on self-test** at ~0x484A4FEA, which never enables interrupts
because a check fails and the whole test retries. Traced in detail:
- `0x4849FFE3` = **RAM test of 0x50000000** (write 0x5A5A5A5A/0xA5A5A5A5, read back
  via a scratch buffer, `setlb`/`lcs` loop of 0x80000 words = the full 4 MB work
  RAM). **PASSES** (returns d1=0). Confirms setlb/Lcc, the DSP context save, and
  the scratch round-trip all work.
- `0x484A005A` = a **byte read/checksum of 0x44000000** (`movbu (a0),d0` sweep) --
  0x44000000 is mapped as a plain RAM placeholder returning 0; if the test expects
  specific data (a ROM/device signature) it FAILS.
- `0x484A4F06` = a **panel handshake** (`bclr 0x20,(0x36008004)` + reads) -- the
  panel sub-CPU HLE does not respond, so this likely FAILS.
The caller (0x484A4FE3..) ORs the three results and, on non-zero, retries the whole
sequence forever -> IE never set -> no tick -> no UI.

NEXT: determine which of the two non-RAM checks fails (trace the combined error /
disassemble each check's pass condition), then satisfy it -- either map 0x44000000
with the expected content/device, or make the panel handshake respond (the panel
HLE + delivering panel RX via intc_assert). Only then does the boot enable
interrupts and start the scheduler. (Everything up to here -- CPU incl. AM33 DSP
ops, retf, movm, level-triggered interrupts -- is correct and committed.)

## UPDATE (2026-07-05, cont.2): INTERRUPTS NOW FIRE; call/ret SP-convention is next

Two coupled fixes (commit f2b6201) got the boot through the power-on self-test and
into live interrupts:
1. **0xCD (call disp16) now caches MDR** (return address), same as 0xDD already did
   and as the GDB sim does for both. The self-test caller uses 0xCD to invoke the
   RAM/checksum/panel subroutines, which return via `retf` (PC<-MDR). Without the
   cache, retf used a stale MDR and returned *into the call instruction* -> the
   self-test looped forever and IE was never set.
2. **retf (0xDE) rewritten to unwind like `ret`** (this core's call/ret use
   push/pop, frame = [return][regs][locals]); the previous version used the sim's
   absolute-offset layout, which does not match this core's push-based call.

With these, the self-test passes, PSW.IE is set, the timer IRQ fires, and the
library dispatcher runs the real tick ISR at 0x4C02BB05. **First live interrupts.**

### The remaining blocker: call/ret/calls/retf stack convention
The tick ISR is entered via `calls` (simple call, pushes only PC) and returns via
`ret [d2],0x14` (register-restoring). It reads a return PC of 0 and runs away,
because this core moves SP by (4 + regs_bytes + imm8) on call and the inverse on
ret, whereas the **hardware/sim move SP by imm8 ONLY**: `call` stores next_pc at
[SP] (no predecrement), writes the saved regs *below* without touching SP, then
`SP -= IMM8`; `ret`/`retf` do `SP += IMM8` and read PC at [SP] with regs at fixed
negative offsets. This is invisible for matched call/ret pairs (they cancel) but
corrupts `calls`<->`ret` and `retf` frames. FIX NEXT: reimplement call (0xCD/0xDD),
calls (F0/FA/FC forms), ret (0xDF) and retf (0xDE) to the imm8-total convention
(ref: sim_mn10300.igen call/ret/retf; IMM8 = 4(PC) + regs_bytes + locals). movm's
own store_regs/load_regs stay push/pop (movm really does push/pop).

## UPDATE (2026-07-05, cont.3): call/ret convention rewritten -> runaway fixed; PANEL is next

The call/calls/ret/rets/retf family was rewritten from the push/pop convention to
the exact AM33 imm8-total convention (commit a933090). Verified three ways: an
11-agent workflow that extracted the sim semantics (mn10300.igen 0xcd/0xdd/0xdf/
0xde + calls/rets) and checked both firmware frames balance; the empirical run
(runaway gone, all PCs valid, ~475%); and hand analysis. The convention:
- call: [SP]=next_pc (no predecrement); regs at [SP-4],[SP-8],... (no SP move);
  SP -= imm8; MDR = next_pc.  (imm8 = 4 + regs + locals; the ONLY SP move.)
- calls: [SP]=next_pc; MDR=next_pc; SP UNCHANGED.
- ret: SP += imm8; regs from [SP-4]...; PC = [SP].
- rets: PC = [SP]; SP UNCHANGED.
- retf: SP += imm8; PC = MDR; regs from [SP-4]...
Helpers store_regs_at/load_regs_at do the offset-based block; movm (0xCE/0xCF)
keeps the push/pop store_regs/load_regs (correct for movm).

Tick-ISR frame now balances exactly: dispatcher `calls` leaves [S0]=retaddr, ISR
prologue `movm [d2],(sp)`+`add -0x10,sp` puts D2 at S0-4 and SP at S0-0x14, and
`ret [d2],0x14` does SP+=0x14->S0, D2=[S0-4], PC=[S0]=retaddr. No more return-to-0.

### Next blocker: the panel-handshake self-test sub-check (0x484A4F06)
With registers now restored correctly, the power-on self-test no longer fluke-
passes (last tick it "passed" on corrupted regs, set IE, ran the tick ISR, and
ran away). It now correctly LOOPS in the panel handshake at 0x484A4F06 -- a
setlb/llt GPIO delay loop around 0x484A4F2D that strobes panel GPIO 0x36008004
and waits for the panel sub-CPU to answer. My panel HLE does not answer, so the
sub-test's error result is non-zero, the self-test retries forever, and PSW.IE is
(correctly) never set -> no tick -> no UI. NEXT: make the panel handshake succeed
(model the panel sub-CPU's expected response to the 0x484A4F06 protocol, likely
delivering panel RX via intc_assert on the panel group), OR determine what
0x484A4F06 checks and satisfy it. Then the self-test passes, IE is set, the tick
ISR runs (now correctly), and the scheduler/display should follow.

## UPDATE (2026-07-05, cont.4): SCHEDULER TICK IS LIVE (jiffy increments)

The "panel handshake" blocker turned out to be a boot taking a wrong turn into a
factory power-on diagnostic. Two coupled fixes (commits 48ae7a7, fcc06c6):
1. **btst imm16 (0xFA EC) was unimplemented** -> it never set the Z flag, so the
   strap test at program-flash 0x484A4FDA (`btst 0x8000,d0; beq 0x484A4FE3`) used a
   stale flag and always branched into the diagnostic at 0x484A4FE3.
2. **0x98070000 strap**: bit 15 selects normal boot (set) vs the diagnostic
   (clear). io_r returned 0, so bit 15 was clear. Now returns 0x8000.
Also implemented **lra (0xDA)** = branch to setlb loop top (was hitting 'default'
74k times) and the **(d16,sp) store forms (0xFA 90/91/92/93 + reg)**.

RESULT: the boot SKIPS the diagnostic, sets PSW.IE, the timer ISR at 0x4C02BB05
runs, and the scheduler's jiffy counter at 0x500D3C58 increments at ~1 kHz. The
RTOS heartbeat is alive; the boot runs library/scheduler code (0x4C00xxxx..) that
it never reached before. No unimplemented opcodes on this path; -validate clean.

### The factory diagnostic (0x484A4FE3), for reference
Reached only when 0x98070000 bit15 is clear. Runs a battery of sub-tests
(0x4849FFE3 RAM@0x50000000; 0x484A005A RAM@0x44000000 write/read 0x5A/0xA5 x256KB;
0x4849FC54/FCDF/FCF4, 0x484A00AA, 0x484A5A45 ...), OR-ing each result and bit-
banging the code out via 0x484A4F06 (strobes panel GPIO 0x36008004 bit5, LSB-first
pulse widths, ~96M instructions per call due to software delays). All sub-tests
PASS in emulation; it's just not the normal boot path.

### Next: the framebuffer is still black
Scheduler ticks but the 640x240 framebuffer at 0x500D4080 stays zero -> the
display/repaint task has not drawn. Investigate whether the display task is
scheduled yet, waits on a device (panel/LCD init), or draws elsewhere. This is the
last hop to pixels on the emulated LCD.

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

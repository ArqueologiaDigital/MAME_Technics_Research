# KN7000 / MN10300 (AM33) interrupt mechanism — RE notes for the MAME core

The firmware is a MILK RTOS that only advances its scheduler (and therefore only
draws the UI, and only delivers panel/MIDI receive bytes) when it takes a
periodic interrupt. The MN10300 MAME core currently **stubs** interrupts
(`check_irq`/`take_irq`/`execute_set_input` are empty). These notes capture what
the interrupt path looks like, reverse-engineered from the firmware, so the core
can implement it.

## The hardware vector (single maskable entry)

The program flash begins with a tiny vector area (the CPU fetches reset from the
flash base `0x48400000`):

```
0x48400000: jmp 0x4840FF7E      ; RESET vector
0x48400005: nop x5              ; padding
0x4840000A: jmp 0x484D77CF      ; MASKABLE-INTERRUPT vector  <-- offset +0x0A
0x4840000F: 0xFF...             ; empty
```

So there is a **single maskable-interrupt vector at flash+0x0A** that jumps to
the dispatcher **`0x484D77CF`** (like the MN10200's fixed `0x80008`). There is no
per-source hardware vector table (only these two `jmp`s are populated). NMI, if
separate, is TBD.

## The dispatcher `0x484D77CF`

```
484d77cf: movm [d2,d3], (sp)          ; software-save d2,d3 (hardware already saved PC+PSW)
484d77d1: add  -8, sp                 ; local frame
484d77d4: call 0x484d74d2             ; (helper)
484d77d9: mov  0xffff, d0
484d77df: movhu d0, (0x34001092)      ; interrupt-controller: write 0xFFFF
484d77e5: mov  0x82, d0
484d77e8: movbu d0, (0x34001082)      ; interrupt-controller: write 0x82
484d77ee: movhu (0x340010a2), d2      ; <-- READ INTERRUPT SOURCE / VECTOR into d2
484d77f4: clr  d0
484d77f5: movhu d0, (0x9000000e)      ; LCD controller housekeeping
484d77fb: bclr 0x04, (0x36008004)     ; GPIO strobes ...
484d7802: call 0x484101c9
484d7809: bclr 0x20, (0x36008004)
484d7810: bset 0x20, (0x36008004)     ; the panel/reset pulse pattern
484d7817: bclr 0x20, (0x36008004)
...
```

Key facts:
- The dispatcher **reads the interrupt-source register at `0x340010A2`** to learn
  which source fired, then routes to the specific handler. So the driver's
  interrupt-controller model must return the pending source id here.
- The interrupt-controller register block is **`0x34001080..0x340010A2`**
  (`0x34001082` byte, `0x34001092` halfword ack, `0x340010A2` source) — separate
  from the per-source **ICR array `0x34000148..0x34000178`** (enable/priority;
  panel ICR `0x34000168`, MIDI ICRs `0x34000148`/`0x34000150`).
- The dispatcher does LCD (`0x9000000E`) + panel GPIO (`0x36008004`) housekeeping,
  so the periodic interrupt it services is the **system tick / display refresh** —
  exactly the interrupt that must fire for the UI to come up. (The stuck boot loop
  at `0x484A4F09` toggles this same `0x36008004` bit while waiting for it.)

## Per-source ISRs (reached via the dispatcher)

The specific handlers (entered from the dispatcher, or possibly separate vectors —
TBD) all start with a `movm` register save and end with `rti` (`0xF0 0xFD`):

| Source | ISR | ICR |
|---|---|---|
| Panel SIO RX | `0x484ACC13` | `0x34000168` |
| MIDI-1 RX | `0x484B1E86` | `0x34000148` |
| MIDI-2 RX | `0x484B2037` | `0x34000150` |

Example entry (`0x484ACC13`): `movm [d2,d3],(sp)` ; `add -0xc,sp` ; then GPIO
handshake `bclr/bset` on `0x36008064/24/25`. So the **hardware** saves PC+PSW on
entry (the ISR only saves the GPRs it uses); `rti` restores PC+PSW.

## What the CPU core must implement

1. **`take_irq`** (when `PSW.IE` set and an enabled source is pending): push the
   return PC and PSW onto the stack `(sp)`, mask further interrupts (clear IE /
   raise the level field), and set PC to the maskable vector — either `0x4840000A`
   (let the firmware's `jmp` run) or directly `0x484D77CF`. Using `0x4840000A` is
   most faithful.
2. **`rti`** (`0xF0 0xFD`): pop PSW then PC from `(sp)`, restoring IE/level.
3. **`execute_set_input`**: latch the external/peripheral IRQ line(s) as pending.
4. **Driver side**: model the interrupt controller so `0x340010A2` returns the
   pending source id and `0x34001082/1092` acks clear it; add a periodic timer
   (the 0x32000000 block: `0x32000040`/`0x42` reload, `0x32000010` control) that
   raises the tick interrupt into the CPU. **Minimum to get the UI up:** just the
   one periodic tick interrupt driving `0x484D77CF`.

## OPEN QUESTION (must confirm before writing code)

The **exact byte layout the hardware pushes on entry** (and `rti` pops): AM33 PC
is 32-bit; PSW is 16-bit. Is the frame `[PSW:2][PC:4]`, `[PC:4][PSW:4]`, and does
SP decrement by 6 or 8? The MN10200 core pushes PC(24) then PSW(16) at `sp-6`
(`take_irq` in `mn10200.cpp`). Confirm the AM33 size/order from the AM33 manual or
by a sim experiment (install a tiny ISR, take one interrupt, inspect the stack and
the `rti` result) before implementing — a wrong frame corrupts PC/SP on return.

## References
- `notes/panel-serial-protocol.md` (SIO + ICR context), `notes/io-map.md`.
- Sibling template: `src/devices/cpu/mn10200/mn10200.cpp` `take_irq`/`check_irq`.
- `rti` decodes as `0xF0 0xFD` (mn103dasm.cpp).

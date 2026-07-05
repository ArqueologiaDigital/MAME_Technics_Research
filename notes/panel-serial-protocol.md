# KN7000 panel & MIDI serial protocol — implementation spec

Reverse-engineered from the firmware (ROM-grounded, instruction-cited) to drive
the MAME HLE of the panel sub-CPUs and the MIDI ports. The SIO ASIC has three
channels at 0x34000800 / 0x34000810 / 0x34000820 (+0x10 stride): channel 0 =
control panel, channels 1 & 2 = MIDI. See kn5000-docs Control Panel Protocol.

## SIO channel model (all three channels)

I now have complete, ROM-grounded evidence for the SIO model. Here is the report.

---

# KN7000 SIO ASIC — model spec for MAME (three channels @ 0x34000800 / 0x810 / 0x820, +0x10 stride)

All addresses below are CPU addresses (file offset = addr − 0x48400000). Every register/bit claim is tagged with the instruction that proves it. Items I could not prove from the ROM are marked **(inferred)**.

## 1. Register map (per channel, base + 0x10 stride)

Channel bases: **panel 0x34000800**, **MIDI-1 0x34000810**, **MIDI-2 0x34000820**.

| Offset | Width / access | Name | Proof |
|---|---|---|---|
| +0x00 | 16-bit `movhu` R/W | **CONFIG** | panel=0x0C84 `movhu d0,(0x34000800)` @0x484ABCC3; midi1=0x0085 @0x484B2796; midi2=0x1181 @0x484B27A6 |
| +0x04 | 8-bit `movbu` R/W | **CONTROL** | midi ctrl=0x00 `movbu d0,(0x34000814)` @0x484B279D and `(0x34000824)` @0x484B27AD; panel ctrl written dynamically @0x484ABCBA |
| +0x08 | 8-bit `movbu` W | **TX DATA** | writes to 0x34000818 / 0x34000828 / 0x34000808 (see §4) |
| +0x09 | 8-bit `movbu` R | **RX DATA** | `movbu (0x34000819),d0` @0x484B1E89; `(0x34000829)` @0x484B2043; panel `(0x34000809)` |
| +0x0C | 16-bit `movhu` R | **STATUS** | `movhu (0x3400081C),d0` @0x484B1E92; midi2 `(0x3400082C)`; panel `(0x3400080C)` @0x484AC74D |

Note the split at +0x08/+0x09: **TX and RX data are two different byte addresses in the same 16-bit word** (write +0x08 to transmit, read +0x09 to receive). The status word is read at +0x0C.

## 2. STATUS register bits (confirmed)

- **Bits 0–2 (mask 0x07) = receive error flags** (parity / framing / overrun — the three classic UART errors; exact assignment not distinguished by firmware). Tested identically on all three channels:
  - MIDI-1: `btst 0x07,d0` @0x484B1E98 → nonzero branches to error handler 0x484B312C.
  - MIDI-2: `btst 0x07,(0x3400082C)` @0x484B204C → error handler 0x484B313D.
  - Panel: `btst 0x07,d0` @0x484AC753 → sets error flag 0x50150A38.
- **Bit 4 (0x10) = RX data available (RxRDY)**. Used by MIDI-2's sysex drain loop: `btst 0x10,(0x3400082C); bne → read (0x34000829); loop` @0x484B2100 and @0x484B215B. When set, another received byte is waiting in +0x09.
- **TX-ready / TX-empty bit**: a bit almost certainly exists but the MIDI path never polls it — transmission is purely interrupt-driven (§4). **(inferred: present, position unknown.)**

## 3. CONFIG register bit meaning

Raw values written by firmware: **panel 0x0C84**, **MIDI-1 0x0085**, **MIDI-2 0x1181**. Interpretation is **(inferred)** from usage — the ROM sets them as opaque constants except for the panel direction field:

- **Bits 0–2 (mask 0x07) = mode / transfer-direction field.** Proven for the panel's synchronous half-duplex link, which rewrites these bits at runtime:
  - RX direction: `cfg |= 0x07` (established note; also clears/re-arms).
  - TX direction: `cfg = (cfg & 0xFFF8) | 0x04` @0x484ABF6F–0x484ABF7C, then `cfg |= 0x8000` (start bit 15) @0x484ABF88.
  - MIDI channels leave this field fixed (async, no direction toggling): midi1 low nibble 0x5, midi2 0x1.
- **Bit 7 (0x80) = channel/enable bit** — set in all three configs.
- **High byte = clock-source / baud-divisor select.** midi1 high byte = 0x00, midi2 high byte = 0x11 → **the two MIDI channels are NOT clocked identically.** The exact divisor cannot be derived from the ROM (depends on the ASIC input clock, which is not in the firmware). midi2's differing config suggests it may be a differently-clocked port (e.g. a computer/"TO HOST" link) rather than a second plain 31250-baud MIDI port — flag this for the modeler.
- Adjacent block writes in the panel init (`0x34001000=0x80`, `0x34001010=0x0A` @0x484ABCD1/0x484ABCD4) look like clock/prescaler setup for the SIO block **(inferred)**.

For an HLE it is enough to **latch CONFIG/CONTROL and ignore the encoded fields**; use MIDI framing (31250 bps, 8 data bits, no parity, 1 stop — 8N1) for the two MIDI channels. 8N1/no-parity is consistent with the firmware treating every byte as 8-bit (`movbu`) and never checking a parity result, only the error bits.

## 4. MIDI receive path (both channels — standard MIDI confirmed)

RX ISRs: **MIDI-1 @0x484B1E86**, **MIDI-2 @0x484B2037**. Both:
1. Read the byte from RXD (+0x09), save on stack.
2. Read STATUS (+0x0C); if `& 0x07` → error handler + IRQ ack; else parse.

Byte classification (MIDI-1 @0x484B1ED0, MIDI-2 @0x484B209B) — this is exactly the MIDI wire protocol:

| Test | Class | Handler (MIDI-1 / MIDI-2) |
|---|---|---|
| `byte & 0x80 == 0` | **DATA** (0x00–0x7F) | 0x484B2586 / 0x484B25BD |
| `0x80 ≤ byte ≤ 0xF7` | **STATUS** (channel-voice 0x80–0xEF + system-common 0xF0–0xF7) | 0x484B24B4 / 0x484B251D |
| `byte > 0xF7` (`cmp 0xF7; bgt`) | **REALTIME** (0xF8–0xFF) | 0x484B23F4 / 0x484B2454 |

- **Sysex tracking (MIDI-2 only, @0x484B20C5–0x484B20E8):** status byte 0xF0 sets in-progress flag `0x50150ADE = 1`; 0xF7 clears it. While the flag is set, the ISR drains RXD in a tight loop gated by STATUS bit 0x10 (`btst 0x10,(0x3400082C)` @0x484B2100/215B) to keep up with the sysex burst.
- **How received bytes reach the app:** the DATA handler routes the byte through a thunk in the 0x4C00_0000 bank selectable by a mode flag — MIDI-1: `0x4C024A0D` vs `0x4C0249C5` on `0x5006BFD2` bit0 (@0x484B258D); MIDI-2: on `0x5006BFD3` bit7 (@0x484B25C4). These enqueue into the application's MIDI-input buffer / running-status parser.

## 5. MIDI transmit path (interrupt-driven)

TX-empty ISR, **MIDI-1 entry @0x484B1F29** (MIDI-2 parallel):
- Checks pending real-time flags at `0x5006BFD0` (`btst 0xF8`). Sends by priority, **one byte per interrupt**, each `movbu d0,(0x34000818)`:
  - bit 0x08 → **0xF8** Timing Clock (@0x484B1F78)
  - bit 0x40 → **0xFA** Start (@0x484B1FB3)
  - bit 0x10 → **0xFB** Continue (@0x484B1FD0)
  - bit 0x20 → **0xFC** Stop
  - bit 0x80 → **0xFE** Active Sensing (@0x484B1F96)
- Otherwise pulls the next queued application byte via `0x4C024AEE` / `0x4C024A66`. If it returns −1 (queue empty) it **disables the TX interrupt** (`call 0x4C03DD3F, arg 7` @0x484B1F47) and returns; otherwise writes the byte to **0x34000818** (@0x484B200B).
- **Re-arm/ack** via the TX interrupt-control reg 0x3400014C: read, `& 0xFF00`, `| 0x01`, write @0x484B200F–0x484B2022 — so each successful send re-triggers the ISR until the queue drains.
- MIDI-2 TX register = **0x34000828** (same structure; TX ICR **0x34000154** *inferred* by stride).
- A helper @0x484B284E broadcasts **0xFE** (Active Sensing) to **both** 0x34000818 and 0x34000828.

Panel TX (@0x484ABF50) is different — synchronous half-duplex: it flips the CONFIG direction field (§3) before shifting bytes to 0x34000808. It does **not** use the async MIDI TX scheme.

## 6. Interrupt registers (mn10300 interrupt controller — NOT part of the SIO device)

Each channel drives separate RX and TX request lines into the CPU's group interrupt-control registers (GxICR), which the ISRs ack with the pattern *read → `& 0xFF00` → `| 0x01` → write-back*:

| Channel | RX ICR | TX ICR | Aux |
|---|---|---|---|
| MIDI-1 | 0x34000148 | 0x3400014C | 0x34000144 |
| MIDI-2 | 0x34000150 | 0x34000154 *(inferred)* | — |
| Panel | 0x34000168 | — | — |

These belong to the interrupt controller, not the SIO ASIC. In MAME the SIO device should expose **separate RX and TX interrupt-callback lines** per channel; the interrupt controller/ack logic is modeled separately.

## 7. What a MAME SIO device must implement

Per channel (base + 0x10 stride), a `device_serial_interface` with:

- **CONFIG (+0x00, 16-bit R/W):** latch value; no field decode needed for HLE.
- **CONTROL (+0x04, 8-bit R/W):** latch (MIDI writes 0x00); treat as reset/enable.
- **TXD (+0x08, 8-bit W):** writing a byte starts transmission; assert the channel's **TX interrupt** when the holding register goes empty (and TX int is enabled).
- **RXD (+0x09, 8-bit R):** returns the last received byte; reading clears RxRDY (STATUS bit 4).
- **STATUS (+0x0C, 16-bit R):** implement **bit 4 (0x10) = RxRDY** and **bits 0–2 = RX error flags** (drive 0 in normal HLE); expose a TX-ready bit if convenient.

**Interrupt behaviour:**
- **RX interrupt** fires when a byte is fully received (RxRDY set). ISR reads +0x09, checks +0x0C bits 0–2, parses, then acks its GxICR.
- **TX interrupt** fires when the transmit holding register empties and TX int is enabled. Firmware sends exactly one byte per interrupt and re-arms via the TX ICR; when its software queue is empty it disables the TX interrupt.

**Wiring the two MIDI channels:** attach a MAME `midi_port` to each of MIDI-1 (0x34000810) and MIDI-2 (0x34000820): feed `midi_port` RX into RXD and raise the RX IRQ; send TXD to `midi_port` TX and raise the TX IRQ when ready; run 31250 bps 8N1. Because midi1 (cfg 0x0085) and midi2 (cfg 0x1181) are configured differently, verify against hardware whether MIDI-2 is a standard 31250 MIDI port or a differently-clocked host/serial port before hard-wiring its baud.
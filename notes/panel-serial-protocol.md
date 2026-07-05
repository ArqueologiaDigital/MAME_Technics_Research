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
## Switch-report frame (panel sub-CPU -> main CPU) — what the HLE EMITS

I have fully traced the panel-switch wire protocol from the serial byte through to the button event. Here is the report.

---

# KN7000 Panel Sub-CPU → Main CPU: Switch-Report Frame Format

All addresses verified in `kn7000_program.rom`. This is the format an HLE must **emit** on the panel serial link `0x34000800`; the main-CPU decoder `0x484AD111` is what consumes it.

## 0. Frame skeleton (verified)

The frame decoder `0x484AD111` (body `0x484AD116`) pulls bytes from the 92-byte RX ring at base `a3=0x5006BDB4`, tail `0x5006BDB0`, head `0x5006BDB2` (wrap at `0x5C`=92). Key finding:

**The first byte is BOTH the header AND the first data byte (the switch ADDR byte).** At `0x484AD161-167` the decoder reads `ring[tail]` **without advancing tail**, validates it, extracts the type, then jumps to the per-type handler — which re-reads the *same* byte and only then advances. So there is no separate header byte.

Decoder gate: needs ≥2 buffered bytes (`0x484AD15A cmp 2,d3`) before decoding — consistent with 2-byte frames.

## (a) HEADER / first byte format + the 8 TYPEs

First byte bit layout `[b7 b6 | b5 b4 b3 | b2 b1 b0]`:

| bits | field | notes |
|---|---|---|
| 7,6 | **BANK / framing** | Validator `0x484ACFF9` requires `(b & 0xC0) ∈ {00, 11}`. `01`/`10` are rejected → error nibble `0x10` written to `0x5006BE91` and the frame aborted (`0x484AD175`). So there are **2 wire banks, not 4**. |
| 5,4,3 | **TYPE (0–7)** | Extracted at `0x484AD18D`: `type = (byte & 0x38) >> 3`. |
| 2,1,0 | low sub-address | segment/switch address bits |

Type dispatch (`0x484AD18D`, verified):

| TYPE | handler | bytes consumed | meaning |
|---|---|---|---|
| 0 `000` | `0x484AD1C6` | **2** `[ADDR, DATA]` | momentary switch scan, bank segments **0–7** |
| 1 `001` | `0x484AD1C6` | **2** `[ADDR, DATA]` | momentary switch scan, bank segments **8–15** (bit3 of ADDR = high seg bit) |
| 2 `010` | `0x484AD25F` | **2** `[ADDR, DATA]` | latched / rotary control update (data wheel, sliders, pedal) → dispatch `0x484AD680` |
| 3 `011` | `0x484AD2EB` | **2** | status/handshake: skips 2 bytes, sets flag bit3 (`0x08`) at `0x5006BDA4` |
| 4 `100` | `0x484AD2EB` | **2** | same as 3 |
| 5 `101` | `0x484AD2EB` | **2** | same as 3 |
| 6 `110` | `0x484AD331` | **variable** | length-checked multi-item batch; iterates dispatch `0x484AD680` + enqueue |
| 7 `111` | `0x484AD331` | **variable** | same as 6 |
| invalid | — | discards 1 byte, resyncs (`jmp 0x484AD11C`) | |

Types 0 and 1 are the **momentary panel push-buttons** (START/STOP etc.). Note that TYPE is *embedded in the ADDR byte's bits 3–5*, so it also functions as the high part of the segment address (type0 = segs 0–7, type1 = segs 8–15).

## (b) SWITCH data-byte bit layout + press/release

A momentary-switch frame is exactly **2 bytes: `[ADDR, DATA]`**.

**ADDR byte** (= the header byte). Handler `0x484AD1C6` uses it as:
- shadow-table select: `(ADDR & 0xC0)==0 ? tbl@0x5006BE50 : tbl@0x5006BE80` (`0x484AD237`), i.e. bank bits 6–7.
- shadow index: `ADDR & 0x0F` (`0x484AD244`) → per-segment slot (16 per bank).
- For the downstream event queue, normalized at `0x484ADA1B`: `idx = ((ADDR&0xC0)>>1) | (ADDR&0x1F)` → lookup `0x486135A0` → logical segment (bit 5 is dropped).

**DATA byte** = 8-bit switch bitmask, **bit N = switch N in that segment**. Polarity is **active-high on the wire: bit = 1 ⇒ pressed** (verified end-to-end, see below).

**Edge detection** (`0x484AD249-24D`): main CPU keeps a per-(bank,segment) shadow byte; `CHANGED = DATA XOR old_shadow`; then `shadow = DATA`. The triplet `[ADDR, DATA, CHANGED]` is enqueued into cooked FIFO `0x5006BCF8` (enqueue `0x484AD519`). Raw bytes are also latched to `0x5006BDA6/DA7/DA8`.

**Press/release resolution** (event generator `0x484A0CB5`, verified):
- `switch# = normSeg*8 + firstSetBit(CHANGED)` (`0x484A0D1A`; bit-scan `0x484A0C99`).
- class = `tbl@0x4860C9F4[switch#*2]`.
- `pressed = (DATA & CHANGED) != 0` for that bit → emitter `0x484A0B3E(index, 1)`; the release branch `0x484A0DC4` (DATA bit now 0) calls `0x484A0B3E(index, 0)`. This is the ground truth for polarity: **DATA bit 1 = press, 0 = release.**

Recommendation for the HLE: change **one switch per frame** (a single bit in DATA differing from the previous DATA for that segment). Multi-bit changes are only partially handled (the generator scans the lowest changed bit).

## (c) The `0x484AD680` dispatch and its 32-entry table (TYPE 2 / continuous controls — NOT momentary keys)

Dispatch `0x484AD680`: `index = ((byte1 & 0xC0)>>3) | (byte1 & 0x07)` where `byte1`=ADDR, `d0`=DATA passed to the handler. group = `(ADDR&0xC0)>>6` (only 0/3 valid), sub = `ADDR&7`.

Table `0x48613108` (dumped, 32 × 4 bytes) is **sparse** — only 6 live entries, everything else = default `0x484AD7A7`:

| idx | (group,sub) | handler | action |
|---|---|---|---|
| 0 | (0,0) | `0x484AD6B0` | latch DATA→`0x5006BEA0`, remap via `0x48613188`, diff vs `0x5006BEA9` |
| 7 | (0,7) | `0x484AD6A0` | latch DATA→`0x5006BE9F` and `0x5006BEA8` |
| 24 | (3,0) | `0x484AD740` | latch→`0x5006BEA3`, `asr 1`, remap `0x48613488`, diff vs `0x5006BEAC` |
| 25 | (3,1) | `0x484AD6DE` | `not`+latch→`0x5006BEA1`, remap `0x48613288`, diff vs `0x5006BEAA` |
| 26 | (3,2) | `0x484AD772` | `not`+latch→`0x5006BEA6` |
| 27 | (3,3) | `0x484AD70F` | `not`+latch→`0x5006BEA2`, remap `0x48613388`, diff vs `0x5006BEAB` |

These handlers latch a **value** and return `0xFFFF` when unchanged (no event) — they are for **continuously-valued controls** (data dial, sliders, pedal), not push-buttons. This corrects the working note that called `0x484AD680` "the switch dispatch": the momentary keys do **not** go through it; they go through the TYPE 0/1 shadow-XOR path in (b).

## (d) Checksum / terminator

**None.** No checksum byte, no terminator/sync byte, no length byte for types 0–5 (length is implicit from TYPE: 2 bytes). The only integrity check is the header framing rule `bit6 == bit7` (`0x484ACFF9`); a violation sets error nibble `0x10` at `0x5006BE91` and aborts the frame.

## Physical (group, SEG, SW) → wire bytes, and the START/STOP example

Wire ADDR ↔ logical segment (from normalization table `0x486135A0`, dumped):
- bank `11` (bits6-7=11), subaddr 0–0x0B → logical segments `0x00–0x0B`; subaddr 0x10–0x13 → `0x16–0x19`.
- bank `00`, subaddr 0–9 → logical segments `0x0C–0x15`; subaddr 0x10 → `0x1A`, 0x17 → `0x20`.

Formula for a momentary key: `ADDR = (bank<<6, bit7=bit6) | subaddr`, `DATA = 1<<SW` when only that key is down.

**START/STOP = CPL SEG0 SW4** → logical **normSeg 0, bit 4**. normSeg 0 is reached from table index `0x60` = bank `11`, subaddr `0`, so:

```
ADDR = 0b11 000 000 = 0xC0   (type=0, bank=11, seg=0)
DATA (SW4 pressed)  = 0x10
```

- **Press START/STOP:  C0 10**
- **Release START/STOP: C0 00**

(2-byte frames, no checksum.)

Support/confidence: the *mechanics* (2-byte frame, ADDR=header, `DATA bit=1⇒press`, XOR edge-detect) are fully verified. The literal `ADDR=0xC0` rests on `CPL SEG0` = logical **normSeg 0**, whose bit 4 carries switch-class `0xF0` in table `0x4860C9F4[0x04]` — the composite **rhythm-transport** handler `0x484A0D88` (emits the transport group events 3,4,5,6 on press / release), which is exactly what START/STOP drives. The one datum not in the main ROM is the physical-scanline→wire-ADDR translation, which lives in the CPL sub-CPU's own firmware / the schematic. If CPL instead maps to bank `00`, the same key would be `ADDR=0x00, DATA=0x10` (frames `00 10` / `00 00`); the DATA byte (`0x10`) is unaffected.

## Reference addresses for the HLE

- Decoder entry `0x484AD111` / body `0x484AD116`; header validator `0x484ACFF9`; type dispatch `0x484AD18D`.
- Momentary handler (type0/1) `0x484AD1C6`; shadow tables `0x5006BE50` (bank00), `0x5006BE80` (bank11); XOR edge-detect `0x484AD249`.
- Cooked FIFO `0x5006BCF8`; enqueue `0x484AD519`; dequeue `0x484AD53D`; consumer `0x484AD87F` / `0x484A0C4C`.
- ADDR normalization `0x484ADA1B` + table `0x486135A0`; event records `0x5006BEB4` (count `0x5006BEF0`).
- Event generator `0x484A0CB5`; bit-scan `0x484A0C99`; switch-class table `0x4860C9F4` (2 bytes/switch, `switch# = normSeg*8+bit`); emitter `0x484A0B3E` → `0x484B1780`.
- Latched-control dispatch `0x484AD680` + table `0x48613108`.

Service manual `/home/fsanches/compartilhado/KN7000/service_manual/technics_sx-kn7000_keyboard.pdf` confirms the physical PCBs **CPL / CPC / CPR** and the **SD panel** (CPSD) (§7.6, pp. ~555–606); it is print-only/copy-disabled so the per-segment scan matrix must be read from its schematic images (not text-extractable), or from each sub-CPU's firmware, to enumerate every button.
## LED-command frame (main CPU -> panel sub-CPU) — what the HLE DECODES

I have everything verified from the ROM. Here is the complete decode.

---

# KN7000 Panel LED Command Frame — Full Decode

All addresses/values below are read directly from `kn7000_program.rom` (CPU base `0x48400000`). Nothing here is guessed unless explicitly marked *(inferred)*.

## Overview of the path

```
SetHoldLed/SetDialLed/SetOtherPartLed/SetModeLed
      │  d0 = LED-index (1..0x13)
      ▼
SetLedByIndex  ON=0x484B1BCB (table 0x4861518C)  /  OFF=0x484B1CA1 (table 0x486151D8)
      │  jumps to per-LED fn, value d0 = 1(on)/0(off)
      ▼
per-LED fn (0x484B0C3F …)  →  bankA writer (0x484B0BFA…) or bankB writer (0x484B0C1B…)
      │  sets/clears ONE bit in the LED shadow register array. Does NOT transmit.
      ▼   (bank chosen by flag 0x5006BE94 via getter 0x484ABAFD)
diff-flush task  0x484B165D (bankA) / 0x484B16A4 (bankB)
      │  for reg=0..0x1F: if shadow[reg] != last_sent[reg] → send + update mirror
      ▼
frame builder 0x484B1780 → 0x484B170C (bankA) / 0x484B1746 (bankB)
      │  pushes TWO bytes: [ ADDR_TABLE[reg] ][ shadow[reg] ]
      ▼
byte-FIFO 0x5006BD8C  (push prim 0x484AD52B → 0x484AD5B0)
      ▼  drained into 60-byte SIO ring @0x5006BE14 (0x484AD45F)
SIO TX ISR → 0x34000808  → panel sub-CPUs
```

Key point for the HLE: **the LED write and the serial transmit are decoupled.** The `SetLedByIndex` calls only flip bits in a RAM shadow; a periodic diff-flush compares the shadow to a "last transmitted" mirror and emits a 2-byte `[address][data]` frame only for registers whose value changed.

---

## (a) LED shadow buffer — address and layout

The shadow lives at **`0x50150A3C`**. There are **two banks**, selected at runtime by flag byte **`0x5006BE94`** (0 → bank A, non-0 → bank B; getter `0x484ABAFD`). Each bank is a 32-byte *current* array immediately followed by a 32-byte *last-transmitted mirror*:

| region | address | size | meaning |
|---|---|---|---|
| Bank A current | `0x50150A3C` | 32 B | live LED register values (reg 0..0x1F) |
| Bank A mirror  | `0x50150A5C` | 32 B | last value transmitted (for diff) |
| Bank B current | `0x50150A7C` | 32 B | live LED register values |
| Bank B mirror  | `0x50150A9C` | 32 B | last value transmitted |

`register_index = byte_address − 0x50150A3C` (bank A) / `− 0x50150A7C` (bank B). Bank B is bank A + `0x40`.

Each `SetLedByIndex` index writes a fixed **(register, bit)**. Verified per-index (bank A addresses; bank B identical bit at +0x40):

| LED idx | writer | shadow byte | reg | bit | named as |
|---|---|---|---|---|---|
| 1  | 0x484B0BFA | 0x50150A3C | 0  | 5 | **Hold** (SetHoldLed) |
| 2  | 0x484B0C5F | 0x50150A3F | 3  | 4 | |
| 3  | 0x484B1054 | 0x50150A41 | 5  | 4 | |
| 4  | 0x484B0CC2 | 0x50150A4E | 18 | 1 | **Dial** (SetDialLed) |
| 5  | 0x484B0D25 | 0x50150A3F | 3  | 5 | **OtherPart** (SetOtherPartLed) |
| 6  | 0x484B0D8A | 0x50150A47 | 11 | 1 | |
| 7  | 0x484B0DEB | 0x50150A47 | 11 | 0 | |
| 8  | 0x484B0E49 | 0x50150A46 | 10 | 0 | |
| 9  | 0x484B0EAB | 0x50150A40 | 4  | 4 | |
| 10 | 0x484B0F0E | 0x50150A46 | 10 | 1 | |
| 11 | 0x484B0FF3 | 0x50150A44 | 8  | 2 | |
| 12 | 0x484B0F90 | 0x50150A45 | 9  | 4 | |
| 13 | 0x484B10B9 | 0x50150A44 | 8  | 1 | |
| 14 | 0x484B0F71 | 0x50150A45 | 9  | 1 | |
| 19 | 0x484B111E | 0x50150A44 | 8  | 0 | |
| 15 | — | *(none)* | — | — | direct GPIO `bset 0x40,(0x9CC00008)` — **not** panel serial |
| 16 | — | *(none)* | — | — | direct GPIO `bset 0x80,(0x9CC00008)` — **not** panel serial |
| 17,18 | — | — | — | — | **no-op** (table entry → bare `ret`) |

The write idiom (e.g. Hold, 0x484B0BFA): `d2 = shadow[0x3C]; d2 &= ~(1<<5); d2 |= (value&1)<<5; shadow[0x3C]=d2`. So `SetLedByIndex(N, on)` = set that bit; `SetLedByIndex(N, off)` (entry 0x484B1CA1) = clear it. SetModeLed additionally maps its argument through table `0x4859E364`, storing the "currently lit" mode index at `0x50021FD4`, and turns the old one off before the new one on.

Jump tables: ON `0x4861518C` (19 words), OFF `0x486151D8` (19 words), both indexed `(index−1)*4`, bounds `1..0x13`.

---

## (b) TX frame format — exact bytes on `0x34000808`

The frame builder `0x484B170C` (bank A) does, for a changed register `reg` with value `val`:

```
if reg >= 0x15: drop
addr = ADDR_TABLE_A[reg]          ; table @ 0x48615058
if val == 0xFF: drop              ; 0xFF is a reserved sentinel, never a real value
if reg <= 3: <protocol handshake 0x484ABB98>   ; regs with addr C0..C3 only
push_byte(addr)                   ; → FIFO 0x5006BD8C (0x484AD52B)
push_byte(val)
```

**On the wire, one LED update = exactly two bytes: `[ ADDR_TABLE[reg] ] [ register value ]`.**

Address tables (raw bytes, indexed by register):

```
ADDR_TABLE_A @0x48615058 (21):  C0 C1 C2 C3 C4 C5 C6 C7 00 01 02 03 04 05 08 09 0A 0B 0C 0D FF
ADDR_TABLE_B @0x48615070 (20):  C0 C1 C2 C3 C4 C8 C9 01 02 03 04 05 06 09 0A 0B 0C 0D 0E FF
```

The trailing `FF` and any register whose value is `0xFF` are suppressed (never transmitted).

### Worked example — "Hold LED ON"
- `SetHoldLed(1)` → `SetLedByIndex` ON index 1 → 0x484B0BFA sets **bit 5 of register 0** (`0x50150A3C`).
- Register 0 now differs from its mirror → flush emits: `addr = ADDR_TABLE_A[0] = 0xC0`, `data = shadow[0]`.
- If register 0 was otherwise 0: on-wire bytes = **`C0 20`** (0x20 = bit5). Hold LED OFF = **`C0 00`**.

Because several LEDs share a register, the data byte carries **all** LED bits of that register, e.g. register 3 (`addr C3`) holds LED-idx2 at bit4 and OtherPart at bit5; register 8 (`addr 00`) holds idx19/13/11 at bits 0/1/2.

There are also two transmit engines that emit these same logical bytes:
- **Interrupt/ring path (runtime):** FIFO `0x5006BD8C` → 60-byte ring `0x5006BE14` (read idx `0x5006BE10`, write idx `0x5006BE12`, capacity `0x3C`) → SIO ISR to `0x34000808`.
- **Synchronous bit-bang path (boot/handshake, `0x484ABEBF→0x484ABF50`):** sends the two bytes `0x5006BE14`/`0x5006BE15` directly to `0x34000808`, wrapped in GPIO board-select strobes `0x36008004/24/25/64`. Same 2-byte payload.

For an HLE that only watches `0x34000808`, treat the stream as a sequence of `[address][data]` pairs where any byte with bit7-ish high value in the C0..C9 / 00..0E set is an **address**, and the following byte is the **8-bit LED latch value** for that register.

---

## (c) LED grouping per sub-CPU

Registers split into two address groups (from the tables), which correspond to different panel sub-CPUs / boards:

| address range | registers (bankA) | notes |
|---|---|---|
| **`0xC0`–`0xC7`** | reg 0–7 | high bits set; registers 0–3 additionally run the handshake `0x484ABB98` (0x484ACEA5/0x484AD011 — half-duplex turnaround/state, *inferred* board-select, not extra LED payload) |
| **`0x00`–`0x0D`** | reg 8–19 | plain register writes |

The two **banks** (flag `0x5006BE94`) are two different wiring maps of the *same* logical LEDs — the address tables differ (bank A uses `C5 C6 C7 … 00 08`, bank B uses `C8 C9 … 06 0E`). This is consistent with the shared KN5000/KN7000 codebase: the flag selects which hardware variant's LED-register→sub-CPU address mapping to use. Which physical sub-CPU (CPL/CPC/CPR/CPSD) owns the `0xCx` vs `0x0x` address space is *inferred* to be encoded in the address byte's upper bits (the panel RX decoder routes on `(b&0xC0)>>3 | (b&0x07)` per the established facts), but is not needed to reproduce correct LED lighting.

### What the HLE must implement
1. Maintain 32 register latches per active bank (base semantics = `0x50150A3C`).
2. Parse the `0x34000808` byte stream as `[addr][data]` pairs; map `addr` back through `ADDR_TABLE_A/B` to a register index; store `data` as that register's 8 LED bits.
3. Light physical LEDs from the (register,bit) map in table (a) — e.g. Hold = reg0/bit5 (addr `C0`), Dial = reg18/bit1 (addr `0C`), OtherPart = reg3/bit5 (addr `C3`).
4. Ignore `addr == 0xFF` and `data == 0xFF`. LED indices 15/16 are display GPIO (`0x9CC00008`), not panel-serial, and 17/18 are unused.
## Boot handshake — live findings (2026-07-05, MAME HLE bring-up)

Traced with an interleaved event log (panel SIO ops + GxICR[0x1A] ops, chronological):

- The boot ping loop (sync sender `0x484AC59A`, caller region `0x484ABBA5..`) per
  iteration: library helper `0x4C03DD5F/6A` reads + CLEARS `GxICR[0x1A]` (the
  panel-RX group, ICR 0x34000168); config direction set to TX (`cfg&0xFFF8|0x04`);
  one byte 0x00 transmitted (`cfg|=0x8000` start at 0x484AC5E2, byte written at
  0x484AC5E9); then a wait, then retry. 33 pings, then the error screen.
- **CONFIG bit15 = transfer START; the firmware polls the register until the
  hardware self-clears it** (loop at 0x484AC5A3..: read, write, read, write ...).
  The HLE now completes transfers instantly (bit15 self-clears in sio_w).
- The firmware **never reads SIO STATUS (+0xC) or RX data (+0x9) during the
  handshake** (verified with uncapped logging: reads are ONLY reg0). So the wait
  is NOT SIO-status polling.
- After the ping it programs **0x34000280** (read-modify-write: `& 0xFF3F | 0x80`
  at 0x484AC5FE..60B) and sets flag byte `0x5006BE92=1`. 0x34000280 is an
  unmodeled second INTC-level register (our intc map returns 0 / drops writes).
  The handshake wait is gated by whatever 0x34000280 controls -- likely the
  second-level enable/mask for the panel-RX group's interrupt delivery (compare
  0x34000200 = the level-6 group register).
- When our provisional replies set GxICR[0x1A] REQUEST, the firmware acked once
  (read 0x0111 -> write 0x0101 at 0x484AC627/634) -- so it DOES look at the
  group -- but the ISR/decoder never consumed the RX bytes.

HLE state: sio_rx_push now asserts the channel's group (panel 0x1A / MIDI 0x12,
0x14); panel replies (TYPE-3 sync `18 00`) are provisional. NEXT: model
0x34000280 (semantics from the firmware's usage: bits 6-7 cleared, bit 7? set
-- dump more read/write sites), find what completes the per-ping wait (an
interrupt through the quick vector? a flag set by the panel-RX ISR at
0x5006BDA4 bit3?), and check whether GxICR[0x1A] LEVEL/ENABLE are set by
0x4C03DCE9/DCF2 (observed write 0x0100 = ENABLE once).

## 0x34000280 + GxICR semantics + the transfer-complete interrupt (2026-07-05, RESOLVED)

Commit 28ecc1d. Three model corrections, all firmware-evidence-based:

1. **0x34000280 is a latched 2-bit-per-source control-field register.** All 8 real
   code sites (ROM byte-pattern sweep; the other 0x340002xx hits are data): early
   boot 0x48401EAF/EB9 + 0x48404D73/D80; panel init 0x484ABCE3 (`|0xC0`); ping
   path 0x484AC600 (`&0xFF3F|0x80`) and 0x484AC6F1 (`|0xC0`); loader 0x484D725F
   (write); sound path 0x4854BB6A (`|0x0C00`, paired with the 0x98050004 stream
   port) + 0x4854BCC0. Pure RMWs, never tested -> HLE = latch.
2. **GxICR write semantics:** high byte (ENABLE/LEVEL) stored; DETECT bits 0-3
   write-1-to-clear LIMITED to mem_mask-covered bits (the firmware's control-byte
   `movbu` writes, mask 0xFF00, must not ack DETECT); REQUEST derived from DETECT.
   With plain COMBINE_DATA the enable write destroyed pending requests.
3. **Group 0x1A = panel sync-transfer COMPLETE** (not RX-ready). Registered
   dispatch: table1[0x50380A6C + 2*(group*4)] -> slot 8; table2[0x50380B64 +
   2*slot] -> ISR 0x484AC5F1 = the ping sender's own state machine (one step per
   completed transfer, either direction). (Tick sanity: slot 2 -> 0x4C02BB05.)
   sio_w asserts 0x1A on each CONFIG-bit15 completion; panel replies (TYPE-3 sync
   18 00) queue in m_panel_resp and deliver one byte per RX-direction transfer.

STATUS: group 0x1A wins arbitration (0x0111, quick vector) and the state machine
DISPATCHES (verified entry/exit) -- first time ever. It runs ONCE: the enable
window (library enable-helper path 0x4C03DCE9/DCF2, one write of ctl=0x01) is not
re-armed. NEXT: trace how the state machine re-arms the enable between transfers
(the library enable/disable helpers around 0x4C03DCB0-0x4C03DD6A and their arg ->
group mapping: arg 5/6 used by the sender; find what arg maps to group 0x1A and
who calls enable per ping), then what the machine does at each step (it should
turn the link around to RX and clock in the 2-byte reply).

## THE COMPLETE BOOT HANDSHAKE CHAIN (2026-07-05, 6-agent workflow, fully verified)

0x34000280 = **EXTMD** (MN103E external-interrupt trigger-mode register): eight
2-bit fields, field n = trigger mode of external IRQ pin XIRQn = INTC group
0x17+n. bits1:0<->0x17, bits3:2<->0x18, bits7:6<->**0x1A = the panel ATN pin**,
bits9:8<->0x1B, bits11:10<->0x1C. Values: 11b idle/default, 10b = armed for the
opposite edge. Pure config latch (never bit-tested). io_init writes 0xFFFF at
0x484D725D.

Interrupt registration (library registrar 0x4C03DB26; struct {valid,isr,group,
icr,level,sub}; called from panel-init vtable entry 0x484ABB06 via 0x484ABBEC):
slot 4 -> 0x484AC5F1 (group 0x1A ATN), slot 5 -> 0x484AC70E (group 0x11, TX state
machine, jump table 0x48613034 indexed by state 0x5006BDA0), slot 6 -> 0x484AC74A
(group 0x10, RX: status check + state dispatch; state-8 handler 0x484ACC13 reads
0x34000809 -> ring 0x5006BDB4, head 0x5006BDB2). Index table 0x50380A6C entries
at (group*8+sub*2); ISR table 0x50380B64 at slot*4. Tick = slot 1 (level 6).

THE CHAIN (one ping transaction, retried 10x from 0x484ABBB5):
1. 0x484AC2A8: clears result 0x5006BDA5, resets ring head/tail, sets flag bit0
   of 0x5006BDA4, calls kick 0x484AC523(cmd,arg) -- commands: 0x20 00 ping CPL,
   0xE0 00 ping CPR, 0x1F DA / 0x1F 1A init.
2. TX side: each SIO0 byte completion raises group 0x11 -> state machine emits
   [one/two 0x00 sync bytes + 2 command bytes] (states 1..7).
3. Panel answers with an ATN PULSE (2 edges) on group 0x1A:
   - pass 1 (0x5006BE92==0): EXTMD bits7:6 11b->10b (re-arm opposite edge),
     be92=1, ack GxICR[0x1A].
   - pass 2 (be92!=0): SIO CONFIG |= 0x07 then |= 0x4000 (RX enable), enable
     group 0x10 (lib enable arg 6), disable group 0x11 (arg 5), state:=8,
     EXTMD bits7:6 back to 11b, be92=0, ack.
4. Panel sends reply bytes on SIO0: one group-0x10 interrupt per byte; state-8
   handler stores into the ring, bumps head, sets 0x5006BDA1=2.
5. SUCCESS: head 0x5006BDB2 != 0 within ~7 ticks (counter 0x50151BFC; the delay
   0x484AC102 has NO timeout -- the tick must run); result nibble == 9 (bit0 =
   0x20 answered, bit3 = 0xE0 answered).

HLE (commit 2ed2d34): command detection in sio_tx_byte (first byte 0x20/0xE0/
0x1F) queues a TYPE-3 reply + schedules ATN edge 1 (one-shot timer, 60us —
NEVER assert synchronously from ISR-context register writes: pass 1 runs with
IE clear and acks on exit, wiping sync asserts); EXTMD 11b->10b write schedules
edge 2; CONFIG bit14 + queued reply -> deliver one byte per group-0x10 assert
(timer-chained).

STILL FAILING -- open questions for the next session:
(a) Does the 2-byte command ever reach sio_tx_byte? Earlier tracing saw ONLY
    0x00 bytes on the wire (the sync sender transmits ring slots 0x5006BE14/15
    which were never filled by the FIFO 0x5006BD8C drain 0x484AD45F). If the
    kick path enqueues but the drain never runs, the command never goes out and
    nothing should reply. Trace 0x484AC523 -> FIFO -> drain -> ring -> sender.
(b) Does state 0x5006BDA0 ever leave 0? (Probe showed 0 throughout earlier.)
    Who sets state:=1 (the kick?) and what advances 1..7?
(c) Sound-path unblock (from the workflow): the OTHER hot loop spins at
    0x4854BC59 waiting for **0x9805000E to read back the value written**
    (d1|0x80). A readback latch at 0x9805000E unblocks the sound init.
(d) GxICR[0x17] REQUEST poll after the probe at 0x48404D48 (presence flag
    0x500066CD) -- another device-presence gate to model eventually.

## Handshake bring-up part 2 (2026-07-05, commit caea343)

- **GPIO 0x36008084 bit0 = panel READY/presence line.** State-1 handler tests it
  (btst 0x01 @0x484AC80C) right after incrementing the state; if clear it aborts
  the whole transaction back to state 0 (state:=0, 0x5006BDA1:=0). This was THE
  silent killer of every attempt. HLE: mapped high (lr16 -> 0x0001).
- **Both TX write orders exist**: sync sender = arm(bit15) then data; state-2
  payload = data then arm. HLE completes on whichever comes second, always via a
  deferred one-shot (an ISR-context TX + synchronous assert = wiped by the exit
  ack; confirmed empirically).
- **Progress**: the wire now carries [00, 00, 1F] and the machine reaches state 3
  (0x484AC923). It parks: state 3 does NOT transmit the second payload byte
  (0xDA). OPEN: what advances state 3 -- disassemble 0x484AC923 (does it wait for
  a completion my model doesn't generate, a GPIO edge, a timed gap, or does it
  expect the 0x1A ATN mid-command?). Also verify state-2's bit15 write actually
  arrived after the data write (the pending->complete path).
- Sound: 0x9805000E readback latch added (init loop 0x4854BC59 unblocked).

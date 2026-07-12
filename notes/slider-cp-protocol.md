# Volume sliders / pots are delivered via the CP serial protocol (TYPE 2 frames) — NOT a raw ADC

**2026-07-12.** Correcting the earlier "find the ADC read address" hypothesis: the 4 volume sliders
(MAIN/APC-SEQ/MIC/LINE-IN), the data wheel, pitch-bend/mod and the expression pedal are **digitised by a
panel sub-CPU and delivered to the main CPU as TYPE 2 frames on the control-panel serial link**
(0x34000800), which the driver ALREADY models (`panel_queue` / the RX ring). So making a slider functional =
emit the right TYPE 2 frame when the ioport adjuster changes — no ADC modelling, no CPU-core change.

## The mechanism (see notes/panel-serial-protocol.md §c)
- Panel→main frames are 2 bytes `[ADDR, DATA]`. ADDR bit layout `[b7 b6 = bank | b5 b4 b3 = TYPE | b2 b1 b0 = sub]`.
- **TYPE 2 (`010`) = "latched / rotary control update (data wheel, sliders, pedal)"**, handler chain
  `0x484AD25F` → dispatch **`0x484AD680`** (32-entry table @ **0x48613108**).
- Dispatch index = `((ADDR & 0xC0) >> 3) | (ADDR & 0x07)`; only bank 00 and 11 are valid.

## The 6 real continuous controls (rest of the table = no-op handler 0x484AD7A7)
| wire ADDR byte (TYPE2) | dispatch idx | handler | latch RAM | scaling | remap table |
|---|---|---|---|---|---|
| **0x10** (bank00 sub0) | 0  | 0x484AD6B0 | 0x5006BEA0 | —              | 0x48613188 |
| **0x17** (bank00 sub7) | 7  | 0x484AD6A0 | 0x5006BE9F+0x5006BEA8 | — (raw, no remap) | — |
| **0xD0** (bank11 sub0) | 24 | 0x484AD740 | 0x5006BEA3 | asr 1 (÷2)     | 0x48613488 |
| **0xD1** (bank11 sub1) | 25 | 0x484AD6DE | 0x5006BEA1 | not (invert)   | 0x48613288 |
| **0xD2** (bank11 sub2) | 26 | 0x484AD772 | 0x5006BEA6 | not + asr 1    | 0x48613508 |
| **0xD3** (bank11 sub3) | 27 | 0x484AD70F | 0x5006BEA2 | not (invert)   | 0x48613388 |

(The "wire ADDR byte" is what a frame carries: `(bank<<6) | (2<<3) | sub`. The dispatch strips the TYPE
bits, so its index only sees bank+sub.) Each handler latches DATA (scaled) to its RAM byte, remaps through a
256-entry taper table, and diffs against a shadow (0x5006BEA8..0x5006BEAC) to emit a change event only when
the value moves. The **`0xD0-D3` group (÷2 / invert scaling) are the 4 analog VOLUME pots**; `0x10`/`0x17`
(bank00) are the data-wheel / pitch-mod family.

## NEXT — identify which ADDR is APC/SEQ VOLUME, then wire the driver
Identification is the only open piece. Two ways:
1. **Lua live-probe (no rebuild!):** the frame decoder `0x484AD111` reads the 92-byte RX ring at base
   **0x5006BDB4**, tail **0x5006BDB0**, head **0x5006BDB2** (wrap 0x5C). Inject a frame from Lua by writing
   `[header, DATA]` into `ring[head]`/`ring[head+1]` and advancing head by 2 (mod 92). Sweep DATA for each
   candidate header (0xD0/D1/D2/D3) and watch the effect.
   To know which is APC/SEQ: MUTE UP/DOWN 9 edits the SAME setting (sliders.txt). Press MUTE UP 9 (SEG09
   0x10) N times and tap RAM writes to find the APC/Seq-volume setting byte (the press-count method), then
   inject each 0xDx header and see which one moves that same byte.
2. **Driver implementation (once ADDR known):** on VOL_APCSEQ (PORT_ADJUSTER) change, emit `[0xDx, value]`
   through the existing panel frame path (panel_queue / the RX ring). Scale the 0..100 adjuster to the pot's
   raw 8-bit range, honouring the handler's invert/÷2 so the remap lands on the intended volume. Also light
   `apcseq_vol_led` when the slider position matches the current value (the soft-takeover the LED wants).
   The same pattern makes MAIN/MIC/LINE-IN functional too (their ADDRs come out of the same probe).

Verified data (all from kn7000_program.rom @ base 0x48400000): dispatch table dump + handler disasm above.

## ★ MECHANISM CONFIRMED LIVE (2026-07-12, /tmp/ringprobe.lua, no rebuild)
Injected a frame `[0xD0, 0xAA]` by writing it into the RX ring (RING[head]=0xD0, RING[head+1]=0xAA,
then head=(head+2)%92 at 0x5006BDB2) at t=8 on the home screen. Result: **0x5006BEA3 became 0xAA** — the
0xD0 handler (0x484AD740) ran and latched the raw DATA exactly as disassembled. So: (1) the RX-ring stuffing
DOES drive the decoder task (it polls head!=tail); (2) the ADDR→handler map is correct; (3) sliders are
injectable end-to-end from Lua. head/tail are u8 offsets (0..91); the ring had head=tail=4 idle at boot.

NEXT is now purely: (a) ID which of 0xD0-D3 is APC/SEQ (press MUTE UP 9 = SEG09 0x10, find the setting byte
it moves, then inject each 0xDx and see which moves the same byte); (b) implement in the driver: on
VOL_APCSEQ change, emit `[0xDx, scaled_value]` through panel_queue (or, minimally, the same RX-ring write).
The probe already proves (b) will work.

### Identification attempt 1 (2026-07-12, /tmp/idprobe.lua) — CONFOUNDED by the demo screensaver
Injected each of 0xD0-D3 (low+high swing) on the "home" screen and snapshotted. But the KN7000 auto-starts
its DEMO slideshow after a few seconds of no input, so by t=9 the LCD already showed demo graphics (not the
PMEM home screen), and all snapshots diff against that moving demo -> unreadable. Consecutive-diff signals
were noisy (D0 large, D2 small localized @ (505,218)-(537,268), D1/D3 lo->hi = 0) but not trustworthy under
the demo. FIX for the next attempt: keep the machine active (tap EXIT / a harmless button every ~1 s to
suppress the demo) OR navigate to a stable settings screen, THEN inject; better still, use the RAM
correlation (MUTE UP 9 finds the APC/Seq setting byte; inject each 0xDx to see which moves it) which is
demo-immune. Injection itself is proven (ring-probe PASS above).

# FINDINGS — the factory test-jig port (CN106 / CN110) on the MN10300 KN models

**2026-10-08.** Question (Felipe): could the test-jig port be used to run custom code or dump ROMs?
**Answer: not with the stock firmware, on any model.** No firmware ever touches the jig's chip
select, and the jig-presence line is never read. The port is a plain 8-bit slave bus that becomes a
fast data port only for code that already runs by another route (on the KN6000/6500, the XAPR
board route of `FINDINGS-expansion-buses-and-code-exec.md`). One lead stays open on the KN2400/2600.

Sources: service manuals (rendered pages; crops in `test-jig-crops/`, page numbers below), static RE
of the KN6000, KN6500, KN7000 and KN2400 images (CRCs checked against the upstream driver), and a
MAME check of the boot gate. Scripts: `~/compartilhado/research-scratch/pr16220-rd/jig/`
(`build_images.py`, `scan_consts.py`, `cs6_refs.py`, `strap_bits.py`, `jig_probe.lua`,
`jig_window_tap.lua`, `render_crops.sh`, README). Labels: [V] seen on a rendered page / in
disassembly / in a MAME run; [I] inferred.

## Hardware

| model | connector | bus | chip select | JIGU.ON |
|---|---|---|---|---|
| KN6000 / KN6500 | **CN106**, 19 pins, no cable (KN6500 p.140) | D0-D7 = CPU D16-D23 unbuffered, A1-A2, RE, WR (=WE2) | JIGU.CS = '138 IC1 Y3 on CS6 → **0x98030000-0x9803FFFF** (KN6000 p.28, KN6500 p.80) | IC109 1A2 → D30 = **bit 14 of the input word at 0x98070000** (KN6500 p.90→p.89 [V]; KN6000 same circuit [I]) |
| KN7000 | **CN106**, 11 pins, no cable (p.160) | none: pins 4-7 are the SD card's SPI lines (p.104, p.112) | decoder Y3 drawn **open** (p.100) — no jig chip select | IC106 1A2 → D30 = bit 14 (p.104→p.106) |
| KN2400 / KN2600 | **CN110**, same pin order as the KN7000's CN106 | pins 5-7 JIGU.SD/CLK/SI → **serial port 3 of tone generator IC301** (SCK31/SI3/SO3, 2400sch2.pdf p.3) | KN2400: Y3; KN2600: Y3 a stub | IC109 1A1 → D31 = **bit 15** |

KN6000/6500 CN106 pins: 1-2 E, 3 +3.3D, 4 +5D, 5-12 D0-D7, 13-14 A1-A2, 15 RE, 16 WR, 17 CS,
18 SNS (power sense → NMI), 19 JIGU.ON. Crops: `kn6500_p90_cn106.png`, `kn6000_p39_jiguon_run.png`,
`kn6500_p89_ic109_top.png`, `kn6000_p38_ic109_wide.png`, `kn6500_p140_cn104_cn106.png`.

No jig connector carries bus request/grant, reset, the MMODE/BMODE boot pins (tied to ground through
R30/R31, KN7000 p.100, `kn7000_p100_mmode_bmode.png`) or the debug pins. A jig is a bus slave; the
only things it could force are electrical (pulling SNS for a power-fail NMI, or fighting the
unbuffered D16-D23 lines on the KN6000/6500) [I].

**Bit 15 of 0x98070000 is the factory self-test gate.** KN6000/6500: the SW pin of a separate test
header, **CN104** (E/SW/LED/+3.3D, no cable; LED = SELF.LED). KN2400/2600: JIGU.ON itself. KN7000:
IC106 1A1 has only a pull-up, so the bit always reads 1 (`kn7000_p106_ic106_1a1.png`).

## Firmware

- **Zero references to 0x9803xxxx** in any image, by byte scan and in full disassembly; no register
  is ever loaded with the bare 0x98000000 base, so nothing reaches it by base + offset either.
  Positive control, same scan (`test-jig-crops/cs6_refs.txt`): FDC 0x9802 = 13/13/32/32 operands,
  0x98070000 = 9/9/14/27 (KN6000/KN6500/KN7000/KN2400).
- **Bit 14 (JIGU.ON on the KN6000/6500/7000) is never tested** by any read of 0x98070000
  (`test-jig-crops/strap_bits.txt`).
- **Bit 15 is tested once, at boot**, by a routine shared by all four images: `movhu (0x98070000),d0 ;
  bset 0x20` ×3 on the GPIO ports ; `btst 0x8000,d0 ; beq selftest`. Gates: KN6000 0x484505AF
  (caller 0x4847AD6E), KN6500 0x4845071F (0x4847AF02), KN7000 0x484A4FBF (0x484D7272), KN2400
  0x48663543 (0x487050BC). Low → factory self-test: LCD controller init, RAM tests (0x5A/0xA5),
  ROM checksums (the KN6000's include goldens for its **undumped table ROMs: 0x504EEB12 and
  0x2C7CD2D4**), a custom-flash write/verify at 0x96806000, the LCD register and VRAM tests, a
  4-pulse LED code on GPIO 0x36008004 bit 5 after each step, then a pass/fail loop. **No input is
  read after the gate; there is no peek, poke, transfer or jump.**
- Factory two-key power-on tests also exist (KN6000 dispatcher 0x48450B15): D3+D4 → mode 0xF5,
  E3+E4 0xF6, F3+F4 0xF7, G3+G4 0xF8, A3+A4 0xF9, B3+B4 0xFA (C#3+D#3+C#4 = the documented service
  mode 0xFC); one screen reads "Please check by the LED of test port (PANEL CPU : OK=Lit SHORT,
  NO=Lit LONG)". No service-manual text mentions a jig (KN6000 pp.21-24, KN6500 pp.20-24, KN7000
  pp.27-34 rendered; the same search finds "JIGU" on the schematic pages).

### MAME check (`jig_probe.lua`, upstream driver + #16220 v3, 20 s, 2026-10-08) [V]

| run | JIGU.CS window | FDC reads | 0x98070000 reads | 0x36008004 writes | PC at 20 s |
|---|---|---|---|---|---|
| kn6000, normal | 0 | 6,384 | 3,409 | 361 | 0x4C3F734C (normal running) |
| kn6000, bit 15 forced low | 0 | 0 | **2** | **59,650** (LED blinking) | 0x48450AF7 (self-test pass/fail loop region 0x48450645/0x48450ADD) |
| kn6000, bit 14 forced low | 0 | 6,384 | 3,409 | 361 | identical to normal |
| kn7000, normal | 0 | 7,758 | 23,420 | 311 | 0x4C014F3E |
| kn7000, bit 15 forced low | 0 | 0 | 3 | 45 | 0x484A4F46 — boot diverted, but not in the predicted final loop 0x484A506B/0x484A5DCC; not followed further |

Plus `jig_window_tap.lua`: 0 accesses to 0x98030000-0x9803FFFF in 20 s of normal boot on all five
sets; the same tap on 0x98020000 (FDC) sees 15,615 on the KN6000.

## What a homebrew jig could do

| goal | KN6000/6500 | KN7000 | KN2400/2600 |
|---|---|---|---|
| run code, stock firmware | no | no | no |
| dump program/table/custom flash | no | no | no |
| dump wave ROMs | only as a fast output port for code that already runs | no | **open**: via the tone generator's serial port 3 |
| upload code | only as an input port for code that already runs | no | open |

- **KN6000/6500 jig, as a data port:** 3.3 V logic; latch D0-D7 on the rising edge of WR while CS
  is low; drive D0-D7 only while CS and RE are both low; 4 registers (data, status, control). With
  board code running from CN105 (XAPR), this is a much faster dump channel than MIDI — e.g. for the
  undumped table ROMs IC13/IC14 and wave ROMs.
- **KN7000:** at most an SD-card emulator, the same path as the card slot. Grounding IC106 pin 47
  would run the self-test [I].
- **KN2400/2600:** the wave memory (IC302/IC303, "64M FLASHROM") sits behind tone generator IC301,
  whose serial port 3 is wired to the jig; the KN2400 firmware never drives that port
  (0x9805000C/E unused). Its protocol is unknown and needs real hardware and a logic analyser.

## Corrections

- `fdc-architecture.md` addendum 11 called 0x484A4FBA **dead code**: it is entered past its
  prologue at 0x484A4FBF from 0x484D7272 (itself called from 0x48447F7B), and its bit-15 path is
  the **factory self-test**, not FDC init (addendum 10): 0x9CC000xx is the LCD controller,
  0x9CE00000 its video RAM, 0x484A506B the self-test's final loop. Correction appended there.
- The upstream `strap_r` comment could name bit 15 (self-test gate), bit 14 (JIGU.ON, unread) and,
  on the KN2400/2600, bit 5 (a bit-banged serial input).

## Open

1. The KN6000's JIGU.ON wire end-to-end (1-bit scan). 2. What enables IC109 on the KN2400/2600
(no Y7). 3. Which tone generator owns the SD pins on KN7000 p.112. 4. What the KN2400 tone
generator's serial port 3 accepts. 5. Whether a factory-only firmware used 0x98030000. 6. Which CPU
pin SELF.LED is (inferred GPIO 0x36008004 bit 5). 7. Where the KN7000's forced self-test parks.

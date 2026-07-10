# F.3 — runtime capture of the 21065L IOP programming (ground truth)

Captured 2026-07-10 by temporarily logging every `iop65l_r/w` on the running DSP
(DRC, ~6 emulated seconds, DSP host stub ON). This is the actual sequence the
recovered kernel writes to the SHARC's IOP registers — cross-check for the F.3
research. IOP register names per the Technical Reference `def21065L.h` (Appendix E).

## Distinct IOP writes (reg = value)

System / SDRAM / wait:
- `0x02 = 0x200D0001`  — WAIT (external-memory wait states) / SDRAM timing
- `0x2E = 0x8852A05B`  — SDRAM control (DMISC/SDCTL)
- `0x20 = 0x000003A2`  — (SYSCON-ish config; confirm)

DMA channel registers (chain pointers = CP; TCBs at 0x4309..0x4341):
- `0x33 = 0x4331`   `0x3B = 0x4341`   `0x53 = 0x4311`   `0x5B = 0x4321`
- `0x63 = 0x4329`   `0x6B = 0x4339`   `0x73 = 0x4309`   `0x7B = 0x4319`
- (0x08-0x0F, 0x28-0x3C, 0x58-0x5C written mostly 0; `0x0A = 0x00069D40` — a DMA
  count? note 0x69D40 == top of the external delay buffers B3=0x656F0 + L3=0x4650)

SPORT0 (0xE0-0xEF) and SPORT1 (0xF0-0xFF):
- `0xE0 = 0x013CB173`  STCTL0 (SPORT0 transmit control)
- `0xE1 = 0x013C3173`  SRCTL0 (SPORT0 receive control)
- `0xF0 = 0x013CB173`  STCTL1 (SPORT1 transmit control)
- `0xF1 = 0x013C3173`  SRCTL1 (SPORT1 receive control)
- `0xE8-0xEC = 0`, `0xF8-0xFC = 0`  — multichannel selectors / compand = 0 (NOT multichannel)

## Load-bearing observations for F.3

1. **TDIV/RDIV (0xE4-0xE7, 0xF4-0xF7) are NEVER written.** => the SPORTs run off an
   EXTERNAL serial clock + frame sync (the codec drives them). The audio SAMPLE RATE
   is therefore a HARDWARE property, NOT derivable from firmware. The driver's 44.1 kHz
   IRQ0 tick is a stand-in for the codec frame sync; its true value comes from the KN7000
   codec hardware, not the DSP program. (Keep 44.1 kHz unless the service manual pins it.)

2. **No writes to TX/RX DATA registers** (0xE2/0xE3/0xF2/0xF3, nor the B buffers
   0xEE/0xEF/0xFE/0xFF). => audio is moved ENTIRELY BY DMA (autonomous), not PIO. The
   main loop processes DM buffers that the SPORT RX DMA fills and the TX DMA drains.

3. **The main loop hammers reg 0x2F** (444,511 writes, alternating 0/1) — its per-frame
   flag store `DM(0x2F)=R13` / `DM(0x2F)=0`. 0x2F is in the IOP window (0x0-0xFF); the
   kernel uses it as scratch. The stub accepting it (no-op) does not break the loop.

4. Both SPORTs have BOTH transmit and receive control programmed (0xE0+0xE1, 0xF0+0xF1).
   => a full-duplex codec interface on each; determine which carries input (ADC/TG->DSP)
   vs output (DSP->DAC) from the STCTL/SRCTL bit decode + the DMA channel assignments.

## Open for F.3 (being researched)

- The DMA TCBs live at DM 0x4309..0x4341 — BELOW internal SRAM (0x8000) and above IOP
  (0xFF). Is 0x4300 a short-word alias of internal SRAM, a separate internal region, or
  external? Must be mapped so the kernel can build TCBs and the modeled DMA can read the
  II (buffer address) fields. (Currently unmapped => TCB reads/writes are lost, harmless
  only because the DMA isn't modeled yet.)
- Decode STCTL0/SRCTL0 = 0x013CB173/0x013C3173 bit-by-bit => serial word length (sample
  width), DMA-enable (SDEN), TX/RX enable, clock/frame-sync source.
- Which DMA channels (from 0x33/0x53/0x5B/0x63/0x6B/0x73/0x7B/0x3B) are the SPORT RX/TX
  channels, and the II/buffer address each TCB points to = the audio in/out buffers.

## KN7000 hardware audio path (from the SERVICE MANUAL, service_manual/*.pdf)

- **IC306 = S21065LKS240** = the ADSP-21065L effects DSP (confirmed part number).
- **IC307 / IC308 = 1M FAST SRAM x16 each** (labelled "2M SRAM"): the DSP's EXTERNAL
  memory (the 0x20000+ region; delay lines for reverb/echo). NOTE: it's static RAM, not
  SDRAM — but the kernel still writes an "SDRAM control" IOP reg (0x2E) to configure the
  external-memory interface. Map as plain RAM (already done, 0x20000-0xFFFFF).
- **DAC = PCM1716ET** (TI stereo audio DAC, up to 96 kHz): the DSP's SPORT TX output feeds
  this -> analog out. So the SHARC SPORT TX is the WET/processed audio to the speakers.
- Oscillators on the board: 50 MHz (likely the SHARC input clock — driver currently uses
  60 MHz; the 21065L PLLs up, so exact input matters only for SPORT/timer timing, not the
  DRC), plus 17.73 / 24 / 14.32 / 4 MHz. No oscillator label is an unambiguous audio master
  clock; sample rate is most likely 44.1 or 48 kHz (PCM1716 supports both) but is NOT pinned
  by the manual text extraction — a "FSYNC" signal exists (frame sync). Keep the 44.1 kHz
  IRQ0 assumption; revisit if the wave-ROM/service-mode audio spec pins it.
- Implication for MAME routing: TG (IC201/IC205) digital audio -> SHARC SPORT RX (dry in);
  SHARC SPORT TX -> PCM1716 DAC -> speakers (wet out). This matches the F.3 topology.

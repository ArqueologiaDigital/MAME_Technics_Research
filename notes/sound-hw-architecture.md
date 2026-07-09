> Recon report produced 2026-07-09 by the sound-subsystem planning sweep (5 parallel research agents).
> Companion to notes/sound-subsystem-plan.md. Verify page/line citations before building on them.

# KN7000 Service Manual — Sound Subsystem Mining Report

Source: `/home/fsanches/compartilhado/KN7000/service_manual/technics_sx-kn7000_keyboard.pdf` (160 pages; PDF page number == printed page number, verified by footers). Methods: full `pdftotext -layout` extraction + visual reads of pages 28–36, 43–44, 79–80, 100–103, 108–119, 120–123.

---

## 1. PAGE INVENTORY (sound-relevant pages)

| Page | Content |
|---|---|
| 2–6 | Specifications: "SOUND GENERATOR: PCM", "MAX. POLYPHONY: 128 NOTES", part effects "SUSTAIN, DIGITAL EFFECT, SOUND DSP", global effects "REVERB, CHORUS, MULTI, MIC" |
| 27–28 | §8 Service Diagnostic Function: entry = hold **C#3 + D#3 + C#4** keys and power on (Fig.20/21). 12 test pages |
| 28–29 | §8.1 ROM device test (Fig.21/22): PROGRAM ROM IC16/IC17, RHYTHM ROM IC18 (IC20), CUSTOM FLASH IC21, PICTURE ROM IC19 |
| 29 | §8.2 RAM device test (Fig.23): WORK RAM IC12/IC13, STATIC RAM IC23, LCD V-RAM IC104, FAST S-RAM IC14/IC15 |
| 29–30 | §8.3 Other device test (Fig.24): **PANEL CPU (IC1): CPL/CPR; DSP: IC306; DSP RAM: IC307, IC308**; FDC IC103 |
| 34 | §8.9 WAVE ROM test (Fig.30): "MAIN TG BANK 0-15 ROM: IC203, IC204 / SUB TG BANK 0-15 ROM: IC207, IC208" |
| 34–35 | §8.10 SOUND SYSTEM test (Fig.31/32): 6 sine-wave check modes (full text in §5 below) |
| 35–36 | §8.11 SD test incl. "Audio test" (SD-audio playback path) |
| 36–37 | §8.12 WAVE EXPANSION BOARD test (Fig.34): slots EXP1–EXP4, boards SY-EW01/02/03/04 |
| 37–40 | §9 FLASH ROM servicing: IC16/IC17 = PROGRAM ROM (rewritten from PROGRAM DISKs), IC18 = CUSTOM DATA ROM (defaulted by loading "CTMINI" from INITIAL DATA DISK) |
| 41 | §11.1: in diagnostic mode "The WAVE ROM output will then be output as a sine wave to facilitate the servicing check" |
| 43–44 | §12 MEASURING CONDITION: scope check points ①RESET ②**TG CLOCK** (sine, T≈0.06 µs ⇒ ~16.9 MHz) ③④⑤ = DAC serial pins on IC311 (sheet-6 callouts). Conditions: diag mode, SOUND=BRASS, volume MAX, C4 key |
| 47–59 | Parts list `<MAIN P.C.B.>` (all sound ICs on pp.54–55) |
| 59–66 | `<FAJ P.C.B.>` parts (IC501–514 = NJM4558L op-amps ×14; power regulators AN6913, KIA7815/7915) |
| 67–68 | `<ASUB P.C.B.>` (speaker-amp sub board, IC820 TC7WU04FU) `<INV>`, `<ACP>` |
| 79 | **BLOCK 1/2 DIAGRAM (1/2)**: CPU + memory + DSP + TGs + wave ROMs (the key architecture drawing) |
| 80 | BLOCK 1/2 DIAGRAM (2/2): SD/USB audio subsystem, DACs/ADCs, MKB keybed boards |
| 81 | BLOCK 2/2 (1/2): CPR/CPL/CPC panels, MAIN/LINE-IN/APC volume pots (VR1103/VR1105/VR1102, PWM) |
| 82 | BLOCK 2/2 (2/2): FAJ jacks + EQ + amps + speakers (SP-L/R 12 cm 8Ω, TW-L/R 6.5 cm, WF 14 cm) + power |
| 83–94 | PCB layout views (p.83 = MAIN component/foil sides) |
| 100–103 | Sheets 1–2 = MAIN 1/5: CPU MN103002A, chip-select decoders IC1/IC2/IC3, memory array, IC25 sound-control latch |
| 104–107 | Sheets 3–4 = MAIN 2/5: FDC, LCD controller (drives SD.PLY/SD.ACC/... transport nets), MIDI/USB |
| 108–109 | **Sheet 5 = MAIN 3/5 (1/2): DSP IC306 + SDRAMs IC307/IC308 + CPU↔DSP host bridge** |
| 110–111 | **Sheet 6 = MAIN 3/5 (2/2): DACs IC310/IC311, ADC IC309, analog mix switches, CN301/CN302 to FAJ** |
| 112–113 | **Sheet 7 = MAIN 4/5 (1/2): IC201 MASTER TONE GENERATOR + IC203/IC204 + expansion connectors** |
| 114–115 | **Sheet 8 = MAIN 4/5 (2/2): IC205 SUB TONE GENERATOR + IC207/IC208 + expansion connectors** |
| 116–117 | Sheet 9 = MAIN 5/5 (1/2): SD u-COM IC401, SD decoder IC402, EEPROM IC403, 4M flash IC414 |
| 118–119 | Sheet 10 = MAIN 5/5 (2/2): USB CPU IC407/IC408, USB DAC IC406, record ADC IC410 |
| 120–123 | Sheets 11–12 = FAJ: MIC/LINE/AUX/SUB/MAIN jacks, headphone amp, EQ, speaker drive, PMUT mute |
| 124–139 | ACP power (124–125), ASUB (126–127), CPL/CPC/CPR (128–133), JACK/BEND/INV (134–135), MKB1–3 (136–137), HP (138–139) |
| 140–159 | Same schematics reprinted for A4 (duplicates; e.g., DSP sheet again at 144, TGs at 146–147) |

---

## 2. ARCHITECTURE (as drawn, block diagram p.79/80 + sheets)

**Digital chain (all on MAIN P.C.B. — every IC below is in the `<MAIN P.C.B.>` parts list, pp.51–59):**

```
MN103002A CPU (IC4, D0-D31/A0-A25)
 ├─ D16-31 + A1-A4, TGCS,  RE/WE2, IORST ──► IC201 MASTER TONE GENERATOR LSI (C1BB00000709)
 ├─ D16-31 + A1-A4, TGCS2, RE/WE2, IORST ──► IC205 SUB TONE GENERATOR LSI  (C1BB00000709)
 │        ◄── TGS.INT1, TGS.INT2 (TG interrupt lines, sheet 1 p.100 / sheet 7 p.112)
 ├─ D16-31 via IC302/IC304 ('245) + IC303 ('574 addr latch), ADSPCS/ADSPAD/RE/WE2/DSP.RDV/DSP.RST
 │                                        ──► IC306 ADSP-21065L DSP (S21065LKS240)
 └─ EXP.CS0-3 + A1-A19/D16-31 ──► wave expansion connectors (SY-EW01..04)

IC205 (sub TG) ── SUB0-SUB3 + BCKSUB/LRCKSUB (4 serial lines) ──► IC201 (master TG)
IC201 ◄──► IC306 serial: SD00/SD01/SD02(/SD03), SDI, BCK, LRCK, CKOUT, MTMG, BCKX/LRCKX,
                          SDIE(0-3)/SDOE(0-3)  (sheets 5 & 7 edge stubs)
IC306 ◄── IC307 + IC308 KM416S1120DT 16M SDRAM ×2 (32-bit wide DSP memory)
```

**Wave ROMs (private TG buses, never on CPU bus):**
- IC201: IC203 C3CBQD000002 on AWAY0-22 + IC204 C3CBQD000001 on AWAX0-22, shared data AWD0-15 (sheet 7, p.112)
- IC205: IC207 C3CBQD000004 on BWAY0-22 + IC208 C3CBQD000003 on BWAX0-22, shared data BWD0-15 (sheet 8, p.114)
- All four are "128M ROM" (128 Mbit each = 64 MB total)

**Digital→analog (sheet 6, p.110):**
- **IC311 (C0FBBK000025, "D/A CONVERTER")** — the main stereo DAC: serial pins LRCK/DATA/BCK/SCK0/SCK1, differential current outputs IOUTL±/IOUTR±, mode pins MD0/MD1/CS driven by nets **DAC.MDI/DAC.MC/DAC.ML** (a CPU-writable latch, see below). Output → I/V + filters IC313/IC314/IC315/IC316 (M5218AFP) → **MIXOUTL/MIXOUTR** → CN302 → FAJ CN501.
- **IC310 PCM69BU** dual 18-bit DAC (pins WDCK/SYSCK/BCK/DA-L/DA-R) → IC312 → SUBOUT path.
- **IC309 PCM1800E** stereo ADC digitizes MIC/LINE-IN (from FAJ via CN302: MICIN, LINEINL/R) — mic/line into the digital domain (DSP mic effects).
- **SD/USB playback bypass**: SD-audio (IC402 ARO/ALO) and USB DAC **IC406** ("USB DA.L/USB DA.R", sheet 10 p.118) are switched into the analog mix by Q307/Q308 (B1CFDC000004) and Q309 (net SD.PLY) — this path never touches TG or DSP.
- **Record path**: nets MAINL/MAINR (final mix) → op-amps IC409 → **IC410 PCM1800E ADC** → USB CPU / SD subsystem (sheet 10, p.118).

**Analog out (FAJ board, sheets 11–12, pp.120–123):** all op-amps NJM4558L. MIC jack JK501 (+preamp), LINE IN JK502/503, AUX IN JK504/505, SUB OUT JK506/507, MAIN OUT JK508/509, headphone amp (IC509/IC511 + CN504 → HP board), multi-band "EQUALIZING" op-amp bank (IC502-505/508/510-514) → discrete FET/transistor power stages → speakers via CN607/CN608: SP-L/SP-R 12 cm 8Ω, TW-L/TW-R 6.5 cm 8Ω, WF 14 cm 8Ω (block p.82). PMUT = mute control from CPU; SPSW = speaker switch. ASUB board (CN820/821, sheet 14 p.126) is in the speaker-drive path.

**SD subsystem (sheet 9, p.116):** IC401 MN102H60KTA "SD u-COM", IC402 MN67737DB1 "SD DECORDER" (SD-Audio decoder w/ built-in DAC outputs ARO/ALO), IC403 "(EEPROM)" S29L331AFSTB = Seiko 3-wire serial EEPROM (CS/SK/DI/DO), IC414 C3FBKD000162 "4M FLASH" (u-COM program, SDA1-18/SDD0-15). Transport keys driven from LCD-controller GPIO nets SD.SRT/STP/FWD/BWD/VUP/VDN/ACC/PLY (block p.79, sheet 9 stubs). Serial link stubs SD.SI/SD.SO/SD.CLK appear both on sheet 9 and next to IC201 pins SI3/SCK31 on sheet 7 (p.112). Net **11.2896M** (11.2896 MHz = 256×44.1 kHz) runs between sheet 1 (p.100) and sheet 9 (p.116).

---

## 3. DSP SUBSYSTEM (IC306, sheet 5, pp.108–109; A4 copy p.144)

- **Part**: IC306 S21065LKS240 "(DIGITAL SIGNAL PROCESSOR)" (= ADSP-21065L SHARC), Panasonic code C2HBBY000012 (parts list p.55).
- **Clock**: oscillator module **X301 = H1A3005B0005** → R303 100Ω → CLKIN (pin 30). Frequency not printed; by Panasonic part-number pattern (X105 H1A**5005**B0014 is listed as "50MHZ OSCILATOR", p.58-area parts list) X301 decodes to **≈30 MHz** (21065L ×2 core ⇒ 60 MHz). XTAL pin unused (module drive).
- **Boot**: **no EPROM/flash of any kind is attached to the DSP bus** — its external bus carries only the two SDRAMs. BSEL is pin 152 (strap not legible in PDF). The only program path is the CPU host bridge ⇒ **host-booted by the MN103002A**.
- **DSP memory**: IC307 + IC308 = KM416S1120DT (C3ABMG000039, "16M SDRAM", 1M×16) — IC307 on DD16-31, IC308 on DD0-15 ⇒ one 32-bit bank, 4 MB total. DSP SDRAM controller pins wired: RAS(42), CAS(43), SBWE(44), DQM(46), SDCKE, SDA10(48), SDCLK0, plus CLK/CKE/LDQM/MDQM on the SDRAMs. Address DA(8)-DA(23) through 4.7kΩ packs (Z308/313/317/318), data DATA0-31 through 22Ω packs (Z309-Z312).
- **CPU host interface** (the physical layer behind the fw's DSP access): IC302 + IC304 TC74VHC245F bus transceivers bridge CPU **D(16-31) ↔ DSP DD(0-15)**; IC303 TC74VHC574F latches CPU D(16-23) → **DSP address DA(0)-DA(7)** (strobe net **ADSPAD**); chip select **ADSPCS** (from decoder IC2 TC74VHC139F, sheet 1 p.100); strobes RE/WE2; ready **DSP.RDV**; small glue IC305 (C0JBAZ000874), IC301 TC7SH02. So the CPU performs address-latched, 16-bit-data host cycles into the DSP's external port (multiprocessor/host space) — this is how the DSP program is loaded and how "Other device test" can test IC306 *and* IC307/IC308 from the CPU (p.30).
- **Control/status sidebands**: **DSP.RST** (driven from CPU sheet 1), FLAG0-FLAG11 pins present; nets **DSP.FLAGB** (sheet 5) and **DSP.FLAGE** (sheet 1) — flag lines to CPU (plausible source of the boot-time "sound status" read at 0x98070000; not provable from the manual). **CP.CLK/CP.DATA** — a 2-wire link drawn from the DSP block to the CPU (block p.79; sheet-1 stubs p.100). BR1/BR2 (pins 27/28) and PWM_EVENT0/1 pins also brought out.
- **Serial audio**: both SPORTs wired. Pin column shows SPORT0 group (RFS0/DR0A "DRBA"/DR0B "DRBB"/TFS0/TCLK0, DT0A/DT0B) and SPORT1 group (RFS1/RCLK1/DR1A/DR1B/TFS1/TCLK1/DT1A/DT1B). The four **SDIE(0-3)** nets enter the DSP receive pins and **SDOE(0-3)** leave the transmit pins via 100Ω packs (Z301 etc.) — 4 in + 4 out serial data channels shared with the TGs (2 SPORTs × A/B channels). Clock nets BCK/LRCK (+ secondary BCKX/LRCKX domain) and CKOUT come from the TG side (TG owns the 16.93 MHz audio crystal).
- **DSP RAM test**: §8.3/Fig.24 p.30 — firmware tests "DSP: IC306" and "DSP RAM: IC307, IC308" with OK/NG per chip. Excellent emulator probe for host-port + SDRAM behavior.

---

## 4. TONE GENERATORS (sheets 7/8, pp.112–115; A4 copies 146–147)

- **IC201** = C1BB00000709 "MASTER TONE GENERATOR LSI"; **IC205** = same part, "SUB TONE GENERATOR LSI".
- **Clock**: X201 (H0J169300002) on IC201 pin 28, pin label "X1(16.9944MHz)" (p.112). Part number decodes ≈16.93 MHz; 16.9344 MHz = 384×44.1 kHz is the standard value — the "16.9944" print is almost certainly a typo for **16.9344 MHz**. The scope waveform "② TG CLOCK" (p.44) shows T≈0.06 µs, consistent. Only the master has a crystal; sub receives clock (pins SMCK, MST, MSET0/MSET1 straps on both).
- **CPU interface (each TG)**: D16-D31 (16-bit), A1-A4 (⇒ 16 half-word registers — matches the (address,data) indirect ports at 0x98040000/2 and 0x98050000/2), chip selects **TGCS** (IC201) / **TGCS2** (IC205) generated by decoder IC1 TC74VHC138F on sheet 1 (p.100), strobes RE/WE2, reset IORST, interrupts **TGS.INT1 / TGS.INT2** back to CPU.
- **Wave buses (each TG)**: 16-bit wave data (AWD0-15 master / BWD0-15 sub) + **two independent 24-bit address ports**: AWAX0-23 & AWAY0-23 (master), BWAX0-23 & BWAY0-23 (sub) — dual simultaneous sample fetch (X and Y). ROMs use bits 0-22 (+CE/OE/BYTE pins, strapped 16-bit).
  - Master: **IC203 = AWAY ROM (C3CBQD000002)**, **IC204 = AWAX ROM (C3CBQD000001)**
  - Sub: **IC207 = BWAY ROM (C3CBQD000004)**, **IC208 = BWAX ROM (C3CBQD000003)**
- **Expansion**: top address bits (…22/23) of each port feed IC202/IC206 TC74VHC139F "2 TO 4 DEMULTIPLEXER" ⇒ chip enables EXACEX(0-3)/EXACEY(0-3) (master) and EXBCEX(0-3)/EXBCEY(0-3) (sub) for the wave-expansion connectors — internal ROMs are "BANK 0-15" (Fig.30, p.34), expansions occupy banks above. Expansion connectors: 80-pin K1KA80A00100 (CN204/206/208/209) carrying EXAWD/EXBWD + WAX/WAY addresses, and 40-pin QJTG02840AA (CN202/203/205/207) carrying the CPU bus (A1-A19, D16-31, EXP.CS0-3, WE2/RE) for flash-type boards.
- **Sub→master digital mix**: IC205 outputs SDSUB0-3 → nets **SUB(0)-SUB(3)** + BCKSUB/LRCKSUB → IC201's SDSUB0-3 inputs. Sub TG audio reaches the DSP only through the master.
- **Master↔DSP/DAC serial**: IC201 pins SD00/SD01/SD02/SD03 (serial data out), SDI (serial in), BCK/LRCK/CKOUT/MTMG/BCKX/LRCKX, plus the SDIE(0-3)/SDOE(0-3) enables shared with the DSP (sheet 7 top edge, sheet 5 left edge). The DAC IC311's LRCK/DATA/BCK/SCK come from this same net cluster (sheet 6, via Z314/Z315/Z316 packs); exact per-net assignment is not legible.
- **Keybed scanned by the TGs in hardware**: keybed matrix (MKB1-3 boards, diodes D201-208) connects via CN201 (sheet 7, "TO MKB2 CIRCUIT (CN3) ON SCHEMATIC DIAGRAM-19") to pins **KS0-3, KF0-3, KB0-4 on BOTH IC201 and IC205** (block p.79 shows the KB/KF/KS arrows into both TG blocks). Two contact rows (KF/KS) = velocity timing. This is the hardware behind the key-event FIFOs read at 0x98040004/0x98050004.
- **Misc TG pins visible** (p.112): RSTOUT, RSTZ, XSM, P00-P02/P10-P13 (GPIO), XTST, SI3/SCK31 (serial port 3, adjacent to nets SD.SI/SD.SO/SD.CLK), AVDD/AGND.

---

## 5. TEST MODES (full text)

**Entry (p.27):** "Press and hold the C#3, D#3, C#4 keys, and then turn on the power switch." Release after the diagnostic screen appears; select tests with the buttons under "page select" (12 pages).

**8.1 ROM device test (pp.28–29, Fig.21/22):** screen lists `PROGRAM ROM: IC16 = , IC17 =` / `RHYTHM ROM: IC18 (IC20) =` / `CUSTOM FLASH: IC21 =` / `PICTURE ROM: IC19 =`; EXECUTE; result OK/NG within twenty seconds; NG may also mean address/data-bus or strobe-line break/short. "ALL DEVICE OK" banner when passing.

**8.3 Other device test (pp.29–30, Fig.24):** `PANEL CPU (IC1): CPL = OK . CPR = OK` / `DSP: IC306= OK` / `DSP RAM: IC307= OK , IC308= OK` / `FLOPPY DISK CONTROLLER: IC103= OK`. EXECUTE; result within a few seconds; same NG caveat.

**8.9 WAVE ROM test (p.34, Fig.30):** screen: `MAIN TG BANK 0-15 ROM: IC203= OK , IC204= OK` / `SUB TG BANK 0-15 ROM: IC207= OK , IC208= OK`. "Press the EXECUTE button to start the test. The test result (OK or NG) is displayed within thirty seconds. If the test result is NG, not only the respective IC, but also a break or short circuit in the ADDRESS/DATA BUS as well as in any of the strobe signal lines may be the cause of the failure." (Presumably a checksum read-back — 30 s for 64 MB.)

**8.10 SOUND SYSTEM test (pp.34–35, Fig.31/32):** "Use the button in the SOUND GROUP to select an item from 1 to 6. Press a keyboard key." Screen (Fig.31) CHECK MODE list, with an **AUTO SWEEP** button and `KEY DOWN INFORMATION = ( )` readout:
1. `SINE WAVE at Full level (w/o Touch and Key note)` — **`C-key = IC203&204, C#-key = IC207&208`** — "Generate a full amplitude sine wave in the pitch of each key. (No touch, fixed stereo center). If no sound is generated or if the sound is distorted, the sound generator ROM corresponding to the key position is defective."
2. `GENERATOR LSI PAN check (w/o Touch and Key note)` — `C-key = LEFT, C#~B-key = RIGHT` — "For confirming the output pathway from the sound generator. (Fixed scale, no touch). The Lch and Rch sound outputs are confirmed separately."
3. `HIGH SOUND check (+2octave w/o Touch and Key note)` — sine at each key +2 octaves, checks output frequency range.
4. `LOW SOUND check (-2octave …)` — sine at each key −2 octaves.
5. `NORMAL SOUND check with TOUCH` — sine with velocity; confirms volume follows touch.
6. `SINE WAVE at 16dB DOWN level (w/o Touch and Key note)` — same as 1 at −16 dB.
Selected by SOUND GROUP buttons 1–6 = PIANO, GUITAR, MALLET&ORCH PERC, WORLD, STRINGS&VOCAL, BRASS (Fig.32).

**8.5 Panel SW & LED test (p.31, Fig.26):** counters `CPL: 2/52, CPC: 0/34, CPR: 2/62, CPSD: 0/6`; "If all buttons are checked, **sine wave will ON**." DEMO button lights CPL LEDs, HELP → CPC, PANEL MEMORY SET → CPR.

**8.11 SD test (pp.35–36, Fig.33):** Load/save test (repeated save/load/compare, OK/NG counts) + **Audio test**: "Insert the SD card. Press the START button to begin the test." (exercises the MN102H60KTA/MN67737 SD-audio playback path). Screen also shows `SD COVER:` status.

**8.12 WAVE EXPANSION BOARD test (pp.36–37, Fig.34):** screen slots `EXP1: EXP2: EXP3: EXP4:`; "Insert the SY-EW01,EW02,EW03 or EW04 board", EXECUTE, OK/NG per board.

**§11.1 (p.41):** "To measure the waveforms, first set this unit to the service diagnostic mode (refer to 'WAVE ROM test'). The WAVE ROM output will then be output as a sine wave to facilitate the servicing check." Waveform check conditions (p.44): diag mode, SOUND=BRASS, MAIN VOLUME=MAX, C4 key; check points: ①RESET, ②TG CLOCK (~16.9 MHz sine, 2.6 Vp-p), ③/④/⑤ = IC311 DAC serial pins (③ 2.7 Vp-p, ④ 3.2 Vp-p T≈0.33 µs ≈ 3 MHz bit clock, ⑤ 0.8 Vp-p T≈22 µs ≈ 44.1 kHz frame).

**8.8 MIDI IN/OUT test (p.33, Fig.29)** also displays `BASS PEDAL SW =` (rear switch SW701 — matches the REARSW finding).

---

## 6. SURPRISES / CORRECTIONS vs. background facts

1. **IC307 is NOT a tone generator and there is no second DSP** — IC307 + IC308 = KM416S1120DT 16-Mbit SDRAMs, the DSP's 32-bit external memory (parts list p.55; sheet 5 p.108; Fig.24 p.30 calls them "DSP RAM").
2. **Wave ROM part numbers & mapping** (parts list pp.54–55, sheets 7/8): IC203=C3CBQD000002 (master AWAY), IC204=C3CBQD000001 (master AWAX), IC207=C3CBQD000004 (sub BWAY), IC208=C3CBQD000003 (sub BWAX). Each is 128 Mbit ⇒ **64 MB total undumped wave data**. Note: the block diagram (p.79) column layout can be read as IC208=BWAY/IC207=BWAX, but the schematic (p.114 text layer) clearly puts BWAY0-22 on IC207 and BWAX on IC208 — trust the schematic.
3. **TG crystal**: printed "X1(16.9944MHz)" (p.112) but part H0J169300002 ≈16.93 MHz; almost certainly **16.9344 MHz** (384 × 44.1 kHz). The "16.9944" print looks like a typo.
4. **DSP is host-booted** — no boot memory exists on the DSP bus; the CPU loads it through a '574-latched-address / '245-data 16-bit host bridge (ADSPCS/ADSPAD/RE/WE2/DSP.RDV/DSP.RST). Relevant to the MAME blocker: the firmware must be feeding the DSP program through the 0x98xxxxxx window before the playback engine can rely on it.
5. **A CPU-writable sound-control latch exists**: IC25 (74HC174, sheet 2 p.102) drives nets **DAC.MDI / DAC.MC / DAC.ML / SDMODE / SPSW / USB.WAITM** — software mode-programming of the main DAC (IC311 MD0/MD1/CS) + speaker relay. A physical candidate for one of the unidentified sound regs (0x98060000/0x98070000 area) — mapping not stated in the manual.
6. **Main DAC is a Panasonic-coded unknown**: IC311 = C0FBBK000025, only labeled "D/A CONVERTER" (sheet 6 p.110) — differential current-output stereo DAC with LRCK/DATA/BCK/SCK0/SCK1 + MD0/MD1/CS mode port. Commercial equivalent not identified anywhere in the manual.
7. **IC406 discrepancy**: parts list p.55 says PCM1716ET2 (C0FBBK000009), schematic p.118 prints **PCM1734EB-EZ2** — production change; it is the USB/SD-side DAC, not in the TG/DSP main path.
8. **ROM roles named by the ROM test** (Fig.21/22, pp.28–29): IC16/IC17 = PROGRAM ROM (flash), IC18 = **RHYTHM ROM** (alt. footprint IC20, "We do not supply IC20 as replacement parts", sheet 2 p.102), IC21 = **CUSTOM FLASH**, IC19 = **PICTURE ROM**. IC18 = CUSTOM DATA ROM holding RHYTHM&ACCOMP + user COMPOSER data, restored via "CTMINI" load (pp.39–40) — matches the 01CTMINI.AST finding.
9. **Sine test waves live in the wave ROMs themselves** (mode 1: C keys exercise IC203&204, C# keys IC207&208) — the SOUND SYSTEM test cannot pass without wave ROM dumps (or stand-ins containing sine samples at the right banks).
10. **Both TGs scan the keybed directly** (KS/KF/KB pins on IC201 *and* IC205) — confirms/explains the two key-event FIFOs (0x98040004/0x98050004) seeing the same keybed.
11. **Independent SD/USB audio playback path** bypasses TG+DSP entirely: IC402 MN67737DB1 decoder (analog ARO/ALO out) and IC406 USB DAC are mixed in analog (Q307/Q308/Q309, nets ALB/ARB/SD.PLY, sheet 6 p.110); record side re-digitizes the final mix (MAINL/MAINR → IC410 PCM1800E). Also IC403 "EEPROM" = Seiko S-29L331A 3-wire serial EEPROM (not a 32-Mbit Spansion flash as the part string might suggest).
12. **Two TG interrupt lines** (TGS.INT1, TGS.INT2) and a 2-wire **CP.CLK/CP.DATA** DSP↔CPU link exist (pp.79, 100) — undocumented in the current io-map notes.
13. Clocking extras: net **11.2896M** (256×44.1 kHz) between CPU sheet and SD sheet; DSP oscillator X301 ≈30 MHz (H1A3005B0005); CPU X1 H0J160500026 (≈16.05 MHz) through spread-spectrum IC6 (C0ZBZ0000667 "SPECTRAM SPREAD"); SD u-COM X401 H0J327200034 (≈32.7 MHz), SD decoder X402 H2D225500001 (≈22.55 MHz) — frequencies inferred from Panasonic part-number pattern except where printed.
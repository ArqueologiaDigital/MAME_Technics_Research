> Recon report produced 2026-07-09 by the sound-plan rev-2 research sweep.
> Companion to notes/sound-subsystem-plan.md. Verify page/line/address citations before building on them.
> Note: the ROM-backup/custom-firmware work here targets Felipe's OWN instrument for preservation (dumping otherwise-unreadable mask ROMs), analogous to console homebrew — legitimate, reversible, no third party.

# KN6000 / KN6500 sound-subsystem RE inventory
(All firmware addresses are MN10300 CPU addresses; program-ROM file offset = addr − 0x48400000. New findings in this report were verified this session by direct binary scan + unidasm; commands are reproducible.)

## 1. WHAT EXISTS

| Material | KN6000 | KN6500 |
|---|---|---|
| Service manual | `/home/fsanches/compartilhado/KN6000/technics_sx-kn6000-sm.pdf` — 89 pp, **image-only, NO text layer** (contents p.3: schematics p.27, block diagram p.68, parts list p.74) | `/home/fsanches/compartilhado/KN6000/service_manual_kn6500.pdf` — 142 pp, **has text layer** (pdftotext works; §12.9 WAVE ROM test / §12.10 SOUND SYSTEM test at text lines 792–830) |
| Firmware (program flash IC11/IC12) | Dumped from update disks: `kn6-71.zip` → `IK1.SLD`+`IK2.SLD` decompressed+concatenated (0x3F7A31 bytes). Files: `/home/fsanches/compartilhado/kn7000_scratchpad_snapshot/kn6ext/kn6000_program_full.bin`, padded 4 MB `.../kn6000_prog.bin`; MAME even/odd in `/home/fsanches/compartilhado/kn7000_mame_build/roms/kn6000/` (CRCs in `kn7000_mame/notes/mame-pr-rom-manifest.md:26-34`) | Same pipeline from `kn65-13.zip` (`IKV1`+`IKV2`, 0x381691 bytes); MAME even/odd in `/home/fsanches/compartilhado/kn7000_mame_build/roms/kn6500/`; source zip at `/home/fsanches/compartilhado/KN6000/ca_software_files/kn65-13.zip`. No pre-built linear image existed — I built one this session at scratchpad `kn6500_prog.bin` (interleave even/odd 16-bit words) |
| Table mask ROM (IC13/IC14) | **NOT dumped.** The MAME `kn6000_table_*` ROMs are a placeholder: verified this session that the interleaved table image is byte-identical to program bytes 0x200000+ (i.e. it is just IK2 again), not the physical `QSIGX3C16008/16007` mask ROMs. Driver comment admits derivation (`kn7000_mame/src/mame/matsushita/kn7000.cpp:1548-1552`) | Same situation; physical parts are `C3FBMD000069`/`C3FBMD000068` (kn6500_sm pdftotext lines 8610–8614, IC14 block) |
| Rhythm-data ROM (IC15) / custom flash (IC18) | IC15 `QSIGX3C32021` (32 Mbit) undumped; IC18 defaults recreatable from `idd6000.exe` (`/home/fsanches/compartilhado/KN6000/ca_software_files/`) | IC15 same part `QSIGX3C32021`; IC18 = M29LV160B8TN |
| Wave ROMs | **UNDUMPED** (4 chips, see §2) | **UNDUMPED** (6 chips) |
| MAME driver | Shared `kn7000.cpp`: `kn6000()` machine config at `kn7000_mame/src/mame/matsushita/kn7000.cpp:1502-1507`; systems at :1606-1607, both `MACHINE_NOT_WORKING | MACHINE_NO_SOUND`. Boot notes: `kn7000_mame/notes/kn6000-kn6500-boot.md` | same |
| Disassembly repo | **None.** `kn7000_disassembly/` is KN7000-only (no kn6000 sym/Makefile targets). Only scratch artifacts (`kn7000_scratchpad_snapshot/kn6000_prog.bin`, name dumps) | none |
| Docs site (local mirror) | `/home/fsanches/compartilhado/kn5000-docs/kn6000-hardware.md` (hardware architecture incl. audio path), `kn6000-roadmap.md`, `kn6000-names.md` | covered by the same pages |

There is **no KN6000/KN6500-specific sound note** in `kn7000_mame/notes/` — everything sound there is KN7000. This report is the first sound-focused pass on these two models.

## 2. SOUND HARDWARE (from the two service manuals)

KN6000 sources: parts list pp.79–80 + block diagram pp.68–69 (read visually this session — renders in scratchpad `kn6sm_ic-79/80.png`, `kn6sm_block-68/69.png`). KN6500 sources: pdftotext line numbers given.

| Function | KN6000 | KN6500 | KN7000 (reference) |
|---|---|---|---|
| Tone generator | **IC213 `D82398GD001`** ×1, "TONE GENERATOR LSI" (SM p.80; block p.69: A1–A3 + D16–D31 CPU side ⇒ 8×16-bit regs; WAX0-24/WAY0-24 private wave buses; SDI0-3/SDO0-3 serial to DSP; KB/KF/KS keybed scan via IC202) | Same **IC213 `D82398GD001`** ×1 (kn6500_sm lines 8960, 20495-20497) | 2× `C1BB00000709` (IC201 master + IC205 sub) |
| Polyphony | 64 notes (KN6000 spec pages equivalent) | 64 notes, PCM (kn6500_sm lines 55–61) | 128 notes |
| Wave ROMs | **4× 64 Mbit mask ROM = 32 MB**: IC205 `QSIGX3C64004`, IC206 `QSIGX3C64005`, IC207 `QSIGX3C64006`, IC208 `QSIGX3C64007` (p.80); IC205/207 on WAY bus, IC206/208 on WAX bus (block p.68) | **6× 64 Mbit = 48 MB**: same four part numbers **plus IC209 `QSIGX3C64020`, IC210 `QSIGX3C64019`** (lines 8900–8950); 3 per WAY/WAX bus (block, lines 33254–33298) | 4× 128 Mbit `C3CBQD00000x` = 64 MB, two per TG |
| Effects DSP | **IC304 `S21065LKS240` = ADSP-21065L SHARC — the exact same part as the KN7000's IC306** (KN6000 SM p.80) | Same IC304 `S21065LKS240` (lines 9010–9012); "A MAIN DSP CIRCUIT" schematic with nets DSP.RST/DSP.RDY/DSP.FLAG0/ADSPCS/ADSPAD/MTMG/BCKX/LRCKX/SDOE[0-3]/SDIE[0-3] (lines 16999–17206, 21806–21824) — same net names as the KN7000 host-boot glue | IC306 `S21065LKS240`, host-booted |
| DSP memory | IC305,06 `K16S1120DTG8` (1M×16 SDRAM) ×2 (p.80) | same (line 9020) | IC307/IC308 KM416S1120DT ×2 — same config |
| DAC | IC307 `PCM1728E2K` stereo DAC ("D/A CONVERTER", KN6500 line 22656; same part in KN6000 p.80) — single DAC, no sub-out DAC | same | `C0FBBK000025` main + PCM69BU sub |
| ADC | IC309 `PCM1800E-T1` (mic/line in) ×1 | same (line 9052) | PCM1800E ×2 (mic + record) |
| Clocks | — (image-only) | X201 16.93 MHz ceramic = TG clock; X301 30 MHz = DSP; X1 32 MHz CPU (lines 15058–15122) | TG clock ~16.9 MHz (same) |
| Expansion | none seen on block diagram | `EXP.CS0`/`EXP.CS1` chip selects on a D16-D31 connector (lines 17049–17050, 20066–20268) — 2 expansion selects | EXP.CS0-3, SY-EW01..04 boards |
| Amp/speakers | 66 W (18 W×2 + 30 W bass), FAJ board analog chain (kn6000-hardware.md "Audio path") | same class | 2×12 cm + 2×6.5 cm + woofer |

**KN6000 → KN6500 differences are tiny**: +2 wave ROMs (16 MB more samples), different table mask-ROM contents, custom-flash part swap. TG, DSP, SDRAM, DAC, ADC, rhythm ROM all identical parts. The KN7000 SM's SD/USB audio subsystem (IC401/402/etc.) has **no counterpart** in either KN6xxx manual — no SD MCU on these models.

## 3. SOUND REGISTER MAP (firmware evidence, verified as fc-prefixed abs32 instruction operands, not data)

The 0x98/0x9C sound-bank decode is the **same layout as the KN7000 minus the second TG block (0x9804xxxx)**:

| Register | KN6000 verified sites | KN6500 sites | Role (same semantics as KN7000) |
|---|---|---|---|
| `0x98000000` (16-bit) | write `movhu d0,(0x98000000)` @**0x48557732**; accessor dispatches on logical ids `0x9C0/0x9C2/0x9C4` @0x48557715–0x4855772B — identical id scheme to KN7000's `0x48404E8D` accessor | 0x48557CEE | SHARC host index port |
| `0x9C000000` (16-bit) | read @**0x485576F3**, write @**0x48557749**, bracketed by guard calls reading bus-timing regs `0x32000026/0x3200002E` (@0x48557786/8F); DSP dead-flag = `0x50005D98` (checked @0x48557762; KN7000's was 0x500066CC) | read 0x48557CAF, write 0x48557D05 | SHARC host data port |
| `0x98050000` / `0x98050002` | TG reg-pair writer @**0x4849465B** (`movhu hi16→+0; movhu lo16→+2`), second writer + readback @0x48494672–0x48494697 | 0x48494529/0x48494544/0x48494556 | the **single** TG's register port (KN7000 uses 0x9804 pair for main TG, 0x9805 for sub; KN6xxx uses only 0x9805) |
| `0x98050004` | 3 raw sites | 3 | keybed/voice-event FIFO (KN7000-compatible) |
| `0x98050006/8/A` | wave-ROM readback window: checksum routine @**0x4856BB1A** writes `0x8000|page`→+6 (@0x4856BB2D/4E), `0x8000|offset`→+8 (@0x4856BB6E), reads data @+A (@0x4856BB74); second copy @0x48571F36/66/75 | 5/2/2 sites | **byte-for-byte the KN7000 WAVE-ROM-test protocol** — same software dump path exists for the undumped wave ROMs on real hardware |
| `0x98060000` | 4 sites @0x48573DC8–0x48573EA1 | 0x485745CA–0x485746A3 | codec bit-bang GPIO latch |
| `0x98070000` | 9 read sites (0x48432792, 0x4844EBB3/CC/F1, 0x484505AF, 0x4847B11E/38, 0x48557D9B/B3) | 9 | board-type/strap word |
| `0x98010000`, `0x98020004/8/A/E` | Device-A mailbox module clustered @0x48510xxx (e.g. 0x98020004 @0x485104C0–0x48510544; 0x98010000 @0x48510D6A/0x48510E00/0x48510EE6) | 0x48510314–0x48510D3A | the KN7000's unidentified "Device A" exists here too |
| `0x98040000/2` | ONE write pair @0x4851045D/0x48510463, **inside the Device-A module** — looks like a probe, not a TG driver; no other 0x9804 usage | 0x485102B1/B7 | (KN7000 main-TG address — vestigial/probe on KN6xxx) |

No `0x98040010`/`0x98050010` init-strobe writes (KN7000's TG-init pattern) — consistent with a **different TG chip** (D82398GD001 vs C1BB00000709) needing different init, even though the register-pair and readback-window conventions match.

MAME driver handling today: the whole `0x98000000–0x9807ffff` window goes through the KN7000 HLE `io_r/io_w` (`kn7000.cpp:408`, TG latches :473–481, FIFO :436–442, `0x9805000E` echo :450/463, strap :423); `0x9C000000–0x9CFFFFFF` is flat RAM (`:355`) so the DSP data port is unmodeled — the same 0x9C-bank conflict documented for the KN7000 in `notes/dsp-host-interface.md` §2 applies to all three machines.

## 4. DSP PROGRAM — embedded, same host-download format, found in BOTH firmwares

Scanned for the KN7000's `0x2004` record format (blocks `{u16 0x2004 BE, u8 mode 0x80=PM/0x00=DM, u8 flag, u16, u16 target, u16, u16 len, payload}`, 12-zero-byte terminator):

- **KN6000: 80 records @ ROM 0x387064–0x398809 (CPU `0x48787064–0x48798809`)**, 71,589 bytes, 6,493 PM words + 5,775 DM entries.
- **KN6500: 80 records @ ROM 0x3128E8–0x32408D (CPU `0x487128E8–0x4872408D`)**, identical totals.
- **KN6000 pool == KN6500 pool byte-identical, 80/80 records** — one effects firmware for both models.
- Kernel record (KN6000 @`0x48787B48`, KN6500 @`0x487133CC`) has the **identical block map** to the KN7000 kernel: DM 0x9800(0x190)/0x9C40(0x64)/0xC000(0x181)/0xC302(0x2F8), PM 0x8000(0x60C = 258 words)/0x8300/0x8400/0x8D00. The four leading variant/probe records (DM 0xC000 + PM 0x8400, 0x2B9 each) are present too.
- **Verified genuine SHARC code**: repacked the KN6000 kernel PM@0x8000 block and ran `unidasm -arch sharc` — textbook ADSP-2106x vector table (`IDLE` @0x8004, `JUMP 0x8071` @0x8005, RTI-filled vectors), same shape as the KN7000's (repacked binary: scratchpad `kn6000_sharc_pm8000.bin`).
- vs KN7000: only **3/80 records byte-identical** (the last three, indices 77–79); in the kernel all four **DM (parameter/table) blocks are byte-identical** while all four **PM (code) blocks differ** — the KN7000 shipped a revised SHARC code build over the same effect architecture/parameter layout.

Conclusion: the KN6000/KN6500 DSP is **the same host-booted ADSP-21065L subsystem**, not fixed-function — record interpreter, host-port protocol (index 0x98000000 / data 0x9C000000, logical ids 0x9C0/0x9C2/0x9C4, bus-timing bracket, dead-flag) all carried over.

## 5. SIMILARITIES & DIFFERENCES vs KN7000

| Aspect | KN6000/KN6500 | KN7000 | Cross-RE value |
|---|---|---|---|
| Effects DSP chip | ADSP-21065L (`S21065LKS240`) + 2× 1M×16 SDRAM | identical part + memory | **Maximal** — one SHARC device model serves all three; KN6xxx even shares its exact microprogram pool between the two models |
| DSP host interface | 0x98000000 idx / 0x9C000000 data, ids 0x9C0/2/4, dead-flag guard | identical protocol | Maximal — KN7000 `dsp-host-interface.md` findings port directly |
| DSP program | embedded 80-record pool, same format; DM tables identical to KN7000, PM code older revision | 80 records @0x486BCEC4 | High — diffing the PM blobs isolates the KN7000's effect-code changes |
| Tone generator | 1× `D82398GD001`, 64 voices, regs @0x98050000/2 | 2× `C1BB00000709`, 128 voices, @0x98040000/2 + 0x98050000/2 | **Partial** — register-pair convention, keybed FIFO (+4) and wave-readback window (+6/8/A) identical; chip and init sequence differ |
| Wave ROMs | 4×64 Mbit (KN6000) / 6×64 Mbit (KN6500), `QSIGX3C640xx`, undumped; KN6500 superset of KN6000's four | 4×128 Mbit `C3CBQD`, undumped | Shared dump strategy: the same service-test readback window can software-dump all of them; one KN6500 dump covers KN6000's four chips |
| DAC/ADC | PCM1728 + PCM1800 | custom DAC + PCM69 + 2×PCM1800 | Low — simpler analog on KN6xxx |
| Device-A mailbox (0x98010000/0x98020000) | present, module @0x48510xxx | present, identity still open | Same open question; two more data points |
| SD/USB audio | absent | separate MN102H MCU subsystem | n/a — KN6xxx are free of the paused SD problem |
| Table/sample-map ROMs | physical mask ROMs IC13/IC14 **undumped; current MAME "table" ROMs are an IK2 mirror placeholder** | table ROM dumped | Blocker specific to KN6xxx — TG sample maps likely live there |

**Bottom line:** cross-model RE is clearly worth it on the DSP side (same chip, same protocol, near-same program — anything built for the KN7000 SHARC works on all three) and on the TG *interface* side (FIFO + readback windows identical). The genuinely new work for KN6xxx sound is (a) the D82398GD001 TG's register semantics/init, (b) dumping 4–6 `QSIGX3C640xx` wave ROMs (hardware or via the service readback window), and (c) dumping the real IC13/IC14 table mask ROMs, without which even a perfect TG model would lack sample maps.

---

## ★ DYNAMIC CAPTURE (2026-07-10) — KN6000 already drives its tone generators live

Ran the KN7000 Lua TG-tap methodology against the **kn6000** machine (live in MAME,
video on; taps on 0x98040000/0x98050000 write + 0x98050004 read, key presses on
:KEYS0). Findings:

- **KN6000's TG voice engine is ALREADY running on key-bed notes — no gate fix
  needed.** A 3-note press (C4/E4/G4 on+off) gave `fifoPolls=2006, consumed=6` (the
  firmware reads the 0x98050004 key FIFO and consumes exactly the 6 events) and a
  rich burst of per-voice TG writes. Unlike the KN7000, the strap-probe TG-enable
  gate is open by default here (the CONFIG bit1 fix is a KN7000-only thing).
- **It boots to its play screen (no SD subsystem)** → KN6000/KN6500 are a *cleaner*
  sound bring-up platform than the KN7000 (which is stuck on the SD menu when its
  gate is opened). Sound could be default-on for the KN6xxx with no screen trade-off.
- **The tonegen device + speakers are already wired** (shared kn7000() config); the
  machines are just flagged MACHINE_NO_SOUND and the tonegen currently only decodes
  the KN7000 pitch class (0x2401), so it produces nothing for KN6000 yet.
- **KN6000 per-voice register layout DIFFERS from the KN7000** (captured, first voice,
  C4/E4/A4 all in one octave so only the fine-pitch field moved):
  | class | data | note |
  |---|---|---|
  | **0x5800** | C4=0x0C00, E4=0x0BF4, A4=0x0BE8 | **fine pitch (within-octave)** — decreases ~2.7/semitone; same value range as the KN7000's 0x3000 field |
  | 0x0000 | 0x8000 | key-on / gate flag candidate |
  | 0x4000 | 0x3FFF | voice LEVEL (near-max; KN7000 analog 0x2009=0x5FFF) |
  | 0x4400 | 0x6000 | ? |
  | 0x2800 | 0x0200 | flag |
  | 0x2C02 / 0x2C03 | 0xC800 | ? (index varies by voice) |
  | 0x5C07 | 0xFFFF | ? |
  | **0x800B/0x8400/0x8804/0x8C0F** | D546/38AF/2AB9/C750 | sample/waveform params — **identical DATA to the KN7000's 0x400B/0x4400/0x4804/0x4C0F quartet** (same default patch), just group 0x80 not 0x40 |

- **NEXT to make KN6000 sing:** (1) find the octave/coarse pitch register — needs notes
  in DIFFERENT octaves, but KN6000's :KEYS1 (C5+) produced NO writes in this test, so
  first check the KN6000 key-bed→note mapping (KEYS1 wiring / octave offset). (2) Add a
  KN6000 branch to `kn7000_tonegen_device::tg_write` decoding 0x5800(+octave) for pitch
  and 0x0000/0x4000 for gate/level. (3) Flip kn6000/kn6500 to MACHINE_IMPERFECT_SOUND
  (likely no CONFIG switch needed — no SD side effect). Reuse tools/stage2_tg_diagnostic.lua.

Not found: any KN6000/KN6500 wave-ROM, table-ROM, or panel-MCU dumps anywhere under `/home/fsanches/compartilhado/`; any KN6xxx disassembly workspace; any KN6xxx-specific sound notes in `kn7000_mame/notes/`.
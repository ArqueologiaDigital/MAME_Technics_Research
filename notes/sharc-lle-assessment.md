> Recon report produced 2026-07-09 by the sound-subsystem planning sweep (5 parallel research agents).
> Companion to notes/sound-subsystem-plan.md. Verify page/line citations before building on them.

# MAME SHARC support assessment for KN7000 IC306 (ADSP-21065L) LLE

## 1. What MAME's SHARC core models, and the gap to the 21065L

### Device types and family coverage
- The core is explicitly a **family 2106x emulator**: header comment "Analog Devices ADSP-2106x SHARC emulator v3.0" (`/home/fsanches/compartilhado/mame/src/devices/cpu/sharc/sharc.cpp:3`).
- Two device types exist: **`ADSP21062`** (2 Mbit internal SRAM) and **`ADSP21060`** (4 Mbit), declared at `sharc.h:553-554`, defined at `sharc.cpp:69-70`. The 21060 is just a subclass of `adsp21062_device` that passes different internal address maps (`sharc.cpp:131-141`); the protected constructor already takes `address_map_constructor internal_pgm, internal_data` parameters (`sharc.h:91-98`, `sharc.cpp:143-153`). **No 21065L (or 21061) variant exists anywhere in MAME** — `grep -rn "21065" src/` returns only ROM CRC/SHA1 false positives.
- Internal maps: `pgm_2m`/`pgm_4m`/`data_2m`/`data_4m` (`sharc.cpp:83-117`). IOP registers at data addresses 0x00000-0x000FF, RAM blocks based at 0x20000, short-word aliases at 0x40000+.

### ISA coverage
- The interpreter (`sharcops.hxx`, table in `sharcops_table.cpp`), a working DRC (`sharcdrc.cpp`, enabled via `enable_recompiler()`, `sharc.h:36` / `sharc.cpp:239-244`) and a full disassembler (`sharc_dasm.cpp`) cover the first-generation SHARC instruction set. Since the 21065L uses the same 2106x core ISA (stipulated in the task; ADI markets it as code-compatible), **no instruction-level work is needed** — interpreter, DRC and disassembler are reusable as-is.

### Peripheral coverage (this is where the gaps are)
- **IOP registers**: only a tiny 2106x subset. Reads: 0x00 (SYSCON, returns 0) and 0x37 (DMA status); **any other read throws `emu_fatalerror`** (`sharc.cpp:355-371`). Writes: SYSCON 0x00, wait-state 0x02 (ignored), EPB0 ext-port DMA buffer 0x04, message regs 0x08-0x0F (ignored), DMA6 (ctrl 0x1C, params 0x40-0x47), DMA7 (ctrl 0x1D, params 0x48-0x4F), 0x14/0x17/0x20 ignored; **anything else throws** (`sharc.cpp:373-445`).
- **DMA**: only the external-port-style channels 6/7 are wired; packing modes no-packing, 16/32, 8/48 (plus 16/48 on the `external_dma_write` host path, `sharc.cpp:517-563`); handshake and single-word-interrupt modes `fatalerror` (`sharcdma.hxx:280-283`).
- **SPORTs (serial ports): not emulated at all** — grep for sport/serial across `src/devices/cpu/sharc/` finds nothing but the `BOOT_MODE_LINK` enum name (`sharc.h:23`).
- **Link ports: not emulated** (irrelevant — the 21065L has none anyway).
- **On-chip timer: not emulated** — TPERIOD/TCOUNT exist only as disassembler register names (`sharc_dasm.cpp:46`) and TODO comments (`sharcops.hxx:1753` etc.).
- **External IRQ0-2 lines**: supported (`execute_set_input`, `sharc.cpp:1084-1097`); FLAG0-3 in/out supported (`set_flag_input` / `flag_out_cb`, `sharc.h:33,41`).
- **Boot modes**: `BOOT_MODE_EPROM` and `BOOT_MODE_HOST` implemented in `device_reset` (`sharc.cpp:927-965`); LINK/NOBOOT throw. EPROM boot immediately runs a DMA6 8→48-bit-packing transfer of 0x600 external byte-words from ext address 0x400000 into 0x100 instructions at internal 0x20000, then PC = 0x20004 (`sharc.cpp:934-948, 967`).

### Which 21065L differences actually matter for running its program on this core
| Difference | Matters? | Why / where it bites in the code |
|---|---|---|
| IOP register map (completely different offsets; SDRAM-ctrl regs, SPORT regs, different DMA channel layout) | **Yes — first blocker** | `iop_r`/`iop_w` `fatalerror` on any unknown offset (`sharc.cpp:367,443`); a 21065L program will die on its first SPORT/SDCTL/wait-reg access |
| 2 SPORTs (I2S-capable, the audio path of an effects DSP) | **Yes — biggest new code** | zero serial-port emulation exists; audio in/out for IC306 has nowhere to flow |
| 544 Kbit internal SRAM at 21065L-specific addresses (vs 2 Mbit at base 0x20000) | **Yes** | the binary is linked for 21065L addresses. The internal-RAM base 0x20000 is hardcoded in DMA logic (`sharc.cpp:299,308,524`; `sharcdma.hxx:13`) and the PM word-mangling templates assume the 2M/4M block geometry (`sharc.cpp:306-334`) |
| SDRAM controller | Minor | model the external SDRAM as plain `.ram()` in the data map; only SDCTL/SDRDIV config writes need stubs |
| Boot modes (EPROM/host/no-boot) | Minor | EPROM+HOST already exist generically; a 21065L subclass reset just needs its own boot-DMA base/channel numbers |
| No link ports | None | MAME never emulated them |
| On-chip timers | Unknown | not emulated; matters only if the KN7000 DSP program uses them |

## 2. How existing drivers boot/host-load SHARC programs

Complete user list (grep for ADSP2106x outside the core): `konami/k001005.cpp`, `konami/gticlub.cpp`, `konami/konppc.h/.cpp`, `konami/nwk-tr.cpp`, `konami/zr107.cpp`, `konami/hornet.cpp`, `sega/model2.h/.cpp`. **Every one uses the SHARC as a 3D geometry coprocessor; there is no SHARC-as-audio-DSP precedent in MAME** (firebeat.cpp has no SHARC; the taitojc/taito_b/merit hits were CRC/SHA1 hex false positives). The KN7000 would be the first.

### Pattern A — closest analogue to "host CPU uploads DSP program through a parallel host port": Sega Model 2B (`/home/fsanches/compartilhado/mame/src/mame/sega/model2.cpp`)
- `ADSP21062(config, m_copro_adsp, 32_MHz_XTAL); set_boot_mode(BOOT_MODE_HOST)` (`model2.cpp:2857-2859`).
- i960 host sets control-reg bit 31 → "start copro upload": halts the DSP and zeroes a word counter (`copro_ctl1_w`, `model2.cpp:428-447`).
- Each subsequent host word goes to `m_copro_adsp->external_dma_write(m_coprocnt, data & 0xffff)` (`model2.cpp:671-682`) — the core's `external_dma_write` 16/48-packs three 16-bit writes into one 48-bit instruction in internal PM using the DMA6 settings preloaded by `BOOT_MODE_HOST` reset (`sharc.cpp:517-563, 951-961`).
- Host can also poke IOP registers directly: `map(0x008c0000, 0x008c0fff).w(m_copro_adsp, FUNC(adsp21062_device::external_iop_write))` (`model2.cpp:1410`).
- Clearing bit 31 → `copro_boot()` releases `INPUT_LINE_HALT` (`model2.cpp:661-664`).
- Runtime data exchange: SHARC data map exposes host FIFOs in/out via `generic_fifo_u32_device` (`copro_sharc_map`, `model2.cpp:649-655`).
- Caveat in-file: "lastbrnx: uses external DMA port 0 for uploading SHARC program, hook-up might not be 100% right" (`model2.cpp:18`).

### Pattern B — host writes program into shared RAM, then reset-driven "EPROM" boot: Konami CG boards (`konppc` + zr107/gticlub/hornet/nwk-tr)
- `BOOT_MODE_EPROM` (`hornet.cpp:1408`, `zr107.cpp:756`, `nwk-tr.cpp:644`, `gticlub.cpp:885`). On reset the core auto-DMAs 0x100 instructions from external data address 0x400000 (`sharc.cpp:934-948`) — and in these drivers 0x400000 is mapped to banked **shared RAM** that the PowerPC filled with the DSP program (`hornet.cpp:1057-1066` `sharc_map`; `konppc.cpp:296-309` `dsp_shared_ram_w_sharc`).
- The PPC holds/releases the SHARC via `INPUT_LINE_RESET` from a control-register bit (`konppc.cpp:160-171`), and signals it at runtime with FLAG0 + IRQ0/1/2 (`konppc.cpp:218-238`).
- zr107 also shows `m_dsp->enable_recompiler()` for speed (`zr107.cpp:755`).

### For the KN7000
Whichever the real hardware does — MN10300 pushing the image through the 0x980xxxxx sound block (model2 pattern) or a boot EPROM/shared RAM pulled by reset DMA (konppc pattern) — both host-side templates exist and are small. Which one applies is **not yet known**; nothing in `kn7000_mame/notes/io-map.md`'s sound block has been proven to be a DSP host port (0x98060000 / 0x98070000 "sound status" are the candidates to watch in firmware traces).

## 3. unidasm invocation for raw SHARC blobs

- Arch entry: `{ "sharc", le, -3, ... }` (`/home/fsanches/compartilhado/mame/src/tools/unidasm.cpp:613`) — little-endian, granularity 8 bytes per address unit.
- The disassembler consumes one **64-bit little-endian word per instruction** with the 48-bit opcode right-justified (top 16 bits ignored): `disassemble()` does `opcodes.r64(pc)` and decodes from `(opcode >> 40) & 0xff` (`sharc_dasm.cpp:1241-1251`); `opcode_alignment() == 1` (`sharc_dasm.cpp:1253-1256`).
- **Verified experimentally** with `/home/fsanches/compartilhado/mame/unidasm`:
  ```
  unidasm sharctest.bin -arch sharc
  0: 0000000000000000  NOP
  1: 00000c0020004000  LCNTR = 0x0020, DO (0x00004001) UNTIL LCE
  ```
  where sharctest.bin was two `struct.pack('<Q', instr)` records.
- **Exact invocation**: `unidasm <blob.bin> -arch sharc [-basepc 0xNNNN]` — basepc/addresses are in instruction words, not bytes.
- **Alignment caveat**: raw/packed images are 6 bytes per instruction and must first be repacked to 8-byte LE records (pad 2 zero bytes on top). Byte order when repacking: an EPROM-boot image is LSB-first (byte at src+0 = opcode bits 7:0, per `DMA_PMODE_8_48`, `sharcdma.hxx:127-141, 221-237`); a 16-bit host-upload stream packs 16/48 with word order depending on the MSWF control bit (`sharc.cpp:540-556`). The disassembler is family-generic (pure bit decode), so it is valid for 21065L code.

## 4. Verdict and minimum new device work

**SHARC LLE for IC306 is realistic later.** The expensive parts — a mature 2106x interpreter, a DRC, and a disassembler proven in shipping drivers (model2, gticlub/zr107/hornet/nwk-tr) — already exist and cover the 21065L's ISA. What does not exist is the 21065L's I/O personality, and (uniquely for this project) any audio plumbing. Minimum work, in order:

1. **Locate the DSP program image** (prerequisite): find the 21065L binary in the dumped MN10300 firmware (48-bit-pattern hunting; validate candidates with `unidasm -arch sharc` after repacking), or establish that it lives on an undumped ROM. Also determine the load path (host-port upload vs boot ROM) from firmware RE — currently unknown.
2. **`adsp21065l_device` subclass** following the `adsp21060` pattern (`sharc.cpp:131-141`): new internal program/data address maps for the 544 Kbit two-block layout; parametrize the internal-RAM base currently hardcoded as `0x20000` in the DMA paths (`sharc.cpp:299, 308, 524`; `sharcdma.hxx:13`) and adapt the `pm_r/pm_w` block mangling (`sharc.cpp:306-334`). Exact 21065L internal base addresses/block split must be transcribed from the ADSP-21065L datasheet at implementation time (not asserted here).
3. **21065L IOP register bank**: replace the fatalerror defaults (`sharc.cpp:367, 443`) with the 21065L map — SYSCON/SYSTAT/WAIT, SDRAM controller regs as logged stubs (model the SDRAM itself as plain RAM in the external data map), external-port DMA regs, message regs.
4. **SPORT emulation (the genuinely new piece)**: 2 serial ports with RX/TX data regs, DMA channels and interrupts, streaming audio between the tone-generator LSIs and the DSP and out to the DAC — no precedent anywhere in MAME's SHARC usage, so this is written from scratch (a device_sound_interface/stream on the driver side).
5. **Driver-side boot glue** in `kn7000.cpp`: copy `model2.cpp` `copro_ctl1_w`/`copro_fifo_w`/`external_dma_write` (host upload) or the konppc shared-RAM + `INPUT_LINE_RESET` EPROM-boot pattern, per what step 1 reveals.

Part-marking note: "S21065LKS240" reads as ADSP-21065L**KS**-240 (KS = 208-lead MQFP package; -240 speed grade = 60 MHz core, 240 MFLOPS peak) — consistent with the service-manual identification given as established fact.
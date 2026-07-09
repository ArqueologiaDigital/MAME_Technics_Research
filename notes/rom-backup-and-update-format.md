> Recon report produced 2026-07-09 by the sound-plan rev-2 research sweep.
> Companion to notes/sound-subsystem-plan.md. Verify page/line/address citations before building on them.
> Note: the ROM-backup/custom-firmware work here targets Felipe's OWN instrument for preservation (dumping otherwise-unreadable mask ROMs), analogous to console homebrew — legitimate, reversible, no third party.

# Technics SX-KN7000 — ROM-backup utility engineering research

Scope: how the official firmware-update mechanism works, where the flash-write path is, and how to build a reversible ROM-backup utility (including the undumped wave ROMs) that runs on the real instrument. All addresses are MN10300 CPU addresses unless a file offset is stated; program-ROM file offset = CPU addr − 0x48400000. Primary artifacts: `/home/fsanches/compartilhado/kn7000_disassembly/baserom/kn7000_program.rom` (0x3F6F01 bytes), the update disks under `/home/fsanches/compartilhado/KN7000/`, and the RE notes under `/home/fsanches/compartilhado/kn7000_mame/notes/`.

---

## Task 1 — Update-disk format (PROGRAM update, package "v16" = kn7-16)

### 1.1 File inventory (per disk half)
`/home/fsanches/compartilhado/KN7000/kn7-16/kn7-16a-files/` (disk 1) and `.../kn7-16b-files/` (disk 2) each hold four files:

| file | disk 1 size | disk 2 size | role |
|------|------|------|------|
| `JK1.SLD` / `JK2.SLD` | 1,143,233 | 945,141 | **the actual program-ROM image**, LZSS-compressed |
| `SMCKPR1.INF` / `SMCKPR2.INF` | 316 | 316 | checksum descriptor (identical on both disks) |
| `TECHNICS.PR1` / `TECHNICS.PR2` | 464 | 464 | ASCII catalog / file-type manifest (NOT image data) |
| `DUMMY.2` | 10 | 10 | literal ASCII `"Technics\r\n"` marker |

**`TECHNICS.PR*` is not the ROM.** It is a 464-byte plain-text catalog enumerating every Technics file signature (`KN7KP1 Technics KN7000 Program DATA 1/2`, `KN7KP2 … 2/2`, `KN7KT1/2 … Table`, `KN7KCT … CUSTOM DATA`, `KN7KHD … HDD-FIRMWARE`, `KN7KW1/2 … EXPANTION BOARD`, `KN7KR1/2 … RHYTHM`, `KN7KDM … DEMO`). `.PR1` leads with the `DATA 1/2` line, `.PR2` with `DATA 2/2` — a self-identifying header line + the shared catalog body. It is the model/type guard, not payload.

### 1.2 The `.SLD` container = LZSS (verified against the known ROM)
Format (documented and code-verified in `/home/fsanches/compartilhado/kn7000_extraction/kn7000_extract.py` and `FORMAT.md`):

```
off 0  : 8-byte magic  "JKPRG4K\0" (program)  |  "JKTB14K\0"/"JKTB24K\0" (table)
off 8  : 24-bit BIG-ENDIAN decompressed size
off 11 : LZSS stream — 4 KB sliding window prefilled with 0x00,
         12-bit offset / 4-bit length, min match 3 (max 18). "4K" = window size.
```
`JK1.SLD` header bytes are `4a 4b 50 52 47 34 4b 00  20 00 00 …` → magic `JKPRG4K\0`, size `0x200000`. `JK2.SLD` header size = `0x1F6F01`.

**This is the same container the KN5000 used (`SLIDE4K\0`)** — the KN7000 project's extractor is a direct adaptation of the KN5000 LZSS code.

**Verification (refutes "raw"; confirms LZSS + linearity):** running the extractor decompresses and concatenates the two halves and checks them against the on-disk `.INF` oracle:
```
JK1.SLD: 0x1171C1 compressed -> 0x200000 raw
JK2.SLD: 0xE6BF5  compressed -> 0x1F6F01 raw
checksums OK: total=0x18CE8702 and all 16 blocks match SMCKPR1.INF
-> kn7000_program.rom  (0x3F6F01 bytes)
```
So the two decompressed payloads **concatenate as a linear address image** (disk 1 = 0x000000–0x1FFFFF, disk 2 = 0x200000–0x3F6F00), *not* even/odd chip halves. FORMAT.md notes a JPEG straddles the 0x200000 seam, independently proving linearity. The even/odd split into the two physical chips is a hardware-bus detail handled below (1.4).

### 1.3 The `.INF` descriptor and validation
`SMCKPR1.INF` / `SMCKPR2.INF` are identical ASCII:
```
@18CE8702  ;  TOTAL SUM CHECK   <- 32-bit sum of every byte of the full 0x3F6F01 image
@4C81      ;  BLOCK  0          <- 16-bit sum of bytes in flash block 0 (0x40000 = 256 KB)
@0412      ;  BLOCK  1
... 16 entries (BLOCK 0..15); the last block is partial (image is 0x3F6F01, not a full 0x400000)
```
Algorithm (from `kn7000_extract.py` `parse_inf`/`verify_checksums`): `total = sum(all_bytes) & 0xFFFFFFFF`; `block_i = sum(rom[i*0x40000 : (i+1)*0x40000]) & 0xFFFF`. **There is no model-ID, version, or size field in the `.INF`** — only the checksums. The model/version guard is carried by (a) the `JKPRG4K` magic, (b) the `TECHNICS.PR*` catalog signatures, and (c) the on-image internal version (PROGRAM = **941**, dword at file 0x33660C, printed via `"PROGRAM : %4d"` at file 0x1D67E0 — `FORMAT.md §2`). The package label "v16"/"v14" is unrelated to that internal number.

**Does the on-keyboard updater validate before flashing?** The user procedure has a dedicated **CHECK pass** (see 2.2) that runs the `.INF` oracle and prints `ILLEGAL DISK` on failure or `UPDATEDISK OK` on success (install.pdf). Whether the *install* pass re-verifies is **not directly observable** — the updater routine is not in the dumped image (see 2.1). The safe assumption for a hand-built disk is to reproduce the exact `.INF` (trivially regenerated by the extractor's algorithm), so any checksum gate passes regardless.

### 1.4 Mapping to IC16/IC17 (even/odd)
The MAME driver (`/home/fsanches/compartilhado/kn7000_mame/src/mame/matsushita/kn7000.cpp:1511-1513`) loads the program region as two 16-bit-wide chips interleaved on the 32-bit bus:
```
ROM_REGION32_LE(0x400000,"maincpu",ERASEFF)                 // IC16/IC17 -> 0x48400000
ROM_LOAD32_WORD("kn7000_program_even.rom",0x000000,0x200000, CRC 529b87ce)  // IC16 = even 16-bit words
ROM_LOAD32_WORD("kn7000_program_odd.rom", 0x000002,0x200000, CRC a36e6222)  // IC17 = odd  16-bit words
```
So the *linear* image from the `.SLD` payloads (JK1=addr 0x000000-0x1FFFFF, JK2=0x200000-0x3F6F00) is de-interleaved into even-word (IC16) and odd-word (IC17) 2 MB chips — done by `rom_split_evenodd.py` for MAME, and by hardware address decoding on the real bus. The update disks split by **address range** (lower/upper half), the chips split by **word parity**; the two are orthogonal. Service manual §9.3 confirms IC16 and IC17 take the *same* flash part and "the included PROGRAM DISKs contains all programs" (SM lines 939-941).

---

## Task 2 — Flash-write path in firmware

### 2.1 The AMD flash primitives in the dump target the CUSTOM flash, not IC16/IC17
The named flash routines (symbols in `kn7000.sym`) are real and disassemble cleanly, but every one hardcodes the **custom-data-flash command window at 0x96800000** (AMD/Fujitsu 29LV160-class, unlock at 0x9680AAAA/0x96805554):

- `FlashWordProgram` **0x4847F721**: `AA→(0x9680AAAA); 55→(0x96805554); A0→(0x9680AAAA); data→(a2)` — classic AMD word-program.
- `FlashSectorErase` **0x4847F75A**: `AA/55/80→…AAAA; AA/55/30→sector` (30 = sector erase).
- `FlashReadAutoselect` **0x4847F980**: `AA/55/90→…AAAA`, then reads manufacturer/device ID at 0x96800000/0x96800002; matched against `FlashChipIdTable` **0x485CF9E0** (`MBM29LV160B`/`MX29LV160B`/`AT49BV16X4`, 0x20-byte records, sector table pointer at +8).
- `FlashProgram128Words` **0x4847F9F7** — chunk programmer; `FlashReset` **0x4847F6C7** (writes 0xF0). Each brackets the operation with library calls `0x4C03DCFA` (enter: cache/IRQ off) / `0x4C03D6BC` (exit).

These implement the **Initial Data / custom-data (IC18) install** — `AstLoadHandler 0x4852CC9E → header-ingest 0x4848594D (buffer 0x502B8000) → FAT read 0x485335FF → FlashProgram128Words 0x4847F9F7`, target read-view 0x56000000 / cmd-view 0x96800000 (`notes/initial-data-disk-and-custom-flash.md`, `FORMAT.md`). *(Note: SM §9.4.2 labels the custom-data flash **IC18**; some project notes call it "IC21" — the service manual is authoritative: IC18 = CUSTOM DATA ROM.)*

**A binary scan for AMD unlock writes by target region** (movhu of an immediate to `…AAAA`/`…5554`) finds hits **only** at 0x9680AAAA/0x96805554 — **no absolute unlock write to the program-flash region 0x484xxxxx anywhere in the dump.**

### 2.2 The program-flash (IC16/IC17) updater is NOT in the dumped image
Corroborating evidence that the resident **PROGRAM updater is absent from `kn7000_program.rom`**:
- The updater UI strings do not exist in either ROM. `strings` finds the normal disk-I/O errors ("An error has occurred while the disk was loading") but **no** `Flash Memory Update`, `ILLEGAL DISK`, `UPDATEDISK OK`, `Change Disk`, `Completed!!`-for-update, etc.
- No 0x484xxxxx AMD unlock cycles (2.1).
- The dumped image is **0x3F6F01 bytes**; the real chip is **0x400000**. The top **0x90FF (37,119 bytes)** at CPU **0x487F6F01–0x48800000 is not shipped in the update and not in the dump.** FORMAT.md §2 records that code reads a *not-shipped* top-of-flash info block near 0x7FFFE0 "written by the resident updater," and my scan finds 33 dword cross-references from dumped code into 0x487Fxxxx, several past the dump end (0x487FEA00 ×6, 0x487FFC48 ×2, 0x487FA700, 0x487FBC00, 0x487F825D — all in the missing region).

**Conclusion:** the routine that erases+programs IC16/IC17 (plus its FDC reader, LZSS decompressor, and version block) lives in the **un-dumped top ~0x90FF resident block**, which the PROGRAM update never rewrites (it writes only 0x000000–0x3F6F01). It is RAM/register-indirect relocated (that is why no absolute 0x484xxxxx command writes appear — the base 0x48400000 is loaded into an address register), and it must run from RAM or the aliased library window while erasing the flash it lives above. **This is itself a preservation finding: the current `kn7000_program.rom` is the *update payload*, not a full chip dump — a real IC16/IC17 readback would recover the missing 37 KB resident updater + version block that we do not currently have.**

### 2.3 How the updater is entered (official, from the service manual + install.pdf)
- **Version display:** hold SOUND-GROUP `[PIANO]+[GUITAR]+[MALLET & ORCH PERC]` during power-on → version shown bottom-right (install.pdf).
- **CHECK the disks (verify only):** insert disk 1, hold **PANEL MEMORY 2-3-4** during power-on → runs the `.INF` oracle; `ILLEGAL DISK` = bad, else `UPDATEDISK OK, COMPLETED` after disk 2 (install.pdf, CA-Software).
- **INSTALL (erase+flash):** insert disk 1, hold **PANEL MEMORY 1-2-3-4** during power-on → LCD shows `Flash Memory Update`, release keys, it auto-writes, prompts `Change Disk 2/2`, finishes `Completed!!`, then "turn power off and on" (SM §9.4.1, lines 943-960; install.pdf §4).
- **Post-update re-init (wipes user data except Custom):** hold RHYTHM `[60s & 70s]+[MODERN DANCE]+[SOUL & R&B]` at power-on (install.pdf).

Entry is therefore a **power-on key combo**, not automatic-on-disk-insert. The panel-memory combo is read at boot; the boot/kernel-init path (reset vector 0x48400000 → `jmp 0x4840FF7E` hardware init → `call 0x484D7111` kernel init, all in the dumped image) is where that check must branch into the resident updater.

### 2.4 What a hand-built update disk must contain
Reproduce the shipped structure exactly and regenerate the derived fields: (1) two floppies, each with `JKn.SLD` (magic `JKPRG4K\0` + 24-bit BE decompressed size + valid LZSS stream), `TECHNICS.PRn` catalog (byte-for-byte from the originals), `SMCKPRn.INF` (regenerated: 32-bit total + 16×0x40000 block sums of the *new* image), and `DUMMY.2`; (2) split at the 0x200000 boundary (disk 1 = 0x000000-0x1FFFFF → 0x200000 raw; disk 2 = remainder). The extractor already contains the inverse of every step, so a packager is a small addition (LZSS-compress + emit `.INF`).

---

## Task 3 — ROM-backup strategy (ranked by safety/reversibility)

### (a) Modified PROGRAM update image with an added backup routine — RECOMMENDED
**Mechanism.** Start from the verified linear image (0x3F6F01). Insert the backup routine into existing slack — the image has **36 runs of ≥256 bytes of 0xFF totaling ~71 KB** of unused space, enough for a compact reader + output driver. **Trigger it without touching the boot path** by repointing one entry of the service test-menu function-pointer table (`0x4874AD34–0x4874AFF0`, e.g. `WaveRomTestRunFunc@…AF90` or `MainSDTestFunc@…AFF0`, per `notes/service-diagnostic-mode.md`) to the new routine. Recompress → JK1/JK2, regenerate `.INF`, install via PANEL MEMORY 1-2-3-4.

**What it can read once running on the MN10300.** Everything the firmware can address: program flash `0x48400000`, table flash `0x48000000`, self-loaded library RAM `0x4C000000`/`0x8C000000`, work RAM `0x50000000+`, custom-data flash `0x56000000` (read view), factory-data flash `0x57000000`, picture flash `0x57800000`, **wave ROMs via the 0x9804x/0x9805x readback window** (Task 5), and the output peripherals (FDC 0x34001xxx, MIDI TX 0x34000818, SD via 0x90200000 + CPSD).

**Risk.** Same class as an official update: the reset vector and boot code live in the rewritten 0x000000–0x3F6F01 range, so a power-loss mid-flash or a corrupted boot path can brick the ability to re-enter the updater (recoverable then only by chip replacement/JTAG, SM §9.2). Keep the entire boot + panel-combo→updater path **byte-identical** to the original and confine edits to slack + one menu pointer to hold the risk at the official-update level.

**Restore.** Fully reversible: re-flash the pristine `kn7-16a/b` disks (PANEL MEMORY 1-2-3-4). The resident updater at the top 0x90FF is never touched by either flash.

### (b) Non-reflashing "load code from disk and run it" — NOT AVAILABLE
The disk dispatcher `DiskLoadDispatch 0x4852CFE4` walks `DiskFileHandlerTable 0x486642B0`, keyed by extension (`DiskFileExtTable 0x48664438`: MD/FAV/HMP/AST/SQF/SEQ/ACT) and tag (`DiskFileTagTable 0x48664090`: `JK`, `J K`, `TCMP`, `TPAD`, `KN7000 SOUND RAM`). Every handler loads *data* into RAM buffers (e.g. AST → 0x502B8000) and parses it; **none is an executable/"jump to loaded code" type.** The debug `DbMemoryDumpProc 0x484878AC` is an on-LCD RAM hex viewer (range ~0x50001–0x600B4), not a bulk exporter. So there is **no shipped code-injection path short of the program-flash update** — (a) is the only route to run custom code.

### (c) SD-based equivalent — POSSIBLE ONLY AS OUTPUT, not as a code channel
See Task 4: SD cannot install/run code, but a routine already running via (a) can use the firmware's SD file-write path as its output sink (best for large dumps).

---

## Task 4 — SD as an update / code channel

**Can SD install system updates or load+run an executable? No, not today.** The main↔SD link is **SIO channel 2** (`0x34000820` TX/cfg, `0x34000828` RX, `0x3400082C` status; RX ISR `0x484B2037`, group 0x14, ICR `0x34000150`), talking to the **CPSD sub-CPU IC401 `MN102H60KTA`** + SD host controller **IC402 `MN67737`** (register bank at `0x90200000`) — `notes/sd-card-emulation-plan.md`. The firmware's SD surface is **file/content only**: `SDCardInfoFunc 0x4855D901`, SD-Audio/SD-Song playback, `SdcSmfLoadAsFunc 0x4855AE81`, save paths, `MainSDTestFunc 0x484A3C5F`. There is **no SD path that flashes IC16/IC17 or jumps to loaded code** — the program-update entry is FDD-only (PANEL MEMORY 1-2-3-4 reads the floppy), and the resident updater (Task 2.2) has no SD reader we can see.

**What would have to be true to enable it:** the resident updater would need an SD (CPSD-served) file reader in addition to its FDC reader — a firmware change on the main CPU. Since CPSD firmware is a separate undumped mask ROM, it already exposes file read/write over SIO ch2 (that is how SD-Audio/Song load), so **no CPSD change is needed**; only the main-CPU updater would need to accept the `.SLD` stream from an SD file instead of floppy. **Minimum change to enable it:** add, inside a custom program image installed via route (a), a small loader that opens a file on SD through the existing SD-file API and feeds it to the same install logic — i.e. SD becomes usable as an update/output channel *only after* one FDD-delivered custom firmware bootstraps it.

**Practical SD use for backup:** a routine from (a) writes the dump to an SD card via the firmware's SD save functions. On real hardware the SD path works (it is only the MAME HLE that is currently stuck pre-init); a GB-class card trivially holds the full wave set.

---

## Task 5 — What a backup routine can read, and how to get it out

### 5.1 Directly bus-readable ROMs (plain loads, no window)
- Program flash **0x48400000** (IC16/IC17, 4 MB) — *and* this recovers the missing top 0x90FF resident block that the update payload lacks.
- Table flash **0x48000000** (0x3E94D4).
- Custom-data flash **0x56000000** (IC18, read view).
- Factory-data flash **0x57000000**, picture flash **0x57800000** (IC19).
- Self-loaded library/kernel **0x4C000000** (already inside the program flash, but worth capturing as executed).

### 5.2 Wave ROMs via the readback window — CONFIRMED it yields raw samples for all four ROMs
Disassembly of the service wave-ROM checksum routine **0x4848399E–0x48483B0A** (confirming the given I/O map) shows a per-tone-generator page/offset/data window:

| register | main TG (IC203/IC204) | sub TG (IC207/IC208) | meaning |
|---|---|---|---|
| page | `0x98040006` | `0x98050006` | write `0x8000 \| page`; `page = byteaddr >> 15` (bit15 = read-enable latch) |
| offset | `0x98040008` | `0x98050008` | write `0x8000 \| byte_offset`; inner loop 0x0000→0x7FFE step 2 (0x8000-byte page) |
| data | `0x9804000A` | `0x9805000A` | **read** the 16-bit sample word |

The routine's inner loop reads `movhu (0x9805000A),d0` (raw 16-bit sample) and merely *sums* hi+lo bytes into a checksum; a backup routine substitutes "store the word" for "add to checksum" — identical addressing, different sink. The page field is 15 bits and the offset covers a full 0x8000-byte page, so the window addresses **each tone generator's entire wave space** (both of its ROMs appear as one contiguous page range). The service dispatcher `MainWaveRomTestFunc 0x484A2E3A → wrapper 0x48483B63` switches over **20 region indices (0..0x13)** and calls the readback for each, i.e. it already walks all banks of both TGs — proving the window pages every bank, not one checksum blob. **So yes: raw sample data for the full wave set is reachable; the checksum is only what the *test* does with it.**

Wave ROM identities (SM lines 5013-5077): IC203 `C3CBQD000002`, IC204 `C3CBQD000001`, IC207 `C3CBQD000004`, IC208 `C3CBQD000003`. **Total size caveat:** the task's "~64 MB" is plausible and consistent with a `0x02000000` (32 MB)-per-TG constant seen in the test dispatcher (×2 TGs = 64 MB); the MAME driver's current `4×0x400000 = 16 MB` reservation (`kn7000.cpp:1534-1538`) is a placeholder. The exact per-ROM capacity needs the C3CBQD mask-ROM datasheet — **not found** in the service manual text. The readback window itself is not the limiter (15-bit page × 0x8000 = up to ~1 GB per TG), so a backup routine can dump whatever the real ROMs actually contain.

### 5.3 Output channels — practicality for ~64 MB + the small ROMs
- **SD card (via CPSD/MN67737, firmware SD-save API):** the only practical sink for tens of MB. GB-class media; native firmware support. **Recommended for the wave ROMs.**
- **Floppy (FDC 0x34001xxx, firmware disk-save):** 1.44 MB/disk → ~45 disks for 64 MB (impractical for wave data) but fine for the smaller ROMs (program/table/custom/picture) in a few disks.
- **MIDI SysEx bulk-out (TX byte reg 0x34000818, 31,250 baud ≈ 3.1 KB/s):** ~6 hours for 64 MB — usable but slow; a PC captures the stream. Good/simple for the small ROMs; borderline for wave data. There is **no ready-made ROM-bulk-dump SysEx routine** in the firmware (`RhySysexLen 0x484403CD` is only rhythm-pattern length), so the routine must emit its own SysEx framing.

Recommended split: small ROMs → floppy or MIDI (no extra hardware); wave ROMs → SD.

---

## Task 6 — Concrete sketch

### 6.1 Backup routine (runs on MN10300 after install via 3(a))
```c
/* Entry: reached by repointing a service-menu handler pointer in
   0x4874AD34..0x4874AFF0 (e.g. the WaveRomTest slot) to this routine.
   Uses only firmware/library facilities already proven present. */

/* ---- readback of ONE tone generator, mirroring 0x4848399E ---- */
static void dump_tg(volatile u16 *base /* 0x98040006 main | 0x98050006 sub */,
                    u32 nbytes, sink_t out)
{
    volatile u16 *PAGE = base;       /* +6 */
    volatile u16 *OFF  = base + 1;   /* +8 (16-bit stride) */
    volatile u16 *DATA = base + 2;   /* +A */
    *PAGE = 0x8000;                  /* enable read/latch (as the test does) */
    for (u32 a = 0; a < nbytes; a += 2) {
        u16 page = (a >> 15) & 0x7FFF;
        u16 ofs  =  a & 0x7FFE;
        *PAGE = 0x8000 | page;       /* select page  */
        *OFF  = 0x8000 | ofs;        /* select word  */
        out_word(out, *DATA);        /* RAW sample word -> sink */
    }
    *PAGE = 0;                       /* clear latch (test does this too) */
}

void backup_all(void)
{
    sink_t out = sink_open_sd("KN7000.WAVE");   /* firmware SD save API */
    dump_tg((u16*)0x98040006, WAVE_TG_BYTES, out);  /* IC203+IC204 */
    dump_tg((u16*)0x98050006, WAVE_TG_BYTES, out);  /* IC207+IC208 */
    sink_close(out);

    /* directly-mapped ROMs: plain memcpy to a second sink */
    dump_mem(0x48400000, 0x00400000, "PROGRAM.BIN");  /* full IC16/17 incl. top 0x90FF */
    dump_mem(0x48000000, 0x00400000, "TABLE.BIN");
    dump_mem(0x56000000, 0x00200000, "CUSTOM.BIN");
    dump_mem(0x57000000, 0x00200000, "FACTORY.BIN");
    dump_mem(0x57800000, 0x00800000, "PICTURE.BIN");
    halt_and_prompt("BACKUP COMPLETED - TURN OFF");
}
```
`WAVE_TG_BYTES` = the real per-TG size (set from the datasheet; start conservative and grow, or probe by walking until data mirrors/zeros). `dump_mem` is a `movhu`/`mov` copy loop; `sink_*` wraps either the SD save path or a self-written MIDI-SysEx emitter on 0x34000818. Real entry points to reuse: library `memcpy`-family `0x4C003051`, FAT sector I/O near `0x485335FF`, SD status `0x4855D901`.

### 6.2 Modified-update-disk packaging (reversible)
```
1. img = extractor.decompress(JK1)+decompress(JK2)         # 0x3F6F01, verified
2. place backup_routine into a >=256B 0xFF gap in img       # ~71 KB slack available
3. patch ONE service-menu pointer (0x4874AD34..0x4874AFF0) -> routine addr
   (leave reset vector 0x48400000, boot 0x4840FF7E, kernel-init 0x484D7111,
    and the panel-combo->updater path byte-identical)
4. JK1' = "JKPRG4K\0" + BE24(0x200000) + LZSS(img[0:0x200000])
   JK2' = "JKPRG4K\0" + BE24(len-0x200000) + LZSS(img[0x200000:])
5. INF' : "@%08X ; TOTAL SUM CHECK" % (sum(img)&0xFFFFFFFF)
          + 16x "@%04X ; BLOCK n"   % (sum(img[n*0x40000:(n+1)*0x40000])&0xFFFF)
6. disk1 = {JK1', SMCKPR1.INF=INF', TECHNICS.PR1 (verbatim), DUMMY.2}
   disk2 = {JK2', SMCKPR2.INF=INF', TECHNICS.PR2 (verbatim), DUMMY.2}
7. install: PANEL MEMORY 1-2-3-4 + power on
8. restore anytime: re-flash pristine kn7-16a/b disks (same key combo)
```
Every step is the inverse of a step already implemented/verified in `kn7000_extract.py`; only an LZSS *compressor* and the `.INF` emitter are new code.

---

## Key uncertainties (stated, not guessed)
- **Resident PROGRAM updater internals** (exact validation it performs, its FDC reader, its LZSS decompressor, whether it re-verifies the `.INF` on install): **not directly observable** — that code is in the un-dumped top 0x90FF (0x487F6F01–0x48800000). Backing up the real IC16/IC17 is what would recover it.
- **Wave-ROM total size:** **not found** in the service-manual text; 16 MB (MAME placeholder) vs ~64 MB (task figure / 32 MB-per-TG test constant) unresolved. The readback window can address far beyond either, so it does not constrain the backup.
- **Brick risk of route 3(a):** real but bounded to the official-update level *iff* the boot/updater-entry path is left byte-identical; the resident top block is never erased, and the original disks always re-flash.
- Custom-flash IC designator: SM §9.4.2 says **IC18**; some project notes say "IC21" — service manual takes precedence.

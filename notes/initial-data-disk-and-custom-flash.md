# The Initial Data disk + the (unmodeled) custom-data flash — reframes the style bug

The user asked whether the empty style region could be a **flash ROM populated from the
"Initial Data" floppy disk**. The answer is **yes**, and it is confirmed directly by the
KN5000 driver (shared codebase) and by the KN7000 Initial Data disk contents.

## KN5000 evidence (the reference architecture)
`kn5000.cpp` defines separate memory regions for distinct physical chips:
```
map(0x300000,0x3fffff) custom_data   // 8Mbit FLASH ROM @ IC19 (CS5)
map(0x400000,0x7fffff) rhythm_data    // 32Mbit ROM @ IC14
map(0x800000,0x9fffff) table_data     // 2*8Mbit ROMs @ IC1, IC3
map(0xe00000,0xffffff) program        // 2*8Mbit FLASH @ IC4, IC6
map(0x1e0000,0x1fffff) backup SRAM    // 1Mbit SRAM @ IC21 ("ERROR in back-up SRAM")
```
And the load comment for IC19 is decisive:
> "IC19 is a flash ROM. The contents here were dumped from a system that had it already
> **programmed by the initial data disk**."

So on the KN5000, the **custom_data flash (IC19)** is written by the *initial data disk*;
its dump was obtained from a real, already-programmed unit. The program/table/subprogram
regions come from *system-update* floppies (LZSS-compressed .SLD payloads) — a **separate**
data source from the initial-data disk.

## KN7000 Initial Data disk (idd7000) — the source data
`/home/fsanches/compartilhado/KN7000/idd7000/idd7000-files/` (extracted from idd7000.exe):
```
01CTMINI.AST  320498 B  -- "CusTom" INItial; 1260 0xF5 style-record markers + embedded
                           abs pointers (0x485A9C1D program-ROM, 0x5006ED88 RAM). = style/
                           custom data.
02UMDINI.MD      640 B  -- header "JK "
03FAVINI.FAV     408 B  -- Favorites INI: names " Cool Sounds ! "/" Cool Rhythms ! "/
                           "  Entertainer  "/"    Example    "
04HPGINI.HMP   17474 B  -- Home-Page/help INI
```
All four begin with the Technics **"JK"** block marker (`4A 4B`/`4A 20 4B`) — the SAME
marker as table-ROM directory entry [6] @0x4806EA98 and the ZZZ/JK sections. So the
Initial Data files share the on-flash block format. `01CTMINI.AST`'s 1260 `f5` records are
the same record marker as the rhythm/genre style records (0x4804AF61) and the program-ROM
user-style area (0x4872AB44).

## What this means for the emulator (and the style bug)
- **The KN7000 has a custom-data flash (the analog of KN5000 IC19) that is programmed by
  the Initial Data disk (idd7000).** The current KN7000 MAME driver models only two flash
  regions — `table` (0x48000000) and `maincpu`/program (0x48400000), both derived from
  .SLD *update* payloads. It does **NOT** model the custom-data flash. So the Custom Panel,
  Favorites, Music Stylist customs — and plausibly the rhythm/Composer style working set —
  are **absent** in emulation, which is why they fall back to defaults (e.g. "8 Beat 1").
- This complements the tick-5 finding (style list parsed from an EMPTY 0x96800000 window):
  the missing custom-data flash is a strong candidate for *why* that working set is never
  populated — either the region IS the custom flash, or the copy that fills 0x96800000 is
  gated on the initial data being installed.

## Answering the two questions
1. **Could 0x96800000 be a flash ROM?** The KN7000 certainly has unmodeled flash/ROM chips
   beyond the two mapped (mirroring KN5000: custom_data flash, rhythm_data ROM, waveform
   ROMs). The driver *labels* 0x90000000-0x97ffffff as LCD V-RAM and the firmware copies
   table-ROM data into it, so that specific window looks like a work/VRAM buffer rather than
   flash — but the general premise (an unmodeled flash holds the style/custom data) is
   correct; the custom-data flash is a distinct region whose KN7000 address is still TBD.
2. **Could such flash hold Initial-Data-disk data?** **Yes, definitively** — that is exactly
   what the KN5000 IC19 custom_data flash is ("programmed by the initial data disk"), and
   the KN7000 idd7000 disk (01CTMINI.AST custom/style data, 03FAVINI.FAV favorites, …) is
   the KN7000's initial data.

## Next steps
1. Find the KN7000 **custom-data flash region address** (trace where the firmware reads
   custom/initial data, or where the idd7000 install writes) and add a `ROM_REGION`/`map`
   for it in kn7000.cpp — mirroring the KN5000 `custom_data` region.
2. Obtain its contents: ideally a **dump of a programmed KN7000 flash** (as KN5000 did for
   IC19), OR replicate the disk-install by parsing the idd7000 `.AST`/`.FAV`/… files into
   the on-flash layout (cf. felipesanches/kn5000_homebrew kn5000_extract.py for the KN5000
   equivalent). The `01CTMINI.AST` embedded absolute pointers suggest the file is close to a
   RAM/flash image snapshot, which may map in with light transformation.
3. Re-test: with the custom flash populated, the rhythm/Music-Stylist/Favorites screens
   should show real entries instead of defaults.

## Extractor + dispatch table (tick: idd7000 extractor)
Built `extract_idd7000.py` (committed in the sibling `kn7000_extraction` repo) — a first-
pass inspector of the idd7000 files. It decoded: 4 favorites ("Example"/" Cool Sounds ! "/
" Cool Rhythms ! "/"  Entertainer  ", each ~10 {type,value} settings referencing built-in
AND 0x20xxxx CUSTOM style-IDs), 69 user style-IDs in 02UMDINI.MD, and 1260 0xF5-records in
01CTMINI.AST. The firmware's **disk-file-type dispatch table is at program-ROM 0x48664090**
(tags "JK "/"J K"/"TCMP"/"TPAD"/"KN7000 SOUND RAM"). Remaining for a MAME-loadable custom
flash image: the install-to-flash transformation (which flash offset each file lands at;
whether the body is reformatted into the 0x56000000 directory-archive layout) — under RE
via a workflow. Once known, the extractor emits kn7000_custom.rom for the driver ROM-set
(map at 0x56000000, replacing the current read-as-0 placeholder).

## CONFIRMED (workflow salvage + direct verify): the custom flash is 0x96800000
The install-RE workflow died (2nd background workflow to die at a turn boundary) but its
scout transcripts held verified leads, confirmed directly:

### 0x96800000 = the ONE writable custom flash (AMD/Fujitsu command set)
The firmware issues flash unlock/program sequences to **0x9680AAAA** (7 ROM refs) and
**0x96805554** (4 refs) -- the classic AMD 0x555/0x2AA unlock addresses scaled for a
16-bit part (matches the flash-ID strings MBM29LV160B/MX29LV160B/AT49BV16X4 = 16Mbit/2MB
flashes). So **0x96800000-0x969FFFFF is the writable custom flash**, programmed by the
"Initial Data" disk. The mid-level install routine **0x4849FD40** copies the data in
0x80-byte blocks via **0x4847F9F7** (the same 0x96800000 helper found in tick 5) --
confirming the tick-5 "0x96800000 is empty" observation was pointing at the RIGHT region:
it is the custom flash, mis-modeled by the driver as blank RAM inside the 0x90000000-
0x97ffffff "vram" mapping. Library flash primitives: 0x4C024003 / 0x4C024033 (called by
SdcSetupFlashFunc with a section index).

### CORRECTION to last tick
0x56000000 / 0x57000000 are the FACTORY read-only data flashes (rhythm/wave data), NOT
the custom flash. The writable custom flash the idd7000 disk programs is **0x96800000**.
(My tick-6 driver map of 0x56000000 as "dataflash" is still an OK placeholder for those
undumped read-only flashes, but the comment is corrected.)

### Disk-file dispatch is by EXTENSION
Table @0x48664438: extension strings "MD ","FAV","HMP","AST","SQF","SEQ","ACT" (4 bytes
each) with a handler-pointer array at 0x48664454. So MD/FAV/HMP share the "JK " magic and
are disambiguated by the file EXTENSION (.MD/.FAV/.HMP), while .AST uses the "J K" magic.
The KN7000 disk data types are thus: MD (memory), FAV (favorites), HMP (home page), AST
(custom/style), SQF/SEQ (sequencer), ACT (?).

### The unified rhythm-name-bug picture
Genre table 0x48735EE4 works -> style-IDs -> the style NAME/data is read from the custom
flash at 0x96800000, which is EMPTY in emulation (mis-modeled as blank vram) -> every
style name defaults to "8 Beat 1". The idd7000 disk (esp. 01CTMINI.AST, declared size
0x1e0000 ~ 1.9MB) is the source that programs 0x96800000. FIX = model 0x96800000 as an
AMD 29LV160-class flash device (MAME has intelflash/amd flash) with the installed
content, OR a ROM region preloaded with a dump/extractor output; then re-test.

### Next
1. Trace 0x4849FD40's caller + source to learn the disk-file -> 0x96800000 flash layout
   (how .AST/.MD/.FAV data maps to flash offsets; whether the body is decompressed).
2. Extend extract_idd7000.py to emit a 0x96800000 (2MB) flash image; map it in kn7000.cpp
   (split it out of the vram range) and re-test Favorites/rhythm names.

## AUTHORITATIVE install architecture (idd7000 workflow COMPLETED, 5/5 agents, byte-verified)
The 2nd install-RE workflow did NOT die -- it was just slow (a ~50-min straggler scout);
it completed with a byte-verified spec. This settles the addressing (I had flip-flopped):

### The custom flash = ONE chip, two apertures
- **0x56000000 = custom-flash READ view** (disk-programmed data; archive parser 0x4844A000,
  u32-offset directory at flash-offset 0x200). THIS is the MAME ROM_LOAD base for the image.
- **0x96800000 = custom-flash COMMAND/PROGRAM window** (the ONLY base with AMD unlock stores
  0x9680AAAA/0x96805554). Driver routines: word-program 0x4847F721, sector-erase 0x4847F75A,
  read-ID 0x4847F980, reset 0x4847F6C7, 128-word chunk-prog 0x4847F9F7, addr->sector
  0x4847E7C0; each wrapped by a libROM critical section (~0x4C03DCFA / ~0x4C03D6BC).
- **0x57000000 = FACTORY read-only** rhythm/style flash (extends table ROM 0x48000000).
- Chip: AMD/Fujitsu x16, 2MB/16Mbit bottom-boot (MBM29LV160B / MX29LV160B / AT49BV16X4;
  descriptor table 0x485CF9E0, sector map 0x485CF788: 16K/8K/8K/32K + 64K x N = 0x200000).

### Only the AST installs to flash; it is COMPRESSED (codec = the blocker)
Dispatch: LOAD dispatcher 0x4852CFE4 -> handler table 0x486642B0 -> AST("J K",type10)
handler 0x4852CC9E. Install (0x4848594D..): validates internal type byte==0x17, bounds the
declared size vs 0x1E0000, reads the file into SDRAM scratch **0x502B8000** (0xC0000 work
size), then programs flash from there via libROM 0x4C003039. The AST payload [0x08..EOF] is
**opaque/high-entropy (~7.998 b/byte)**; header[4:8]=0x001E0000 is the DECLARED (expanded)
size (~6:1 vs the 320KB file). So the firmware DECOMPRESSES/decodes the AST and re-serializes
it into the 0x56000000 directory-archive layout before programming. **That codec is NOT yet
reversed** -- it is the one blocker to emitting the 2MB flash image. (The "embedded pointers"
0x485A9C1D/0x5006ED88 I noted earlier are NOISE, not fields.)

### FAV/MD/HMP -> battery SRAM (NOT flash) -- separately loadable NOW
- 03FAVINI.FAV: 4x 100-byte records {name[16] + u32 lead + 10x(u32 param,u32 value)};
  param 3=style/sound ID, 4=rhythm ID, 2=terminator. Install dest = SRAM favorites bank
  directory **0x5008FDCA** (40x 34-byte {name[16], u16 items[9]}), block base 0x50083D72
  magic "KN7000 SDDIR INF".
- 02UMDINI.MD: 44x u32 style-IDs + 3x 144-byte units -> SRAM user-memory.
- 04HPGINI.HMP: 64x 6-byte hotspot records + an embedded **BMP** (160x100 8bpp) at 0x18C.

### Extractor status (extract_idd7000.py)
CAN emit today (byte-exact): the FAV/MD SRAM images, the HMP hotspots + carved BMP, and the
AST header + raw opaque payload. CANNOT yet: the 2MB custom-flash image (needs the AST codec).
NEXT: (1) reverse the AST codec (trace 0x4C003039 / the SDRAM 0x502B8000 decode); (2) model
0x56000000 as the custom flash + ROM_LOAD the image; (3) optionally load FAV/MD/HMP as a
separate NVRAM to get Favorites working before the flash codec is cracked.

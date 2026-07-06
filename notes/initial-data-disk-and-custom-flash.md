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

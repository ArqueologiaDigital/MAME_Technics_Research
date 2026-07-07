# Rhythm style-list bug ("all slots show 8 Beat 1") — traced to the table ROM

The rhythm-selection screen (e.g. RHYTHM / BALLAD) shows every style slot as
"8 Beat 1" instead of distinct names. Earlier work proved this is **not** a udf /
CPU-core bug (implementing udf00 did not change it; udf07 is math-only). This note
traces where the style list is built and where the names come from.

## The functions (from kn7000.sym)
- `MainGetRhythmName` 0x48416204 — a **per-ID** name getter: `cmp 0x60056,d1 ; bne
  +` → returns a name only for `d1==0x60056` (via library calls 0x4c014948 →
  0x48433c23), else `clr d0 ; ret` (NULL). Adjacent per-ID getters follow
  (0x4841622e handles 0x60057, …). So names are resolved through a framework of
  small per-message getters, not one table lookup.
- `AcCtgStyleListBoxProc` 0x4847BCCA — the genre ("category") style **list-box**
  proc. It is a GUI **message dispatcher**: validates arg `d1` in 0x50001..0x1550001,
  subtracts 0x50000, hashes `(d1 & 0xf)*8` into an 8-byte-record table at
  **0x485CF408** (`[key u32][handler u32]`, keys like 0x01500000/0x00000001, handlers
  0x4847bxxx) to find the handler for the current message (init/draw/select/populate).
- Siblings: `AcAlpStyleListBoxProc` (alphabetical), `AcEraStyleListBoxProc` (era),
  `AcCustomStyleListBoxProc`, `AcStyleNameProc` 0x4847B221, `AcRhythmNameProc`
  0x4841F3A0, `MoreStyleFunc` 0x4847F24B.

## Where the built-in style DATA lives = the TABLE ROM (the key finding)
`kn7000_table.rom` is mapped at **0x48000000-0x483FFFFF** (driver `map(...).region
("table")`, "Table / rhythm flash") and is flagged **BAD_DUMP** (CRC eb3a0f01, the
decompressed 0x3E94D4-byte image). It **contains the real built-in style names**:
```
"Easy 8 Beat" @0x48035D7E, "16 Beat" (x2), "Ballad" (x13), "Waltz" (x17), "March" (x11) ...
```
A memory read-tap over 0x48000000-0x483FFFFF during the BALLAD rhythm menu shows the
list build **reads the table ROM 269,228 times, spanning 0x48000000..0x483E8F74**
(essentially the whole 4 MiB). So the build is actively scanning the table-ROM style
data — yet the on-screen names default to "8 Beat 1" (which is NOT a table-ROM string;
the table-ROM name is "Easy 8 Beat"). The displayed default comes from RAM/program-ROM
current-style state, not from the styles being scanned.

## Sources RULED OUT as the display source
- 0x4872ABxx (program ROM) — the **user-style memory** area (records with `f5` marker
  + "8 Beat 1    ", empty slots `f4`). A read-tap over 0x4872A000-0x4872CFFF got
  **0 reads** during the menu → not the built-in-style source.
- 0x485Cxxxx (program ROM) — a **flash-chip-ID** table ("MBM29LV160B"/"MX29LV160B"/
  "AT49BV16X4"), a red herring caught by an earlier tap.

## Table ROM integrity — it looks LARGELY INTACT (weakens the bad-dump theory)
Header @0x48000000 is a clean **directory of ascending u32 offsets** (0x00000200,
0x00034858, 0x00035d08, 0x00040674, 0x0004238c, … monotonic) — a valid sub-section
index, not garbage. The image is only **1.8% 0xFF** (73148/4101332 bytes), the tail
near the read-hi (0x483E8F74) is real data, and the style name strings are intact.
So despite the BAD_DUMP flag, the table ROM is mostly well-formed. A wholesale
"corrupt ROM → list fails" explanation is therefore **not well supported**.

## Conclusion (nuanced)
The screen shows 10 populated slots (not blanks), all resolving to the default
"8 Beat 1" — so the list IS built with 10 entries, but every entry's **per-slot
style-ID or name resolution is uniformly stuck at the default**. The build reads the
(largely valid) table ROM 269K times yet none of the read style data reaches the
displayed names. This looks less like a corrupt-dump data loss and more like a
**parse/build defect or a dependency on state that is wrong in emulation** (a per-slot
index computed as 0, a "current genre's style count" read as 0/garbage, or a value
from an unmodeled device/RAM region). The bad-dump remains a *possible* contributor
(one wrong field in an otherwise-intact image could still break a specific record the
build keys on), but is no longer the leading explanation.

## Next steps
1. Trace the actual failure point: which specific value makes every slot index 0?
   Set a read-tap narrowed to the style **directory/count** the build keys on
   (a subsection pointed to by the 0x48000000 header) and see whether the build reads
   a plausible style count or 0. Or watch the arg `d1` passed per slot into the name
   getter (needs a debugger/execution trace, since a read-tap can't see it).
2. Check whether the per-slot loop in the list-box **populate** handler (one of the
   0x4847bxxx handlers in the 0x485CF408 dispatch table) increments the style index
   or leaves it constant.
3. Rule the table ROM in/out: force-swap a couple of style-record bytes and see if the
   default name changes; if a good `kn7000_table.rom` is ever dumped, re-test directly.

## Method notes (for the next tick)
- MAME Lua read-tap works: `cpu.spaces["program"]:install_read_tap(lo, hi, "n", cb)`.
  Caveats: the **end address must have its low 2 bits set** (e.g. 0x483FFFFF, not
  0x48400000); do **not** access CPU state (`cpu.state[...]`) inside the callback — it
  segfaults (reentrant). Record offsets/counts only; print + `m:exit()` at a set time.
- Press a genre to open the menu: set `SEG00` mask 0x10 (BALLAD) at t≈17.3, sample at
  t≈18.7.

## Execution-trace results (PC-triggered register log in the CPU core)
Added a temporary trace to mn10300.cpp's fetch loop (`switch(start_pc){case ...:
logerror regs}`) for four candidate name functions, pressed BALLAD, captured -log.
Findings (the trace hook has since been reverted):
- **Only `AcRhythmNameProc` (0x4841F3A0) fired — 5×** with `a2=0x5000757C` (the live
  UI object table) and `d1` = **distinct** IDs: 0x50001, 0x50002, 0x60021, 0x350002.
- `MainGetRhythmName` (0x48416204), `AcStyleNameProc` (0x4847B221), and
  `AcCtgStyleListBoxProc` (0x4847BCCA) did **NOT** fire during the menu at all.

### AcRhythmNameProc is the CURRENT/FOCUSED-rhythm-name path, not the 10-slot list
AcRhythmNameProc dispatches on the style ID (cmp 0x50001/0x50009/0x50014/0x6003a,
else default 0x4841F447 → resolver **0x48429569** → **0x48414A4F**). Disassembling
0x48414A4F: it **ignores the passed style ID** and instead returns the *current task's
focused-object id*:
```
a2 = *0x50380004 (currently-running task handle)
a1 = *0x5038002C (main task handle)
idx = (a2==a1) ? *0x500D3C60 : *0x500D3C5C   ; main-task vs AP-task focused-object id
```
(all normal workram per the driver map/comments — not an unmodeled device). 0x48429569
then indexes the UI object table `0x5000757C + idx*0x38` and reads the object's name.
So this resolves the **focused/current** rhythm object's name (title/status area), and
it fired only 5× with scattered IDs — **it is not the per-slot list drawer**.

### Where the 10-slot list actually comes from (still open)
Since neither the style list-box procs nor these name getters populate the 10 visible
slots, the list is drawn by a different mechanism — most likely a **generic list
widget** whose items were **populated once when the menu opened** (on the BALLAD key
press), each item holding a pre-resolved name string/pointer. If population wrote the
same default name into all 10 items, the per-frame draw faithfully shows 10×"8 Beat 1".

### Next (concrete)
1. Trace the **menu-open / populate** path: put the PC-trigger on the BALLAD-key
   handler and on the list-item **add** routine (or on the text-render function with
   its string-pointer arg) to catch all 10 slot names + their source addresses in one
   pass. The population runs once, so trace from the key press (t≈17.3) with a short
   window.
2. Find the list-item store: search for writes into the list-widget's item array
   (near 0x5000757C UI objects) right after the genre key press.
Trace method that works (reuse): temporary `switch(start_pc){case TARGET: logerror(
"...", m_d[0..3], m_a[0..2]);}` right after `start_pc = m_pc` in the fetch loop; build
CPU only; run in background (>120s, the Bash tool's own limit kills a foreground run);
NB the udf07 unimplemented log also writes ~420K lines/boot, so filter by "RNTRACE".

## Render-trace attempt (tick 3): the menu text does NOT use DrawString/list-box procs
Traced (PC-trigger in the fetch loop, since reverted) all six `DrawString*` variants
(0x48425393/896/97A/9F3/ABF/B18) with the string ptr (a0) + string bytes, plus the
generic list-box procs `AcListBoxProc` 0x48419E34 / `PsListBoxProc` 0x484198B4, over a
full boot + BALLAD-menu render (snapshot confirms the menu shows "8 Beat 1"×10).
**Result: ZERO calls to any of them.** `DrawString` also has **0 static call sites**
(no `cd`/`dd` targets it). So the KN7000 renders on-screen text through a **different,
lower-level path** — a char/glyph blit or a routine in the self-loaded library ROM
(0x4C000000, whose PCs a program-ROM trace can't see), not these DrawString wrappers.
The style list-box procs (AcCtgStyleListBoxProc etc.) never fire either.

### Implication for the bug hunt
The 10 slots are drawn by an unidentified renderer. The connection to the DATA side is
now clearer from table-rom-format.md: the built-in styles + names live in the **TCMP
chunk** (0x48035D08). The most promising next angle is DATA-side, not render-side:
decode the TCMP per-style record layout (how a genre+index selects a name), then check
whether the emulated read of that structure yields index 0 for every slot. A render
trace would need to target the library-ROM glyph routine (find it by tracing writes to
the LCD framebuffer / video device and resolving the writer PC — but note a read/write
tap must NOT touch cpu.state in its callback: segfault).


## DECISIVE (tick 4): the menu shows a program-ROM DEFAULT, not the table-ROM genre styles
Cross-checking names settles it: the on-screen "8 Beat 1" is **not present anywhere in
the table ROM** (0 hits), while the table ROM DOES contain the real genre styles as
`f5`-marker records with descriptive names — BALLAD has 13 ("Pop Ballad Piano", "EP
Ballad Maj", "Angel Ballad", ...), WALTZ 17, MARCH 11 (see table-rom-format.md). The
only "8 Beat 1" string in any ROM is program-ROM 0x4872AB44 (the user-style area, also
an `f5` record) — but a read-tap there showed 0 reads, so the displayed text is a **RAM
copy of that default** (copied at init), shown for all 10 slots.

**So the bug is: the genre-style-list build never populates from the table-ROM genre
records — every slot falls back to the default current/user style "8 Beat 1".** The
genre (BALLAD) is selected correctly (title is right) but its 13 table-ROM styles are
not enumerated into the list. Since the build DOES read the table ROM 269K times, the
failure is in **locating/enumerating the genre's f5-records** (a wrong genre->section
pointer, a scan that finds 0 records, or a count read as 0) rather than in the raw
data. NEXT: find the genre->style-list pointer/count the build uses (likely a table in
the 0x48000000 config block or a program-ROM table indexed by genre) and check what it
yields for BALLAD in emulation vs the real 13.

## ROOT CAUSE FOUND (tick 5): genre styles are parsed from the EMPTY 0x96800000 "LCD window"
A multi-agent workflow (6 scouts; orchestrator died between turns but the leads were
salvaged from transcripts) + follow-up RE pinned the mechanism:

### The genre->style-list pointer chain (answers the question)
- `getDir4()` **0x4843D7B9**: `d1 = *0x48000010 (table-ROM directory entry [4] = 0x0004238C) + 0x48000000` = **0x4804238C** (the genre-style SECTION base; BALLAD's 13 f5-records at 0x4804AF61 live inside it).
- Genre setup **0x484342BE** stores that base to **RAM global 0x50007760**.
- The style-list build reads 0x50007760 and STAGES/parses the section through the window at **0x96800000**: reader **0x4847FB68** (`mov 0x96800000,a2 ; mov (0x50007760),a1 ; mov 0x10000,d0 ; call 0x4847F9F7`, looped 0x20x0x10000) and parser **0x4847F9F7** (`... sub 0x96800000,a2` = offset within the window).

### The emulation bug (runtime-confirmed)
With the BALLAD menu open: `*0x50007760 = 0x4804238C` (**correct**), but a dump of the
window shows **0x96800000 = all zeros (0 f5-markers, 0 'Ball' in the first 256KB)**.
So the pointer chain is right, but the **genre-style DATA never reaches 0x96800000**,
which the parser reads from -> it enumerates 0 styles -> every slot falls back to the
default "8 Beat 1". The driver maps `0x90000000-0x97ffffff .ram()` (comment: "LCD
controller window (regs + trampolines)") as **inert RAM**; whatever populates that
window on real hardware -- an aperture that maps/decompresses the table ROM, a DMA, or
a software staging copy that isn't being reached in emulation -- is **missing**. That
is the emulation defect behind the rhythm-name bug.

### Music Stylist parallel (NOT the rhythm menu, for the record)
Table **0x4873BEE8** (0x18-byte entries: [+0]list-ptr 0x4876xxxx, [+4]name-ptr
0x485D10xx e.g. "Disco Hustling"/"Strummed Ballad", [+8]genre-id<<16, [+C]sub-idx,
[+10/+14]counts), indexed by RAM category index **0x50001270**, getter **0x4847BD9F**
(`index*0x18 + 0x4873BEE8`). This is the **Music Stylist** category system (near
`MusicStylistJpgData` 0x4847B137), which is why `AcCtgStyleListBoxProc` never fired in
the rhythm menu. Kept as a reference implementation of the same genre->list pattern.

### Next (the fix path)
1. Determine what populates 0x96800000 on real HW: is `0x90000000-0x97ffffff` an
   aperture that mirrors/decompresses the table ROM (map it to the "table" region /
   0x48000000 data), or is 0x4847FB68 a software copy that simply isn't being called
   (find its caller + the gating condition)? Trace whether 0x4847FB68 executes at all
   (PC-trigger), and what 0x4847F9F7/0x4847F980 do with a2=0x96800000 vs a1=section.
2. If it's an aperture, add the mapping in kn7000.cpp; if it's a missed software copy,
   find why the path isn't reached. Then the BALLAD menu should list the 13 real styles.

## REFRAME (tick 6, user insight): the missing CUSTOM-DATA FLASH (Initial Data disk)
The user asked whether the empty style region is a flash ROM populated by the "Initial
Data" floppy. Confirmed by the KN5000 shared codebase: `kn5000.cpp` maps a **custom_data
FLASH @ IC19** and states it "was dumped from a system that had it already programmed by
the initial data disk." The KN7000 ships the same concept — the **idd7000 Initial Data
disk** (01CTMINI.AST = custom/style data w/ 1260 f5-records, 03FAVINI.FAV = favorites,
...), all in the Technics "JK" block format. The KN7000 driver models only table+program
flash, NOT this custom-data flash -> the custom/style working set is absent. This is a
strong candidate for why 0x96800000 stays empty (the region may BE the custom flash, or
the table->0x96800000 copy is gated on the initial data being installed). See
notes/initial-data-disk-and-custom-flash.md.

## CORRECTION + AUTHORITATIVE ANSWER (tick 7, verified multi-agent workflow)
A 6-scout workflow (it completed, ~31 min; 2 scouts hit the schema retry cap but the
rest + verify gave a byte-level-confirmed result) established the REAL genre->style-list
mechanism and CORRECTS earlier premises here.

### The genre->style-list table (VERIFIED, program ROM -- not the table ROM)
- Table **0x48735EE4**: 16 records x 0x18 bytes = `{char name[16]@+0; u8 flag@+0x10;
  u8 styleCount@+0x11; u16 pad@+0x12; u32 styleListPtr@+0x14}`. Genre count u16 @0x48736064 = 16.
- The 16 names dump cleanly: "   8&16 BEAT    ","   ROCK & POP   ","     BALLAD     ",
  "  JAZZ & SWING  ", ... ,"     CUSTOM     ","     MEMORY     ".
- **BALLAD = genre[2]** @0x48735F14: styleCount=**16**, styleListPtr=**0x485B8A04** ->
  16 contiguous u32 style-IDs (0x065B,0x066B,...,0x0762), all built-in (bits&0x00700000==0).
- Current genre = RAM byte **0x50034C3C** (GetCurrentGenreIndex 0x48435A1B).
- Accessors: GetGenreName 0x48435A9F (record+0, 16B memcpy via 0x4C003039),
  GetGenreStyleCount 0x48435AD9 (record+0x11). Style-ID source bits: 0=built-in,
  0x100000=MEMORY user, 0x200000=CUSTOM user. LUT 0x48734EE4 (2048 u16) maps num->bank/slot
  (resolver 0x48435B33). Flat-ordinal builder 0x4843FB0D.

### This table ENUMERATES CORRECTLY -> the bug is DOWNSTREAM
BALLAD yields a valid count (16) and 16 valid built-in style-IDs, so "all 8 Beat 1" is
**NOT** a wrong genre->style pointer. The failure is the style-ID -> NAME resolution:
MainGetRhythmName 0x48416204 delegates to the self-loaded **library ROM** 0x4C014948
(resource id 0xC000), which a program-ROM disassembly can't see. The built-in style
NAME/DATA is fetched there and/or from the unmapped **0x56000000** data-flash (this tick).

### CORRECTIONS to earlier notes in this file (superseded)
1. The "BALLAD = 13 f5-records at 0x4804AF61 (Pop Ballad Piano)" premise is **WRONG**:
   those f5-records are **Performance-Pad ("Technics Pads") phrases** in table-ROM section
   [4] (0x4804238C), not rhythm-BALLAD styles. Authoritative BALLAD count is 16, and the
   styles are program-ROM style-IDs (built-in), resolved via LUT 0x48734EE4.
2. The tick-5 "ROOT CAUSE = styles parsed from empty 0x96800000" is **NOT confirmed** by
   the workflow: the name fetch is in the library ROM (0x4C014948), and 0x4847FB68 /
   0x96800000 was not shown to be the style-name parser (may be a graphics/other path).
   Downgrade that from "root cause" to "an empty region of uncertain relevance."
3. The 0x4873BEE8 table IS the Music Stylist subsystem (RAM idx 0x50001270), confirmed
   -- not the front-panel rhythm menu.

### Current best understanding of the bug
Genre table works -> 16 BALLAD style-IDs -> resolve each ID to a NAME. The name/data
source for built-in styles is unmodeled/empty in emulation: either the library-ROM
resource fetch (0x4C014948, res 0xC000) fails, or it reads the style DB from the UNMAPPED
0x56000000 data-flash (now mapped read-as-0 placeholder; still empty). NEXT: dump the
library-ROM code path 0x4C014948 at runtime (it IS resident in libram) to see what
address the style name is read from; if it's 0x56000000, the fix is that flash's contents.

## TICK 8 (static library-resource trace): the name DATA is PRESENT -> bug is resolution, not missing flash
Disassembled the library name path from full.bin (library 0x4C000000 <- prog-flash source 0x487B8FD1,
so 0x4C0xxxxx = full.bin off 0x3B8FD1 + (addr-0x4C000000)). Findings:

### The library resource system (what 0x4C014948 does)
- **0x4C014948** = a resource DISPATCHER: `d0 &= 0xFFFFFF` (resource id, e.g. 0xC000) -> `call 0x4C01BB0C`
  (lookup) -> record ptr in a0 -> reads `*(a0+4)` type (0 or 1) -> dispatches to name-handler
  **0x4C015607** (type 0) or **0x4C015C4A** (type 1), passing a1=arg, d0=arg2.
- **0x4C01BB0C/BB1C** = a **nibble-trie (radix) lookup** rooted at table **0x4858B424** (program ROM):
  walks the id's nibbles (`(id>>shift)&0xF`, 8-byte records `[leafptr u32][flag u8]...`) to a leaf record
  whose first u32 == the requested id.
- **0x4C015607** reads a subtype `*(a0+6)` (0..0x24), `*4`, indexes a **jump table 0x4858C254** (program
  ROM; entries 0x4C0156xx) and `jmp`s to the per-subtype sub-handler.

### KEY: this resource system reads ENTIRELY from the PROGRAM/TABLE ROM -- not the data-flash
Scanned the resource descriptors 0x4858A000-0x4858C000: **964 pointers, ALL 0x48xxxxxx** (prog/table ROM).
**ZERO** point to the data-flash (0x56xxxxxx), libram (0x4Cxxxxxx), or the "LCD window" (0x90-97xxxxxx).
So the built-in resource data these getters read is fully resident in the dumped ROMs.

### KEY: the built-in style-name STRINGS are present in the program ROM
`full.bin` (program flash) contains the real built-in names: **"8 Beat" @0x485CCF31, "16 Beat"
@0x485CCF78, "Pop Ballad" @0x485D0105, "Easy 8 Beat" @0x486D38BC**. The displayed **"8 Beat 1"** is the
**user-style default @0x4872AB44** (a RAM copy; a read-tap there showed 0 live reads, tick 4).

### CONCLUSION -- corrects the tick-7 "missing data-flash 0x56000000" hypothesis
The style-name DATA (built-in names + the resource system that fetches them) is **fully present in the
dumped program ROM**. So "all 8 Beat 1" is **NOT** a missing-dump / missing-data-flash problem. It is a
**resolution/logic failure**: the genre-style-list populate resolves the 16 BALLAD style-IDs but falls
back to the RAM default "8 Beat 1" instead of the built-in names at 0x485Cxxxx.

### NEXT (decisive, bounded)
1. Read-tap **0x485C0000-0x485DFFFF** (the built-in-name region) during the BALLAD menu. If **0 reads**,
   the populate never reaches the built-in names (the resolver returns/uses the default without reading
   them) -> the defect is upstream in the style-ID->name resolver. If reads occur, the names ARE fetched
   but not stored into the list items (a store/copy defect).
2. Then find the resolver: MainGetRhythmName didn't fire in the menu (tick 3), so the list uses another
   getter that (per this trace) still bottoms out in the 0x4C014948 resource system -> trace which
   resource id / style-ID it passes per slot, and why it degenerates to the default.

## TICK 8b (runtime read-tap): the built-in name strings are NEVER read -> resolution fails upstream
Read-tap on **0x485C0000-0x485DFFFF** (the built-in style-name region) with BALLAD held to open the menu
(SEG00 0x10 = "RHYTHM BALLAD"), addresses logged:
- **15 reads total, ALL clustered in 0x485D6260-0x485D62B0** (a small descriptor struct: little u16/u8
  IDs/indices 0x26/0x27/0x28/0x2a..., a self-near ptr 0x485D6254, and a RAM ptr 0x500012CC -- NO pointers
  into the name-string area).
- **ZERO reads at the actual name strings** (0x485CCF31 "8 Beat", 0x485CCF78 "16 Beat", 0x485D0105
  "Pop Ballad", etc.).

### Conclusion (decisive)
The genre-style-list populate **never reads the built-in style-name strings**, even though they are
present in the program ROM. So it is NOT "names fetched but not stored" -- the names are simply never
fetched; the resolution fails **before** reaching the strings, and every slot falls back to the RAM
default "8 Beat 1". The only 0x485Dxxxx data it touches is the descriptor struct @0x485D6260, which in
emulation does not lead on to the name strings.

### NEXT (needs a PC-trigger, i.e. a CPU-core rebuild)
Put a PC/read trigger on the reads of **0x485D6260** (or on the style-list populate loop) to capture the
reader PC, then disassemble that code to see the indirection it follows from the 0x485D6260 descriptor to
a name -- and which step yields a null/default in emulation (a RAM global read as 0, an index computed as
0, or a pointer through an unmapped region). The struct's RAM ptr **0x500012CC** is a prime suspect: if
that workram holds a per-style name-pointer table that is uninitialised (0) in emulation, the resolver
would default for every slot. Check 0x500012CC's contents during the menu (read-tap or dump).

### TICK 8c (follow the struct's RAM pointer): 0x500012CC is UNINITIALISED (0xffffffff) in the menu
Dumped RAM during the BALLAD menu. The descriptor struct @0x485D6260 (read 15x) has a field +0x24 =
**0x500012CC** (a RAM address). Live contents:
- **0x500012CC = 0xffffffff** (uninitialised). The whole surrounding config area 0x50001280-0x50001310
  is largely 0xffffffff / 0x00000000, except a **region-base table @0x500012EC = 84000000 50000000
  4c000000 48400000** (the RAM/workram/libram/program-flash bases).
So the resolver's data chain from the ROM descriptor bottoms out at an **uninitialised RAM slot**
(0xffffffff), a plausible reason it yields no name and defaults. CAVEAT: not yet proven that 0x485D6260
IS the style-name resolver's descriptor (it is merely what was read in the name region during the menu);
it could be a font/UI descriptor. Confirming requires the reader PC (PC-trigger, CPU-core rebuild) to tie
the 0x485D6260 read + 0x500012CC deref to the style-list populate.

### Status summary of this bug (for the next tick)
SOLID: (a) genre->16 style-IDs works; (b) built-in name strings ARE in the program ROM (0x485CCF31 etc.);
(c) they are NEVER read during the menu -> resolution fails upstream, not a store defect, not missing
data-flash. OPEN: the exact resolver + why it stops. Best next move: temporary PC-trigger in mn10300.cpp's
fetch loop keyed on a read of 0x485D6260 or 0x500012CC (log PC+regs), press BALLAD, disassemble the PC.

## TICK 9: narrowed to the NAME-FETCH from (bank,slot); the pipeline before it WORKS
Read-taps during the BALLAD menu (genre held = SEG00 0x10) prove the whole index pipeline runs:
- genre table **0x48735EE4 read 125x**, BALLAD style-ID list **0x485B8A04 read 23x** (16 IDs),
  LUT **0x48734EE4 read 16x** (once per style). So genre->16 style-IDs->per-style LUT all execute.
- Resolver **0x48435B33** (disassembled): masks the style-ID source bits (`&0x700000`; 0=built-in,
  0x100000=MEMORY, 0x200000=CUSTOM), builds a packed index `((id&0xf00)>>1)|(id&0x7f)`, reads
  `LUT[index]` @0x48734EE4 (with a 0x7FFF-invalid indirection), and writes **bank=id>>8 -> *(a0),
  slot=id&0xff -> *(a2)**. MEMORY/CUSTOM branches validate slot against counts @0x4873606A/6E/70.
  So (bank,slot) is produced correctly, 16x.

### The failure is downstream: locating + reading the NAME record from (bank,slot)
The built-in style names are **structured records** starting at **0x485CCF31**: a 16-byte space-padded
name ("    8 Beat     ", "    16 Beat     ", "   Dance Pop    ", ...), then u16 params and a run of
sub-pointers (0x485CCxxx). A **3-byte-entry index precedes them @0x485CCF00** (entries `0c 04 02`,
`0c 04 03`, `0c 09 01`, ... terminated by `ff ff` @0x485CCF2A). The names are **NOT in a flat pointer
table** (0 pointers to "8 Beat"/"16 Beat" anywhere in the ROM). So the name-fetch must locate the record
by (bank,slot) -- via a bank->record-base mapping + the index -- and that step is what never reads the
name records in emulation (read-tap: 0 reads at the name strings).

### Strong suspect (ties tick-8c together)
A **bank -> record-base table that is uninitialised in emulation** (cf. the RAM slot 0x500012CC = 0xffffffff
seen tick-8c). If the base for the built-in bank is null/uninit, the fetch can't locate the record ->
returns the RAM default "8 Beat 1" for every slot. NEXT: find the caller of 0x48435B33 (the build loop)
and the code that turns (bank,slot) into the record address; identify the bank-base table and check if it
lives in an uninit RAM / unmapped region in emulation. That table (populated at init on real HW, perhaps
gated on the initial-data disk) is the likely fix point.

## TICK 10 (CPU PC-trigger): CORRECTION -- the resolver is validation, the name path is the 0xC000 resource object
Added a temporary PC-trigger in mn10300.cpp (start_pc==0x48435B33 -> fprintf d0/sp/stack; reverted after).
Pressed BALLAD, captured the resolver's callers + args:
- The resolver 0x48435B33 IS called with BALLAD style-IDs (d0=0x65B, the first BALLAD style-ID 0x065B),
  from several sites: 0x4843FB04 (id->ordinal), 0x484AFBDE, 0x4849771F, and **~10x from 0x48497B19**
  (with the UI object table 0x5000757C and the 10 list-item object ids 0x600059..0x600062 on the stack).

### CORRECTION: 0x48435B33 is NOT the name-fetch -- it is style-ID <-> bank/slot validation
Its sibling **0x48435B01** does the INVERSE: `(bank,slot) -> styleListPtr[slot]` = the style-ID at that
slot (genre_record[bank].styleListPtr @+0x14, i.e. 0x485B8A04 for BALLAD). The list code 0x48497AE9 calls
resolver(id)->(bank,slot) then 0x48435B01(bank,slot)->id and COMPARES -- a round-trip **match/validate**,
not a name lookup. (So last tick's "resolver is the name path" was wrong; the LUT-16x reads were validation.)

### The actual NAME-FETCH = the 0xC000 resource OBJECT (async)
In the same list module: `0x48497ACB: mov 0x0000C000,d0 ; ... call 0x4841C37C`. **0x4841C37C** allocates a
16-byte object (`*(obj)=0xC000` resource id, `*(obj+4)=item id`), then dispatches GUI messages via
**0x4842AD45** (ids 0x30002/0x600C0, 0x30003/0x60023). The name is fetched + drawn by the OBJECT's message
handlers -- the same 0xC000-resource path as MainGetRhythmName -> library **0x4C014948** (tick 8: trie
0x4858B424, reads program ROM). So the name comes from the **0xC000-resource GUI-object system**,
asynchronously (at draw), not inline in the populate.

### Where the bug is now
The 0xC000-resource object, given the built-in item id, must resolve to the style-name string -- but the
read-tap shows the strings are never read, so that resolution defaults. NEXT: trace the 0xC000 object's
draw/name handler -- the 0x4842AD45 message targets and the library 0x4C014948 processing of resource
0xC000 *with the specific item id* -- to find where the built-in-style string lookup yields the default.
The object id at *(obj+4) (a 0x600xx-style id) and how it maps to a name index is the key.

## TICK 11 (trace 0xC000 path): the 0xC000-object path does NOT fire -> hypothesis corrected AGAIN
Instrumented 0x4841C37C (0xC000-object creator), 0x4C014948 (library resolver, log res id+args), and its
not-found path; held BALLAD. Results:
- **0x4841C37C: ZERO calls** during the menu. The 0x48497ACB `call 0x4841C37C` site is a NOT-TAKEN branch
  for the built-in-genre list -> the 0xC000-object is not how the list gets names. (Tick-10 hypothesis wrong.)
- **0x4C014948: 100,309 calls**, but for resource ids **0x03 / 0x04 / 0x08** (arg d1 frequently 0x0006003A,
  an object id 0x60000+0x3A), and **NEVER 0xC000**. LIB-NOTFOUND = 0 (every trie lookup succeeds).
So the list's UI/name resolution goes through the library with **low resource ids 0x03/0x04/0x08**, not the
0xC000 rhythm-name resource (0xC000 is MainGetRhythmName's path, which doesn't fire in the menu -- tick 3).
NEXT: instrument 0x4C014948 to capture the res-id + arg for the calls that actually feed the visible slot
text, and follow res 0x03/0x04/0x08 with arg 0x6003A through the sub-handlers to the (defaulted) name.

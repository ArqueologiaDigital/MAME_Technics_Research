# KN7000 style-name build subsystem (the "8 Beat 1" trail)

## Enabler: MN10300 disassembly via unidasm
The disassembly repo ships MAME's standalone disassembler at `../mame-sony-video/unidasm`
(read-only use is fine). To disassemble a program-ROM region:

```
python3 -c "d=open('kn7000_program.rom','rb').read(); open('w.bin','wb').write(d[OFF:OFF+N])"
../mame-sony-video/unidasm w.bin -arch mn10300 -basepc 0xADDR
```
where `OFF = ADDR - 0x48400000`. This unblocks all static MN10300 RE (the debugger `-debug`
segfaults with `QTDEBUG=0`, and no `mn10300-objdump` is installed).

## The style-list name path (why every slot shows "8 Beat 1")
Confirmed at runtime (read-taps, tick 2026-07-07j): the rhythm-style list reads a **boot-built
RAM name-table**, NOT the custom flash (0 dataflash reads during display). Disassembly of that
build (tick 2026-07-07L):

Flow: `style records --parse--> TEMPLATE 0x5003A2BC --memcpy--> NAME-TABLE 0x5003A37C --> list`.

Key functions (program ROM):
- **0x48441D1B StyleRecordToTemplate** — parses ONE style record at `a2` into the template
  `0x5003A2BC + idx*0x18`. Record subtype = `(a2+4) high nibble`: 0xB0/0xC0/0xD0/0xE0 branches
  write different name/param fields (e.g. 0xB0 copies bytes to `+0/+1`, others to `+2..+4`,
  `+0x12..+0x14`). Type nibble `>=8` => skip.
- **0x48441CBF StyleTemplateToNameTable** — `memcpy(0x5003A37C, 0x5003A2BC, 0xC0)` (0xC0 = 8
  entries x 0x18) — copies the template into the displayed name-table.
- **0x48441CDB StyleTemplateBuildLoop** — nested loop over 8 x 0x18 entries; per entry sets
  `a3 = 0x5003A37C + i*0x18`, `a2 = 0x5003A2BC + i*0x18`, loads handler ptr **0x48435DD0** into
  `(0x18,sp)`, and calls **0x48440862** (per-entry record fetch — NEXT to trace).
- **0x48442072 StyleNameDefaultFill** — `memcpy(dest = (sp+0x40)+0x20 + idx*0x18, src = *(sp+0x14),
  0xf)` — copies the 15-byte DEFAULT name. `*(sp+0x14)` is the default string "  8 Beat 1  "
  (@0x4872AB42; note it is NOT loaded as an immediate anywhere — reached via this arg pointer).
  This runs ~14x at boot (208 string-byte reads / 15) => the ~14 list slots all get the default.
- **0x48435DD0 StyleIdArrayHandler** — per record builds the style-ID arrays `0x50034C48` (u32,
  idx `0x50034C40`) and `0x50035448` (u32, idx `0x50034C44`), limit `0x1FF` (511 styles). Tags
  IDs with source bits `0x70000000`. Sub-calls: 0x48435C29 (type->slot), 0x48440535 (lookup),
  **0x48435D83 StyleIdArrayStore**, 0x48446C9D (mode 0x90 special, gated by flag `0x50034C3D`).

RAM globals:
| addr | meaning |
|------|---------|
| 0x5003A37C | displayed style-name table (8+ entries x 0x18) |
| 0x5003A2BC | template the name-table is memcpy'd from (parsed from records) |
| 0x50034C40 / 0x50034C44 | u16 style-list build counters (limit 0x1FF) |
| 0x50034C48 / 0x50035448 | u32 style-ID arrays |
| 0x50034C3D | style mode flag (gates the 0x90 special path) |

## OPEN (next step)
The default fill runs => the record parse produced no real names => the **record SOURCE is empty
or wrong**. Since the names do NOT come from the custom flash, the records come from the table
ROM (TCMP) or the library ROM. Trace **0x48440862** (the per-entry fetch in the build loop) and
what pointer it hands to `StyleRecordToTemplate` — that pointer's origin is the bug.


## RESOLVED CHAIN: the built-in style-name lookup (tick 2026-07-07n, via stack unwind)
Read-taps don't catch instruction fetches, so I tapped the DEFAULT STRING (0x4872AB42) read and
dumped the stack when the library memcpy (0x4C003043) read it -> caller = **0x484334BF**. From there:

- **StyleNameCommit 0x484334A4**: `memcpy(dest=0x50034B9C, src=*(0x50034B8C), 13)` -- copies the
  current style name. When `*(0x50034B8C)` is the default string 0x4872AB42, the slot shows "8 Beat 1".
- **StyleNameSourceSet 0x48433400**: sets `*(0x50034B8C)` from the style-ID. Dispatches on the ID's
  source bits `& 0x00700000`: 0=built-in -> call **0x48433AC4**; 0x100000=MEMORY -> 0x484355E2;
  0x200000=CUSTOM -> 0x4848457D. The returned pointer becomes the name source.
- **StyleBuiltinNameLookup 0x48433AC4**: indexes RAM directory `0x50034B7C` (stride 2) and
  `0x50034B80` (stride 3, via 0x48440363), name base `0x50034B78`, threshold `0x50034B74`. Returns
  the default 0x4872AB42 when the style-ID does not resolve.

RUNTIME globals at boot (ramchk.lua):
| global | value | meaning |
|--------|-------|---------|
| 0x50034B74 (u16) | 0x0001 | threshold/count |
| 0x50034B78 | 0x48729988 | built-in name-string base (default 0x4872AB42 = base+0x11BA) |
| 0x50034B7C | 0x483E82BF | style directory A (indexed by style-ID*2) |
| 0x50034B80 | 0x4872A9BB | style directory B (indexed *3) |
| 0x50034B88 | 0x4872AB42 | = the DEFAULT string |
| 0x50034B8C | 0x4872AB42 | current name source = DEFAULT (this is why "8 Beat 1") |

KEY: the directory pointers are NON-null, yet the lookup returns the default -> the **style-ID passed
to 0x48433AC4 is invalid/0**, or the directory does not contain it. The style-ID comes from the
style-ID arrays (0x50034C48/0x50035448) built by StyleIdArrayHandler 0x48435DD0 (tick 2026-07-07L).
NEXT: data-tap the directory read in 0x48433AC4 and read d0 (the style-ID) -- if 0/invalid, the
upstream style-ID enumeration (0x48435DD0) produced no styles, which is the true root.


## ROOT NARROWED (tick 2026-07-07p): "8 Beat 1" = rhythm STYLE-ID is 0; sounds are fine
Tapped the directory-global read (0x50034B7C) in StyleBuiltinNameLookup 0x48433AC4 and read d0
(the style-ID) at runtime (home screen, genre 0):
- 1st lookup: **d0 = 0x00000000** -> the RHYTHM style -> returns the default 0x4872AB42 = "8 Beat 1".
- later lookups: **d0 = 0x0000065A** (and 0x8000-flagged) -> the SOUNDS -> resolve to REAL names
  (this is why the home snapshot shows correct "Concert Grand"/"Bigband Brass"/"Modern E.P." but
  "8 Beat 1" for the rhythm). So the name-lookup + directories WORK; the SOUND path is fine.

**The bug is that the rhythm STYLE-ID handed to the lookup is 0 (unset).** When a genre list is
opened, every slot's style-ID is likewise 0 -> every slot shows "8 Beat 1" (matches the BALLAD-list
snapshot). So the root is upstream of the name lookup: the **genre -> style-ID enumeration yields 0**.

CORRECTIONS to earlier notes:
- 0x5003A37C is NOT the displayed name-table -- its content at runtime is binary/param data, not
  name strings. (The 0x48441CBF memcpy fills a param/template area, not the visible names.)
- 0x50034C48/0x50035448 is a style-ID QUEUE (ring & 0x1FF): enqueue **0x48435DD0**, dequeue
  **StyleIdQueueDequeue 0x48435E84** (write idx 0x50034C40, read idx 0x50034C42, count 0x50034C44);
  it is DRAINED at t=15, so its residue is not the current list.

NEXT: find where the rhythm style-ID is produced (the caller path that hands 0 to 0x48433400 for the
rhythm/style, vs 0x65A for sounds). The genre->style table is 0x48735EE4 (styleListPtr 0x485B8A04 for
BALLAD); check whether that list yields 0s at runtime, or whether the style-load that should set the
current style-ID never runs. Stack-unwind (tap a data read in the rhythm path + read the return chain).


## REFRAMED (tick 2026-07-07q): the genre-style DATA is valid; the bug is in the LIST path
Static dump of the genre-style table 0x48735EE4 (already symbol GenreStyleTable): **all 16 genres are
fully populated + valid** -- 8&16 BEAT(10), ROCK & POP(16), BALLAD(16), JAZZ & SWING(20), ... each
with a real name, style count, and styleListPtr. BALLAD's list (0x485B8A04) = **distinct valid u32
style-IDs**: 0x65B, 0x66B, 0x662, 0x75B, 0xC63, 0x24E, 0x94B, 0x34A, ... (adjacent to the working
sound-ID 0x65A). So the STYLE DATA IS PRESENT AND VALID.

**This CORRECTS the roadmap's long-standing "empty style data / 0x96800000-empty -> 8 Beat 1" theory.**
The '8 Beat 1' bug is NOT missing data.

Runtime tap: during a genre-list build (press a RHYTHM GROUP button), there are **0 reads** of the
static styleList region (0x485B8900-0x485B8DFF). So the list-box does not consult the static table at
press time -- it reads a RAM copy / prior enumeration.

Re-framing of what I traced: the path I mapped (StyleNameCommit 0x484334A4 <- StyleNameSourceSet
0x48433400 <- StyleBuiltinNameLookup 0x48433AC4) is the **current-style / conductor** name path (home
screen), where style-ID 0 -> "8 Beat 1" is probably the CORRECT power-on default (genre 0 = 8&16 BEAT,
style 0). The **list** "all 8 Beat 1" bug is a SEPARATE path: **AcCtgStyleListBoxProc 0x4847BCCA**
(from the roadmap) building the 10-slot list. That is the path to trace next.

NEXT: trace AcCtgStyleListBoxProc 0x4847BCCA -- where it gets each slot's style-ID/name (a RAM copy,
not the static table), and why every slot resolves to the default. The static data (0x485B8A04) is
good, so the defect is in the list enumeration's read of it (boot-time copy, or the aperture).

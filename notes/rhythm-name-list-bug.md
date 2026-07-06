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

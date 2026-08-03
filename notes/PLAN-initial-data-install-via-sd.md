# Plan: run the Initial Data install via SD instead of floppy

**2026-08-03.** Goal: make the firmware *itself* perform the custom-data install, rather than us
pre-loading a flash image, so the region ends up in the state a real instrument reaches.

## Why not floppy

**Floppy disk operations do not work and are parked at an engine-timing wall.** The FDC (IC103) is
located and modelled, but a non-masking tap during a format shows the async disk-task dispatch
(class-5 handler) **never runs** — 0 writes to its command/FDC markers against 811/27793 in a
masked run — so the command is posted and the task is not scheduled in time, giving **ERROR 08**.
SHARC-DRC, `-debug`, `perfect_quantum` and `-sound none` are all ruled out. The divergence is RTOS
dispatch, not the FDC, and it is un-observable at instruction level (the timing is what masks it).

⇒ Fixing floppy first is a research project of unknown length. SD is the pragmatic route.

## Why SD is plausible — the firmware already supports it

| evidence | where |
|---|---|
| Two drives: `A:\` (floppy) and `C:\` (SD), **adjacent in one table** ⇒ drive-agnostic file I/O | CPU `0x485CFB20` |
| **`SD_LD2_LBAST` / `SD_LD2_BAST`** — an "AST" item on the **SD Load page 2**; `SD_SV2_LBAST` on Save | `0x28ACFE`, `0x28AE4B`, `0x28B121` |
| Extension table includes `AST` alongside TM/MSP/EFC/MD/FAV/HMP/SQF/SEQ/ACT | `0x264444` |
| SD transport works: card mounts (CRC16 init-0 fix), LOAD and SAVE both verified, all soft keys mapped | `notes/AUTONOMOUS-STATUS.md` |

**So the AST file type is loadable from SD by design.** That is the single biggest reason to expect
this to work.

## ⚠ Two conditions that could sink it

### 1. The SD naming/index convention is NOT the floppy one

The real card is MBR-partitioned, FAT16, partition 0 at **LBA 97**, OEM-ID `Technics`, 16 KiB
clusters. Its layout:

```
C:/KN7000_M.AME                                     0 bytes   (marker)
C:/PRIVATE/TECHNICS/KN7000/KN7000MN.INF         54816 bytes   (master index)
C:/PRIVATE/TECHNICS/KN7000/TFLD001/01001KN7.EFC  1398
                                   01001KN7.TM   15751
                                   01001KN7.LSW   4057
                                   01001KN7.PMT  10939
                                   01001KN7.MSP   5080
                                   01001KN7.CMP  16145
                                   01001KN7.SQT   6155
                                   01001KN7.ACT     42
```

Files are `<item><folder>KN7.<ext>` inside `TFLD<nnn>`, enumerated through **`KN7000MN.INF`** —
*not* the floppy's `01CTMINI.AST` at the root. **Dropping `01CTMINI.AST` onto the card will most
likely be invisible to the browser**, because the firmware lists what the INF indexes.

⇒ **Mitigation (the good trick): let the instrument build the slot.** Use the emulator's own SAVE
to create an AST item on the card, which produces a correctly-named file *and* a valid INF entry.
Then overwrite that file's contents with the Initial-Data payload, keeping the size or fixing up the
directory entry. We never have to decode `KN7000MN.INF`.

### 2. Loading an AST may only populate the working set, not the flash — UNKNOWN

On the KN5000 the equivalent `.RCM` load **did** write flash (`Flash_StoreSection`). Whether the
KN7000's *SD* AST load reaches the flash programmer, or merely loads into RAM, is **not
established**. This is the pivotal unknown and it is cheap to settle.

## The plan

**Step 0 — safety.** Work on `sdcard_work.img`, never `sdcard_from_real_kn7000.img` (Felipe's own
card; personal data, root-owned, and the only copy besides the published folder). `run.sh` already
creates the working copy.

**Step 1 — settle the pivotal unknown first (cheap, no file surgery).**
Instrument writes to the custom-flash window and drive the existing SD LOAD flow on whatever AST/
data item the card already has. Reuse the tap from today:
`install_write_tap(0x96800000, 0x969fffff)` and count. **If an SD load produces flash writes at all,
the route is real.** If it produces none for any data type, stop — SD load is a working-set path and
this whole approach is dead, no matter how the file is named.
*Falsifier stated up front: zero flash writes across every SD load ⇒ abandon.*

**Step 2 — establish the round trip.** Use SD **SAVE** to write an AST item from the emulator. This
proves the naming/index machinery end-to-end and yields a template slot plus a known-good
`KN7000MN.INF` delta to diff against the pre-save copy. (SD save is already verified working.)

**Step 3 — swap in the real payload.** Replace the saved AST file's contents with `01CTMINI.AST`
(the container, not the inflated image — the firmware does its own inflate). Adjust the directory
entry size, and re-check the INF if the size is recorded there.

**Step 4 — load it and watch the flash.** Drive SD LOAD → AST with the write tap armed. Success
looks like: a burst of writes to `0x96800000+`, unlock/erase/program sequences decoded by the flash
device (which now answers autoselect correctly), and NVRAM differing from the ROM afterwards.

**Step 5 — verify against the null.** Re-run the with/without screenshot comparison from today. The
control matters: today's identical snapshots are what proved pre-loading changed nothing visible.

**Step 6 — if it works**, the emulator can reach the post-install state by the instrument's own
code path, and the pre-loaded `custom_data` region becomes a convenience rather than the mechanism.

## Cheaper alternative worth trying before Step 3

The firmware reads chip offset `0x4000` at boot and finds `0xFF`. That area is **`0xFF` in
Panasonic's distributed payload regardless of placement**, so the disk does not supply it — the
firmware must initialise it itself. There may be a *menu-driven* initialise/format of the custom
area (a service or "clear custom" function) that populates it without any disk at all. Finding that
function in the UI string table is far cheaper than the file surgery above, and would answer why the
style list stays empty.

---

## ⛔ THE CHEAP ALTERNATIVE IS CLOSED (2026-08-03, measured)

**`CONTROL MENU -> INITIAL -> Yes` runs, and does NOT touch the custom flash.**

Established by breakpointing all 23 entries of the SysInit handler table (addresses at
`0x4874C140`, names at `0x4874C1A0`; auto-`g` so the machine never halts). Felipe drove the UI by
hand. The captured sequence:

```
SystemInitMDFunc        menu drawn
CtlIniLngCheck x2
SystemInitOkFunc      <- INITIAL selected
InitShowHideFunc
AttnLngCheck x2
SysSureLngCheck x2      "are you sure?"
SureLngCheck x2
SysIniYesFunc         <- CONFIRMED YES
InitShowHideFunc x3
```

Custom-flash counters on **every** line: `CF r=2962 w=20` — the boot baseline, unchanged.

⇒ INITIAL initialises the CONTROL MENU settings (touch sensitivity, P.MEM mode, foot controllers —
the handlers sitting beside it in that same table), **not** the custom-data region. No menu function
populates the `0x4000` area the firmware probes at boot; only a real data-disk install does.

★ The index->name mapping **proved itself** (`FIRED 0 SystemInitOkFunc`, `FIRED 6 SysIniYesFunc`),
so the parallel-array ordering is verified, not assumed.

### What this cost, and the lesson

- A wrong hypothesis: the `0x56000000` "dataflash" alias is NOT the read path — **4 reads, 0
  writes** across a whole session. Cheap to rule out, worth having done.
- An **unvalidated proxy**: the battery-SRAM window was picked because Favorites live there and it
  showed 6890 boot writes. That proved the window was live; it never proved INITIAL would write
  there. A flat reading was therefore uninformative — not evidence of absence.
- **Two runs lost to a stale emulator**: a `kill` silently failed, leaving two windows open, so the
  UI was being driven on an uninstrumented instance. Always confirm the old process is gone AND
  that the survivor has the script loaded (`/proc/<pid>/cmdline`).

> **The lesson:** observe the thing itself, not a signature it might leave. The breakpoint settled
> in one attempt what two memory-watching rounds could not, because a proxy that does not fire tells
> you nothing unless you have shown it *would* fire.

⇒ **Proceed to the SD plan, Step 1** — does any *load* path reach the flash programmer? The tap
harness is built and proven. Falsifier unchanged: zero flash writes across every SD load ⇒ abandon.

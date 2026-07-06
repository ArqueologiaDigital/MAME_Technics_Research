# MILK class-system tables: the MT_ method dictionary + the boot InitializeBlockNN table

Two adjacent reflection tables in the program ROM describe the firmware's object
framework (the "MILK" class system whose reflection metadata already gives us ~2300
recovered symbols) and its boot init sequence.

## MT_ method-name dictionary — `0x48726CE4 .. 0x487270A4` (241 entries)

A contiguous array of 241 `u32` pointers, each to an ASCII method name of the form
`MT_<Name>`. These are the MILK class-system's **method dictionary** — the named
methods an object can respond to. Examples across the table:

- Class introspection: `MT_GetClassSp`, `MT_GetParentClassSp`, `MT_GetProcedureSp`,
  `MT_GetInstanceSizeSp`, `MT_CheckClassSp`, `MT_GetPropStringEx`
- UI/drawing: `MT_WaitDraw`, `MT_IconDraw`, `MT_SetRect`, `MT_GetBox`,
  `MT_GetClientBox`, `MT_DialLed`, `MT_HoldLedWait`
- Data/resources: `MT_GetTag`, `MT_CheckTag`, `MT_GetFileName`, **`MT_GetJpegData`**,
  `MT_GetPartID`, `MT_GetSoundIcon`, `MT_GetSoundDSPName`

The table holds **names only** — the method *implementations* are resolved per class
(via each class's procedure/v-table, `MT_GetProcedureSp`), not from this dictionary,
so these are NOT yet mapped to function addresses (a future symbol-recovery target:
find the per-class method tables that pair a method id/name with its handler).
`MT_GetJpegData` is notable given the boot-splash JPEG work but is just a name here.

## Boot init-block table — `0x487270AC ..` (48 entries: InitializeBlock00..47)

Immediately after the MT_ dictionary (one `0x00000000` separator at `0x487270A8`) is
the array of **boot initialization block** function pointers. Index N = the function
named `InitializeBlockN` in the MILK reflection data — all 48 are **already recovered**
into `kn7000.sym` and the mapping matches this table exactly. A few anchors:

| Idx | Addr | Note |
|-----|------|------|
| 00 | `0x48431AEE` | first init block |
| 01 | `0x48487420` | |
| 04 | `0x4848A4D8` | **opening/splash view setup** — installs `OpeningFrameDraw` `0x4848A931` (see splash-green-palette-bug.md) |
| 09 | `0x4850747D` | |
| 30/31 | `0x48431CB6`/`0x48431CB9` | small stubs in the `0x48431Cxx` thunk region |

These are the boot's staged init phases; identifying what each block sets up (display,
palette, panel, SIO, SD, ...) is a good way to map the boot flow. InitializeBlock04 is
the one that drives the power-on splash animation.

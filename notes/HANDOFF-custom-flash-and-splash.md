# HANDOFF — KN7000 custom flash: what is done, and the OPEN splash byte-order bug

**2026-08-03.** Read this before touching the custom-data flash or the Initial Data files.

## ✅ DONE — the custom-data flash works

`IC21` at `0x96800000` is a real **`FUJITSU_29LV160B`** (16 Mbit bottom boot), installed at
**runtime in `machine_start`**, not in the address map. The map is SHARED between machines and is
also built during the validity check, where the optional device finder is unresolved — a map-time
`if (m_customflash)` silently skips the install and every access falls through to the RAM window.
Symptom if that regresses: a write of `0xF0` reads back as `0xF0`.

The firmware's autoselect now succeeds: it reads **mfr `0x04`, device `0x2249`** — the
`MBM29LV160B` entry in its own table at `0x485CF9E0`.

### The Initial Data Disk is FOUR files at FOUR offsets

```
  0x004000  02UMDINI.MD     640 B   header 0x10 + 0xC0 + 3 x 0x90 = 0x280 = its size
  0x010000  03FAVINI.FAV    408 B   template compare at 0x4849EDC0
  0x011000  04HPGINI.HMP  17474 B   template compare at 0x48496F60
  0x020000  01CTMINI.AST   payload (inflated, 0x1E0000)
```

Offsets were **derived, not guessed**: each region is validated against a blank **template in
program ROM**, and matching template↔file on the first 16 bytes identifies them —
`0x48617638`=UMDINI 16/16, `0x48605728`=FAVINI 16/16, `0x485F9584`=HPGINI 15/16 (the ROM copy is
the *empty* variant, differing in one count field). The chip address each template is compared
against then falls straight out of the code.

⚠ Three of the four carry the ASCII signature **`"JK "` (`4a 4b 20`)**; the boot check at
`0x487DCE9A` compares flash `0x4000` against ROM `0x4858D730` and sets an error bit at
`0x5001602C` on mismatch — which made the firmware discard ALL custom data.

**Load flags:** `ROMX_LOAD(..., ROM_GROUPWORD | ROM_REVERSE | ROM_OPTIONAL)` for the three signed
files (CTMINI is a plain `ROM_LOAD_OPTIONAL`).
⚠ `ROM_LOAD16_WORD_SWAP` is NOT optional — using it made the machine refuse to boot without the
files ("Required files are missing"). Keep `ROM_OPTIONAL`.

**Measured effect:** payload reads in the `0x20000` bucket go **2 → 3022**, and the play screen
gains a populated P.MEM bank (`BANK A: KN7000 Tour` — Easy 8 Beat, Easy 16 Beat, …). Confirmed by a
frame-synchronised, LCD-region-only pixel diff: **47.23 % of LCD pixels differ** with vs without.

### Also done
- **`fav_preload` RETIRED.** That block is the **SD DIRectory INFo** cache (ROM string table at
  `0x4868DEA6` pairs the magic with `C:\`/`PRIVATE`/`TECHNICS`/`KN7000`/`TFLD`/`CUSTOM`). With a
  card attached the firmware writes the magic itself by ~t=8s. ⚠ An earlier measurement said it was
  still needed — that run had **no `-harddisk` attached**, so nothing could populate it. Always test
  this with the SD card.

---

## 🔴 OPEN — the KN7000 splash logo renders with a WRONG PALETTE

**Felipe, observing the running emulator:** the big green "KN7000" logo **does not fade — it stays
there**, and *"seems to be using an incorrect color palette"* (green with red speckles). It is a
glitch, not a boot animation. **Do not repeat my mistake of assuming it is mid-fade.**

### What the bisect established

```
  armB  no data              plain PMEM: A- screen,  NO logo
  armC  data minus HPGINI    plain PMEM: A- screen,  LOGO STUCK
  armA  all four files       P.MEM bank list,        LOGO STUCK
```

⇒ **HPGINI is NOT the cause** — it is what produces the P.MEM bank list. The stuck logo comes from
**UMDINI / FAVINI / CTMINI** being present. The logo appears ONLY when data is installed.

### ★ The leading hypothesis — my own byte-order fix

The three signed files are loaded **word-swapped** (`ROM_GROUPWORD | ROM_REVERSE`), which I added
because the `"JK "` signature read back as `"KJ"` without it. A swap that is correct for
**record/header fields** will **corrupt a palette or a pixel run**, which are byte streams. That
matches the evidence exactly: structure parses fine (signature validates, bank list appears) while
imagery renders with mangled colour.

⇒ **A file may mix both kinds of data, so one blanket load convention cannot be right for all of
it.** Find which region the splash pixels/palette come from and check whether that part wants
UNSWAPPED bytes.

### ★ Corroborating precedent (same project, same day)

The KN5000 wallpaper path (`Gfx_LoadSplashBMP` `0xFAE86D`, `Flash_SaveSplashScreen` `0xFAF00B`) has
three non-obvious properties, any of which produces exactly this failure if mishandled:
- the **palette is stored AFTER the pixels** (pixels `0x3C0000`–`0x3D2BFF`, palette
  `0x3D2C00`–`0x3D2FFF`),
- rows are un-flipped to **top-down**,
- palette entries are reordered **BGR0 → RGB0**.

Green-with-red-speckles is what a channel-order or stride mistake looks like.

### Next steps

1. Find where the KN7000 draws the splash/wallpaper — search for the pixel source and its palette
   (the composited LCD image lives at `0x9CE00000`, share `lcdbuf`).
2. Determine whether those bytes come from the custom flash and, if so, from which of the four
   files / which offset range.
3. Test the load convention **per region**, not per file: keep the swap where headers are validated,
   drop it where pixels/palette live. `ROM_LOAD` vs `ROMX_LOAD(... ROM_GROUPWORD|ROM_REVERSE ...)`
   over sub-ranges of the same file is fine.
4. Falsifier: if unswapping the image range does not fix the colours, the palette is coming from
   somewhere we have not modelled (IC19 picture ROM is `NO_DUMP`), and this is not a byte-order bug.

## Reproducing the comparison

```sh
# frame-synchronised, LCD only -- do NOT compare whole frames, artwork and splash timing swamp it
SP=<scratchpad>;  cd ~/compartilhado/kn7000-emulator
# late.lua snapshots once at frame 3000; both.lua also presses FAVORITES
./run.sh -window -autoboot_script $SP/late.lua -seconds_to_run 55
# crop LCD = (168, 78, 818, 318) from the 1000x750 snapshot, then diff with PIL
```

⚠ Withhold files by moving them out of `kn7000-emulator/roms/kn7000/` — and **always move them
back**. `ROM_OPTIONAL` means the region simply stays `0xFF`.

## Commits (kn7000_mame)

```
c95f33b  keep the Initial Data files OPTIONAL
39ccf71  retire the fav_preload stopgap
429c38d  place all four Initial Data files correctly -- custom data now populates
ac13ad4  actually map the custom flash -- the map-time guard silently skipped it
c9862c2  model IC21 as a real flash device so saving custom data works
```

---

## ★★ THE FIRMWARE ERASES SECTOR 0x20000 AT BOOT (2026-08-03)

Arming the write tap and changing a setting produced no writes from the setting — but revealed
that **boot itself issues a complete AMD SECTOR ERASE**, and the target is the CTMINI payload:

```
  W 9680AAA8 = 00AA    unlock 1
  W 96805554 = 0055    unlock 2
  W 9680AAA8 = 0080    ERASE SETUP
  W 9680AAA8 = 00AA    unlock 1
  W 96805554 = 0055    unlock 2
  W 96820000 = 0030    SECTOR ERASE CONFIRM  <- chip 0x20000
```

⇒ **The write path works end to end** — the firmware programs, and our `FUJITSU_29LV160B` decodes
the sequence. That is the first confirmed flash *programming* in this emulator.

⇒ ⚠ **But it erases the sector our CTMINI payload occupies, on every boot.** All 31 writes are
complete by ~t=25s. Whatever the firmware decides during validation, it is clearing 0x20000.
Flash reads still reach 4.5 M in a 50 s run, so data is being consumed — but the payload sector may
be getting wiped after (or before) use. **This needs tracing: which routine issues the erase, and
what condition triggers it.** It may explain residual oddities including the stuck splash.

**TRANSPOSE does not persist to flash** — zero writes across four presses. If a setting-driven write
is wanted for testing, use one of the handlers that names flash explicitly
(`CustomPanelFlashFunc`, `LangSetFlashFunc`, `MainWallSetFlashFunc`, `DataProtectOKFunc`),
reachable from the settings menus rather than a panel button.

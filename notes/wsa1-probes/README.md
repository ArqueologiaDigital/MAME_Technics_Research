# SX-WSA1R probes

Three MAME Lua autoboot scripts.  Each answers one question about the
development driver in `src/mame/matsushita/wsa1.cpp`, and each produced a number
quoted in that file's comments or in the session notes.  Run them against the
focused build:

```
cd ~/compartilhado/kn7000_mame_build
DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms -skip_gameinfo -str 6 -window \
    -autoboot_script ~/compartilhado/kn7000_mame/notes/wsa1-probes/<script>
```

⚠ The ROM filenames in `technics_roms/roms/wsa1/` are `wsa1_os_v2.icNN`, but the
driver's `ROM_LOAD` names are the factory part numbers.  Stage a `roms/wsa1r/`
with these four links (CRC32s verified to match the driver):

| link name          | file             | CRC32    |
|--------------------|------------------|----------|
| `qsigcwsa1ax.ic12` | `wsa1_os_v2.ic12`| 5f34af46 |
| `qsigcwsa1bx.ic13` | `wsa1_os_v2.ic13`| f3f84441 |
| `qsigcwsa1cx.ic28` | `wsa1_os_v2.ic28`| 855c8ac4 |
| `qsigcwsa1dx.bin`  | `wsa1_os_v2.ic21`| 735ae465 |

⚠ MAME's Lua GC silently collects a tap or a notifier that is not held in a
global.  Every script here keeps its handles in `_G`.

## `wsa1_lcd_port_tap.lua` — does the boot ever reach the panel?

Installs a read tap and a write tap on CPU 1's program space at
`0x790000-0x790001`, the SED1330's status/data and data/command ports, and
prints a running access count.

**Signal:** any nonzero count means CPU 1 got as far as `LCD_Init_SED1330`.

**Result, 2026-08-25, 6 s of emulated time: `total accesses = 0`.**  The LCD
controller is wired up correctly but is never driven — CPU 1's boot does not
reach the display init in the time modelled.  That is upstream of the display
work, so a blank window is the expected state of this driver today and is not
evidence against the SED1330 wiring.

## `wsa1_lcd_vram_probe.lua` — is anything drawn?

Walks all 32 KiB of the SED1330's display RAM once a second and counts non-zero
bytes.  Independent of the tap above: it would catch drawing that arrives by any
route.

**Result, same run: 0 non-zero bytes at every sample.**  Consistent with the
tap.

## `wsa1_pc_sample.lua` — where is each processor actually spending its time?

Samples both processors' `CURPC` once per frame and prints the five hottest
addresses every five seconds.

**Result, same run:**

```
cpu1  F951A7 F95184 F951A9 F5AA9E F5AA9A
cpu2  F9A382 F9A347 F9A36D F9A399 F9A385
```

CPU 2's whole histogram sits inside the uPD6383GF microcode upload's READY poll
on P9 bit 3 (`0xF9A19F` and seventeen siblings, each bounded at 0x1F40
iterations).  With no callback bound, MAME's port read returns 0, so every byte
of the upload runs the poll to its bound.  That is where CPU 2's boot time goes.
The driver deliberately does NOT fake the READY line — see the block in
`wsa1r(machine_config &)`.

Neither processor is wedged: both histograms are spread over several addresses,
not pinned to one.

## Not reproduced here

The `spinscan` that produced the census of unbounded wait loops in prom_c lives
in another session's scratchpad and was not available to copy.  Its findings are
quoted in the driver comments; the script itself is **not** preserved, and that
census should be treated as unreproducible until it is rerun and committed.

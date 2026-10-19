# Integrating into a MAME tree

> **Quick build:** run `./build.sh` (env: `MAME_SRC`, `BUILD_TREE`, `ROM_SRC`). It
> assembles a disposable build tree, symlinks these overlay files into it, applies
> the registration below, and compiles a focused `kn7000` MAME. The steps below
> document what it does.


These files are an overlay: each sits at the path it occupies inside MAME. To
build them into a MAME checkout:

## 1. Copy the files in

The overlay is 55 files across eight directories, each already at the path it
occupies inside MAME, so one recursive copy places them all:

```
cp -r src/. <mame>/src/
```

`build.sh` step 2 does the same with symlinks, one `ln -sf` per file, and that
step is the authoritative inventory: the CPU cores `mn10300/`, `sharc/`,
`tlcs900/` and `upd6383/`, `video/sed1330.h`,
`bus/technics/kn5000/hdae5000`, the KN5000/KN6000/KN7000/KN1500 and SX-WSA1
drivers with their control-panel and tone-generator devices, and four layouts.
37 of the 55 replace a file MAME already ships, so an upstream fix to one of
those is inert here until it is ported across —
`notes/overlay-upstream-sync/overlay_vs_upstream.sh` is the gate that catches it.

`src/devices/cpu/mn10300/mn103dasm.{cpp,h}` (the disassembler) already exists in
MAME and is reused unchanged.

## 2. The MN10300 CPU registration

Upstream MAME has registered the MN10300 as a full CPU since the core was
merged, so `scripts/src/cpu.lua` needs no change: the overlay's `mn10300.cpp`
and `mn10300.h` simply replace upstream's. (Before that merge this step
promoted the disassembler-only block to a full-CPU one; `build.sh` step 3 still
checks for it and leaves an already-registered core alone.)

## 3. Register the driver

Upstream's `src/mame/mame.lst` already carries most of this overlay's systems, in
the `matsushita` section:

```
@source:matsushita/kn5000.cpp
kn5000

@source:matsushita/kn7000.cpp
kn2400
kn2600
kn6000
kn6500
kn7000

@source:matsushita/wsa1.cpp
wsa1r
```

The two it does not carry are `kn1500`, which gets its own
`@source:matsushita/kn1500.cpp` block, and `wsa1`, listed under its `wsa1r`
parent. `build.sh` step 4 inserts exactly those, testing for each system
separately so that a system upstream already lists is left untouched.

## 4. Provide the ROM images

MAME will look for a `kn7000` romset holding the even and odd halves of both
flash pairs — `kn7000_program_even.rom`, `kn7000_program_odd.rom`,
`kn7000_table_even.rom`, `kn7000_table_odd.rom`, 2 MB each, split even/odd from
the decompressed `.SLD` images. Place them in a `kn7000.zip` (or a
`roms/kn7000/` folder) on your ROM path. Their CRC/SHA1 are already filled in the
driver and they load as good dumps: the `.SLD`/`.INF` block checksums verify the
decompression. The rest of the set is optional — the synthetic wave and rhythm
images, flagged `BAD_DUMP` because they are generated rather than read from the
physical chips, and the four Initial Data disk payloads for the custom-data flash.
`tools/make-roms.sh` rebuilds the whole set from the preserved sources, checks it
against its md5 manifest, or restores it from the private `technics_roms` repo
that holds the authoritative copies.

## 5. Build and run

```
./build.sh                                          # focused build, Qt debugger included
./kn7000 kn7000 -skip_gameinfo                      # boots the firmware to its home screen
./kn7000 kn7000 -debug                              # step the boot code
./kn7000 -validate kn7000                           # driver definition check (0 errors)
```

`build.sh` runs `make SUBTARGET=kn7000 SOURCES=<list> REGENIE=1 USE_QTDEBUG=1
QT_HOME=/usr/lib/qt6 -j<nproc>`, where `<list>` is the driver *and* every
`src/mame` device `.cpp` it pulls in — `kn7000_cpanel`, `kn7000_tonegen`, the
KN6000 and KN5000 pairs, the WSA1 set. Each of those carries the
`DEFINE_DEVICE_TYPE` for a device `kn7000.cpp` instantiates, so naming only
`kn7000.cpp` compiles the driver and leaves those types undefined at link time.
`-skip_gameinfo` also skips the red warnings screen, which the build patches into
`ui.cpp`. The CPU starts fetching at `0x48400000` (`jmp 0x4840FF7E`) and boots
into the MILK kernel, which loads its library code out of the program flash into
the RAM window aliased at `0x4C000000`/`0x8C000000` (see §6). The driver ships a
clickable front-panel layout (`src/mame/layout/kn7000.lay`, from
`tools/gen_lay.py`): 164 bound panel controls and 101 indicator LEDs, in a
Compact and a Full Unit view plus four per-block views.

## 6. Current state of knowledge

The MN10300 execute core now implements **~99.94% of the instruction forms the
firmware actually uses** (the remainder are unused `udf*` coprocessor ops). Its
semantics were cross-checked by an independent Python interpreter
(`technics-roms-disasm/kn7000/tools/mn10300_sim.py`) that executes **4.59 million** real
boot instructions coherently — through hardware init and BSS setup and into the
MILK kernel — and on into the **library/kernel code at `0x4C000000`** (the C
runtime + kernel; 7,965 calls to 298 entry points). That code is **not a separate
chip**: early in kernel init, `InitializeBlock27` (`0x484D7BBD`) copies ~253,720
bytes out of the program flash at `0x487B8FD1` to `0x8C000000`, and `0x4C000000`
is the same RAM seen through bit 30, so the driver maps both windows onto one
share and the boot runs real library code with no dump and no HLE. See
`notes/library-rom-loading.md`; `notes/library-rom-api.md` catalogues the entry
points.

What *is* mapped and understood, for building out the peripherals:

* **I/O** — 112 registers across five banks, decoded in `notes/io-map.md`
  (timers `0x32000000`, GPIO `0x36008000`, the 58-register LCD/panel block
  `0x34000000`, the **dual tone generators** `0x98040000`/`0x98050000`).
* **Subsystems** — the firmware's event/dispatch, tasks/scheduler, display and
  storage layers are documented from the disassembly on the technics-docs site
  (KN7000 section), with the relevant work-RAM globals listed in the driver
  header.

So the productive next step is to keep moving I/O out of the driver's catch-all
`io_r`/`io_w` — still the handler for `0x20000000`, the timers at `0x32000000`,
the LCD/panel block at `0x34000000` and the GPIO at `0x36008000` — into device
models, using the register map and subsystem docs. The tone generators, control
panel, SD card, FDC and the MIDI UARTs are already devices in the machine config;
the rear USB co-processor is not, and its own firmware is undumped
(`notes/FINDINGS-usb-subsystem.md`).

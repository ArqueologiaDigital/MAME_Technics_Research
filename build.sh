#!/bin/bash
# Build a MAME with the KN7000 driver + MN10300 CPU core from this overlay repo.
#
# This overlay holds only the KN7000-specific files (src/devices/cpu/mn10300/
# mn10300.* and src/mame/matsushita/kn7000.cpp). To compile them they must sit
# inside a full MAME source tree with the CPU + driver registered in the build
# system. This script assembles a *disposable* build tree next to the overlay,
# SYMLINKS the overlay's source files into it (so this git repo stays the single
# source of truth -- editing a file here is immediately live in the build), and
# builds a focused `kn7000` MAME.
#
# The build tree is regenerable and NOT version-controlled; only this repo is.
# Re-running is incremental (the tree and its object files are reused).
#
# Overridable environment variables:
#   MAME_SRC   full MAME checkout to copy the tree from   (default: ../mame)
#   BUILD_TREE where the build tree lives (non-volatile!) (default: ../kn7000_mame_build)
#   ROM_SRC    dir holding kn7000_program.rom/kn7000_table.rom for a run test
#   JOBS       parallel compile jobs                       (default: nproc)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
MAME_SRC="${MAME_SRC:-$HERE/../mame}"
BUILD_TREE="${BUILD_TREE:-$HERE/../kn7000_mame_build}"
ROM_SRC="${ROM_SRC:-}"
JOBS="${JOBS:-$(nproc)}"
LOG="$BUILD_TREE/kn7000_build.log"

echo "overlay:    $HERE"
echo "mame src:   $MAME_SRC"
echo "build tree: $BUILD_TREE"

# 1. Assemble the build tree (reuse if present for a fast incremental build).
if [ ! -d "$BUILD_TREE/src" ]; then
	echo "==> creating build tree (rsync from $MAME_SRC, excluding .git) ..."
	rsync -a --exclude='.git' "$MAME_SRC"/ "$BUILD_TREE"/
else
	echo "==> reusing existing build tree"
fi

# 2. Symlink the overlay's source files in (single source of truth = this repo).
ln -sf "$HERE/src/devices/cpu/mn10300/mn10300.cpp"           "$BUILD_TREE/src/devices/cpu/mn10300/mn10300.cpp"
ln -sf "$HERE/src/devices/cpu/mn10300/mn10300.h"             "$BUILD_TREE/src/devices/cpu/mn10300/mn10300.h"
ln -sf "$HERE/src/devices/cpu/mn10300/mn10300_insn_length.h" "$BUILD_TREE/src/devices/cpu/mn10300/mn10300_insn_length.h"
# Effects-DSP LLE (Phase F): the SHARC core is forked here to add the adsp21065l_device variant
# (KN7000 IC306). Only sharc.h/sharc.cpp are overlaid; the rest of the SHARC core is stock.
ln -sf "$HERE/src/devices/cpu/sharc/sharc.h"                 "$BUILD_TREE/src/devices/cpu/sharc/sharc.h"
ln -sf "$HERE/src/devices/cpu/sharc/sharc.cpp"               "$BUILD_TREE/src/devices/cpu/sharc/sharc.cpp"
ln -sf "$HERE/src/devices/cpu/sharc/sharcops.hxx"            "$BUILD_TREE/src/devices/cpu/sharc/sharcops.hxx"
ln -sf "$HERE/src/devices/cpu/sharc/sharcdrc.cpp"            "$BUILD_TREE/src/devices/cpu/sharc/sharcdrc.cpp"
ln -sf "$HERE/src/devices/cpu/sharc/sharcfe.cpp"             "$BUILD_TREE/src/devices/cpu/sharc/sharcfe.cpp"
mkdir -p "$BUILD_TREE/src/devices/machine"
ln -sf "$HERE/src/devices/machine/spi_sdcard.cpp"            "$BUILD_TREE/src/devices/machine/spi_sdcard.cpp"
ln -sf "$HERE/src/devices/machine/spi_sdcard.h"              "$BUILD_TREE/src/devices/machine/spi_sdcard.h"
ln -sf "$HERE/src/mame/matsushita/kn7000.cpp"                "$BUILD_TREE/src/mame/matsushita/kn7000.cpp"
ln -sf "$HERE/src/mame/matsushita/kn7000_tonegen.cpp"        "$BUILD_TREE/src/mame/matsushita/kn7000_tonegen.cpp"
ln -sf "$HERE/src/mame/matsushita/kn7000_tonegen.h"          "$BUILD_TREE/src/mame/matsushita/kn7000_tonegen.h"
ln -sf "$HERE/src/mame/matsushita/kn7000_cpanel.cpp"         "$BUILD_TREE/src/mame/matsushita/kn7000_cpanel.cpp"
ln -sf "$HERE/src/mame/matsushita/kn7000_cpanel.h"           "$BUILD_TREE/src/mame/matsushita/kn7000_cpanel.h"
ln -sf "$HERE/src/mame/matsushita/kn_cpanel.cpp"             "$BUILD_TREE/src/mame/matsushita/kn_cpanel.cpp"
ln -sf "$HERE/src/mame/matsushita/kn_cpanel.h"               "$BUILD_TREE/src/mame/matsushita/kn_cpanel.h"
ln -sf "$HERE/src/mame/matsushita/kn6000_cpanel.cpp"         "$BUILD_TREE/src/mame/matsushita/kn6000_cpanel.cpp"
ln -sf "$HERE/src/mame/matsushita/kn6000_cpanel.h"           "$BUILD_TREE/src/mame/matsushita/kn6000_cpanel.h"
ln -sf "$HERE/src/mame/matsushita/kn1500.cpp"                "$BUILD_TREE/src/mame/matsushita/kn1500.cpp"
mkdir -p "$BUILD_TREE/src/mame/layout"
ln -sf "$HERE/src/mame/layout/kn7000.lay"                    "$BUILD_TREE/src/mame/layout/kn7000.lay"
ln -sf "$HERE/src/mame/layout/kn6000.lay"                    "$BUILD_TREE/src/mame/layout/kn6000.lay"
echo "==> overlay files symlinked"

# 3. Register the MN10300 as a full CPU (idempotent).
python3 - "$BUILD_TREE/scripts/src/cpu.lua" <<'PY'
import sys
p = sys.argv[1]; s = open(p).read()
if 'mn10300/mn10300.cpp' not in s:
    anchor = 'if opt_tool(CPUS, "MN10300") then'
    block = ('if CPUS["MN10300"] then\n\tfiles {\n'
             '\t\tMAME_DIR .. "src/devices/cpu/mn10300/mn10300.cpp",\n'
             '\t\tMAME_DIR .. "src/devices/cpu/mn10300/mn10300.h",\n\t}\nend\n\n')
    open(p, 'w').write(s.replace(anchor, block + anchor, 1))
    print("cpu.lua: MN10300 promoted to full CPU")
else:
    print("cpu.lua: already patched")
# Effects-DSP LLE (Phase F): the KN7000's IC306 is an ADSP-21065L SHARC. MAME's SHARC
# core has a DRC, but cpu.lua's DRC_CPUS list names it "ADSP21062" while the actual CPU
# flag is "ADSP2106X" -- so in a SHARC-only focused build CPU_INCLUDE_DRC stays false and
# drcuml fails to link. Add the correct flag so the DRC backend is pulled in (idempotent).
s2 = open(p).read()
# NB: check the DRC_CPUS LIST specifically -- "ADSP2106X" always appears elsewhere in cpu.lua
# as the SHARC's CPU token (CPUS["ADSP2106X"]), so a bare `'"ADSP2106X"' not in s2` check is
# always false and the patch never fires (the DRC backend then fails to link).
if 'DRC_CPUS = { "ADSP2106X"' not in s2 and 'DRC_CPUS = { "ADSP21062"' in s2:
    s2 = s2.replace('DRC_CPUS = { "ADSP21062"', 'DRC_CPUS = { "ADSP2106X", "ADSP21062"', 1)
    open(p, 'w').write(s2)
    print("cpu.lua: DRC_CPUS += ADSP2106X (SHARC DRC linkage)")
else:
    print("cpu.lua: DRC_CPUS already has ADSP2106X")
PY

# 4. Register the driver in the driver list (idempotent).
python3 - "$BUILD_TREE/src/mame/mame.lst" <<'PY'
import sys
p = sys.argv[1]; s = open(p).read()
changed = False
if '\nkn7000\n' not in s:
    anchor = '@source:matsushita/kn5000.cpp\nkn5000\n'
    s = s.replace(anchor, anchor + '\n@source:matsushita/kn7000.cpp\nkn7000\n', 1)
    changed = True
# KN6000 / KN6500 / KN2400 / KN2600 draft drivers live in the same source file as kn7000.
for drv in ('kn6000', 'kn6500', 'kn2400', 'kn2600'):
    if '\n' + drv + '\n' not in s:
        s = s.replace('@source:matsushita/kn7000.cpp\nkn7000\n',
                      '@source:matsushita/kn7000.cpp\nkn7000\n' + drv + '\n', 1)
        changed = True
if '\nkn1500\n' not in s:
    anchor = '@source:matsushita/kn5000.cpp\nkn5000\n'
    s = s.replace(anchor, anchor + '\n@source:matsushita/kn1500.cpp\nkn1500\n', 1)
    changed = True
if changed:
    open(p, 'w').write(s)
    print("mame.lst: kn7000 family + kn1500 registered")
else:
    print("mame.lst: already registered")
PY

# 4b. Make -skip_gameinfo also skip the startup WARNINGS screen (idempotent).
# The Technics drivers are MACHINE_NOT_WORKING and use a BAD_DUMP synthetic wave ROM, so MAME's
# red "There are known problems with this system" screen shows on every launch and blocks until a
# keypress. Stock MAME's -skip_gameinfo only gates the game-info screen, not the warnings screen
# (ui.cpp: `bool show_warnings = true;`). This patch ties show_warnings to skip_gameinfo so our
# launcher (run.sh passes -skip_gameinfo) boots straight into the instrument. Anyone running the
# raw binary without -skip_gameinfo still sees the honest warning.
python3 - "$BUILD_TREE/src/frontend/mame/ui/ui.cpp" <<'PY'
import sys
p = sys.argv[1]; s = open(p).read()
old = '\tbool show_warnings = true;'
new = '\tbool show_warnings = !machine().options().skip_gameinfo(); // KN7000: -skip_gameinfo also skips warnings'
if old in s:
    open(p, 'w').write(s.replace(old, new, 1))
    print("ui.cpp: show_warnings tied to skip_gameinfo")
elif 'KN7000: -skip_gameinfo also skips warnings' in s:
    print("ui.cpp: already patched")
else:
    print("ui.cpp: WARNING anchor not found (upstream changed?) -- warnings screen not suppressed")
PY

# 5. Stage ROMs for a run test, if provided.
if [ -n "$ROM_SRC" ] && [ -f "$ROM_SRC/kn7000_program.rom" ]; then
	mkdir -p "$BUILD_TREE/roms/kn7000"
	cp -f "$ROM_SRC/kn7000_program.rom" "$ROM_SRC/kn7000_table.rom" "$BUILD_TREE/roms/kn7000/"
	echo "==> ROMs staged into roms/kn7000/"
fi

# 6. Focused build (REGENIE picks up the cpu.lua / mame.lst edits).
echo "==> building (log: $LOG) ..."
cd "$BUILD_TREE"
# USE_QTDEBUG=0: build without the Qt debugger (no Qt 'moc' needed).
make SUBTARGET=kn7000 SOURCES=src/mame/matsushita/kn7000.cpp,src/mame/matsushita/kn7000_tonegen.cpp,src/mame/matsushita/kn_cpanel.cpp,src/mame/matsushita/kn7000_cpanel.cpp,src/mame/matsushita/kn6000_cpanel.cpp,src/mame/matsushita/kn1500.cpp REGENIE=1 USE_QTDEBUG=0 -j"$JOBS" 2>&1 | tee "$LOG"
echo "==> done. Binary:"; ls -la "$BUILD_TREE"/kn7000 2>/dev/null || echo "(no binary — check $LOG)"

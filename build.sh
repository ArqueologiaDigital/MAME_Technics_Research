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
ln -sf "$HERE/src/mame/matsushita/kn7000.cpp"                "$BUILD_TREE/src/mame/matsushita/kn7000.cpp"
ln -sf "$HERE/src/mame/matsushita/kn1500.cpp"                "$BUILD_TREE/src/mame/matsushita/kn1500.cpp"
mkdir -p "$BUILD_TREE/src/mame/layout"
ln -sf "$HERE/src/mame/layout/kn7000.lay"                    "$BUILD_TREE/src/mame/layout/kn7000.lay"
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
make SUBTARGET=kn7000 SOURCES=src/mame/matsushita/kn7000.cpp,src/mame/matsushita/kn1500.cpp REGENIE=1 USE_QTDEBUG=0 -j"$JOBS" 2>&1 | tee "$LOG"
echo "==> done. Binary:"; ls -la "$BUILD_TREE"/kn7000 2>/dev/null || echo "(no binary — check $LOG)"

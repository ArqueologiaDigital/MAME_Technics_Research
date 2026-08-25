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
#
# THE BUILD ALWAYS INCLUDES MAME'S Qt DEBUGGER (USE_QTDEBUG=1). Run it with -debug:
#     cd ../kn7000-emulator && ./kn7000 kn5000 -rompath ./roms -debug
# There is ONE build and ONE binary. Felipe uses the Qt debugger and nothing else, so the
# old QTDEBUG=0/1 split is gone -- it existed only to avoid needing Qt, and its two modes
# shared -DUSE_QTDEBUG-sensitive object files, which silently produced a binary that built
# fine but had the qt module stripped at link time. One mode cannot desync with itself.
# Requires Qt dev packages (Debian: qt6-base-dev).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
MAME_SRC="${MAME_SRC:-$HERE/../mame}"
BUILD_TREE="${BUILD_TREE:-$HERE/../kn7000_mame_build}"
ROM_SRC="${ROM_SRC:-}"
JOBS="${JOBS:-$(nproc)}"

# ---------------------------------------------------------------------------------------
# GUARD: the base tree must be on kn7000-base.
#
# MAME_SRC is rsynced wholesale into the build tree, so whatever branch it sits on becomes
# the build.  The upstream-PR branch (technics-rom-record) carries its OWN
# src/mame/matsushita/kn7000.cpp -- a ROM-record skeleton with no CPU -- plus its own
# mame.lst entries.  Building from it silently produces a driver that is not this project's.
# That happened on 2026-08-02 and is exactly what this check prevents.
#
# PR work belongs in the sibling worktree ~/compartilhado/mame-pr.  Neither tree should ever
# change branch; see tools/sync-check.sh.
# ---------------------------------------------------------------------------------------
if _br=$(git -C "$MAME_SRC" rev-parse --abbrev-ref HEAD 2>/dev/null); then
	if [ "$_br" != "kn7000-base" ]; then
		echo "ERROR: MAME_SRC ($MAME_SRC) is on branch '$_br', expected 'kn7000-base'." >&2
		echo "       Do not switch branches in this tree -- it is the overlay's base tree." >&2
		echo "       Upstream PR work lives in the ~/compartilhado/mame-pr worktree." >&2
		echo "       Override deliberately with ALLOW_ANY_BASE=1 if you really mean it." >&2
		[ "${ALLOW_ANY_BASE:-0}" = "1" ] || exit 1
	fi
fi
# ~/.local/bin/qmake6 is a STUB that always echoes ~/.local/share/noqt.  It was added back when
# this script built WITHOUT Qt, to stop "-I$(shell qmake6 -query ...)" collapsing to a bare "-I"
# that swallowed the following -std=c++20.  It also HIDES the real qmake6, so MAME's moc probe
# (scripts/src/osd/modules.lua: qmake6 -query QT_HOST_LIBEXECS) finds nothing and the build dies
# with "Qt's Meta Object Compiler (moc) wasn't found!".  Put the real Qt6 bin dir first.
for _qtbin in /usr/lib/qt6/bin /usr/lib/x86_64-linux-gnu/qt6/bin; do
	if [ -x "$_qtbin/qmake6" ]; then PATH="$_qtbin:$PATH"; export PATH; break; fi
done
if [ "$(qmake6 -query QT_HOST_LIBEXECS 2>/dev/null)" = "$HOME/.local/share/noqt" ]; then
	echo "ERROR: the real qmake6 is shadowed by the ~/.local/bin/qmake6 stub." >&2
	echo "       Install qt6-base-dev, or prepend the dir holding the real qmake6 to PATH." >&2
	exit 1
fi
# Sanity-check moc against the headers we compile against.  A moc from a DIFFERENT Qt emits code
# the installed headers do not declare (we hit "Qt 6.10.2" moc output vs 6.8.2 headers ->
# "qt_staticMetaObjectStaticContent<...> expected primary-expression", which reads like a MAME
# incompatibility but is really just stale/mismatched moc).
_mocver=$("$(qmake6 -query QT_HOST_LIBEXECS)/moc" --version 2>/dev/null | awk '{print $NF}')
_hdrver=$(sed -n 's/^#define QT_VERSION_STR "\(.*\)"/\1/p' \
	"$(qmake6 -query QT_INSTALL_HEADERS)/QtCore/qconfig.h" 2>/dev/null)
if [ -n "$_mocver" ] && [ -n "$_hdrver" ] && [ "$_mocver" != "$_hdrver" ]; then
	echo "WARNING: moc is $_mocver but Qt headers are $_hdrver -- generated moc output may not compile." >&2
	echo "         If it fails, clear: $BUILD_TREE/build/generated/osd/modules/debugger/qt" >&2
fi
LOG="$BUILD_TREE/kn7000_build.log"

echo "overlay:    $HERE"
echo "mame src:   $MAME_SRC"
echo "build tree: $BUILD_TREE"

# 1. Assemble the build tree.
#
# This rsync runs EVERY TIME, not just on first creation. It used to be skipped whenever the
# build tree already existed, which meant any change to the base tree -- a cherry-picked core
# device, a bus registration -- silently never reached the build. On 2026-08-02 that produced a
# "successful" build that did not contain the flash device types it was supposed to, and the
# failure only surfaced one build later. rsync is incremental, so unchanged files keep their
# mtimes and the compile stays fast; the cost of always syncing is a directory walk.
#
# 'build' is excluded so object files and the generated project survive, and the overlay's own
# files are re-symlinked in step 2 (rsync replaces a symlink with the base-tree copy).
echo "==> syncing build tree from $MAME_SRC ..."
rsync -a --exclude='.git' --exclude='/build/' --exclude='/kn7000' --exclude='/kn7000_build.log' \
	"$MAME_SRC"/ "$BUILD_TREE"/

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
ln -sf "$HERE/src/mame/matsushita/kn_tonegen.cpp"            "$BUILD_TREE/src/mame/matsushita/kn_tonegen.cpp"
ln -sf "$HERE/src/mame/matsushita/kn_tonegen.h"              "$BUILD_TREE/src/mame/matsushita/kn_tonegen.h"
ln -sf "$HERE/src/mame/matsushita/kn7000_tonegen.cpp"        "$BUILD_TREE/src/mame/matsushita/kn7000_tonegen.cpp"
ln -sf "$HERE/src/mame/matsushita/kn7000_tonegen.h"          "$BUILD_TREE/src/mame/matsushita/kn7000_tonegen.h"
ln -sf "$HERE/src/mame/matsushita/kn6000_tonegen.cpp"        "$BUILD_TREE/src/mame/matsushita/kn6000_tonegen.cpp"
ln -sf "$HERE/src/mame/matsushita/kn6000_tonegen.h"          "$BUILD_TREE/src/mame/matsushita/kn6000_tonegen.h"
ln -sf "$HERE/src/mame/matsushita/kn7000_cpanel.cpp"         "$BUILD_TREE/src/mame/matsushita/kn7000_cpanel.cpp"
ln -sf "$HERE/src/mame/matsushita/kn7000_cpanel.h"           "$BUILD_TREE/src/mame/matsushita/kn7000_cpanel.h"
ln -sf "$HERE/src/mame/matsushita/kn_cpanel.cpp"             "$BUILD_TREE/src/mame/matsushita/kn_cpanel.cpp"
ln -sf "$HERE/src/mame/matsushita/kn_cpanel.h"               "$BUILD_TREE/src/mame/matsushita/kn_cpanel.h"
ln -sf "$HERE/src/mame/matsushita/kn6000_cpanel.cpp"         "$BUILD_TREE/src/mame/matsushita/kn6000_cpanel.cpp"
ln -sf "$HERE/src/mame/matsushita/kn6000_cpanel.h"           "$BUILD_TREE/src/mame/matsushita/kn6000_cpanel.h"
ln -sf "$HERE/src/mame/matsushita/kn1500.cpp"                "$BUILD_TREE/src/mame/matsushita/kn1500.cpp"
# Technics SX-WSA1R (two TLCS-900/H TMP95C061 at 28 MHz).  The DEVELOPMENT copy of
# this driver lives here; the upstream-PR copy is on branch technics-wsa1 in the
# MAME checkout and the two deliberately diverge.
#
# sed1330 is overlaid alongside it: stock sed1330_device leaves update_graphics()
# an empty function body, so the WSA1's all-graphics three-layer mode drives a
# correctly-programmed but permanently blank panel.  See the note at the top of
# the overlay copy of sed1330.h.
ln -sf "$HERE/src/mame/matsushita/wsa1.cpp"                  "$BUILD_TREE/src/mame/matsushita/wsa1.cpp"
# The control-panel microcontroller (M37471M2196S on CONTROL PANEL 1), HLE'd as a
# device on CPU 1's serial channel 1 -- the same part and the same protocol as the
# KN5000's panel.  See the byte evidence at the top of wsa1_cpanel.h.
ln -sf "$HERE/src/mame/matsushita/wsa1_cpanel.cpp"           "$BUILD_TREE/src/mame/matsushita/wsa1_cpanel.cpp"
ln -sf "$HERE/src/mame/matsushita/wsa1_cpanel.h"             "$BUILD_TREE/src/mame/matsushita/wsa1_cpanel.h"
mkdir -p "$BUILD_TREE/src/devices/video"
ln -sf "$HERE/src/devices/video/sed1330.cpp"                 "$BUILD_TREE/src/devices/video/sed1330.cpp"
ln -sf "$HERE/src/devices/video/sed1330.h"                   "$BUILD_TREE/src/devices/video/sed1330.h"
# KN5000 (SX-KN5000): the driver itself is upstream, but a large body of work is not --
# the tone generator (IC303), the DSP1 stub (IC311), FDC/UART/MIDI wiring, the SNS NMI
# payload checksum and the Program data wheel. Those live here as overlay files exactly
# like the KN7000 ones, so this repo stays the single source of truth for every Technics
# model. See notes/upstream-patches/README.md for the matching patch series.
mkdir -p "$BUILD_TREE/src/devices/cpu/tlcs900" "$BUILD_TREE/src/devices/bus/technics/kn5000"
# tmp95c061: a ONE LINE fix, and the file is overlaid only to carry it.  Internal
# address 0x12 is P6 and its write side dispatched to port_w<PORT_7>, so every P6
# write went to PORT_7.  The SX-WSA1R needs P6 bit 5 (the serial EEPROM's chip
# select) to arrive, and CPU 1's `ldio P6,0x1B` was clobbering the link handshake
# shadow on P7.  Keep the diff to that line; see the comment at it.
# ⚠ tmp95c061.h IS ALSO OVERLAID NOW.  It carries the serial-channel-1 additions
# the SX-WSA1R's control panel needs (sc1_txd / sc1_mod / sc1_rxd); the .h and the
# .cpp have to move together, so symlink both or neither.
ln -sf "$HERE/src/devices/cpu/tlcs900/tmp95c061.cpp"         "$BUILD_TREE/src/devices/cpu/tlcs900/tmp95c061.cpp"
ln -sf "$HERE/src/devices/cpu/tlcs900/tmp95c061.h"           "$BUILD_TREE/src/devices/cpu/tlcs900/tmp95c061.h"
ln -sf "$HERE/src/devices/cpu/tlcs900/tmp94c241.cpp"         "$BUILD_TREE/src/devices/cpu/tlcs900/tmp94c241.cpp"
ln -sf "$HERE/src/devices/cpu/tlcs900/tmp94c241.h"           "$BUILD_TREE/src/devices/cpu/tlcs900/tmp94c241.h"
ln -sf "$HERE/src/devices/cpu/tlcs900/tmp94c241_serial.cpp"  "$BUILD_TREE/src/devices/cpu/tlcs900/tmp94c241_serial.cpp"
ln -sf "$HERE/src/devices/cpu/tlcs900/tmp94c241_serial.h"    "$BUILD_TREE/src/devices/cpu/tlcs900/tmp94c241_serial.h"
# ⚠ THE TLCS-900 SHARED CORE IS OVERLAID TOO, for control register 0x3C/0x7C --
# INTNEST, the interrupt nesting counter.  MAME had no such register: every
# access fell through p_CR16's default into m_dummy, the scratch word that ALSO
# absorbs every other undecoded control-register reference, and nothing ever
# counted.  The SX-WSA1R's whole RTOS hangs off it (prom_a IRQ_Epilogue enters
# the scheduler only when it reads 1) so without it the machine never got past
# its splash.  tlcs900.h holds the storage and the accept helper, tlcs900.cpp the
# save-state entry and the resets, 900tbl.hxx the decode and the RETI decrement,
# and each device calls the helper where it accepts an interrupt.
# ⚠ These four files are shared with EVERY tlcs900 driver, ours and upstream's
# (ngp, namcos10, dvd-n5xx, kkcount on the TMP95C061; taitopjc/taitotz on the
# TMP95C063).  tmp96c141.cpp is deliberately NOT overlaid: its check_irqs() is
# empty, so it has no acceptance site to count at.
ln -sf "$HERE/src/devices/cpu/tlcs900/tlcs900.h"             "$BUILD_TREE/src/devices/cpu/tlcs900/tlcs900.h"
ln -sf "$HERE/src/devices/cpu/tlcs900/tlcs900.cpp"           "$BUILD_TREE/src/devices/cpu/tlcs900/tlcs900.cpp"
ln -sf "$HERE/src/devices/cpu/tlcs900/900tbl.hxx"            "$BUILD_TREE/src/devices/cpu/tlcs900/900tbl.hxx"
ln -sf "$HERE/src/devices/cpu/tlcs900/tmp95c063.cpp"         "$BUILD_TREE/src/devices/cpu/tlcs900/tmp95c063.cpp"
ln -sf "$HERE/src/devices/bus/technics/kn5000/hdae5000.cpp"  "$BUILD_TREE/src/devices/bus/technics/kn5000/hdae5000.cpp"
ln -sf "$HERE/src/mame/matsushita/kn5000.cpp"                "$BUILD_TREE/src/mame/matsushita/kn5000.cpp"
ln -sf "$HERE/src/mame/matsushita/kn5000_cpanel.cpp"         "$BUILD_TREE/src/mame/matsushita/kn5000_cpanel.cpp"
ln -sf "$HERE/src/mame/matsushita/kn5000_cpanel.h"           "$BUILD_TREE/src/mame/matsushita/kn5000_cpanel.h"
# NEC uPD6383GF (KN5000 IC311) -- DRAFT DSP core + disassembler.  No audio, and
# the core is instantiated DISABLED; it exists to hold the uploaded microcode in
# a real, debugger-visible I-RAM and to make the corpus readable by unidasm.
mkdir -p "$BUILD_TREE/src/devices/cpu/upd6383"
ln -sf "$HERE/src/devices/cpu/upd6383/upd6383.cpp"           "$BUILD_TREE/src/devices/cpu/upd6383/upd6383.cpp"
ln -sf "$HERE/src/devices/cpu/upd6383/upd6383.h"             "$BUILD_TREE/src/devices/cpu/upd6383/upd6383.h"
ln -sf "$HERE/src/devices/cpu/upd6383/upd6383d.cpp"          "$BUILD_TREE/src/devices/cpu/upd6383/upd6383d.cpp"
ln -sf "$HERE/src/devices/cpu/upd6383/upd6383d.h"            "$BUILD_TREE/src/devices/cpu/upd6383/upd6383d.h"
ln -sf "$HERE/src/mame/matsushita/kn5000_tonegen.cpp"        "$BUILD_TREE/src/mame/matsushita/kn5000_tonegen.cpp"
ln -sf "$HERE/src/mame/matsushita/kn5000_tonegen.h"          "$BUILD_TREE/src/mame/matsushita/kn5000_tonegen.h"
# GENERATED (tools/gen_kn5000_pitch_trim.py) -- the firmware's per-selector absolute-pitch
# constant C, #included by kn5000_tonegen.cpp. It exists only in this overlay, so a missing
# symlink here is a hard compile error, not a silent behaviour change.
ln -sf "$HERE/src/mame/matsushita/kn5000_pitch_trim.hxx"     "$BUILD_TREE/src/mame/matsushita/kn5000_pitch_trim.hxx"
mkdir -p "$BUILD_TREE/src/mame/layout"
ln -sf "$HERE/src/mame/layout/kn7000.lay"                    "$BUILD_TREE/src/mame/layout/kn7000.lay"
ln -sf "$HERE/src/mame/layout/kn6000.lay"                    "$BUILD_TREE/src/mame/layout/kn6000.lay"
ln -sf "$HERE/src/mame/layout/kn5000.lay"                    "$BUILD_TREE/src/mame/layout/kn5000.lay"
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

# 3b. Register the NEC uPD6383GF draft DSP core + disassembler (idempotent).
# CPUS["UPD6383"] is FORCED true: in a focused build the CPU list is derived from
# the drivers, and although kn5000.cpp now includes upd6383.h the annotation
# scan is fragile enough that forcing it is the honest way to keep the core in
# the binary. The disassembler is also added to unidasm's arch table so the
# extracted microprogram images can be read with `unidasm -arch upd6383`.
python3 - "$BUILD_TREE/scripts/src/cpu.lua" <<'PY'
import sys
p = sys.argv[1]; s = open(p).read()
if 'upd6383/upd6383.cpp' in s:
    print("cpu.lua: UPD6383 already registered")
else:
    anchor = '--------------------------------------------------\n-- NEC uPD7725\n'
    block = ('--------------------------------------------------\n'
             '-- NEC uPD6383GF (Technics KN5000 effects DSP -- DRAFT)\n'
             '--@src/devices/cpu/upd6383/upd6383.h,CPUS["UPD6383"] = true\n'
             '--------------------------------------------------\n\n'
             'CPUS["UPD6383"] = true\n\n'
             'if CPUS["UPD6383"] then\n\tfiles {\n'
             '\t\tMAME_DIR .. "src/devices/cpu/upd6383/upd6383.cpp",\n'
             '\t\tMAME_DIR .. "src/devices/cpu/upd6383/upd6383.h",\n\t}\nend\n\n'
             'if opt_tool(CPUS, "UPD6383") then\n'
             '\ttable.insert(disasm_files , MAME_DIR .. "src/devices/cpu/upd6383/upd6383d.cpp")\n'
             '\ttable.insert(disasm_files , MAME_DIR .. "src/devices/cpu/upd6383/upd6383d.h")\n'
             'end\n\n')
    if anchor not in s:
        anchor = 'if CPUS["UPD7725"] then'
        block = block + anchor
    else:
        block = block + anchor
    open(p, 'w').write(s.replace(anchor, block, 1))
    print("cpu.lua: UPD6383 registered (forced on)")
PY

python3 - "$BUILD_TREE/src/tools/unidasm.cpp" <<'PY'
import sys
p = sys.argv[1]; s = open(p).read()
if 'upd6383d.h' in s:
    print("unidasm.cpp: upd6383 already registered")
else:
    s = s.replace('#include "cpu/upd7725/dasm7725.h"',
                  '#include "cpu/upd6383/upd6383d.h"\n#include "cpu/upd7725/dasm7725.h"', 1)
    entry = ('\t{ "upd6383",         be,  0, []() -> util::disasm_interface * '
             '{ return new upd6383_disassembler; } },\n')
    anchor = '\t{ "upd7725",'
    i = s.index(anchor)
    s = s[:i] + entry + s[i:]
    open(p, 'w').write(s)
    print("unidasm.cpp: upd6383 registered")
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
# Technics SX-WSA1R and SX-WSA1.  Neither exists upstream on kn7000-base, so this
# creates both; they are registered here rather than in ~/compartilhado/mame so
# that the base tree stays untouched, exactly as with the cpu.lua edits above.
# Two systems, one source file: the same ROM set runs in the rack module and in
# the keyboard, and the firmware picks its code paths from a strap on PB bit 0.
# The clone is listed under the parent, which is the order mame.lst uses.
if '\nwsa1r\n' not in s:
    anchor = '@source:matsushita/kn5000.cpp\nkn5000\n'
    s = s.replace(anchor, anchor + '\n@source:matsushita/wsa1.cpp\nwsa1r\nwsa1\n', 1)
    changed = True
if changed:
    open(p, 'w').write(s)
    print("mame.lst: kn7000 family + kn1500 + wsa1r/wsa1 registered")
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

SOURCES_LIST="src/mame/matsushita/kn7000.cpp,src/mame/matsushita/kn_tonegen.cpp,src/mame/matsushita/kn7000_tonegen.cpp,src/mame/matsushita/kn6000_tonegen.cpp,src/mame/matsushita/kn_cpanel.cpp,src/mame/matsushita/kn7000_cpanel.cpp,src/mame/matsushita/kn6000_cpanel.cpp,src/mame/matsushita/kn1500.cpp"
# The KN5000 rides in the same focused binary. NOTE: mame.lst already carries an
# `@source:matsushita/kn5000.cpp` anchor upstream, so if kn5000.cpp is NOT listed in SOURCES
# the filtered driver list still emits `driver_kn5000` while the object file is never
# compiled -- that is exactly the "only driver_kn5000 undefined" link failure seen before.
# Listing the driver *and* every device .cpp it pulls in from src/mame keeps them in step.
SOURCES_LIST="$SOURCES_LIST,src/mame/matsushita/kn5000.cpp,src/mame/matsushita/kn5000_cpanel.cpp,src/mame/matsushita/kn5000_tonegen.cpp"
# The SX-WSA1R rides in the same focused binary.  Its driver/@source: pair has to
# stay in step with the mame.lst injection in step 4 for the same reason the
# KN5000 comment above gives.  No cpu.lua or video.lua edit is needed: makedep
# follows #include recursively, so "cpu/tlcs900/tmp95c061.h" keeps CPUS["TLCS900"]
# on (kn5000.cpp already does) and "video/sed1330.h" turns VIDEOS["SED1330"] on
# through the annotation at scripts/src/video.lua:1474.
SOURCES_LIST="$SOURCES_LIST,src/mame/matsushita/wsa1.cpp,src/mame/matsushita/wsa1_cpanel.cpp"
make SUBTARGET=kn7000 SOURCES="$SOURCES_LIST" REGENIE=1 USE_QTDEBUG=1 -j"$JOBS" 2>&1 | tee "$LOG"
echo "==> done. Binary:"; ls -la "$BUILD_TREE/kn7000" 2>/dev/null || echo "(no binary — check $LOG)"
echo "==> Qt debugger included. Run it with -debug:"
echo "    cd $HERE/../kn7000-emulator && ./kn7000 kn5000 -rompath ./roms -debug"

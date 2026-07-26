#!/bin/bash
# license:BSD-3-Clause
# copyright-holders:Felipe Sanches
#
# MIRROR-AGREEMENT CHECK for the NEC uPD6383GF (KN5000 IC311) disassembler.
#
# The ISA is described by two files that are meant to be identical in behaviour:
#
#     kn7000_mame/src/devices/cpu/upd6383/upd6383d.{cpp,h}     (MAME, C++)
#     kn5000-roms-disasm/dsp/tools/dsp_disasm.py               (the ISA reference)
#
# They have drifted before, and each time nothing noticed because nothing ever
# ran them side by side.  This script closes that: it builds the C++ side into a
# tiny stdin/stdout harness (tools/upd6383d_dump.cpp), runs BOTH over the whole
# 3057-word microprogram corpus extracted from the Sub CPU ROM, and diffs the
# output line for line.  Exit 0 and "MIRRORS AGREE" iff every line matches.
#
#     tools/upd6383d_diff.sh                 # build + compare
#     tools/upd6383d_diff.sh -k              # keep the two dumps for inspection
#
# Env: BUILD_TREE (default ../kn7000_mame_build), DISASM_REPO (default
# ../kn5000-roms-disasm), WORK (default a mktemp dir).
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
OVERLAY="$(dirname "$HERE")"
BUILD_TREE="${BUILD_TREE:-$OVERLAY/../kn7000_mame_build}"
DISASM_REPO="${DISASM_REPO:-$OVERLAY/../kn5000-roms-disasm}"
KEEP=0
[ "${1:-}" = "-k" ] && KEEP=1
WORK="${WORK:-$(mktemp -d)}"

[ -d "$BUILD_TREE/src/emu" ] || { echo "ERROR: no MAME build tree at $BUILD_TREE" >&2; exit 1; }
[ -f "$DISASM_REPO/dsp/tools/dsp_disasm.py" ] || { echo "ERROR: no dsp_disasm.py under $DISASM_REPO" >&2; exit 1; }

# 1. build the C++ harness against THE OVERLAY's disassembler (the build tree
#    symlinks it, but compile the overlay path directly so this works even
#    before ./build.sh has ever run).
echo "==> building upd6383d_dump ..."
g++ -std=c++20 -O1 -DCRLF=2 -DLSB_FIRST -DPUGIXML_HEADER_ONLY \
	-I "$BUILD_TREE/src/osd" -I "$BUILD_TREE/src/emu" -I "$BUILD_TREE/src/devices" \
	-I "$BUILD_TREE/src/lib" -I "$BUILD_TREE/src/lib/util" -I "$BUILD_TREE/3rdparty" \
	-I "$BUILD_TREE/build/generated/emu" -I "$BUILD_TREE/3rdparty/asio/include" \
	-I "$BUILD_TREE/3rdparty/expat/lib" -I "$OVERLAY/src/devices" \
	"$HERE/upd6383d_dump.cpp" "$OVERLAY/src/devices/cpu/upd6383/upd6383d.cpp" \
	"$BUILD_TREE/src/lib/util/disasmintf.cpp" "$BUILD_TREE/src/lib/util/strformat.cpp" \
	-o "$WORK/upd6383d_dump"

# 2. extract the corpus -- the 60-word shared header, the 23-word output stage
#    and all 38 distinct effect-body images, with their real I-RAM indices (the
#    C00 self-address annotation depends on them).
echo "==> extracting the corpus ..."
python3 - "$HERE" "$DISASM_REPO" > "$WORK/words.txt" <<'PY'
import sys, os
tools, repo = sys.argv[1], sys.argv[2]
sys.path.insert(0, tools)
import kn5000_dsp_extract as E
rom = E.Rom(os.path.join(repo, "original_ROMs", "kn5000_subprogram_v142.rom"))
def words(addr, limit=None):
    ir, _c, _o = E.parse_stream(rom, addr, limit=limit) if limit else E.parse_stream(rom, addr)
    return [int.from_bytes(bytes(w), "big") for _a, ws, _l in ir for w in ws]
for i, w in enumerate(words(0x01E496, 40)[:60]): print("%d %010X" % (i, w))
for i, w in enumerate(words(0x01E63C, 40)[:23]): print("%d %010X" % (60 + i, w))
seen = {}
for a in range(100):
    if a in {79, 88, 89, 90, 91}: continue
    try: ws = words(rom.u32le(0x0001ED7C + 4 * a))
    except Exception: continue
    if ws: seen.setdefault(tuple(ws), a)
for ws, a in sorted(seen.items(), key=lambda kv: kv[1]):
    base = 200 if a == 16 else 84          # the reverb is the one unit-1 image
    for i, w in enumerate(ws): print("%d %010X" % (base + i, w))
PY

# 3. run both and compare
"$WORK/upd6383d_dump" < "$WORK/words.txt" > "$WORK/cpp.txt"
PYTHONPATH="$DISASM_REPO/dsp/tools" python3 - "$WORK" > "$WORK/py.txt" <<'PY'
import sys
import dsp_disasm as D
for line in open(sys.argv[1] + "/words.txt"):
    at, w = line.split()
    print(D.text(int(w, 16), int(at)))
PY

n=$(wc -l < "$WORK/words.txt")
if diff -q "$WORK/py.txt" "$WORK/cpp.txt" > /dev/null; then
	echo "MIRRORS AGREE -- $n/$n words render identically in C++ and Python"
	rc=0
else
	echo "*** MIRRORS DISAGREE ***"
	diff "$WORK/py.txt" "$WORK/cpp.txt" | head -40
	rc=1
fi

if [ "$KEEP" = 1 ]; then echo "dumps kept in $WORK"; else rm -rf "$WORK"; fi
exit $rc

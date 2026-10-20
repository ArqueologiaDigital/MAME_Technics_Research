#!/bin/bash
# oracle_attribution_msgr.sh OLD_BINARY NEW_BINARY OUTDIR -- is the move of the gate's KN7000 audio oracle the MSGR
# read-back, and nothing else?
# tools/gate.sh's oracle (tools/rigs/money.lua: one keybed note held at t=16-17 s, 22 s captured with -wavwrite) moved
# from bd02a9c15b580d6b4b4c0a42f78a1fcb when the 21065L's own reads of MSGR0-7 (IOP 0x08-0x0F) started returning the
# stored value (sharc.cpp iop65l_r) instead of 0. Runs the gate's recipe in the published folder, each run with its own
# copy of nvram/kn7000 (no IC23 there: a blank IC23, as in the gate):
#   old         OLD_BINARY as it is: must give bd02a9c1..., or something else moved (folder, SD image);
#   new         NEW_BINARY as it is: the new hash;
#   new-msgr0   NEW_BINARY with a read tap on the DSP's data space 0x08-0x0F that returns 0, as the old iop65l_r did.
#               If this gives the old hash bit for bit, the move is the MSGR read-back and nothing else.
# Prints one line per run: name, md5 of the WAV, and its peak RMS over channels 1-2.
set -euo pipefail
OLD="$(readlink -f "$1")"; NEW="$(readlink -f "$2")"; OUT="$(mkdir -p "$3" && cd "$3" && pwd)"
HERE="$(cd "$(dirname "$0")" && pwd)"; RIGS="$HERE/../../tools/rigs"
EMU="${EMU_DIR:-$HOME/compartilhado/kn7000-emulator}"
cat > "$OUT/oracle_msgr0.lua" <<LUA
-- the old iop65l_r: the DSP's own reads of MSGR0-7 give 0; then the oracle rig itself
local dm = manager.machine.devices[":dsp"].spaces["data"]
_G.MSGR0 = dm:install_read_tap(0x08, 0x0f, "msgr_zero", function(o, d, m) return 0 end)
dofile("$RIGS/money.lua")
LUA
for RUN in old new new-msgr0; do
  O="$OUT/$RUN"; mkdir -p "$O/nv"; cp -r "$EMU/nvram/kn7000" "$O/nv/"
  BIN="$NEW"; SCRIPT="$RIGS/money.lua"
  [ "$RUN" = old ] && BIN="$OLD"
  [ "$RUN" = new-msgr0 ] && SCRIPT="$OUT/oracle_msgr0.lua"
  ( cd "$EMU" && DISPLAY="${DISPLAY:-:0}" timeout 500 "$BIN" kn7000 -rompath ./roms -pluginspath ./plugins -skip_gameinfo \
      -window -nothrottle -seconds_to_run 22 -autoboot_script "$SCRIPT" -wavwrite "$O/o.wav" \
      -cfg_directory "$O/cfg" -nvram_directory "$O/nv" -harddisk sdcard_from_real_kn7000.img > "$O/run.log" 2>&1 ) || true
  if [ -s "$O/o.wav" ]; then
    rms=$(python3 -I - "$O/o.wav" <<'PY'
import struct, sys, wave
w = wave.open(sys.argv[1]); n, ch = w.getnframes(), w.getnchannels()
s = struct.unpack("<%dh" % (n * ch), w.readframes(n))
r = [(sum(float(v) * v for v in s[c::ch]) / max(n, 1)) ** 0.5 for c in range(ch)]
print("%.1f" % max(r[1:] if ch > 1 else r))
PY
)
    echo "$RUN: $(md5sum "$O/o.wav" | cut -d' ' -f1)  rms $rms"
  else
    echo "$RUN: no wav (see $O/run.log)"
  fi
done

#!/bin/bash
# oracle_attribution.sh OLD_BINARY NEW_BINARY OUTDIR -- why did the gate's KN7000 audio oracle move?
# tools/gate.sh's oracle (tools/rigs/money.lua: one keybed note held at t=16-17 s, 22 s captured with -wavwrite)
# went from 4c3a522a63f4e86fe9f7d7c8d94f5dbe to bd02a9c15b580d6b4b4c0a42f78a1fcb when the four PRs were ported in.
# The port changes what the firmware sees in two windows: IC18 at 0x40000000 (the old binary left it unmapped,
# reading 0) instead of the synthetic rhythm resource at 0x54E00000, and IC19 at 0x57800000 (unmapped before).
# Runs the gate's recipe in the published folder, each run with its own copy of nvram/kn7000:
#   old      OLD_BINARY as it is: must give the old baseline, or something else moved (folder, SD image);
#   new      NEW_BINARY as it is: the new hash;
#   new-old  NEW_BINARY with oracle_oldmap.lua: Lua read taps make 0x40000000-0x407FFFFF and 0x57800000-0x57FFFFFF
#            read 0 again and serve roms/kn7000/kn7000_rhythms_synthetic.rom at 0x54E00000 (0xFF past its end), as
#            the old binary did. If this gives the old hash, the move is the rhythm and picture ROMs, nothing else.
# Prints one line per run: name, md5 of the WAV, and its peak RMS over channels 1-2.
set -euo pipefail
OLD="$(readlink -f "$1")"; NEW="$(readlink -f "$2")"; OUT="$(mkdir -p "$3" && cd "$3" && pwd)"
HERE="$(cd "$(dirname "$0")" && pwd)"; RIGS="$HERE/../../tools/rigs"
EMU="${EMU_DIR:-$HOME/compartilhado/kn7000-emulator}"
cat > "$OUT/oracle_oldmap.lua" <<LUA
-- the old binary's memory picture around the rhythm and picture windows, then the oracle rig itself
local sp = manager.machine.devices[":maincpu"].spaces["program"]
local f = io.open("$EMU/roms/kn7000/kn7000_rhythms_synthetic.rom", "rb"); _G.SYN = f:read("a"); f:close()
_G.T1 = sp:install_read_tap(0x40000000, 0x407fffff, "ic18_off", function(o, d, m) return 0 end)
_G.T2 = sp:install_read_tap(0x57800000, 0x57ffffff, "ic19_off", function(o, d, m) return 0 end)
_G.T3 = sp:install_read_tap(0x54e00000, 0x551fffff, "syn_rhythms", function(o, d, m)
  local i = (o - 0x54e00000) & ~3
  if i + 4 <= #_G.SYN then return string.unpack("<I4", _G.SYN, i + 1) end
  local v = 0
  for k = 3, 0, -1 do v = (v << 8) | ((i + k < #_G.SYN) and _G.SYN:byte(i + k + 1) or 0xff) end
  return v
end)
dofile("$RIGS/money.lua")
LUA
for RUN in old new new-old; do
  O="$OUT/$RUN"; mkdir -p "$O/nv"; cp -r "$EMU/nvram/kn7000" "$O/nv/"
  BIN="$NEW"; SCRIPT="$RIGS/money.lua"
  [ "$RUN" = old ] && BIN="$OLD"
  [ "$RUN" = new-old ] && SCRIPT="$OUT/oracle_oldmap.lua"
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

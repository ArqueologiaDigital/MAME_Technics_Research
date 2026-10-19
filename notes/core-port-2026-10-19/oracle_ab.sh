#!/bin/bash
# oracle_ab.sh OUTDIR BINARY... -- the gate's KN7000 audio oracle (tools/gate.sh, rigs/money.lua: one keybed note held
# at t=16-17 s, 22 s captured with -wavwrite, the real SD image in the slot) for each binary, without publishing it.
# Runs in the published folder (EMU_DIR) with its ROMs, plugins and SD image, each run with its own copy of
# nvram/kn7000 and a fresh cfg. Prints one line per binary: md5 of the WAV (the gate compares this with ORACLE_MD5)
# and its peak RMS over channels 1-2.
set -euo pipefail
OUT="$(mkdir -p "$1" && cd "$1" && pwd)"; shift
HERE="$(cd "$(dirname "$0")" && pwd)"; RIGS="$HERE/../../tools/rigs"
EMU="${EMU_DIR:-$HOME/compartilhado/kn7000-emulator}"
n=0
for B in "$@"; do
  n=$((n + 1)); BIN="$(readlink -f "$B")"; O="$OUT/$n"; mkdir -p "$O/nv"; cp -r "$EMU/nvram/kn7000" "$O/nv/"
  ( cd "$EMU" && DISPLAY="${DISPLAY:-:0}" timeout 500 "$BIN" kn7000 -rompath ./roms -pluginspath ./plugins -skip_gameinfo \
      -window -nothrottle -seconds_to_run 22 -autoboot_script "$RIGS/money.lua" -wavwrite "$O/o.wav" \
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
    echo "$(basename "$BIN"): $(md5sum "$O/o.wav" | cut -d' ' -f1)  rms $rms"
  else
    echo "$(basename "$BIN"): no wav (see $O/run.log)"
  fi
done

#!/bin/bash
# run_checks.sh OUT [machine...] -- the two light DSP checks of PLAN-2026-10-21-dsp-emulation.md:
#   1. G3: save state at 30 s (kn7000), load it in a new session, does DM 0xC003 still move? (g3_state.lua)
#   2. is the effects DSP's kernel running at 30 s on each machine, and at what rate? (dsp_alive.lua)
# OUT is scratch (default parent: $TMPDIR, i.e. ~/compartilhado/tmp, never /tmp). EMU defaults to the published
# emulator. Machines default to kn7000 kn6000 kn6500 kn2400. Prints the "G3 ..." and "ALIVE ..." lines.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
EMU="${EMU:-$HOME/compartilhado/kn7000-emulator}"
O="$(mkdir -p "${1:?usage: run_checks.sh OUT [machine...]}" && cd "$1" && pwd)"; shift
if [ $# -gt 0 ]; then MACHINES=("$@"); else MACHINES=(kn7000 kn6000 kn6500 kn2400); fi
run() {  # run DIR [env...] -- [mame args...]
  local d="$1"; shift; mkdir -p "$d"
  local envs=(); while [ "$1" != "--" ]; do envs+=("$1"); shift; done; shift
  ( cd "$EMU" && env "${envs[@]}" DISPLAY="${DISPLAY:-:0}" timeout 900 ./kn7000 "$@" -rompath ./roms \
      -pluginspath ./plugins -skip_gameinfo -window -nothrottle -sound none \
      -nvram_directory "$d/nv" -cfg_directory "$d/cfg" -state_directory "$d/sta" ) > "$d/run.log" 2>&1
}
echo "emulator md5 $(md5sum < "$EMU/kn7000" | cut -c1-32)"
run "$O/g3" G3_MODE=save G3_AT=30 -- kn7000 -autoboot_script "$HERE/g3_state.lua"; grep -h '^G3' "$O/g3/run.log"
mv "$O/g3/run.log" "$O/g3/save.log"
run "$O/g3" G3_MODE=load -- kn7000 -state g3 -autoboot_script "$HERE/g3_state.lua"; grep -h '^G3' "$O/g3/run.log"
for m in "${MACHINES[@]}"; do
  run "$O/alive-$m" ALIVE_AT=30 -- "$m" -autoboot_script "$HERE/dsp_alive.lua"; grep -h '^ALIVE' "$O/alive-$m/run.log"
done

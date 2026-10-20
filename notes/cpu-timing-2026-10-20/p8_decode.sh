#!/bin/bash
# p8_decode.sh RUNDIR -- pull DSPRATE.BIN + DUMPLIST.TXT off a run_test.sh --dsprate run's sd.img and decode it
set -euo pipefail
R="$(readlink -f "${1:?run dir}")"
T=~/compartilhado/technics-roms-disasm/kn7000/tools/cnv_romdump
mkdir -p "$R/files"
python3 -I "$T/fatls.py" "$R/sd.img" 'C:\DSPRATE.BIN' "$R/files/DSPRATE.BIN"
python3 -I "$T/fatls.py" "$R/sd.img" 'C:\DUMPLIST.TXT' "$R/files/DUMPLIST.TXT"
cd "$T" && python3 check_dsp_probe.py "$R/files" > "$R/check.txt" 2>&1 || true
grep -E "calibration|BC change|samples per tick|access timing:|commonest pair|re-latch|steps per ms over|verdict" "$R/check.txt" | head -20

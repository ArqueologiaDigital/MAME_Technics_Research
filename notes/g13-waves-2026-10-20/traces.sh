#!/usr/bin/env bash
# traces.sh NAME OUTDIR [BINARY] -- regenerate one of the tone-generator captures the README quotes.
#
#   strap5     -- the driver as it was (hardware subtype 5): PIANO ORGAN STRINGS BRASS, all 61 keys
#                 (this is "trace2"; "trace1" was the same rig over 12 groups, keys C2..C7)
#   strap1     -- subtype 1 forced by a Lua read tap (G13_STRAP=0x0400) on the binary that still
#                 reports 5: 15 groups, 16 keys each ("trace5"); set TRACE_GROUPS=... TRACE_KEYS=... to vary
#   play       -- the new binary as built, with -wavwrite: 6 groups, keys C3 C4 A4 C5 held 1.2 s
#                 ("play1"; analyse with wavpitch.py OUTDIR/trace.txt OUTDIR/o.wav)
#
# BIOS=v13 runs Felipe's firmware (893) instead of v16 (941); the voice-record base moves with it.
# Runs in the published emulator folder (ROMs, plugins, SD image) with a fresh cfg and a copy
# of nvram/kn7000 without IC23, like the gate. BINARY defaults to the published one.
# Scratch goes to OUTDIR (put it under ~/compartilhado/tmp/, never /tmp).
set -euo pipefail
NAME="$1"; OUT="$(mkdir -p "$2" && cd "$2" && pwd)"; BIN="$(readlink -f "${3:-$HOME/compartilhado/kn7000-emulator/kn7000}")"
HERE="$(cd "$(dirname "$0")" && pwd)"
EMU="${EMU_DIR:-$HOME/compartilhado/kn7000-emulator}"
mkdir -p "$OUT/cfg" "$OUT/nv"
cp -r "$EMU/nvram/kn7000" "$OUT/nv/"
rm -f -- "${OUT:?}/nv/kn7000/ic23"
EXTRA=()
case "$NAME" in
	strap5) export G13_KEYS=ALL G13_ON=0.3 G13_GAP=0.15 G13_GROUPS="${TRACE_GROUPS:-PIANO,ORGAN,STRINGS,BRASS}"; SECS=200 ;;
	strap1) export G13_STRAP=0x0400 G13_KEYS="${TRACE_KEYS:-C2,E2,G#2,C3,E3,G#3,C4,E4,G#4,C5,E5,G#5,C6,E6,G#6,C7}" G13_ON=0.35 G13_GAP=0.15
	        export G13_GROUPS="${TRACE_GROUPS:-PIANO,ORGAN,STRINGS,BRASS,GUITAR,BASS,SYNTH,PAD,MALLET,SAX,WORLD,TABORGAN,DRAWBAR,ACCREG,EXPLORER}"; SECS=200 ;;
	play)   export G13_KEYS=C3,C4,A4,C5 G13_ON=1.2 G13_GAP=0.6 G13_GROUPS="${TRACE_GROUPS:-PIANO,ORGAN,STRINGS,BASS,BRASS,MALLET}"; SECS=200
	        EXTRA=(-wavwrite "$OUT/o.wav") ;;
	*) echo "usage: $0 strap5|strap1|play OUTDIR [BINARY]" >&2; exit 2 ;;
esac
export G13_OUT="$OUT/trace.txt"
BIOS="${BIOS:-v16}"
[ "$BIOS" = v13 ] && export G13_RECBASE=0x500A10E0
cd "$EMU"
DISPLAY="${DISPLAY:-:0}" timeout 2400 "$BIN" kn7000 -bios "$BIOS" -rompath ./roms -pluginspath ./plugins -skip_gameinfo \
	-window -nothrottle -seconds_to_run "$SECS" -autoboot_script "$HERE/tg_trace.lua" \
	-cfg_directory "$OUT/cfg" -nvram_directory "$OUT/nv" -harddisk sdcard_from_real_kn7000.img "${EXTRA[@]}" \
	> "$OUT/run.log" 2>&1 || true
grep -c '^W' "$OUT/trace.txt" | sed 's/^/register writes: /'
md5sum "$OUT/trace.txt"

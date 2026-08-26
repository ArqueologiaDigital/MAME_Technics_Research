#!/bin/sh
# Which five-key column beside the LCD is SEG3 and which is SEG9?
#
# QUESTION IT ANSWERS.  The CP1/CP2 schematic traces SW25-29 to SEG3 and SW73-77
# to SEG9, but neither column is legended on either board and prom_a's switch->LED
# table gives both the same family tag 0x0604, so only the P.C. BOARD page's
# left-right orientation separated them.  That was the last reading in
# src/mame/layout/wsa1r.lay resting on geometry alone.
#
# THE DISCRIMINATOR IS THE FIRMWARE'S OWN DISK MENU.  Screen 0x40 draws FOUR
# entries down the LEFT of the LCD (DISK LOAD / DISK SAVE / MIDI FILE DIRECT PLAY /
# FLOPPY DISK FORMAT) and TWO down the RIGHT (LOAD SINGLE SOUND / LOAD SINGLE
# COMBI.).  So the column with four live rows IS the left one.  This script puts
# that menu up by pressing MENU DISK, then presses each of the ten soft keys in
# turn and prints the family-B screen id the firmware moves to.
#
# Both presses are driven through the LAYOUT's own inputtag/inputmask -- the rig
# reads them out of the .lay -- so this also proves those bindings end to end.
#
# RUN (needs a built + published binary; see tools/publish-binary.sh)
#   sh notes/wsa1-probes/wsa1_softkey_columns.sh
#
# RESULT, 2026-08-26, one run per row:
#
#   row  LEFT (SEG9)          RIGHT (SEG3)
#   1    47  DISK LOAD        54  LOAD SINGLE SOUND
#   2    4C  DISK SAVE        53  LOAD SINGLE COMBI.
#   3    45  MIDI FILE D.P.   40  (no change)
#   4    50  FLOPPY FORMAT    40  (no change)
#   5    40  (no change)      40  (no change)
#
# Four live rows on SEG9 and two on SEG3, exactly as the menu is drawn.
# ==> SEG9 is the LEFT column and SEG3 is the RIGHT column.  Not geometry: the
#     firmware said so.
set -eu
EMU="${EMU_DIR:-/home/fsanches/compartilhado/kn7000-emulator}"
RIG="${RIG:-/home/fsanches/compartilhado/kn7000_mame/tools/rigs/wsa1r_layout_button.lua}"
OUT="${OUT:-${TMPDIR:-/tmp}/wsa1_softkey_columns}"
mkdir -p "$OUT"

printf '%-24s %s\n' "soft key" "family-B screen after the press (0x40 = the DISK menu itself)"
for side in LEFT RIGHT; do
	for row in 1st 2nd 3rd 4th 5th; do
		K="$side column, $row"
		d="$OUT/$(echo "$K" | tr ' ,' '__')"
		rm -rf "$d"
		line=$(cd "$EMU" && BTN="MENU DISK" BTN2="$K" SNAP_AT=45 DISPLAY="${DISPLAY:-:0}" \
			timeout 300 ./kn7000 wsa1r -rompath ./roms -skip_gameinfo -window -nomax \
			-resolution 1600x520 -snapshot_directory "$d" -autoboot_script "$RIG" 2>&1 \
			| grep "SECOND t" || true)
		printf '%-24s %s\n' "$K" "$(echo "$line" | sed 's/.*screens //; s/ after.*//')"
	done
done

#!/bin/bash
# aw_ic23_check.sh MAME_BINARY OUTDIR -- what does the Another World SP7001 build do to IC23, now that the emulator
# models IC23 as the 256 KB battery-backed SRAM it is (repeating every 256 KB through 0x44000000-0x44FFFFFF) and the
# session ends with the firmware's own power-down (POWER OFF stamps IC23's checksum)?
#   control   -bios sp7001, the AW card in the slot but not started; POWER OFF at 60 s; then a second boot from
#             what that saved, which reads the firmware's verdict (ic23_probe.lua at 40 s)
#   game      the same, but SD CARD LOAD at 12 s starts the game, which runs until POWER OFF at 60 s
# Then compares the two saved IC23 images (the bytes the game changed) with ic23_diff.py.
# The card is rebuilt with research-scratch/aw-real-unit-sweep/build_card.sh into its scratch (122 MB, read-only
# template); each run writes its own copy, deleted afterwards. sp7001's validity byte is 0x5006CC90
# (tools/kn7000_bios_addresses.py --ram 0x5006CC80).
set -euo pipefail
# MAME keeps a non-default BIOS's NVRAM in its own folder (-bios sp7001 -> nvram/kn7000_0/, v13 -> kn7000_4/)
ic23() { ls "$1"/nv/kn7000*/ic23 2>/dev/null | head -1; }
BIN="$(readlink -f "$1")"; OUT="$(mkdir -p "$2" && cd "$2" && pwd)"
HERE="$(cd "$(dirname "$0")" && pwd)"; EMU="${EMU_DIR:-$HOME/compartilhado/kn7000-emulator}"
SWEEP="$HOME/compartilhado/tmp/aw-real-unit-sweep"
[ -f "$SWEEP/another_sd.img" ] || bash "$HOME/compartilhado/research-scratch/aw-real-unit-sweep/build_card.sh" > "$OUT/build_card.log" 2>&1
for R in control game; do
  O="$OUT/$R"; mkdir -p "$O/nv"; rm -rf -- "${O:?}/nv"; mkdir -p "$O/nv"
  cp "$SWEEP/another_sd.img" "$O/sd.img"; chmod u+w "$O/sd.img"
  P=""; [ "$R" = game ] && P=1
  ( cd "$O" && AW_PRESS="$P" POWER_AT=60 IC23_VALID=0x5006CC90 DISPLAY="${DISPLAY:-:0}" timeout 900 "$BIN" kn7000 \
      -bios sp7001 -rompath "$EMU/roms" -pluginspath "$EMU/plugins" -skip_gameinfo -window -nothrottle \
      -harddisk "$O/sd.img" -cfg_directory cfg1 -nvram_directory nv -snapshot_directory snap \
      -autoboot_script "$HERE/aw_power.lua" > run1.log 2>&1 ) || true
  cp "$(ic23 "$O")" "$O/ic23-after-session.bin"
  ( cd "$O" && IC23_AT=40 IC23_VALID=0x5006CC90 DISPLAY="${DISPLAY:-:0}" timeout 900 "$BIN" kn7000 \
      -bios sp7001 -rompath "$EMU/roms" -pluginspath "$EMU/plugins" -skip_gameinfo -window -nothrottle \
      -harddisk "$O/sd.img" -cfg_directory cfg2 -nvram_directory nv -autoboot_script "$HERE/ic23_probe.lua" > run2.log 2>&1 ) || true
  rm -f -- "$O/sd.img"
  echo "$R session: $(grep -m1 '^PROBE t=' "$O/run1.log" || echo 'no PROBE line')"
  echo "$R saved:   $(python3 -I "$HERE/ic23_file.py" "$O/ic23-after-session.bin")"
  echo "$R reboot:  $(grep -m1 '^PROBE t=' "$O/run2.log" || echo 'no PROBE line')"
done
python3 -I "$HERE/ic23_diff.py" "$OUT/control/ic23-after-session.bin" "$OUT/game/ic23-after-session.bin"

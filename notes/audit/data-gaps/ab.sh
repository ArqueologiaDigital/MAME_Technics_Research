#!/usr/bin/env bash
set -u
S=/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/c6cf97f4-b4f1-4ba1-adc0-85474706b167/scratchpad
E=/home/fsanches/compartilhado/kn7000-emulator
TAG=$1; BIN=$2
W=$S/gaps/$TAG; rm -rf "$W"; mkdir -p "$W"; cp -r "$S/nvram2" "$W/nvram"
cd "$E"
ABOUT="$W/ab" ABKEYS="L1,L2,L1p2" ABNOTES="C4:KEY2:1" T_BASE=22 SLOT=10 HOLD=1.6 \
 timeout 500 "$BIN" kn5000 -rompath ./roms -skip_gameinfo -window -nomaximize \
   -nvram_directory "$W/nvram" -cfg_directory "$W/cfg" -autoboot_delay 0 \
   -autoboot_script "$S/tvf/ab.lua" -seconds_to_run 54 -nothrottle -wavwrite "$W/ab.wav" \
   > "$W/run.log" 2>&1
echo "exit=$? tag=$TAG"

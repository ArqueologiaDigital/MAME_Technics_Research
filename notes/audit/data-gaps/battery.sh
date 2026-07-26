#!/usr/bin/env bash
# battery.sh <tag>   -> runs the reg.mid no-regression battery, writes $S/gaps/<tag>.wav
set -u
S=/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/c6cf97f4-b4f1-4ba1-adc0-85474706b167/scratchpad
E=/home/fsanches/compartilhado/kn7000-emulator
TAG=$1
W=$S/gaps/$TAG; rm -rf "$W"; mkdir -p "$W"; cp -r "$S/nvram2" "$W/nvram"
cd "$E"
timeout 400 ./kn7000 kn5000 -rompath ./roms -skip_gameinfo -window -nomaximize \
  -nvram_directory "$W/nvram" -cfg_directory "$W/cfg" \
  -midiin2 "$S/tvf/reg.mid" -seconds_to_run 46 -nothrottle \
  -wavwrite "$W/reg.wav" > "$W/run.log" 2>&1
echo "exit=$? tag=$TAG"; ls -la "$W/reg.wav"

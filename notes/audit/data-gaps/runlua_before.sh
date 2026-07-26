#!/usr/bin/env bash
set -u
S=/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/c6cf97f4-b4f1-4ba1-adc0-85474706b167/scratchpad
E=/home/fsanches/compartilhado/kn7000-emulator
TAG=$1; LUA=$2; SEC=${3:-46}
W=$S/gaps/$TAG; rm -rf "$W"; mkdir -p "$W"; cp -r "$S/nvram2" "$W/nvram"
cd "$E"
LIFEOUT="$W/life.log" timeout 500 "$S/tvf/kn7000_before" kn5000 -rompath ./roms -skip_gameinfo -window -nomaximize \
  -nvram_directory "$W/nvram" -cfg_directory "$W/cfg" -autoboot_script "$LUA" -autoboot_delay 0 \
  -seconds_to_run $SEC -nothrottle -wavwrite "$W/out.wav" > "$W/run.log" 2>&1
echo "exit=$? tag=$TAG"

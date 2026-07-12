#!/usr/bin/env bash
# Publish the freshly-built KN7000 MAME binary to a host-accessible, self-contained
# folder so it can be run OUTSIDE the VM.  /home/fsanches/compartilhado is a virtiofs
# mount shared_from_host, so files placed here are directly visible on the host.
#
# Run this after every rebuild of the driver:
#     bash tools/publish-binary.sh
#
# The published folder (kn7000-emulator/) is fully self-contained: binary + ROMs +
# launcher + README. Copy that folder anywhere on the host and run ./run.sh.
set -euo pipefail

BUILD=/home/fsanches/compartilhado/kn7000_mame_build
BIN="$BUILD/kn7000"
DEST=/home/fsanches/compartilhado/kn7000-emulator
# Models that reach a display and are worth shipping (each ships a roms/<model>/ subfolder).
MODELS="kn7000 kn6000 kn6500"

[ -x "$BIN" ] || { echo "error: binary not built at $BIN (build the driver first)"; exit 1; }

mkdir -p "$DEST/roms"

# 1) The binary -- the only thing that changes each build. Atomic replace so a running
#    instance on the host is never left half-copied.
cp -f "$BIN" "$DEST/.kn7000.tmp"
chmod +x "$DEST/.kn7000.tmp"
mv -f "$DEST/.kn7000.tmp" "$DEST/kn7000"

# 2) The ROMs, per model (even/odd flash images). Copy each shipped model's set.
for m in $MODELS; do
  [ -d "$BUILD/roms/$m" ] || { echo "warning: no ROMs for $m at $BUILD/roms/$m -- skipping"; continue; }
  mkdir -p "$DEST/roms/$m"
  cp -u "$BUILD/roms/$m"/*.rom "$DEST/roms/$m/"
done

# 3) Launcher: self-contained, resolves ROMs relative to this folder.
cat > "$DEST/run.sh" <<'SH'
#!/usr/bin/env bash
# Launch a Technics keyboard emulator. An optional first argument selects the model
# (kn7000 / kn6000 / kn6500; default kn7000); everything else passes through to MAME.
#   ./run.sh                  # KN7000, fullscreen
#   ./run.sh -window          # KN7000, windowed
#   ./run.sh kn6000 -window   # KN6000, windowed (boots to its play screen)
#   ./run.sh kn6500 -window   # KN6500, windowed
cd "$(dirname "$(readlink -f "$0")")"
MODEL=kn7000
if [ $# -gt 0 ] && [ "${1#-}" = "$1" ]; then MODEL="$1"; shift; fi
# -skip_gameinfo skips the game-info AND (via our ui.cpp patch) the red "known problems"
# warnings screen, so the emulator boots straight in without needing a click to dismiss it.
exec ./kn7000 "$MODEL" -rompath ./roms -skip_gameinfo "$@"
SH
chmod +x "$DEST/run.sh"

# 4) README with run instructions + host requirements + troubleshooting.
cat > "$DEST/README.md" <<'MD'
# Technics SX-KN7000 — MAME emulator (work in progress)

Self-contained build of the in-development KN7000 MAME driver. Copy this whole folder
anywhere on your machine and run it.

## Run
```
./run.sh                 # KN7000, fullscreen
./run.sh -window         # KN7000, windowed (recommended while developing)
./run.sh kn6000 -window  # KN6000, windowed (boots to its main play screen)
./run.sh kn6500 -window  # KN6500, windowed
```
The first argument may be a model name (`kn7000` / `kn6000` / `kn6500`); anything else is
passed straight through to MAME. Or run directly, e.g. `./kn7000 kn6000 -rompath ./roms -window`.
The front panel is clickable artwork. Cycle layout views with the **Tab** menu →
*Video Options*, or press the view-select keys. Quit with the MAME menu (Tab) or `Esc`.

## Host requirements (Linux x86-64)
This binary is **dynamically linked** against standard desktop libraries. It was built on
Debian 13 (trixie), so it needs:
- **glibc ≥ 2.38** and **libstdc++ from GCC ≥ 13** (Debian 13 / Ubuntu 24.04+ or newer).
- SDL2 + usual desktop libs. On Debian/Ubuntu, if it complains about a missing library:
  ```
  sudo apt install libsdl2-2.0-0 libsdl2-ttf-2.0-0 libfontconfig1 libpulse0 libasound2
  ```
  (X11/OpenGL/wayland libs come with any desktop environment.)

If you get `version 'GLIBC_2.38' not found` or a `libstdc++`/`GLIBCXX` error, your host is
older than the build machine — ask for a **self-contained bundled-libs build** and one can
be produced (binary + its own copies of the libraries + loader).

## What works so far
- **KN7000** boots to its home screen; the front panel (buttons + LEDs) is wired; MIDI-in works.
- **KN7000 can now make sound**, driven by the real firmware voice engine. It is an opt-in
  switch because turning it on also lets boot advance into the (still unfinished) SD subsystem,
  so the machine then rests on the SD menu instead of the home screen:
    - Open the **Tab menu → Machine Configuration** and set
      *"Tone generators / firmware sound (experimental)"* to **On**, then reset (Tab → Reset, or F3).
    - Play notes with the PC keyboard: **Z S X D C V G B H N J M** = C4…B4, **Q 2 W 3 E R…** = C5 up.
    - Pitch and polyphony are the firmware's own; the timbre is a placeholder sine (see below).
- **KN6000 / KN6500** boot to their main play screen (tone/sound-group icon row, menus, status bar).

The four PCM **wave ROMs are undumped**, so the sound uses a placeholder sine rather than the real
samples — the notes are in tune and firmware-timed, they just don't have the KN7000's actual voices
yet. A few built-in mask ROMs (icon graphics) are also still undumped, so some icons use
placeholders. See the project notes.

## ROMs
`roms/kn7000/` holds the two dumped flash images. MAME flags them "NEEDS REDUMP" (a hash
note) but they load and run fine.
MD

SZ=$(du -h "$DEST/kn7000" | cut -f1)
echo "published -> $DEST"
echo "  kn7000  ($SZ, $(date '+%Y-%m-%d %H:%M'))"
echo "  run on host:  cd $DEST && ./run.sh -window"

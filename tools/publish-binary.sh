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
ROMS="$BUILD/roms/kn7000"
DEST=/home/fsanches/compartilhado/kn7000-emulator

[ -x "$BIN" ] || { echo "error: binary not built at $BIN (build the driver first)"; exit 1; }

mkdir -p "$DEST/roms/kn7000"

# 1) The binary -- the only thing that changes each build. Atomic replace so a running
#    instance on the host is never left half-copied.
cp -f "$BIN" "$DEST/.kn7000.tmp"
chmod +x "$DEST/.kn7000.tmp"
mv -f "$DEST/.kn7000.tmp" "$DEST/kn7000"

# 2) The ROMs (static; copy only if missing or newer).
cp -u "$ROMS/kn7000_program.rom" "$DEST/roms/kn7000/"
cp -u "$ROMS/kn7000_table.rom"   "$DEST/roms/kn7000/"

# 3) Launcher: self-contained, resolves ROMs relative to this folder.
cat > "$DEST/run.sh" <<'SH'
#!/usr/bin/env bash
# Launch the KN7000 emulator. Extra args are passed through to MAME.
#   ./run.sh                 # fullscreen
#   ./run.sh -window         # windowed
#   ./run.sh -window -nomax  # windowed, not maximized
cd "$(dirname "$(readlink -f "$0")")"
exec ./kn7000 kn7000 -rompath ./roms "$@"
SH
chmod +x "$DEST/run.sh"

# 4) README with run instructions + host requirements + troubleshooting.
cat > "$DEST/README.md" <<'MD'
# Technics SX-KN7000 — MAME emulator (work in progress)

Self-contained build of the in-development KN7000 MAME driver. Copy this whole folder
anywhere on your machine and run it.

## Run
```
./run.sh              # fullscreen
./run.sh -window      # windowed (recommended while developing)
```
or directly:
```
./kn7000 kn7000 -rompath ./roms -window
```
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
Boots to the home screen; the front panel (buttons + LEDs) is wired; MIDI-in works.
Audio needs the (undumped) wave ROMs, so there is no sound yet. See the project notes.

## ROMs
`roms/kn7000/` holds the two dumped flash images. MAME flags them "NEEDS REDUMP" (a hash
note) but they load and run fine.
MD

SZ=$(du -h "$DEST/kn7000" | cut -f1)
echo "published -> $DEST"
echo "  kn7000  ($SZ, $(date '+%Y-%m-%d %H:%M'))"
echo "  run on host:  cd $DEST && ./run.sh -window"

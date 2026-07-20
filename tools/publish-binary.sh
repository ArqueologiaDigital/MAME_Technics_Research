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
# (kn2600 is a clone of kn2400 -- it resolves its ROMs from the kn2400 set, no own folder.)
MODELS="kn7000 kn6000 kn6500 kn2400"

# The AUTHORITATIVE home of every ROM artifact: a private, git-versioned repo. The build
# tree and this published folder are both DERIVED from it. See technics_roms/README.md.
ROMREPO="${TECHNICS_ROMS:-/home/fsanches/compartilhado/technics_roms}"

[ -x "$BIN" ] || { echo "error: binary not built at $BIN (build the driver first)"; exit 1; }

mkdir -p "$DEST/roms"

# 0) Top up the build tree from the authoritative repo. The build tree is disposable, so
#    anything missing there is restored from the repo before publishing -- that way the
#    published folder is always derived from the source of truth rather than from whatever
#    happens to have survived in the build tree.
if [ -d "$ROMREPO/roms" ]; then
  for m in $MODELS; do
    [ -d "$ROMREPO/roms/$m" ] || continue
    mkdir -p "$BUILD/roms/$m"
    for f in "$ROMREPO/roms/$m"/*.rom; do
      [ -e "$f" ] || continue
      [ -f "$BUILD/roms/$m/$(basename "$f")" ] || {
        cp -p "$f" "$BUILD/roms/$m/"
        echo "restored from technics_roms: $m/$(basename "$f")"
      }
    done
  done
else
  echo "warning: authoritative ROM repo not found at $ROMREPO -- publishing from the build tree alone"
fi

# 1) The binary -- the only thing that changes each build. Atomic replace so a running
#    instance on the host is never left half-copied.
cp -f "$BIN" "$DEST/.kn7000.tmp"
chmod +x "$DEST/.kn7000.tmp"
mv -f "$DEST/.kn7000.tmp" "$DEST/kn7000"

# 2) The ROMs, per model (even/odd flash images). Copy each shipped model's set.
#
#    IMPORTANT -- this copy is ONE WAY (build tree -> published folder) and never
#    deletes. The build tree is DISPOSABLE (build.sh says so: "regenerable and NOT
#    version-controlled"), so if a model's ROMs go missing there, this step used to
#    print a quiet mid-run warning and silently leave a STALE copy in the published
#    folder -- which then became the only surviving copy. That is exactly how the
#    kn6000/kn6500 sets ended up published-only. So: missing ROMs are now a HARD
#    ERROR, collected and reported prominently at the end.
#      Restore/regenerate them with:   tools/make-roms.sh restore   (or 'generate')
#      Provenance for every file:      notes/rom-provenance.md
#    Set PUBLISH_ALLOW_MISSING_ROMS=1 to downgrade the failure to a warning.
MISSING_MODELS=""
for m in $MODELS; do
  if [ ! -d "$BUILD/roms/$m" ] || ! ls "$BUILD/roms/$m"/*.rom >/dev/null 2>&1; then
    MISSING_MODELS="$MISSING_MODELS $m"
    continue
  fi
  mkdir -p "$DEST/roms/$m"
  cp -u "$BUILD/roms/$m"/*.rom "$DEST/roms/$m/"
done

# 2a) KN6000/KN6500 table/font ROM -- BAD_DUMP PLACEHOLDER.
#     Their own table/font mask ROMs (IC13/IC14: QSIGX3C16008/QSIGX3C16007 on the
#     KN6000, C3FBMD000069/68 on the KN6500) have NEVER been dumped, and without a
#     valid table ROM header those models render NO TEXT at all. The driver therefore
#     loads the KN7000's table ROM into their "table" region, flagged BAD_DUMP, so the
#     machines are usable. The glyphs shown are the KN7000's data, NOT the KN6xxx's own
#     -- see the comment above ROM_START(kn6000) in src/mame/matsushita/kn7000.cpp and
#     notes/kn6000-kn6500-boot.md. Dumping IC13/IC14 remains the real fix.
#     Since the ROM entries reference the kn7000_table_*.rom filenames, those files must
#     also be present in each model's set folder for MAME to resolve them.
for m in kn6000 kn6500; do
  [ -d "$DEST/roms/$m" ] || continue
  for f in kn7000_table_even.rom kn7000_table_odd.rom; do
    if [ -f "$DEST/roms/kn7000/$f" ]; then
      cp -u "$DEST/roms/kn7000/$f" "$DEST/roms/$m/$f"
    elif [ -f "$BUILD/roms/kn7000/$f" ]; then
      cp -u "$BUILD/roms/kn7000/$f" "$DEST/roms/$m/$f"
    else
      echo "warning: $f not found -- $m will render no text"
    fi
  done
  # Retire the old ${m}_table_*.rom files: they were never a dump of IC13/IC14, just
  # the program ROM's upper half loaded a second time, and are no longer referenced.
  rm -f "$DEST/roms/$m/${m}_table_even.rom" "$DEST/roms/$m/${m}_table_odd.rom"
done

# 2a-bis) KN5000 (SX-KN5000). Deliberately NOT in MODELS: its set is not the even/odd
#     "*.rom" pair the loop above assumes but a mixed bag of per-IC files (.ic1/.ic3/.ic14/
#     .ic19/.ic30 plus several *.rom), and its master copy lives outside the build tree in
#     ../kn5000_original_roms/kn5000. Ship the whole folder verbatim when it is available,
#     and stay silent (not a hard error) when it is not -- the KN5000 is a bonus model here,
#     the KN7000 family is what this folder is primarily for.
KN5000_SRC=""
for cand in "$BUILD/roms/kn5000" /home/fsanches/compartilhado/kn5000_original_roms/kn5000; do
  [ -d "$cand" ] && { KN5000_SRC="$cand"; break; }
done
if [ -n "$KN5000_SRC" ]; then
  mkdir -p "$DEST/roms/kn5000"
  cp -u "$KN5000_SRC"/* "$DEST/roms/kn5000/" 2>/dev/null || true
else
  echo "note: no KN5000 ROM set found -- kn5000 will not be runnable from the published folder"
fi

# 2b) MAME plugins. The "layout" plugin registers the cb_layout callback that EXECUTES a
#     layout's <script> block -- without it, layout scripts silently never run. The KN7000
#     volume faders are made draggable by such a script (tools/slider_lib.lua), so the
#     emulator MUST ship the plugins dir or the sliders can't be dragged. Bundle them all
#     (small, ~1 MB) so the folder stays self-contained; run.sh points -pluginspath here.
if [ -d "$BUILD/plugins" ]; then
  rm -rf "$DEST/plugins"
  cp -r "$BUILD/plugins" "$DEST/plugins"
else
  echo "warning: no plugins dir at $BUILD/plugins -- layout <script> (draggable sliders) will NOT work"
fi

# 3) Launcher: self-contained, resolves ROMs relative to this folder.
cat > "$DEST/run.sh" <<'SH'
#!/usr/bin/env bash
# Launch a Technics keyboard emulator. An optional first argument selects the model
# (kn7000 / kn6000 / kn6500 / kn2400 / kn2600 / kn5000; default kn7000); everything else passes
# through to MAME.
#   ./run.sh                  # KN7000, fullscreen
#   ./run.sh -window          # KN7000, windowed
#   ./run.sh kn6000 -window   # KN6000, windowed (boots to its play screen)
#   ./run.sh kn6500 -window   # KN6500, windowed
#   ./run.sh kn2400 -window   # KN2400, windowed (boots to its play screen)
#   ./run.sh kn2600 -window   # KN2600, windowed (same firmware as the KN2400)
#   ./run.sh kn5000 -window   # KN5000, windowed (boots to its main play screen)
cd "$(dirname "$(readlink -f "$0")")"
MODEL=kn7000
if [ $# -gt 0 ] && [ "${1#-}" = "$1" ]; then MODEL="$1"; shift; fi
# The KN7000 has an SD-card slot. Attach an SD image by default: without a card the
# firmware reports "ERROR 93: SD lid is open" REGARDLESS of the SD-slot-cover switch,
# because its card-detect line reads "no card" the same as "lid open" -- so the cover switch
# only has a visible effect when a card is actually present. (Only kn7000 has this slot.)
# In-emulator SD SAVE works, so we attach a WRITABLE WORKING COPY (sdcard_work.img,
# auto-created from the pristine real-card dump on first run) -- your saves persist there
# while sdcard_from_real_kn7000.img stays untouched. Delete sdcard_work.img to reset the
# card to the factory dump. Pass your own "-harddisk <img>" to use a different card, or
# "-harddisk \"\"" for an empty slot.
EXTRA=()
if [ "$MODEL" = kn7000 ]; then
	case " $* " in
		*" -harddisk "*) ;;   # caller already chose (or cleared) the SD image
		*)
			if [ ! -f sdcard_work.img ] && [ -f sdcard_from_real_kn7000.img ]; then
				cp sdcard_from_real_kn7000.img sdcard_work.img && chmod u+w sdcard_work.img
			fi
			if [ -f sdcard_work.img ]; then
				EXTRA=(-harddisk sdcard_work.img)
			elif [ -f sdcard_from_real_kn7000.img ]; then
				EXTRA=(-harddisk sdcard_from_real_kn7000.img)
			fi
			;;
	esac
fi
# -skip_gameinfo skips the game-info AND (via our ui.cpp patch) the red "known problems"
# warnings screen, so the emulator boots straight in without needing a click to dismiss it.
# -pluginspath ./plugins ensures MAME finds the bundled "layout" plugin, which runs the
# layout <script> that makes the volume faders draggable with the mouse.
exec ./kn7000 "$MODEL" -rompath ./roms -pluginspath ./plugins -skip_gameinfo "${EXTRA[@]}" "$@"
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
  The four **volume faders** (MAIN / APC-SEQ / MIC / LINE-IN) are draggable with the mouse — click
  and drag a knob, or click anywhere on its track. (This needs the bundled `plugins/` folder, which
  `run.sh` points at via `-pluginspath`; running the binary without it disables the drag script.)
- **KN7000 can now make sound**, driven by the real firmware voice engine. It is an opt-in
  switch because turning it on also lets boot advance into the (still unfinished) SD subsystem,
  so the machine then rests on the SD menu instead of the home screen:
    - Open the **Tab menu → Machine Configuration** and set
      *"Tone generators / firmware sound (experimental)"* to **On**, then reset (Tab → Reset, or F3).
    - Play notes with the PC keyboard: **Z S X D C V G B H N J M** = C4…B4, **Q 2 W 3 E R…** = C5 up.
    - Pitch and polyphony are the firmware's own; the timbre is a placeholder sine (see below).
- **The SD card works, including saving**: a real-card image is attached by default and the
  full SD UI runs — LOAD/SAVE browsers, SD TOOLS, play paths. A TECHNICS FORMAT panel save
  and load-back round-trip has been verified end-to-end (FAT writes reach the card image).
  Your saves persist in `sdcard_work.img` (auto-created working copy); delete that file to
  reset the card to the pristine dump.
- **KN6000 / KN6500** boot to their main play screen (tone/sound-group icon row, menus, status bar).
- **KN2400 / KN2600** boot to their main play screen too (320x240 4-level grayscale LCD;
  sound-group tiles + instrument icons). Text rendering on the KN6xxx/KN2xxx screens is still
  in progress.

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

# 5) Prominent missing-ROM summary. Deliberately LAST and LOUD: a shipped model whose
#    ROMs are absent from the build tree means the published folder now holds the ONLY
#    copy of those files, and this script would otherwise ship a stale set without
#    anyone noticing.
if [ -n "$MISSING_MODELS" ]; then
  echo
  echo "################################################################################"
  echo "## ERROR: MISSING ROMs IN THE BUILD TREE"
  echo "##"
  echo "## No .rom files found under $BUILD/roms/<model> for:"
  for m in $MISSING_MODELS; do
    echo "##     $m"
  done
  echo "##"
  echo "## These models were NOT refreshed. Whatever sits in $DEST/roms/"
  echo "## is STALE, and for any file missing from the build tree it is now the ONLY"
  echo "## surviving copy -- wiping the published folder would lose it permanently."
  echo "##"
  echo "## They are also absent from the authoritative repo at:"
  echo "##     $ROMREPO"
  echo "## which should normally have topped them up in step 0 -- check that repo first."
  echo "##"
  echo "## Fix:   tools/make-roms.sh restore     # repopulate from the technics_roms repo"
  echo "##        tools/make-roms.sh generate    # rebuild them from the preserved sources"
  echo "##        tools/make-roms.sh check       # verify the whole set against md5"
  echo "## Docs:  notes/rom-provenance.md  +  technics_roms/README.md"
  echo "################################################################################"
  if [ "${PUBLISH_ALLOW_MISSING_ROMS:-0}" = "1" ]; then
    echo "(PUBLISH_ALLOW_MISSING_ROMS=1 -- continuing anyway)"
  else
    exit 1
  fi
fi

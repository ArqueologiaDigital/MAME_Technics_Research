# Testing the rebuilt floppy software lists (2026-10-18 set)

The 40 rebuilt images are staged, not installed: the published emulator still uses the old
ones. Staging folder (private, not in git):

    S=$HOME/compartilhado/technics_romsets/floppy-rebuild-2026-10-18
    $S/roms/{kn5000_flop,kn6000_flop,kn7000_flop}/<entry>.zip   # the new images
    $S/hash/{kn5000_flop,kn6000_flop,kn7000_flop}.xml           # MAME's lists, new crc/sha1 only
    $S/summary.tsv                                               # old and new hashes per entry

Every command below runs from the published emulator folder and puts the staging folder
first in MAME's search paths. A later `-rompath`/`-hashpath` replaces the one `run.sh`
passes (all 41 entries, `idd5000` included since 2026-10-25, are in the staging folder):

    cd ~/compartilhado/kn7000-emulator
    NEW=(-rompath "$S/roms;./roms" -hashpath "$S/hash;hash")

Use throwaway settings, so loading Initial Data or panel memories does not overwrite your
saved instrument state:

    T=$(mktemp -d); KEEP=(-cfg_directory "$T" -nvram_directory "$T")

## 1. Hashes (seconds, no emulation)

    for l in kn5000_flop kn6000_flop kn7000_flop; do ./kn7000 "${NEW[@]}" -verifysoftlist $l; done

Pass: no entry is reported missing or with a wrong checksum (41 entries, `idd5000` included).

## 2. Each disk on its instrument

Start the instrument with the disk in the drive, by software-list name:

    ./run.sh kn6000 -window "${NEW[@]}" "${KEEP[@]}" -flop ca6001

| list        | machine                  | entries                                                                           |
|-------------|--------------------------|-----------------------------------------------------------------------------------|
| kn5000_flop | `kn5000`                 | ca5001-ca5010, ca5000r, ca5000w, mix5000                                          |
| kn6000_flop | `kn6000` (also `kn6500`) | idd6000, ca6000p, ca6000s, ca6001-ca6010, ca6dim, ca6fp01-04, ca6tm01-02, scd6000 |
| kn7000_flop | `kn7000`                 | idd7000, custom1, custom2, organs, scd7000, ca7001                                |

On each one:

1. **The disk is seen.** DISK MENU, then LOAD: the file list shows the disk's files (the counts
   per entry are in `$S/summary.tsv`, column "files"). Where the instrument shows the disk name
   (the KN6000's SMF DIRECT PLAY page does), it reads the entry name, e.g. `CA6001_____`.
2. **A file loads.** Load one file of each kind the disk has:

   | files on the disk                         | entries                                       | what to try                                         |
   |-------------------------------------------|-----------------------------------------------|-----------------------------------------------------|
   | `.SQT` songs with `.CMP` `.PMT` `.LSW` `.TM` | style disks (ca50xx, ca60xx, ca6000s, ca6dim, ca7001, mix5000, ca5000r) | load a song and play it; load a style or panel memory |
   | `.BMP` wallpapers                         | ca5000w, one each on ca5001-ca5010            | load one                                            |
   | `.HMP` panel memories                     | ca6000p                                       | load a bank and recall a memory                     |
   | `.TM` + `.EFC` sounds                     | ca6tm01, ca6tm02                              | load the sounds and play one                        |
   | `.AST` `.MD` `.FAV` `.HMP` Initial Data   | idd6000, idd7000                              | load it (with `KEEP` above, nothing is overwritten) |
   | `.AST` + `.LSW` Custom Data               | custom1, custom2                              | load a custom sound and play it                     |
   | `.CNV` converters                         | scd6000, scd7000                              | DISK MENU, STYLE CONVERT: the converter list appears |
   | `FEATURE.PRE` `.ACT` `.SQT` `.JPG`        | ca6fp01-ca6fp04                               | see below                                           |

3. **Feature presentations** (KN6000) load from the DEMONSTRATION screen when the disk goes in
   *after* DEMO is pressed. Either by hand: boot without `-flop`, press DEMO, then insert the
   disk from MAME's menu (Tab, File Manager, floppydisk, software list, `ca6fp02`). After
   "PLEASE WAIT" a button with the presentation's name appears at the bottom right and the
   slides start (with ca6fp01, about 45 s after inserting). Or scripted, with the image unzipped
   first:

       unzip -o -d "$T" "$S/roms/kn6000_flop/ca6fp02.zip"
       PRES_RUN=0 PRES_SNAP=0 PRES_IMG="$T/ca6fp02.img" ./run.sh kn6000 -window "${KEEP[@]}" \
           -autoboot_script ~/compartilhado/kn7000_mame/tools/slideshow/kn6000_pres_insert.lua

   Pass: the slides advance with the song.

Things that are the emulation, not the disks:

- **Run the overlay build.** The KN5000 needs it: mainline MAME cannot load any `.img` on the
  KN5000 yet.
- **Dropped first press.** Right after a disk goes in, the first panel press is often lost, on
  all three models. Press again.
- **KN5000 panel can go dead.** Its panel sometimes stops responding for the rest of the session
  (see `run.sh`). Restart MAME.
- **KN7000 message boxes.** They draw without their text.

## 3. If one fails

Check the same disk's old image (drop `NEW` from the command). If the old one works and the new
one does not, the layout is to blame. `verify_floppy.py` and `dissect_disk.py` show what is on
the new disk:

    unzip -o -d "$T" "$S/roms/kn6000_flop/ca6001.zip"
    python3 -I dissect_disk.py "$T/ca6001.img" --zip ~/compartilhado/ca-software-mirror/files/6000/files/ca6001.exe

## Rebuilding the set

    python3 -I build_all.py ~/compartilhado/technics_romsets/floppy-rebuild-2026-10-18

It reads `manifest.tsv` and builds each entry on its own instrument's disk from `base/`. Each
image must pass `verify_floppy.py` and carry the same files as the image it replaces, or the
build stops. It also writes `hash/*.xml` and `summary.tsv`. Two runs produced identical files
(all 43, 2026-10-18).

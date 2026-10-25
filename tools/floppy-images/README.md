# Floppy software-list images, built on the instrument's own formatted disk

## The rule

A software-list floppy for a Technics instrument is a dump of a real disk whenever one exists.
When none does and the image has to be built from an installer's files, it starts from a blank
disk **formatted by that instrument itself** (DISK > DISK TOOLS > FORMAT, run in MAME and saved
as a raw `.img`): `kn5000_flop` entries on the KN5000's formatted disk, `kn6000_flop` on the
KN6000's, `kn7000_flop` on the KN7000's, and so on for any other model. Its volume label is the
software-list entry's name, the way a user would type it on the instrument's DISK NAMING screen
(`ca6fp01` becomes `CA6FP01____`). The files are then added the way the installer adds them.

Why: the installers (`ca6fp01.exe`, `idd7000.exe`, ...) never write a disk layout. All 79 in
the CA software mirror are ZIP archives behind a self-extractor stub (WinZip Self-Extractor, a
16-bit Windows program, for 70; Mijenix ZipMagic, 32-bit, for 9; `unzip -t` checks every member's
CRC-32). Run on a PC they copy their members onto an already formatted HD disk ("Please insert a formatted HD-disk"). The
bytes of every file are therefore fixed by the archive, and the rest of the disk (boot sector,
FATs, label, unused sectors) by whatever formatted it. Running them under Wine would only write
the same files into a host folder; DOSBox would need a Windows install and would still take the
layout from the PC's FORMAT. The instrument's own format is the layout these disks were made to
be read on, so it is the base.

The first software-list builds (`research-scratch/kn7000-softlists/build_fat_floppy.py`, pyfatfs)
did not follow this: 12-sector FATs, FAT ID `F0 0F FF`, a pinned serial, zeroed timestamps. The
KN6000/KN7000 media probes reject that layout (`notes/kn6000-feature-presentation.md`).

## What the three formatters write (measured 2026-10-18)

The KN5000 (v10), KN6000 and KN7000 (941) formatters produce **byte-identical** blank disks:
SHA-1 `32d74744faf9d0648663fd29b13338a2267c7193` with the name left empty (`base/SHA1SUMS`).

| region         | sectors    | content                                                                                                                                                                                                                       |
|----------------|------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| boot sector    | 0          | 32 bytes `EB 1C 90 "Technics"` + DOS 3.x BPB (512 B/sector, 1 sector/cluster, 1 reserved, 2 FATs, 224 root entries, 2880 sectors, media F0, 9 sectors/FAT, 18/track, 2 heads, 0 hidden) + `EB FE`, then zeros; **no `55 AA`** |
| FAT 1, FAT 2   | 1-9, 10-18 | `F0 FF FF`, then zeros                                                                                                                                                                                                        |
| root directory | 19-32      | entry 0: volume label (attribute `0x28`, date/time/cluster/size 0); rest zeros                                                                                                                                                |
| data           | 33-2879    | `E5` in every byte (the FORMAT TRACK fill byte)                                                                                                                                                                               |

- The label is the typed name padded with `_` to 11 characters; an empty name is eleven `_`.
  Typing "KN" on the KN6000 changed exactly two bytes (`base/kn6000_formatted_named_KN.img.gz`).
  Pressing EXIT on DISK NAMING instead writes **no label at all**: the root stays zeros
  (`base/kn5000_formatted_unnamed.img.gz`, SHA-1 `15f888af...`, 12 bytes from the named one). The
  KN7000 disk ejected before its naming step is byte-identical to it.
- All three issue FORMAT TRACK with N=2 (512 bytes), 18 sectors, gap 0x6C, fill `E5` on all 80
  cylinders and both heads (`runs-2026-10-18/*_format.fdc.txt`). The KN5000 and KN7000 traces then
  match command for command: WRITE DATA to sectors 0-32 in order, two more writes to sector 19
  (the root's first sector, where the label goes), and reads of cylinder 79 sector 18, then of
  sectors 18, 1 and 19 of cylinder 0. The KN6000's untapped run gave the same disk.
- Each asks for the name after formatting: the KN5000 and KN6000 open DISK NAMING directly, the
  KN7000 first shows a message box that EXIT dismisses.
- The same 32-byte boot head is in each program ROM, next to a 720 KB twin (`find_bpb.py`; file
  offsets of the head): KN5000 v10 0x450DA (`FDC_Format2HD_BootSectorHead`, 0xE450DA), v5
  0x450BA; KN6000 0x385097; KN7000 941 0x3360DF.
- `fsck.fat -n` exits 1 on these disks, the untouched blank one included, for a single reason:
  there is no extended boot record, so it finds no boot-sector label to match the root's. It also
  prints 4,276,813,824 hidden sectors, because it reads `00 00 EB FE` at 0x1C as a 32-bit field. Both are
  how the instruments format, not defects of a build.

## Getting the formatters to run in MAME took six driver fixes

| model         | defect                                                                                                                                                    | evidence                                                               |
|---------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------|
| KN5000        | only MFM container formats registered: every `.img` (all 14 `kn5000_flop` entries) failed with "Unable to identify image file format"                     | `-flop ca5001.img` run, 2026-10-18                                     |
| KN5000        | FD.I/O (Port D bit 6) fed from MAME's step-cleared disk-change latch: a disk inserted at run time was never seen ("ERROR 02")                             | `kn5000.cpp` comment; firmware never steps while the line says no disk |
| KN5000        | drive on unit 0; the firmware sets US=1 in every command (`FDC_CMD_SEND`: `set 0, a`), so every command came back "not ready"                             | `kn5000_drive_on_unit0_not_ready.fdc.txt`                              |
| KN5000        | RDY taken from the drive; the firmware issues SEEK ~5 ms after motor-on (aux `0xFE`), so RDY must be tied active (inferred; net not traced)               | same trace, ST0 `0x69`/`0x49`                                          |
| KN5000        | aux "control internal mode" `0x4B`/`0x0B` (500/250 kbit/s) ignored: everything ran at 250 kbit/s, MAME saved a 720 KB image                               | `kn5000_rate_not_switched.fdc.txt`                                     |
| KN6000/KN7000 | the KN6000's DMA-end ISR does a dummy DACK read; during FORMAT it stole the last sector-ID byte, ST1 `0x10` overrun, sector 18 of every track unformatted | `kn6000_format_dack_overrun.fdc.txt`                                   |

All six are in `src/mame/matsushita/kn5000.cpp` / `kn7000.cpp` with the reasoning in comments.
The KN5000 ones also mean mainline MAME's `kn5000_flop` list cannot be loaded at all today.

## The single-disk trial: `ca6fp01` (KN6000 feature presentation)

Built from the KN6000's formatted disk with label `CA6FP01`; SHA-1
`e5f4f3d28ab9cb70621fc17f609f8f707bfeed03`, identical across two builds. `verify_floppy.py` passes
all 28 checks; `fsck.fat` reports only the label note above
(`runs-2026-10-18/ca6fp01_build_verify.txt`). Inserted on the KN6000's DEMONSTRATION screen in
the published overlay build it loads directly, with no relayout step: 1,589 DMA sector transfers,
then the Weserbergland slides from t=69 s onwards (`ca6fp01_kn6000_play.log`, `.jpg`).

## What official Technics disks look like

`runs-2026-10-18/official_update_disks_compared.md` compares six official KN5000 system-update
images (the archive.org item `technics-kn5000-system-update-disks`; v5-v8 untouched since
1997-98: v5/v6 as `.IMG` files shipped with `DOSIMAGE.EXE`, v7/v8 appended to
`KN5KPV7/8.EXE`, Matsushita's DOS "Self executable Image file to FD V0.1") with the formatter
output and a rebuilt disk (`compare_disks.py`, `dissect_disk.py`). All six:

- carry the instruments' boot head (Technics template, no `55 AA`): they were formatted on an
  instrument; on v5 and v6 Windows 95 later replaced the OEM name with its `?????IHC` marker;
- have **no volume label**, as an instrument formats a disk when its naming is skipped;
- hold their files contiguously from cluster 2 in directory order, upper-case 8.3 names,
  creation and access fields zero, write dates kept: the layout `technics_floppy.py` writes;
- leave whatever the writing PC had in the slack after end of file (`E5`, `00`, stray bytes),
  where our builds write zeros;
- have `E5` free space (v7-v10), or `F6` and leftovers (v5, v6: those master disks had been used).

v9 and v10, as uploaded, also show a dirty flag at byte 0x25, access dates 2023-02-26 and
creation dates 1980-01-01, which a read-write mount (most likely Linux) writes; v5-v8 have none
of these.

## The rebuilt software lists (2026-10-18)

`build_all.py` rebuilt all 40 entries that have an installer (`manifest.tsv`) on their own
instruments' disks, labelled with the entry names. *2026-10-25:* `idd5000`, which has no installer,
is rebuilt the same way from its six loose files (`kn5000_project/idd5000/Initial_Data_Disk`, dated
July 1997; manifest row `dir:`): 41 entries. Its listed image (crc `04e7983f`, built with pyfatfs,
FAT starting `F0 0F FF`) makes the KN5000 offer to FORMAT the disk; the rebuilt one (crc `3283e937`)
is listed as `IDD5000____`, and loading `01CTMINI.RCM` gives the factory panel (16 Beat 1, Piano,
Bigband Brass, Modern E.P.1). The other 40 rebuilt byte-identical to the 2026-10-18 set. Every image passes
`verify_floppy.py` and carries the same files as the image it replaces. Two runs gave identical
zips and lists. Staged, not installed, in
`~/compartilhado/technics_romsets/floppy-rebuild-2026-10-18/` (private); the new lists and
hashes are also in `rebuild-2026-10-18/`. How to test them: `TESTING.md`.

**`scd7000` before and after, on the KN7000 (2026-10-18).** The same command file, run in the
published overlay build with MAME's debugger, breaks on the converter call `0x48479929` after
DISK MENU > STYLE CONVERT > OK:

| image                                   | FAT starts | STYLE CONVERT                                   |
|-----------------------------------------|------------|-------------------------------------------------|
| upstream `scd7000` (crc `3e588db0`)     | `F0 0F FF` | an empty box; the converter is never called (0) |
| rebuilt `scd7000` (crc `13a03dd1`)      | `F0 FF FF` | a converter is loaded and called (3 calls)      |

The command file and runner are in kn5000-anotherworld `kn7000/probes/cnv/` (`taskprobe.cmd`,
`run_probe.sh`); the rebuilt run adds `-rompath "$S/roms;./roms" -hashpath "$S/hash;hash"`.

## Files

| file                 | question it answers                                                                                               | command                                                                               |
|----------------------|-------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------|
| `technics_floppy.py` | what disk does installer X leave on a disk instrument Y formatted?                                                | `python3 -I technics_floppy.py BASE.img INSTALLER.exe OUT.img --label NAME`           |
| `verify_floppy.py`   | is OUT exactly BASE plus the installer's files (names, attributes, dates, contents, layout), and nothing else?    | `python3 -I verify_floppy.py BASE.img INSTALLER.exe OUT.img NAME` (exit 0 = all pass) |
| `fat12_summary.py`   | what is in each region of a raw 1.44 MB image?                                                                    | `python3 -I fat12_summary.py IMAGE.img`                                               |
| `find_bpb.py`        | where does a ROM keep the boot sector its FORMAT writes?                                                          | `python3 -I find_bpb.py ROM` or `--pair EVEN ODD`                                     |
| `decode_fdc_log.py`  | what did the firmware send the FDC, and what came back? (from tap lines in a rig log)                             | `python3 -I decode_fdc_log.py RIG.log [--from MARKTEXT]`                              |
| `build_all.py`       | the whole rebuild: images, zips, MAME lists with new hashes, summary (stops on any failed check)                  | `python3 -I build_all.py OUT`                                                         |
| `manifest.tsv`       | which installer and which base disk each software-list entry is built from                                        |                                                                                       |
| `dissect_disk.py`    | everything a real disk records about how it was written (dates, chains, slack, fill)                              | `python3 -I dissect_disk.py IMAGE.img [--zip INSTALLER.exe]`                          |
| `compare_disks.py`   | the same traits for several disks, side by side                                                                   | `python3 -I compare_disks.py IMAGE.img ...`                                           |
| `TESTING.md`         | how to test the rebuilt set in the emulator                                                                       |                                                                                       |
| `step.sh`            | run a few `remote.lua` commands, wait for them, crop the newest snapshot (for walking menus by eye)               | `step.sh DIR "press PORT MASK;wait 3"`                                                |
| `base/*.img.gz`      | the blank disks the formatters wrote (`gzip -dc`); `SHA1SUMS` is of the uncompressed images                       |                                                                                       |
| `runs-2026-10-18/`   | the command files `remote.lua` ran for each format (`*_format.cmd`, with the rig's `.log`), FDC traces, the trial |                                                                                       |

### Re-making a base disk

`tools/rigs/remote.lua` drives the running instrument from a command file. For the KN6000:

    D=$HOME/compartilhado/tmp/fmt6k; mkdir -p $D/snap
    printf 'wait 30\ncreate %s/blank.img\nwait 6\n' $D > $D/cmd.txt
    REMOTE_CMD=$D/cmd.txt ./tools/rig.sh remote kn6000 -s 1200 -- -snapshot_directory $D/snap &
    step.sh $D "press CPR_SEG6 80;wait 4"     # DISK
    step.sh $D "press CPL_SEG3 08;wait 5"     # DISK TOOLS: an unformatted disk opens FLOPPY DISK FORMAT
    step.sh $D "press CPR_SEG3 10;wait 3"     # 1.44M Byte format : 2HD
    step.sh $D "press CPR_SEG3 10;wait 100"   # YES, then the format runs
    step.sh $D "press CPR_SEG3 20;wait 6"     # OK on DISK NAMING (letters: the MUTE buttons)
    step.sh $D "unload;exit"                  # ejecting writes blank.img

KN5000: floppy `REMOTE_FLOPPY=:fdc:1:35hd`, DISK `CPR_SEG10 20`, DISK TOOLS `CPL_SEG10 02`,
2HD and YES `CPL_SEG8 01`, OK `CPL_SEG7 02`. KN7000: DISK `CPR_SEG1 04`, DISK TOOLS
`CPL_SEG0 02`, 2HD and YES `CPR_SEG7 01`, then EXIT `CPC_SEG11 80` past a message box, OK
`CPR_SEG6 01`; attach a scratch SD copy (`-- -harddisk COPY`). Look at each snapshot before the
next press: right after a disk is inserted the first press is often dropped (all three models).

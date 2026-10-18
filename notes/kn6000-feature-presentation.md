# KN6000 feature-presentation floppies in MAME (2026-10-18)

Question: what stops a KN6000 "feature presentation" disk (CA-6FP01 *Weserbergland*, from the
`kn6000_flop` software list) from loading when it is inserted on the DEMONSTRATION screen, as the
instrument's users did ("press DEMO, then insert the disk")?

Answer: five things, one after the other. Four were emulation defects, fixed in the overlay
driver and MN10300 core. The fifth is the software-list images themselves. With all five
addressed, all four CA-6FP disks play their slide shows (2026-10-18).

| # | stage                                   | what was wrong                                                                                   | fixed by                                                         |
|---|-----------------------------------------|--------------------------------------------------------------------------------------------------|------------------------------------------------------------------|
| 1 | sector data never reached RAM           | DRQ raised an interrupt instead of driving the on-chip DMA channel                               | DMA channel 0 in the core (port of upstream #16394)              |
| 2 | the insertion was never noticed         | the drive's INDEX pulse (IRQ7, INTC group 0x1E) was not delivered                                | `fdd_index_poll` in `kn7000.cpp`                                 |
| 3 | the file system's memory pool corrupted | the DMA channel moved one byte too many per sector (upstream's count + 2)                        | count + 1, DMA-end interrupt on group 0x0F, FDC TC from GPIO     |
| 4 | the disk was rejected, then not found   | the list's images are not laid out like a DOS-formatted floppy (FAT ID bytes, 12-sector FATs)    | not fixed: the images need rebuilding (see below)                |
| 5 | the show stopped at its first slide     | the KN6000's tempo timer (MN10300 timer 6, INTC group 9) was not emulated: the song never ticked | timer 6 in the core (`tm6_*`)                                    |

## The insert path in the KN6000 firmware

Addresses are program-ROM addresses (`kn6000_prog.bin`, linear, base 0x48400000); the firmware runs
much of this code from the library alias 0x4C000000 + (address − 0x48400000).

1. **Disk monitor** `0x4851299D`, a three-state machine in byte `0x50004AB8` (0xFF unknown, 0 empty,
   1 disk in). It posts event `0x10708000` with 1 on 0 → 1 and with 0 on 1 → 0.
2. **Presence check** `0x485128A3`: reads the FDC's DIR (`0x9802000E`). DSKCHG clear → present.
   DSKCHG set → present only if an INDEX interrupt arrived within the last 0x6E ticks; the INDEX ISR
   `0x48512866` (group 0x1E, registered at `0x485127AD`) stamps the time into `0x50005B50`. A disk
   inserted while the instrument runs leaves DSKCHG set, so without INDEX pulses it is never seen.
   The KN7000 has the same code (`0x484025DD`, ISR `0x484025A1`, window 0x6E ticks of the 2 ms
   time base 0x50151BFC = 220 ms, just over one revolution at 300 rpm). Schematic (KN7000 service
   manual PDF page 100): net HDD.INDEX → CPU pin 48, IRQ7.
3. **DEMONSTRATION screen proc** `0x484B1D1E`, message `0x1800014` with event word `0x708000` and
   sub-code 1 → screen check `0x484AD0C9` (title `0x1F000CF`, three not-busy checks) → media check
   and mount `0x484AD107` (result ignored) → `"FEATURE .PRE"` lookup `0x4854CCC4` → post
   `0x018F0026` with `"FEATURE "`, which opens the presentation.
4. **Media type** `0x4854CDA4`: cached in byte `0x500605FD`, probed by `0x4853312E` while the cache
   holds 0xFF. The probe reads one sector and accepts the disk only if it starts with `F0 FF FF` or
   `F9 FF FF` (the FAT's media-descriptor entry); anything else returns 0 ("no usable disk", −7).
   The KN7000 has the identical probe at `0x48470CE3`.
5. **File system**: find-first `0x48533461` → path parse `0x485333DF` → directory open `0x4853008C`
   → scan `0x485302BD` → match `0x485335B5`. Buffers come from a small RTOS pool through
   `0x48512A37` (allocate) / `0x48512A5F` (free).

## Defect 3: one byte too many per sector

The KN6000 programs DMA channel 0 at `0x48510DEE` (read) / `0x48510EC8` (write) with
`count = length − 1`; its DMA-end ISR on group 0x0F (`0x48512476`, which calls `0x48510D63`)
asserts the FDC's TC by clearing GPIO `0x36008004` bit 4, reads one dummy byte from the DACK port
`0x98010000`, and releases TC. The KN7000 (941) programs `count = length − 2`; its group-0x0F ISR
(`0x4840219C`) waits for the FDC's DRQ on IRQ1 (group 0x18), moves the last byte by CPU and then
asserts TC (`0x4840210C`). Both are consistent with a channel that moves **count + 1** bytes and
then raises its end interrupt, and with no other model.

Upstream's channel (#16394) moves count + 2 and pulses TC itself: right for the KN7000 by
coincidence, one byte past every KN6000 buffer. Measured with `tools/slideshow/kn6000_pres_trace.lua`
(binary B, md5 below): a 0x21C-byte block freed at `0x501C95C0` could not be allocated again a few
instructions later, the next free received `0x6005004F` (directory bytes, not a pointer), and every
allocation after it failed, so `"FEATURE .PRE"` could not even be searched for. After the fix
(binary D) the same searches open their directory and scan it.

## Defect 4: the software-list images

Every image in `kn5000_flop`, `kn6000_flop`, `kn7000_flop` and `wsa1_flop` (34 checked, all merged
upstream) was built by `research-scratch/kn7000-softlists/build_fat_floppy.py` with pyfatfs and has:

| field                 | the list's images | a DOS/Windows-formatted 1.44 MB floppy |
|-----------------------|-------------------|----------------------------------------|
| OEM name              | `MSWIN4.1`        | e.g. `MSDOS5.0`                        |
| FAT start (entry 0/1) | `F0 0F FF`        | `F0 FF FF`                             |
| sectors per FAT       | 12                | 9                                      |
| root directory at     | sector 25         | sector 19                              |

- The FAT start fails the media probe on both instruments: KN7000 `ca7001` as listed → `−7`; the
  same image with only bytes 1-2 of each FAT set to `FF FF` → accepted (`tools/slideshow` run FL3/FL4).
- With the FAT start fixed but 12-sector FATs kept, the KN6000 mounts the disk but its directory
  scan finds nothing (it does not follow the BPB to the root directory). The same 22 files laid
  out by `tools/slideshow/make_fat12.py` (9-sector FATs) are found.

So the images need rebuilding in the standard layout, which changes every hash in the four lists.
The archives' payloads are unchanged; only the container differs.

## Result with all four addressed

| run | binary | disk                              | result                                                                 |
|-----|--------|-----------------------------------|------------------------------------------------------------------------|
| B1  | B      | `ca6fp01` as listed               | insert seen (state 0 → 1, INDEX stamps, 19 DMA reads), nothing else    |
| B5  | B      | as listed                         | media probe 0 → mount −7 → find −1                                     |
| B6  | B      | FAT start patched                 | probe 3 (HD), mount 0, find −1 (pool exhausted, defect 3)              |
| D1  | D      | FAT start patched                 | find opens the directory, scan finds nothing (12-sector FATs)          |
| D2  | D      | standard layout (`make_fat12.py`) | FEATURE.PRE found, `0x018F0026` posted                                 |
| D3  | D      | standard layout                   | WESERBERGLAND button; 1599 DMA reads to t=69; slide 1 from t≈74 to 264 |
| D4  | D      | standard layout                   | as D3; LCDR 5 at t=84, START/STOP at t=114 → back to the DEMO menu     |

All four disks, through the published folder's `run.sh` (runs E01-E04, logs in
`tools/slideshow/runs-2026-10-18/kn6000_E_*.log`): 01, 02 and 03 draw their first slide;
04 reads its files (1569 DMA transfers) and then stays on the DEMONSTRATION menu with its
LETS GET BACK button highlighted, the drive still turning. Not traced yet.

## Defect 5: the tempo timer

With defects 1-4 addressed the presentation loaded and drew its first slide, then held it: over
190 s the slides never advanced (runs D3, D4). The same symptom had been the KN7000's before its
on-chip tempo timer was modelled (kn7000_mame 60d5392, `notes/demo-and-sequencer-engine.md`): the
slide show follows the song, and the song advances only on the tempo interrupt.

The KN6000 does not use the KN7000's TM5 for tempo (it programs TM5 for its millisecond counter).
Its tempo routine (`0x484692C4` sets the constant 1,250,000 at `0x50033758`; `0x484692EB` divides it
by the BPM, clamped 40..300) writes **`0x340010C4`**, compare A of **MN10300 16-bit timer 6**. The
setup at `0x4846919E` programs its mode word `0x34001084` (low bits = 1, then a load pulse on bit 14
and count enable on bit 15) and `0x340010B4` (bits 7:6 = 01); the restart at `0x48469345` is
stop / load / start. Its tick ISR `0x48468A69` (registered at `0x48469289` on INTC group 9, GxICR
`0x34000124`) is the KN7000's `0x48447084` in other registers: a 96-PPQN phase counter at
`0x50276E0C` (mod 0x60), a stop flag at `0x50276DFE`, and the same five clock lanes. 1,250,000 / BPM
at 96 PPQN is a 2 MHz count, IOCLK / 8, the KN7000 TM5's clock too. The overlay core had no timer 6
at all, so the writes went nowhere and the ISR never ran.

Modelled in `mn10300.cpp` (`tm6_*`): compare A is the period at IOCLK / 8, bit 15 counts, bit 14
reloads, group 9 on every match. The firmware never reads these registers back or reads the count,
and the KN7000 firmware does not touch them.

Result (binary F, md5 `f88039d7908c07715d38044e1c1cd927`, runs F01-F04, 200 s after the insert):

| disk                       | what plays                                                                                                       |
|----------------------------|------------------------------------------------------------------------------------------------------------------|
| 01 *Weserbergland*         | the river towns one by one (Hann. Münden … Holzminden), then the lyric slides over the river, at the song's pace |
| 02 *Sexy Girls*            | the title, then a new picture every 5-10 s                                                                       |
| 03 *Freisprecheinrichtung* | the title and the story slides to "Euer Christian", then back to the DEMONSTRATION menu (the show ends)          |
| 04 *Let's Get Back to Bed* | the title and its pictures (before the timer it did not get past the menu)                                       |

So the KN6000 `I KD` songs do carry the slide cues; how they are encoded was not needed and was
not decoded (they are not the KN7000's `0x8A` picture events, `tools/slideshow/kn6000_sqt_pic_scan.py`).

Binaries: B (md5 `8c85ba51ae8027841251966f61aa9532`) is the resync build with DMA + INDEX
(count + 2); D (md5 `d398d07ca975241dc4c969270dca1a4a`) adds count + 1, the group-0x0F end
interrupt and the GPIO TC.

## Reproduce

    # standard-layout copy of the listed image (md5 a06b15c5a36d18a3df8bce56310a93ca):
    python3 -I tools/slideshow/fat12_relayout.py ca6fp01.img ca6fp01_std.img
    PRES_RUN=240 PRES_IMG=$PWD/ca6fp01_std.img kn7000 kn6000 -rompath ROMS -window -nothrottle \
        -snapshot_directory OUT -autoboot_script tools/slideshow/kn6000_pres_insert.lua
    # the stage-by-stage trace (needs -debug -debugger none):
    PRES_IMG=... kn7000 kn6000 ... -debug -debugger none -autoboot_script tools/slideshow/kn6000_pres_trace.lua

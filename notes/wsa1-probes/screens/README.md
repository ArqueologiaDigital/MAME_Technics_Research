# SX-WSA1R boot screens — the "does it still boot?" control

Two frames from one run of the build committed alongside them, captured by
`wsa1_panel_link.lua` (which snapshots every 15 emulated seconds):

```
cd ~/compartilhado/kn7000_mame_build
DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms -skip_gameinfo -str 200 -window \
    -autoboot_script ~/compartilhado/kn7000_mame/notes/wsa1-probes/wsa1_panel_link.lua
```

| file | when | what it shows |
|---|---|---|
| `wsa1r_t60_blank.png`                  | t = 60 s  | still blank — the panel is being drawn |
| `wsa1r_t195_all_initial_setting.png`   | t = 195 s | `ALL INITIAL SETTING!`, unchanged since t = 75 s |

The run takes 14 shots at t = 15, 30 … 195 s. The first four are blank (857 byte
PNGs) and the last ten are the message (1,214 byte PNGs), so the message appears
between t = 60 and t = 75 and then stops changing — a live system sitting on a
message, not a hang. That is the control the control-panel work had to pass:
wiring `wsa1_cpanel` must not cost the machine its boot.

⚠ The colours are a DRIVER CHOICE, not a measurement — see `palette_init()` in
`wsa1.cpp`. Only the glyphs are evidence.

---

## Third frame, added 2026-08-25 with the floppy controller

`wsa1_t195_all_initial_setting.png` is the same t = 195 s frame from the
**SX-WSA1 (keyboard)** driver, captured by `wsa1_fdc_probe.lua` on the build
that instantiates the `upd765a_device`:

```
cd ~/compartilhado/kn7000_mame_build
DISPLAY=:0 ./kn7000 wsa1 -rompath ./roms -skip_gameinfo -str 200 -window \
    -autoboot_script ~/compartilhado/kn7000_mame/notes/wsa1-probes/wsa1_fdc_probe.lua
```

It exists as the control for the FDC work: adding a floppy controller, a drive,
two interrupt lines and a TC output must not cost either variant its boot, and
both still reach the message on the same schedule (blank through t = 60 s, the
message from t = 75 s, unchanged to t = 195 s).  `wsa1r` was re-captured in the
same session and is byte-for-byte the frame already committed here.

---

## ★ The SOUND MODE frames, added 2026-08-25 with control register 0x3C

`ALL INITIAL SETTING!` above is no longer where either machine stops. Implementing
INTNEST -- the TLCS-900 interrupt nesting counter, cr 0x3C, which prom_a's kernel
is built on -- lets the scheduler run, the draw task dequeue, and both variants
draw their real UI. See the "cr 0x3C is NOW IMPLEMENTED" section of `../README.md`
for the before/after table and the evidence.

| file | machine | what it shows |
|---|---|---|
| `wsa1r_intnest_before_all_initial_setting.png` | wsa1r | the NULL: no register, the kernel never entered |
| `wsa1r_intnest_after_sound_mode.png`           | wsa1r | the hypothesis test (`wsa1_intnest_experiment.patch`, now superseded) |
| `wsa1r_intnest_implemented_sound_mode.png`     | wsa1r | the SHIPPED implementation -- **byte-identical** to the line above, md5 `491b27987a25e894eb44e322d72b465a` |
| `wsa1_intnest_sound_mode.png`                  | wsa1  | the keyboard variant, which draws **two** parameter panes where the wsa1r draws one |

Captured with the committed rigs, not by hand:

```
cd ~/compartilhado/kn7000_mame_build
# wsa1r, with the kernel-state numbers printed alongside the shots
DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms -skip_gameinfo -str 45 -window \
    -snapshot_directory <dir> \
    -autoboot_script ~/compartilhado/kn7000_mame/notes/wsa1-probes/wsa1_kernel_state.lua
# wsa1, one frame at t = 30 s
DISPLAY=:0 SNAP_AT=30 ./kn7000 wsa1 -rompath ./roms -skip_gameinfo -window \
    -seconds_to_run 40 -snapshot_directory <dir> \
    -autoboot_script ~/compartilhado/kn7000_mame/tools/rigs/snap_at.lua
```

⚠ Pass `-snapshot_directory`. MAME's default `snap/<machine>/` is shared and two
concurrent runs interleave their auto-numbered files -- which happened while these
were being taken, and is why the rig documents the flag.

---

## The timer-fix regression frames, 2026-08-25

Three machines, one snapshot each at t = 45 s, from the build carrying OVERLAY
FIX 1-4 in `src/devices/cpu/tlcs900/tmp95c061.cpp` plus the shared-core INTNEST
register.  Captured with a two-line autoboot script that calls
`manager.machine.video:snapshot()` once:

```
cd ~/compartilhado/kn7000_mame_build
for m in wsa1r kn5000 kn7000; do
    DISPLAY=:0 ./kn7000 $m -rompath ./roms -skip_gameinfo -str 47 -window \
        -snapshot_directory /tmp/snaps -autoboot_script /tmp/snap.lua
done
```

| file | machine | CPU | what it shows |
|---|---|---|---|
| `wsa1r_timerfix_t45_sound_mode.png`      | SX-WSA1R | TMP95C061 x2 | `SOUND MODE` with its parameter row (OCT/LVL/PAN/EFF1/EFF2/REV/INT/MIDI), reached without any input |
| `kn5000_timerfix_t45_play_screen.png`    | SX-KN5000 | TMP94C241 | the normal play screen, `PMEM: 1-`, `16 Beat 1`, `♩=120`, eight part sliders |
| `kn7000_timerfix_t45_play_screen.png`    | SX-KN7000 | MN10300 | the normal play screen with the `KN7000` splash still dissolving over it |

⚠ WHY THE LAST TWO ARE HERE.  They are the ones that could have been BROKEN.
`tlcs900.{h,cpp}`, `900tbl.hxx` and the TMP95C061 are shared, and the KN5000
runs the sibling TMP94C241 off the same shared core, so it is the machine that
had to be checked, not the machine the work was for.  The KN7000 is an MN10300
and shares nothing with any of it — it is in the set because the brief asked
for every Technics system, and a change that somehow reached it would be a very
loud alarm.  `tools/gate.sh` passed 17/0/1 on the same binary with every
liveness hash equal to its recorded baseline.

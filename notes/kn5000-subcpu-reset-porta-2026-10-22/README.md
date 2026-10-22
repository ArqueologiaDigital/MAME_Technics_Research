# KN5000: STYLE CONVERT held the sub CPU in reset (2026-10-22)

Found while adding keybed controls to Another World as a style converter (technics-anotherworld
`kn5000cnv/`): once DISK MENU > STYLE CONVERT was open, keys played nothing and sent nothing to the main CPU.

**Symptom.** From the moment STYLE CONVERT opens, the sub CPU's audio tick counter (sub RAM `0x1040`) stops
and its PC stays at `0x034FDF`: the keybed, the tone generators and everything else on the sub CPU stop.

**Cause.** Port A of the TMP94C241 has a data register and a function register, but no control register;
its pins are outputs. On the KN5000 bit 0 drives the sub CPU's `/RESET`. In v10 the STYLE CONVERT screen
toggles bit 3 with `set 3,(PA)` at `0xF97C22` and `res 3,(PA)` at `0xF97C4B`, both read-modify-write. MAME's
`port_r` returns the latch only for bits whose control bit is 1, and `m_port_control[PORT_A]` was 0, never
written since no `PACR` exists. So the read returned the external pins, 0. The write-back then cleared
bit 0 and held the sub CPU in reset.

**Fix** (`tmp94c241.cpp`, `device_reset`): ports A and B (no `PxCR` either) read back their output latch.

## The measurements

| question                                  | probe                                                 | result                                                                                                      |
|-------------------------------------------|-------------------------------------------------------|-------------------------------------------------------------------------------------------------------------|
| does the sub CPU stop?                    | `subtick.lua`                                         | before: the tick counts 252 per 0.5 s until 28.1 s, then stays at 11846, PC `0x034FDF`; after: it counts on |
| what does the firmware write to port A?   | `porta.lua`                                           | before: `08` from `0xF97C25` and `00` from `0xF97C4E` (bit 0 low); after: `FF`                              |
| does the keybed reach the main CPU after? | technics-anotherworld `kn5000cnv/probes/notering.lua` | note and velocity pairs (`30 64`, `30 00`, ...) in the ring at `0x202CB`                                    |

Both runs: `-bios v10`, the AW floppy, `SEQ="25:DISK;28:L3;33:R4"` (STYLE CONVERT opens at 28 s).

## Reproducing

```sh
H=~/compartilhado/technics-anotherworld/kn5000cnv/probes; N=~/compartilhado/kn7000_mame/notes/kn5000-subcpu-reset-porta-2026-10-22
R=~/compartilhado/tmp/kn5000-porta; mkdir -p $R/nv $R/cfg; cp $H/../build/aw5000.img $R/disk.img
cd ~/compartilhado/kn7000-emulator && PA_ADDR=28 PA_FROM=27 ST_FROM=26 PROBES="$H/seq.lua $N/porta.lua $N/subtick.lua" \
    SEQ="25:DISK;28:L3;31:quit" DISPLAY=:0 ./kn7000 kn5000 -rompath ./roms -pluginspath ./plugins -skip_gameinfo \
    -window -nothrottle -sound none -flop $R/disk.img -nvram_directory $R/nv -cfg_directory $R/cfg \
    -autoboot_script $H/multi.lua 2>&1 | grep -E "PORTA|SUBTICK"
```

Any floppy holding a `.CNV` file opens the screen as well.

| file          | question it answers                                                                         |
|---------------|---------------------------------------------------------------------------------------------|
| `porta.lua`   | each main-CPU write to port A (`PA_ADDR`, `0x28`) from `PA_FROM`: value and PC              |
| `subtick.lua` | the sub CPU's audio tick counter and PC every 0.5 s from `ST_FROM`: is the sub CPU running? |

## After the fix

Binary md5 `44828eab2e95a2d3b6b3bd33baacf074`.

| check                                          | result                                                                                              |
|------------------------------------------------|-----------------------------------------------------------------------------------------------------|
| `tools/gate.sh` (all models)                   | 17 passed, 1 skipped (kn1500 liveness); oracles unchanged: kn7000 `d5205327`, kn5000 `3f29427f`     |
| leave AW.CNV (EXIT held, NO), v10, main screen | the parts' names (Piano, Bigband Brass, Modern E.P.1); the previous binary shows "Sound Name Error" |

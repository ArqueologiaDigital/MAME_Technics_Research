# KN5000 v7 and v9: panel buttons did the wrong thing (2026-10-22)

Found while running Another World as a style converter (technics-anotherworld `kn5000cnv/`), whose test
runs open DISK MENU > STYLE CONVERT on each firmware version.

**Symptom.** With `-bios v7` or `-bios v9`, DISK did nothing, LEFT 3 on the main screen opened ENTERTAINER,
and EXIT changed the transposition. v5, v6, v8 and v10 were fine (v6 showed "ERROR in CPU data transmission"
at boot instead).

**Cause.** A race in `kn5000_cpanel_device`. When a command's second byte arrives, the panel queues its
answer and arms the idle timer for 50 us; INTA is asserted when it expires. The firmware still sends a
phantom byte after the command, and on v7 and v9 its first clock edge comes more than 50 us later. The panel
then asserted INTA while the firmware was still transmitting; the firmware's INTA handler switched SC1 to
receive mid-byte, and from then on the receive ring held one byte more than the parser had consumed. Every
later two-byte packet was decoded as the last byte of one packet and the first of the next.

**Fix** (`kn5000_cpanel.cpp`): after a command the panel answers no sooner than 150 us later; the phantom
byte's edges, 75-100 us after the command, then slide the 50 us window as before, so the answer still comes
right after the firmware's last byte. The button scan also no longer pushes a packet between the two bytes
of a command.

## The measurements

| question                                                                                      | probe                 | result                                                                                                                                                                                   |
|-----------------------------------------------------------------------------------------------|-----------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| does v7 get different bytes for a press?                                                      | `sc1rx.lua`           | no: EXIT gives `C7 08`, then `C7 00`, under v7 and v10 alike                                                                                                                             |
| does v7 map the packet to another action?                                                     | `cmp_tables.py`       | no: the event-index table (v7..v10 at `0xEDA03C`) and the 32 action lists match byte for byte apart from handler addresses; v9's match v10's exactly                                     |
| does v9 post the DISK event?                                                                  | `evq.lua`, `recq.lua` | v10 posts `A9 20` and record `AA 15 20 20` at 25.05 s; v9 posts nothing and queues no record                                                                                             |
| is the receive ring in step?                                                                  | `ringptr.lua`         | v9: write index 15, read index 14, and stays one apart; v10: equal                                                                                                                       |
| where do v9 and v10 part?                                                                     | `sc1all.lua`          | identical SC1 traffic for 124 accesses; at 7.79 s the left-panel bulk request `2B 00`: v10 receives `C0 00 C2 00 ...` at once, v9 nothing until its next command, then `40 18 18 80 ...` |
| when is INTA serviced?                                                                        | `inta.lua`            | v10: 561 us after the firmware's last byte of the command; v9: 8 us after it, while that byte is still shifting                                                                          |
| what the panel model saw (a build with `VERBOSE (LOG_COMMANDS \| LOG_SERIAL)`, not committed) |                       | v9: "Command: 2B 00", queue 22 bytes, `tx_start` of the phantom byte, then "SCLK idle, asserting INTA" before its edges; v10: the phantom byte's eight edges first                       |
| how far apart are the firmware's bytes?                                                       | `gaps.py`             | TX writes less than 1 ms apart, over a boot: up to 520-530 us (v9, v10), most at 75-100 us and 250-275 us                                                                                |

## After the fix

Binary md5 `73d8d102e49e3d94ac64816f99df2b69` (published 2026-10-22).

| check                                                         | result                                                                                                  |
|---------------------------------------------------------------|---------------------------------------------------------------------------------------------------------|
| DISK, then LEFT 3, at 25 s / 28 s, `-bios` v5 v6 v7 v8 v9 v10 | all six reach STYLE CONVERT ("Please Insert the Style Convert Disk!")                                   |
| receive ring at 24 s (v8, v9, v10)                            | write index = read index (40/40, 60/60, 42/42)                                                          |
| v6 at 38 s                                                    | the main screen; the previous binary (`7f1205b7`) shows "ERROR in CPU data transmission"                |
| `tools/gate.sh --model kn5000`                                | 5 passed: `-validate`, `-listxml`, verifyroms, liveness (distinct 20), demo oracle `8bbe54f7` unchanged |

## Reproducing

The probes run with technics-anotherworld's `kn5000cnv/probes/seq.lua` (timed panel presses) and
`multi.lua` (several scripts in one session):

```sh
P=~/compartilhado/technics-anotherworld/kn5000cnv/probes; N=~/compartilhado/kn7000_mame/notes/kn5000-panel-race-2026-10-22
E=~/compartilhado/kn7000-emulator; R=~/compartilhado/tmp/kn5000-panel; mkdir -p $R/nv $R/cfg
cd $E && PROBES="$P/seq.lua $N/ringptr.lua" RP_FROM=24 RP_TO=27 SEQ="25:DISK;27.2:quit" DISPLAY=:0 ./kn7000 kn5000 -bios v9 \
    -rompath ./roms -pluginspath ./plugins -skip_gameinfo -window -nothrottle -sound none \
    -nvram_directory $R/nv -cfg_directory $R/cfg -autoboot_script $P/multi.lua 2>&1 | grep RINGPTR
PROBES="$N/inta.lua" IN_FROM=7.785 IN_TO=7.80 ...      # same command line, -seconds_to_run 9
python3 -I $N/cmp_tables.py $E/roms/kn5000
```

| file            | question it answers                                                                              |
|-----------------|--------------------------------------------------------------------------------------------------|
| `sc1rx.lua`     | the bytes the CPU reads from SC1BUF (`0xD4`) from `RX_FROM` on                                   |
| `sc1all.lua`    | every SC1BUF write and read up to `ALL_TO`, to diff two versions' boots                          |
| `inta.lua`      | each SC1 byte with the CPU's interrupt mask and INTEAB, and each INTA service (`0x8D98` cleared) |
| `ringptr.lua`   | the receive ring's write (`0x8D9F`) and read (`0x8D9D`) indices (v8..v10)                        |
| `evq.lua`       | the panel events PanelEvent_Post writes at `0xC039` (v9, v10)                                    |
| `recq.lua`      | the panel records queued at `0x8E94` (v8..v10)                                                   |
| `cmp_tables.py` | the event-index table and the action lists of each version, compared with v10's                  |
| `gaps.py`       | the gaps between the firmware's SC1 writes in `sc1all.lua` output                                |

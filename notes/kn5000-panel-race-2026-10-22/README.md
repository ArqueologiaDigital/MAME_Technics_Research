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

**Fix 1** (`kn5000_cpanel.cpp`, commit `802d189`): after a command the panel answers no sooner than 150 us
later; the phantom byte's edges, 75-100 us after the command, then slide the 50 us window as before, so the
answer still comes right after the firmware's last byte. The button scan also no longer pushes a packet
between the two bytes of a command.

**A second fault, under v7 with a floppy in the drive.** DISK still failed there. The panel sends a long
answer (11 segments for `2B 00`) as one two-byte packet per INTA. It pulsed INTA for the next packet 20 us
after the previous one, while the firmware was still in its INTRX1 handler, which ends by clearing the INTA
request (`INTCLR 0x12`): that pulse was lost and its packet clocked out to a CPU not listening. So every other
packet was lost, on every version (the CPU received `C0, C2 ... CA` of `C0 ... CA`). With floppy interrupts
delaying the INTA service as well, a packet once arrived before the previous packet's second byte was read
(`C4 C5` for `C4 00`), and the ring went one byte off as before.

**Fix 2**: 150 us between packets, and 300 us from INTA to the first clock edge (was 20 us each).

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

## After fix 1

Binary md5 `73d8d102e49e3d94ac64816f99df2b69`.

| check                                                         | result                                                                                                  |
|---------------------------------------------------------------|---------------------------------------------------------------------------------------------------------|
| DISK, then LEFT 3, at 25 s / 28 s, `-bios` v5 v6 v7 v8 v9 v10 | all six reach STYLE CONVERT ("Please Insert the Style Convert Disk!")                                   |
| receive ring at 24 s (v8, v9, v10)                            | write index = read index (40/40, 60/60, 42/42)                                                          |
| v6 at 38 s                                                    | the main screen; the previous binary (`7f1205b7`) shows "ERROR in CPU data transmission"                |
| `tools/gate.sh --model kn5000`                                | 5 passed: `-validate`, `-listxml`, verifyroms, liveness (distinct 20), demo oracle `8bbe54f7` unchanged |

## After fix 2

Binary md5 `3e9ee312330a64cbec3a0c458caec32c` (published 2026-10-22).

| check                                                                        | result                                                                                            |
|------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------|
| bytes received at boot for `2B 00` and `EB 00` (v7, with and without floppy) | all 22 packets, `C0 00 C1 00 ... CA 00 00 00 01 00 ... 0A 00`; ring 48/48 at 9 s in both          |
| DISK, then LEFT 3, with the floppy in, v5 v6 v7 v8 v9 v10                    | all six reach STYLE TYPE SELECT listing the floppy's `.CNV`                                       |
| `tools/gate.sh --model kn5000`                                               | 5 passed after re-baselining the demo oracle to `3f29427f` (rms 501.8; was `8bbe54f7`, rms 500.1) |

**The demo oracle re-baseline.** The demo capture changed because the boot's panel answers now arrive whole
and take longer. `wavshift.py` finds the new capture starting 5.6 ms earlier and not equal to the old one at
any one shift; `tgseq.lua` records every sub-CPU write to the tone generator during the demo, and `tggates.py`
compares the note-on gates: 2720 in the old run, 2721 in the new, first different at gate 44 only in the voice
slot (40 against 32, same data `0x8100`), and with the slot left out the same sequence plus one note at the
end, which fits before the 90 s cut since the demo starts earlier. The same notes in the same order, on other
voices.

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

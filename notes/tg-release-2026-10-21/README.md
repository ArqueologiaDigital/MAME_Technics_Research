# Notes that did not stop: the tone generator's status reads (2026-10-21)

Felipe's report (`notes/listen-2026-10-21/`, "How the file got its order"): notes received on MIDI IN 1 rang on after
their note-offs for piano (GM 0), strings (GM 48) and pad (GM 89); the church organ (GM 19) fell 9 dB and held; All
Notes Off (CC 123) and All Sound Off (CC 120) stopped nothing; only the square lead (GM 80) ended. Another World's
notes hung the same way. On the instrument notes end normally.

## The cause

It was not MIDI. The firmware's voice allocator asks the tone generators which voices still sound, and the emulator
answered "none".

`TgVoiceStatusSweep` (library `0x4C03AA86` in v16) visits one group of 16 slots per pass, about every 0.1 s per group.
For each chip it writes the address `0xFC08 + g`, a 0, then reads the data port. It ORs the answer with its own mask of
held keys (`0x500D288C`), and a slot whose bit falls from 1 to 0 has ended: its node is retired. For slots that are
still sounding and not held it reads `0xFC02 | slot<<4` and keeps `(x & 0x1FFF) >> 5` as the voice's level (node
`+0x2A`). A level below `0x80` marks the voice as the first to steal (`TgVoiceNodeFadeKick`, `NodeKeyOff`). The driver
returned 0 for every read of `0x98040002`/`0x98050002`, so on the sweep's first visit after a note-on, 43-82 ms
later, each fresh voice read as level 0 and its node was keyed off and dropped. At the note-off, `TgPartKeyEvent`
asked `TgPartHoldQuery` and found no voice left to release, so it wrote nothing to the tone generator.

What the old model made of that (`kn7000_tonegen.cpp` before this change):

- **One-voice notes** (the GM piano, strings and pad on channels 4-6): no TG write at all at the note-off or at
  CC 123/120 (`probe.lua`'s write log: not one write between the note-off and the next section's note-on). The voice held at its
  sustain level for good. The piano was later "released" by an unrelated note: the old pair rule released voice v2
  when the pad keyed v3.
- **Two-voice notes** (the keybed and channel 1 piano, the organ): the sweep dropped one of the two voices, and the
  key-off burst reached only the other. The old rule released the even/odd pair `{v & ~1, v | 1}` of the voice that got
  the burst. The square lead's two voices sat in one pair on one chip (v68, v69), so it ended. The organ's sat on two
  chips (v67, v4): only v4 ended, so the level fell 9 dB. The keybed piano's second voice (v64) decayed on its own, so
  nobody noticed.

The trace (`keyoff_trace.dbg` on v16, the build whose addresses `program.s`'s equates use): before the change, every
note-on is followed 43-82 ms later by the sweep's `NodeKeyOff(slot, 0x0F)` on one of its slots: 657,984 instructions
(71 ms at the run's 9.27 M instructions per emulated second) after the keybed note-on, 82 ms for channel 1, 76 ms for
the channel 4 piano. At the note-off,
`NodeKeyOff`, `TgVoiceSlotService` and `TgVoiceEgBurstWrite` run for one slot, or for none. After the change: no early
`NodeKeyOff`; at every note-off the three run for **every** slot of the note; and the sweep retires each slot once its
release has ended, 0.19-1.45 s after the note-off.

The earlier notes' "the key-up burst goes to the note's odd companion block even when only the even block sounds"
(`tg-envelope-implementation-plan.md`, 2026-07-11) and "plucked/brass/sax/organ get no key-up write" are what the
firmware did with its voices already dropped. They are corrected in those files.

## The change (`kn7000_tonegen.cpp`, `kn_tonegen.h`, `kn7000.cpp`)

1. **The status reads.** `io_r` passes reads of `0x98040002`/`0x98050002` to `tg_read(tg, latched address)`:
   - `0xFC08 + g`: bit i set if the chip's voice `16g + i` sounds (in attack, or its envelope above zero);
   - `0xFC02 | ch<<4`: the voice's envelope level as 13 bits, `0x1FFF` at the EG's level `0x7F`;
   - `0xFC01 | ch<<4` (`TgVoiceStatusRead`, behind a gate the firmware keeps shut in these runs): the level too.
     Since 2026-10-22 it answers 0: on the KN6000 the firmware compares this read with a stored target and retries
     until they agree, so it is not the level (`../tg-release-kn6000-2026-10-22/`). No KN7000 run here reads it.
2. **The release rule follows the write.** The low byte of r0 is [release flag | level]. In the probe's log after the
   change, all 26 key-off and reset writes have bit 7 set with level 0: `9180`, `9280`, `8D80`, `8580`, `7A80`, `AA80`,
   `C280`, `8780`, CC 120's `A280`, and 13 resets `FF80`. All 13 note-on programmings have it clear, with level `0x7F`:
   `D27F`, `557F`, `E57F` and the rest. So an r0 write with bit 7 set releases that voice, at the write's rate byte. The pair rule, its 20 ms guard
   and the r3 rule are gone. r3 is not a gate: `TgVoiceGateOn` writes `0x87FF` and `TgVoiceGateOff` the cached word
   (`0x8000`-`0xF000`) 0.1 ms apart inside every note-on, and nothing writes it at key-off.

Inferred, not measured on the unit: the meaning of a set bit in `0xFC08 + g` ("still sounding") is read from the code
(a 1→0 edge retires the node, and held keys are ORed in as 1). The level's scale is the model's own envelope, which is
in the EG's register-level domain; the chip's curve is not known. The flag's name is ours: the KN5000 shares the damp
constants `0x7F80`/`0xA280`/`0xFF80`, which fit "jump to level 0 at this rate".

## Results

### The probe (`probe.mid`, program 893), before (published `7336efbe`) and after (`06334896`)

`measure.py`: the note's fundamental (0.1 s Hann windows) held, then how long after the note-off (or the CC) it takes to
fall 40 dB, and where it stands 1 s and 3 s after. "never" means not within the 4.5 s searched. REVERB is off, so the
sound is the dry tone generator.

| section                    | held (rel.) | before: to -40 dB | before: +1 s | before: +3 s | after: to -40 dB | after: +1 s | after: +3 s |
|----------------------------|-------------|-------------------|--------------|--------------|------------------|-------------|-------------|
| keybed C4 (panel sound)    | 29.9 dB     | 3.68 s            | -14.2 dB     | -23.9 dB     | 0.32 s           | digital 0   | digital 0   |
| MIDI ch 1 D4 (panel sound) | 24.9 dB     | never (4.5 s)     | -14.4 dB     | -25.2 dB     | 0.29 s           | digital 0   | digital 0   |
| ch 4 GM 0 piano E4         | 14.4 dB     | never (4.5 s)     | -2.9 dB      | -4.0 dB      | 0.36 s           | digital 0   | digital 0   |
| ch 5 GM 48 strings F4      | 32.1 dB     | never (4.5 s)     | -3.8 dB      | -4.1 dB      | 0.59 s           | digital 0   | digital 0   |
| ch 6 GM 89 pad G4          | 35.4 dB     | never (4.5 s)     | -2.2 dB      | -0.9 dB      | 0.89 s           | -51.6 dB    | digital 0   |
| ch 7 GM 19 organ A4        | 32.3 dB     | never (4.5 s)     | -8.9 dB      | -8.9 dB      | 0.13 s           | digital 0   | digital 0   |
| ch 8 GM 80 square lead B4  | 44.9 dB     | 0.04 s            | -60.9 dB     | -60.7 dB     | 0.04 s           | digital 0   | digital 0   |
| ch 5 strings C5, CC 123    | 32.4 dB     | never (4.5 s)     | +2.0 dB      | +0.9 dB      | 0.52 s           | digital 0   | digital 0   |
| ch 6 pad D5, CC 120        | 36.6 dB     | never (4.5 s)     | -1.6 dB      | -5.2 dB      | 0.13 s           | digital 0   | digital 0   |

The tone generator's own voice state (`voices.txt`): before, four voices still sounded at full or sustain level when
the probe ended (v3, v5, v67 at 1.000, v70 at 0.913). After, the last voice above zero was at 73.85 s (v5, 0.001,
the pad's CC 120 tail), and none after it. The key-off writes after the change, one burst per voice (`tgw.txt`):

| end   | section                    | the burst's r0 on each voice                    |
|-------|----------------------------|-------------------------------------------------|
| 33.5  | keybed C4                  | `9180` on TG 1 ch 0 and on TG 0 ch 0            |
| 38.5  | MIDI ch 1 D4               | `9280` on TG 1 ch 1 and on TG 0 ch 1            |
| 43.5  | ch 4 piano                 | `8D80` on TG 0 ch 2 (before: no write)          |
| 48.5  | ch 5 strings               | `8580` on TG 1 ch 2 (before: no write)          |
| 53.5  | ch 6 pad                   | `7A80` on TG 0 ch 3 (before: no write)          |
| 58.5  | ch 7 organ                 | `AA80` on TG 1 ch 3 and on TG 0 ch 4            |
| 63.5  | ch 8 square lead           | `C280` on TG 1 ch 4 and on TG 1 ch 5            |
| 68.5  | CC 123 on the strings      | `8780` on TG 1 ch 6 (before: no write)          |
| 73.5  | CC 120 on the pad          | `A280` on TG 0 ch 5; r4, r5, r8, r9 `0000`       |

### Another World in the tone-generator mode (`aw_voices.lua`, 64 s of intro)

Voices above zero, how many of them are still keyed, and the age of the oldest note still sounding, each emulated
second (selected seconds; the intro starts at 84.55 s):

| t (s) | before: sounding | before: keyed | before: oldest | after: sounding | after: keyed | after: oldest |
|-------|------------------|---------------|----------------|-----------------|--------------|---------------|
| 96    | 5                | 5             | 10.8 s         | 5               | 5            | 10.8 s        |
| 104   | 33               | 30            | 18.8 s         | 32              | 8            | 2.4 s         |
| 112   | 93               | 90            | 16.7 s         | 29              | 8            | 4.0 s         |
| 120   | 102              | 99            | 14.7 s         | 29              | 8            | 3.6 s         |
| 136   | 77               | 77            | 22.8 s         | 7               | 6            | 9.6 s         |
| 148   | 53               | 53            | 28.1 s         | 7               | 6            | 2.6 s         |

Before, the game's notes piled up to 102 sounding voices, 99 of them keyed. After, at most 32 sound and at most 10
are keyed in any second. The oldest note reaches 13.6 s at 140 s and ends by 144 s: a long note in the music, not a
hanging one.

### The gate's audio oracle

`oracle_ab.sh` (the gate's recipe: keybed C4 held 16-17 s, REVERB on, 22 s): the published `7336efbe` gives
`5069aedab573b1c63ef6df7689382bd9` (the current `ORACLE_MD5`), the new binary `d520532727c7d590066fc888a18a3f5d`.
`oracle_diff.py`: every sample frame is identical up to 17.0656 s, 66 ms after the key-up. From there the second piano
voice (v64), which the old model never released, now ends with the first:

| second | before      | after       |
|--------|-------------|-------------|
| 17     | -54.1 dBFS  | -57.8 dBFS  |
| 18     | -60.0 dBFS  | -89.1 dBFS  |
| 19     | -64.9 dBFS  | digital 0   |
| 20     | -69.9 dBFS  | digital 0   |
| 21     | -74.9 dBFS  | digital 0   |

## Still approximate

- The rate-byte law (`eg_tau`, 13 x 2^(-rate/20) s) is the old provisional fit; the release times above come from it.
- The level returned by `0xFC02` is the model's envelope. If the chip's curve differs, the firmware's choice of which
  released voice to steal first differs; what sounds and what ends does not.
- The gate-follow coupling (`key_break`, wave page bit 2) and the one-shot class (`m_mode`) were written to make up for
  key-off writes that the firmware now sends. They are left as they were. Both would be worth re-checking against the
  firmware's writes in a sweep of the panel's sound families.
- The KN6000/KN6500 tone generator (`kn6000_tonegen.cpp`) still answers 0 (the base class's `tg_read`). Whether its
  firmware polls the same way was not checked. (2026-10-22: it does, and its notes hung too; fixed the same way,
  `../tg-release-kn6000-2026-10-22/`.)

## The scripts

| file                | question it answers                                                                                                                                 |
|---------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------|
| `gen_probe_mid.py`  | writes `probe.mid`: one note per section, its own pitch, on channel 1 and on channels 4-8 (GM 0, 48, 89, 19, 80), then CC 123 and CC 120 on held notes |
| `probe.lua`         | logs every TG write (`tgw.txt`), every data-port read with its latched address (`tgr.txt`) and the tone generator's voice state (`voices.txt`); REVERB off; keybed C4 |
| `run_probe.sh`      | `run_probe.sh EMU_DIR OUT`: one probe run, -bios v13, the computed stream only                                                                       |
| `measure.py`        | `measure.py OUT`: the table above, from `run.wav` and `voices.txt`                                                                                  |
| `keyoff_trace.dbg`  | MAME debugger script: logs the library's key-event, hold, key-off, slot-service, burst and gate calls (v16 addresses)                               |
| `run_trace.sh`      | `run_trace.sh EMU_DIR OUT [BIOS]`: the probe under `-debug` with `keyoff_trace.dbg`; the calls go to `OUT/error.log`                                |
| `libdump.lua`       | dumps the self-loaded sound library (`0x4C000000`-`0x4C03FFFF`) of a booted kn7000 to `lib.bin`                                                     |
| `libdis.sh`         | `libdis.sh lib.bin ADDR [BYTES]`: disassembles the dump from one entry point                                                                        |
| `callers.py`        | `callers.py lib.bin TARGET...`: relative calls and jumps into TARGET (byte scan)                                                                    |
| `aw_voices.lua`     | Another World's intro (`../listen-2026-10-21/aw_intro.lua`) plus the voice count each second (`voices.txt`)                                         |
| `oracle_ab.sh`      | `oracle_ab.sh EMU_DIR OUT`: the gate's audio oracle with any binary                                                                                 |
| `oracle_diff.py`    | `oracle_diff.py A.wav B.wav`: the first differing frame and each differing second's level                                                          |

The library's addresses differ by build: in v13 (program 893) the code here sits 0x18 bytes lower than in v16
(`TgVoiceGateOff` `0x4C03768D`, the burst `0x4C0376CB`), so the trace runs on v16. The probe's figures are from v13.

## Reproducing

```sh
N=~/compartilhado/kn7000_mame/notes/tg-release-2026-10-21; T=~/compartilhado/tmp/tg-release; export DISPLAY=:0
E=~/compartilhado/kn7000-emulator                      # or a folder with another binary next to links to E's
                                                       # roms, plugins and sdcard_from_real_kn7000.img
$N/run_probe.sh $E $T/after && python3 -I $N/measure.py $T/after
$N/run_trace.sh $E $T/trace16                          # then: grep "TR " $T/trace16/error.log
cd $N/../listen-2026-10-21 && AWI_SCRIPT=$N/aw_voices.lua EMU=$E ./run_aw.sh $T/aw-after tg wav
$N/oracle_ab.sh $E $T/oracle && python3 -I $N/oracle_diff.py OLD/o.wav $T/oracle/o.wav
# the library: TR_OUT=$T/lib ./kn7000 kn7000 -bios v16 ... -autoboot_script $N/libdump.lua, then libdis.sh
```

`probe.mid` md5 `3631652942883f2ec9073242d43c88ec` (36 events). The runs' outputs are scratch in
`~/compartilhado/tmp/tg-release/`; Another World's recordings there are copyrighted and are not committed.

# The KN6000's notes that did not stop (2026-10-22)

The KN7000's hanging notes (G23, `../tg-release-2026-10-21/`) came from the tone generators' status reads
answering 0. That README ended with "the KN6000/KN6500 tone generator still answers 0; whether its firmware polls
the same way was not checked". It does poll the same way, and its notes hung the same way.

## What the KN6000 firmware does

The KN6000 program flash (`mkprog6.py`, loaded at `0x48400000`; the firmware runs it through its mirror at
`0x4C000000`) has the KN7000's voice sweep, instruction for instruction:

- `0x4849A499` (the KN7000's `TgVoiceStatusSweep`) steps a group counter `g` (0-3, at `0x5004A9A0`), reads
  `0xFC08 + g`, ORs in its mask of held keys (`0x50285CB0[g]`), and compares with the previous answer
  (`0x50285CA8[g]`). A voice whose bit falls from 1 to 0 is retired (`0x4849A289`, `0x4848F3C9`, `0x48493C82`,
  `0x4849A838`). For a voice still sounding and not held (node flags `& 0x81` clear), it reads `0xFC02 | ch<<4`,
  keeps `(x & 0x1FFF) >> 5` as the level, and kicks a released voice below `0x80` (`0x4849A2FA`).
- The read itself is `0x48494675`: write the address half to `0x98050000`, the data half to `0x98050002`, read
  `0x98050002`. Seven call sites use it.
- In the probe (`probe.mid`, before the fix) it reads `0xFC08`-`0xFC0B` every 24 ms, one group per read: 2,083 reads
  in 50 s, all answered 0.
- Four other call sites (`0x48481471`, `0x484815CE`, `0x48483521`, `0x4848358E`) read `0xFC01 | ch<<4`. They
  sign-extend bit 12 of the 13-bit answer and compare it with a stored target byte `<< 5` (node `+0x79`), retrying
  every 12 ms until they agree. So it is the current position of something the chip ramps, not the amplitude. It is
  left unanswered (0), as before. Before the fix the probe saw 24 of these reads; after it, 602, because more voices
  now live long enough to be asked.

Before the fix, each note keyed two voices (an even/odd pair). The odd one was released about 10 ms after the note-on,
and the even one was never released: at the end of the probe (78.95 s), v4, v6 and v10 (strings, pad, the CC 120 pad)
still sounded at full level and v8, v9 near it. The firmware wrote **nothing** to the tone generator at any of the
eight note-offs or CCs.

## A second fault: the KN6000's 0x98040000 is not a tone generator

The odd voices' early release came from the driver, not from the firmware's voice handling. `kn7000_state::io_w` fed
every write to `0x98040000`/`0x98040002` (the KN7000's second tone generator) into the tone generator as `tg 0`, and
the KN6000 device ignores `tg`. The KN6000 has only one tone generator. Its one writer of `0x98040000` is the
"Device-A" module at `0x48510459` (`notes/sound-cross-model-kn6000-kn6500.md` already lists it): byte writes of a
register `0x10 | n`, then a value. About every 0.1 s it writes registers `0x14`, `0x34`, `0x54` and `0x74` with
`0x8E`. Decoded as tone-generator addresses, those are voices 1, 3, 5 and 7, cls `0x0004`, with bit 7 set: a release
under the new rule, and the voice's default slow release under the old one.

Finding it: `v1trace.lua` showed no write to the TG window between voice 1's last note-on write and its release. A
temporary `logerror` in the release paths (not committed) then showed the writes arriving as `0x008E` on voice 1's
cls `0x0004` without passing through `0x98050002`. `0x9804` occurs in the KN6000 program only at `0x4851045D`.

## The change

- `kn6000_tonegen.cpp`, `kn6000_tonegen.h`: `tg_read()` answers `0xFC08 + g` (bit i set if voice `16g + i` is in
  attack or above zero) and `0xFC02 | ch<<4` (the voice's level, 13 bits). This is the KN7000's answer, read from the
  shared voice state (`kn_tonegen.h`). `0xFC01` stays 0.
- The release follows the write, as on the KN7000: a cls `0x0004` write (the amp EG's first register, the KN7000's r0)
  with low-byte bit 7 set releases that voice, at the write's rate byte. The cls `0x0000` "gate" rule and the
  20 ms-guarded cls `0x0004` heuristic are gone. Cls `0x0000` is the KN7000's r3 key-on strobe: `0x87FF` first and
  `0x8000` last inside every note-on, never at key-off (11 of each in the probe, one pair per note-on).
- `kn7000.cpp`: on a one-chip model (`m_tg_one_chip`, KN6000/KN6500), writes to `0x98040002` no longer reach the tone
  generator, and reads of it answer 0.
- `notes/kn6000-tonegen-spec.md` and the device's comments called `0x0000 = 0x8000` the KN6000's "universal key-up
  gate". That reading came from the `0x8000` that closes each note-on. Corrected.

## Results

Binary before: published md5 `06334896956d22a2706028be5b86f7f2`. After: `0f75c6df2870c51a721b495e9ec3c242`,
published 2026-10-22. `run_probe6.sh` (kn6000, `probe.mid`) and `../tg-release-2026-10-21/measure.py`. The KN6000's
wave ROMs are undumped, so every voice is the placeholder sine. The "keybed C4" section is not played on the KN6000
(`probe6.lua` presses no key), so it is left out.

| section                    | held (dB) | before: to -40 dB | before: +1 s | after: to -40 dB | after: +1 s | after: +3 s |
|----------------------------|-----------|-------------------|--------------|------------------|-------------|-------------|
| MIDI ch 1 D4 (panel sound) | 35.4      | never (4.5 s)     | -1.3 dB      | 1.05 s           | -38.4 dB    | digital 0   |
| ch 4 GM 0 piano E4         | 26.4      | never (4.5 s)     | -2.8 dB      | 0.80 s           | -38.0 dB    | digital 0   |
| ch 5 GM 48 strings F4      | 31.1      | never (4.5 s)     | -1.2 dB      | 0.60 s           | -49.8 dB    | digital 0   |
| ch 6 GM 89 pad G4          | 35.3      | never (4.5 s)     | +2.8 dB      | 1.57 s           | -23.8 dB    | digital 0   |
| ch 7 GM 19 organ A4        | 38.0      | never (4.5 s)     | -0.7 dB      | 1.12 s           | -32.7 dB    | digital 0   |
| ch 8 GM 80 square lead B4  | 26.5      | never (4.5 s)     | -0.8 dB      | 1.18 s           | -30.3 dB    | digital 0   |
| ch 5 strings C5, CC 123    | 26.4      | never (4.5 s)     | -0.2 dB      | 0.59 s           | -51.1 dB    | digital 0   |
| ch 6 pad D5, CC 120        | 30.5      | never (4.5 s)     | +0.8 dB      | 1.19 s           | -25.6 dB    | digital 0   |

The tone generator's own voice state (`voices.txt`): before, eleven voices were above zero at 78.95 s, five of them
at 0.80 or more. After, the last voice above zero is v10 at 73.85 s (0.001, the tail of the CC 120 pad), and none
follows it.

After the fix the firmware sends a key-off burst at every note-off and CC, to every voice of the note. It writes the
same six registers as on the KN7000, shifted by four (`{4,5,8,9,C,D}` for `{0,1,4,5,8,9}`), with the same rate bytes
(`tgw6.py after/tgw.txt`):

| end  | section            | cls 0x0004 / 0x0005 on each voice | KN7000, same section (`../tg-release-2026-10-21/`) |
|------|--------------------|-----------------------------------|----------------------------------------------------|
| 38.5 | MIDI ch 1 D4       | `8C80` / `8C00` on v0 and v1      | `9280` (its panel sound differs)                   |
| 43.5 | ch 4 piano         | `8D80` / `8D00` on v2             | `8D80`                                             |
| 48.5 | ch 5 strings       | `8580` / `8500` on v3             | `8580`                                             |
| 53.5 | ch 6 pad           | `7A80` / `7A00` on v4             | `7A80`                                             |
| 58.5 | ch 7 organ         | `AA80` / `AA00` on v5 and v6      | `AA80`                                             |
| 63.5 | ch 8 square lead   | `C280` / `C200` on v7 and v8      | `C280`                                             |
| 68.5 | CC 123, strings    | `8780` / `8700` on v9             | `8780`                                             |
| 73.5 | CC 120, pad        | `A280` / `A200` on v10            | `A280`                                             |

Every note-on programs cls `0x0004` with bit 7 clear (`E57F`, `D97F`, `557F`, `B17F`, `BA7F`, `BE7F`), after an
`FF80` reset. That is the KN7000's r0 pattern exactly.

**The KN7000 is unchanged.** `../tg-release-2026-10-21/oracle_ab.sh` with the new binary gives
`d520532727c7d590066fc888a18a3f5d`, the gate's current `ORACLE_MD5`.

**The KN6500** runs the same sweep (`0xFC08`-`0xFC0B`, 2,083 reads in the probe, `MODEL=kn6500 run_probe6.sh`),
but in this probe it plays no note from MIDI IN 1 with either binary: 70 TG writes, none a note-on, and digital
silence. So the change is not exercised there yet. Why the KN6500 ignores `probe.mid` was not looked into.

## Still approximate

- As on the KN7000: the release-rate law (`eg_tau`) is the provisional fit, and the level answered for `0xFC02` is
  the model's envelope. The release times above come from both.
- `0xFC01 | ch<<4` is answered 0. The firmware retries those reads until the answer matches its stored target, so it
  now asks more often (602 reads against 24). It has no audible effect in the probe. What the chip reports there is
  not known.

## The scripts

| file            | question it answers                                                                                                                 |
|-----------------|-------------------------------------------------------------------------------------------------------------------------------------|
| `probe6.lua`    | logs every TG write (`tgw.txt`), every read of `0x98050002` with its latched address (`tgr.txt`) and the voice state (`voices.txt`) |
| `run_probe6.sh` | `run_probe6.sh EMU_DIR OUT`: one KN6000 run of `../tg-release-2026-10-21/`'s `probe.mid`; `MODEL=kn6500` for the KN6500             |
| `tgw6.py`       | `tgw6.py OUT/tgw.txt FROM TO`: the writes between two times with voice and class decoded (the key-off and cls tables)               |
| `v1trace.lua`   | each TG write around voice 1's note-on with voice 1's state: showed that no TG-window write released it                             |
| `mkprog6.py`    | `mkprog6.py ROMDIR OUT.bin`: the KN6000 program flash as the CPU sees it (the two ROMs interleaved word by word)                    |
| `dis6.sh`       | `dis6.sh prog.bin ADDR [BYTES]`: disassembles from an entry point (`0x4C` mirror addresses accepted)                                |
| `callers6.py`   | `callers6.py prog.bin TARGET...`: relative calls and jumps into TARGET (byte scan); found the seven users of the read               |

The measurement is `../tg-release-2026-10-21/measure.py OUT` (its first row is the keybed note, which the KN6000 run
does not play).

## Reproducing

```sh
N=~/compartilhado/kn7000_mame/notes/tg-release-kn6000-2026-10-22; T=~/compartilhado/tmp/tg-release-kn6000; export DISPLAY=:0
E=~/compartilhado/kn7000-emulator                       # or a folder with another binary next to links to E's roms, plugins
$N/run_probe6.sh $E $T/after && python3 -I $N/../tg-release-2026-10-21/measure.py $T/after
python3 -I $N/tgw6.py $T/after/tgw.txt 38.49 38.6       # the first key-off burst
MODEL=kn6500 $N/run_probe6.sh $E $T/kn6500
python3 -I $N/mkprog6.py $E/roms/kn6000 $T/prog.bin && $N/dis6.sh $T/prog.bin 0x4849A499 0x120   # the sweep
```

`probe.mid` md5 `3631652942883f2ec9073242d43c88ec`, `prog.bin` md5 `7651ce8b12e75499a853ddead7f45aca`. The runs'
outputs are scratch in `~/compartilhado/tmp/tg-release-kn6000/`.

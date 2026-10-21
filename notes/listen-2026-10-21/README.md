# Listening recordings of the emulated KN7000 (2026-10-21)

A set of recordings for Felipe to compare by ear, made easy to listen to. The previous set
(`~/compartilhado/tmp/dsp-noise/`) sounded silent: about -45 dBFS RMS, the notes filling about 21 s of a 50-90 s file
after about 30 s of boot silence, and 3-channel WAVs that many players handle badly. These files are trimmed to the
music, stereo 16-bit 48 kHz, normalized to a -1 dBFS peak with one gain per comparison group, and come with MP3s.

The listening files are in `~/compartilhado/tmp/listen-2026-10-21/` (scratch, with its own `README.txt`). None are
committed: Another World's audio is copyrighted, and the rest can be regenerated from the scripts here.

Everything was run on the published emulator `~/compartilhado/kn7000-emulator/kn7000` (md5 `7336efbe`: the effects
DSP at 60 MHz, DRC on), `-bios v13` (program 893), with `-window` and `DISPLAY=:0`. Background:
`notes/dsp-noise-2026-10-21/README.md` (live capture, speed) and `notes/PLAN-2026-10-21-dsp-emulation.md` (D2).

## Felipe's verdict (2026-10-21)

He listened to `aw-intro-dsp-computed.wav` (Another World's intro in DSP mode, MAME's `-wavwrite` stream) and found
it "sounding great" -- "perfect"; for him that settles that the noise heard live in MAME is emulation speed, not
wrongly computed audio (`notes/dsp-noise-2026-10-21/README.md`). The other files were not listened to.

## The scripts

| file                | question it answers                                                                                                                                                                                                                                                        |
|---------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `gen_listen_mid.py` | writes `listen.mid` (ours, public domain): a square-lead chord with a release and tail, Bach's Prelude BWV 846 bars 1-4 on piano, strings with drums, a pad chord. `--layout=1..4` rebuilds the files of the earlier takes, each checked against the md5 its take recorded |
| `listen.mid`        | the file itself (layout 5, md5 `8ed7203d`)                                                                                                                                                                                                                                 |
| `midi_take.lua`     | one take of `listen.mid`: leaves REVERB at its boot state (on) or presses it off at 27 s, and logs the firmware's REVERB LED (`cpr_led27`) at 26.5, 28.5, 30 s and the end; a screen snapshot at 29.5 s                                                                    |
| `run_midi.sh`       | `run_midi.sh EMU OUT on\|off`: `listen.mid` on MIDI IN 1 (`-midiin1`), the computed stream (`-nothrottle -sound none -wavwrite`); `BYPASS=1` for a bypass-scratch binary                                                                                                   |
| `aw_intro.lua`      | Another World's intro through the program menu card: boot, menu, game, sample bank, then 64 emulated s of the intro; in `tg` mode PART SELECT RIGHT 2 once as the intro starts; logs the mode and the speed                                                                |
| `run_aw.sh`         | `run_aw.sh OUT dsp\|tg wav\|live`: the card build put into a copy of the real card image; `live` is throttled with real sound, `pw-record` of the sink monitor and `-wavwrite` in the same session                                                                         |
| `mklisten.py`       | `mklisten.py WORK OUT`: trims, keeps channels 0-1, applies one gain per group, writes WAV and MP3, and checks every output (duration, peak, RMS, first note, sounding share, section levels)                                                                               |
| `levels.py`         | `levels.py WAV FROM TO STEP [NOTES]`: does a note stop at its note-off? Window levels, and the level at given notes' fundamentals                                                                                                                                          |

## The listening set (`mklisten.py`, as written)

MAME's `-wavwrite` file has 3 channels. Channels 0 and 1 are the instrument's left and right outputs and were kept.
Channel 2 is the floppy drive, and it was digital silence (-240 dBFS) in every trimmed span. The live capture is
`pw-record`'s two channels.

| file                      | group  | source                      | cut (s in source) | duration | gain      | peak       | RMS         | first note | 1 s windows > -50 dBFS |
|---------------------------|--------|-----------------------------|-------------------|----------|-----------|------------|-------------|------------|------------------------|
| midi-reverb-on.wav        | midi   | midi-on/run.wav ch 0,1      | 29.53-68.03       | 38.50 s  | +5.23 dB  | -5.96 dBFS | -24.85 dBFS | 0.50 s     | 92%                    |
| midi-reverb-off.wav       | midi   | midi-off/run.wav ch 0,1     | 29.50-68.00       | 38.50 s  | +5.23 dB  | -1.00 dBFS | -18.63 dBFS | 0.50 s     | 89%                    |
| aw-intro-dsp-computed.wav | aw-dsp | aw-dsp-live/run.wav ch 0,1  | 84.66-145.16      | 60.50 s  | +21.22 dB | -1.56 dBFS | -19.15 dBFS | 0.50 s     | 100%                   |
| aw-intro-dsp-live.wav     | aw-dsp | aw-dsp-live/live.wav ch 0,1 | 138.40-239.74     | 101.34 s | +21.22 dB | -1.00 dBFS | -18.89 dBFS | 0.50 s     | 100%                   |
| aw-intro-tg-computed.wav  | aw-tg  | aw-tg/run.wav ch 0,1        | 84.75-145.25      | 60.50 s  | +6.85 dB  | -1.00 dBFS | -15.54 dBFS | 0.49 s     | 100%                   |

`listen.mid`'s sections in the two takes (`mklisten.py`; seconds after the first note, at emulated 30 s):

| section                      | REVERB on   | REVERB off  |
|------------------------------|-------------|-------------|
| square-lead chord held 0.5-3 | -17.9 dBFS  | -11.5 dBFS  |
| 0.2-0.7 s after its release  | -31.4 dBFS  | -240.0 dBFS |
| 1-2 s after its release      | -62.1 dBFS  | -240.0 dBFS |
| 3-5 s after its release      | -240.0 dBFS | -240.0 dBFS |
| piano 8-21.3                 | -33.1 dBFS  | -26.6 dBFS  |
| strings+drums 22-30          | -25.4 dBFS  | -19.4 dBFS  |
| pad held 31.5-35             | -22.4 dBFS  | -16.1 dBFS  |
| pad 0.5-1.5 s after release  | -22.3 dBFS  | -16.1 dBFS  |
| end 36.5-38                  | -22.1 dBFS  | -16.3 dBFS  |

What this shows:

- **D2 holds for MIDI-played voices.** With REVERB on, every section is 6.0-6.5 dB quieter than with it off, and the
  first sound comes 30 ms after the note-on (29.53 s against 29.50 s): the output is the reverb's return only, with
  its pre-delay, and no dry sound. With REVERB off the square-lead chord ends in digital zero within 0.25 s of its
  note-off. With REVERB on, a tail follows that falls from -26 to -104.5 dBFS in about 2.4 s (about 32 dB/s) and
  is digital zero from 35.5 s (`levels.py midi-on/run.wav 32.5 36 0.25`).
- **The hung voices.** From the piano on, the last three sections' "after release" levels equal their held levels:
  the piano, strings and pad never stop (next section).
- **Another World.** In the DSP mode the intro's computed stream peaks at -22.8 dBFS. The tone-generator mode is
  14.4 dB louder (the gains differ by that much). The live capture ran at a mean 63.2% speed over the intro
  (`aw_intro.lua`'s per-second log), so it lasts 101.3 s for the computed 60.5 s, the same music stretched. One
  gain covers the computed and live files, and their RMS agrees within 0.3 dB.

## How the file got its order: MIDI-received notes hang in MAME

The file needs a sustained chord with a clear release, so that the reverb tail can be heard. It took five versions
and nine MIDI takes (`gen_listen_mid.py --layout=N` rebuilds each; the takes are in
`~/compartilhado/tmp/listen-2026-10-21/work/`):

| layout | takes             | order                                                       | what the take showed (`levels.py`)                                                                                                   |
|--------|-------------------|-------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------|
| 1      | midi-off-v1       | piano, strings + drums, organ, pad                          | B2, A3, F4, played only by the strings at 48-52 s, are still at full level at 66-68 s; the level never falls after 52 s              |
| 2      | midi-off-v2       | as 1 with pad and organ swapped, CC 123 + CC 120 per part   | the pad's C major (C3 G3 E4 G4 C5) is undiminished at 65-68 s, 3-6 s after CC 123/120 at 57.5 s; the controllers stop nothing        |
| 3      | midi-off/on-v3    | piano, organ, strings + drums, pad                          | after the Prelude the piano holds at about -35 dBFS (REVERB off) under everything that follows                                       |
| 4      | midi-off/on-v4    | organ first, then piano, strings + drums, pad               | the church organ (GM 19) falls 9 dB at its note-off (-25.4 to -34.5 dBFS; REVERB on 10 dB) and then holds                            |
| 5      | midi-off, midi-on | square lead (GM 80) first, then piano, strings + drums, pad | the square lead ends: digital zero within 0.25 s (REVERB off); a 2.4 s tail to digital zero (REVERB on). The listening set uses this |

So, in this overlay (`4f7b9c7`, binary `7336efbe`), notes received on MIDI IN 1 do not end at their note-off for GM
0 (piano), 48 (strings), 89 (pad) or, partly, 19 (church organ), and All Notes Off and All Sound Off don't end them
either. GM 80 does end. The note-off probe (technics-anotherworld `probes/cnv/README.md`, `awcnv_noteoff.lua`) had
shown the same for GM 0 against GM 80. The overlay's tone generator releases a voice on the firmware's gate-off
write (`r3` = 0x80xx) or on the managed release burst (`kn7000_tonegen.cpp`). Which of those the firmware sends for a
MIDI note-off on these voices hasn't been traced. The order of layout 5 works around this: the chord whose release
matters comes first, into silence. On the real instrument, all five sections should end at their note-offs.

Traced and fixed later on 2026-10-21: the tone generators' status reads answered 0, so the firmware dropped its
voices within 0.1 s of each note-on (`../tg-release-2026-10-21/README.md`, OVERLAY-GAPS G23).

## Another World in the tone-generator mode: when RIGHT 2 is read

The first `tg` run pressed PART SELECT RIGHT 2 between the end of the sample bank (80.70 s) and the intro (84.50 s).
The panel byte showed the press, but the game's sound mode (`DV_MODE`) stayed 0 for the whole intro. That run's
computed stream is the DSP mode (`work/aw-tg-v1/`, not used). The game reads the button only once its loop runs.
`aw_intro.lua` therefore presses it as the intro starts: at 84.55 s the intro starts, and at 84.88 s the mode is 1,
before the intro's first sound at about 85.2 s.

## Not done

- **The take with the effects DSP bypassed.** The bypass-scratch binary (`~/compartilhado/tmp/dsp-noise/emubyp/`,
  `../dsp-noise-2026-10-21/bypass-scratch.patch`) would have been one more run, but the MIDI takes had already used
  the budget. It would add little to the set: with REVERB off the DSP isn't heard at all (B1/B2 identical statistic
  for statistic, bypassed or not, in `../dsp-noise-2026-10-21/README.md`), so the bypass take would sound like the
  REVERB-off one. The dry sound is in `midi-reverb-off`.

## Runs

Eleven MAME runs in all: nine MIDI takes (above), two `tg` runs (the first one with the ignored press), and one live
`dsp` run, which also wrote the computed DSP stream. The MIDI and `tg` runs ran up to three at a time (`-nothrottle`:
their computed streams do not depend on host speed). The live run ran alone.

## Reproducing

```sh
N=~/compartilhado/kn7000_mame/notes/listen-2026-10-21; W=~/compartilhado/tmp/listen-2026-10-21/work
E=~/compartilhado/kn7000-emulator; export DISPLAY=:0
python3 -I $N/gen_listen_mid.py $N/listen.mid             # md5 8ed7203d6de097e5d457f25074f02508
$N/run_midi.sh $E $W/midi-off off
$N/run_midi.sh $E $W/midi-on on
$N/run_aw.sh $W/aw-tg tg wav
$N/run_aw.sh $W/aw-dsp-live dsp live                      # alone: the live capture depends on host speed
python3 -I $N/mklisten.py $W ~/compartilhado/tmp/listen-2026-10-21
# an earlier take: python3 -I $N/gen_listen_mid.py $W/l4.mid --layout=4, then run_midi.sh with it as listen.mid
```

`run_aw.sh` uses the card build `technics-roms-disasm/kn7000/tools/kn7menu/build/card/` as it is (menu KN7APP.BIN
sha1 `0566fba3`, `AW\KN7APP.BIN` sha1 `94910f68`) and the owner's loader floppy release 2026-10-19. The live mode
needs PipeWire's `pw-record`. The computed WAVs of this set have these md5s: `midi-reverb-on.wav` `b42823af`,
`midi-reverb-off.wav` `dde049c4`, `aw-intro-dsp-computed.wav` `e1f07495`, `aw-intro-tg-computed.wav` `d4b0e6d0`
(the live capture is not reproducible to the bit).

# G13: the KN7000's voices on the dumped wave ROMs (2026-10-20)

The voices now play the four wave ROMs (IC203/IC204, IC207/IC208). This folder holds the decoding
and the scripts that produced every number below. No ROM data is here: every table is computed
from the ROM files at run time (`wavedir.py` reads them from `~/compartilhado/kn7000-emulator/roms/kn7000/`,
or from `$KN7000_ROMS`).

## What decides a voice's sample

Three things, all measured:

1. **The tone generator the voice is on picks the ROM pair.** The TG at `0x98050000` (the firmware's
   MAIN TG) reads IC203 + IC204; the one at `0x98040000` (SUB TG) reads IC207 + IC208. These are the
   pairs the firmware's WAVE ROM test reads through each TG's port. The firmware decides which TG
   a voice goes to, from where its sample lives (`TgVoiceSideSelect` 0x4C02BECB: bits 10/11 of the
   note's routing entry).
2. **A 20-bit select written to plane 0x1C** (the old "aux word", register class 0x1C0x):
   the register index (address bits 3:0) carries select bits 19:16 and the data bits 15:0.
   Bits 19:12 are the **ROM page**, bits 11:0 the **directory entry** in that page.
   Pages 0x00-0x0F are the 16 pages of the TG's own pair; 0x20 and up are the expansion board
   (`TgVoiceRouteFieldSet` 0x4C037C16 adds 0x20/0x30 for the expansion banks).
3. **The page's directory** in the ROM, which gives the sample's start, format, loop and pitch
   exponent. The firmware never sends an address, a loop or a length; the TG reads them itself.

### The hardware subtype was wrong in the driver

The firmware reads a hardware subtype from strap `0x98070000` bits 11:10 (`PanelSubTypeGet`
0x484D7751: 00 -> 5, 01 -> 1, 10 -> 2, 11 -> 3). The driver always returned 00, subtype 5. Under
subtype 5 the firmware remaps every wave page (ROM table 0x48587774: pages 0x00-0x07 and 0x08-0x0F
both fold onto 0x20-0x2B) and assigns voices to the tone generators by a table (0x48586514)
instead of by where the sample is. Every select it wrote was an expansion page:

| capture (`traces.sh`, md5 of trace.txt)       | strap    | voices | select names an internal page | either pitch test passes |
|-----------------------------------------------|----------|--------|-------------------------------|--------------------------|
| `strap5` (`ecea30eb204d2da2584e65efede39d3f`) | 00 (old) | 488    | 0 (all pages 0x20-0x2B)       | 0                        |
| `strap1` (`5dcc2ad916b861d58c9b401017dee272`) | 01 (new) | 556    | 556                           | 478                      |

With bits 11:10 = 01 the routes are the pages themselves, each voice lands on the TG whose pair
holds its sample (both layers of the stereo piano land on different TGs, one per pair), and the
pitch tests below pass. Subtypes 1 and 2 behave the same everywhere the firmware reads the
subtype (the SD worker and SPI clock, the side select, the route remap), so the driver now
reports 1 for the KN7000 only. **The real unit's strap has not been read**; see "Open" below.

## The wave ROM format

Each pair is one stream of 16-bit words: word 2i is word i of the Y ROM (IC203 / IC207), word
2i+1 word i of the X ROM (IC204 / IC208), low byte first (`technics_roms/.../wave-analysis/`).
The stream is 16 pages of 0x100000 words, and every page starts with its own directory:

| words of entry j | name | meaning                                                                      |
|------------------|------|------------------------------------------------------------------------------|
| 4j               | A    | the entry's record, in words from the page start; A of entry 0 = 4 x entries |
| 4j+1             | P    | 0x1000 \| E<<4 \| F<<3 \| K                                                  |
| 4j+2             | B    | the sample's first word, in units of 16 words from the page start            |
| 4j+3             | Q    | a copy of the record's second word                                           |

- **E** (bits 11:4) is the pitch exponent: a waveform with a period of 2^(E-9) samples sounds at the
  note pitch18 encodes. **F** (bit 3) set: two 8-bit samples per word, low byte first.
  **K** (bits 2:0): the loop granule L = 2^(K+4) samples.
- **The record** at word A is B again, then words `[flags:2][code:6][value:8]`. A value >= 0x80 is a
  segment of (256 - value) granules from the start. Flag 0x40 on a segment: the loop starts at its
  end. Flag 0x80: the loop ends at its end. Without an explicit end the loop is the single granule
  after the segments. Values below 0x80 (descending multiples of 8) are not segments, and the word
  with both flags ends the record. Explicit loops usually end 32 samples before the next entry's
  start (main 446 entries, sub 341), and those 32 samples repeat the loop's first 32 (440 and 339
  of them exactly) -- the interpolator's run-out. The loop counts per kind are `loopcheck.py`'s.
- **8-bit samples** keep each segment near full scale; the segment's code (a, b) scales it by
  2^(-b/2) (3 dB per step, fitted by `code8fit.py`; a is not used).
- Main pair: 2426 entries (1948 16-bit, 478 8-bit); sub pair: 1548 (1027 / 521). Entries per page:
  main 181 130 119 138 70 117 1132 36 92 27 42 45 44 174 57 22, sub 208 198 37 110 139 111 109 29 44
  170 45 36 46 202 36 28.

The KN5000's IC307 looks like the Y half of such a pair (an inference, not checked on KN5000
hardware): its {param_ptr, wave_offset} directory is our Y ROM's {A, B}, its "x16 bytes" is our
B x 16 stream words seen from one chip, its four 1 MB pages are our pages seen from one chip, and
its "256-sample sine" is the even half of the 512-sample sine both pairs' page 0 starts with. P,
Q and every other record word would then be on the undumped partner chip, which is why the
KN5000 notes found no loop or root data in IC307.

## Pitch

    rate = 2^((pitch18 - 0x1E200) / 0x3000 + E - 9) * C7 / 44100     (source samples per output sample)

pitch18 0x1E200 is note 96 (C7, 2093.0045 Hz), 0x400 per semitone. The firmware already folds each
zone's tuning into pitch18 (the "multisample correction" the tone tables carry); the TG adds only
the sample's octave E. Checked in two ways on every voice of the `strap1` capture (15 sound
groups x 16 keys; `pitchcheck.py`), against the note the firmware itself meant (the voice
record's notePitch16; drum voices, which have none, are left out):

| group    | voices | loop holds a whole number of periods | spectrum within 15 cents | either |
|----------|--------|--------------------------------------|--------------------------|--------|
| ACCREG   | 32     | 32                                   | 28                       | 32     |
| BASS     | 32     | 32                                   | 32                       | 32     |
| BRASS    | 48     | 48                                   | 25                       | 48     |
| DRAWBAR  | 78     | 22                                   | 0                        | 22     |
| EXPLORER | 32     | 26                                   | 32                       | 32     |
| GUITAR   | 48     | 48                                   | 22                       | 48     |
| MALLET   | 32     | 32                                   | 32                       | 32     |
| ORGAN    | 16     | 10                                   | 16                       | 16     |
| PAD      | 32     | 32                                   | 32                       | 32     |
| PIANO    | 32     | 12                                   | 32                       | 32     |
| SAX      | 64     | 48                                   | 24                       | 49     |
| STRINGS  | 32     | 29                                   | 32                       | 32     |
| SYNTH    | 32     | 32                                   | 0                        | 32     |
| TABORGAN | 30     | 16                                   | 12                       | 23     |
| WORLD    | 16     | 16                                   | 16                       | 16     |
| all      | 556    | 435                                  | 335                      | 478    |

The failures are voices whose note is not the key: the digital drawbar's and the tab organ's
footages (16', 5 1/3', ...), the sax's breath layer (fixed pitch18). Natural recordings (piano)
loop over a non-whole number of their inharmonic periods but pass the spectrum test; single-cycle
synth waves pass the loop test exactly and fool the spectrum test.

In the emulator, the new build plays the notes at their keys (`wavpitch.py`, capture `play`):
piano C3/C4/A4/C5 +2.1/+4.5/+1.5/+4.5 cents, organ -0.9/-0.3/+0.9/+2.1, brass -0.3/-0.3/+0.3/+0.3,
strings +13.5/+14.7/-6.9/+4.5, bass and mallet within 10 cents except where the previous note's
tail is still ringing (A4: the estimator locks onto the C4 that is still sounding; the spectra
show 440 Hz and, for the bass, 220 Hz, its octave-down sound). That capture (`traces.sh play`, v16)
gave trace md5 `0142effa3455ffcc209c07355496005d`, WAV `2190015dc1a8a16a022776c25097d6c7`.

Felipe's firmware (893, `BIOS=v13 ./traces.sh play ...`) does the same: the piano's C4 again on both
TGs (selects 0x0A00F and 0x08023), all 48 voices pass `pitchcheck.py`, and `wavpitch.py` gives the
same pitches within 2 cents except where a previous note's tail overlaps (bass C4 -4.5 against
+10.5 cents, and the A4s above) (trace md5 `4575449db08c0a44c35759d862e35042`, WAV
`36dd19521c005e7d46ca93a96a2d42c0`).

## What changed in the overlay

| file                     | change                                                                                                |
|--------------------------|-------------------------------------------------------------------------------------------------------|
| `kn7000.cpp`             | strap 0x98070000 bits 11:10 = 01 (hardware subtype 1), KN7000 only (`m_strap_subtype`)                |
| `kn_tonegen.{h,cpp}`     | ROM voices: directory/record parse (cached per select), 16/8-bit fetch, loop, the pitch law           |
| `kn7000_tonegen.{h,cpp}` | finds the four ROM regions; note-on selects (TG pair, 20-bit select); held-voice pitch writes re-rate |

Without the four ROM regions the voices keep the synthetic wave pack (the KN6000/KN6500/KN2400
models, and any build without the dumps). The envelope model is unchanged; the gate-follow class
it took from "aux bit 15" is now page bit 2, which is what that bit was under subtype 5.

## Scripts

| script           | question it answers                                                                                     | run                                                 |
|------------------|---------------------------------------------------------------------------------------------------------|-----------------------------------------------------|
| `tg_trace.lua`   | every TG register write (and the strap override), for single notes of chosen sound groups               | through `traces.sh`                                 |
| `traces.sh`      | regenerates the captures quoted here: `strap5`, `strap1`, `play`                                        | `./traces.sh strap1 ~/compartilhado/tmp/x [BINARY]` |
| `noteons.py`     | one row per voice note-on: TG, channel, 20-bit select, pitch18, the firmware's note                     | `python3 noteons.py trace.txt`                      |
| `wavedir.py`     | the ROM model (library); alone it prints the directory census                                           | `python3 wavedir.py`                                |
| `loopcheck.py`   | does the record grammar put each loop where the data has one (exact pre-roll copies), and where it ends | `python3 loopcheck.py`                              |
| `pitchcheck.py`  | does each traced voice sound at the firmware's note under the select and pitch rules                    | `python3 pitchcheck.py trace.txt... [-v]`           |
| `code8fit.py`    | which gain law makes 8-bit samples continuous across their segments                                     | `python3 code8fit.py`                               |
| `wavpitch.py`    | the pitch, level and clipping of each note in a `-wavwrite` capture of a `tg_trace.lua` run             | `python3 wavpitch.py trace.txt o.wav`               |
| `oracle_note.py` | the gate oracle capture in numbers: level, clipping, pitch of the held C4, the tail after release       | `python3 oracle_note.py old.wav new.wav`            |

## The gate, the audio oracle, the boot

On the build tree (binary md5 `ed65537dda916adc765b90925fc4a373`, run from a copy of the published
folder with that binary: `EMU_DIR=... tools/gate.sh`): 16 passed, 1 failed, 1 skipped. The failure is
the KN7000 audio oracle, as expected: its md5 is now **`dbe3683b25d0e26f823ddbb1fa78bb56`** (was
`8a1fe2a44e064f94ff935242fd717cb4`, which the published binary still gives under
`notes/core-port-2026-10-19/oracle_ab.sh`). `ORACLE_MD5` in `tools/gate.sh` is not changed here.
Liveness passes for every model, and the KN5000 demo oracle is unchanged (`8bbe54f7...`).

The oracle capture before and after (`oracle_note.py`, `tools/kn5000_wav_ab.py`,
`notes/dsp-probe-2026-10-20/wav_shift.py`):

| capture             | t=10-15.5 s | note t=16-18 s (rms / peak) | tail t=18-21 s (rms / peak) | clipped | held note (t=16.25-17.0 s) |
|---------------------|-------------|-----------------------------|-----------------------------|---------|----------------------------|
| before (`8a1fe2a4`) | silent      | 163.7 / 969                 | 0.7 / 9                     | 0       | 260.13 Hz, -9.9 cents      |
| after (`dbe3683b`)  | silent      | 241.8 / 1616                | 21.1 / 84                   | 0       | 262.31 Hz, +4.5 cents      |

The note is the Concert Grand's C4 from the two piano samples (one per TG) instead of a KN5000
donor; it is 3.4 dB louder, starts 9.4 ms earlier (wav_shift: onset 16.0795 s against 16.0889 s)
and leaves a tail where the donor was silent after the release. Every second but 16-21 is
identical, except second 0, where the old binary has a 4-unit blip (rms 0.5) and the new one none.

Boot, published binary (`2a8e2fce`) against this one (`ed65537d`), `notes/core-port-2026-10-19/ab_boot.sh`
(no media, fresh settings, snapshots at 2 3 4 5 6 8 12 20 45 s): all nine snapshots identical for
kn7000 v16, v15, v13 and sp7001, kn6000, kn6500, kn2400 and kn2600, and no unimplemented-opcode or
divide-by-zero lines in either. The strap's other readers (the SD worker's subtype-4 tests and the
SPI clock) show nothing at boot without a card.

## Open

- **The strap value on the real unit.** Bits 11:10 of `0x98070000` read 01 or 10 on Felipe's unit if this
  is right; 00 (what the driver gave) would put every internal sound on the expansion pages. A
  read-only .CNV probe can read the halfword at `0x98070000` and the subtype the firmware derived (call
  `0x484D7751`).
- **The 8-bit gain law** is fitted, not derived: 2^(-b/2) brings the segment boundaries close to the
  inside-segment floor (median |log2 jump| 0.384 against 0.348; no gain 0.629; 2^-b 0.516), and the
  free fit leaves about 0.2 octave unexplained, correlated with a. A line-out recording of a sound
  built from 8-bit samples (e.g. STRINGS, whose attack swells through the codes 5..0) would settle it.
- **What the split lists are** (the descending values below 0x80, 1/8-octave steps of pitch18): not
  needed for the pitch, which they do not change. Probably the interpolator's or a filter's switch
  points by pitch range. Not modelled.
- The post-loop data many samples carry (organ: a decaying tail after a one-granule loop) is never
  played here; the chip may use it as a release segment.

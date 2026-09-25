# Where the noise comes from, and what the DSP split changes

Felipe, 2026-09-25: *"The sound is very noisy in the current state of the driver.
I think that perhaps it could be a good idea to split this PR into two PRs."*

The split was done. This records what the noise measurement found, because the
premise — that the noise is the effects DSP — is not what the captures show.

## The captures have THREE channels, and that matters

The driver instantiates two speaker devices, confirmed by enumerating them in the
running machine:

```
:speaker                             2 ch   the instrument
:fdc:0:35hd:floppysound:output       1 ch   the drive, from .enable_sound(true)
```

`-wavwrite` emits them in creation order, so ch0/ch1 are the instrument and ch2 is
the drive. Reading a "noise level" off the mixed file attributes the drive motor to
the tone generator. The first pass here did exactly that.

## The key bed is not a usable stimulus

Driving all 61 `KEYS` fields leaves the instrument pair **bit-identical** to a run
that presses nothing — the firmware never polls the key FIFO. MIDI in does reach the
tone generator: `-midiin2 test.mid` (the keybed bridge) gives peak −13.7 dBFS
against −50.0 dBFS for silence. `midiin1` works too.

## Measured

| | instrument peak | instrument rms | energy >1 kHz | quietest second |
|---|---|---|---|---|
| driver only (no DSP) | −8.0 dBFS | −26.3 dBFS | **0.00%** | true digital zero |
| with the effects DSP | −13.7 dBFS | −31.5 dBFS | **0.00%** | true digital zero |

**There is no broadband noise in the instrument output of either build.** All the
energy is in 200–1000 Hz, none above 1 kHz, and the gaps between notes are exact
zero rather than a noise floor.

Two real differences the DSP makes, neither of them noise:

- **Without it the output is mono** — L and R are bit-identical. The DSP build
  differentiates them (peak 6755 vs 5828).
- **It is about 5 dB quieter** with the DSP in circuit.

## The one constant signal is the drive motor

Channel 2 carries a steady tone at −53.6 dBFS, **identical with and without notes
and identical in both builds**: 87.7% of its energy in 200–1000 Hz, strongest
components at 459–465 Hz and 225 Hz. Not hiss — a hum. It starts about 5 s after
boot and does not stop within a 30 s run.

That is the floppy spindle. `dor_w` is wired through to the FDC, so this reflects
the firmware leaving the motor enabled rather than a missing motor line. Enabling
floppy sound is ordinary MAME practice — 120 of 269 `FLOPPY_CONNECTOR` users do it.

**If the noise is a constant hum rather than hiss, this is it, and the DSP split
does not touch it.** If it is something else, it is not in these captures, and the
conditions that produce it need to be pinned down before anything is changed.

## Reproducing

```
python3 make_test_midi.py /tmp/test.mid
cd ~/compartilhado/mame-pr-kn7000drv
./kn kn7000 -rompath ~/compartilhado/technics_romsets -skip_gameinfo \
    -nothrottle -str 30 -window -nomaximize \
    -midiin2 /tmp/test.mid -wavwrite /tmp/out.wav
python3 analyse_audio.py /tmp/out.wav
python3 spectrum.py  /tmp/out.wav
```

`play_notes.lua` drives the key bed instead, and is kept only as the negative
control: it is what showed the key bed produces nothing.

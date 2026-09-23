# Why the driver still reads the firmware's voice records

**The question:** the MAME driver reads the firmware's per-slot voice record out
of work RAM to get the musical pitch, at `KN7000_VOICE_RECORDS` and friends. That
is the driver reaching into another device's memory from a distance, and the
standing principle is that if the tone generator's behaviour depends on data X,
and its inputs are register writes, then X is already in the register writes.

So: is the 18-bit value the firmware writes to the TG's pitch register an
absolute musical pitch, or something else?

**The answer, and it is why the dependency survives:** it is a rate index
*relative to the selected wave zone's native playback rate*, not an absolute
pitch. The same MIDI note reaches the TG as a different number depending on which
sample is selected — the probe measures 7.79 semitones of zone offset between the
keybed and an Overture part sounding the same MIDI 55.

```sh
python3 notes/tg-pitch-probes/tg_pitch_is_zone_relative.py \
    --kn7000 <de-interleaved kn7000 program image> \
    --kn6000 <de-interleaved kn6000 program image> \
    --unidasm ~/compartilhado/mame/unidasm
```

**PASS, 2026-09-23** — every check matched. It also confirms the KN6000 record
base `0x5027AF28` appears at 58 sites in the KN6000 image and `0x5027AF1C` (the
KN6500 value) at none: a different build, twelve bytes away, which is exactly why
these cannot be one shared constant.

Arithmetic the probe derives:

    pitch18 at a zone's native rate = (0x4280 + 0x1800) << 2 = 0x16A00
    one semitone = 0x400 in pitch18; one octave = 0x3000 = 12288
    rate = zone_native_rate * 2 ** ((pitch18 - 0x16A00) / 12288)

**What would remove the dependency.** The per-sample root lives in wave ROMs that
have no dump, so the absolute pitch cannot be recovered from the raw index alone.
The register classes that *name* the sample (0x1000/0x1400/0x1800/0x1C00/0x2000,
blitted from the voice shadow at +0x34..+0x44) are on the bus and the driver
currently discards them. Decoding those would let the root be keyed on the sample
identity and the work-RAM read would go. Until then the three constants stay, and
the driver says so rather than claiming the machine offers no other route.

Related: `notes/irq-vector-probes/` — the interrupt vector, reset stack pointer
and SD lamp dependencies from the same block, all of which *were* replaceable.

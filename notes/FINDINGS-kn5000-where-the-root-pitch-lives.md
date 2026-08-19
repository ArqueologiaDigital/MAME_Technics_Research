# Why nothing transfers the pitch constant to the tone generator

Date: 2026-08-19. Written in response to a reasonable objection: *the program ROM has this data,
the tone generator needs it, and you are telling me nothing transfers it — trace the unknown
register fields.* The objection was right to make and the trace was worth doing; the resolution is
that one premise is false.

## The resolution

**The chip does not need the root pitch, so nothing sends it.**

IC303 is told a RATE, in register +0x400, and plays the selected recording at that rate. The pitch
you hear is the recording's own fundamental multiplied by that rate. The recording's native pitch is
never transmitted because it is a physical property of the audio the chip is already reading.

The private full implementation says so in its own words
(`src/mame/matsushita/kn5000_tonegen.cpp:1975-1980`):

> PITCH: driven ENTIRELY by the equal-tempered played note ... via the recording's **measured**
> fundamental period. Advancing the read pointer by that period-derived step makes the recording's
> fundamental recur at exactly the played frequency, so absolute pitch is DECOUPLED from the
> recording's **(un-stored)** native root.

and obtains it by measurement, not lookup (`analyse_chunk` -> `detect_period`, :2093-2101).

So the three parties want different things:

| party | needs | gets it from |
|---|---|---|
| firmware | C, to compute the rate to send | multisample SET descriptors in `table_data` ROM |
| the chip | the rate only | register +0x400 |
| **our minimal HLE** | absolute frequency | **nothing — it has no recording to inherit pitch from** |

Our problem is self-inflicted in the precise sense that it exists only because we synthesise a sine
instead of playing PCM. It is not a gap in the emulation of the hardware.

## What the register trace found anyway (this is the progress)

A full capture of the demo (`tools/rigs/kn5000_tg_burst_capture.lua`, 2071 note-on bursts, 91
selectors) shows the sub-CPU writes **31 distinct registers**, not the 8 the minimal HLE decodes.
Analysed with `tools/kn5000-rootpitch/burst_correlate.py`:

| register | behaviour | reading |
|---|---|---|
| `+0x040` | constant per selector | the selector itself |
| `+0x0C0` | constant per selector, **7** distinct values | a per-recording bank/mode select |
| `+0x4C0` | constant per selector, **2** distinct values | per-recording, binary |
| `+0x840` | constant overall, 1 value (`FF00`) | fixed configuration |
| `+0x140` | **12** distinct per-recording values | per-recording, unexplained |
| `+0x080`, `+0x400`, `+0x880` | vary within a selector | note-dependent, already decoded |

**No register carries a sample address.** That is the structural confirmation: if the chip had to be
told where each recording lives, a high-cardinality per-recording field would exist. There is none,
because the chip resolves the recording itself from the selector through the wave ROM's own
directory.

C has 25 distinct values across the same selectors, so none of the per-recording registers (7, 2 and
1 values) can encode it.

⚠ **A false lead, recorded so it is not re-derived.** `+0x140` initially appeared to track C exactly
on a six-selector sample. Over all 51 selectors it does not: many different C values map to `7F58`,
and C=0 maps to eight different values.

## A live-machine corroboration of the flags bit-1 bug

Independent of the disassembly: the five observed selectors belonging to bit-1 SETs — the ones the
extractor mis-assigns +49/+57 semitones — carry `+0x140` in {`40DD`, `6632`} and `+0x0C0` in
{`7800`, `7F00`}, and both `6632` and `7F00` also occur among selectors whose table C is **0**. The
machine treats them like C=0 recordings, which is what the bit-1 rule predicts.

## What this means for the PR

Two honest sources for C, and only two:

1. **The SET descriptors in `table_data`** — covers all 1444 selectors, and the ROM is one MAME
   already loads and hashes. This is the runtime walk.
2. **Measuring the fundamental from the dumped PCM** — genuinely first-principles, needs no
   firmware data at all, but only works for the ~465 selectors that resolve into IC307. The other
   three wave ROMs are NO_DUMP, and 979 selectors live on IC304 alone.

There is no third source, and there is no formula. The register stream is not one, and now we know
why: the chip was never in the business of knowing what note it was playing.

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

---

# The unknown fields, traced to the instruction

Follow-up, same day, in response to: *trace back where those unknown values come from and how they
are computed; if they are indirectly derived from the ROM data we have a solution, otherwise we
have a better understanding, which is also progress.*

Both outcomes happened. Every one of them IS ROM-derived and processed on the way to the chip --
the thesis was correct -- and none of them carries the multisample root.

| latch | what it is | where the value comes from |
|---|---|---|
| `+0x0C0` | coarse level + expression pair, two 7-bit fields | `hi = clamp(patchrec[+0x0F] + (partrec[+0x0F] - 0x40) + sext(patchrec[+0x66]), 0, 0x7F) << 8`, dropped when `patchrec[+0x12] == 0` or global mode `0x04134C == 6`; `lo = 0x7F` in modes 5/6 else `patchrec[+0x12]`. **Patch/part derived.** `asm:10795-10943`, stores to `0x0451D2` |
| `+0x140` | the SECOND TVF word -- depth / bias | `TVF_Lookup_Depth_Amount(VP[+0x50]) \| TVF_Bias_Clamp_Amount(VP[+0x4F])`; on one route it is a second independent cutoff from `tonerec[+0x13]`. **Voice-patch derived.** `asm:16938-16944`, `:8814-8893` |
| `+0x4C0` | oscillator-config + stream slot | the literal `0x4400` seeded unconditionally by `Voice2_UpdatePitch` (`asm:19192`), OR'd with `(tone_record2[+0x1E] & 0x3300) \| slot` when that byte is non-zero; zeroed at teardown. **Carries no per-recording pitch data** |
| `+0x500` | key-scaled descriptor pair | `hi = clamp(Detune_ScaleUnsigned(tonerec[+0x07]) + PitchBend_Scale(tonerec[+0x12], key), 0, 0x7F)`, `lo = clamp(0x7F + PitchBend_Scale(tonerec[+0x48], key), 0, 0x7F)` -- **both halves are ROM descriptor bytes scaled against the played note.** `asm:9612-9655` |
| `+0x100` | TVF cutoff (already decoded) | `cutoff \| (tonerec[+78] << 13) \| (tonerec[+80] << 10) \| bit7` |
| globals `0x0200-0x0205`, `0x0C00-0x0C05`, `0x0E00` | fixed config, written once at power-up | a 26-byte ROM block at `0x00F8BB`. **None is a ROM base address** -- checked specifically, since a chip-wide wave-ROM base would have had to live here |

So the answer to "the program ROM has the data and nothing transfers it" is: **plenty is
transferred, and all of it is processed rather than copied** -- levels, filter cutoff and depth,
detune and bend scaling, all computed from patch and tone records and clamped before the write. The
one thing not transferred is the multisample root, and now we know why: the chip plays a recording
whose pitch is inherent to its audio, so it is never told what note it is playing.

## ⚠ A defect this turned up in the FULL implementation

`kn5000_tonegen.cpp:1549` tests bit `0x0400` of `+0x100` as a boolean "filter enabled". That bit is
the **low bit of the 3-bit `tonerec[+80]` field** packed at `<< 10`, so the test reads one bit of a
three-bit ROM field and will mis-classify any patch whose field is even. Worth fixing in the
private tree independently of the PR.

## Progress ledger

Explained that were not before: `+0x0C0`, `+0x140`, `+0x4C0`, `+0x500`, and the thirteen global
config words. Confirmed absent: any register carrying a sample address, and any carrying a wave-ROM
base. Confirmed present but useless for pitch: three per-recording constants with 7, 2 and 1
distinct values against C's 25.

---

# ⚠ CORRECTION: descriptor bits DO reach the chip, in +0x080's top three bits

The census above concluded that no register carried per-recording data with enough distinct values
to matter. That was wrong, and the error was one of GRANULARITY: it tested whole 16-bit registers.
`+0x080`'s low twelve bits are the output level and change with nearly every note, so the word
failed a "constant per recording" test while its top three bits were doing exactly that.

`Voice_Build_OutputLevel` (ROM `0x0232C7`, `kn5000_subprogram_v142.asm:15687-15726`) fills
`+0x080` bits[14:12] from the SELECTED ZONE RECORD:

    bit 7 of zone_record[+0x02] SET   ->  field = (zone_record[+0x02] >> 4) & 7
    bit 7 CLEAR                       ->  field = T[folded_note mod 12],  T[n] = floor(2*(n%12)/3)
                                          (a 128-entry u16 table at sub-CPU 0x00FBE4)

That is the same record whose word[0] is the `+0x040` selector and whose word at `stride-2` is C.

**Verified** (`tools/kn5000-rootpitch/reg080_oracle.py`, 2182-burst capture): the override branch
predicts the captured field **196/196 = 100.0%** for selectors mapping to a unique zone record.
The field structure is visible in the data before any code is read -- the low nibble of that byte is
zero across all 1444 records.

⚠ Score only selectors with a unique record. A selector can appear in more than one SET; scoring all
of them reads 204/211 = 96.7% and the seven "errors" are the mapping, not the theory.

## The field audits the shipped pitch table

On the note branch the field pins the note modulo 12, hence C to within a whole semitone, on every
note-on. `tools/kn5000-rootpitch/reg080_note_oracle.py` over the same capture:

* **53 of 67** note-branch selectors agree with the shipped C on every burst.
* **2 are corrected** by a candidate the firmware tables already list, against a generator that
  currently breaks ties by dictionary insertion order:
  `0002` -> 2756 (shipped 0), 64/64 bursts; `508D` -> 3132 (shipped -1408), 24/24 bursts.
* **12 remain open**, needing a whole-semitone offset no listed candidate provides.

## Third line of evidence for the flags bit-1 bug

`tools/kn5000-rootpitch/bit1_bus_test.py`: for the bit-1 selectors the demo plays on the note
branch, dropping the coarse term fits every burst while the shipped value does not.

| selector | shipped C | agrees | with C=0 |
|---|---|---|---|
| `00303C` | 12543 | 12/19 | **19/19** |
| `00303D` | 12543 | 0/1 | **1/1** |
| `00303E` | 12543 | 0/1 | **1/1** |

3 support, 0 contradict. Independent of the disassembly and of the junk-root-byte observation.

## What is still open

The 12 selectors needing an unexplained whole-semitone offset. Two readings, both worth having: the
derived C is a semitone out for them, or a post-fold term (part transpose, bend, master tune) is
active -- it would move `+0x400` without moving this field, since the fold runs first.

⚠ **A dead end, recorded so it is not repeated.** Recomputing C from the zone-record bytes, assuming
the tsv's record column holds bytes `+0x02..+0x05`, gave WORSE agreement than the shipped table.
That is evidence the byte-offset guess was wrong, not evidence about the table. Confirm the record
layout in the disassembly before trying again.

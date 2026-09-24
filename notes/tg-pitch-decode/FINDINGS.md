# Can the TG pitch decode be finished, so the RAM lookup can go? (2026-09-24)

**Answer: no, and not for the reason I first gave.** The register decode is not
incomplete. The lookup is a stand-in for the four **undumped wave ROMs**, and no
amount of decoding the register stream can replace it.

## What was asked

`kn7000.cpp` resolves a note-on's musical pitch by reading the firmware's voice
record out of CPU work RAM at a hardcoded, firmware-build-specific address:

```c
constexpr offs_t KN7000_VOICE_RECORDS = 0x500AF940;
constexpr offs_t KN6000_VOICE_RECORDS = 0x5027AF28;
constexpr offs_t KN6500_VOICE_RECORDS = 0x5027AF1C;
```

That crosses a chip boundary the hardware does not have — a tone generator on a
register bus cannot read CPU DRAM — so the question was whether the note could be
recovered from what the chip is actually told.

## Why it cannot

The firmware's own formula, already reverse-engineered (kn7000.cpp:571 in the
overlay, from the record initialiser at `0x48493D80` and the writer at
`0x4C030FB9`):

    +0x0C u16: notePitch16 = (note<<8) + 0x80 + part transpose + master tune
                             + scale stretch

Three of those four terms — part transpose, master tune, scale stretch — are
firmware state. They never cross the register bus, so no decode of the bus can
recover them.

But that is the smaller reason. The larger one:

**The chip never receives a musical note, and does not need one.** It receives
`p18`, an 18-bit playback RATE, and plays the selected sample at that rate. Rate
becomes pitch only via the sample's own root rate — which lives in the wave ROMs.
All four are `NO_DUMP`:

    c3cbqd000002.ic203  c3cbqd000001.ic204  c3cbqd000004.ic207  c3cbqd000003.ic208

So the driver cannot turn `p18` into an audible frequency, because the constant
that would do it is in a ROM nobody has dumped. It reads the firmware's own
already-computed musical pitch instead. **The lookup substitutes for missing ROM
data, not for missing RE.**

That is a materially different defect from the one I described first ("a shortcut
standing in for undone RE"). The RE is done and documented; the dumps are absent.

## What the measurements actually showed

Four acquisition routes were tried, and each ruled something out rather than
merely failing:

| route | result | what it rules out |
|---|---|---|
| DEMO button | 256 pitch writes, all `p18=0`, 128 slots | the KN7000 demo is a picture slideshow, not music |
| key bed, 61 keys C2..C7 | 256 writes, **0 with a key held** | — |
| FIFO read tap `0x98050004` | **0 reads** vs 12458 TG writes | the firmware never polls the key FIFO in this state, so no key press can become a note |
| rhythm `8 & 16 BEAT` + START/STOP | rhythm screen loads, 256 writes, **0 active records** | the accompaniment did not start either |
| record-array sweep, 16 scans / 180 s | `best nonzero = 0` | the array is never populated in any state reached |
| work-RAM control sweep | `50000000: 250/256`, `500E0000: 256/256`, `500AE000: 20/256`, array span `0/256` | **the reads work** — the empty array is a real observation, not a broken probe |

The control is the one that makes the rest mean anything: memory either side of
`0x500AF940` holds data while the array's own span is empty, so "all zeros" is a
measurement rather than a dead read path.

⚠ What this does NOT show: that the lookup is inert in general. The record is
populated *before the first pitch write of a note*, and no note ever played, so
the empty array is downstream of that. The PR branch is an extract and a machine
that never sounds a note is the wrong tree to measure in.

## A subtlety worth keeping: the KN6000 has TWO record arrays

The overlay's trailing comment says `(KN6000: 0x502858F8)`; the constant in the PR
says `0x5027AF28`. Both appear in the RE and only the second is correct for this
use:

* `0x502858F8` is the **library** array, indexed by note-event element.
* `0x5027AF28` is the per-TG-**slot** copy the firmware makes at note-on
  (`0x48492F20`: `mulu slot,0xB4; add 0x5027AF28`), which is what indexing by slot
  requires. Live-verified: slot 0 -> note 60 pitch16 `0x3C80`, slot 2 -> note 72
  pitch16 `0x4880`.

The PR constant is right. The overlay's trailing comment points at the wrong array
and should be corrected there.

## Recommendation

Keep the lookup, and say what it is. On a `MACHINE_NOT_WORKING` driver whose wave
ROMs are `NO_DUMP`, a documented HLE compromise is defensible; an undocumented
layering violation is not. The comment should say it reads firmware RAM *because
the sample root rates are in undumped ROMs*, so a reader knows it is waiting on a
dump rather than on cleverness.

Deleting it is the alternative and costs pitch accuracy wherever the anchored
fallback (`96.0 + (p18 - 0x1C838)/1024`) is wrong. That trade is measurable — same
audio-hash A/B already harnessed — but it cannot be measured until the machine
plays a note.

## Reproducing

    pitch_decode_probe.lua   DEMO route, records p18/aux/record per pitch write
    scale_probe.lua          keybed route, every row tagged with the key pressed
    rhythm_probe.lua         accompaniment route, keeps only ACTIVE records
    analyse_pitch.py         the fit, with a label-shuffling null control

`analyse_pitch.py` was written before the data arrived, so its criterion could not
be tuned to the answer. It has never been run on a non-empty capture.

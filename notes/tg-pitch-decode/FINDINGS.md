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
the empty array is downstream of that.

⚠ CORRECTION (later the same day): I first blamed the PR extract for this and said
the overlay, which has working audio, was the tree to measure in. **That was wrong.**
Running the identical scale probe on `kn7000_mame_build/kn7000` (2026-09-23, the
overlay) gives the SAME result: 256 pitch writes, 0 with a key held. Whatever state
the firmware needs before it polls the key FIFO, neither build reaches it under this
harness, and the extract is not the cause.

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


---

# Follow-up (2026-09-24): can the anchor be grounded in the KN5000 instead?

Felipe's proposal: if something must be hardcoded, hardcode an estimate of the chip
pitch word (or a formula for it), not the firmware's answer read out of RAM. That is
the right shape -- it keeps `p18` coming from the register bus and confines the
estimate to the genuinely missing data. Three questions followed.

## 1. How does the KN5000 store playback rate -- explicit metadata, or implicit? ANSWERED

Measured from IC307, the one hardware-rooted wave-ROM dump (`crc32 20ff4629`), with
`kn5000_wave_tuning.py`. The parse self-checks: **198 of 198 parameter records
terminate on a bit-7 flag**. (An earlier version ran each record to the next record's
pointer instead of its terminator, swept PCM bytes in as "parameters", and invented
undocumented flags and impossible offsets -- the termination rate is what caught it.)

* **No per-sample base-rate or root-key field exists.** The PCM is recorded at one
  fixed base rate and the chip pitch-shifts from there.
* What IS explicit: key-zone boundaries, and small per-key tuning trims --
  **1177 tuning words across 43 of 198 records, range -16..-1**, overwhelmingly -1
  (628) or -2 (199).

**So the design supports exactly what Felipe proposed: one global anchor plus small
corrections, not a per-sample table.**

## 2. What is the typical pitch value? NOT OBTAINED

Two routes, both empty, and neither is evidence about the hardware:

* **KN5000 register tap** (`kn5000_pitch_probe.lua`, latch 0x100000 / data 0x100002 on
  `:subcpu`): **0 TG writes captured, total.** The tone generator is certainly written
  during boot, so the tap did not fire -- a harness fault, not a measurement. The
  device lookup has a fallback that can also match `:subcpu_latch`.
* **KN7000 scale** on both the PR build and the overlay: 256 pitch writes, 0 with a key
  held, because the firmware never polls the key FIFO (measured: 0 reads of
  0x98050004 against 12458 TG writes).

## 3. The prior RE for the KN5000 pitch encoding does not hold ⚠

`kn5000-vs-kn7000-tonegen-design.md` §4 states the KN5000 computes pitch in
`ToneGen_Calc_Pitch` at 0x03D11F, taking a 16-bit semitone ratio (0x8000 = 1.0x) from
a 12-entry table at 0x01217D. Two independent checks say otherwise:

* The project's own symbol reconciliation renames that routine:
  `0x03D11F  CURATED  ToneGen_Calc_Pitch -> Keybed_Decode_Event`, and flags the old
  name as appearing "only in comments and in symbols/proposals/". It decodes key
  presses, not pitch.
* A **scale-free** search for twelve consecutive words whose ratios follow 2^(k/12)
  (any base, both endiannesses) across the sub-CPU program ROM, both table-data ROMs,
  the sub-CPU boot ROM and IC307 finds **zero** such runs.

That section of the design note is already marked "SUPERSEDED IN PART" for its
envelope verdict; its §4 pitch claim needs the same treatment.

## The open discrepancy this was meant to settle

    driver fallback   96.0 + (p18 - 0x1C838)/1024      -> C7 (MIDI 96) at 0x1C838
    design note §4    "+0x400 per semitone, C4 = 0x0000C838"

At 0x400 per semitone these cannot both hold: C7 = 0x1C838 puts C4 at 0x13838, not
0xC838. They share the digits C838 attached to notes 36 semitones apart, which looks
like a dropped leading 1 plus a mislabelled note rather than two measurements. The
driver's own reading is at least self-consistent -- the KN7000 keybed is C2..C7, C2 =
MIDI 36, so C7 = MIDI 96 really is "the keybed top-C reference".

**Unresolved.** Settling it needs one note-on with a known key, which is exactly what
no route produced today.

## What to do next, in order of cost

1. Fix `kn5000_pitch_probe.lua`'s device lookup (explicit `:subcpu`, assert the tap
   installed) and re-run. The KN5000 is the better subject anyway: it has a real wave
   ROM, so its register value can be checked against sample data.
2. Find what state makes the KN7000 firmware poll the key FIFO at 0x98050004. The
   MIDI bridge feeds the same FIFO, so `-kbdmidi` will not help by itself.
3. Only then decide the anchor. Until it is measured, replacing the RAM read with an
   estimate would swap a documented layering violation for an undocumented guess.

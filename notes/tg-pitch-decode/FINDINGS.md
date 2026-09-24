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

---

# ★ THE DESIGN, DECODED (2026-09-24, from the KN5000 sub-CPU disassembly)

The KN5000's own firmware settles what the pitch register carries, and the KN7000
shares the encoding. This is what makes a chip-boundary-respecting implementation
possible.

## The register carries an ABSOLUTE LOG PITCH

`kn5000_subprogram_v142.s:7262`, from the staged per-voice register block:

    0x0451DA -> +0x400   absolute log pitch          (Pitch_Emit_Reg400)
    0x0451CE -> +0x040   recording selector, (class << 12) | entry

and the same file states the firmware never walks the wave ROMs at all --
"IC304-IC307 hang off IC303 and are in no CPU's address space", with a traffic
census over the whole payload to back it. The chip resolves the sample AND its
tuning itself. The CPU sends a pitch and an index; that is the whole interface.

## The value is built by ADDITION in a log domain

`Pitch_Emit_Reg400` (0x023A4A):

    +0x400 = saturate15( (rec+0x0A) + [0x041347]          ; global fine tune
                                    +/- (rec+0x23)->[0x1D] ; detune, optional
                                    + [0x04135A] )         ; glide, conditional

    (rec+0x0A) = (rec+0x06) + [0x293E] + (rec+0x17)->[0x05]*2
                            + (rec+0x27)->[0x21] + (rec+0x23)->[0x14]

Every term is additive, so note -> register is affine.

## The units are 8.8 SEMITONES, and keys map as key*256 + 0x80

`Pitch_Fold_Octaves_Into_Range` (0x006059) says it outright:

    In: WA = signed 16-bit pitch (8.8 semitones), C = low key limit, E = high key
    limit. Adds or subtracts 0x0C00 (twelve semitones) until the value lies inside
    [C*256+0x80, E*256+0x80].

256 units per semitone; a key K sits at `K*256 + 0x80`. The fine-tune stage confirms
it independently: signed semitone bytes are `exts` then `sla 8` before being added.

**This is the KN7000's encoding too.** Its firmware's `notePitch16 = (note<<8) + 0x80`
is the same 8.8 form, and the constant `0x4280` that the KN7000 driver calls "the
formula constant" for unpitched drums is the KN5000's literal `ldw iz, 0x4280`
snap-to-centre value -- note 0x42 = 66 with the +0x80 half-step. Same family, same
constant. The KN7000's chip register is 1024/semitone, exactly 4x finer.

## ★ WHAT THE WAVE ROM IS ACTUALLY NEEDED FOR: THE OCTAVE, AND ONLY THE OCTAVE

The pitch written to the chip is the musical pitch **folded by a whole number of
octaves** into the sample zone's key range, and it is folded only "when a sample zone
cannot cover the played key". The zone limits are wave-ROM data -- precisely the
key-zone boundary words measured in IC307 (flags 0x00 / 0xC0, low byte = MIDI key).

Consequences for a driver with NO_DUMP wave ROMs:

* **pitch class (note mod 12) is EXACT** from the register alone;
* **the octave is ambiguous** by an integer number of octaves, and resolving it needs
  the zone limits, i.e. the dump;
* an octave-wrong note is therefore the EXPECTED failure mode, not a sign of a broken
  decode. `notes/kn7000-demo-playback-status` already records "P10 ~octave sharp".

That is a far smaller gap than "the pitch is unrecoverable", and it is the whole
justification for dropping the RAM read: the register gives everything except an
integer octave, and the RAM read was buying exactly that one integer.

## Implementation this licenses (no chip-boundary crossing)

    note_x256 = (p18 - ANCHOR) * 256 / 1024        // chip constants only
    // octave fold is a wave-ROM property; with the ROMs absent, assume the zone
    // covers the played key (no fold) and accept an octave error on zones that
    // would have folded.

The only hardcoded numbers become the chip's scale (1024 units/semitone, measured)
and its anchor -- properties of the tone generator, not addresses in someone's
firmware build. ANCHOR is still unsettled: the driver's fallback implies 0x4838
(from `96.0 + (p18-0x1C838)/1024`), the design note's "C4 = 0x0000C838" implies
something 28 semitones away, and no note-on with a known key was captured to decide.
Taking the driver's existing value changes nothing audible today, because it is
already what every voice uses (the record array is empty in every reachable state).

## The falsifiable prediction

The record array was measured empty in every state reachable in either build, so
`tg_pitch_resolve`/`tg_type_resolve` always return -1 and the fallback always runs.
**Deleting both RAM reads must therefore leave the audio hash bit-identical.** If it
does not, the measurement was incomplete and the deletion is not safe.

---

# ✅ IMPLEMENTED AND VERIFIED (2026-09-24)

The register-only decode is folded into the two commits that own the code, so no
commit in the PR stack ever contains the layering violation.

**Removed:** `KN7000_VOICE_RECORDS` / `KN6000_VOICE_RECORDS` / `KN6500_VOICE_RECORDS`,
`m_tg_recbase`, `m_tg_one_chip`, `m_tg_pitch_cls`, `m_tg_pitch_mask`, `tg_slot()`,
`tg_pitch_resolve()`, `tg_type_resolve()`, and the two out-of-band parameters of
`tg_write()` -- which now reads

    virtual void tg_write(int tg, uint16_t addr, uint16_t data) = 0;

so the device cannot be handed anything the chip is not given.

**Kept:** the register-only decode, documented with what the KN5000 settled --
absolute log pitch, 0x400 units per semitone, octave-folded into the sample zone's
range by the firmware, so the pitch class is exact and only the octave depends on the
undumped wave ROMs.

## The prediction held

The record array was measured empty in every reachable state, so the resolves always
returned -1 and the fallback always ran. The prediction was therefore that deleting
them leaves the audio bit-identical:

    before (pre-pitch-fix)      wav md5 5d45998db116   7200050 bytes
    after  (register-only)      wav md5 5d45998db116   7200050 bytes

Identical. The RAM read was carrying no behaviour -- only risk.

## Two process failures worth recording

1. **The rebase conflicts were not mechanical.** The effects-DSP commit legitimately
   reroutes the tone generator through `m_dspbridge`; resolving with "ours" wholesale
   would have silently reverted that. Each conflict had to be read.
2. **An over-greedy resolution deleted nine DSP member declarations.** The assertion
   checked that the conflicting hunk *contained* the resolve code, not that it
   contained *only* it, and `m_dsp_index`..`m_dsp_running` sat in the same hunk. The
   build caught it -- but a build only catches deletions that break compilation. The
   check that catches the rest is

       git diff pre-pitch-fix technics-kn7000-driver -- src/mame/matsushita/

   read for removals unrelated to the intended change. Worth running after every
   stack surgery, not only when something fails to compile.

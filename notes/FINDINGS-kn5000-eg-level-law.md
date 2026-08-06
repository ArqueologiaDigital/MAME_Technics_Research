# The EG level law, from the fader tables

2026-08-06. Follows the organ-envelope investigation (`8a5ed73`, blog part 129).
Both tables dumped from `kn5000_subprogram_v142.rom` and analysed. **Structure solved; the
absolute dB-per-code slope is NOT determined, and I am not going to guess it.**

## The tables

    PeakLevel_Fader  sub-CPU 0x011899  (file offset 0x2999)
    Level_Fader      sub-CPU 0x0118FE  (file offset 0x29FE)

101 entries each (index 0..100), monotonic NON-INCREASING, `[0] = 0xFF`,
`Peak[100] = 0x09`, `Level[100] = 0x04`. **Index is an ATTENUATION percent** — higher index
gives a LOWER level code.

## Three exact structural facts (MEASURED)

1. **`code = 234 - 2*index`, EXACTLY, over index 21..94.** A least-squares fit returns
   234.000 and -2.000, and reproduces `Level_Fader[60] = 114 = 0x72` exactly — the very code
   that makes the organ collapse. Two code units per percent.
2. **`Level_Fader = PeakLevel_Fader + 20`, EXACTLY, over index 18..94.** The two tables are the
   same curve offset by a constant 20 code units. So PEAK and SUSTAIN really are on one scale
   (this closes the standing uncertainty), and 20 codes is a FIXED acoustic ratio between them.
3. Both curves are COMPRESSED outside that body — index 0..17 and 95..100 — so the linear form
   is the working range, not the whole table.

## What this does NOT settle

The tables map **index <-> code**. They do not map **code -> gain**. So they give the SHAPE of
the law and its linear region, but not the dB per code unit. Three candidate readings, and the
data rules against all three:

| law | gain(114) organ sustain | gain(206) piano | verdict |
|---|---|---|---|
| current `2^((L-255)/16)` | 0.0022 (-53 dB) | 0.12 (-18 dB) | ✗ organ inaudible — the bug |
| linear `L/255` | 0.447 (-7.0 dB) | 0.808 | ✗ MEASURED: piano peak pinned at 32768, 0.56% clipped |
| fader-as-linear-amplitude, `gain = (code-34)/200` | 0.40 (-8.0 dB) | 0.86 | ✗ LOUDER than L/255 at the piano's level, so it clips worse |

★ **The trap this exposes.** Every law that lifts the organ's code 114 to a musical level also
lifts the piano's code ~206, and the piano is ALREADY at the clipping edge. Fixing the EG law
alone cannot be right — a compensating factor has to exist elsewhere in the chain. The obvious
candidate is the `sample * env_level / 0xFF` multiply, whose own comment says it is
"Known to be the WRONG reading and deliberately retained". **The next pass should treat the EG
law and the env_level multiply as ONE joint calibration, not two independent fixes.**

## The measurement that would settle it

The 20-code Peak/Level offset is a fixed ratio in whatever domain the codes live. If a slope
`m` dB/code is correct, that offset is `20m` dB:

    m = 0.188 -> 3.8 dB     m = 0.376 (current) -> 7.5 dB
    m = 0.300 -> 6.0 dB     m = 0.500 -> 10.0 dB

So: **find what the firmware's own UI or documentation says the peak-vs-sustain relationship is,
or find the consumer of these tables and read what it does with the result.** One known ratio
pins `m`, and `m` plus the exact linear form above gives the whole law with no fitting.

Second, cheaper route: the SUST class parks at code 242 and the CLICK class at 114, and both
were measured in the same capture. Their true gain RATIO is one number that any correct law must
reproduce — but it must be measured from a window that does not straddle the 1.9 ms attack (the
earlier 0.812 figure for the SUST class does, which is why it disagreed with its own prediction).

## Do not repeat

The organ's decay tail rising is NOT evidence for a law — it follows arithmetically from raising
gain(114) by any amount at all. The piano's HEADROOM is the criterion that can actually fail, and
it is the one that killed the linear law.

---

# 2026-08-06 (later) — the law is DERIVED and UNCHANGED; the defect is a missing register

Routes 1 and 2 of the plan above were both run and both produced hard results. **Neither
produced a change to ship.** The law that ships, `gain(L) = 2^((L-255)/16)`, survives — but it
is no longer resting on an unproven transfer, and the reason the organ class is 50 dB down is
now located somewhere else. Route 3 (fitting a slope) was NOT used and would have been wrong:
the derivation forbids a free slope.

Vehicle for everything below: sub-CPU image `kn5000_subprogram_v142.rom` (load base 0x00EF00),
plus a live raw-bus trace of both demos (`tools/kn5000_tgbus_trace.lua`, PCM mode, AREA = 2,
private cfg + nvram per run, `-seconds_to_run 36`, window t = 30.0–34.0 s).

## ROUTE 1 — the consumer of the fader tables. The transfer is VALID.

Chain, MEASURED end to end:

```
Voice_Calc_LevelPair_EGA  0x026769
    i  = clamp( paramA[+0x2D] + (int8)tonerec[+0x6C], 0, 100 )
    IZ = Level_Fader[i]                                             ; 0x0118FE
    if tonerec[+0x0A] bit0 and !(slot[+0x01] bit8):
         IZ = min( IZ, Level_Fader[ LevelCap[ tonerec[+0x18] ] ] )  ; cap 0x011ADF
    if paramA[+0x35] != 0: IZ += Pan_ScaleWithVelocity(...); clamp 0..255
    (IZ<<8)|0x80 -> 0x0451F8      (IZ<<8) -> 0x0451FA
scratch base = 0x0451CC, so those are scratch +0x2C and +0x2E
ToneGen_WriteLevelPair  0x02D50E   and   ToneGen_WriteLevelBurst 0x02D436
    both called with XBC = 0x0451CC (asm L21533, L30279, L30364, L30390)
    scratch+0x2C -> IC303 register +0x800      scratch+0x2E -> +0x840
```

**So a Level_Fader output byte IS the +0x800/+0x840 level byte.** The "unproven transfer" that
the section above called the root defect is not a defect: peak/sustain codes and fader codes
live in one domain, and that is now traced register-by-register rather than assumed.

`Voice_Calc_LevelPair_Full` reaches the same registers by the other road: 0x0451E4/E6/E8 =
scratch +0x18/+0x1A/+0x1C, and `ToneGen_WriteVoiceParams` (0x02D...) maps +0x18/+0x1A/+0x1C ->
+0x800/+0x840/+0x880. Its table is `PeakLevel_Fader` 0x011899. Both fader tables land on the
amplitude EG.

### Three lanes, not one — and lanes B/C are probably NOT amplitude

`Voice_Calc_LevelPair_EGB` (0x026975) and `_EGC` (0x026AAA) are the SAME routine on different
parameter bytes — `paramA[+0x0F]` and `paramA[+0x45]` — writing scratch +0x30/+0x32 and
+0x34/+0x36, i.e. **+0x900/+0x940 and +0x9C0/+0xA00**. The 22-word burst gives each lane three
segments (+0x800/840/880, +0x900/940/980, +0x9C0/A00/A40). The HLE models lane A only.

Tempting, but the bus says NO: MEASURED at a piano note-on, lane C runs `FF00 / 44E8 / 34B0`
(255 -> 68 -> 52 with real rates) while lane B holds flat at 174; at the organ's 0x727F class,
B and C are both flat `FF00`. A lane that opens and closes on the piano and does nothing on the
organ is a brightness envelope, not a second amplitude. **The organ's missing loudness is not
in lanes B/C.** (INFERRED, not settled — worth a separate pass.)

### Direction: LARGER CODE = LOUDER (two independent proofs)

1. The cap is `IZ = min(IZ, cap_value)` **in the code domain** (`cp wa,iz; jr gt,skip; ld iz,wa`,
   0x0267DD region, and outright in `Voice_ComputeVolume_CappedLFO`). A minimum is a loudness
   *ceiling* only if a larger code is louder.
2. MEASURED on the bus: every one of 117 piano note-ons is programmed peak 199..248 and then
   decay-1 target 12..140. A piano does not get louder after its attack.

⚠ This **refutes a comment in the current disassembly**: `Voice_InitVoiceState`'s
"0x0451E4 = 0xFF7F (register pair 1 = maximum attenuation, maximum rate — i.e. silent)" is
backwards. 0xFF7F is *full level at the fastest rate*. The same mislabel is echoed wherever
0xFF00/0xFF80 is called a "hard mute".

### And the domain is logarithmic

Every consumer combines level codes by **addition of signed trims followed by a 0..255 clamp**
(EGA/EGB/EGC velocity term, `Voice_Calc_LevelPair_Full`'s LFO + depth terms,
`Voice_Build_OutputLevel`'s three tonerec/slot terms). Addition in the code domain is
multiplication in the gain domain. MEASURED, and it rules out any linear-amplitude reading of
the byte on its own.

## ROUTE 2 — the +0x080 table at 0x010764. This is where the derivation actually comes from.

Re-verified from the ROM, independently of the earlier claim: **256 of 256 entries** are
bit-exactly

    T[i] = round( 128 * log2( 2^(i>>4) * (1 + (i&15)/16) ) )

`T[255] = 2042`, the firmware writes `T[i]*2 = 4084`, and the destination field is 12 bits
(max 4095). The byte's whole range exactly fills the register's whole range.

**What was missing before, and is the point of this pass: what feeds that table.** The previous
derivation asserted "a level converter" without identifying the input, and that is precisely
the step the section above called the root defect.

```
Voice_Build_OutputLevel  0x0232C7            (verified by disassembling the bytes, not the .s)
    BC += tonerec[+0x0C] ; BC += tonerec[+0x10] ; BC += slot[+0x33]
    WA = BC ; calr 0x0232B3                  ; SIGNED clamp to 0..255
    BC = HL*2 ; WA = word at 0x010764+BC ; WA += WA
    OR in pan bits 14:12 and bit15 ; LD (0x0451D0),BC
0x0451D0 = scratch+0x04 -> IC303 register +0x080
entered by tail-jump (JRL, which is why a call-scan found no caller) from
    Voice_ApplyPortamento  0x026637   and   Voice_ApplyPortamento2 0x026684, BC = slot[+0x0D]
```

**`slot[+0x0D]` is a LEVEL, and `Voice_ComputePitch*` / `Voice_ApplyPortamento*` /
`Voice_Build_OutputLevel` are the per-voice OUTPUT-LEVEL chain. The current disassembly's
"pitch"/"portamento" names are mislabels.** Four independent reasons:

* `Voice_ComputePitch_Mono` (0x026533) builds it as `((curve[..] - 0xD0) * depth) >> 5 + 0xD8`
  plus small signed terms — a value centred on **0xD8 = 216**, inside the 0..255 clamp.
  (Disassembled: the trailing `add HL,(0x2940)` is a MEMORY operand at 0x2940, not a `+10560`
  immediate; the .s rendering `addda16 xiz, 10560` reads as an immediate and is misleading.)
* `Voice_ApplyPortamento`'s `paramA[+0x17] == 0 -> SUB DE,0x200` branch drives the result
  negative so the clamp returns 0. A detune cannot mute a voice; a **channel volume of zero**
  must. Non-zero values add `paramA[+0x17] - 100`, a bipolar ±100 trim about 100.
* A 15-bit pitch already has its own path: `Pitch_Emit_Reg400` saturates to 15 bits and stores
  to 0x0451DA = scratch+0x0E = **+0x400**, the register `ToneGen_WriteVoiceParams` documents as
  the absolute log pitch. Pushing a 15-bit pitch through a 0..255 clamp would saturate on every
  note.
* The additive trims are the same add-and-clamp idiom the fader-table level codes use.

### The law, DERIVED

The table's input is a level code in 4-bit-exponent / 4-bit-mantissa float form and its output
is that value's exact log at 128 counts/octave (doubled to 256 counts/octave for the register).
Therefore

    gain(L) = F(L)/F(255),   F(i) = 2^(i>>4) * (1 + (i&15)/16)
            = 2^((L - 255)/16)   to within 0.086 dB

**0.37629 dB per level count · 16 counts per octave · 96.33 dB across the byte.** Non-circular
cross-check: 12-bit field ÷ 256 counts-per-octave = 16 octaves = 96.3 dB = the same span, and
the table's doubled maximum (4084) fills 4095. The byte and the field are two encodings of one
96 dB domain.

**Residual gap, stated exactly.** This derives the slope for the **+0x080** byte. That the
**+0x800** byte uses the same scale remains an INFERENCE: one chip, one level encoding, both
8-bit, both built by the same add-trims-and-clamp idiom, both 0..255. I looked for a routine
that puts one register's byte into the other's chain and there is none. What has changed is
that the inference is now between two *level* registers of the same chip instead of between a
level register and an unidentified one.

### An open corroboration (do not cite as proof)

Table **0x011C96** is `round(32*log2(i)) + 31` — exact at every power of two (31, 63, 95, 127,
159, 191, 223, 255: every doubling of the input adds exactly 32) and ±1 elsewhere, 128 entries.
It converts a linear 7-bit control into a level code at 32 counts per doubling of that control.
At 16 counts/octave that is `gain ∝ input²` — the standard square law. At 32 it would be linear
in the control, which nothing uses. But its index is `slot[+0x0C] & 0x7F`, which the current
disassembly calls the note, and if it really is a note this says nothing about velocity or
volume. Resolve `slot[+0x0C]` before promoting this.

## The premise needs correcting: the organ demo is the one that CLIPS

MEASURED, current tree, PCM, t = 30–34 s, both speaker channels:

| demo | rms | peak | clipped samples (4 s) |
|---|---|---|---|
| **organ** | **10017** | **32768 (pinned)** | **302** |
| piano | 3421 / 3362 | 22517 | 0 (3.3 dB headroom) |

The organ demo is **9.3 dB LOUDER** than the piano and it is already the one at the rail. What
is 50 dB down is a *class of voices inside it* (`+0x840 = 0x727F`), not the demo. Any statement
of the form "the organ is inaudible" should be qualified to that class from now on.

Programming, MEASURED from the raw bus over the same window (310 organ / 117 piano note-ons):

| | +0x080 code | lane-A peak | lane-A sustain | decay-1 rate |
|---|---|---|---|---|
| organ | 167.4 ± 25.2 (134..239) | 247.2 ± 16.8 | 121.6 ± 31.1 | 127 in 196/310 |
| piano | 206.2 ± 17.9 (164..234) | 222.0 ± 13.1 |  70.4 ± 35.2 |  76 in 68/117 |

The attack rate is 127 in **310/310 and 117/117** note-ons, which independently confirms
LAW (b)'s "127 = fastest" — a universal attack rate is only sensible as *immediate*.

## Why no re-slope can be the fix, restated with the new numbers

The organ class sits 128 counts below the loud class. Closing that with a slope needs
0.047 dB/count (128 counts/octave), and the 0x010764 table is bit-exact at 16 counts/octave, so
that slope is refuted by the ROM. **The slope is not the free parameter.** The free parameter is
the REFERENCE — which code maps to full scale — and that is chip gain-staging, which is not in
the firmware at all (the same class of unknown as `eg_rate_to_step`'s `T127`).

## The concrete defect found instead: the HLE does not read +0x080

`data_w()` uses +0x080 only as a burst strobe (`if (group==0 && bank==2 && (data & 0x8000))
resolve_waveform(ch);`). It is a per-voice OUTPUT LEVEL carrying 39 dB of spread in the organ
demo and 26 dB in the piano demo, and every voice is currently rendered as if it were constant.
That is a defect independent of the law question, and it is the "compensating factor elsewhere
in the chain" the previous section was looking for.

Weak supporting observation, reported as weak: between the two demos, +0x080 alone differs by
39 codes (14.6 dB) and lane-A peak by 25 codes (9.5 dB), but their SUM differs by only 13.6
codes (5.1 dB) — 414.7 ± 25.5 versus 428.3 ± 21.7. Within a demo the correlation is weak
(r = −0.32 organ, −0.05 piano). **One comparison of two demos is a hint that the two registers
multiply, not a proof**, and it must not be quoted as one.

## Verdict

Routes 1 and 2 both succeeded as investigations; neither yields a change to ship. The shipped
law is unchanged and is now DERIVED rather than transferred. **No code was touched and no law
was committed.** A fitted slope was deliberately not produced.

## What is still missing, in order

1. **Model +0x080.** `gain *= 2^((code080 - 255)/16)`, with `code080` recovered from the 12-bit
   field by inverting 0x010764 (or, equivalently, `2^(field/(256*... ))` straight from the log
   value — the field IS the log, so no inversion is needed: `gain080 = 2^((field - 4084)/256)`).
   This makes everything quieter, so it must land together with the reference in step 2, and
   the piano headroom (peak 22517, 0 clipped, 3.3 dB) is the number that must not get worse.
2. **The reference.** One free constant `R` such that `gain = 2^((code080 + codeEG - R)/16)`.
   It is gain-staging and cannot be derived from the ROM. **The experiment that settles it is
   twenty minutes on Felipe's real KN5000:** hold one PIANO note at maximum velocity, record the
   line output, and report its peak relative to the instrument's own clip point; the register
   codes for that note are already readable from the firmware, so one measurement gives `R`.
3. **Lanes B and C** (+0x900/940/980, +0x9C0/A00/A40) — establish what they modulate before
   assuming anything. The piano's lane C (255 → 68 → 52 with rates) versus the organ's flat 255
   is the discriminating pair already in hand.
4. **Fix the disassembly names.** `Voice_ComputePitch`, `Voice_ComputePitch_Mono`,
   `Voice_ApplyPortamento`, `Voice_ApplyPortamento2` are the output-level chain, not a pitch
   chain; `Voice_InitVoiceState`'s "maximum attenuation ... silent" comment is inverted. These
   mislabels are what made the 0x010764 derivation look unsupported in the first place.

---

# 2026-08-06 (later still) — the GATE-LATCH hypothesis is REFUTED, and the click has TWO causes

Felipe, on real listening: *"I still hear lots of clicks in place of notes [in SINE mode],
even though there are also notes playing OK. The PCM mode sounds a bit better."*

The hypothesis under test: **the HLE re-reads the EG segment register at each segment hop
instead of latching all three at the note-on gate**, so `load_eg_segment()`'s
`v.regs[20 + seg]` picks up a word the note never had. Its premise was that the sub-CPU
rewrites `+0x840` about **2 ms** after the gate, i.e. after the EG has already hopped.

**REFUTED.** The premise is wrong by three orders of magnitude, and rendering the latching
arm fails the clipping gate in three of four capture conditions.

Vehicle: one binary, two experiment switches added for this pass (`KN5000_EGSEG=gate`,
`KN5000_LVL080=on`), both default OFF. **Null control: with neither set, the organ-PCM WAV
is md5-identical to the pre-change tree (`241e3dc4a88fe510a8a8565024e650e5`), and every arm
logs the same note-on count (1828 organ / 667 piano), so the switches perturb no firmware
behaviour.** Captures: `tools/kn5000_capture_perf.sh {organ,piano} {pcm,sine} … 45`,
private cfg + nvram, AREA = 2; mix statistics over t = 30–34 s.

## 0. FIRST, A DETECTOR THAT CAN ACTUALLY SEE IT — `tools/kn5000_collapse_detect.py`

The old step detector (`|x[n]−x[n−1]| > 8000`) needs a fundamental above ~21 kHz to fire on
a 16384-peak sine, so "sine mode has zero clicks" was a null that could not fail. The
replacement is a RATIO inside one voice, taken from the notelog's own 10 ms envelope
profile: **attack peak over 0–20 ms versus the peak from 30 ms to key-up, and it only counts
buckets in which the key was still DOWN**. A note that was ASKED to stop is `SHORT`, not a
click; a voice that never reached −30 dBFS at all is `INAUDIBLE` (a missing note, a
different defect) rather than a click.

**It discriminates, and it can come out both ways** (organ, PCM *and* sine, identically):

| register class | n | click fraction |
|---|---|---|
| segment-1 decay target 114 (`0x727F`) | 831 | **0.827** |
| hand-off word = 0 | 738 | 0.248 (PCM) / 0.053 (sine) |
| never left segment 1 | 193 | **0.000** |

**It fires at sine level**: the sine-mode CLICK class has a median attack peak of 9917 and a
median tail/attack of **−49.5 dB**. And it is not knife-edge — the count is *identical* for
collapse thresholds of 12, 18, 24 and 30 dB (the distribution is that bimodal), and moves
only 833 → 921 across a 10x sweep of the audibility floor (328 → 3277 LSB).

## 1. FELIPE'S REPORT, REPRODUCED AND QUANTIFIED

Per note-on, t ≥ 22.6 s:

| demo | mode | note-ons | CLICK | INAUDIBLE | OK |
|---|---|---|---|---|---|
| organ | pcm  | 1762 | **870 (49.4 %)** | 539 | 161 |
| organ | sine | 1762 | **726 (41.2 %)** | 696 | 161 |
| piano | pcm  |  601 |   24 (4.0 %) | 221 | 348 |
| piano | sine |  601 |   36 (6.0 %) | 211 | 346 |

**"The PCM mode sounds a bit better" is real but small, and it is not fewer clicks.** Sine
turns 157 MORE organ note-ons completely inaudible (696 vs 539) and produces 50 % more piano
clicks (36 vs 24); the OK count is identical (161 organ, ~347 piano). Sine mode trades clicks
for silence. Neither mode is close to clean, which is what Felipe said.

## 2. TWO MECHANISMS, NOT ONE — and they split cleanly

Attributed from the same rows. The split is **identical in both render modes**, which is what
"the symptom appears in both modes" actually means:

**(a) `eg-target-114` — 687 clicks, the SAME 687 in PCM and in sine.** Median attack peak
17392 (PCM) / 9917 (sine), median tail/attack −49.5 dB. These are the voices programmed
`+0x840 = +0x880 = 0x727F` — decay to level 114 at rate 127 and hold there. Under the derived
law that is −53.06 dB, reached 5.3 ms into the note.

**(b) `handoff-0` — the group0/bank0 hand-off word carries magnitude 0.** MEASURED: it
arrives **37–41 µs after the gate** (median 0.037 ms organ / 0.041 ms piano, 738/738 and
179/179 note-ons), and `sample * env_level / 0xFF` then mutes the voice outright.
**These are overwhelmingly MISSING NOTES, not clicks**: median whole-note peak 35 (organ PCM)
and 1 (organ sine), so 539 of 738 land in INAUDIBLE. Only 183 (PCM) / 39 (sine) get loud
enough first to be heard as a click. This is the known "the two defects cancel" reading of
the hand-off word (see `data_w()`), now sized: **it accounts for 42 % of the organ demo's
note-ons and 30 % of them being silent.**

## 3. THE HYPOTHESIS, TESTED TWO WAYS. BOTH REFUTE IT.

### 3a. The raw bus says the registers are final 1100x before they are read

Re-analysed from the trace the previous pass took (`tools/kn5000_tgbus_trace.lua`, both
demos, t = 30–31 s), measuring gate-to-write latency per note-on rather than eyeballing a
burst:

| write | organ (310 gates) | piano (117 gates) |
|---|---|---|
| `+0x840` after the gate | median **3.0 µs** (p10 3.0, p90 4.0, max 4.0) | median **3.0 µs**, max 4.0 |
| `+0x880` after the gate | median **6.0 µs**, max 7.0 | median **6.0 µs**, max 7.0 |

Misses: 0/310 and 0/117. The EG's own hops, from the notelog, are at ~3.4 ms (0→1) and
~5.3 ms (1→2). **The word is in the register roughly 1100x earlier than the moment
`load_eg_segment()` reads it.** The "2 ms" in the hypothesis is the HOP time, not the WRITE
time; the two were conflated.

Worse for the hypothesis: **`+0x840` reads `0xFF00` at the gate in 310/310 and 117/117
note-ons** — level 255 at rate 0, i.e. HOLD. Latching at the gate does not recover a lost
value; it freezes segment 1 on the *pre-mute placeholder* and **discards the entire decay
program the firmware writes 3 µs later.**

### 3b. Rendering it: it removes the EG clicks by holding every voice at its attack peak

`KN5000_EGSEG=gate`, same four conditions (peak / rms / clipped samples per channel over
4 s, from the speaker mix):

| arm | CLICK | peak | rms | clipped | headroom |
|---|---|---|---|---|---|
| organ pcm  base | 870 | 32767 |  9534 |    25 (0.00013) | 0.00 dB |
| organ pcm  **latch** | 578 | 32768 | 20204 | **29584 (0.15408)** | 0.00 dB |
| organ sine base | 726 | 31429 |  5816 |     0 (0.00000) | 0.36 dB |
| organ sine **latch** | 159 | 32768 | 16732 | **8467 (0.04410)** | 0.00 dB |
| piano pcm  base |  24 | 23048 |  2550 |     0 | 3.06 dB |
| piano pcm  **latch** | **42** | 26539 |  6293 |     0 | 1.83 dB |
| piano sine base |  36 | 25455 |  5272 |     0 | 2.19 dB |
| piano sine **latch** |   0 | 32767 | 11723 | **24 (0.00013)** | 0.00 dB |

* **The clipping gate FAILS in 3 of 4 conditions**, by a factor of 1180x on the organ in PCM.
* **The piano gets WORSE in PCM on its own click count** (24 → 42): holding voices at peak
  makes previously-inaudible hand-off-muted voices loud enough to be heard as clicks.
* It does exactly what §3a predicts: `eg-target-114` clicks go **687 → 0** and the median
  attack peak of the OK class goes 18483 → **32083** — every voice parked at the rail.
* The `handoff-0` clicks are not touched at all (they become the *only* mechanism left:
  578/578 and 159/159), because they are not an EG effect.

**Verdict: REFUTED.** The premise is false on the bus, and the arm fails the agreed gate.
Left in the tree as `KN5000_EGSEG=gate` so the next person does not have to re-derive it.

## 4. THE +0x080 DEFECT IS REAL, BUT IT CANNOT BE THE COMPENSATING FACTOR — by construction

Tested separately, `KN5000_LVL080=on`, `gain = 2^((field − 4084)/256)`:

| arm | CLICK | INAUDIBLE | peak | rms | headroom |
|---|---|---|---|---|---|
| organ pcm base | 870 |  539 | 32767 | 9534 |  0.00 dB |
| organ pcm **+0x080** |  66 | **1506** |  9885 | 1330 | 10.41 dB |
| organ sine **+0x080** |  23 | **1662** |  5428 | 1500 | 15.62 dB |
| piano pcm **+0x080** |   0 |  **381** |  5697 |  567 | 15.20 dB |

The click counts collapse only because 85–94 % of the programme becomes inaudible: rms falls
17.1 dB (organ) and 13.1 dB (piano). That is the missing gain-staging reference `R`, exactly
as step 1 of the previous section predicted, and it is why this is not shippable alone.

**But the decisive point is structural.** MEASURED on the raw bus, per note-on:
`+0x080` is written **exactly once inside the note's rendered life — 31 µs after the gate**.
A second write exists for 246/310 organ and 53/117 piano notes, but at a median of **827 ms**
(organ) and **2062 ms** (piano), p10 = 435 ms — i.e. after the 240 ms profile window in over
90 % of cases, and after the organ's own median key-up at 107 ms. **A gain that is constant
across a note cannot change any ratio inside that note**, and the collapse is precisely such
a ratio. Confirmed rather than assumed: over the 60 piano notes that align between the two
arms, the tail/attack ratio shifts by a median of **+0.003 dB** (p10 −0.008, p90 +0.016,
max |shift| 0.861 dB).

So `+0x080` is a real defect worth fixing for the *balance* between voices — it is not a
candidate explanation for the click.

## 5. AND NO RE-SLOPE CAN RESCUE THE ORGAN EITHER — a fresh bound, from this capture

Take the law as `gain(L) = 2^((L − 255)/s)`, `s` = level counts per doubling (`s = 16` today,
bit-exact from table 0x010764 for the `+0x080` byte; that the `+0x800` byte shares the scale
is still the standing INFERENCE). Raising `s` lifts every level by
`6.0206·(255 − L)·(1/16 − 1/s)` dB. MEASURED here:

* piano attack level: median 218, p90 240 → 37 / 15 counts below full scale;
* piano headroom: **3.06 dB** at peak 23048, 0 clipped samples;
* organ peak → sustain: median 255 → 114 = **141 counts**.

The piano hits the rail at **s ≤ 20.5** (median proxy) or **s ≤ 34.9** (p90 proxy). At those
slopes the organ's 141-count drop still measures **41.4 dB** and **24.3 dB** — above the
detector's own 18 dB collapse threshold in both cases. Bringing the organ within 12 dB needs
s ≈ 71, which makes the piano 10.8 dB louder (peak ≈ 79 700, i.e. 7.7 dB into the clipper).

**This criterion could have failed**: had the piano's headroom admitted s ≥ 71, a re-slope
would have been the answer. It does not. The free parameter is still the REFERENCE, not the
slope — and it is chip gain-staging, which is not in the firmware.

## 6. WHAT THE NEXT PASS SHOULD DO, in order

1. **The hand-off word is the bigger of the two mechanisms and the cheaper one.** 42 % of the
   organ demo's note-ons are muted 37 µs after their gate by a register field whose meaning
   the disassembly explicitly records as UNDECODED. Decoding `slot[+0x2d]`'s low bits — or
   establishing that the chip ignores them — is worth more than any level-law work, and it is
   a pure RE task with no calibration in it.
2. **Do not spend another pass on the EG level law without `R`.** Three independent routes
   (linear-amplitude law, gate latching, +0x080 modelling) have now each been falsified
   against the piano headroom. `R` is one measurement on Felipe's real KN5000 (§"What is
   still missing", step 2) and every one of these arms is decidable once it exists.
3. `tools/kn5000_collapse_detect.py` is the regression gate for all of it. Report CLICK and
   INAUDIBLE separately — collapsing them is what hid mechanism (b) for this long.

---

# 2026-08-06 (later still) — the HAND-OFF WORD is DECODED, and it is NOT an amplitude

Step 1 of the list above, done. **The group0/bank0 word's low field carries no magnitude, and
reading it as one deletes the entire DRUM PART of both demos.** DERIVED from the sub-CPU ROM
and MEASURED on the live bus and in the sub-CPU's own slot records. Nothing was calibrated
and no constant was chosen; the only new code is an experiment switch, default OFF.

New tool: `tools/kn5000_handoff_probe.lua` — a write tap on 0x100000/2 that, at every
group0/bank0 write, also reads the sub-CPU's voice slot (0x04308E + ch*0x47; the slot index
IS the TG channel, proven by 0x027338 `muls WA,0x47; lda XBC,0x0430BB; (XBC+WA) <- 0xF000`,
0x0430BB = base+0x2D) and the records it points at. That is what turned this from a guess
into an attribution.

## A. What the register receives — MEASURED, both demos, t = 22–40 s

| demo | 0x8100 gate | 0x7E00 free | hand-off | the ONLY values seen |
|---|---|---|---|---|
| organ | 1330 | 1320 | **1330** | FEFF 706 · FE00 412 · F000 157 · F0FF 55 |
| piano |  484 |  458 |  **484** | F0FF 278 · F000 146 · FEFF 60 |

* **the low byte is only ever 0x00 or 0xFF, and bit 8 is NEVER set** — 1814/1814;
* one hand-off per gate, always: it is **the last write of the note-on burst**, not a
  parting shot before the firmware abandons the note. MEASURED offsets from one gate:
  `+3..28 µs` the nine EG words, `+31 µs` the +0x080 burst LOAD STROBE released,
  `+38 µs` the hand-off;
* **the free count tracks the gate count.** The old `data_w()` claim that the firmware
  "has freed the channel and will never send that voice a 0x7E00" is refuted on the bus.

## B. The two builders — DERIVED

```
Voice_Build_GateCommand           0x025589
    BC = 0xFF - 4*(partial[0] & 0x3F) ;  BC |= 0x100 iff partial[0] != 0   (partial = slot[+0x17])
    OR 0xFE00 if part[+0x12] != 0 and 0x04134C in {0,5,6}, else OR 0xF000
Voice_Build_GateCommand_NoPartial 0x0255F3   ... same, but NO LOW FIELD IS EVER COMPUTED
Voice_Apply_GateRouting           0x02552A   rewrites bits[14:12] and bits[11:9] from the two
    nibbles of part[+0x25] (the byte CC 0x9B writes): 0 -> OR 111, 1 -> leave, 2 -> force 001
```

Fields: bit 15 (always set) · two 3-bit per-PART fields · bit 8 · byte. Only the last two
could be a magnitude, and bit 8 is the byte's own present/enable flag — the firmware sets it
exactly when the source is non-zero and emits the neutral 0xFF when it is not.

## C. Which builder runs is a TONE-ARCHITECTURE choice — MEASURED, 1814/1814

The partial's offset inside its tone record splits the population perfectly:

| partial offset | stride | partial[0] | hand-off low byte | n |
|---|---|---|---|---|
| +102, +183, +264, +345 | 81 | **0 in 1099/1099** | **0xFF** | 1099 |
| +16, +37 | 21 | 20,32,40,52,64,76,88,96,108 — never 0 | **0x00** | 715 |

**PART 3 is 100 % of the 21-byte kind** (157/157 organ, 146/146 piano), its descriptor byte
varies per hit over that drum-key-shaped set, and its onsets sit on a steady grid (median
inter-onset 0.197 s organ / 0.125 s piano). **Part 3 is the drum part, and the shipped code
silences every note of it.** The organ's parts 0 and 1 fire SIX and FIVE voices per note-on,
two of which are of the same kind — so the mute also strips two layers off every organ note.

## D. The criterion that could have failed, and did not

A velocity, a per-part volume or an expression value must move when a note's loudness moves.
Organ demo, within one fixed hand-off word:

| word | n | attack level min…max | +0x080 level field min…max (sd) |
|---|---|---|---|
| FEFF | 960 | 242…255 | 2242…3190 (329) |
| FE00 | 553 | 255…255 | 2166…2816 (225) |
| **F000** (drums) | **185** | **162…249 = 32.7 dB** | **1792…3922 = 8.3 dB** (469) |
| F0FF |  64 | 233…247 | 3508…3884 (104) |

The drum part's own loudness registers span 32.7 dB and 8.3 dB across 185 note-ons while the
hand-off word is **bit-identical in all 185**.

## E. What the field IS

**A per-partial parameter of the partial descriptor's byte 0, expanded as
`0xFF - 4*(byte0 & 0x3F)`, with bit 8 as its own enable — and it is never enabled.** byte 0
is 0 in every 81-byte partial in both demos, so the field is the constant 0xFF with its flag
clear; the 21-byte partials have no such field, which is why their word carries 0x00. It is
not a velocity, not a per-part volume, not an expression value (expression is part+0x10 and
reaches the chip through `Voice_Calc_LevelPair_*` → +0x800/+0x840/+0x880, traced last pass),
and not a per-note magnitude of any kind. Its chip-side meaning is NOT claimed here. What is
settled is that nothing rendered may be gated on it.

## F. Rendered — `KN5000_HANDOFF=ctrl`, default OFF

**NULL CONTROL:** with the switch unset the organ-PCM WAV is md5-identical
(`96ba4fa846752971a165a13bd1997bef`) to a capture from a binary rebuilt from HEAD with the
change stashed, same note-on count (1828). Mix window t = 28–38 s, speaker pair — it
reproduces `cb1c144`'s own baseline exactly (piano peak 24072 / 0 clipped; organ peak 17676 /
rms 2661).

| demo | mode | arm | CLICK | INAUDIBLE | OK | peak | rms | clipped | into the soft knee |
|---|---|---|---|---|---|---|---|---|---|
| organ | pcm  | base | 17 | 1320 | 338 | 17676 | 2661 | 0 | 0 |
| organ | pcm  | **ctrl** | **0** | **1199** | **473** | 32747 | 6871 | 0 | 366 (0.0381 %) |
| organ | sine | base |  1 | 1516 | 198 |  9894 | 3109 | 0 | 0 |
| organ | sine | **ctrl** |  1 | **1404** | **316** | 26626 | 7094 | 0 | 0 |
| piano | pcm  | base |  4 |  247 | 342 | 24072 | 3499 | 0 | 0 |
| piano | pcm  | **ctrl** |  **0** |  **142** | **451** | 32411 | 8402 | 0 | 139 (0.0145 %) |
| piano | sine | base |  0 |  218 | 377 | 32622 | 6373 | 0 | 396 (0.0413 %) |
| piano | sine | **ctrl** |  0 |  **157** | **438** | 32680 | 7493 | 0 | 569 (0.0593 %) |

Per hand-off class, organ PCM — the population split §6 asked for:

| word | n | median voice peak base → ctrl | verdicts base → ctrl |
|---|---|---|---|
| FEFF | 960 |   528 → 531 | unchanged — a NULL, this class already had env_level 0xFF |
| F0FF |  64 | 11221 → 11224 | unchanged |
| FE00 | 553 |    85 → 309 | 553 INAUDIBLE → 540 INAUDIBLE + 13 OK |
| **F000** | 185 | **158 → 2931 (+25.4 dB)** | 168 INAUDIBLE + 17 CLICK → **60 INAUDIBLE + 125 OK** |

★ The `FE00` class rises only 3.6× and stays under the detector's −30 dBFS floor. Its
baseline 85 is not the mute leaking — it is the 1.8 output samples rendered between the gate
and the hand-off 37 µs later. Those voices are quiet for a **second, independent** reason;
un-muting is necessary but not sufficient there. Separate open item, not a failure of this
decode.

## G. Why the default is still OFF

The agreed clipping gate passes — 0 clipped samples in all four conditions — **but that gate
is nearly incapable of failing**, because the output stage ends in a tanh soft knee at
0.85 FS that bounds the mix below full scale by construction. The metric that can fail is how
much programme the knee acts on: piano PCM 0 → 139 samples (0.0145 %), and the peak the mix
would have had without the knee goes **24072 → 35910, +3.5 dB**; organ PCM 0 → 366 samples
and 17676 → 42959, +7.7 dB. That is the missing gain-staging **reference R** again — putting
~40 % of the voices back raises the sum, and nothing in the firmware says which code is full
scale.

**Recommendation:** make `ctrl` the default once `R` exists, or at Felipe's direction sooner.
Silencing the whole percussion section is a far larger error than being 3.5 dB hot, and the
present behaviour is not defensible on any reading of the firmware — it survives only because
flipping a default that moves the instrument's loudness by 8 dB is his call.

## H. Corrections to the record

* `LABEL_022587` is `Voice_Clear_HoldBit` (clears the voice record's HELD bit and
  re-prioritises), **not** "free the channel". The old `data_w()` argument built on it falls.
* "a handed-off voice has NO remaining path to end" — refuted; frees track gates 1:1.
* "rhythm voices get the bare 0xF000 … and render at −81 dB" — right about the mechanism,
  wrong that it is acceptable: those are the drums.
* §2(b)'s `handoff-0` population is confirmed and now attributed — it is the drum part plus
  the 21-byte partials of the melodic tones, **not** "voices that are silent by design".

## I. What the next pass needs

1. **The `FE00` class** — 553 organ note-ons still at a median voice peak of 309 with the
   mute gone. Their EG parks on a HOLD (segment-2 words 0xB800 / 0x7800 / 0x7000, rate 0).
   Find what else attenuates them.
2. **`R`** — unchanged, and now blocking two ship-quality changes instead of one.
3. **Bits[14:12] and bits[11:9]** of this word. They take only 000/001/111, come from
   `part[+0x25]` (CC 0x9B) and `part[+0x12]`, and are the only content of the word that
   varies at all. That is what this register has left to give.

---

# J. The undumped-ROM mute, and the retraction of the "extreme noise" attribution

2026-08-06, second pass. Felipe's spec, verbatim:

> I want the PCM mode to mute all samples from the undumped ROMs, but do not mute any samples
> from the good ROM. And I want the sine wave mode to play everything regardless of the
> associated ROM, because it does not depend on the samples, so there's no need to mute them
> in that mode. Then we should focus on fixing the organ demo, to make it sound correctly.
> And that should be doable because (as far as I remember) the organ is entirely stored in
> the good ROM.

Implemented as `voice_t::wave_undumped` + `m_mute_undumped` (default ON, `KN5000_UNDUMPED=play`
to hear what is being suppressed). It zeroes the voice's contribution AFTER the pan and BEFORE
the mix, so the EG, the wave pointer, the release/hold counters and the silence interlock all
still run on the unmuted sample: voice allocation and everything `status_r()` reports back to
the firmware are unchanged by it.

## J.1 The bank census — WHICH ROM each demo actually plays

Note-ons per wave bank, 45 s captures, `KN5000_NOTELOG` (bank 1 = IC307, the one hardware-rooted
dump; bank 0 = the socket serving classes 0-3, which is IC304/305/306 and is UNDUMPED — filled
with a BAD_DUMP copy of IC307, kn5000.cpp ROM_REGION):

| demo  | bank 1 = IC307 | bank 0 = UNDUMPED | share of note-ons | **share of rendered ENERGY** |
|-------|---------------:|------------------:|------------------:|-----------------------------:|
| organ | 1698           | 129               | 7.1 % undumped    | **75.5 % undumped**          |
| piano |  565           | 101               | 15.2 % undumped   | **0.35 % undumped**          |

**Felipe's premise is true by note count and false by loudness.** 92.9 % of the organ demo's
note-ons are on IC307, but three quarters of the sound coming out of it today is *not*. The
whole of that 75.5 % is one layer: 64 note-ons of `+040` = 0x109A/9B/9C (class 1 → bank 0,
page 1), sounding in the bass register (period 256 samples played at 0.66x = 113 Hz) on a
~0.33 s onset grid, median voice peak **11269** while the organ's own voices sit at **531**. All three selections resolve to the same IC307 page-1 chunk (they share a
wave offset), so today the demo plays one sustained IC307 tone 64 times in place of three
different recordings nobody has.

Muting it is therefore both correct and expensive, exactly as measured:

| arm (28-38 s window, ch1) | rms | peak | note-ons OK / INAUDIBLE |
|---|---:|---:|---|
| organ PCM, mute off (= previous build, md5-identical) | −21.81 dB | 17676 | 338 / 1320 |
| organ PCM, **mute on** | **−29.18 dB** | 8012 | 276 / 1384 |
| piano PCM, mute off | −19.02 dB | 24072 | 342 / 247 |
| piano PCM, **mute on** | **−19.03 dB** | 23994 | 340 / 249 |

**The piano regression gate passes with 0.01 dB and two notes.** That was PREDICTED before the
run from the energy share (0.35 % ⇒ 0.015 dB) and then measured — it is not a gate that could
not fail: the same prediction for the organ said −6.1 dB and the organ moved −7.37 dB.

Three controls, all of which could have failed and did not:

* `KN5000_UNDUMPED=play` reproduces the pre-change build **bit-for-bit** (organ WAV md5
  96ba4fa8… in both). So the change is exactly the mute and nothing else.
* Both **sine** arms are **bit-identical** to the pre-change build (organ 2d77e917…, piano
  06148142…). Sine mode plays everything, per spec.
* Note streams are identical row for row (1827 / 666 rows, same `t_on`/`ch`/`+040`), and every
  bank-1 row's voice peak is unchanged. The mute did not leak into voice allocation.

One residue: 1 of the 101 muted piano rows reaches peak **6** (−74.7 dBFS). `data_w()` re-runs
`resolve_waveform()` on every `+0x080` burst strobe, so a voice still ringing under release can
be re-pointed at a dumped chunk by the *next* note's burst. Pre-existing, unrelated to the mute.

## J.2 RETRACTION — the "extreme noise" was never the undumped ROMs

The previous pass explained Felipe's verdict on `KN5000_HANDOFF=ctrl` ("that is now really bad!
extreme noise!") as un-muting the percussion, which it said selects the undumped sockets. **That
is refuted by the census above.** Of the note-ons the decode un-mutes (hand-off low byte 0x00):

    organ 739 of 1827 — 738 on IC307;   piano 180 of 666 — 179 on IC307

The single exception in each is the power-on ping at `+040` = 0x0000. So the noise lives on the
**good** dump, the mute in J.1 cannot suppress any of it, and re-enabling the decode "because
the bank mute now handles it" would have shipped the identical noise a second time.

**What the noise actually is.** The 185 un-muted organ voices are IC307 **page 1** selections
held for a median of **4.4 s** (max 6.3 s), and `detect_period()` cannot pitch those recordings.
Its fallback then declares the *whole recording* to be one cycle, and `update_pitch()` stretches
it to reach the note:

| `+040` | notes | samples | detected period | playback rate | median peak (ctrl) |
|---|---:|---:|---:|---:|---:|
| 0x505B | 87 | 1496 | 1496 (= N) | **11.5×** | 621 |
| 0x5046 |  7 | 1568 | 1568 (= N) | **19.0×** | 1007 |
| 0x504C | 31 | 2448 | 0 (aperiodic, zcr 0.53) | 1.0× | 7339 |
| 0x5054 | 20 | 10488 | 0 (aperiodic, zcr 0.59) | 1.0× | 2270 |

A 31 ms recording crammed into one 130-sample cycle (369.9 Hz) and repeated ~1830 times over a
five-second note is a granular buzz at the right pitch, not a note; and for the aperiodic ones
`compute_loop()` sets `loop_len` = the whole recording, so a 51 ms noise burst repeats ~100
times per note at up to −4.6 dBFS while the organ's own voices are at −36 dBFS. Measured on the ctrl arm *with* the bank mute on: mix rms
−29.18 → **−12.93 dB**, peak 8012 → **32502 (−0.07 dBFS)**.

`m_handoff_ctrl` therefore stays OFF, for a **new and measured** reason: the estimator defect,
not the missing dumps. §G's recommendation is superseded — `R` is no longer what blocks it.

## J.3 What is still wrong with the organ demo

1762 note-ons (t ≥ 12 s), classified with `tools/kn5000_collapse_detect.py`, each attributed to
one cause. Regrouped by simultaneity, these are **549 key presses**, of which **239 (44 %)** now
produce a summed voice peak ≥ 1000; median composite peak 1298 → 389 after the mute.

| cause | note-ons | median voice peak | status |
|---|---:|---:|---|
| A. undumped socket — silenced by J.1 | 64 | 0 | **NOT FIXABLE without a dump of IC304/305/306** |
| B. hand-off low byte 0x00 ⇒ `env_level` = 0 | 738 (721 INAUDIBLE + 17 CLICK) | 86 | on IC307; blocked by J.2 |
| C. audible path, EG segment-2 target 114 | 594 INAUDIBLE (+181 OK, 56 SHORT) | 350 | see below |
| C′. EG segment-2 target 146 | 5 INAUDIBLE (+95 OK, 29 SHORT) | 748 | |

**B is now the largest defect in the organ demo — bigger than the missing ROMs.** 42 % of its
note-ons are silenced by a register reading the previous pass showed to be wrong, and they are
all on the one ROM we have.

**On C, a caution about the unit.** These are class-6 selections = IC307 page 2 = the drawbar
footage waves: 64- and 128-sample single-cycle tables, near full scale in the ROM (peak 32742,
rms ~19000-23000). The organ demo fires a **median of 4 and up to 10 of them per key press**
(1513 page-2 voices in 416 simultaneity groups) — they are *partials of one additive tone*,
not notes. A quiet partial is not automatically a
defect, and the per-note classifier has no way to know that. What separates the audible from the
inaudible ones is **`+0x080`, not the EG**: within the identical `eg2` = 0x727F class,
`+040` = 0x6096 has field 0xC2C (−21.4 dB) and median peak 1963, while 0x6263 has field 0x8F4
(−40.6 dB) and median peak 239 — a 19 dB spread that is exactly the drawbar registration. So
`R` (§G) remains the open question for C, and "the organ is too quiet" and "the drawbars are
correctly at different levels" are the same measurement until `R` is known.

## J.4 What the next pass needs

1. **Decide `detect_period()`'s aperiodic fallback**, which is J.2's blocker. The final
   `return (samples <= 2048) ? (samples << 16) : 0` is reached only when the correlation *has*
   crossed zero (so the window holds more than one cycle) *and* no lag correlates above 0.5 —
   i.e. after a positive measurement of aperiodicity, which the fallback then contradicts.
   Returning 0 instead is self-consistent, **but it is not obviously better**: the current arm
   gives the right pitch with a destroyed timbre, and `0` gives the recording's own timbre with
   no pitch control at all. Both are wrong for a melodic voice; `0` is right for a one-shot.
   **This needs to know what IC307 page-1 chunks 0x46/0x4A/0x4C/0x54/0x5B ARE** — the
   directory's own param block (key-split bytes) or Felipe playing the patch on real hardware
   would decide it. Do not flip it on taste.
2. `compute_loop()` gives an aperiodic recording `loop_len` = the whole recording. A one-shot
   should stop, not repeat ~90 times — but "stops" also frees the channel earlier through the
   silence interlock, which changes voice allocation. Measure that before changing it.
3. **`R`**, unchanged, still blocking C.

# K. The HELD-NOTE SUSTAIN defect — reproduced, attributed, and the rig that keeps it fixed

2026-08-06, later still. Felipe, playing the emulator from a MIDI controller:

> "Many instruments have incorrect length of sustain in their envelope params. For instance,
> all strings should keep sounding for a long time while the player is holding a key down.
> But instead, they decay after a very short sustain interval."

**Verdict up front.** The lead hypothesis (that the HLE runs through the final EG segment while
the key is still held) is **REFUTED, measured**. The symptom is reproduced **exactly and only**
by the **logarithmic EG level law** — the arm that was the default until `cb1c144` earlier the
same day. Under the shipped default (`KN5000_EGLAW` unset = `lin`) **19 of 19 voices across nine
sound families survive a full 6-second hold** and are ended by the real key release; under
`KN5000_EGLAW=log` **9 of those 19 are torn down by the firmware between 0.13 s and 0.31 s**.
The cause is DERIVED (the register decode and the segment semantics come out of the sub ROM);
the *cure* — the linear law — remains **FITTED**, exactly as §"2026-08-06" already recorded.

## K.0 The rig, and the criterion that CAN fail

New, all default-off, nothing compiled into the driver:

    tools/kn5000_hold_note.lua      select a SOUND GROUP, hold ONE key, tap the raw TG bus
    tools/kn5000_capture_hold.sh    one sweep -> notes.csv + bus.txt + marks.txt + out.wav
    tools/kn5000_hold_analyze.py    per-hold rendered amplitude ENVELOPE

With one key down and nothing else sounding, **the rendered WAV IS the per-voice envelope**.
That matters because of the discipline this file keeps returning to: **rms / peak / clipping
over a capture cannot see this defect at all.** Every one of them is perfectly happy while every
held note dies 200 ms in — the demo keeps re-triggering notes, so the level metrics stay put.

The reported number is `sus_db` = (mean of the last tenth of the hold) / (loudest tenth), in dB.
It is a RATIO inside one hold, so it measures decay-*during*-the-hold and nothing else — a patch
that is merely quiet scores 0 dB, and a patch that dies scores −40 dB or worse. **It demonstrably
fails**: −47.4 dB on the strings arm that carries the bug, −2.0 dB on the arm that does not.
`rel_db` is its mate and guards the opposite error — a "fix" that never releases — by measuring
100 ms after key-up; it reads −120 dB (silent) in every arm, so the release is intact throughout.

## K.1 REFUTED — the EG does not run past its last segment while the key is held

MEASURED, `strings` held 8 s, `KN5000_NOTELOG` (the 10 ms envelope profile is 24 buckets):

    ch0  eglvl10ms  77;54;54;54;54;54;54;54;54;54;54;54;54;54;54;54;54;54;54;54;54;54;54;54
         egseg10ms   1; 2; 2; 2; 2; 2; 2; 2; 2; 2; 2; 2; 2; 2; 2; 2; 2; 2; 2; 2; 2; 2; 2; 2
    ch1  eglvl10ms  66;66;66;...   egseg10ms 2;2;2;...
    eg_seg_end = 2   eg_level_end = 54.0000 / 66.0000   (after 8 s of hold)

The EG reaches segment 2 in 12 ms and **holds there, at a constant level, for the whole hold**.
`load_eg_segment()` already clamps `seg` to 2 and the stepper only advances `if (v.eg_seg < 2)`,
so there is no fourth hop to make. The hypothesis was worth testing and it is wrong.

## K.2 What the three segments ARE — DERIVED from the sub ROM (v142)

| register | scratch | built by | from partial bytes | meaning |
|---|---|---|---|---|
| `+0x800` | `0x0451E4` | `Voice_Calc_LevelPair_PatchAtk` 0x025636 (asm L19848) | `+0x27`/`+0x28` (= +39/+40) | **ATTACK**: `(PeakLevel_Fader[+0x27] << 8) \| RateTab[+0x28]` |
| `+0x840` | `0x0451E6` | same, L19862 / `Voice_WriteChPanShift` L20105 | `+0x29`/`+0x2A` (= +41/+42) | **DECAY1 → SUST1**, rate **floored at 4** (L19981) |
| `+0x880` | `0x0451E8` | same, L19870 / L20095 | `+0x2B`/`+0x2C` (= +43/+44) | **DECAY2 → SUST2**, rate floored at **0** (L19989) |

The brief's couple layout `(+39,+40)/(+41,+42)/(+43,+44)` is **CONFIRMED exactly**, and the same
three couples drive `_Full` (0x025C87), `_Mono` (0x025F7F) and `_FixedAtk` (0x025A35, whose
attack rate is the literal `0x7F`). `Voice_Stage_EnvSegments` (0x02684A) is not a builder: it
re-ships the cached `slot+0x3e` / `slot+0x40` to `+0x840` / `+0x880`.

**All three are KEY-DOWN segments, and segment 2 is TERMINAL.** The decisive question — does the
firmware program a RELEASE segment at key-off? — is answered three ways:

* **By exhaustion.** `0880h` occurs at exactly **three** emitting sites in the whole payload
  (asm L30870 note-on burst, L31233 `ToneGen_WriteEnvSegments`, L31281
  `ToneGen_WriteSegRegs_SameLevel`). The latter two have four call sites, all inside
  `Voice_Reload_Levels` / `Voice_AllNotes_SustainRetrigger`, and both re-ship the *note-on*
  words. **No release word exists.**
* **On the live bus**, this capture, one 8-second held C4 (`bus.txt`):
      20.005905 0800 B07F | 20.005907 0000 8100 | 20.005911 0840 3674 | 20.005914 0880 3674
      ... 8 SECONDS WITH NOT ONE WRITE ...
      28.004975 0840 7900   0940 AE00   0A00 AE00   0800 7980   0900 AE00   09C0 AE00
      28.124534 00C0 0000   0000 7E00
  Key-off writes `+0x800` and `+0x840` only, with **rate 0** and a level (0x79 = 121) that is
  *louder* than the sustain it replaces — a level COMMAND, not a ramp. `+0x880` is never touched.
* **No fourth segment exists.** `+0x8C0` is built by `Voice_PortaLevel_Compute` (L18261) whose
  low byte comes from `Detune_ScaleSymmetric`, the same helper that feeds `+0x900…+0xA40` — it is
  a `level|pan` word, not `level|rate`. Only group 8 carries a rate. There IS a fourth *level*
  parameter (`partial[+0x2D]`, read by `Voice_Calc_LevelPair_EGA` at L21580) but **no fourth
  rate**: it is the software-commanded steady level pushed at every volume/expression/key-off.

So the HLE's structure — three segments, stop and hold on the third — is **correct as written**.

## K.3 The symptom, reproduced. MEASURED A/B, nine sound families, sine mode, 6 s hold

Sine mode is the right instrument here: it ignores wave data entirely, so a decay it shows is
unambiguously the envelope and not a recording running out.

| family | `sus_db` shipped (`lin`) | `sus_db` `KN5000_EGLAW=log` | segment-2 word |
|---|---:|---:|---|
| strings | **−2.0** | **−47.4** | `3674` / `427F` |
| pad     | −0.1 | −23.5 | `427F` `4467` `647F` |
| organ   | −0.0 | −27.9 | `727F` |
| brass   | −5.6 | **−120 (silent)** | `197F` |
| flute   | −6.8 | **−120** | `326A` |
| sax     | −5.0 | **−120** | `2674` `2A60` |
| synth   | −34.1 | **−120** | `046A` `0467` |
| guitar  | −0.0 | −0.0 | `4E00` |
| piano   | −2.7 | −23.1 | `4000` |

**Eight of nine families die under the log law; none die under the shipped default.** That is
Felipe's sentence — "many instruments … for instance, all strings" — as a table. `guitar` is the
one family the log law spares, and for a reason that supports rather than weakens the reading:
its `+0x840` is `9200`, rate 0, so it never leaves segment 1 and its own peak IS its sustain.
`synth` is the one family that decays under BOTH laws, also for a decoded reason: its segment-2
level code is `0x04` = `Level_Fader[100]`, the table's maximum attenuation — a plucky patch
programmed to decay, not a defect.

Why the log law does this is already derived in this file: `gain = 2^((L−255)/16)` puts the
strings' SUST2 code 54 at **−75.6 dB** and the organ's code 114 at −53 dB. The register spread
between a patch's PEAK and its SUST is a structural 120–160 codes (organ census: PEAK 255 /
SUST2 114, delta 141, n = 554), and under 0.376 dB/code that is a 45–60 dB collapse for
*every sustaining instrument in the machine*.

## K.4 The mechanism is a VOICE TEARDOWN, not merely a low level

This is why the symptom is "length of sustain" and not "too quiet". MEASURED `ko_src` (2 = the
firmware's own `0x7E00` FREE, 1 = the real key release), same 6-second holds:

    KN5000_EGLAW=log   strings ch0 ko=0.167 src=2 | brass ch8 0.142 src=2 | flute ch9 0.200 src=2
                       sax ch10/11 0.155 src=2    | synth ch12 0.215, ch13 0.313 src=2
                       pad ch4 0.125 src=2                        -> 9 of 19 voices, all src=2
    shipped (lin)      19 of 19 voices: ko = 6.012 … 6.015, src=1  -> every one released by the key

End to end: the level law drives the sustain below the silence interlock (0.5 output LSB held
for one 98.33 ms bank-poll period) → `eg_running` drops → `status_r()` reports the voice silent →
the firmware's voice manager (`Voice_Manager_PollBank` → `ToneGen_SilenceChannel`) writes
`0x7E00` and **deallocates the channel**. The note is not quiet, it is *gone*, ~0.2 s into a hold
that has seconds left to run. Nothing can bring it back. That is the reported defect, exactly.

## K.5 Two clean negatives, both worth having

**Interference — a MIDI player holds notes WHILE PLAYING OTHERS.** A single isolated held note
cannot see a false key-off, and the HLE's release heuristic fires on any `+0x900` write >1 ms
after the gate while `Voice_Reload_Levels` re-emits that burst for ten different reasons. So:
hold C4 for 8 s and strike E4 at +2 s, +4 s and +6 s (`KN5_POKEMASK`/`KN5_POKE_AT`), strings /
organ / piano, both render modes. MEASURED: the held voices report `t_ko_rel = 8.000, src = 1`
in **6 of 6** cases and the pokes take their own channels with their own correct 0.257 s
releases. `sus_db` −2.7 / −3.1 / −5.6 dB. **No false key-off.** Not the defect.

**Velocity.** DERIVED, asm L19742-19756: the PEAK level index is
`clamp(partial[+0x27] + (int8)tone_rec[+0x6b], 0, 100)` — a **key-track** term, not a velocity
one; velocity reaches `+0x080` and the TVF instead. So velocity scales a note uniformly and
**cannot shorten it**. The ioport key bed's fixed `KEYBED_VELOCITY = 100` is therefore not a
blind spot for *this* question (it still is for loudness — see `notes/dsp-audiopath-wired.md`).

Also MEASURED, and a limitation of the rig rather than a finding: pressing a SOUND GROUP button
repeatedly does **not** page through the group — eight consecutive `STRINGS & VOCAL` presses gave
byte-identical segment words and `sus_db` −1.8 … −2.0 every time. The rig reaches each group's
default patch only; reaching the rest needs the LCD soft keys.

## K.6 SEPARATE, and Felipe should know it: four of nine groups are now SILENT in PCM mode

Not the envelope, but he will hit it the moment he presses STRINGS. With the shipped defaults
(`J.1`'s undumped-socket mute ON), the DEFAULT patch of these sound groups renders **nothing**:

    strings  brass  synth  guitar        (peak 0 over a 6 s hold)
    pad organ flute sax piano            play normally

Their `+0x040` resolves to **bank 0**, i.e. IC304 — one of the three sockets nobody has dumped.
`KN5000_UNDUMPED=play` renders them from the substituted IC307 material and they sustain
correctly (`sus_db` −1.9 … −9.8). This is the mute working as specified, not a regression, but
"the strings are silent" and "the strings decay" are different reports and should not be
confused with each other.

## K.7 What this leaves for the next pass

1. **Nothing to change in the driver.** The segment structure is correct, the terminal-segment
   hold is correct, the release is correct, and the level law that broke the sustain was already
   swapped out earlier the same day. `git diff` for this pass is three new tools and this note.
2. **Ask Felipe to re-test on the current published binary** (built 15:37, `7c53c1b`). His report
   is reproduced bit-for-bit by the `log` arm and by nothing else in the test space above, which
   places it before `cb1c144` (11:08) — but he is the ground truth, and if a held strings note
   still dies on the 15:37 build then the cause is outside everything measured here and the rig
   above is the thing to point at it.
3. **`R` is still the open question** (§G, §J.4). `lin` is a fitted compromise that happens to
   keep every family's sustain alive; it is not believed to be IC303's law. When the
   gain-staging reference arrives from real hardware, `tools/kn5000_hold_analyze.py` is the gate
   the new law has to pass — 8 of 9 families at `sus_db` > −10 dB, and `rel_db` at the floor.

---

# L. Felipe re-tested on the current build. §K's conclusion was OVER-GENERALISED — RETRACTED

2026-08-06, evening. §K.7 asked Felipe to re-test on the published 15:37 binary. He did:
~20 minutes, real MIDI controller, `-midiin2 "SINCO SMK25-Master"`. Two things follow.

**First, which build.** `-midiin2` is the SECOND `MIDI_PORT` the driver instantiates, i.e.
`kbdmidi` — the MIDI→key-bed bridge, not the rear MIDI IN. So his notes take the same
`push_keybed_event()` path §K measured, and his binary is the current source (the only
later commit, `4bf5746`, touched tools and notes; no kn5000 source is newer than the
binary). He is on the shipped `KN5000_EGLAW=lin` default.

**Second, and this is the retraction.**

> ⚠ **RETRACTED:** "*Eight of nine families die under the log law; none die under the
> shipped default*" ⇒ "*the short-sustain defect is cured; nothing to change in the
> driver*" (§K.3, §K.7.1).

The **measurement** stands — those 19 voices really do survive, and the log law really does
kill them. What is withdrawn is the **generalisation from it to the class**. §K.5 had already
written down the reason and it was not respected:

> "pressing a SOUND GROUP button repeatedly does **not** page through the group … The rig
> reaches each group's default patch only; reaching the rest needs the LCD soft keys."

So "nine sound families" was **nine patches — each group's default** — out of roughly 800 in
the machine. It was never evidence about the class, and Felipe playing actual patches found
counter-examples immediately. This is the same failure this file keeps recording: a result
that could not have failed in the direction that mattered, because the rig could not reach
the cases that would have falsified it.

## L.1 The rig can now reach any patch — and it has to prove it did

`tools/kn5000_patch_probe.lua` selects by **sound group + LCD page + LCD soft key**, so any
of the ~800 patches is reachable; `tools/kn5000_capture_patch.sh` drives it. The soft-key
map is lookup from `kn5000_cpanel.cpp`'s `PORT_NAME`s, and it works: FLUTE L1/L2/L3 give
three distinct selectors `5000` / `5003` / `5007`.

⚠ **A NEW WAY TO BE WRONG, and it bit immediately.** A ten-patch ORGAN sweep produced ten
holds, ten envelopes and ten tidy `sus_db` rows — and **seven of the ten had silently
re-used the previous patch's selector `4007`**, because the panel had wandered onto the
ENTERTAINER screen and every later soft key landed there. Read naively it said "nine of ten
organ patches sustain". It actually said "one patch sustains, nine times". Two more runs
drifted onto the BASS group and onto page 1/2 while *still* passing a
distinct-selector check.

Countermeasures, all now in the rigs, and none of them sufficient alone:

* `tools/kn5000_patch_check.py` — flags any patch step whose selectors repeat the previous
  step. NECESSARY, not sufficient: two real patches may legitimately share a selector.
* **exactly one LCD snapshot per patch**, taken immediately before the note, so the
  snapshot ordinal *is* the patch index and the picture is a countable arbiter.
* **short runs**. Drift grows with run length; one patch per run did not drift once.

**Every per-patch number below comes from a one-patch run whose LCD snapshot was read and
confirms the patch by name.** The ten-patch runs are used only where they agree with those.

## L.2 MEASURED: Felipe's three named ORGAN & ACCORDION facts

One key (C4) held 6 s, PCM mode, shipped defaults, `sus_db` as defined in §K.0.

| patch | page / key | Felipe | MEASURED `sus_db` | verdict |
|---|---|---|---:|---|
| **Rock Organ** | 2/2 LEFT 4 | sustains | **−3.2 dB** | ✅ **reproduces** |
| **Chapel Organ** | 1/2 LEFT 3 | sustains | **−2.3 dB** | ✅ **reproduces** |
| **Theatre Novelty** | 2/2 RIGHT 3 | silent | **peak 0** | ✅ **reproduces** (see §L.4) |
| Soul Organ | 2/2 LEFT 3 | (unnamed) | **−22.0 dB** | decays, and §L.3 says why |

**Three of three named facts reproduce exactly.** His two "good" patches are good here too,
so his differential is real and the rig can see it.

## L.3 …but "almost all of ORGAN & ACCORDION" does NOT reproduce

> ⚠⚠ **RETRACTED IN FULL — see §M.0.** The ten-patch runs behind this table reached at most TWO
> distinct organ patches each and then wandered onto ENTERTAINER and onto the LEFT part's PIANO
> group; their own LCD snapshots say so. Eighteen of the twenty numbers below are not the patch
> they are labelled with, and the "18 of 20 sustain" conclusion is unsupported. §M.3 has the
> re-measurement, one patch per run, every name read off the LCD — and it CONFIRMS Felipe.

All 20 patches of both pages, from the validated ten-patch runs:

    page 1/2  Perc Organ −0.1  Full Drawbars −0.0  Chapel Organ −2.4  Full Organ −1.3
              Cathedral Organ −2.0  Jazz Drawbars −0.7  16'&1' −0.6  Bright Accordion −2.8
              Musette −3.8  Folk Accordion −2.6            <- ALL TEN SUSTAIN
    page 2/2  Accomp Drawbars −0.0  Pop Organ −0.0  **Soul Organ −22.4**  Rock Organ −1.3
              Organ Bass −0.0  Theatre Organ −0.2  Theatre Accomp/Novelty silent
              Mellow Accordion −0.1  Bandoneon −2.5

**18 of 20 sustain; exactly one decays** (Soul Organ), and it decays for a fully decoded
reason: its segment-2 word is `047C` on all four partials — level code **`0x04`**, the
`Level_Fader` table's maximum attenuation, the same "programmed to decay" signature §K.3
already identified in `synth`. That is a patch design, not a defect.

⇒ **Felipe's "almost all" is NOT reproduced at one key, velocity 100, 6 s.** Extending the
hold to **30 s** changes nothing (Perc Organ −0.1, Full Drawbars −0.1 over thirty seconds),
so it is not a slow decay the 6 s window was missing.

## L.4 Theatre Novelty is CORRECT BEHAVIOUR, not a defect
<!-- ⚠ the Theatre NOVELTY finding stands; the Theatre ACCOMP sentence at the end is RETRACTED, §M.5 -->


MEASURED, one-patch run, LCD confirmed: its three partials select `0000`, `0000`, `3195` —
all **bank 0**, `wave_real = 0`, i.e. the undumped IC304/305/306 sockets. With
`KN5000_UNDUMPED=play` it sounds normally (peak 1711, `sus_db` −2.5). So §J.1's PCM-mode
mute is doing exactly what Felipe specified. **Theatre Accomp (2/2 RIGHT 2) is silent for
the same reason** and he did not mention it — worth telling him, since "silent" and
"decays" are different reports.

## L.5 The two obvious explanations, TESTED AND REFUTED

Both were tested by feeding a Standard MIDI File to **`-midiin2`** — the `kbdmidi` bridge,
the very port Felipe plugs his controller into — via `tools/kn5000_mkmidi_vel.py` and
`KN5_MIDI=`. That path carries real velocities, which the ioport key bed cannot
(`KEYBED_VELOCITY = 100` is compiled in). Patch: **Full Drawbars**, LCD-confirmed.

**1. VELOCITY — REFUTED.** It was the best suspect: §K.4's teardown is *level falls below
the silence interlock → firmware deallocates the channel*, so a quiet note starts nearer
that floor. One C4 held 6 s at each of seven velocities:

    vel  15  30  50  70  90 110 127
    peak 873 1057 1366 1819 2428 3221 3953     <- 13 dB of level, so the test has range
    sus_db -0.1 -0.1 -0.0 -0.1 -0.1 -0.1 -0.1  <- FLAT AT EVERY VELOCITY

Velocity scales a note and does not shorten it — which is also what §K.5 derived from the
ROM (the peak-level index carries a *key-track* term, not a velocity one). The criterion can
fail: the same `sus_db` reads −22 dB on Soul Organ and −47 dB on the log-law arm.

**2. POLYPHONY — REFUTED, and this time on a real patch.** C4 held **16 s** while E4, G4,
B4, D5, E4, G4 are struck through it at 2 s intervals. MEASURED: the held voice reports
`t_ko_rel = 15.995 s, ko_src = 1` — i.e. it survived the whole hold and was ended by its own
key-off, not by the firmware's `0x7E00` FREE — and each struck note took its own channel with
its own 0.30 s release. **No false key-off.** §K.5 found the same thing but only on default
patches; that objection is now closed for this patch too.

**3. Panel state — still uncontrolled.** 20 minutes of playing sets effects, parts, volumes
and transposition the rig never touches. This is now the only untested difference, and it is
also the least specific, which is why §L.6 asks Felipe for patch NAMES instead.

⇒ **Do not conclude "Felipe is wrong" and do not conclude "the class is fixed."** The
correct statement is narrow and it is the one to carry forward:

> ⚠⚠ **RETRACTED — §M.0.** "18 of 20 … sustain" was never measured (the runs behind it did not
> select the patches), and the reproduction it was contrasted against needed a CONFIG bit the
> rig could not set. §M: on Felipe's saved cfg the count is **18 of 20 CUT at 0.11-0.16 s**, and
> the two survivors are exactly the two he named. The velocity and polyphony refutations above
> stand and remain correct; they were simply the wrong suspects.
>
> ~~On the shipped defaults, **18 of 20 ORGAN & ACCORDION patches sustain a held note
> indefinitely** (verified to 30 s), at every velocity from 15 to 127, and with other notes
> played through the hold. **All three of Felipe's named patches behave exactly as he
> describes.** The one patch that decays does so by design (`0x04` sustain level).~~

The gap between that and "almost all decay" is **unexplained**, and the two hypotheses that
would have explained it are now dead. That makes the patch NAMES the next thing needed.

## L.6 For Felipe — the one question that now matters

The velocity and chord explanations are both measured and dead, so the remaining
possibilities all hinge on *which patches*:

* ⭐ **Which ORGAN & ACCORDION patches, by the name on the LCD, decay for you?** "Almost all"
  and the measured "one of twenty" cannot both be true. If the list turns out to be Soul
  Organ and a couple of others, the two reports agree and there is nothing left to fix; if
  it is genuinely most of them, something in your panel state that the rig never sets is
  doing it, and knowing the names is what will find it.
* Does a single held note decay for you **with nothing else playing at all** — no rhythm, no
  accompaniment, no sequencer?
* Theatre Accomp (page 2/2, RIGHT 2) should be silent too, for the same undumped-ROM reason
  as Theatre Novelty. Confirm?


---

# M. Felipe's ORGAN & ACCORDION report is CONFIRMED. §L.3's "18 of 20 sustain" is RETRACTED, and the cause is a DIAGNOSTIC PROBE LEFT ON IN THE SHARED cfg

2026-08-06, night. §L.6 asked Felipe *which* patches decay. He answered by exclusion, which
makes his list complete:

> A shorter than expected sustain during held keydown can be observed with almost all
> instruments of the "ORGAN&ACCORDION" sound group, pages 1/2 and 2/2. The only exceptions are
> Rock Organ (Page 2/2, LCD LEFT 4) and Chapel Organ (Page 1/2, LCD LEFT 3) which do keep
> sounding for as long as a key is held. And Theatre Novelty (Page 2/2, LCD RIGHT 3) does not
> sound at all.

**All twenty rows of that report now reproduce, by name, in one run each.** The thing the rig
was missing was not in the patches at all: it was a **diagnostic CONFIG bit saved in the shared
`kn7000-emulator/cfg/kn5000.cfg`**, which every rig run overwrote with its own private cfg and
therefore could never see.

## M.0 ⚠ RETRACTION — "18 of 20 ORGAN & ACCORDION patches sustain" was never measured

> ⚠ **RETRACTED:** §L.3's twenty-patch listing and the sentence it produced — "*On the shipped
> defaults, 18 of 20 ORGAN & ACCORDION patches sustain a held note indefinitely*" (§L.5) — plus
> the "30 s changes nothing" corroboration that rested on the same runs.

Not "superseded": **unsupported by its own evidence**. The four one-patch runs behind §L.2
(Chapel Organ, Rock Organ, Soul Organ, Theatre Novelty) stand. The twenty-row table did not come
from those; it came from the four ten-patch runs, and **their own LCD snapshots refute them**:

    organ_p1  (10 steps, tags organ:L1..R5)   11 snapshots. Distinct SOUND screens appearing in
              them: "Perc Organ" and "Full Drawbars" -- and then ENTERTAINER / VOCAL REVERB,
              and finally SOUND / **LEFT** / **PIANO** with "Modern E.P.1" selected.
              Chapel Organ, Full Organ, Cathedral Organ, Jazz Drawbars, 16'&1', Bright
              Accordion, Musette and Folk Accordion NEVER APPEAR ON ANY SNAPSHOT.
    organ_p2  (10 steps, tags organ+:L1..R5)  "Accomp Drawbars" on PAGE 2/2 for step 1, then
              **PAGE 1/2 with "Full Drawbars"** from step 2 onward. Nine of ten rows are not
              the patch they are labelled with.

So §L.3's page-1 line is at most two distinct patches reported ten times, and its page-2 line at
most two. §L.1 had written the countermeasure down — "*exactly one LCD snapshot per patch … the
snapshot ordinal IS the patch index*" — but that version of `kn5000_patch_probe.lua` was saved at
21:13 and those runs are from 20:53 and 21:08. **The snapshots were taken and never read.** A
picture that nobody looks at is not a control.

## M.1 The rig this time: ONE PATCH PER RUN, and every name read off the LCD

Twenty patches x two arms = forty runs, **one patch each**, 12 s hold on C4 (MIDI 60), PCM mode,
shipped `KN5000_EGLAW=lin` / `LVL080=on` / `HANDOFF=off` / `UNDUMPED=mute`, private `cfg/`,
`nvram/` and `snapshot/` per run. For every one of the forty, snapshot `0000.png` was cropped to
the LCD and **read**; all forty show `SOUND / RIGHT1 / ORGAN&ACCORDION`, the right PAGE, and the
intended patch highlighted. No run drifted — drift grows with run length and these are one step
long. Selectors are distinct across all twenty (`kn5000_patch_check.py` passes), but the *name*
is what is being relied on, because a distinct-selector check is necessary and not sufficient.

`tools/kn5000_hold_analyze.py --shape` is new and is the measurement §K/§L were missing.
`sus_db` compares the last tenth of a hold with the loudest tenth, so **a patch that falls 20 dB
in three seconds and then holds scores like a patch that never moved** — which is exactly the
difference between "sustains" and "shorter sustain than expected" to a player. `--shape` reports
the level at 0.5 / 1 / 2 / 5 / 10 s relative to the ATTACK PEAK, the first crossing of -3 / -6 /
-12 dB, and per voice `t_ko_rel` / `ko_src` (1 = ended by the real key release, 2 = the
firmware's own `0x7E00` FREE, i.e. torn down mid-hold).

*The measurement can fail, two ways.* The rendered noise floor with no key down is **exactly 0**
on every channel (MEASURED, 3 s window, all three WAV channels), so a decay cannot be hidden by a
floor; and the same metric reads -120 dB on seventeen patches in arm B below and -0.0 dB on the
same patches in arm A.

## M.2 THE CAUSE — Felipe's saved cfg has TGMODE bit 1, the "free voices whose EG has finished" PROBE, turned ON

`~/compartilhado/kn7000-emulator/cfg/kn5000.cfg` (written 20:48, the exit of his session; his
binary is md5 `29ae7a61f754b49a2bc33600ebe66da1`, **byte-identical** to the build tree):

    <port tag=":TGMODE" type="CONFIG" mask="2" defvalue="0" value="2" />

MAME writes a port line only when the value differs from the default, so this is a bit somebody
switched On in the machine-configuration menu and MAME has been restoring ever since. It is
`kn5000.cpp`'s

    PORT_CONFNAME(0x02, 0x00, "  ^ probe: free voices whose EG has finished")

and it is not Felipe's mistake: `notes/FINDINGS-sound-name-error.md` §5, written EARLIER THE SAME
DAY, already records "*the shared `kn7000-emulator/cfg/kn5000.cfg` … only non-defaults are TGMODE
bit 1 (the EG-free probe) and `ENCODER=73`*" — it was noticed, and its consequence for sustain
was never connected. That note also pins the bit as ON before his session.

**What the bit does**, `kn5000_tonegen.cpp` sound_stream_update, one line:

    const bool eg_done = free_on_eg_done && v.eg_seg >= 2 && v.eg_level <= v.eg_target;
    if (mag >= (int64_t(1) << 14) && !eg_done)   // >= 0.5 LSB of the 16-bit output
        v.silent_samples = 0;
    else if (++v.silent_samples >= SILENT_HOLDOFF)   // 98.33 ms, one bank-poll period
    { ...; v.eg_running = false; }

Default OFF, the interlock is calibration-independent and provably inaudible: a voice reports
itself silent only after its own rendered contribution has been below half an output LSB for a
full bank-poll period, so `status_r()` can only report 0 for a voice already contributing
nothing. `status_r()`'s own comment states the consequence — "*while a key is down the EG sits at
its programmed sustain level, so the interlock never arms and the voice is structurally
unreclaimable, for any hold duration*".

**The probe deletes the `mag` term.** A voice whose last EG segment has reached its target is
reported silent *regardless of what it is still rendering*. 98.33 ms later `eg_running` drops,
the firmware's voice manager reads the bitmap, `Voice_Manager_PollBank -> ToneGen_SilenceChannel`
writes `0x7E00` and **deallocates the channel** — while the key is still down and the voice is
still at full level. That is §K.4's teardown, reached from the other side: not by the level
falling, but by the report lying about it.

## M.3 The A/B, all twenty patches, every one LCD-confirmed

One key (C4, velocity 100), 12 s hold, nothing else sounding. Arm A = shipped defaults. Arm B =
identical in every respect **except TGMODE bit 1**. Levels are dB relative to that hold's own
attack peak; `pk` is the attack peak in output LSB, so a level change is separable from a decay.

| # | LCD name | page/key | selectors (bank) | eg2 words | A: probe OFF  0.5/1/2/5/10 s (dB re attack) | B: probe ON | B teardown |
|---|---|---|---|---|---|---|---|
| 1 | **Perc Organ** | 1/2 LEFT 1 | 4002(b1)/4002(b1) | 727F/727F | pk 1784 · -0.1 / -0.1 / -0.0 / -0.0 / -0.1 | pk 1779 · -120 / -120 / -120 / -120 / -120 | 0.16 s src2 |
| 2 | **Full Drawbars** | 1/2 LEFT 2 | 4007(b1)/4007(b1) | 9A76/9A76 | pk 2767 · -0.0 / -0.0 / -0.0 / -0.1 / -0.0 | pk 2755 · -120 / -120 / -120 / -120 / -120 | 0.16 s src2 |
| 3 | **Chapel Organ** | 1/2 LEFT 3 | 4017(b1)/401E(b1)/5011(b1) | 727F/727F/9A00 | pk 602 · -0.1 / -0.5 / -1.1 / -1.1 / 0.4 | pk 568 · -8.1 / -8.0 / -8.1 / -8.1 / -8.1 | 0.16 s src2 (1 partial survives, audible) |
| 4 | **Full Organ** | 1/2 LEFT 4 | 4025(b1)/4025(b1)/401E(b1) | 727F/727F/4A7F | pk 1139 · -2.7 / -1.0 / -1.4 / -1.8 / -1.0 | pk 1116 · -120 / -120 / -120 / -120 / -120 | 0.16 s src2 |
| 5 | **Cathedral Organ** | 1/2 LEFT 5 | 402B(b1)/4032(b1)/4025(b1) | 727F/727F/4A7F | pk 1640 · -3.1 / -2.0 / -2.3 / -3.0 / -1.4 | pk 1387 · -120 / -120 / -120 / -120 / -120 | 0.16 s src2 |
| 6 | **Jazz Drawbars** | 1/2 RIGHT 1 | 400E(b1)/400E(b1) | 9A76/9A76 | pk 3366 · -0.1 / -0.1 / -0.1 / -0.4 / -0.1 | pk 3340 · -120 / -120 / -120 / -120 / -120 | 0.16 s src2 |
| 7 | **16' & 1'** | 1/2 RIGHT 2 | 4011(b1)/4011(b1) | 7A76/7A76 | pk 3443 · -0.0 / -0.0 / -0.0 / -0.0 / -0.0 | pk 3430 · -120 / -120 / -120 / -120 / -120 | 0.16 s src2 |
| 8 | **Bright Accordion** | 1/2 RIGHT 3 | 4037(b1)/4037(b1) | 727F/727F | pk 1689 · -1.8 / -4.5 / -3.7 / -2.4 / -1.7 | pk 1551 · -120 / -120 / -120 / -120 / -120 | 0.16 s src2 |
| 9 | **Musette** | 1/2 RIGHT 4 | 4042(b1)/4042(b1) | 727F/727F | pk 1966 · -1.4 / -4.3 / -3.7 / -1.2 / -1.3 | pk 1821 · -120 / -120 / -120 / -120 / -120 | 0.16 s src2 |
| 10 | **Folk Accordion** | 1/2 RIGHT 5 | 4047(b1)/4042(b1)/404D(b1)/4071(b1) | 727F/727F/4A6C/4A7F | pk 2154 · -0.8 / -2.7 / -2.5 / -2.8 / -1.7 | pk 1871 · -120 / -120 / -120 / -120 / -120 | 0.16 s src2 |
| 11 | **Accomp Drawbars** | 2/2 LEFT 1 | 6096(b1)/6096(b1)/0000(b0)/6050(b1) | 727F/727F/727F/727F | pk 1988 · -0.1 / -0.1 / 0.0 / 0.2 / 0.7 | pk 1988 · -120 / -120 / -120 / -120 / -120 | 0.11 s src2 |
| 12 | **Pop Organ** | 2/2 LEFT 2 | 6096(b1)/6096(b1)/0000(b0)/6050(b1) | 727F/727F/AE00/727F | pk 1353 · -0.1 / -0.1 / 0.0 / 0.5 / 1.1 | pk 1353 · -120 / -120 / -120 / -120 / -120 | 0.11 s src2 |
| 13 | **Soul Organ** | 2/2 LEFT 3 | 6070(b1)/6070(b1)/6070(b1)/6048(b1) | 047C/047C/047C/047C | pk 959 · -21.8 / -21.8 / -21.8 / -21.8 / -21.8 | pk 959 · -120 / -120 / -120 / -120 / -120 | 0.11 s src2 |
| 14 | **Rock Organ** | 2/2 LEFT 4 | 4005(b1)/4007(b1)/6040(b1) | 9A76/9A76/B300 | pk 2731 · -8.7 / -3.1 / 1.5 / -0.9 / 1.3 | pk 2731 · -4.0 / -3.9 / -3.9 / -3.9 / -3.9 | 0.11 s src2 (1 partial survives, audible) |
| 15 | **Organ Bass** | 2/2 LEFT 5 | 6070(b1)/6070(b1) | 727F/727F | pk 2533 · -0.0 / -0.0 / -0.0 / -0.0 / -0.0 | pk 2533 · -120 / -120 / -120 / -120 / -120 | 0.11 s src2 |
| 16 | **Theatre Organ** | 2/2 RIGHT 1 | 402B(b1)/0005(b0)/3195(b0) | 727F/727F/FC00 | pk 495 · -0.1 / 0.0 / -0.5 / -0.5 / 0.0 | pk 454 · -120 / -120 / -120 / -120 / -120 | 0.11 s src2 |
| 17 | **Theatre Accomp** | 2/2 RIGHT 2 | 0005(b0)/0005(b0)/401E(b1) | 727F/727F/727F | pk 472 · -0.4 / -0.2 / 0.0 / -0.0 / -0.0 | pk 472 · -120 / -120 / -120 / -120 / -120 | 0.11 s src2 |
| 18 | **Theatre Novelty** | 2/2 RIGHT 3 | 0000(b0)/0000(b0)/3195(b0) | FF7F/C27F/727F | pk 0 · -120.0 / -120.0 / -120.0 / -120.0 / -120.0 | pk 0 · -120 / -120 / -120 / -120 / -120 | 0.11 s src2 |
| 19 | **Mellow Accordion** | 2/2 RIGHT 4 | 403B(b1) | 727F | pk 1543 · -0.0 / -0.0 / -0.1 / -0.1 / 0.0 | pk 1529 · -120 / -120 / -120 / -120 / -120 | 0.11 s src2 |
| 20 | **Bandoneon** | 2/2 RIGHT 5 | 403B(b1)/403E(b1) | 727F/727F | pk 935 · -0.3 / -0.6 / -1.0 / -0.3 / -0.1 | pk 934 · -120 / -120 / -120 / -120 / -120 | 0.11 s src2 |

**Arm A: twenty of twenty sustain flat** (Soul Organ's -21.8 dB is a 50 ms percussive attack —
its shape is flat at -21.8 dB from 0.1 s to 12 s — and its `047C` segment-2 level `0x04` is the
`Level_Fader` table's maximum attenuation, the "designed to decay" signature; Theatre Novelty is
silent, §M.5). **Arm B: 17 of the 19 AUDIBLE patches are cut to digital silence at 0.11-0.16 s,
every partial `ko_src = 2`.** The two that survive are **Chapel Organ** and **Rock Organ**.
(Stated exactly: 18 of 20 have all their voices freed by the firmware — Theatre Novelty's voices
are freed too, but it was rendering silence anyway, so 17 is the number of patches that AUDIBLY
stop. Both countings are in the table; do not quote the 18 as "18 patches went quiet".)

**That is Felipe's list, patch for patch, with nothing left over.** Both of his named exceptions
are exceptions here; every patch he did not except is cut; and the one patch he says is silent is
silent in both arms. Twenty of twenty rows agree.

### ARM C — his own cfg FILE, copied verbatim, not a reconstruction

Arms A/B set the bit from a cfg the rig writes, which proves the MECHANISM but not that his
file does it. So a third arm ran with `KN5_CFGSRC=~/compartilhado/kn7000-emulator/cfg`, i.e. his
`kn5000.cfg` copied in unchanged — TGMODE bit 1, `ENCODER=73`, and **AREA left at the DIPSWITCH
default `0x06`** rather than the `0x02` the rig has always forced. MEASURED:

    Perc Organ    (1/2 L1)  cut to silence at 0.16 s, both partials ko_src = 2
    Chapel Organ  (1/2 L3)  sounds for the whole 12 s, FLAT at -8.1 dB from 0.5 s to 10 s
    Rock Organ    (2/2 L4)  sounds for the whole 12 s, FLAT at -4.0 dB from 0.5 s to 10 s

Identical to arm B to the tenth of a dB. **His configuration file, on his binary, reproduces his
report** — and the AREA strap makes no difference, which retires that difference too.

## M.4 WHY exactly those two survive — DERIVED, and it is a one-line rule

`eg_done` needs `eg_level <= eg_target` on segment 2. If the segment-2 word's **rate byte is 0**
the EG never steps, `eg_level` stays where segment 1 left it — above the target — and the
condition is never true, so that partial is never freed. The rule is therefore:

> **a patch keeps sounding under the probe iff it has at least one partial whose segment-2 word
> has rate 0 AND whose wave is in a dumped bank.**

    Chapel Organ   ch2  sel 5011  bank 1  eg2 = 9A00   rate 0, REAL  -> survives, AUDIBLE
    Rock Organ     ch2  sel 6040  bank 1  eg2 = B300   rate 0, REAL  -> survives, AUDIBLE
    Pop Organ      ch2  sel 0000  bank 0  eg2 = AE00   rate 0, but bank 0 = MUTED -> inaudible
    Theatre Organ  ch2  sel 3195  bank 0  eg2 = FC00   rate 0, but bank 0 = MUTED -> inaudible
    all other 16   every partial has a non-zero segment-2 rate                    -> all freed

The bank qualifier is not a patch: **it is what makes the rule agree with Felipe rather than
over-predict.** Pop Organ and Theatre Organ do have a rate-0 partial and it does survive the full
12 s in arm B (MEASURED, `ko_src=1`, `t_ko_rel` 12.01) — but it is an undumped-socket partial
rendering silence, so both patches go quiet on schedule and Felipe correctly did not except them.

## M.5 Three corrections and one answer, from the same runs

* ⚠ **RETRACTED: "Theatre Accomp (2/2 RIGHT 2) is silent for the same reason as Theatre
  Novelty"** (§L.4). It is **not silent**. MEASURED, LCD-confirmed: three partials, `0005`/
  `0005` in bank 0 (muted) and **`401E` in bank 1, real, peak 1439** — it plays, quietly, and in
  arm A it sustains flat for 12 s. Theatre Novelty is genuinely all-bank-0 (`0000`/`0000`/`3195`,
  peak 0) and its silence is §J.1's mute working as specified. Partial muting is common in this
  group: Theatre Organ, Accomp Drawbars and Pop Organ each lose one partial the same way.
* **"Does a held note decay with nothing else sounding?" — ANSWERED, no need to ask him.** Every
  run above is one key with nothing else playing: no rhythm, no accompaniment, no second note.
  Arm B still cuts the note at 0.11-0.16 s. Polyphony is not required and §L.5's polyphony
  refutation was correct but irrelevant.
* ★ **The KN5000's on-screen octave numbering is ONE LOWER than MIDI's.** Felipe's "Db4..F#4" is
  **MIDI 73..78**, not 61..66. That was a naming-convention difference and NOT an error in his
  report; `notes/TASK-QUEUE-kn5000-sound.md` already carries the corrected numbers.
* The rig's other uncontrolled difference is now on the record too: `kn5000_capture_patch.sh` has
  always forced `AREA = 0x02` while the driver's DIPSWITCH default — and Felipe's cfg — is
  `0x06`. It is not the cause (arm C below holds his cfg verbatim, AREA and all) but it should
  never have been silently different. `KN5_AREA` now overrides it.

## M.6 What to do

1. **Nothing in the tone generator is wrong here.** Arm A is correct behaviour and matches the
   real instrument as Felipe describes it. The defect is a diagnostic left On in a shared
   configuration file.
2. **Clear the bit in the published tree**: turn "^ probe: free voices whose EG has finished"
   Off in the machine-configuration menu (Tab -> Machine Configuration) and exit, or delete
   `kn7000-emulator/cfg/kn5000.cfg`. Then a held ORGAN & ACCORDION note sustains.
3. **The probe is dangerous as a persisted CONFIG.** It is `PORT_CONFNAME`, so it lives in
   `cfg/*.cfg` forever and silently, and it does not merely change a diagnostic reading — it
   deletes notes. Its own banner already says "*it is NOT a fix and must not be used as one*"
   (§2026-08-05, REFUTED). It should be an environment variable like every other diagnostic in
   this driver, or it should be removed.
4. **Rig rule, added to the list this file keeps**: when reproducing a REPORTED session, hold the
   reporter's whole environment — cfg, nvram, straps — not just the parts the rig knows about.
   `kn5000_capture_patch.sh` now takes `KN5_CFGSRC` / `KN5_NVSRC` (copies, never shared) and
   `KN5_TGPROBE` / `KN5_AREA` so a saved session can be re-run bit for bit.

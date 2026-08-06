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

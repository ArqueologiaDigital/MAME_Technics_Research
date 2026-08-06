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

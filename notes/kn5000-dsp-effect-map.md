# NEC uPD6383GF — the per-effect structural map: all 38 microprogram images

KN5000 IC311 effects DSP (NEC uPD6383GF-3BA). Date: 2026-07-22.
Tool: `tools/kn5000_dsp_effectmap.py` (imports `_extract`, `_class2`, `_biquad`,
`_biquadmap`, `_params`, `_coeffs`; **none of them is edited**).

**Append-only successor material.** This note does not edit
`kn5000-dsp-cursor-general.md`, `-biquad-map.md`, `-biquad-coeffs.md`, `-biquad.md`,
`-reverb.md`, `-class2*.md`, `-coefficients.md`, `-parameters.md`, `-encoding.md`
or `-header.md`. Corrections to them are collected in §8.

Claims are tagged **MEASURED**, **PROVEN BY CONSTRUCTION**, **INFERRED** or
**SPECULATIVE**. §9 lists what is falsified or not established.

Reproduce:

```
python3 tools/kn5000_dsp_extract.py \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom /tmp/progs
python3 tools/kn5000_dsp_effectmap.py \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom /tmp/progs \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_v10_program.rom
```
Sections: `map multitap deficit reverbs compress op76 vocab triplet`.
The `map` section is ~710 lines and is the raw form of §4 below.

---

## Headline

1. **★★★ MULTI TAP DELAY is no longer a failure of the cursor model.** Its
   shortfall is exactly **3**, and the three overrunning class-A words
   (`[52] 000.A.00.1D5  [53] 212.A.00.415  [54] 202.A.00.1D5`) are a verbatim
   repeat — modulo `[0]`'s `hi12`, the field the biquad-map note showed names the
   *bus*, not the operand — of the group at `[47..49]`, which reads
   `0x0C 0x0D 0x0E`. It is the **PARAMETRIC EQ's channel-sharing, in miniature**:
   a second channel re-reading the previous channel's last three coefficients.
   The bank corroborates from the other side: it **already contains the 3-word
   tone filter twice** (`0x08..0x0A` == `0x0B..0x0D`, byte-identical), and the
   host's `op 0x76` writes it at **both** `0x08` and `0x0B`. What is missing is
   only the *encoding* of a −3 rewind (§5). **MEASURED**; the mechanism is
   **INFERRED**.
2. **★★★ A wholly new instruction idiom: the 3-word TABLE-LOOKUP triplet.**
   `xxx.0.00.C63 | 000.6.TT.4CD/407 | 012.4.01.1CE`, always consecutive, 53
   occurrences. It accounts for **every class-4 and every class-6 word in the
   corpus** (53 = 53 = 53), which is why those two class counts are equal in all
   38 images. It is present in exactly the **25 images that have an LFO or a
   distortion stage** and in **none** of the other 13 — **MCC +1.000, TP 25,
   FP 0, FN 0**. The class-6 word's `addr8` is a **table selector**: `0x18/0x1A/
   0x1E/0x20` occur only in LFO-bearing images, `0x28` only in distortion-bearing
   ones (plus `ROCK ROTARY`, which has a drive stage). **MEASURED**; "it is a
   table lookup, shared by the LFO waveform and the waveshaper transfer curve"
   is **INFERRED, strong** (§6).
3. **★★ `op 0x76` writes a fixed 3-word block.** Pre-registered test, run in §7:
   in all **5** images that use it (14 entries), **every** `op 0x76` address is a
   class-A cursor slot, and the three coefficients from it form a one-pole-plus-zero
   damping filter that repeats verbatim at the image's other entries
   (`SINGLE DELAY` 4/4 identical, `GATED REVERB` 2/2, `MULTI TAP DELAY` 2/2,
   `ROOM REVERB 1` 2/2, `ENHANCER` two distinct blocks × 2 channels).
   **PREDICTION MET, MEASURED.** This settles cursor-general §6's "the block it
   writes is not a fixed width" — the width *is* 3; the 3/4/7/8 figures were
   *spacings between placements*, not widths.
4. **★★ `BRIGHT REVERB 2` is fully explained: its coefficient bank is
   ROOM REVERB 1's with ONE EXTRA WORD (`200000` = +0.250) inserted at block index
   3, and everything after it shifted by +1.** Structure for structure, its
   ladder, its three DRAM-stage `0.5`s, its two damping triples and its output
   tails all sit exactly one slot later; the tail block grows 7 → 8 words, giving
   the 38. All twelve presets share **one** `T1` map (`0x1CB72`), so its host
   parameter writes (`op 0x76 -> 0x9E/0xA6`, `op 0x66 -> 0xA9..`) land one slot
   off. **MEASURED** (§3.2). **INFERRED:** a defect in that one preset's data.
5. **★★ The compressor's candidate set drops from eleven families to THREE.**
   cursor-general §4 stated the criterion "present in every compressor stage and
   in no zero-deficit image", but its tool never applied the second half (the
   exclusion loop `for a in progs: pass` is a no-op). Applying it properly leaves
   **`0A2.2.000`, `C40.1.451`, `C40.2.000`** (§5.2). Of these, `C40.2.C0.000`
   is the only one that occurs outside the compressor — in `NO OPERATION`,
   `GATED REVERB`, `AUTO WAH` and `AUTO WAH+S.DELAY`, **all four of which have a
   positive deficit, and no zero-deficit image contains it (TP 8, FP 0)**. The
   *rate* is still not constant, so it is not by itself the consumer.
   **NOT IDENTIFIED**, but the search space is now three words wide.
6. **★★ The compressor `+4` is used as an oracle and passes.** Decoding each
   compressor image's second PEQ section at the *raw* cursor slot yields garbage
   (Q = 1733, Q = 2621); decoding it at `slot + 4` — the host's own `op 0x70`
   address — yields the **identical 50.1 Hz / Q 10 flat default** that every other
   PEQ combination carries. Three images, three hits. **MEASURED** (§4, §5.2).
7. **★ One new section type decoded: `ROCK ROTARY`'s biquad** is a
   **2000.0 Hz, Q = 4.0000 bandpass** with an exact `(1, 0, −1)` numerator — the
   horn/rotor crossover of a Leslie simulation. **MEASURED.** But it **falsifies
   the make-up-gain oracle as a universal law**: its peak |H| is exactly 10.000
   and its sixth coefficient is +1.8000, product **18**, not ±1 (§7.2).
8. **★ `NO OPERATION` is not empty, and that is why it is the two controls' false
   positive** (INDEX backlog item 5). It carries a complete envelope-detector
   block — `2/π = 0.6366` input scale (the same first coefficient as
   `COMPRESSOR`), a `C40` pair at words 13/19, three DRAM writes and two tap
   reads. **MEASURED.**
9. **Coverage: 38 of 38 images mapped, with a plain-English signal flow for each.**
   **25 at *high* confidence** (every class-A word lands on a loaded bank word and
   the structure detectors agree with the host parameter map) and **13 at *medium***
   (topology identified, one or more blocks undecoded). **None at *low*** — but
   "medium" is doing real work: `GATED REVERB`'s gate, `PHASER`'s stage count,
   `AUTO WAH`'s and `ROCK ROTARY`'s private section families, `ENSEMBLE`'s
   `op 0x77` and `NO OPERATION`'s purpose are all genuinely open (§4, §9).

---

## 1. What "mapped" means here

Every entry in §4 is produced by the same battery, applied without per-image
tuning:

| detector | definition | status |
|---|---|---|
| coefficient cursor | +1 per class-A word, reset by `801.0.00.021` | biquad-map §2, cursor-general §1 |
| biquad section | 9-word window within d ≤ 3 of algo 39's `[5..13]` | biquad §1 |
| biquad coefficients | `+0=b1 +1=b0 +2=b2 +3=−a1/a0 +4=−a2/a0` (Q1.22, `+4` Q0.23), `+5` make-up | biquad-map §4 |
| all-pass motif | 8-word reverb stage within d ≤ 1 | reverb §1 |
| all-pass marker | `104.2.00.000` | class2-round2 |
| DRAM write / tap read | `880.1.60.*` / `880.1.20.*` | class2 |
| LFO read | `hi12 = 0x082` | class2-round2 |
| envelope family | `hi12 = 0xC40` | class2-round2 |
| filter-output step | class 8 | biquad-map §6 |
| **table lookup** | the 3-word triplet | **new, §6** |
| delay lengths | mode-`0x0B` records of the parameter stream | coefficients note |
| host map | `T1` opcode → coefficient address | parameters note |

Two caveats stated up front, both **MEASURED**:

* The mode-`0x0B` "delay length" extraction is only sane for some images. Chorus
  family values (200, 650, 1100, 1550 samples = 4.5…35 ms) are exactly right;
  `FLANGER`'s second value 140800 (3193 ms) and `S.DELAY+FLANGER`'s 1964800
  (44.5 s) are not delay lengths at all. Those records carry something else and
  are reported verbatim, not interpreted.
* `find_sections(maxdiff=3)` has false positives inside compressor stages. Where
  the host's `op 0x70` gives one address per section, the tool prefers it and
  says so; where it does not, low confidence is marked.

## 2. The corpus at a glance (MEASURED)

38 distinct images over 96 loadable algorithm slots (5 malformed, excluded).
`NO OPERATION` alone is shared by **42** slots — the KN5000's unimplemented effect
names (`----------`, and also `MODULATION DELAY`, `SLOW ATTACKER`, `NOISE FLANGER`,
which are *named in the ROM but not implemented*). `ROOM REVERB 1`'s image serves
all 12 reverb presets; `ROCK ROTARY`'s serves `ROTARY SPEAKER` too. The other 36
images are one-to-one with an effect.

Only **one** image loads into effect unit 1: the reverb, at I-RAM 200, bank base
`0x90`, terminator `addr8 = 0x0F`. All 37 others load at I-RAM 84, bank base
`0x00`, terminator `addr8 = 0x0E`. This reproduces cursor-general §1.2's `+0x80`
unit-1 displacement and adds that **no other effect is ever built for unit 1** —
the reverb is the unit-1 program.

## 3. The reverb family

### 3.1 Ladders across the twelve presets (MEASURED)

Unchanged from cursor-general §3.4 for 9 of 12. One correction:

* `PLATE REVERB 2` does carry `ROOM REVERB 1`'s gain multiset
  `{0.75 0.63 0.62 0.52 0.50 0.40}` permuted.
* **`BRIGHT REVERB 1` does NOT.** Its stage gains are
  `0.600 0.630 0.300 0.400 0.750 | 0.630 0.620 0.420 0.520` — the multiset
  contains **0.300 and 0.420, which appear in no other preset**, and lacks 0.500.
  cursor-general §3.4's "PLATE REVERB 2 **and BRIGHT REVERB 1** carry the same
  multiset permuted" is half right. **CORRECTED** (§8).

### 3.2 `BRIGHT REVERB 2`, explained (MEASURED)

Its first op-2 block is still 30 words at `0x90`; its second grows from 7 to 8.
Aligned against `ROOM REVERB 1` by role:

```
   role                       ROOM 1 block idx     BRIGHT 2 block idx
   input scaling triple            0,1,2                0,1,2
   -- inserted word 200000 --        --                   3
   damping triple #1               3,4,5                4,5,6
   DRAM stage (0.500)                6                    7
   op 0x75 slot (0.200)              7                    8
   chain-0 ladder                  8..12                9..13
   DRAM stage (0.500)               13                   14
   damping triple #2              14,15,16            15,16,17
   chain-1 ladder                 17..20               18..21
   DRAM stage (0.500)               21                   22
   damping triple #3              22,23,24            23,24,25
   LEFT output tail               25..28               26..29
   RIGHT output tail          29 + block2[0..2]   block2[0..3]
```

Every role lands **exactly one slot later**, and the extra word is a plain
`200000` (+0.250) at index 3. The 38th word is the consequence, not a separate
anomaly. **MEASURED.** Because all twelve presets share `T1 = 0x1CB72`, the host
still writes `op 0x76 -> 0x9E, 0xA6` and `op 0x66 -> 0xA9..0xB2`; for this preset
those addresses hit the *second* word of damping triple #2 and the tail one word
early. **INFERRED:** this preset's coefficient table is off by one — a data
defect. **SPECULATIVE alternative:** a deliberate 4-word input group for this one
preset, in which case the host's writes are the ones that are wrong.

### 3.3 The DRAM bracket counts (MEASURED, and a caution)

Counting `880.1.60.*` and `880.1.20.*` separately over the whole corpus, the two
are **not** equal in most images (`ROOM REVERB 1`: 13 writes / 14 reads;
`GATED REVERB` 10/9; `MULTI TAP DELAY` **2 writes / 4 reads**). The multi-tap
case is the informative one: one write and **four** reads is exactly what a
multi-tap delay line is. So `880.1.60` / `880.1.20` are best read as **write** and
**tap read**, not as a matched open/close bracket pair. cursor-general §3.2's
"12 balanced brackets" in the reverb is a count of *paired occurrences*, which
still holds for that image's motif region, but "balanced" is not a corpus-wide
property. **MEASURED**, interpretation **INFERRED**.

## 4. THE MAP

Format: name(s) · unit / load · size · structure · coefficients · flow.
Confidence: **high** = every class-A word lands on a loaded bank word and the
structure detectors agree with the host map; **medium** = structure identified
but some blocks undecoded; **low** = little beyond counts.

### Family: reverb / ambience

**`ROOM REVERB 1` (algo 16; image shared by algos 16–27: ROOM 1/2, PLATE 1/2,
CONCERT 1/2, DARK 1/2, BRIGHT 1/2, WAVE 1/2)** — *confidence: **high***
Unit 1, I-RAM 200, 133 words. Classes `1:33 2:67 A:33`. 33 class-A, bank 37 at
`0x90`, deficit **+3**. 13 DRAM writes, 14 tap reads. 9 all-pass motifs at
`19 27 35 43 51 | 69 77 85 93`, 9 `104.2.00.000` markers, 4 `C40` words.
Coefficients (ROOM 1): input triple `0x90-92` = +0.250 +0.500 +0.500; damping
triple #1 `0x93-95` = +0.384 +0.198 −0.206; single-multiply DRAM stages
`0x96/0x9D/0xA5` = +0.500 each; `op 0x75` slot `0x97` = +0.200; chain-0 ladder
`0x98-9C` = 0.750 0.630 0.520 0.500 0.400; damping #2 `0x9E-A0` and #3 `0xA6-A8`
= +0.438 +0.363 −0.415 (both written by `op 0x76`); chain-1 ladder `0xA1-A4` =
0.630 0.620 0.520 0.400; left tail `0xA9-AC` = 0.358 0.500 0.493 0.390; right
tail `0xAD-B0` = 0.200 0.200 0.450 0.500. `0xB1-B4` loaded, never reached.
*Flow:* input × 0.25 → pre-delay write → damping filter → five all-pass diffusers
in series (descending gains 0.75 → 0.40) → DRAM stage → damping filter → four
more diffusers → DRAM stage → damping filter → two 4-tap output mixes, left and
right. A classic Schroeder/Moorer reverberator with a nine-stage diffuser network.

**`GATED REVERB` (algo 8)** — *confidence: **medium***
Unit 0, 102 words. `1:21 2:58 3:1 A:22`. 22 class-A, bank 27, deficit **+4**.
10 DRAM writes / 9 tap reads, **5** all-pass motifs (`13 21 39 47 55`), 6 all-pass
markers, 2 `C40` words at 82/86. Cursor: input pair `0x00/0x01` = +0.250,
`0x02` = +0.500, `0x03` = **−0.245**, then two ladders of three
(`0x04-06` = 0.7059 0.7203 0.7350 and `0x0B-0D` = the same three) each followed by
an `op 0x76` damping triple (`0x07-09` and `0x0E-10` = +0.273 +0.307 −0.131),
then `0x11` = 0.6366 = 2/π, `0x12` = 0.500 and a **gate tail** `0x13 0x14 0x15`
= +0.0019 +0.0019 +0.0005 fed by the `C40` envelope words.
*Flow:* input → pre-delay → three all-pass diffusers with *ascending* gains →
damping → three more → damping → envelope detector (2/π scaling) drives a gate
whose three tiny coefficients are the attack/hold/release rates written by
`op 0x6F`/`op 0x6D` → output. The +4 deficit and the two host writes at
`0x16/0x17` sit inside the gate block. **NOT fully decoded:** the gate's exact
arithmetic.

### Family: delay

**`SINGLE DELAY` (algo 9)** — *confidence: **high***
48 words, `1:7 2:23 A:18`, 18 class-A, bank 19, deficit **0**. 3 DRAM writes /
2 tap reads. No LFO, no biquad. Cursor: per channel — `0.0 0.0` (host `op 0x73`
writes the two feedback/level words), `0.500`, then **two identical `op 0x76`
damping triples** `+0.2734 +0.3871 −0.2073`. The whole 18-word walk is that
9-word group, twice, one per channel.
*Flow:* input → DRAM write → tap read → damping filter → feedback multiply →
sum; ×2 channels. `op 0x67 -> 0x26, 0x28` are the DRAM delay-length registers.

**`MULTI TAP DELAY` (algo 10)** — *confidence: **high** (see §5.1)*
68 words, `0:2 1:8 2:40 A:18`, 18 class-A, bank **15**, deficit **−4**.
**1 DRAM write, 4 tap reads** at words 12/16/20/24. Cursor: `0x00 0x01` = +0.250
(input L/R), `0x02` = +0.500, **`0x03-06` = 0.500 0.350 0.150 0.000 = the four
tap levels, and the host's `op 0x66` writes exactly `0x03 0x04 0x05 0x06`** —
four consecutive host addresses on four consecutive class-A words at `[27..30]`.
`0x07` = +0.025 (feedback, host `op 0x73 -> 0x07`); `0x08-0A` and `0x0B-0D` = the
same damping triple twice (`op 0x76 -> 0x08, 0x0B`); `0x0E` = +0.250.
*Flow:* input × 0.25 → one DRAM write → four taps read at four displacements →
each scaled by its own level → summed → damping filter → feedback ×0.025 →
per-channel output mix. The last three class-A words are channel 1's copy of the
output mix and re-read `0x0C 0x0D 0x0E` (§5.1).

**`S.DELAY+S.DELAY` (algo 65)** — *confidence: **high***
68 words, 16 class-A, bank 17, deficit **0**. 5 DRAM writes / 4 tap reads.
Cursor is four repeats of `0.0 0.0 0.500 0.300` — two delay lines × two channels,
each with a host-written pair (`op 0x73`, 8 addresses) plus a 0.5 mix and a 0.3
feedback. *Flow:* two independent single delays in series/parallel per channel.

### Family: chorus / ensemble

All members share one skeleton: **LFO read (`082.*`) → table-lookup triplet →
modulated DRAM tap read → mix**. The `C40.3.20.44C` + `A00.0.00.041` pair that
precedes each tap read is the *fractional-delay interpolation* step
(**INFERRED**, §6.3), which is why it appears in chorus/vibrato/rotary and not in
flanger (whose taps are not interpolated).

**`CHORUS` (algo 1)** — *confidence: **high***
70 words, 19 class-A, bank 20, deficit **0**. 4 tap reads, delays
**200 / 720 / 1240 / 1760 samples = 4.54 / 16.3 / 28.1 / 39.9 ms**. 5 LFO reads,
4 `C40.3` interpolation words, **2 triplets: table `0x18` and table `0x20`** —
i.e. a main LFO waveform plus one phase-shifted second read. Coefficients: mostly
zeros (host-written depth/rate), `0x06/0x07` = +0.350 (wet levels),
`0x09/0x0A` = +0.500, `0x0B/0x0C` = −0.250 (the phase-inverted cross-mix that
makes it stereo), `0x11/0x12` = +0.350.
*Flow:* input → DRAM write → two LFO-modulated taps per channel (4.5–40 ms) →
interpolated → ±0.25 cross-mixed and ×0.35 wet → summed with dry.

**`MODULATED CHORUS` (algo 2)** — *confidence: **high***
85 words, 25 class-A, bank 26, deficit 0. Delays 200/650/1100/1550. 6 LFO reads,
**3 triplets** (`0x18`, `0x18`, `0x20`). Two modulators (a second LFO modulates
the first's depth — hence the name), otherwise `CHORUS`'s topology with an extra
0.060 depth pair.

**`ENSEMBLE` (algo 6)** — *confidence: **medium***
96 words, 15 class-A, bank 16, deficit 0. 3 DRAM writes / **6 tap reads**, delays
`200 200 200 664 664 664` — **three voices per channel**. 7 LFO reads and
**4 triplets with four different tables `0x18 0x1A 0x20 0x1E`** — the strongest
evidence for the phase-shifted-LFO reading: an ensemble needs several
decorrelated modulators. Every bank word is 0.0 except `0x01` = +1.000; all
levels come from the host, and it is the only image using `op 0x77`
(6 entries at `0x02 0x04 0x06 0x09 0x0B 0x0D`). *Flow:* one delay line, six
independently modulated taps, host-set levels. **`op 0x77` still undecoded.**

**`MIX UP` (algo 56)** — *confidence: **medium***
64 words, 15 class-A, bank 16, deficit 0. 2 tap reads (200/640 samples), 5 LFO
reads, 3 triplets (all table `0x18`), `op 0x68` writes 3 addresses. Alternating
`0.0001 / 1.0000` pairs at `0x00..0x05` = three LFO phase accumulators.
*Flow:* three modulators driving two short taps and a 0.5 mix — a
multi-voice detune/"mix up" doubler.

**`VIBRATO` (algo 50)** — *confidence: **high***
53 words, 12 class-A, bank 13, deficit 0. 2 tap reads (200/620 = 4.5/14.1 ms),
4 LFO reads, 2 triplets (`0x18`), 2 `C40.3` interpolation words. Bank is two
`0.0001 / 1.0000` accumulator pairs plus two `0.500` mixes.
*Flow:* 100 % wet LFO-modulated delay, one tap per channel — pitch modulation
with no dry path.

**`S.DELAY+CHORUS` (algo 64)** — *confidence: **high***
95 words, 23 class-A, bank 24, deficit 0. 6 tap reads; delays **6850 / 7170 /
15025 / 15345 samples = 155 / 163 / 341 / 348 ms** (the long delay) plus the
chorus taps. 5 LFO reads, 2 triplets (`0x18`, `0x1E`). `0x02/0x0E` = +0.300
(delay feedback), `0x04/0x10` = +0.400, `0x0A/0x16` = +0.250.
*Flow:* a 155 ms delay with 0.3 feedback into a two-voice chorus.

**`S.DELAY+VIBRATO` (algo 67)** — *confidence: **high***
86 words, 22 class-A, bank 23, deficit 0. Delays 7825 / 15900 (177 / 361 ms).
Same construction with the vibrato block substituted.

### Family: flanger / phaser

**`FLANGER` (algo 4)** — *confidence: **medium***
65 words, 18 class-A, bank 19, deficit 0. 4 tap reads, 2 LFO reads, 2 triplets,
**no `C40` interpolation words**. Bank per channel: `0.300` (feedback),
`0.0`, **`0.0039`** (= 1/256, the sweep step), `0.0`, `0.0`, `0.0`, `1.0000`
(LFO accumulator), `0.0`, `0.500`. `op 0x6C -> 0x50, 0x52` addresses the second
space (state), `op 0x68` the LFO.
*Flow:* input → short DRAM delay swept by the LFO → 0.3 regeneration → 0.5 mix.
The mode-`0x0B` values 12800 and 140800 are not usable as delay lengths (§1).

**`PHASER` (algo 5)** — *confidence: **medium***
106 words, only 14 class-A, bank 15, deficit 0. **No DRAM at all** — a true
all-pass phaser. 2 `104.2.00.000` all-pass markers at 41/100, 2 LFO reads,
2 triplets. Class histogram `2:83` — 83 of 106 words are class 2, by far the
highest ratio in the corpus, consistent with a long chain of non-multiplying
all-pass state shuffles. Coefficients: `0x02/0x0A` = +0.300 (feedback),
`0x05/0x06` and `0x08/0x09` = `0.0250 / 0.4380` — **two identical (sweep-step,
centre) pairs, one per channel**, `0x0D` = 1.000.
*Flow:* input → a chain of first-order all-pass sections whose common coefficient
is swept by the LFO around 0.438 with step 0.025 → 0.3 feedback → mixed with dry.
**NOT decoded:** the number of all-pass stages (the two markers bracket the
chain rather than counting it).

**`S.DELAY+FLANGER` (algo 66)**, **`S.DELAY+PHASER` (algo 68)** —
*confidence: **medium***
100 / 110 words, 28 / 22 class-A, deficit 0 both. Each is a 0.5-mix, 0.3-feedback
single delay followed by the corresponding modulator block, coefficient for
coefficient (`0.300` feedback, `0.150` output trim, the `0.0039` or
`0.0500/0.4380` sweep pair). `S.DELAY+PHASER` keeps the two all-pass markers.

### Family: EQ / filter

**`PARAMETRIC EQ` (algo 39)** — *confidence: **high** (the reference)*
105 words, **60 class-A**, bank 31, deficit **−30** (the channel-sharing rewind
`801.0.00.021` at word 58). 10 biquad sections at `5 14 23 32 41 | 59 68 77 86 95`,
10 class-8 steps. Defaults invert to **5000, 250, 2500, 4000, 6300 Hz, all
Q = 0.1000**, bands 2–5 exactly flat, make-up −2.0000 in every band. Host
`op 0x70 -> 00 06 0C 12 18 | 64 68 6C 70 74` (the second group = channel-1 state
bases). *Flow:* 5 cascaded peaking biquads per channel, shared coefficients,
separate state.

**`ENHANCER` (algo 3)** — *confidence: **medium***
99 words, 26 class-A, bank 27, deficit 0. **4 all-pass markers** at 17/34/65/81,
2 tap reads (7718 / 15437 samples = 175 / 350 ms), 2 LFO reads, 2 `C40` words,
and **the only `filt`-labelled image with no class-8 word** (biquad-map §9).
`op 0x76` writes **four** 3-word blocks: `0x00-02` = +0.0035 +0.0035 +0.4723 and
`0x04-06` = −0.1093 +0.1093 +0.3745, each once per channel. `0x08/0x09/0x0A` and
`0x15/0x16/0x17` = 0.500 ×3.
*Flow:* two `op 0x76` shelving/damping filters per channel (one near-DC pair, one
±0.109 differencing pair — a high-frequency extractor), an all-pass pair, and a
175 ms delayed path summed at 0.5. **NOT decoded:** why it has no class-8 word.

**`EXCITER` (algo 35)** — *confidence: **high***
69 words, 22 class-A, bank 23, deficit 0. 2 biquad sections (18, 53), 2 class-8
steps, **2 triplets on table `0x28`** — the distortion table. Biquad = **4000.0 Hz
Q 0.1000 bandpass**, exact `(1, 0, −1)` numerator, make-up +1.0000.
*Flow:* band-split at 4 kHz → the extracted band through the `0x28` transfer
curve (harmonic generation) → `0x08/0x09/0x0A` = 0.5 mixes back with the dry
path. Per channel, twice.

**`AUTO WAH` (algo 52)** — *confidence: **medium***
72 words, 13 class-A, bank 15, deficit **+1**. No DRAM. 1 `C40` word at 27,
2 class-8 steps at 14/67, and the **second, undecoded 9-word filter family**
(`804.8.16.1DA`, biquad-map §9). Coefficients: `0x00` = −1.0000, `0x01/0x02` =
+0.9950 (the swept pole pair), `0x03` = **0.6366 = 2/π** (envelope input scale),
`0x04` = 0.500, `0x05/0x06` = 0.0048 / 0.0005 (envelope attack/release),
`0x09/0x0A` = 0.025 / 1.000, `0x0C` = 0.9992.
*Flow:* envelope follower (2/π scale, two time constants) sweeps a resonant
state-variable filter whose pole radius is 0.995. **NOT decoded:** the
`804.8.16.1DA` section itself; the +1 deficit is inside it.

### Family: dynamics

**`COMPRESSOR` (algo 36)** — *confidence: **medium***
Only 40 words, 10 class-A, bank 19, deficit **+8** (4 per stage × 2 stages).
No DRAM, no filter, **4 `C40` words at 5/12/26/33** = two per channel.
Coefficients: `0x00` = 0.6366 = 2/π, `0x01` = 0.500, `0x02/0x03` = 0.0019
(attack/release), `0x04` = 0.750 (threshold/ratio), then the same again for
channel 1 with `0x06` = −0.500 and `0x07` = 0.250.
*Flow:* rectify → 2/π scale → one-pole smoother (0.0019) → gain computer
(0.750 knee, ±0.500/0.250 slope terms) → apply. Host `op 0x72 -> 0x04, 0x0D`
(the threshold, at in-stage offset +4) and `op 0x6D -> 0x02 0x03 0x0B 0x0C`
(the two time constants per channel).

### Family: distortion

**`DISTORTION` (algo 32)** and **`FUZZ` (algo 34)** — *confidence: **high***
42 words each, **6 class-A**, bank 7, deficit 0 — the two smallest programs.
Two triplets on table `0x28`, no DRAM, no filter. Bank is
`drive, 0.0, output` twice: `DISTORTION` = **0.9874 / 0.0 / 0.0500**,
`FUZZ` = **1.0000 / 0.0 / 0.0200**. Host `op 0x61 -> 0x00, 0x03` (drive) and
`op 0x62 -> 0x02, 0x05` (level).
*Flow:* input × drive → table `0x28` transfer curve → × output level. Per channel.
The two effects are the **same program** with different defaults — `FUZZ` is
harder-driven (1.0 vs 0.987) and quieter (0.02 vs 0.05).

**`OVERDRIVE` (algo 33)** — *confidence: **high***
63 words, 18 class-A, bank 19, deficit 0. Adds a **4000.0 Hz Q 0.7070 Butterworth
lowpass** (exact `(1,2,1)` numerator, DC gain 0.6666, make-up +1.5001 —
the make-up-gain identity, product +1.000) after the `0x28` table.
*Flow:* × drive (1.0) → table `0x28` → 4 kHz Butterworth lowpass with unity
make-up → × level (0.100). Per channel. This is `DISTORTION` plus a tone stage.

### Family: rotary

**`ROCK ROTARY` (algo 15; also `ROTARY SPEAKER`, algo 53)** —
*confidence: **medium***
86 words, 33 class-A, bank 38, deficit **+4**. 1 DRAM write / 3 tap reads
(delays 160 / 502 / 862 samples = 3.6 / 11.4 / 19.6 ms), 3 LFO reads, **5 `C40`
words** (3 `C40.3` interpolation + 2 `C40.0.00.1DA`), 1 triplet on table `0x28`,
2 class-8 steps, 1 biquad at word 17 and a second, undecoded 9-word section
family (`80A.8.16.000`).
**The biquad decodes to a 2000.0 Hz, Q = 4.0000 bandpass**, exact `(1, 0, −1)`
numerator, make-up +1.8000. Coefficients: `0x00/0x01` = 0.0575 (input),
`0x0E/0x12` = ~1.0 and `0x10/0x14` = 0.320 / 0.420 (the two rotor speeds,
host `op 0x69 -> 0x0F, 0x13`), `0x16/0x17` = −0.867 / +0.929 (a second, sharper
resonator), `0x1C/0x1D` = 0.0035.
*Flow:* drive stage (table `0x28`) → 2 kHz Q 4 crossover splitting horn from
rotor → each half amplitude- and delay-modulated by its own LFO (3.6 / 11.4 /
19.6 ms taps, interpolated) at independent rates 0.320 and 0.420 → summed.
**NOT decoded:** the `80A.8.16.000` section; the +4 deficit.

### Family: pan / tremolo / ring

**`AUTO PAN` (algo 48)** — *confidence: **high***
50 words, 8 class-A, bank 9, deficit 0. No DRAM. 2 LFO reads, 2 triplets
(`0x18`). Bank: `0.250`, then `0.0 / 1.0000` twice (two LFO accumulators),
`0.0`, `0.250`. *Flow:* one LFO through table `0x18` produces a gain pair;
the two channels multiply by complementary values. Tremolo is the same program
with the two gains in phase.

**`RING MODULATOR` (algo 54)** — *confidence: **high***
46 words, 6 class-A, bank 7, deficit 0. 2 LFO reads, 2 triplets (`0x18`).
Bank: `0.0227 / 1.0000 / 0.0` twice — carrier frequency increment, accumulator
scale, phase. *Flow:* the LFO accumulator runs at audio rate; table `0x18` turns
phase into a sine; the input is multiplied by it. Per channel.

### Family: combinations

All ten follow the same construction rule: a **one-band** PEQ section
(default 50.1 Hz, Q 10.0181, exactly flat — `b ≡ a`, make-up −2.0000) per
channel, with the coefficients **not** shared between channels, plus one or two
of the standalone effect blocks verbatim.

* **`PEQ+CHORUS` (71)** *high* — 93 w, 31 class-A, bank 32, def 0. 2 biquads
  (`0x02`, `0x12`), 4 tap reads (200/520/840/1160), 5 LFO reads, 2 triplets
  (`0x18`, `0x1E`). Chorus block with wet 0.250/0.150.
* **`PEQ+S.DELAY` (72)** *high* — 54 w, 20 class-A, bank 21, def 0. 2 biquads
  (`0x00`, `0x0A`), 0.500 mix and 0.150 feedback per channel.
* **`PEQ+FLANGER` (73)** *high* — 91 w, 32 class-A, def 0. Biquads at `0x04`,
  `0x14`; flanger's 0.300/0.0039/0.150 triplet per channel.
* **`PEQ+VIBRATO` (74)** *high* — 77 w, 26 class-A, def 0. Biquads at `0x04`,
  `0x11`; vibrato's two accumulator pairs and 0.500 mix.
* **`PEQ+COMPRESSOR` (75)** *high* — 59 w, 22 class-A, bank 31, def **+8**.
  Biquad #1 at `0x00`; biquad #2's cursor slot is `0x0B` but the host writes
  `0x0F` — **+4, and at `0x0F` it decodes to the identical flat 50.1 Hz default**
  (§5.2). Compressor block at `0x06..0x0A` and `0x15..`.
* **`PEQ+COMPR+DIST` (96)** *high* — 90 w, 30 class-A, bank 39, def **+8**.
  Same, with `+4` verified again (cursor `0x0F`, host `0x13`), plus
  `DISTORTION`'s drive/level pair at `0x0F/0x11` and two `0x28` triplets.
* **`PEQ+COMPR+OVERDR` (97)** *high* — 97 w, 36 class-A, bank 45, def **+8**.
  `+4` verified a third time (cursor `0x12`, host `0x16`). 4 class-8 steps: the
  overdrive tone biquad is present too.
* **`PEQ+DIST+DELAY` (98)** *high* — 92 w, 28 class-A, def 0. Two flat PEQ
  bands, distortion drive 1.0 / level 0.0625, delay 0.500 mix / 0.300 feedback.
* **`PEQ+OVERDR+DELAY` (99)** *high* — 104 w, **40 class-A**, bank 41, def 0.
  **4 biquad sections**: two flat PEQ bands and **two copies of `OVERDRIVE`'s
  4000 Hz Q 0.707 Butterworth with make-up +1.5001** — the same block, byte for
  byte, as the standalone effect. The cleanest demonstration in the corpus that
  these are compiled from a common library.
* **`AUTO WAH+S.DELAY` (70)** *medium* — 105 w, 21 class-A, bank 23, def **+1**.
  `AUTO WAH`'s block (2/π, 0.995 pair, 0.0048/0.0005, 0.9992) plus a 0.500/0.300
  delay. The +1 sits in the wah block, as in the standalone.

### Family: null

**`NO OPERATION` (algo 0; image shared by 42 slots)** — *confidence: **medium***
49 words, 8 class-A, bank 11, deficit **+2**. 3 DRAM writes / 2 tap reads,
**2 `C40` words at 13/19**, no `T1` map at all (it uses the shared `NULL_T1`).
Coefficients `0x00` = **0.6366 = 2/π**, `0x01` = 0.500, `0x02` = 0.0048,
`0x03` = 0.0019, `0x04` = 0.0500, `0x05` = 1.0000, `0x06` = 0.9991,
`0x07` = 0.9629. Those are an envelope detector's constants, identical in kind to
`COMPRESSOR`'s and `AUTO WAH`'s.
*Flow (INFERRED):* a dry pass-through that still runs a level detector — most
plausibly the panel's effect-level metering, or a de-click/mute ramp
(0.9991/0.9629 are one-pole smoothers). **This explains INDEX backlog item 5:**
`NO OPERATION` trips the `env` and `dram` controls because it genuinely contains
those blocks, not because the controls are wrong.

## 5. Mining the failures

### 5.1 `MULTI TAP DELAY` — resolved as channel sharing (§Headline 1)

The facts, all **MEASURED**:

* 18 class-A words, 15-word bank, shortfall **3** (the `−4` is `bank − classA − 1`
  and the `−1` is the spare-word convention; the actual overrun is 3 slots).
* The overrunning words are the **last three of the program**, `[52][53][54]`.
* They are `000.A.00.1D5 / 212.A.00.415 / 202.A.00.1D5`; the group at
  `[47][48][49]` is `202.A.00.1D5 / 212.A.00.415 / 202.A.00.1D5`. **The only
  difference is `[0]`'s `hi12`, 000 vs 202** — and biquad-map §5 measured that
  `hi12` of a group's first word names the *stage's source bus*, not an operand.
  So these are the same three instructions reading a different input.
* `[47][48][49]` read `0x0C 0x0D 0x0E`. If `[52][53][54]` re-read them the pair
  becomes channel 0 / channel 1 of one output stage.
* The bank **already duplicates** its 3-word tone filter (`0x08..0x0A` ==
  `0x0B..0x0D` byte for byte) and the host writes it twice (`op 0x76 -> 0x08`
  and `-> 0x0B`). Per-channel duplication of 3-word blocks is this program's
  established habit; the final block is where the duplication stops.

Three candidate mechanisms, and what can be said about each:

1. **An unrecognised partial rewind.** The only two words between the groups are
   `[50] 202.2.00.407` and `[51] 000.2.01.000`. Control (tool section
   `multitap`): `202.2.00.407` occurs in **1** zero-deficit image
   (`SINGLE DELAY`) and `000.2.01.000` in **4**. So neither is a *dedicated*
   rewind, though either could carry one in an unexamined field.
   **NOT EXCLUDED, NOT ESTABLISHED.**
2. **Wrap-around of the cursor at the bank size.** Would give `0x00 0x01 0x02`
   = +0.250 +0.250 +0.500. **EXCLUDED as a general mechanism**: the PARAMETRIC
   EQ needs an explicit `801.0.00.021` to rewind 30 slots, which a size-modulo
   cursor would make unnecessary; and an 8-bit hardware pointer wraps at 256, not
   at 15.
3. **Three of the 18 class-A words do not consume.** Cannot be excluded, but
   would be the only such case in the corpus, and it would have to fall exactly
   on a three-word repeated group.

> **VERDICT: `MULTI TAP DELAY` is not evidence against the cursor.** The shortfall
> equals, exactly, the size of a terminal group that repeats the preceding group —
> the same phenomenon as the PARAMETRIC EQ's `−30`, at 3 words instead of 30.
> What remains unknown is the **encoding of a partial rewind**, which is a much
> smaller and much better-posed question than "why does the cursor overrun".
> **MEASURED** facts, **INFERRED** mechanism.

### 5.2 The compressor's `+4`

**Correction first.** cursor-general §4 reports eleven candidate families as
"present in every compressor stage and in **no** zero-deficit image". Its tool
(`kn5000_dsp_cursorgen.py`, `sec_compress`) builds an empty `zero` set with a
no-op loop and never applies the second condition. Six of the eleven —
`000.2.40E` among them, which occurs in 77 of 96 algorithms — fail it outright.

Applying the stated criterion (tool section `compress`) leaves **three**:

```
   0A2.2.000      2 per compressor image, in no other image at all
   C40.1.451      2 per compressor image, in no other image at all
   C40.2.000      2 per compressor image, and in 4 OTHER images
```

The third is the interesting one. Its four other homes are `NO OPERATION` (+2),
`GATED REVERB` (+4), `AUTO WAH` (+1) and `AUTO WAH+S.DELAY` (+1) — **every one
has a positive deficit, and no zero-deficit image contains it: TP 8, FP 0,
FN 2** (the two false negatives, `ROCK ROTARY` +4 and `ROOM REVERB` +3, contain
other `C40`-family words instead: `C40.0.00.1DA` ×2 and `C40.1.*` ×4). The same
holds for the class-A word `hi12 = 0x018` (`018.A.*.1D5`), which occupies the same
eight images (MCC +0.864 against `deficit > 0`).

Quantitatively it does **not** close: deficit ÷ `C40.2` count is 2, 4, 4, 1, 1, 4,
4, 4 across the eight. So "each `C40.2` word fetches N coefficients" is false for
any fixed N — the same shape of failure that killed the "two per `C40`" reading
in cursor-general §4, now with the *class-restricted* version tested too.

> **VERDICT: narrowed, not identified.** The consumer lies in the three-family
> set `{0A2.2.000, C40.1.451, C40.2.000}`; `C40.2.C0.000` is the only member
> whose presence predicts a positive deficit outside the compressor (8/8, no
> false positives), and it is therefore the leading candidate; but its per-image
> *rate* is not constant, so it cannot be the whole story. **Plainly: I cannot
> narrow it below three, and I cannot make any of the three account for the
> arithmetic.**
>
> **The `+4` itself is now confirmed a fourth and fifth time, as an oracle.**
> Decoding each compressor image's second PEQ biquad at its raw cursor slot gives
> nonsense (Q = 1733.7, Q = 2621.8, an unstable-looking `b`); decoding it at
> `slot + 4` — where the host's `op 0x70` says it is — gives the **identical**
> `800C7F 400000 3FF455 7FF380 801755 800000` = 50.1 Hz, Q 10.0181, `b ≡ a`,
> make-up −2.0000 that every other PEQ combination carries. Three images, three
> hits, on a quantity (a filter's stability and centre frequency) that a wrong
> offset destroys. **MEASURED.**

### 5.3 The twelve `bank != classA + 1` images, classified

| algo | effect | deficit | classification |
|---|---|---|---|
| 39 | PARAMETRIC EQ | −30 | **EXPLAINED** — `801.0.00.021` rewind, 30 shared words |
| 10 | MULTI TAP DELAY | −4 | **EXPLAINED in substance** (§5.1) — 3-word channel repeat; rewind encoding unknown |
| 16 | ROOM REVERB 1 | +3 | **PARTLY** — unit-1 base `0x90` is accounted for; the 3 words `0xB1..0xB4` are loaded and host-written (`op 0x66`) but never reached. Two consumers bounded to `{202.2.08.1CD, 090.2.FB.40E, 212.2.05.000}` (cursor-general §3.3) |
| 36 | COMPRESSOR | +8 | **BOUNDED** (§5.2) — 4 per stage × 2 |
| 75 | PEQ+COMPRESSOR | +8 | same |
| 96 | PEQ+COMPR+DIST | +8 | same |
| 97 | PEQ+COMPR+OVERDR | +8 | same |
| 52 | AUTO WAH | +1 | **UNEXPLAINED**, but localised to the `804.8.16.1DA` section family, the only block `AUTO WAH` has that zero-deficit images lack |
| 70 | AUTO WAH+S.DELAY | +1 | same block, same deficit — a **presence-and-absence control that passes**: the delay half contributes 0 |
| 8 | GATED REVERB | +4 | **UNEXPLAINED**; contains `C40.2.000`, 1 occurrence |
| 15 | ROCK ROTARY | +4 | **UNEXPLAINED**; localised to the `80A.8.16.000` section family (present only here and in `PEQ+COMPR+OVERDR`) |
| 0 | NO OPERATION | +2 | **UNEXPLAINED**; contains the envelope block (§4) |

Score: 2 explained, 1 partly, 4 bounded to one block each, 2 localised to a named
undecoded section, 3 unexplained.

## 6. The table-lookup triplet (new vocabulary)

### 6.1 The idiom (MEASURED)

```
   xxx.0.00.C63      class 0, lo12 = 0xC63     hi12 = 040 (x46) or 142 (x7)
   000.6.TT.4CD      class 6, addr8 = TT       lo12 = 4CD (x46) or 407 (x7)
   012.4.01.1CE      class 4, invariant        53 of 53
```

* **53 occurrences, always these three words consecutive, never otherwise.**
* Class 4 occurs 53 times in the corpus and class 6 occurs 53 times.
  **Every one is part of a triplet.** The two classes have no other use.
* The two variants are perfectly correlated: `040` always with `4CD`, `142`
  always with `407`. **MEASURED.**

### 6.2 What it means (INFERRED, strong; presence AND absence both clean)

```
   triplet present  vs  (image has an LFO OR a distortion stage)
        MCC +1.000    TP 25   FP 0   FN 0   TN 13
   triplet present  vs  LFO alone          MCC +0.649
   triplet present  vs  distortion alone   MCC +0.372
```

Neither half predicts it; the disjunction predicts it exactly. The single
mechanism both halves need is a **lookup table**: an LFO needs a waveform table,
a waveshaper needs a transfer-curve table. The class-6 word's `addr8` behaves as
the **table selector**:

```
   table 0x18   29 occurrences   LFO-bearing images only
   table 0x1A    1               ENSEMBLE
   table 0x1E    3               ENSEMBLE, S.DELAY+CHORUS, PEQ+CHORUS
   table 0x20    3               CHORUS, MODULATED CHORUS, ENSEMBLE
   table 0x28   17               every distortion-bearing image, and ROCK ROTARY
```

`0x28` never appears in a purely modulating effect and `0x18/0x1A/0x1E/0x20`
never in a purely distorting one. The one image that carries `0x28` without a
distortion name is `ROCK ROTARY`, which is a Leslie simulation — i.e. it has a
drive stage; its `0x28` triplet sits at word 9, before the 2 kHz crossover.
**Presence and absence both predict.**

The `142/407` variant is the **multi-voice** one: it appears exactly where an
effect needs additional decorrelated modulators —
`ENSEMBLE` (3 of them, tables `0x1A 0x20 0x1E`, and `ENSEMBLE` has six modulated
taps), `MODULATED CHORUS`, `CHORUS`, `S.DELAY+CHORUS`, `PEQ+CHORUS` (one each).
No single-voice effect has one. **INFERRED.**

> **ASSIGNED:** `lo12 = 0xC63` = table-lookup request; `class 4` /
> `012.4.01.1CE` = take the table result; `class 6` = table select, with `addr8`
> the table base. **`hi12 = 0x040`** = primary table read, **`hi12 = 0x142`** =
> auxiliary/phase-offset table read. **INFERRED, strong**, on a
> presence-and-absence control with MCC +1.000 and no exceptions.

### 6.3 Other assignments this map supports

| value | assignment | evidence | tag |
|---|---|---|---|
| `lo12 0x4CD`, `0xC63` | the table-lookup triplet's members | MCC +1.000 vs triplet, n=25 | **MEASURED** |
| `lo12 0x700` (`092.2.*.700`, 41 words) | table-lookup *driver*, not a triplet member | MCC +1.000 vs triplet presence, n=25, FP 0 | **INFERRED** |
| `hi12 0x040` / `0x142` | primary / auxiliary table read | §6.2 | **INFERRED** |
| `hi12 0x094` | LFO phase accumulator | n=16, MCC +0.948 vs LFO-bearing, FP 0 | **INFERRED** |
| `hi12 0x092` | LFO / table-driver stage | n=27, MCC +0.885 vs triplet | **INFERRED, weak** |
| `hi12 0x192` | LFO read companion | n=15, MCC +0.851 vs the `082` LFO-read word, FP 0 | **INFERRED, weak** |
| `C40.3.20.44C` + `A00.0.00.041` | fractional-delay interpolation pair for a modulated tap | **29 of 29** occurrences are `C40.3.20.44C`, `A00.0.00.041`, then a `880.1.20` tap read, with no exception; in CHORUS/MOD CHORUS/VIBRATO/MIX UP/ROCK ROTARY/ENHANCER and the S.DELAY+/PEQ+ versions, and **not** in FLANGER, PHASER or ENSEMBLE | co-occurrence **MEASURED**, role **INFERRED** |
| `hi12 0x018`, `0x182`, `C40.2.C0.000` | envelope-detector / gain-computer block | the same 8 images; every one has a positive deficit; 2/π = 0.6366 is that block's first coefficient in COMPRESSOR, AUTO WAH, GATED REVERB and NO OPERATION | **INFERRED** |
| `hi12 0x09A`, `0x0A2`, `0x0A6`; `lo12 0x219`, `0x451` | compressor-private | MCC +1.000 vs `compr`, n = 3–4 | **MEASURED co-occurrence**, function unknown |
| `hi12 0x112`; `lo12 0x1D1`, `0x413`, `0x455` | `AUTO WAH`-private | MCC +1.000, n = 2 | **MEASURED co-occurrence**, function unknown |
| `lo12 0x00B` | external-DRAM address/length operand | n=25, MCC +0.885 vs images with DRAM words, FP 0 | **INFERRED** |
| `lo12 0x44C`, `0x4C8`, `0x041` | modulated-delay-line family | MCC +0.82…+0.89 vs `moddelay` | **INFERRED, weak** |

### 6.4 Reported UNASSIGNED, deliberately

`hi12`: `000 002 010 012 020 022 024 026 028 02A 02C 02E 050 090 102 142(role
only) 182(block only) 184 202 204 212 282 292 29A 302 400 420 424 428 42C 504
602 604 612 800 80A 80B` — 37 values with no predicate above |MCC| 0.80.
The large ones (`000` n=38, `012` n=34, `102` n=34, `202` n=30, `212` n=38) are
**universal** and therefore carry no image-level signal at all; co-occurrence is
the wrong instrument for them and no amount of scoring will assign them.

`lo12`: `000 1C0 1C8 1CD 1CE 1D5 200 216 21A 2C7 2D5 2D9 2DA 359 407 40B 40E 412
415 419 41A 41D 447 44D 452 64B 655 688 68B 692 695 6CE 6D5 839 864 921` — 36
values, same reasoning.

**No role is claimed for any of these.** The honest summary is that
co-occurrence at image granularity has now been mined out: what remains needs
*position*-level evidence (which operand, which cursor) or the datasheet.

## 7. Two pre-registered tests

### 7.1 `op 0x76`'s block width — PREDICTION MET

> **Stated before running:** if `op 0x76` writes a 3-word block, then in every
> image each of its `T1` addresses must be a class-A cursor slot, and the three
> coefficients from that address must repeat verbatim at the image's other
> `op 0x76` addresses (one tone filter per channel or per tap).

```
    3 ENHANCER          0x00 0x04 0x0D 0x11   all slots; two distinct blocks, each twice
    8 GATED REVERB      0x07 0x0E             all slots; identical  +0.2734 +0.3071 -0.1311
    9 SINGLE DELAY      0x03 0x06 0x0C 0x0F   all slots; identical  +0.2734 +0.3871 -0.2073
   10 MULTI TAP DELAY   0x08 0x0B             all slots; identical  +0.2734 +0.3071 -0.1311
   16 ROOM REVERB 1     0x9E 0xA6             all slots; identical  +0.4385 +0.3630 -0.4153
```

**14 of 14 addresses are class-A cursor slots; 4 of 5 images have all blocks
byte-identical, and the fifth (`ENHANCER`) has two blocks each duplicated per
channel.** Width **3**, universally. **MEASURED.** Note the recurring `+0.2734`
first coefficient across three unrelated effects — a shared library filter.

### 7.2 The make-up-gain oracle — PREDICTION FAILED on a new section

> **Stated before running (biquad-map §10 item 3):** "for any newly found section,
> the 6th coefficient should be the reciprocal of the section's own gain."

`ROCK ROTARY`'s newly decoded biquad is a 2000 Hz Q 4 bandpass,
`b = [+0.339461, 0, −0.339461]`, `a = [1, −1.854196, +0.932108]`. Its peak
|H(f)| is **10.000029 at 2000.0 Hz** (a suspiciously round number — the designer
normalised it to exactly ×10). Its sixth coefficient is `733333` = **+1.8000**.
Product = **18.0**, not ±1.

> **VERDICT: the make-up-gain identity is NOT universal.** It holds for the three
> cases biquad-map measured (`PARAMETRIC EQ` −2.0 × 0.5, `OVERDRIVE` +1.5001 ×
> 0.6666, `EXCITER` +1.0 × 1.0) and for every PEQ-combination band found here
> (−2.0000 with the fixed ½, 10 images), and **fails** on `ROCK ROTARY`. Using it
> as an oracle for block boundaries is therefore unsafe. **MEASURED.**

## 8. Corrections and cross-checks to earlier notes

| earlier claim | source | status here |
|---|---|---|
| `MULTI TAP DELAY` is "the one genuine failure" of the cursor model | cursor-general §1.2, §8 | **SUPERSEDED**: the shortfall is exactly the size of a repeated 3-word channel group; same species as the PEQ's `−30` (§5.1) |
| the compressor's 11 candidate families are "present in every compressor stage and in no zero-deficit image" | cursor-general §4 | **CORRECTED**: the tool never applied the second condition (no-op exclusion loop). Applying it leaves **3** (§5.2) |
| "each `C40` word fetches two coefficients" is falsified by CHORUS | cursor-general §4 | **UPHELD, and refined**: the class-restricted `C40.2.C0.000` is not falsified by CHORUS (whose `C40`s are class 3), but its *rate* is still not constant, so it too fails (§5.2) |
| `op 0x76`'s block is "not a fixed width" | cursor-general §6 | **CORRECTED**: width is **3**, in 14 of 14 entries over 5 images; 3/4/7/8 are spacings between placements (§7.1) |
| `PLATE REVERB 2` **and `BRIGHT REVERB 1`** carry ROOM REVERB 1's gain multiset permuted | cursor-general §3.4 | **HALF CORRECTED**: true for `PLATE REVERB 2`; `BRIGHT REVERB 1` contains 0.300 and 0.420, which ROOM has not (§3.1) |
| `BRIGHT REVERB 2`'s 38-word bank and one-slot displacement, "reported, not explained" | cursor-general §3.4, §8 | **EXPLAINED**: one extra `200000` inserted at block index 3, every role shifted +1, tail block 7→8 (§3.2) |
| the reverb has "12 balanced DRAM brackets" | cursor-general §3.2 | **REFRAMED**: `880.1.60` and `880.1.20` counts are unequal in most images (MULTI TAP DELAY: 1 write, 4 reads). Read them as write and tap-read, not as a bracket pair (§3.3) |
| "for any newly found section, the 6th coefficient should be the reciprocal of the section's gain" | biquad-map §10 item 3 | **FALSIFIED as a general rule** by `ROCK ROTARY` (product 18, not 1) (§7.2) |
| `ROCK ROTARY` "has a biquad section, undecoded" | biquad-map §6.3 | **DECODED**: 2000.0 Hz, Q 4.0000, exact `(1,0,−1)` bandpass (§4) |
| "`NO OPERATION` is the sole false positive of two independent controls; worth understanding" | INDEX backlog 5 | **EXPLAINED**: it contains a real envelope-detector block (2/π scale, `C40` pair, one-pole smoothers) and real DRAM accesses (§4) |
| `hi12` of a section's `[0]` names the stage's bus, not an operand | biquad-map §5 | **USED AND CORROBORATED**: it is the only difference between MULTI TAP DELAY's two output groups (§5.1) |
| the compressor `+4` | biquad-map §2.2 | **CORROBORATED a third way**: it is the difference between a nonsense and a textbook filter decode in 3 images (§5.2) |
| 91 valid programs, 38 distinct images | INDEX | **UPHELD**; 38 enumerated and mapped here |
| unit 1 base `+0x80` | cursor-general §1.2 | **UPHELD, and completed**: the reverb is the **only** unit-1 image in the corpus |

## 9. Falsified, or explicitly not established

* **The make-up-gain identity as a universal oracle.** **FALSIFIED** (§7.2).
* **`BRIGHT REVERB 1` as a permutation of ROOM REVERB 1's gains.** **FALSIFIED** (§3.1).
* **A fixed per-`C40.2` coefficient appetite.** **FALSIFIED** (§5.2).
* **Cursor wrap-around at the bank size** as `MULTI TAP DELAY`'s mechanism.
  **EXCLUDED** (§5.1).
* **The encoding of a partial (non-zero-target) cursor rewind.** **NOT IDENTIFIED**
  — the single most valuable remaining question, and now well-posed.
* **Which of `{0A2.2.000, C40.1.451, C40.2.000}` consumes the compressor's four
  words**, and how the count varies. **NOT IDENTIFIED.**
* **The `804.8.16.1DA` (`AUTO WAH`) and `80A.8.16.000` (`ROCK ROTARY`,
  `PEQ+COMPR+OVERDR`) section families.** Both still undecoded; both carry an
  unexplained deficit.
* **`op 0x77`** and `ENSEMBLE`'s six entries. **`op 0x73`** and **`op 0x6D`**
  (both write the second address space) are used throughout §4 as "the host writes
  these" without their semantics being known.
* **`GATED REVERB`'s gate arithmetic**, `PHASER`'s stage count, `ENHANCER`'s
  missing class-8 word, `NO OPERATION`'s +2.
* **The mode-`0x0B` records of `FLANGER`, `S.DELAY+FLANGER`, `PEQ+FLANGER`** —
  values of 140800 / 1964800 / 153600 samples are not delay lengths (§1).
* **73 of the ~111 `hi12`/`lo12` values** still carry no meaning, and
  image-granularity co-occurrence cannot assign them (§6.4).

## 10. Next experiments, in order of value

1. **Find the partial-rewind encoding.** `MULTI TAP DELAY` needs `−3` between
   words 49 and 52; only `202.2.00.407` and `000.2.01.000` sit there. Compare
   against every other place those two words occur and look for a field that
   differs. Cheapest well-posed question left.
2. **Decode the `804.8.16.1DA` and `80A.8.16.000` sections** by the §4 method
   (static bank + class-A prefix + invert). Both carry an unexplained deficit, so
   solving either probably solves a deficit too.
3. **Confirm the table-lookup reading against the hardware tables.** If `0x18` and
   `0x28` are real table base addresses in the chip's coefficient RAM, the loader
   must fill them; look for op-2 blocks landing at `0x18..0x27` and `0x28..`.
   This is a sharp, cheap falsifier for §6.
4. **`op 0x77` / `ENSEMBLE`**, the only user of `LABEL_03B646`.
5. **The `µPD6383` datasheet** — still the highest-payoff move in the file
   (INDEX backlog 6).

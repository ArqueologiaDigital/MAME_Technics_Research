# KN5000 tone-gen (IC303) — the DATA-DERIVED wave map, APPLIED

Author: autonomous APPLY pass, 2026-07-25. Requested by Felipe Sanches.
**This pass edits `src/` and rebuilds.** It implements the mapping validated in
`notes/kn5000-structural-validation.md` (commit `1e1e03e`) on top of the firmware tables
mined in `notes/kn5000-firmware-sample-tables.md` (`cb6b362`), and **deletes the heuristic
GROUP table and zone-scaling compander** that stood in for it.

Evidence labels: **MEASURED** (bytes read from a ROM, or a number read off a live run) /
**INFERRED** / **LABELLED-PLACEHOLDER**.

Files touched:
* `src/mame/matsushita/kn5000_tonegen.cpp`
* `src/mame/matsushita/kn5000_tonegen.h`

---

## 0. TL;DR

* **The wave selection is now DECODED, not guessed.** `select_waveform_index()` — with its
  hand-tuned 8-entry `GROUP[]` table, its `ZONE_SPAN = 32` compander and its `entry % 256`
  truncation — is **gone**. In its place `decode_wave_select()` reads the ROM's own
  self-delimiting page directories. **There is not one tuned constant left in the selection
  path.**
* Answering the mandate — *"which samples correspond to a piano should be documented in
  voice record data structures… it should not involve guessing"* — **class 7 = the acoustic
  piano bank = IC307 page 3**, and the driver now plays exactly that, because that is what
  the ROM's directory and the firmware's tone tables jointly say.
* **Verified live, and it reproduces the firmware's own tables.** A chromatic C4..B4 run
  makes the firmware emit `+0x040` = `0x7007, 0x7008, 0x7009` (and the second oscillator's
  `0x7017, 0x7018, 0x7019`), switching at exactly MIDI 64 and 68 — **the zone boundaries
  the Table Data ROM's SET #0 and SET #1 descriptors specify, 4/4 exact, both oscillators.**
  0 out-of-range, 0 undocumented entries in the whole run.
* **Pitch improved, did not regress:** chromatic **12/12** distinct and monotonic within
  **±6.9 cents** (mean 3.3), octave ratio **2.0015**, chord C-E-G all three tones present at
  12.8× the off-tone floor, **0.000 % clipping**. `-validate kn5000` clean; boots to the
  normal play screen.
* **Honest gap, unchanged and now precisely bounded:** classes 0-3 live on a chip that has
  never been dumped. They are routed through the *correct* datapath onto the BAD_DUMP copy
  of IC307 that `kn5000.cpp` loads into that socket, and every consequence of that is
  flagged by `LOG_BOUND`. That is a **missing dump**, not a missing decode.

---

## 1. What was replaced

The shipped code chose a waveform like this:

```c
int cls = (w >> 12) & 0x0F;  int entry = w & 0x0FFF;
static const group_t GROUP[8] = { {121,134}, {73,83}, {102,107}, {135,141},
                                  {86,89}, {142,146}, {108,111}, {39,54} };   // tuned by ear/spectra
int local = entry % 256;                       // threw away the top 4 bits it had just kept
int q     = (local * size) / 32;               // ZONE_SPAN = 32, a fitted constant
int idx   = GROUP[cls & 7].first + q;          // one flat 198-entry index, page 0 only
```

Everything in it above the register decode was a placeholder: the eight band constants, the
compander, the span, and the premise that IC307 has **one** 198-entry index describing the
first 1 MB. That premise is false (§2), which is why the bands had to be tuned at all.

## 2. What it was replaced with

```c
page      = (w >> 12) & 3        // 1 MB page inside the bank
bank      = (w >> 14) & 3        // which wave ROM   (1 = IC307, the one real dump)
chunk     =  w & 0x0FFF          // PLAIN 0-BASED INDEX into that page's own directory

n         = u16[page_base] / 4                       // the page states its own size
{param_ptr, wave_off} = u16 pair at page_base + 4*chunk
PCM start = page_base + wave_off*16
PCM end   = page_base + 16*(smallest wave_off in the directory strictly greater)   // s16le
```

`parse_page_directories()` accepts a page as a directory only if **all six** MEASURED
structural properties hold — `entry0.param_ptr` a nonzero multiple of 4; the directory fits
the page; `param_ptr` monotonic; the directory does not overlap the first parameter record;
every `wave_off × 16` inside the page; and the **redundant back-reference** (the u16 at the
head of each parameter record equals that entry's own `wave_offset`) for **every** entry.
Re-derived independently in this pass from `kn5000_waveform_rom.ic307`: (**MEASURED**)

```
page 0 @0x000000  n= 198  param mono  wave mono          backref  198/198  PASS
page 1 @0x100000  n= 168  param mono  wave mono (3 back) backref  168/168  PASS
page 2 @0x200000  n=1072  param mono  wave mono          backref 1072/1072 PASS
page 3 @0x300000  n=  57  param mono  wave mono          backref   57/57   PASS
```

A blank or non-directory page is therefore *rejected* rather than producing garbage
addresses — which matters, because it is exactly what the three fabricated
`kn5000_waveform_rom.ic30{4,5,6}` files in the ROM folder are (§6).

## 3. Why this decode and not another — re-checked in this pass

The firmware side was re-derived from `notes/data/kn5000-multisample-sets.tsv` (487 SET
descriptors, walked from the Table Data ROM): **1444 distinct `(class, entry)` pairs**,
per class (**MEASURED**):

| class | entries used | range | directory it REQUIRES (`max+1`) | IC307 page `class & 3` | page size | |
|---|---|---|---|---|---|---|
| 4 | 195 | `0x001`-`0x0C5` | **198** | 0 | **198** | **EXACT** |
| 5 | 164 | `0x000`-`0x0A7` | **168** | 1 | **168** | **EXACT** |
| 6 | 49 | `0x001`-`0x096` | ≥151 | 2 | 1072 | fits |
| 7 | 57 | `0x000`-`0x038` | **57** | 3 | **57** | **EXACT** |
| 0 | 212 | `0x000`-`0x0D5` | ≥214 | — | — | overflows every page but 2 |
| 1 | 168 | `0x000`-`0x0B0` | ≥177 | — | — | " |
| 2 | 184 | `0x001`-`0x0B8` | ≥185 | — | — | " |
| 3 | 415 | `0x000`-`0x1B3` | ≥436 | — | — | " |

The prediction (firmware only, `max(entry)+1`) and the check (ROM only, the page's own
declared count) were produced from different chips by different code: **3 exact hits out of
3 testable classes**, and **465/465** of those classes' pairs in range with **base 0**.
Classes 0 and 3 need ≥214 and ≥436 slots — only page 2 could hold either, so they collide
and **classes 0-3 cannot be on IC307 at all**; for 4-7 the identity map is the unique
injective assignment with more than one exact match.

## 4. Live verification — the decode reproduces the firmware's own zone maps

`LOG_BOUND` was compiled in for one run (chromatic C4..B4, octave, C-E-G chord on the
default PIANO patch) and reports every selection. Complete tally: (**MEASURED**)

```
128 x  +040=0002 cls=0 entry=0x002 -> bank 0 page 0 chunk    2/198  pcm 0x002730  1152 smp  period 127
 12 x  +040=7007 cls=7 entry=0x007 -> bank 1 page 3 chunk    7/57   pcm 0xF49920 16656 smp  period  40
 12 x  +040=7017 cls=7 entry=0x017 -> bank 1 page 3 chunk   23/57   pcm 0xFC5DA0 16656 smp  period  40
 12 x  +040=7008 cls=7 entry=0x008 -> bank 1 page 3 chunk    8/57   pcm 0xF51B40 15504 smp  period  34
 12 x  +040=7018 cls=7 entry=0x018 -> bank 1 page 3 chunk   24/57   pcm 0xFCDFC0 15504 smp  period  34
  8 x  +040=7009 / 7019   -> chunks  9 / 25      2 x  +040=700A / 701A -> chunks 10 / 26
  2 x  +040=0000 cls=0 entry=0x000 -> bank 0 page 0 chunk    0/198  pcm 0x001A30   256 smp  period 256
        OUT-OF-RANGE: 0     UNDOCUMENTED: 0     DECODE ERROR: 0
```

Four independent things fall out of that, none of them arranged:

1. **The zone boundaries are the firmware's, exactly.** The 12 chromatic notes split
   `{C4,C#4,D4,D#4} → 0x007`, `{E4,F4,F#4,G4} → 0x008`, `{G#4,A4,A#4,B4} → 0x009`,
   `{C5} → 0x00A`. The Table Data ROM's SET #1 descriptor reads
   `60-63:7:007; 64-67:7:008; 68-71:7:009; 72-75:7:00A` and SET #0 reads
   `60-63:7:007; 64-67:7:017; 68-71:7:018; 72-75:7:019`. **4/4 exact, on both oscillators.**
2. **The two piano oscillators are 0x10 apart** (`0x7007`/`0x7017`), and page 3 is two
   16-chunk runs — the offset *is* the group size. Both land on 16656-sample chunks with
   identical measured periods: two different recordings of the same note, i.e. two
   oscillators, as predicted.
3. **`+040 = 0x0000` reaches the synthetic sine with no special case.** The old code needed
   `if (w == 0 && timbre == 0) return 0;`. The formula sends it to page 0 chunk 0 — measured
   to be the 256-sample near-perfect single sine cycle, and the one chunk no instrument
   references. The special case was deleted.
4. **Nothing was flagged.** Zero out-of-range, zero entries above what the firmware's tables
   produce.

## 5. Pitch, chord, clipping — live (MEASURED, published binary, isolated nvram)

```
segment            f0 Hz    expect     cents          CHROMATIC  12/12 detected
chrom:C4          262.34    261.63      +4.7          monotonic ascending: True
chrom:C#4         278.29    277.18      +6.9          all distinct (>1% apart): True
chrom:D4          294.57    293.66      +5.3          |cents| max 6.9   mean 3.3
chrom:D#4         311.97    311.13      +4.7
chrom:E4          329.73    329.63      +0.6          OCTAVE  C4 262.18 / C5 524.75
chrom:F4          349.40    349.23      +0.9                  ratio 2.0015  (want 2.0000)
chrom:F#4         370.12    369.99      +0.6
chrom:G4          392.19    392.00      +0.9          CHORD C-E-G   C4 363.4  E4 489.7  G4 452.8
chrom:G#4         416.38    415.30      +4.5                        off-tones 16.1 / 28.3
chrom:A4          441.07    440.00      +4.2                        weakest tone / worst off = 12.8x
chrom:A#4         467.15    466.16      +3.7                        ALL THREE PRESENT
chrom:B4          494.83    493.88      +3.3
                                                      whole capture peak 7672/32767 = 0.234 FS
                                                      clipped samples 0  (0.0000 %)
```

`-validate kn5000` → exit 0, no output. Boots to the normal play screen
(`RIGHT1 Piano / RIGHT2 Bigband Brass / LEFT Modern E.P.1`).

### 5.1 Two measurement bugs found and fixed on the way

Moving PIANO onto its real bank exposed two defects in `detect_period()` that the old
mapping had hidden. Both are fixes to a *biased estimator*, not tuning:

* **Biased normalisation + attack window.** It divided every lag by the FULL-window energy
  while summing progressively fewer terms — a downward bias proportional to lag, which
  systematically rejects low notes — and it correlated across the inharmonic attack. Now:
  unbiased `c/sqrt(e0·e1)` over the overlap, windowed on the recording's body.
  PREDICT-THEN-CHECK on the piano multisample, whose periods **must** fall monotonically:

  ```
  old:  238 173 132 103 82 69 54 40 34 26 21 18 [29 51 16 29]   <- breaks at the top
  new:  237.40 173.47 132.28 103.73 82.17 69.00 54.07 40.68
         34.60  26.22  21.51  18.07  14.40 10.16  8.12  7.21    <- 16/16 strictly falling
  ```
  and the span **60.50 semitones** against the firmware's own 16 zones × 4 semitones = **60**.
  Unresolvable chunks: page 3 **11/57 → 0/57**, page 1 36 → 30/168, page 0 unchanged 16/198,
  page 2 unchanged 0/1072.
* **Integer periods detuned the notes.** The playback rate is proportional to the measured
  period, so rounding it to a whole sample detunes by up to `1200/(2P)` cents — and page 3's
  periods run 237 down to 7 samples. MEASURED before the fix: **+16 cents on C4-D#4, +24 on
  E4-G4, −14 on G#4-B4** — jumping exactly at the 4-semitone zone boundaries, the signature
  of per-chunk rounding — and an octave ratio of **1.9705**. The period is now carried in
  16.16 fixed point, refined by parabolic interpolation of the correlation peak. That is what
  takes the run to ±6.9 cents and the octave to 2.0015.
* A third, caught by the `LOG_BOUND` run: dropping the old "skip the lag-0 shoulder" guard
  made the 256-sample synthetic sine read period **4** (any smooth wave has r ≈ 1 at small
  lags). The guard is restored — a period is only claimed after the correlation has first
  gone negative; if it never does, the recording *is* one cycle and its own length is the
  period. Sine back to **256.000**, no other page's count changed.

### 5.2 Aperiodic recordings now play as recorded

`detect_period` returning 0 used to substitute page-0 chunk 0 (a sine). It now means "this
recording has no fundamental" and `update_pitch` plays it at native rate. This affects
16/198 of page 0 and 30/168 of page 1 — precisely the pages the ROM's own name table fills
with `Rock Bass Drm`, `HiHat Open`, `Applause`, `Telephone`. Resampling a drum to a musical
note is not defined; playing the real recording is. The pitched pages (3 = piano, 2 = drawbar
footage) have **no** such chunks, so no pitched instrument is affected.

## 6. The `bank 0` prediction was RUN — and the files that could have answered it are fakes

`structural-validation.md §7` gives a falsifiable test: whichever of IC304/305/306 is bank 0
must declare page directories of **≥214 / 177 / 185 / 436** at `0x000000 / 0x100000 /
0x200000 / 0x300000`. Three files named `kn5000_waveform_rom.ic30{4,5,6}` do exist in the ROM
folder, so the test was run on them. (**MEASURED**)

```
ic304 / ic305 / ic306 :  page 0 -> n=198 (backref 198/198), ALL THREE with the identical
                         layout (lastparam 0x098C, firstPCM 0x0009A0)
                         pages 1,2,3 -> entry0.param_ptr = 0xFFFF, no directory
                         every byte from 0x100000 to 0x3FFFFF is 0xFF
```

All three **fail** the prediction, and they are not plausible dumps: a 4 MB mask ROM that is
blank above 1 MB, ×3, byte-layout-identical. They are fabrications. `kn5000.cpp` already
ignores them (it loads a BAD_DUMP copy of IC307 into all four sockets), and the new
six-check acceptance test would reject their empty pages anyway. **The prediction stands
untested; nothing here answers it.**

## 7. What is DATA-DERIVED and what is still a labelled gap

**DATA-DERIVED — the whole selection path for classes 4-7 (bank 1 = IC307):**
`+0x040` → `{bank, page, chunk}` → directory lookup → PCM address and extent. Every number
comes from the wave ROM's own bytes; the class→page assignment is validated 3/3 against the
firmware's independently-derived requirements and 465/465 for in-range-ness; and the live
register stream reproduces the firmware's SET zone maps exactly. **No heuristic, no tuned
constant, no ear.**

**LABELLED GAPS (each one bounded, none of them a decode problem):**

1. **Which socket is bank 0** — classes 0-3, i.e. Strings / Brass / Bass / Mallet / Guitar /
   Sax / World / GM. A **wiring fact**, not a decoding fact. Until a real dump exists those
   classes read the BAD_DUMP copy of IC307 in that socket, through the correct paged
   datapath; where their `entry` exceeds the substituted directory (class 3 reaches 435 vs
   IC307 page 3's 57) it **wraps**, which is a **LABELLED-PLACEHOLDER** — every occurrence is
   flagged `OUT-OF-RANGE … (bank is UNDUMPED)`. One constant in `BANK_BASE[]` and one
   `ROM_LOAD` line change when a dump appears; nothing else.
2. **Classes 8-15** never appear (class bit 3 is 0 in all 1444 pairs). Banks 2/3 are
   consequently never selected. Undecided, not assumed.
3. **Class 6 / page 2** — 1072 slots, only 49 claimed by the traced path. Not a
   contradiction (all 49 in range) but `max(entry)+1` cannot confirm the size while the
   drawbar/footage selection path (`LABEL_02B576` / `LABEL_032AE0` / `LABEL_032A08`) is
   untraced.
4. **The per-wave ROOT PITCH is still MEASURED, not read.** Selection is decoded; pitch is
   not. The driver measures each chunk's fundamental by autocorrelation and resamples, rather
   than reading the chip's own per-wave parameter bytes (the `xx/80`, `xx/40` values in the
   parameter records), which remain undecoded. This is the honest residual: it is why the
   chromatic run lands at ±7 cents instead of exact, and why the per-SET regression below
   passes strictly on pianos but not on accordions.

### 7.1 Per-SET pitch regression with the shipped detector (reported miss included)

Each firmware SET regressed on its own — zone lower bound vs `−12·log2(measured period)`,
excluding the catch-all zones the octave fold creates. Slope 1.0 = the chunk this formula
selects is exactly the sample for that key zone. (**MEASURED**)

```
  set   1  class 7  n=14  slope 0.995  R^2 0.9983  rms 0.65    Piano
  set   2  class 7  n=14  slope 0.996  R^2 0.9983  rms 0.66    Piano
  set   4  class 7  n=15  slope 1.008  R^2 0.9980  rms 0.77    Bright Piano
  set   5  class 7  n=15  slope 1.007  R^2 0.9981  rms 0.77    Honky-Tonk Piano
  set   0  class 7  n=15  slope 0.895  R^2 0.9932  rms 1.28    Piano 1 Octave
  set 241/242 class 4 n=6 slope 0.968  R^2 0.9303  rms 2.72    Cathedral Organ
  ...
  aggregate over 43 non-degenerate SETs: 9 strict PASS (|a−1|<0.25 and R^2>0.85), median slope 0.243
  CONTROLS  class->page permutations : 0-6 strict of 33-46 SETs, median slope −0.15..+0.19
            shuffled chunk index x20 : strict-pass rate 0.7 %, median slope +0.03 ± 0.16
```

**Reported miss, plainly:** the five piano SETs are essentially perfect and every control
collapses, but only **9 of 43** SETs clear the strict bar, and the best permutation control
reaches 6. On this aggregate statistic alone the derived map is the best but not decisively
so. The strong evidence is elsewhere and it is structural — 3/3 exact directory sizes,
465/465 in range, and the live 4/4 zone-boundary reproduction of §4. The aggregate weakness
is dominated by gap 4 above (an autocorrelation pitch detector on harmonically dense
accordion/organ reeds) and by SETs that legitimately re-use one recording across zones; it
is **not** separated here, and it is the same miss `structural-validation.md §4.3` reported.

## 8. Reproduction

```
# ROM side — re-derive the four page directories + the integrity back-reference
python3 <scratchpad>/pagedir.py roms/kn5000/kn5000_waveform_rom.ic307

# the shipped detector, standalone, over all 1495 chunks (piano monotonicity + zeros)
g++ -O2 -o probe4 <scratchpad>/probe4.cpp && ./probe4 <ic307> periods.tsv

# per-SET regression + negative controls
python3 <scratchpad>/regress2.py

# live (isolated nvram COPY; never touch kn7000-emulator/nvram):
cd kn7000-emulator && ./kn7000 kn5000 -rp roms -window -nomaximize -skip_gameinfo \
  -nvram_directory <copy> -autoboot_delay 0 -autoboot_script <scratchpad>/pitchtest.lua \
  -seconds_to_run 60 -nothrottle -wavwrite fin.wav
python3 <scratchpad>/anpitch.py fin.wav fin_seg.txt       # chromatic / octave / chord / clipping

# the selection log: rebuild with `#define VERBOSE (LOG_BOUND)` and add -log
```

## 9. Corrections this pass makes to prior notes

1. **`notes/kn5000-faithful-render-v2.md §0/§1/§5.1`** — "the numeric `{cls,entry}→physical-PCM`
   map is the LSI's internal decoder … a hardware black box", and the `CLASS_BAND`/`SAFE_WAVE`
   /`GROUP` constants described as "ear-tunable": **superseded**. The map is read out of the
   ROM; those constants no longer exist in the code.
2. **`kn5000_tonegen.h` / `.cpp` header comments** claiming the waveform ROM is "a 198-entry
   index table at offset 0" + PCM: **corrected** to four 1 MB pages each with its own
   self-delimiting directory.
3. **`kn5000_wave_samples/INDEX.txt`** — its by-ear request stays withdrawn; the driver no
   longer uses anything resembling its class→chunk table.

# KN5000 tone gen — APPLYING the data-derived variant fixes

Author: autonomous APPLY pass, 2026-07-25. Follows `notes/kn5000-variant-diagnosis.md`
(`ffda058`) and `notes/kn5000-variant-model.md` (`16588fa`), and the working data-derived wave
map (`e2f8b60`). Everything below is derived from the firmware's own code and data — the v142
sub-CPU disassembly (`kn5000-roms-disasm/archive/asl/subcpu/kn5000_subprogram_v142.asm`, `L<n>`
= line numbers there), the sub-program ROM, the Table-Data ROM, the IC307 wave ROM — or MEASURED
live on the bus / in the rendered audio. Evidence labels: **MEASURED** / **TRACED** /
**PREDICTED-then-CHECKED**. Where something is *not* derivable it is said so (§4), and the
mechanism was left out rather than invented.

Code: `src/mame/matsushita/kn5000.cpp`, `src/mame/matsushita/kn5000_tonegen.{cpp,h}`.

---

## 0. TL;DR

| # | change | file | effect |
|---|---|---|---|
| 1 | The key-bed FIFO high byte is a key-travel **TIME**, not a velocity | `kn5000.cpp` | every velocity in the machine ran **backwards**; all 24 velocity-split patches picked the wrong sample layer. Fixed and verified on the bus |
| 2 | `+0x400` is an **absolute log pitch**; take the partial TRANSPOSE and DETUNE from it | `kn5000_tonegen.cpp` | `Piano 1 Octave` now sounds its octave; `Honky-Tonk` beats at 2.0 Hz; every unison layer chorusses instead of rendering twice identically |
| 3 | NOT implemented, and why | — | the absolute octave of a chunk never heard untransposed (§4.1); the EG / LFO / brightness registers (§4.2); the undumped wave banks (§4.3) |

---

## 1. Key-bed velocity polarity (`kn5000.cpp`)

### What the firmware does (TRACED + MEASURED)

`ToneGen_Read_Voice_Data` (asm L51500) reads the 16-bit key-bed word at `0x110000` as
`{high, low = key}`. `ToneGen_Calc_Pitch` (L51556) converts the high byte to the note-on
velocity:

```
x   = T1[byte]                              ; 256-byte table @0x01F43E
y   = clamp((x - 0x4D) * G / 0x80 + O)      ; TOUCH curve, G/O @0x01F420/0x01F421,
                                            ; mode *(0x4A48) = 6 at power-on (ToneGen_Init L51415)
vel = T2[y]                                 ; 256-byte table @0x01F53E -> 1..127
```

Both tables were re-dumped **independently in this pass** from `kn5000_subprogram_v142.rom`
(file offset = address − 0xEF00) and verified: `T1` is monotone **DECREASING**
(`FF FF … FB F6 F1 … 01 01 00 00`), `T2` monotone **INCREASING** (`01 02 … 7F`); `K1 = 0x4D`
@0x01F418, `D = 0x80` @0x01F41A; `G[] = 00 10 20 … 90`, `O[] = D0 C7 BD B4 AB A1 98 8F 86 82`.
A decreasing input table is only meaningful if the byte is a make-to-break **time**.

### The defect, MEASURED end to end

`keybed_scan()` and `kbd_midi_rx()` put the MIDI velocity straight into that byte, so the
firmware saw:

| MIDI velocity | 20 | 45 | 70 | 90 | 110 | 127 |
|---|---|---|---|---|---|---|
| firmware velocity **before** | 126 | 98 | 80 | 66 | 49 | 39 |
| firmware velocity **after** | 20 | 45 | 70 | 90 | 110 | 127 |

### The fix

A 128-entry inverse table `KEYBED_TIME[]` (touch mode 6, the power-on default), computed here
as `raw = argmin |firmware(raw) − v|`: **117/127 velocities exact, max round-trip error 1**.
`KEYBED_VELOCITY = 100` (PC keyboard) now emits byte 42, which the firmware reads back as
velocity 100.

### PREDICT-THEN-CHECK, on the bus (run `vcap_AP1`)

`E.Piano 1` is a 4-way velocity split, VSEL splits `3C/50/64` = 60/80/100. Predicted: the
`+0x040` word must now step **UP** with velocity, crossing inside 45→70, 70→90, 90→110.

```
          C4 at velocity   20     45     70     90    110    127
 BEFORE (diagnosis §3.4)  202F   2027   201F   2017   2017   2017     <- DEscending
 AFTER  (this pass)       2017   2017   201F   2027   202F   202F     <- ASCending
```

**3/3 crossings in the predicted buckets**, and the sequence is exactly the reverse of the
diagnosis's. The velocity-scaled level register follows: `+0x500` low byte on plain Piano now
runs `63 66 69 6E 77 7F` **up** with velocity (it ran down before).

This is a **key-bed** fix — inside the key bed's own interface. The tone-gen device is
untouched by it, and the chip boundary is not involved.

---

## 2. `+0x400` — transpose and detune (`kn5000_tonegen.cpp`)

### 2.1 What the register is (TRACED, `LABEL_023584` L15504 → `LABEL_023A05` L15996 → `LABEL_023A4A` L16025)

```
+0x400 = (effective note << 8) + 0x80 + trim(chunk) + 2*fine + detune + tunings
```

0x100 units per semitone, 0xC00 per octave. `trim` is the multisample partial record's own
tuning word (`record[+0x04..05]`, stride-6 records). MEASURED census over the 1046 partial
blocks: 879 have no coarse transpose, 109 are ±12/±24, 58 are other intervals; 364 carry a
non-zero fine transpose. Per patch: 441 of 585 multi-partial patches have no coarse transpose
at all, 117 have a **mixed** set, 27 shift every partial equally.

### 2.2 The trim is a property of the CHUNK — MEASURED

Walking all 143 stride-6 SET descriptors × 128 keys of the Table-Data ROM (independently of
the emulator): the trim is a function of the `+0x040` word **alone** — **367 of 368** distinct
chunks carry exactly one value across every SET, patch and key that reaches them. The single
exception, `+0x040 = 0x6028`, carries two values **3072 apart = exactly one octave** (a drawbar
footage wave deliberately reused an octave up).

So one observation of a chunk pins it:  `trim(chunk) = regs[8] − 0x100·note − 0x80`.

### 2.3 What the device now does

* **Learn** the trim only from a key press it can *prove* carries no coarse transpose: one
  where every partial lands at the same `rho` (below) within half a semitone, and at least two
  DISTINCT chunks are present. A chunk whose observations later disagree by more than half a
  semitone is marked **CONFLICTED** and never anchors anything again — that is what catches the
  27 uniformly-transposed patches and any part-level octave/transpose setting.
* **Place** each voice from **its own** chunk's learned trim:
  `pitch_offset = (regs[8] − 0x80 − trim)/0x100 − played_note`, clamped to ±25 semitones.
* **Spread** voices that share a chunk with a placed voice by their register difference (the
  unknown per-chunk term cancels identically) — this is the unison/detune layer.
* **Fall back** to the played note (exactly the previous behaviour) for anything unresolved,
  and for every voice on an undumped socket (`wave_real`), where the chunk actually played is a
  substituted, unrelated recording.

`rho = regs[8]/0x100 − 12·log2(period)` refers a voice's register to its own recording's
measured fundamental, which is what makes two partials comparable at all.

### 2.4 PREDICT-THEN-CHECK — rendered audio

Every figure below is from `-wavwrite` captures of this build (`apD.wav`, `apG.wav`, channel 1),
with the sound selected from the panel and its patch-record name read back live.

**Octave transpose.** Relative energy at the played note's fundamental and its octaves,
C4 vel 100:

| sound | −12 | **+0** | **+12** | +24 |
|---|---|---|---|---|
| Piano (reference) | 0.02 | **1.00** | 0.66 | 0.07 |
| **Piano 1 Octave** | 0.01 | **0.40** | **1.00** | 0.21 |

The `+12` partial goes from 0.66 of the fundamental (plain Piano — that is just its 2nd
harmonic) to **2.5×** it. The patch record declares partial 0 `coarse = +12`, partial 1 `+0`;
the device places them at +12.03 and 0.00.

**Detune / beating.** `Honky-Tonk Piano` declares partial fine `−6 / +6`; the bus carries
`+0x400 = 34B5` and `34D9` on the same chunk `0x7007`, a difference of 36 units = 0.1406
semitone, which at C4 predicts a **2.13 Hz** beat.

| held note (2.3 s) | envelope beat | modulation depth |
|---|---|---|
| Piano C4 (control, no detune) | 12.05 Hz (the recording's own texture) | 0.221 |
| **Honky-Tonk C4** | **2.01 Hz** | 0.542 |
| Honky-Tonk C5 | 2.23 Hz | 1.135 |

**2.01 measured vs 2.13 predicted** (5.6 %). Before this change the two voices were rendered
bit-identically and could not beat at all.

### 2.5 No regression — MEASURED

* **Chromatic run**, plain Piano, MIDI 36…50, autocorrelation f0 against equal temperament:
  **15/15 within +7.9 / −0.7 cents, span 8.6 cents** — the same few-cents accuracy the
  period-driven model had before (it is the same code path: for an untransposed voice the
  learned trim yields offset 0.000 by construction).
* **Octaves**: Piano C3/C4/C5 = 131.15 / 262.30 / 521.74 Hz.
* **Clipping**: peak 14728/32767 across an 81 s multi-sound capture, **0 clipped samples**.
* **`-validate`**: passes (exit 0, no diagnostics).
* Boots to the PMEM play screen; all four panel sound selections verified by live patch-record
  name read-back (`Piano`, `Piano 1 Octave`, `Bright Piano`, `Rock Piano`).

---

## 3. Per-variant outcome

| sound | before | after |
|---|---|---|
| **Piano** | reference | unchanged (offsets 0.000) |
| **Bright Piano** | +5.38 dB below Piano, otherwise identical | unchanged — its entire difference is in registers whose chip-side response is undecoded (§4.2) |
| **Mellow Piano** | 100.00 % bit-identical to Bright Piano | unchanged, same reason |
| **Piano 1 Octave** | rendered at the played note | **sounds its octave** (§2.4) once the zone has been heard untransposed (§4.1) |
| **Piano 2 Octave** | rendered at the played note | partial 1 placed correctly an octave down; partial 0 needs a zone the plain piano has to have visited (§4.1) |
| **Honky-Tonk** | two bit-identical voices | **beats at 2.0 Hz** (§2.4) |
| **Electric Grand** | two bit-identical voices | detuned by the 2 register units the ROM declares |
| **Rock Piano**, all **E.Pianos**, `Suitcase E.P.`, `Modern E.P.` | wrong sample | still wrong — their samples are on an **undumped** chip (§4.3). Their velocity SPLIT is now correct, so they at least switch layers the right way round |

---

## 4. NOT implemented — and why (this is the honest part)

### 4.1 The absolute octave of a chunk that has never been heard untransposed

A transposed partial selects a multisample zone an octave away, and nothing on the bus says
where that zone sits in absolute terms. Three substitutes were built and **measured**, and all
three are ambiguous by exactly one octave:

1. **Learn the trim from any note-on.** A transposed partial teaches the chunk a trim exactly
   3072 units (one octave) wrong, and the wrong value is indistinguishable from a legitimate
   −12 transpose afterwards. Cold-starting on `Piano 1 Octave` poisons chunk `0x007` and then
   *plain* Piano renders C3 for a played C4 — a regression. Rejected.
2. **The page-local law** `trim + 0x80 − 3072·log2(period) ≡ R0 (mod 0xC00)`. It is real:
   on the acoustic-piano page all 32 chunks agree within **47 units (18 cents)**, and 89 / 64 /
   77 % of the chunks of the other three pages agree within a semitone. But it only fixes the
   trim MODULO AN OCTAVE. Choosing the octave needs the global constant
   `C = played_note + 12·log2(period)`, and C is **not** a constant: over the narrow-zone
   observations of the piano page alone it spans **124.1 … 133.2** (9.1 semitones), and over
   classes 4/5/6 it spans 16–30 semitones, because a one-zone SET stretches one recording over
   the whole keyboard. Rejected.
3. **The relative interval between two partials of one key press**, `rho(i) − rho(j)`. This one
   *is* derivable and *is* used — but only within a chunk. Across chunks it is right only while
   both recordings sit in the same octave slot of the wave ROM. MEASURED live: `Piano 1 Octave`
   (chunks `0x019`/`0x007`) gives **11.974** against the +12 its record declares, but
   `Piano 2 Octave` (chunks `0x019`/`0x004`) gives **36.004** against a true 24 — one octave of
   error. Confirmed in the rendered audio (a partial landed at C6 instead of C5) and then
   restricted out of the code.

**What would settle it: the per-chunk ROOT PITCH in the wave ROM's parameter records** — the
model note's Tier C. It is inside the chip boundary (the LSI reads those records). Page 3's
records are 4 bytes, `{wave_offset u16, u16}`, and the second word (`0x80EB 0x80DC 0x80DD …
0x40E1 … 0x4085`) does not decode as a root pitch by inspection; it was **not** guessed at.
Until it is decoded, a transposed partial is placed only when its own zone has been heard from
an untransposed press — which ordinary playing across the keyboard does within seconds, and
which the octave demonstration in §2.4 relies on.

### 4.2 The timbre registers — `+0x080 +0x0C0 +0x100 +0x140 +0x9C0 +0xA00 +0xA40`

This is the whole of the Piano / Bright Piano / Mellow Piano difference. The **firmware** side
is decoded (model note §6: which patch byte, through which table, into which register — the
`+0x0C0` prediction from `patch[+0x5C]` hits 3/3). The **chip** side is not: what the undumped
IC303 does with a `(level<<8)|rate` envelope word, an LFO word, or `+0x0C0`, cannot be settled
from the emulator, and §9.1 of the model note says so explicitly. Implementing an envelope
whose rate encoding is unknown, or deciding that `+0x0C0` is a filter cutoff rather than a
second gain term, would be inventing chip behaviour. Left out, deliberately.

What is known and already modelled: `+0x800` (log-domain level), which is why Piano is 5.38 dB
above Bright/Mellow today. `+0x080` was checked and is **not** the differentiator — its measured
values `0CC2 / 0CCE / 0D2C` are 0.03 dB and 0.28 dB apart.

### 4.3 The undumped wave banks

Unchanged and still dominant: 312 of 629 patches are wholly on IC304/305/306, 118 more partly;
inside the PIANO group 14 of 20 variants. `Rock Piano` (class 2) and every E.Piano are among
them. `wave_real` now marks those voices explicitly, and they keep the played note rather than
being placed from a register that describes a recording the emulator does not have.

### 4.4 An unrelated pre-existing stall, observed and CONTROLLED

During verification the machine stopped programming tone-gen registers part-way through long
scripted MIDI runs (e.g. after 15 notes at 0.55 s spacing). **Control**: replaying the same
notes at MIDI velocity 58 — which produces exactly the key-bed byte the *old* code produced for
velocity 100 — stalls at the identical instant (30 gates, last gate `t = 33.70343` in both
runs). So it is **not** caused by this change, and it cannot be caused by the pitch code, which
touches no voice-lifecycle state. Filed here as an observation for a later pass.

---

## 5. Reproduction

```bash
# 1. the two key-bed ROM curves and the inverse table (file offset = address - 0xEF00)
python3 - <<'EOF'
d=open('roms/kn5000/kn5000_subprogram_v142.rom','rb').read(); B=0xEF00
T1=list(d[0x1F43E-B:0x1F43E-B+256]); T2=list(d[0x1F53E-B:0x1F53E-B+256])
G=d[0x1F420-B+18]; O=d[0x1F421-B+18]; K1=d[0x1F418-B]; D=d[0x1F41A-B]
fw=lambda r:T2[max(0,min(255,(T1[r]-K1)*G//D+O))]
EOF

# 2. the trim is a function of the +0x040 word alone (Table-Data ROM walk)
#    SET table @0x077914, 15 bytes each; ptrA/ptrB rel32 vs *(0x045310)=0x050000;
#    ptrC = u32[ptrA]+base; zone slot E = ptrA[4+ptrC[key]]; record = ptrB + stride*E;
#    +0x040 = u16[record], trim = s16[record+4]  (stride 6 only)

# 3. live: select the variant from the panel, capture the register stream + audio
cd kn7000-emulator && VTAG=APD T_BASE=24.0 SLOT=14.0 \
  VSOUNDS="Piano:CPL_SEG10:2,Piano1Octave:CPL_SEG9:4,BrightPiano:CPL_SEG10:1,RockPiano:CPL_SEG9:2" \
  timeout 900 ./kn7000 kn5000 -rp roms -window -nomaximize -skip_gameinfo \
    -nvram_directory <copy of scratchpad/nvram2> -snapshot_directory <dir> \
    -midiin2 runD.mid -autoboot_delay 0 -autoboot_script <scratchpad>/vd/vcap4.lua \
    -seconds_to_run 82 -nothrottle -wavwrite apD.wav
#    Honky-Tonk is on SOUND page 2 (CPL_SEG9:0x04 with ':2'); select it FIRST or as the
#    second sound — the SOUND screen keeps whichever page it was left on.
```

Soft keys (`kn5000_cpanel.cpp`): `LEFT1..5 = CPL_SEG10:0x02, CPL_SEG10:0x01, CPL_SEG9:0x04,
CPL_SEG9:0x02, CPL_SEG9:0x01`; `RIGHT1..5 = CPL_SEG8:0x04, CPL_SEG8:0x02, CPL_SEG8:0x01,
CPL_SEG7:0x02, CPL_SEG7:0x01`; `PAGE = CPL_SEG2:0x80`; PIANO group = `CPR_SEG2:0x01`.

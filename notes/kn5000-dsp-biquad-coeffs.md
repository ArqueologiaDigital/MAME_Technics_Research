# NEC uPD6383GF — `op 0x70` decoded: the biquad coefficients, by construction

KN5000 IC311 effects DSP (NEC uPD6383GF-3BA). Date: 2026-07-22.
Tool: `tools/kn5000_dsp_biquadcoeffs.py`.

**This file is append-only successor material.** It does not edit
`notes/kn5000-dsp-biquad.md`, `notes/kn5000-dsp-parameters.md`,
`notes/kn5000-dsp-class2*.md`, `notes/kn5000-dsp-coefficients.md`,
`notes/kn5000-dsp-encoding.md` or `notes/kn5000-dsp-header.md`. Corrections to them are
in §8 here.

Every claim is tagged **MEASURED**, **PROVEN BY CONSTRUCTION**, **INFERRED** or
**SPECULATIVE**. §9 lists what is falsified or explicitly not established.

Reproduce:

```
python3 tools/kn5000_dsp_biquadcoeffs.py \
    ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom
```

---

## Headline

1. **★★★ The `op 0x70` eval helper is `LABEL_03A933`, and it is a textbook
   bilinear-transform biquad designer written in software floating point.** It is not a
   table, not a piecewise approximation, and not RBJ's form. It computes
   `K = tan(pi*f0/fs)` with `fs = 44100`, in IEEE **double**, using the ROM constant
   `pi/44100` at `0x012F57`, and then builds the classic
   `a0 = 1 + K/Q + K²`, `a1 = 2(K²−1)`, `a2 = 1 − K/Q + K²` triple.
   **PROVEN BY CONSTRUCTION.** (§2, §3)
2. **★★★ Its three inputs are literally frequency in Hz, Q, and gain in dB**, read from
   three ROM tables that the tool prints verbatim (§1):
   * `0x012397` — 27 × float32 = `40 50 63 80 … 12500 16000` — the ISO ⅓-octave centres.
     This is byte-for-byte the same list the parameters note found on the *main* CPU at
     `0x032390` ("40 … 16k, 27 entries"). Two ROMs, one list.
   * `0x012403` — 32 × float32 = `0.1 … 1.0 step 0.1`, `1.5 … 4.0 step 0.5`, `5 … 20 step 1`.
   * gain = `0.5 × user − 12.0` dB (doubles at `0x012F07` / `0x012F0F`), i.e.
     **−12.0 … +12.0 dB in 0.5 dB steps** — the main ROM's "+0.5 … +12.0" dB value list.
3. **★★★ FIVE coefficients are emitted, not six, and they are named:**

   | emit # | DSP word | value written | fixed point |
   |---|---|---|---|
   | 1 | `NN+0` | **b1** | `× 2^22` (and pre-halved, see §4) |
   | 2 | `NN+1` | **b0** | `× 2^22` (pre-halved) |
   | 3 | `NN+2` | **b2** | `× 2^22` (pre-halved) |
   | 4 | `NN+3` | **−a1/a0** | `× 2^22` |
   | 5 | `NN+4` | **−a2/a0** | `× 2^23` |

   `a0` is **not stored** — everything is divided by it in the sub-CPU. The recursive
   coefficients are stored **negated**, i.e. the DSP evaluates
   `y = b0·x + b1·x₁ + b2·x₂ + A1·y₁ + A2·y₂` with `A1 = −a1/a0`, `A2 = −a2/a0` — a
   pure MAC form, which is what a multiply-accumulate DSP wants.
   **MEASURED** (the emit sequence and its scale constants at `0x012FAB…0x012FBB`).
4. **★ The "sixth coefficient" of the previous note does not exist.** The host writer
   emits one pointer word plus **five** data words (`LABEL_0387E6` then 4 ×
   `LABEL_0388B3`). Algorithm 39's stride-6 blocks contain **one padding word each**.
   Independent confirmation: **algorithm 79 `GEQ`'s `T1 op 70` group is `84 89`, stride
   5.** MEASURED, and it is exactly the falsifiable cross-check the stride-6 argument
   needed. (§5)
5. **★ Three filter forms share the helper**, selected by the low nibble of the record's
   single immediate byte (§6): **mode 0 = peaking/parametric** (what `PARAMETRIC EQ`
   uses), **mode 1 = bandpass** (`b1 ≡ 0`, `b2 ≡ −b0`, no gain parameter),
   **mode 2 = a third form, not fully decoded**, which emits in a *different order* and
   through a *different writer*.
6. **★ Cut is implemented by reciprocating the section**, not by inverting `A`: for
   `gain < 0` the numerator and denominator polynomials swap wholesale. That is a real
   design decision and it is visible as two mirror-image blocks of divisions (§3.3).
7. **★★ ALL FOUR MANDATORY CHECKS PASS**, over the full **42 336**-preset grid
   (27 f0 × 32 Q × 49 gains): **0 unstable**, f0 recovered to **4.6e−12** relative, Q to
   **4.3e−12**, gain to **1.3e−10 dB**, and the response extremum sits on `f0`
   (1000 Hz → 1000.2 Hz, limited by the 1.0005 scan step). (§7)
8. Correcting the parameters note's own caveat: the **opcode → eval-helper table is now
   settled for all 25 jump-table entries** (§2.1). The old table was off by one from
   `0x64` onward, because entry 24 (`op 0x79`) is out of address order.

---

## 1. Where the numbers come from (MEASURED)

`LABEL_03A620` ("PRE") is called first by every `op 0x70` record. It:

* reads the record's **one immediate byte**: `AND A,0x0F` → the **form selector**
  (0/1/2); `AND C,0xF0` → `0x00/0x10/0x20`, which **shifts the parameter triple** so the
  same three user slots are read whichever of the three the user just edited;
* reads three consecutive user values from the per-unit value block and turns them into

```
    freq  = *(float*)(0x012397 + 4*value[i  ])      27 entries, ISO 1/3-octave
    Q     = *(float*)(0x012403 + 4*value[i+1])      32 entries, 0.1 .. 20.0
    gain  = (double)value[i+2] * 0.5 - 12.0         -12.0 .. +12.0 dB, 0.5 dB steps
```

* writes them, plus the form selector, to four caller slots (`XBC`, `XDE`, and two
  pushed pointers), then `RETD 0x10`.

> **This is the whole answer to "what does it read, in what units and ranges".**
> Frequency is *tabulated* (1996 fixed-point instinct — but only the user-value →
> Hz step; the filter design itself is not tabulated at all). Q is tabulated. Gain is
> affine. **MEASURED**, tool section `tables`.

The frequency table matching the main-CPU display list at `0x032390` is a cross-ROM
consistency check of the same kind the parameters note used for the effect names.

## 2. Finding the helper (MEASURED, and it corrects a published table)

`DSP_PerParameterTranslator` dispatches `0x61..0x79` through `OFFSETS_14745` with
`LDA XIX,0x03CB8E ; JP T,XIX+WA` (asm line 50934). Resolving every entry by locating its
`CALL` opcode (`0x1D`) in the ROM rather than by reading the listing:

```
   op 61 -> 03CB8E +000 -> 038E9F      op 6D -> 03CD3F +1B1 -> 039599
   op 62 -> 03CBDE +050 -> 038EAC      op 6E -> 03CD5C +1CE -> 0396C2
   op 63 -> 03CBFA +06C -> 038EB9      op 6F -> 03CD79 +1EB -> 0397F3
   op 64 -> 03CC33 +0A5 -> 038F9B      op 70 -> 03CD96 +208 -> 03A933   <-- THIS ONE
   op 65 -> 03CC50 +0C2 -> 038FE8      op 71 -> 03CDB9 +22B -> 0398CE
   op 66 -> 03CC6D +0DF -> 039206      op 72 -> 03CDD6 +248 -> 039ABD
   op 67 -> 03CC8A +0FC -> 03925E      op 73 -> 03CDF3 +265 -> 039D26
   op 68 -> 03CCAB +11D -> 0392AC      op 74 -> 03CE10 +282 -> 03869B/039D98
   op 69 -> 03CCC8 +13A -> 0392F2      op 75 -> 03CE25 +297 -> 039D98
   op 6A -> 03CCE5 +157 -> 03943B      op 76 -> 03CE42 +2B4 -> 03B646
   op 6B -> 03CD02 +174 -> 0394CD      op 77 -> 03CE65 +2D7 -> 03A22A
   op 6C -> 03CD1F +191 -> 039525      op 78 -> 03CE82 +2F4 -> 03A282
                                       op 79 -> 03CC16 +088 -> 038EF6
```

**MEASURED, all 25.** The reason the parameters note's table went wrong at `0x64` is
visible here: entry 24 (`op 0x79`) has offset `0x088`, which falls *between* `0x06C` and
`0x0A5`, so an address-ordered walk shifts everything after `op 0x63` by one.

**Two entries are structurally different from the other 23**: `op 0x70` (→ `03A933`) and
`op 0x76` (→ `03B646`) call **no writer** afterwards — they emit their own words. Every
other handler is the fixed `eval → one writer` stub. That alone identifies `0x70` as a
multi-word coefficient generator before any of its arithmetic is read.

`0x0397F3` (`op 0x6F`) — which the parameters note tentatively bound to `0x70` — is an
ordinary single-value helper. That binding is corrected here.

### 2.1 The floating-point library (MEASURED, by decode-routine signature)

`LABEL_03A933` is nothing but calls into the sub-CPU's soft-float library. The routines
split cleanly by which decoder they call (`03DF9C` = unpack **float32**, `03DF60` =
unpack **float64**) and by their sign-branch polarity:

```
   03E2C0  float  mul     03E290  double mul      03DCF2  float -> double
   03D3D4  float  div     ---                     03DD6C  double -> float
   03E15A  float  add     03E10E  double add      03D41C  float negate
   03D92C  float  sub     03D8E0  double sub      03D49A  sign test (-> HL)
   03D4C9  double, one arg on stack  = tan()   (rejects exponent >= 0x41E)
   03D533  double, two args on stack = pow()
```

`03E290` is pinned as *multiply* by construction: its first use is
`w = f0 * (pi/44100)`. The add/sub polarity is pinned because `03DF38` (magnitude-add)
is reached from `03E15A` when the signs are **equal** and from `03D92C` when they
**differ**. `03D4C9` is pinned as `tan` by the coefficients it produces (§3).

## 3. ★★★ The arithmetic, mode 0 (PROVEN BY CONSTRUCTION)

Transcribed from `LABEL_03A933` (asm 48529…), with the ROM constants substituted:

```
    K   = tan( f0 * 0x012F57 )                  ; 0x012F57 = pi/44100  (double)
    K   = (float) K
    A   = K / Q                                 ; 0x03D3D4 float div
    B   = K * K                                 ; 0x03E2C0 float mul
    a0  = (A + B) + 1.0                         ; const 0x012F5F = 1.0f
    a1  = (1.0 - B) * (-2.0)                    ; consts 0x012F63 = 1.0f, 0x012F67 = -2.0f
    a2  = (B - A) + 1.0                         ; const 0x012F6B = 1.0f
    V   = pow(10.0, |gain| / 20.0)              ; consts 0x012F6F = 20.0f, 0x012F73 = 10.0
    n0  = ((double)A * V + 1.0) + (double)B     ; const 0x012F7B = 1.0
    n1  = a1                                    ; a verbatim 4-byte copy [D2] -> [C6]
    V   = pow(10.0, |gain| / 20.0)              ; computed a SECOND time, consts 0x012F83/87
    n2  = (1.0 - (double)A * V) + (double)B     ; const 0x012F8F = 1.0
```

`a0/a1/a2` is the bilinear-transform denominator of a second-order section with
`K = tan(w0/2)`. **This is what proves `03D4C9` is `tan`**: no other function of
`pi*f0/fs` makes `1 ± K/Q + K²` the right thing. **PROVEN BY CONSTRUCTION.**

Note `n1 == a1` **as a byte copy, not as a recomputation** — the firmware literally
`LD XWA,(XSP+0d2h) ; LD (XSP+0c6h),XWA`. The brief anticipated exactly this shared term.

### 3.1 The boost / cut fork (MEASURED)

`03D49A(&gain, BC=1)` is a sign test; the two arms are mirror images:

```
    gain >= 0  (BOOST)                gain < 0  (CUT)
      b0 = n0 / a0                      b0 = a0 / n0
      b1 = n1 / a0                      b1 = a1 / n0
      b2 = n2 / a0                      b2 = a2 / n0
      A1 = -a1 / a0                     A1 = -n1 / n0
      A2 = -a2 / a0                     A2 = -n2 / n0
```

**The cut branch reciprocates the whole section.** A consequence, stated before it was
tested: *for a cut, the recovered pole Q must be `Q / 10^(|gain|/20)`, not `Q`.* §7
confirms this to 4.6e−12 over all 20 736 cut presets — so the cut arm's filter is
narrower in the pole sense by exactly the linear gain, which is the standard
"reciprocal-peak" EQ and is symmetric with the boost curve by construction.

### 3.2 The normalisation, and the halving (MEASURED)

```
    N   = (1.0 - A1 - A2) / (b0 + b1 + b2)      ; const 0x012F97 = 1.0f
    if (compare N against 0x012F9B = 1.0f fails)  N = 1.0f
    b0 = N * b0 / 2.0 ; b1 = N * b1 / 2.0 ; b2 = N * b2 / 2.0   ; 0x012F9F/A3/A7 = 2.0f
```

`N` is literally `1 / H(z=1)`: it forces the section's **DC gain to unity**. For a
peaking section the DC gain is already 1, and the tool measures `N = 1.000000` on every
one of the 42 336 presets — so `N` is a *guard*, not a shaper. **MEASURED.** The
`1.0f` comparison at `0x012F9B` is a range/NaN guard; its exact predicate is
**NOT ESTABLISHED**.

The `/2.0` is applied to the numerator only, so it is a clean **−6.02 dB output
attenuation** of the whole section (`DC gain 0.500000` in §7's dump).
**INFERRED, strong:** headroom for the boost case — with `+12 dB` the peak reaches
+6 dB in the DSP's units, exactly half of the Q1.22 range's usable span. It is not a
Q-format artefact: `−a1` gets the same `2^22` scale without any halving.

### 3.3 Mode 1 = BANDPASS (MEASURED)

Identical `K`, `A`, `B`, `a0`, `a1`, `a2` (constants `0x012FBF`, `0x012FC7…D3`), then

```
    b0 = A / a0        b1 = 0 (stored literally)        b2 = -b0
    A1 = -a1 / a0      A2 = -a2 / a0                    no gain parameter, no N
```

`H(z) = (A/a0)(1 − z⁻²)/…` — zeros at DC and Nyquist, unity gain at the peak. The tool
confirms: peak at `f0`, peak magnitude `1.0000`, DC gain `0.00e+00`, stable.

### 3.4 Mode 2 — NOT DECODED (stated as such)

Reached at `LABEL_03B08A`. It also starts from `tan`, but inserts `LABEL_03D3A4` with a
further constant (`0x012FF3`) and multiplies the tangent by three more doubles
(`0x012FFB`, `0x013003`, `0x01300B`, all equal to `pi/44100` — i.e. it forms `K` and
something like `K·w0` or `K²·w0²`). It runs the same `pow(10, |g|/20)` twice, the same
boost/cut fork, and then emits in a **different order**
(`b1, b2, −a2, b0, −a1`, scales `2^22, 2^22, 2^23, 2^22, 2^22`) through a **different
continuation writer** (`LABEL_038405`, not `0388B3`) — i.e. into the other of the two
memories the parameters note identified. **A shelving section is the obvious candidate
and is NOT claimed.** No algorithm in the corpus was checked for using it.

## 4. What reaches the DSP (MEASURED, byte-for-byte)

The five results are converted by `LABEL_03D44C` (float → 24-bit int) after a final
multiply, and written:

```
    b1  * 0x012FAB (= 4194304 = 2^22)   -> LABEL_0387E6   pointer word + data word
    b0  * 0x012FAF (= 2^22)             -> LABEL_0388B3   data word only
    b2  * 0x012FB3 (= 2^22)             -> LABEL_0388B3
    A1  * 0x012FB7 (= 2^22)             -> LABEL_0388B3
    A2  * 0x012FBB (= 8388608 = 2^23)   -> LABEL_0388B3
```

`0387E6` emits `08 01 (A>>4) ((A<<4)|8) 21` = `801.0.AA.821` (the proven pointer load)
followed by one `0xA__` data word; `0388B3` emits **only** the data word, with the same
`v>>1 / v>>9 / v>>1 / (v<<7)|0x26` scatter. **So the DSP-side block is one pointer set
plus five consecutive coefficient words at `AA, AA+1, AA+2, AA+3, AA+4`.**

Fixed-point formats, therefore: `b0, b1, b2, −a1/a0` are **signed Q1.22**, and
`−a2/a0` is **signed Q0.23** — which is right, because `|a2/a0| < 1` is precisely the
stability condition and the other four routinely exceed 1. This is a *different* format
from the Q0.23 the coefficients note established for static program constants, and it is
per-word. **MEASURED.**

## 5. ★ Five, not six — and the stride-6 padding

The previous note's central inference was "six coefficients per band, because the host
writes stride 6 and the section has six class-A multiplies". The first half is now
falsified by construction: **five words are written.**

The independent confirmation is `T1 op 70` across the corpus:

```
   algo 39 PARAMETRIC EQ   00 06 0C 12 18 | 64 68 6C 70 74     stride 6 | stride 4
   algo 79 GEQ             84 89                               stride 5   <-- !
   algo 35 EXCITER         03 0E          algo 71 PEQ+CHORUS   02 12
   algo 72 PEQ+S.DELAY     00 0A          algo 73 PEQ+FLANGER  04 14
   algo 74 PEQ+VIBRATO     04 11          algo 75 PEQ+COMPR    00 0F
   algo 96 …               00 13          algo 97 …            00 16
   algo 98 …               00 0E          algo 99 …            00 14
```

**GEQ's stride is 5.** Algorithm 39's stride-6 blocks therefore carry **one unused
padding word each** (`0x05, 0x0B, 0x11, 0x17, 0x1D`), and the two-entry combination
effects place their two independent sections wherever they fit (strides 10…22). The
5-word block is the invariant; 6 was an artefact of one algorithm's allocation.

**Ask what the instrument was blind to** (the brief's rule): the stride-6 reading could
not see that a block may be padded, because algorithm 39 is the only image with more
than two blocks, and its own spacing was the only evidence. GEQ is the first
independent measurement of the block size, and it disagrees.

## 6. Fold-back onto the microcode section

The section (previous note §2) is nine words, of which `[0]` is the only one whose bits
vary with the effect (the source-select multiply) and `[1]..[7]` are byte-identical in
all 27 sections corpus-wide. That leaves exactly **five source-independent class-A
multiplies**: `[1] 212.A.01.412`, `[2] 202.A.01.1D5`, `[3] 202.A.01.1D4`,
`[4] 202.A.00.1D5`, `[7] 212.A.FF.407`.

> **INFERRED (not proven):** if the coefficient cursor advances one per class-A word
> from the block base, the section reads the five words in the order the host wrote
> them, giving
> `[1] = b1, [2] = b0, [3] = b2, [4] = −a1/a0, [7] = −a2/a0`.
> **A coherence that was not used to construct the mapping:** `[7]` is the one word
> whose coefficient has a *different fixed-point scale* (Q0.23 vs Q1.22), and it is the
> only class-A word that follows the operand-less class-8 word `804.8.16.415` — whose
> previously *speculated* role was "a shift, a saturate, or a transfer into the
> multiplier latch". A shift by one is exactly what a Q1.22 → Q0.23 change of scale
> needs. This is **suggestive, not established**, and it is recorded here so it can be
> tested rather than believed.
>
> **What this does NOT resolve:** the previous note's cursor walk gives the *state*
> displacements (+4 per band), and the *coefficient* cursor is a second, independent
> pointer whose advance is not observed in any word. The order above is the natural
> reading, not a measured one.

The transposed-direct-form-II conclusion (2 stores, 4 state cells) is untouched by this
work and is neither confirmed nor contradicted: five coefficients is what DF-II-T needs.

## 7. ★★ The mandatory falsification pass — numbers

Tool section `check`. The grid is every value the user can actually select:
27 frequencies × 32 Q values × 49 gains = **42 336 presets**.

```
  cases                             : 42336
  unstable / non-invertible         : 0
  worst relative f0   error         : 4.649e-12
  worst relative Q    error (BOOST) : 4.347e-12
  worst absolute gain error         : 1.251e-10 dB
  CUT: worst |Q_rec - Q/10^(|g|/20)| : 4.647e-12     (the pre-registered prediction)
```

Stability was tested as the textbook pole condition `|a2| < 1 and |a1| < 1 + a2` on the
*stored* coefficients (with `a1 = −A1`, `a2 = −A2`) — **0 failures out of 42 336**,
including the extremes `f0 = 40 Hz, Q = 20` and `f0 = 16 kHz, Q = 0.1`.

Response extremum, scanned at 5 ppt resolution:

```
    f0=1000  Q=1    g=+12.0 -> extremum at  1000.2 Hz, +5.979 dB abs, DC 0.500000, stable
    f0=1000  Q=1    g=-12.0 -> extremum at  1000.2 Hz, -18.021 dB abs, DC 0.500000, stable
    f0=250   Q=4    g= +6.0 -> extremum at   250.0 Hz,  -0.021 dB abs, DC 0.500000, stable
    f0=6300  Q=0.7  g= -9.0 -> extremum at  6301.1 Hz, -15.021 dB abs, DC 0.500000, stable
```

The extremum sits on `f0` to within the scan step in every case, and the *relative*
level (extremum minus the 0.500000 DC gain, i.e. −6.021 dB) is `+12.000`, `−12.000`,
`+6.000`, `−9.000` dB. **The requested gain comes back exactly.**

Mode 1: peak at `f0`, peak gain `1.0000`, DC gain `0.00e+00` (a true zero at DC),
stable — a textbook bandpass.

Sample emitted words (mode 0, so they can be recognised in a live capture):

```
    f0=1000 Q=1  g=+12.0 dB ->  b1=C4D91D  b0=2652E2  b2=156F03  -a1=764DC6  -a2=90F86E
    f0=1000 Q=1  g=-12.0 dB ->  b1=CE9BD2  b0=1AB840  b2=172D5C  -a1=62C85B  -a2=B86993
    f0=16000 Q=0.1 g=+12 dB ->  b1=08AFE0  b0=6B80A4  b2=A1D7C8  -a1=EEA041  -a2=4A9E50
```

**A note on what could NOT be done.** The brief asked for the six words of a stored PEQ
*preset* to be inverted. There are none: `op 0x70` coefficients are **computed at run
time from the user's values and never stored in ROM** (algorithm 39's static coefficient
bank is the 45-word, 43-zero scratch area the previous note already found). The check
above is therefore run on the firmware's own arithmetic over its own complete input
domain, which is strictly stronger than inverting one preset, but it is a different
test from the one the brief specified and is flagged as such.

## 8. Corrections to the earlier notes

| earlier claim | source | status here |
|---|---|---|
| "the band really does have **six** coefficients" | biquad note §2 headline 1 | **CORRECTED**: five are written (`0387E6` + 4 × `0388B3`); GEQ's stride-5 `T1` group confirms independently. The stride-6 blocks of algo 39 are padded. |
| "the identity of the six coefficients is NOT ESTABLISHED" | biquad note §9 | **RESOLVED for five**: `b1, b0, b2, −a1/a0, −a2/a0` in emission order, PROVEN BY CONSTRUCTION |
| `op 0x70 -> LABEL_0397F3` | parameters note §6 (self-flagged as partly wrong) | **CORRECTED**: `0397F3` is `op 0x6F`; `op 0x70 -> LABEL_03A933`. All 25 entries re-derived (§2). |
| 44 100 Hz from `ms × 0xAC44 / 0x3E8` | parameters note §3 | **CONFIRMED by a second, independent constant**: the double `pi/44100` at `0x012F57` (`7.1237928650000007e-05`), used in three separate places (`0x012F57`, `0x012FBF`, `0x012FEB`) |
| main-CPU value list "40 … 16k, 27 entries, ISO ⅓-octave" | parameters note §4 | **CONFIRMED cross-ROM**: the sub-CPU holds the same 27 values as float32 at `0x012397` |
| main-CPU dB list "+0.5 … +12.0" | parameters note §4 | **CONFIRMED**: `gain = 0.5·v − 12.0`, i.e. −12 … +12 dB in 0.5 dB steps |
| coefficients are signed Q0.23 | coefficients note | **REFINED, not refuted**: parameter-path biquad coefficients are Q1.22 except `−a2/a0`, which is Q0.23. The scale is chosen per word by an explicit float multiplier in ROM. |
| `801.0.NN.821` = pointer load, then stream data | parameters/header notes | **CONFIRMED again**: `0387E6` sets the pointer and writes word 0; `0388B3` writes words 1–4 with no pointer |
| class-8 word `804.8.16.415` is "a shift, a saturate, or a latch transfer" | biquad note §5, SPECULATIVE | **still SPECULATIVE**, but §6 notes the Q1.22 → Q0.23 scale change lands exactly across it |

## 9. Falsified, or explicitly not established

* **"Six coefficients per band."** FALSIFIED (§5). Five.
* **Mode 2** (`LABEL_03B08A`): not decoded, and no algorithm was checked for using it (§3.4).
* **`op 0x76` → `LABEL_03B646`**, the other self-emitting handler (used by `GEQ`), is
  untouched. It is the obvious next target and probably shares this helper's shape.
* **The `0x012F9B` guard predicate** in §3.2 (`ToneGen_Compare_Voice_32(N, 1.0f, DE=0)`).
* **Which class-A word reads which coefficient** (§6): INFERRED from emission order and
  a scale-change coincidence, not measured. The coefficient cursor's advance rule is not
  observed anywhere.
* **How the five bands of algorithm 39 pick their `T1` entry.** Algo 39's whole `T2`
  stream is a *single* record — `00 06 | 70 00 00 | 7A` (op `0x70`, operand `0x00`,
  immediate `0x00` = form 0, slot-shift 0) — yet `T1 op 70` has ten addresses. The band
  index must be derived from the parameter index inside `LABEL_03CF53` or the `op 0x70`
  stub. NOT TRACED. (This also revises the previous note's "T2: 15 records, op70
  operands 0,0,0 1,1,1 …", which came from a heuristic record splitter; the raw record
  is 6 bytes long.)
* **What the padding word at `NN+5` is for**, if anything (§5).
* **`EXCITER` (algo 35) has a `T1 op 70` group but its `T2` never uses `op 0x70`**
  (its stream is `61 00 | 61 01`). Its biquad is configured some other way. Not chased.

## 10. Next experiments, in order of value

1. **Decode `op 0x76` / `LABEL_03B646`** (`GEQ`). Same shape, and `GEQ`'s stride-5 group
   makes it the cheapest confirmation that the 5-word block is universal.
2. **Decode mode 2.** If it is a shelf, the KN5000's EQ forms are then complete.
3. **Trace the band-index resolution** (`LABEL_03CF53` with `op 0x70`) — that closes the
   last gap between "one T2 record" and "ten T1 addresses", and it is the same lever the
   previous note wanted for the state block.
4. **Test the `[7] = −a2` / class-8-word coincidence** (§6) by finding another program
   where a class-8 word precedes a coefficient of different scale.

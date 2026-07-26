# KN5000 tone-gen (IC303) AUDIT — the TIMBRE / FILTER path (`+0x080 +0x0C0 +0x100 +0x140 +0x180`)

Audit dimension: **the "Bright vs Mellow" gap.** Requested by Felipe Sanches, 2026-07-26.
Analysis + live measurement only; no `src/` edits, no rebuild. The only tracked change is this note.

Evidence labels: **MEASURED** (ROM bytes / disasm line / value read off a running machine),
**INFERRED** (deduction from measured data), **SPECULATIVE** (unproven). Every prediction that was
checked is reported with its result, including the misses.

Sources
* sub-CPU disasm `kn5000-roms-disasm/archive/asl/subcpu/kn5000_subprogram_v142.asm`
  (line numbers below are 1-based in that file; runtime address → ROM file offset = `addr − 0xEF00`,
  verified this pass against `original_ROMs/kn5000_subprogram_v142.rom` and identical to the
  convention `kn5000.cpp` already documents for the key-bed tables).
* Table-Data ROM `original_ROMs/kn5000_table_data.rom`; patch/partial index
  `notes/data/kn5000-patch-partials.tsv`.
* Live ground truth: `notes/kn5000-live-captures.md` §3-§4 (16 sound groups × 7 notes) and
  `notes/kn5000-variant-diagnosis.md` §3.1 (Piano / Bright Piano / Mellow Piano full note-on burst).
* **New live capture this pass** — 6 notes (C2 C4 E4 G4 A4 C6) on the default RIGHT1 Piano, tapping
  `0x100000`/`0x100002` on the sub-CPU bus plus the RAM inputs of the traced builder. Isolated
  **copy** of the nvram (`kn7000-emulator/nvram` never touched); scripts
  `tools/timbre_tap.lua` and `tools/timbre_tap2.lua` (committed).
* HLE `src/mame/matsushita/kn5000_tonegen.{cpp,h}`.

---

## 0. TL;DR

The timbre path is now **fully traced from patch byte to register bit**, and the decode is
**MEASURED-validated with 9 exact hits on `+0x100`, 18 on `+0x140`, 6 on `+0x080`'s pitch-class
field and 2 on `+0x0C0`** (§1.7). The headline result:

> **`+0x100` bits[6:0] is the per-voice TVF (filter/brightness) parameter.** The firmware computes it
> at note-on as
> `clamp( base + veldepth·CURVE[curve][velocity]/32 + keydepth·(clamp(note,lo,hi) − centre)/32 + 0x18 , 0, 0x78 )`
> and `0x7F` is written when the voice has no filter (bypass). For **Bright Piano it is 0x61 and for
> Mellow Piano 0x45 at the very same key and velocity** (MEASURED live) — a 28-unit difference, and
> the HLE reads neither.

Everything Felipe hears as "Bright Piano and Mellow Piano are the same sound" is that one 7-bit field.
Implementing a single low-pass filter driven by `regs[4] & 0x7F` separates **302 of the 585 patches**
into distinct timbres that are bit-identical today (§3, Gap 1).

---

## 1. WHAT THE FIRMWARE DOES (all MEASURED, cited)

### 1.1 The delivery burst and the scratch struct

`ToneGen_WriteVoiceParams` (asm **L29565**) bursts a 44-byte scratch struct at **0x0451CC** to the
chip, one 16-bit register per field. Confirmed byte-for-byte this pass:

| scratch | reg | asm line | fills |
|---|---|---|---|
| +0x02 | **+0x040** | L29573 | wave select (solved elsewhere) |
| +0x04 | **+0x080** | L29588 (bit15 **SET**) and again L29901 (bit15 **RES**) | level + 3-bit field |
| +0x06 | **+0x0C0** | L29604 | timbre pair |
| +0x08 | **+0x100** | L29619 | **TVF / brightness** |
| +0x0a | **+0x140** | L29634 | second timbre pair |
| +0x0c | **+0x180** | L29649 | expression |
| +0x16 | +0x500 | L29724 | key-scaled pair |

**`+0x080`'s bit 15 brackets the whole burst**: it is SET on the first write (L29594 `SET 0fh,WA`) and
RES on the very last write of the burst (L29907 `RES 0fh,WA`), i.e. it is a *parameter-load strobe*,
not part of the value. (MEASURED. The HLE currently treats that same bit as a "waveform pointer
latch", `kn5000_tonegen.cpp:255`; that happens to fire at a harmless moment — see §4.)

A grep of *every* `ADD WA,<offset>` register write in the ROM shows **`+0x100` and `+0x140` are
written from exactly one place — the note-on burst (L29619 / L29634)**. The per-segment envelope
updater `LABEL_02CD71` (L29178) touches only groups 8/9/10 and `+0x000`. **So the timbre registers are
static for the whole life of a note.** MEASURED.

### 1.2 The two data structures the builders read

From the note-on setup (L26947-26967):
* `desc+0x23` = **PART struct** `0x041368 + part*0x11F` (live per-part state).
* `desc+0x13` = the **tone record** (`*(part+0x06)`), and `desc+0x17` = **VP**, the patch's
  **0x51-byte per-partial block** (the `block_addr` column of `notes/data/kn5000-patch-partials.tsv`;
  Piano partial 0 = sub 0x05253A = ROM 0x3253A, partial 1 = +0x51).
* `desc+0x27` = the tonerec/zone struct (`part + 0x6E + zone*0x25`).
* `desc+0x08` high byte = the **played note**; `desc+0x0c` = the **velocity**.
  MEASURED live this pass (C2/C4/E4/G4/A4/C6 gave `desc+0x08` = 0x2480/0x3C80/0x4080/0x4380/0x4580/
  0x5480 = notes 36/60/64/67/69/84, while `desc+0x0c` stayed 100 = the driver's fixed
  `KEYBED_VELOCITY`). **This corrected an earlier reading of mine that had the two swapped.**

### 1.3 `+0x100` — the TVF / brightness register (the load-bearing decode)

Chain: note-on `LABEL_02B4E3` (**L26803**) → `LABEL_024102` (**L16748**, builds `desc+0x42`/`+0x44`)
→ `LABEL_024444` (**L17106**, emits them to the scratch).

`LABEL_024102` dispatches on `VP[+0x36] & 7` through a 6-entry jump table at 0xF6A7 →
{`022DA1`, `023D01`, `023DB5`, `023EC2`, `023FBD`, `02403D`}. **All 16 SOUND-GROUP defaults and all 20
PIANO-group variants use index 1 = `LABEL_023D01` (L16312)** (MEASURED from the patch bytes).

`LABEL_023D01` computes:

```
V = LABEL_022C06( base = VP[+0x4d] + (int8)PART[+0x67],
                  depth1 = (int8)VP[+0x37],
                  depth2 = (int8)VP[+0x3c] )
desc+0x42  (-> +0x100) = ((VP[+0x4e] & 7) << 13) | 0x0400 | V
desc+0x44  (-> +0x140) = LABEL_022CF8(VP[+0x50]) | LABEL_022CE8(VP[+0x4f])
```

and `LABEL_022C06` (**L14509**) is:

```
if (depth1 != 0)                                  ; VELOCITY sensitivity
    base += depth1 * (int8)KSCURVE[(VP[0x36]&0xE0)>>5][ desc[+0x0c] & 0x7F ] / 32
                                                  ; KSCURVE = 7 x 128 signed bytes @ 0x011519 (L14527)
if (depth2 != 0)                                  ; KEY follow
    base += depth2 * ( clamp(desc[+0x08]>>8, VP[+0x3a], VP[+0x3b]) - VP[+0x39] ) / 32
base += 0x18
V = clamp(base, 0, 0x78)                          ; LABEL_022BF2, L14494
```

The seven key-scale curves at **0x011519** were dumped: each is 128 signed bytes running from **−64 at
index 0 to ≈0 at index 127**, with progressively flatter knees (curve 0 concave, curve 6 nearly
linear-to-zero-by-key-96). Indexed by **velocity**, that is exactly a set of selectable
**velocity→brightness curves: soft playing subtracts up to 64 units, hard playing subtracts none.**

Per-partial field map (MEASURED):

| VP field | role |
|---|---|
| `+0x36` bits2:0 | builder/emitter select (1 for every stock sound) |
| `+0x36` bits7:5 | **velocity curve** index 0..6 into 0x011519 |
| `+0x37` | **velocity depth** (signed) |
| `+0x39` | **key-follow centre key**; `+0x3a`/`+0x3b` = key range lo/hi |
| `+0x3c` | **key-follow depth** (signed) |
| `+0x4d` | **base cutoff** |
| `+0x4e` | 3-bit field placed at `+0x100` bits[15:13] (values 0/1/2 observed) |
| `+0x4f` | `+0x140` low 7 bits (`+0x18`, clamp 0x78) |
| `+0x50` | index (+ sign bit 7) into the 16-entry ± amount table for `+0x140` bits[15:7] |
| `PART[+0x67]` | live per-part offset added to the base (0 in the current nvram, MEASURED) |

The emitter `LABEL_024444` can additionally add or subtract `(int8)PART[+0x1f]` from the low 7 bits of
`+0x100` (case 1 → `LABEL_024366` L17006) and of both registers (cases 3-5 → `LABEL_0243CC` L17053),
gated on `tonerec[+0x18]` bit 6 (enable) / bit 7 (direction) — a live controller offset, re-clamped to
`[0,0x78]`. MEASURED.

**The "no filter" default** `LABEL_022DA1` (**L14697**) writes `+0x100 = 0x017F`, `+0x140 = 0x7F7F`.
The computed path can never reach 0x7F (it is clamped to 0x78), so **0x7F is a reserved
"wide-open / bypass" code**. MEASURED — this is what fixes the polarity of the field without any
guesswork: *higher = brighter, max = no filtering.*

### 1.4 `+0x140` — a per-partial pair, decode exact, meaning not established

`LABEL_022CE8` (**L14610**) = `min(x + 0x18, 0x78)`.
`LABEL_022CF8` (**L14620**) takes `VP[+0x50]`, uses its low nibble as an index into a 16 × 3-byte table
(**0x0119FB** when bit7 = 0, **0x011A25** when bit7 = 1) and returns `(B << 8) | A`, also stashing a
signed byte `C` in the global 0x2940. Dumped:

```
n         0    1    2    3    4    5    6    7    8    9   10   11   12   13  14  15
B       00   40   4E   5B   66   6F   78   7F   78   6F   66   5B   4E   40  00  00
A(b7)  0x80 ...........................  0x00 ..........................  (mirrored in the other table)
C        0  -16  -13  -11   -8   -5   -3    0    0    0    0    0    0    0   0   0
```

So `+0x140 = {[15:8] = a 7-bit amount, [7] = its sign, [6:0] = VP[+0x4f]+0x18}` — symmetric about
n = 7 (amount 0x7F, sign 0). It is **instrument-characteristic and neither key- nor velocity-scaled**
(MEASURED: constant across 7 notes for all 16 sound groups, `kn5000-live-captures.md` §4).
Its physical role is **NOT established**; the shape (a signed amount plus a static level) is what a
filter-EG depth / LFO depth would look like, but nothing in the firmware names it. SPECULATIVE.

### 1.5 `+0x080` — level + a pitch-class field

`LABEL_026637` (**L20622**, last function of the note-on chain) accumulates a level, then
`LABEL_0232C7` (**L15195**) finishes it:

```
idx = clamp( acc + PART[+0x0c] + PART[+0x10] + desc[+0x33] , 0, 0xFF )     ; L15180 clamp
lvl = 2 * LOGTAB[idx]                       ; LOGTAB = 256 words @ 0x010764 (L15205)
if (rec[+0x02] bit7)  hi3 = (rec[+0x02] & 0x70) << 8          ; per-partial constant
else                  hi3 = KEYTAB[ desc[+0x06] >> 8 ]        ; 128 words @ 0x00FBE4 (L15219)
+0x080 = 0x8000 | hi3 | lvl                                    ; L15233
```

* **LOGTAB @0x010764** was dumped: `LOGTAB[16E+M] = 128·E + 128·log2(1+M/16)` — a mini-float
  (4-bit exponent / 4-bit mantissa) → log2 converter, so `+0x080` bits[11:0] = `256·log2(level)`.
  MEASURED, and the arithmetic reproduces the live value exactly (Piano C4 `+0x080` low12 = 0x0E52 =
  2 × LOGTAB[228]).
* **KEYTAB @0x00FBE4** was dumped: 128 words that repeat every 12 entries with values
  `0,0,1,2,2,3,4,4,5,6,6,7 (×0x1000)` = **`floor(2·(key mod 12)/3) << 12`**. So `+0x080` bits[14:12]
  are a 3-bit **pitch-class-derived** field (or a per-partial constant when `rec[+0x02]` bit 7 is set).
  **PREDICT-THEN-CHECK, 6/6 HIT** (new live capture): C4→0, E4→2, G4→4, A4→6, C2→0, C6→0.
  **What that 3-bit field MEANS is not established** — it is a *pitch-class*, not a monotone
  key-scale, so it is not a level trim; it is more likely a chip-internal wave/interpolation selector.
  Saying so is the honest result; do not invent a use for it.
* `VP[+0x17]` is the per-partial level trim inside the accumulation (Piano 0x54 / Bright 0x56 /
  Mellow 0x5C → level index 203 / 204 / 210 in the live capture; the Bright→Mellow step of +6 matches
  the byte delta of +6 exactly, the Piano→Bright step is +1 against a byte delta of +2 — one unit not
  attributed, from another of the differing bytes. Reported as a miss.)

### 1.6 `+0x0C0`, `+0x180`, `+0x500` — decoded, roles partly open

* **`+0x0C0`** = `LABEL_0253FE` (**L18655**, store L18733) / variant `LABEL_025499` (L18736):
  `hi = clamp(PART[+0x0f] + (tonerec[+0x5c] − 0x40) + (int8)PART[+0x66], 0, 0x7F)` (`0` if
  `PART[+0x0f]==0`), `lo = PART[+0x12]`, forced to `0x7F` when the part mode `*(0x04134C)` is 5 or 6.
  **PREDICT-THEN-CHECK, 2/2 HIT:** the tone-record byte `rec+0x5C` is 0x5A for Piano and 0x40 for
  Bright/Mellow (dumped this pass) — a delta of 0x1A — and the measured `+0x0C0` high bytes are
  0x74 and 0x5A, delta 0x1A exactly. It is **not key- or velocity-scaled**.
  Role: a per-part/per-patch 7-bit amount on the part-volume path. **Polarity NOT established** — see
  Gap 4, which states the falsifiable hardware test rather than guessing.
* **`+0x180`** = `desc+0x2b` (`LABEL_0249BF`, **L17662**): `0x0000`, `0x007F`, or `VP[0]`, chosen by the
  part-mode byte at 0x04138E. Rewritten per tick by the second-domain envelope stepper
  (`LABEL_026EC3` → `LABEL_02D670`, already documented in `kn5000-tonegen-register-semantics.md` Q3).
* **`+0x500`** = `LABEL_0248D5` (**L17566**): two 7-bit values, each `0x7F` plus a key-scaled term
  (`LABEL_022B2A`) from `VP[+0x12]` / `VP[+0x48]`, clamped `[0,0x7F]`. Piano/Bright/Mellow are all
  `0x2C68` — it does **not** carry the variant difference.

### 1.7 Prediction ledger (all checks run this pass)

| prediction | result |
|---|---|
| `+0x140` from `VP[+0x4f]/VP[+0x50]` for the 16 SOUND-GROUP defaults | **15/16 exact.** Miss: DRUM KITS (predicted 0x7F58, live 0x7F5F) — drum kits take the per-key wave-fallback path (`pb0a` bit15), so partial 0 of the tone record is not the block in play. Expected, reported. |
| `+0x140` for Piano / Bright / Mellow | **3/3 exact** (0x6FDA / 0x5BDA / 0x5BDA) |
| `+0x100` for Piano at 6 notes, velocity 100 (new live run) | **6/6 exact** (0x2466/0x2466/0x2467/0x2468/0x2469/0x246D) |
| `+0x100` for Piano / Bright / Mellow at C4 (diagnosis-note capture) | **3/3 exact** (0x244E / 0x2461 / 0x2445) at one common effective velocity of 58 — the same solved velocity for all three, which is itself a consistency check |
| `+0x080` bits[14:12] = `floor(2·(key mod 12)/3)` | **6/6 exact** |
| `+0x0C0` high byte delta = `tonerec[+0x5c]` delta | **2/2 exact** |
| `+0x080` low 12 bits = `2·LOGTAB[idx]` | exact for Piano C4; the Piano→Bright index step is +1 vs the +2 predicted from `VP[+0x17]` alone — **1 unit unattributed, reported as a miss** |

The two independent live runs disagree on the absolute `+0x100` value (0x2466 vs 0x244E at C4) purely
because their effective velocities differ (100 vs 58); the same formula reproduces both. That is the
strongest possible evidence that the velocity term was decoded correctly.

### 1.8 Corroboration that IC303 really has a per-voice filter (INFERRED)

The main-CPU ROM's Sound Editor carries per-tone **filter** pages — `SeFilLpq1TitleFunc`,
`SeFilHpq1TitleFunc`, `SeFilBpf1TitleFunc`, `SeFilBcf1TitleFunc`, `SeFilFil2TitleFunc`,
`SeFilEnv1/2TitleFunc`, `SeFilLfo1TitleFunc` (low/high/band-pass, band-cut, filter 2, filter envelopes,
filter LFO) — `kn5000-roms-disasm/archive/asl/maincpu/sound_editor_routines.asm`. The KN5000
architecture therefore has a per-tone filter with selectable type, envelope and LFO. INFERRED
corroboration only; it does not by itself prove `+0x100` is that filter.

### 1.9 Independent data check on the semantics (no ear involved)

Using the firmware's own patch **names** as data: for every patch pair `Bright X` / `Mellow X` in the
629-patch table, compute `V` at C4/velocity 100 from the decoded formula.

```
 Accordion    Bright#145 V=111   Mellow#146 V=109   +2
 Piano        Bright#1   V=112   Mellow#2   V= 80   +32
 Solid Gtr    Bright#50  V=104   Mellow#51  V=103   +1
 Trombone     Bright#163 V=115   Mellow#164 V=106   +9
 -> Bright is the higher value in 4 / 4 pairs.
```

And the PIANO sound group reads exactly like a filter spec (`base / velcurve / veldepth / keydepth`):

```
 #0  Piano             100  c2  32  10   V=102     #9  E.Piano 1      104 c3 20   0   V=119
 #1  Bright Piano      103  c3  23  10   V=112     #10 E.Piano 2      101 c5 30 -30   V=120
 #2  Mellow Piano       64  c3  17   0   V= 80     #13 Wurly E.Piano   33 c3  8   5   V= 52
 #5  Rock Piano        103  c2  38  10   V=101     #15 Modern E.P.2     3 c3 10  12   V= 21
 #6  Honky-Tonk Piano  103  c2  22   4   V=113     #18 Clavi          102 c4 40 -10   V=119
```

Mellow Piano is the only piano in the group with **zero key-follow** and the lowest base — a dark,
key-invariant timbre. Wurly and Modern E.P.2 sit near the bottom of the range. This is what the data
says; no listening was involved.

---

## 2. WHAT THE HLE DOES TODAY (`src/mame/matsushita/kn5000_tonegen.cpp`)

* Every per-voice register is stored: `m_voice[ch].regs[reg_idx] = data;` — **cpp:195**.
* `group 0 / bank 0` drives the gate and the per-tick envelope magnitude — **cpp:205-226**.
* `group 0 / bank 2` (= `+0x080`) with bit15 set triggers `resolve_waveform()` — **cpp:255-256**.
* `group 0 / bank 1` (`+0x040`) and `group 4 / bank 0` (`+0x400`) drive pitch — **cpp:261-262**.
* `group 0 / bank 2` and `group 8` drive `update_voice_params()` — **cpp:266-267**.
* `update_voice_params()` — **cpp:462-521** — reads **only** `regs[20] >> 8` (`+0x800`) and turns it
  into `gain = 2^((level − 231)/10)`; pan is hard-centred at **cpp:515-520**.
* The render — **cpp:1393-1584** — reads the PCM (**cpp:1500-1514**), multiplies by `env_level`
  (**cpp:1520**), by the release fade (**cpp:1524-1543**) and by `volume_l/r` (**cpp:1555-1556**).

**There is no filter anywhere in the device.** `regs[3]` (`+0x0C0`), `regs[4]` (`+0x100`),
`regs[5]` (`+0x140`), `regs[6]` (`+0x180`) and `regs[12]` (`+0x500`) are written to the array at
cpp:195 and **never read again** — a grep for `regs[3]`, `regs[4]`, `regs[5]`, `regs[6]`, `regs[12]`
in `kn5000_tonegen.cpp` returns nothing outside that store.

---

## 3. THE DELTA — numbered gaps

### GAP 1 — `+0x100`'s TVF parameter is ignored: there is no filter at all  ★ highest impact

* **What is wrong.** `regs[4] & 0x7F` is the chip's per-voice brightness control, computed by the
  firmware from the patch's base cutoff + velocity curve + key follow (§1.3). The HLE never reads it,
  so every voice is rendered with the raw wave-ROM PCM at full bandwidth.
* **Audible consequence.** MEASURED (`kn5000-variant-diagnosis.md` §3.1): Bright Piano and Mellow
  Piano render **100.00 % bit-identical**, although the chip is told 0x61 vs 0x45 — a 28-unit cutoff
  difference. Every "Bright/Mellow/Soft/Dark" pair collapses; **302 of 585 patches** that are distinct
  in `(V, +0x140)` are indistinguishable today; velocity does not change tone (only loudness), and
  the instrument does not get brighter as you play up the keyboard.
* **Firmware-derived fix.** Add a per-voice low-pass filter in `sound_stream_update`, driven only by
  the register:

  ```c
  // --- in data_w, alongside the existing group-0 handling ---------------------
  if (group == 1 && bank == 0)          // +0x100
      update_timbre(ch);

  // --- new update_timbre(ch) -------------------------------------------------
  // +0x100 = { [15:13] 3-bit field, [10] flag, [7] mode flag, [6:0] CUTOFF }
  // 0..0x78 is the computed range; 0x7F is the firmware's reserved "no TVF" code
  // (LABEL_022DA1, v142 asm L14697), so it must render as a bypass.
  const int cut = v.regs[4] & 0x7F;
  if (cut >= 0x7F) { v.lp_a = 0.0; }                       // bypass
  else {
      // 1 unit == CENTS_PER_UNIT cents of cutoff. CENTS_PER_UNIT = 100 is the
      // value that makes the firmware's key-follow depth 0x20 exactly 100 %
      // key tracking (see below) -- INFERRED, and the ONE calibration constant.
      const double fc = FC_OPEN * std::pow(2.0, (cut - 127.0) * CENTS_PER_UNIT / 1200.0);
      const double x  = std::exp(-2.0 * M_PI * fc / 48000.0);
      v.lp_a = x;                                          // one-pole; cascade 2x for 12 dB
  }

  // --- in sound_stream_update, after the PCM read (cpp:1514) ------------------
  v.lp_z = sample * (1.0 - v.lp_a) + v.lp_z * v.lp_a;
  sample = int32_t(v.lp_z);
  ```

  `FC_OPEN` ≈ 20 kHz (transparent at 48 kHz) so that `cut = 0x7F` is a true bypass.
* **Why "1 unit ≈ 1 semitone" (INFERRED, and the only free constant).** The key-follow term is
  `keydepth·(note − centre)/32`; a cutoff that tracks the keyboard exactly one semitone per key is
  therefore `keydepth = 0x20`, a natural unity point for a signed 7-bit depth. Under that reading
  Piano's `keydepth = 10` is ~31 % key tracking and its `veldepth = 32` gives a ppp→fff brightness
  swing of 63 units ≈ 5¼ octaves — musically sane numbers for a sampled piano. The chip's true
  cents/unit is internal to the undumped LSI, so this constant is *calibrated*, exactly like `K` and
  `REF` in the existing velocity gain (cpp:490-493). **Label it as such in the code.** Everything else
  in the model — which register, which bits, the bypass code, the monotonic direction — is MEASURED.
* **Confidence.** Decode and bit layout: **MEASURED** (9/9 live). "It is a filter/brightness control":
  **INFERRED**, from (a) the reserved wide-open default, (b) velocity- and key-scaling with soft = low,
  (c) the firmware's own Bright/Mellow naming ordering it 4/4, (d) the Sound Editor's filter pages.
  The cents/unit scale: **calibrated constant**, not derived.

### GAP 2 — `+0x140`'s pair is ignored

* **What is wrong.** `regs[5]` carries `{amount[15:8], sign[7], value[6:0]}` (§1.4) and is
  instrument-characteristic (Piano 0x6FDA, Bright/Mellow 0x5BDA, Strings 0x7F58, Brass 0x66D8,
  Bass 0x7F25, Drawbar 0x6631). The HLE ignores it.
* **Audible consequence.** Two instruments that share `+0x040` *and* `+0x100` still render alike —
  e.g. Bright Piano vs Mellow Piano would still be closer than they should be after Gap 1 alone
  (they share `+0x140 = 0x5BDA`, so this gap does *not* separate that particular pair, but it does
  separate Piano from both).
* **Firmware-derived fix.** Only after Gap 1 is in and A/B'd. The decode is exact, the *meaning* is
  not established, so the honest step is a **falsifiable experiment, not an implementation**: drive
  a filter-EG depth from `((regs[5]>>8)&0x7F)` with the sign from bit 7 and compare against real
  hardware on a sound where the two differ strongly (Piano 0x6F vs Bass/Strings 0x7F vs Drawbar 0x66).
  Do **not** ship a guess as if it were decoded.
* **Confidence.** Decode **MEASURED** (18/18); semantics **SPECULATIVE**.

### GAP 3 — the pitch-class field in `+0x080` bits[14:12] is undecoded (and unused)

* **What is wrong.** `+0x080` bits[14:12] = `floor(2·(key mod 12)/3)` (MEASURED 6/6 live), or a
  per-partial constant `rec[+0x02] & 0x70` when `rec[+0x02]` bit 7 is set. Nothing in the HLE uses it,
  and **nothing in the firmware says what it is for**. It repeats per octave, so it is *not* a level
  or a key-scale; it is most likely a chip-internal wave/interpolation/sub-bank selector.
* **Audible consequence.** Unknown. If it is a wave sub-select, some per-note timbre variation is
  currently missing; if it is an interpolation-phase control, nothing is missing.
* **Firmware-derived fix.** None available — this is a genuine "not derivable from the firmware"
  case, so it is reported and not invented. The falsifiable next step is on hardware: play a
  chromatic run on one instrument and look for a timbral discontinuity every 1½ semitones (where this
  field steps); its absence would rule out a wave sub-select.
* **Confidence.** Decode **MEASURED**; meaning **NOT ESTABLISHED**.

### GAP 4 — `+0x0C0`'s level field is ignored, and it fights `+0x800`

* **What is wrong.** `+0x0C0`'s high byte is a 7-bit per-part/per-patch amount (§1.6). Between Piano
  and Bright Piano it moves **+0x1A (Piano higher)** while `+0x800`'s level moves **−9 (Piano lower)**.
  The HLE reads only `+0x800`.
* **Audible consequence.** MEASURED today: Bright Piano renders **1.857× (5.4 dB) louder than plain
  Piano** with otherwise identical audio. If `+0x0C0` is an attenuation, the real instrument
  approximately cancels that difference and the emulator's 5.4 dB is a pure artefact of reading one
  of the two level registers.
* **Firmware-derived fix.** The polarity cannot be settled from the firmware (both registers are just
  numbers shipped to the chip), so **measure it**: on the real KN5000, play Piano and Bright Piano at
  a fixed velocity and compare loudness. If they are within ~1 dB, `+0x0C0` is a compensating
  attenuation and its scale is solvable directly from the two register deltas (0x1A units of `+0x0C0`
  must cancel 9 units of `+0x800`, i.e. ≈ 0.35 `+0x800`-units per `+0x0C0` unit). If Bright really is
  5 dB louder, `+0x0C0` is not a level and must stay unused. **This is the one place where Felipe's
  hardware is the only available oracle** — and it is a 30-second test.
* **Confidence.** Decode **MEASURED** (2/2); role **INFERRED**; polarity **UNRESOLVED**.

### GAP 5 — `+0x180` (expression) is ignored

* **What is wrong.** `+0x180` is a second per-voice level, seeded at note-on (§1.6) and rewritten
  every tick by `LABEL_026EC3` → `LABEL_02D670`. `regs[6]` is stored and never read.
* **Audible consequence.** Sounds whose second envelope domain does the work (the live capture shows
  Piano partial 1 gets `+0x180 = 0x007F` while partial 0 gets `0x0000` — MEASURED this pass) render
  their two layers at the wrong relative level, and expression pedal / part-volume rides are lost.
* **Firmware-derived fix.** After Gaps 1 and 4: fold `regs[6] & 0x7F` in as a linear per-voice
  multiplier normalised at 0x7F. Low priority; it is already listed as item 4 of
  `kn5000-tonegen-register-semantics.md`'s change list.
* **Confidence.** **MEASURED** that it is a level register written twice (note-on + per tick);
  its scale is **INFERRED**.

### GAP 6 — the HLE's `+0x080` bit-15 trigger is a misreading (latent, not currently audible)

* **What is wrong.** `cpp:255-256` calls `resolve_waveform(ch)` on "group 0, bank 2 with bit 15 SET",
  commented as a waveform-pointer latch. Bit 15 of `+0x080` is the **burst load strobe**
  (SET at asm L29594 before the burst, RES at L29907 after it), and `+0x080` itself is the level
  register. The HLE also re-resolves at key-on (cpp:1344), which is what actually keeps it correct.
* **Audible consequence.** None today: `+0x040` is written *before* `+0x080` in the burst (L29573 vs
  L29588), so the early resolve reads a fresh value. It is a mislabelled trigger that will bite
  whenever `+0x080` is written outside a burst (it is — L14220/14234/14272/14284/15694/23012/26725/
  30237 all write `+0x080` alone), each of which currently re-runs the whole waveform resolve.
* **Firmware-derived fix.** Drop the `group==0 && bank==2` resolve trigger, or gate it on
  `(data & 0x8000) && group0/bank0 has not yet gated`. Keep the key-on resolve, which is the correct
  one. Fix the comment: `+0x080` = `{[15] load strobe, [14:12] pitch-class field, [11:0] 256·log2(level)}`.
* **Confidence.** **MEASURED**.

### GAP 7 — the timbre registers are recomputed on paths the HLE does not watch

* **What is wrong.** `ToneGen_WriteVoiceParams` is called from 8 sites (asm L21951, 26850, 27617,
  27964, 28261, 31139, 39157, 39196), not only from the note-on chain; and the emitter adds a live
  `PART[+0x1f]` offset. So `+0x100` can change on a **held** note when a controller moves.
* **Audible consequence.** Once a filter exists (Gap 1), a filter sweep driven from the panel/MIDI
  would be dropped if the HLE only sampled `+0x100` at key-on.
* **Firmware-derived fix.** Recompute the filter coefficient in `data_w` on **every** `+0x100`
  write (as the sketch in Gap 1 does), not inside `process_key_on`. Costs nothing and is correct by
  construction.
* **Confidence.** **MEASURED** (the call sites and the emitter's modulation are in the disasm).

---

## 4. AUDITED AND FOUND CORRECT

* **The register address decode** `addr = (group<<8)|(bank<<6)|channel` and the `group_map[]` folding
  (`cpp:173-191`) — re-verified against every `ADD WA,<off>` in the ROM. **Correct.**
* **`+0x040` is the only wave-selection register.** Re-checked from the timbre side: none of
  `+0x080 +0x0C0 +0x100 +0x140 +0x180 +0x500` carries any address-shaped or zone-shaped value; they
  are all 7-bit amounts, log levels or 3-bit fields. The existing selection model is not undermined
  by anything found here. **Correct.**
* **`+0x100`/`+0x140` are static per note.** The HLE's assumption that a voice's timbre does not need
  per-tick updating is right — the per-segment updater `LABEL_02CD71` (asm L29178) touches only
  `+0x000` and groups 8/9/10. **Correct** (with the caveat of Gap 7 for controller moves).
* **The key-on discrimination** `(data & 0xFF00) == 0x8100` (cpp:212) — the burst writes exactly
  `LDW (100002h),8100h` to group0/bank0 (asm L29757). **Correct.**
* **`regs[20]` polarity (higher = louder).** Independently corroborated from this side: the level
  table at **0x0118FE** runs 255 → 0 as its *input index* rises (dumped this pass), and the index is
  the patch's attenuation byte, so a larger patch attenuation produces a **smaller** register value.
  The current model (`gain = 2^((level−231)/10)`, cpp:495-511) has the right sense. **Correct.**
* **Pan hard-centred** (cpp:515-520). Nothing in the timbre path contradicts this; the pan really is
  baked into the group-8/9/10 L/R pair, which is the envelope dimension's business, not `+0x0C0`.
  **Correct as scoped.**
* **`+0x500` does not carry the Bright/Mellow difference** — measured identical (0x2C68) for all
  three. Ignoring it costs nothing *for this dimension*. **Correct as scoped.**

---

## 5. HONEST RESIDUAL GAPS

1. **The cents-per-unit scale of the TVF parameter is not in the firmware.** It is a property of the
   undumped LSI. The model above is monotone-correct and bounded-correct (0x7F = bypass) without it;
   only the absolute cutoff needs the constant.
2. **The filter TYPE and slope are not decoded.** `+0x100` bits[15:13] (from `VP[+0x4e]`, values
   0/1/2 observed) and bits[12:10] / bit[7] (set by some builders, clear by others) are the only
   plausible carriers, and the Sound Editor's LPF/HPF/BPF/BCF/24 dB pages say such a selector exists.
   Which encoding is which is **not established**. Ship a low-pass first.
3. **`+0x140`'s meaning** (Gap 2) and **`+0x080` bits[14:12]** (Gap 3).
4. **The five builder variants other than `LABEL_023D01`** (`022DA1`, `023DB5`, `023EC2`, `023FBD`,
   `02403D`) and the parallel `VP[+0x0f..0x14]` parameter set used by the `LABEL_024300` family were
   read but not exercised — no stock sound in the 16 SOUND-GROUP defaults or the 20 PIANO variants
   selects them. They differ only in *how* the same two registers are filled, so the register-side
   model in Gap 1 is unaffected.
5. **One unattributed unit** in the `+0x080` level index between Piano and Bright Piano (§1.7).

---

## 6. REPRODUCTION

* Table dumps: `addr − 0xEF00` is the offset into `original_ROMs/kn5000_subprogram_v142.rom`
  (LOGTAB 0x010764, KEYTAB 0x00FBE4, key-scale curves 0x011519 = 7×128 signed,
  `+0x140` tables 0x0119FB / 0x011A25 = 16×3, level table 0x0118FE).
* Patch bytes: `notes/data/kn5000-patch-partials.tsv` gives `region_off` into
  `original_ROMs/kn5000_table_data.rom`; the 0x51-byte partial block starts there, the tone-record
  header is the 0x66 bytes before it (`rec+0x5C` is the `+0x0C0` offset byte).
* Live re-check: `tools/timbre_tap2.lua`, run as
  `./kn7000 kn5000 -rompath ./roms -skip_gameinfo -window -nomaximize -nvram_directory <COPY>
   -autoboot_script timbre_tap2.lua -seconds_to_run 40 -nothrottle` from `kn7000-emulator/`.
  Press notes after t ≈ 20 s; never point `-nvram_directory` at `kn7000-emulator/nvram`.

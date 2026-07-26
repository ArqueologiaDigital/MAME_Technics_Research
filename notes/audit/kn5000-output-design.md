# KN5000 IC303 — OUTPUT-PATH DESIGN: stereo, "effect sends", headroom

Author: autonomous OUTPUT-PATH decode pass, 2026-07-26. Requested by Felipe Sanches.
Closes the three output-path items of the 6-dimension HLE audit: **GAP OUT-1 (stereo pan)**,
**GAP OUT-2 (effect sends)** and the **clipping WATCH** item.

Evidence labels: **MEASURED** (read out of the disassembly / ROM bytes / captured live on the
running machine), **PROVEN-BY-CONSTRUCTION** (follows from a traced code path), **INFERRED**,
**CALIBRATED** (a constant that is a chip internal and therefore *not* derivable — flagged as
such wherever it appears), **SPECULATIVE**.

Sources
* sub-CPU disasm `kn5000-roms-disasm/archive/asl/subcpu/kn5000_subprogram_v142.asm`
  (`LABEL_0xxxxx` **is** the ROM address; line numbers are 1-based in that file).
* Table-Data ROM `kn5000_table_data_rom_even.ic3` + `..._odd.ic1` interleaved exactly as
  `kn5000.cpp:1131-1133` loads them (`ROM_LOAD32_WORD` at +0/+2), i.e. **16-bit** word
  interleave. `table_data` region offset = sub-CPU address − 0x020000.
* HLE `src/mame/matsushita/kn5000_tonegen.{cpp,h}`.
* Prior audit notes in this directory (`kn5000-audit-output.md`, `-registers.md`,
  `-voicelife.md`) and `notes/kn5000-firmware-sample-tables.md`.
* **NEW live captures this pass** (§5): `panprobe.lua` (RAM + register dump on a held C4),
  `panprobe2.lua` (causal poke-then-play), `concur.lua` (voice concurrency + WAV of a dense
  accompaniment passage).

---

## 0. TL;DR — the three answers

1. **STEREO IS REAL, PER-VOICE, AND IT IS NOT WHERE THE BRIEF SAID.**
   Pan is **register `+0x180` (`regs[6]`), bits [6:0]** — `0x00` … `0x40` (centre) … `0x7F`.
   Traced end to end from **MIDI CC 0x0A (Pan)** through `Voice_CC_Pan` →
   `LABEL_0288C5` → `LABEL_032E1E` → the per-tone-slot byte → the `+0x180` write, and
   **proved causally live**: poking that byte before a note-on changed `+0x180` to exactly the
   poked value (predicted `002A`/`0055`, measured `002A`/`0055`).
   The patch-side source is `partial_block[+0x01]`: **692 / 1046 partials are exactly `0x40`,
   the exact centre; 194 / 216 two-partial patches are mirror-pairs summing to 0x7F/0x80;
   252 / 258 single-partial patches are dead centre; the field never exceeds 0x7F.**
2. **`+0x840` / `+0x880` ARE NOT BUS L/R GAINS.** The premise is falsified by a measurement the
   earlier passes did not have: **the Piano's two oscillators are panned to opposite extremes
   (`+0x180` = `0x0000` and `0x007F`) yet carry byte-identical `+0x840 = 484C`, `+0x880 = 4000`,
   `+0x8C0 = 00B0`.** Registers that carry no stereo difference between a hard-left and a
   hard-right voice cannot be left and right gains. They are envelope segments 1 and 2 of the
   amplitude EG — which also explains **both** the equal and the unequal cases (§1.6).
3. **THERE ARE NO PER-VOICE EFFECT SENDS.** `+0x8C0`, `+0x900…+0x9C0`, `+0xA00/+0xA40` are
   EG stage words. The effects hardware is on a **different bus** (DSP1/DSP2 at
   `0x130000/0x130002`), and **no IC303 register value anywhere in the ROM is derived from the
   per-part effect-depth bytes**. Ignoring them *as sends* is correct; ignoring them *as
   envelope registers* is GAP CAL-1's problem, not this one.
4. **HEADROOM: the mix really does clip today, MEASURED.** In a dense accompaniment passage the
   pre-limiter voice sum reaches **2.80 × full scale (+8.96 dB)** and the limiter is driven to
   its asymptote (48 samples at ±32767). But **only 0.564 % of samples exceed full scale**, so
   the cure is a proper limiter with a true unity pass-through, **not** the present
   unconditional ×0.70 trim that costs 3.1 dB on the other 99.4 %.

---

## 1. (a) STEREO — the pan path, decoded end to end

### 1.1 The register — MEASURED

**`+0x180` (group 1, bank 2 = `regs[6]`), bits [6:0] = PAN.**
`0x00` … `0x40` = centre … `0x7F`. Bit 7 is 0 in every capture; bits [15:8] carry an unrelated
streamed-voice field (§1.7).

Every write of that register in the whole ROM comes from one scratch word, `0x0451D8`
(`ToneGen_WriteVoiceParams` asm L29649), or from `LABEL_02D670` (asm L30169-30178, the only
routine whose body is `ADD WA,0180h ; LD (100000h),WA ; LD (100002h),IZ`). There are exactly
**three** writers of `0x0451D8` in the ROM:

| asm line | writes | meaning |
|---|---|---|
| L17700 (`LABEL_0249BF` tail) | `desc[+0x2b]` | note-on, variant A |
| L18466 (`LABEL_0251BA` tail) | `desc[+0x2b]` | note-on, variant B (the one live traffic uses) |
| L21912 (`LABEL_0272A3`) | **constant `0x0040`** | the reset/default value = **the exact centre** |

A 7-bit field whose firmware default is the exact centre of its range is a bipolar control. That
was already the audit's reading (`kn5000-audit-registers.md` GAP 6, "pan is the leading reading,
INFERRED"). What follows upgrades it to **MEASURED**.

### 1.2 The firmware chain: MIDI CC 0x0A → `+0x180` — MEASURED

```
Voice_CtrlChange        asm L25008 ; CP A,00Ah / JR Z,Voice_CC_Pan   (L25036-25037)
  Voice_CC_Pan          asm L25081
    ├─ LABEL_0288C5     asm L23469 ; chan[0x041376 + ch*0x11F] <- CC value     (store)
    └─ LABEL_032E1E     asm L35522 ; APPLY
```

`LABEL_032E1E(ch)` (asm L35522-35608), decoded verbatim:

```
chan_base = 0x041368 + ch*0x11F
cc        = (int8)(chan_base[+0x0E]) - 0x40          ; 0x041376 = chan_base+0x0E
for slot i in 0..3:
    p = LABEL_032D58(ch, i)                          ; = *(u8*)(subrec_i[0..3] + 1)  = PATCH PAN
    if p != 0x0080:                                  ; 0x80 = "CC-10 does not apply" sentinel
        p = clamp(p + cc, 0, 0x7F)                   ; LABEL_032D44, asm L35430
    subrec_i[+0x23] = (u8)p                          ; asm L35588
    subrec_i[+0x24] = (u8)p                          ; asm L35602
where subrec_i = chan_base + 0x6E + i*0x25
```

`LABEL_032D58` (asm L35445-35521) is a 4-way selector over the four per-part **tone slots**
`0x0413D6 / 0x0413FB / 0x041420 / 0x041445` (stride 0x25, base = `chan_base + 0x6E`), each of
which begins with a **32-bit pointer to the patch's partial block**; it returns
`partial_block[+0x01]`. Slots 0 and 1 are swappable through bits 14/15 of `chan_base[+0x02]`.

Those same sub-records are what the voice descriptor points at:

```
asm L26947  desc[+0x23] = chan_base                                     (the part block)
asm L26961  desc[+0x27] = chan_base + 0x6E + slot*0x25                  (the tone slot)
```

and the two consumers close the loop onto the chip register:

```
note-on   LABEL_0251BA  asm L18427-18466
            chan[+0x26]==1 -> desc[+0x2b] = base            ; hard one end
            chan[+0x26]==2 -> desc[+0x2b] = base | 0x7F     ; hard other end
            else           -> desc[+0x2b] = base | subrec[+0x23]      (asm L18456)
            0x0451D8 = desc[+0x2b]                                     (asm L18466)

per tick  LABEL_026F4A  asm L21561-21578
            desc[+0x2b] = (desc[+0x2b] & 0xFF80) | desc[+0x27][+0x24]  (asm L21568-21575)
            LABEL_02D670(ch, that)  ->  register +0x180                (asm L21577)
```

`chan[+0x26]` (= `0x04138E + ch*0x11F`) is set **only** by proprietary **CC 0x9D**
(`LABEL_028ACB`, asm L23662) and is reset to 0 for all 26 channels at init (asm L25793-25795).
MEASURED live: it is `0x00` on the running machine, so the two "force to the end" branches are
not what live traffic takes. (This also **corrects** `kn5000-docs/sound-parameter-protocol.md`,
which names CC 0x9D `Voice_CC_SetDelayFeedback`; the offset +0x8E is right, the name is wrong —
it is the `+0x180` hard-pan override.)

### 1.3 The patch-side source — MEASURED over the whole ROM

`partial_block[+0x01]` — the byte `notes/kn5000-firmware-sample-tables.md` §2.2 lists as
"partial flags `{00,18,40,58,7f,…}`" — **is the patch's own pan.** Over all **1046** partial
blocks of the 629-patch table (alignment self-verified: `partial_block[+0x02]` reproduces the
TSV's `fine` **1046/1046** and `[+0x03]` reproduces `set` **1046/1046**):

| statistic | value |
|---|---|
| range | strictly **0 … 127**, never above 0x7F |
| exactly `0x40` (centre) | **692 / 1046 = 66.2 %** |
| `0x00` / `0x7F` (the two extremes) | 49 / 50 — **balanced** |
| values with a mirror partner `128 − v` | **992 / 1046 = 94.8 %** |
| single-partial patches that are centred | **252 / 258** (the other 6 are all drum kits, at `0x20`) |
| two-partial patches that are a mirror pair | **194 / 216 = 89.8 %** |
| patches with at least one off-centre partial | 173 / 585 |

The instrument names make it unmistakable — these are stereo layouts, not a coincidence:

```
Piano / Bright Piano / Mellow Piano   00  7F
Chapel Organ                          00  7F  40
Cathedral Organ                       18  68  40          (0x18+0x68 = 0x80)
Chamber Orch                          0E  72  18  68      (two nested mirror pairs)
Unison Strings                        0E  22  5E  72      (four layers spread across the field)
Orchestra Pizz                        22  59  5E  27      ((34,94) and (39,89))
Seashore                              00  7F  7C  08
```

The competing reading — a symmetric **detune** — is excluded three ways: the coarse/fine
transpose fields are separately located at `partial_block[+0x04]/[+0x05]` and are what the
pitch model already uses (`notes/kn5000-firmware-sample-tables.md` §5, live-verified 14/15);
a detuned drum kit (`0x20`) is meaningless while an off-centre one is not; and above all
**MIDI CC 10 is *added* to this field**, which no detune parameter would be.

### 1.4 Live proof — MEASURED, this pass

**Probe 1 (`panprobe.lua`, default sound = Piano, held C4).** Dumped the two voice descriptors
and the part block from sub-CPU RAM while the note sounded:

```
VOICE 0 desc=04308E  ch=00  +17=05253A  +27=0413D6  +2b=0000
VOICE 1 desc=0430D5  ch=00  +17=05258B  +27=0413FB  +2b=007F
  chan_base=041368  panCC[+0E]=40  mode[+26]=00
   slot0 sr=0413D6 ptr=05253A ptr[+1]=00  [+23]=00 [+24]=00
   slot1 sr=0413FB ptr=05258B ptr[+1]=7F  [+23]=7F [+24]=7F
register stream:  0180 0000    0181 007F
```

* `desc[+0x17]` = `0x05253A` / `0x05258B` are **exactly** the Piano's two partial blocks
  (`notes/data/kn5000-patch-partials.tsv` region offsets `3253A` / `3258B`, +0x20000).
* `ptr[+1]` = `0x00` / `0x7F` = the ROM's pan bytes; the propagated `[+0x23]/[+0x24]` match;
  `desc[+0x2b]` matches; the chip register matches. **Five-way agreement.**
* **Both oscillators are on the same channel (`ch=00`)**, so `chan[+0x26]` is identical for
  them — PROVEN-BY-CONSTRUCTION that the differing `+0x180` values *cannot* come from the
  hard-pan override and must come from the per-partial pan byte.
* `panCC[+0E] = 0x40` — CC-10 at its centre default, so `patch_pan + 0` = `patch_pan`. ✓

**Probe 2 (`panprobe2.lua`) — the causal test. PREDICT-THEN-CHECK: EXACT HIT.**
Poked `subrec0[+0x23/+0x24] ← 0x2A` and `subrec1[+0x23/+0x24] ← 0x55` **before** the note-on;
predicted the chip would then be told `+0x0180 = 0x002A` and `+0x0181 = 0x0055`:

```
22.307762 0180 002A          <- predicted 002A
22.308229 0181 0055          <- predicted 0055
(+0x040 wave, +0x800 EG, gate: bit-identical to the un-poked run)
```

Nothing else moved. This is a direct causal proof that the byte MIDI Pan writes is the byte the
chip receives in `+0x180`.

### 1.5 So: per-voice, per-part, or a bus matrix? — **per-VOICE, sourced per-PARTIAL, offset per-PART**

* The **register** is per-voice: the address is `group | bank | channel[5:0]`, one `+0x180` per
  hardware voice. IC303 therefore does the panning itself, per voice.
* The **value** is per-partial: each of a patch's 1-4 partials carries its own pan in
  `partial_block[+0x01]`, which is why a patch can have a *stereo layout* (Unison Strings'
  four layers at 0x0E/0x22/0x5E/0x72).
* The **part's** pan (UI slider `LswPan`, displayed `"CTR"`/`"L%2d"`/`"R%2d"`, and MIDI CC 10)
  is an **offset added to every partial of that part**: `clamp(patch_pan + CC10 − 0x40, 0, 0x7F)`.
  Moving a part's pan slides its whole layer image across the field and *compresses* it against
  the end stops (because of the clamp) — not a matrix, not a master.
* There is **no bus matrix** anywhere: no register in the per-voice set is a bus selector, and
  the 13 global registers are written once at boot and never again (MEASURED,
  `kn5000-audit-output.md` §1.5).

### 1.6 Why `+0x840`/`+0x880` are NOT the L/R gains — and what explains BOTH the equal and the unequal cases

The brief's premise ("their seg1/seg2 levels were measured equal 70/70, e.g. 8A04/8A00,
7404/7400, 6404/6400") is real data — but it is EG data, and the model that explains it is
`{ level : high byte, rate : low byte }`:

* **Why the HIGH bytes are equal** in those rhythm note-ons: it is one EG programmed
  "*decay to X, then hold at X*". Segment 1 = `(X<<8) | rate 0x04` (ramp), segment 2 =
  `(X<<8) | rate 0x00` (**hold** — the rate-0 = hold semantics is proven by the `0xAE00`
  unused-stage sentinel, `kn5000-pipe-registers.md` §4b). Equal levels + different rates is
  exactly a sustain plateau. An L/R gain pair has no reason for its low bytes to differ by a
  constant 4 in 103 of 197 note-ons.
* **Why the HIGH bytes are sometimes unequal**: the Piano's are **not** equal —
  `+0x840 = 484C` (level 72) vs `+0x880 = 4000` (level 64). Under the EG reading that is
  D → S, a 8-unit sustain drop. Under the L/R reading it would mean oscillator 0 is panned
  slightly left.
* **The decisive test**: the Piano's oscillator 0 is at pan `0x00` and oscillator 1 at pan
  `0x7F` — **opposite extremes** — and their group-8 registers are **byte-identical**
  (`notes/audit/data/kn5000-outcap-2s.txt`):

```
voice 0  (+0x180 = 0000)   0840 484C   0880 4000   08C0 00B0
voice 1  (+0x181 = 007F)   0841 484C   0881 4000   08C1 00B0
```

  Two voices that the firmware has just panned hard-left and hard-right carry **identical**
  `+0x840`/`+0x880`. They therefore carry **no stereo information at all**. QED.
* Structural corroboration: the per-segment updater `LABEL_027FD6` (asm L23045-23100, verified
  instruction by instruction this pass) rewrites six registers from six *consecutive* struct
  words — `+0x840←[+0x2e] +0x940←[+0x32] +0xA00←[+0x36] +0x800←[+0x2c] +0x900←[+0x30]
  +0x9C0←[+0x34]` — i.e. three `(seg0, seg1)` pairs. Under "L/R" that would be three stereo
  buses per voice fed from one 12-byte block, leaving `+0x880/+0x980/+0xA40/+0x8C0` homeless;
  under "3 EG domains × 4 segments" all ten registers are accounted for.

**Consequence for the docs:** `kn5000-docs/tone-generator.md:107-108, 135-136, 481-482`
("Pan Left / Pan Right, 0x00=silent, 0x3C=center, 0x78=full") is **FALSIFIED** — the measured
values reach `0xFF`, the low byte is a rate, and hard-panned voices share them. So is the
derived claim in `notes/tg-voice-register-semantics.md:107` ("KN5000 analog: grp0x08 bank1/2,
0=silent/0x3C=center/0x78=full"), which propagated the error to the KN7000 investigation.
`notes/kn5000-tonegen-register-semantics.md` §Q6 item 5 was already flagged as falsified by
`kn5000-audit-output.md` §4.1; this note supplies the *correct* register.

### 1.7 THE STEREO RENDER RULE

```c
// ---- kn5000_tonegen_device::update_voice_params(), replacing the hard-centre pan ----
//
// +0x180 (regs[6]) bits[6:0] = PAN.  MEASURED end to end: MIDI CC 0x0A (Pan) ->
// Voice_CC_Pan (asm L25081) -> LABEL_032E1E (L35522) -> tone-slot byte [+0x23]/[+0x24]
// -> LABEL_0251BA (L18456) / LABEL_026F4A (L21568) -> this register.  Patch source =
// partial_block[+0x01]; firmware default = 0x40 (asm L21912).
int pan = v.regs[6] & 0x7F;                 // bits[15:7]: streamed-voice field, not pan

// Balance law, normalised so that CENTRE keeps today's amplitude.
//   pan  0x00 -> L = 1.0, R = 0.0
//   pan  0x40 -> L = 1.0, R = 1.0        (692/1046 partials live here)
//   pan  0x7F -> L = 0.0, R = 1.0
double gl = (pan <= 0x40) ? 1.0 : double(0x7F - pan) / double(0x7F - 0x40);
double gr = (pan >= 0x40) ? 1.0 : double(pan)        / double(0x40);

v.volume_l = int16_t(std::lround(gain * gl * 32767.0));
v.volume_r = int16_t(std::lround(gain * gr * 32767.0));
```

and, **required**, the reset value (this is a hazard, not a nicety):

```c
// The firmware's own default for this register is 0x0040 = CENTRE (LABEL_0272A3, asm L21912).
// regs[] must be initialised to that, or a voice whose +0x180 is never written renders
// HARD LEFT (pan 0x00) instead of centred.
m_voice[ch].regs[6] = 0x0040;      // in device_reset() and wherever a voice is (re)initialised
```

**What is MEASURED in this rule and what is CALIBRATED:**

| element | status |
|---|---|
| the register and bit field (`regs[6] & 0x7F`) | **MEASURED** (§1.2, §1.4) |
| `0x40` = centre; `0x00`/`0x7F` = the two extremes | **MEASURED** (firmware default + ROM distribution) |
| that pan is per-voice and applied inside IC303 | **PROVEN-BY-CONSTRUCTION** (it is a per-voice chip register) |
| which end is **LEFT** | **INFERRED (strong)** — the firmware adds `CC10 − 0x40` with no inversion, and MIDI CC 10 is 0 = left by definition, so a GM-conformant module must map 0 → left. Not provable from firmware; the chip is undumped. **Felipe's ear is the arbiter: play the default Piano — its two layers are hard-panned, so one side is layer 0 (set 01) and the other layer 1 (set 05).** If it is backwards, invert `pan → 0x7F − pan`, one line. |
| the **taper between the anchor points** (linear balance) | **CALIBRATED.** IC303's pan-attenuator table is a chip internal and is not in the firmware. |

**Why the balance law and not constant-power** — this is a derivation from the measured data,
not a preference:
* **Constraint A (MEASURED):** 66.2 % of all partials sit at exactly `0x40`. Any law must leave
  those at today's amplitude, or two thirds of the instrument changes level on no evidence.
  ⇒ `gL(0x40) = gR(0x40) = 1.0`.
* **Constraint B (MEASURED, the clipping WATCH item):** no law may *raise* a per-channel peak,
  because the mix already reaches +8.96 dB over full scale in dense passages (§3).
  ⇒ `max(gL) = max(gR) = 1.0`.
* Constant-power normalised to centre gives `gL(0) = √2` — violates B (+3 dB).
  Constant-power normalised to the extremes gives `g(centre) = 0.707` — violates A (−3 dB).
  **The balance law is the only standard pan law that satisfies both.** Its remaining freedom
  (the shape between the anchors) is the CALIBRATED part, and linear is the cheapest thing a
  1990s attenuator table does; if hardware A/B says the centre is 3 dB hot, swapping in
  constant-power is a two-line change with the same anchors.
* Note the *musical* consequence, which is correct and not a defect: a hard-panned dual-layer
  patch puts one layer in each channel, so each channel gets ~half the correlated amplitude a
  centred version would. That is what panning does; it can only lower peaks.

**Sequencing (MEASURED):** `+0x180` is written **before** the key-on gate in the note-on burst
(`22.307762 0180 0000` vs `22.307783 0000 8100`), so the pan is valid from the first rendered
sample. It can also be rewritten mid-note by `LABEL_026F4A`, so read it live rather than
latching it once.

---

## 2. (b) EFFECT SENDS — VERDICT: **there are none; ignoring them is correct**

`+0x8C0`, `+0x900 … +0x9C0`, `+0xA00`, `+0xA40` are **envelope-generator stage words**, not
sends. Independently re-verified this pass:

1. **Construction.** The `+0x8C0` builder (asm L17645-17660) is literally
   `rate = curve(TONE[+0x3d] + TONE[+0x3e]) ; level<<8 ; OR ; LD (0451EAh),WA` —
   `(level << 8) | rate`, the same shape as every other group-8/9/10 word.
2. **Grouping.** `LABEL_027FD6` (asm L23045-23100) rewrites exactly six of them, as three
   `(seg0, seg1)` pairs from consecutive struct words `[+0x2c … +0x37]` (§1.6). A send would
   not be paired with another send by a shared struct stride.
3. **The unused-stage sentinel.** STRINGS and FLUTE leave *six* of the ten at `0xAE00`
   (`kn5000-pipe-registers.md` §4b) — level 174, rate 0 = "no movement". As a send, `0xAE`
   would be a large constant send on an unused stage; as an EG stage it is the idle fill.
4. **They carry no routing information.** Two oscillators panned to opposite extremes have
   byte-identical `+0x8C0` (§1.6).

**Where the effects actually live.** The KN5000's effects are in **IC311 (DSP1) and IC310
(DSP2)**, programmed over a completely disjoint interface: `0x130000/0x130002`, 4 channels ×
0x20 registers (`DSP_Write_Channel`, asm L9687-9702), plus the DSP1 host-port path. Not one
byte of that traffic goes through `0x100000/0x100002`.

**The per-part effect depths never reach IC303 — MEASURED.** Their storage is per-channel:

| CC | setter | byte |
|---|---|---|
| 0x91 Reverb depth | `LABEL_028A44` asm L23609 | `0x04137F + ch*0x11F` |
| 0x97 Chorus depth | `LABEL_028A7F` asm L23632 | `0x041380 + ch*0x11F` |
| 0x9B Delay depth | `LABEL_028A90` asm L23639 | `0x04138D + ch*0x11F` |
| 0x9D **(pan override, not "delay feedback")** | `LABEL_028ACB` asm L23662 | `0x04138E + ch*0x11F` |

The reverb-depth byte's only readers are inside `LABEL_0233F8` (asm L15318-15600, an effect
parameter routine). **That whole function contains no access to `0x100000`, `0x100002`, or the
`0x0451CC` chip-image scratch** (checked exhaustively). And the converse holds: all **121**
writers of the chip-image scratch `0x0451CC…0x0451F7` in the entire ROM lie in the note-on /
EG-builder blocks (asm L14302-21925) plus two isolated sites (L31524, L38081) — **none of them
is in the effect-depth code path.**

**Therefore:** on the KN5000 there is no per-voice wet/dry send to model, so the HLE's silence
on `+0x8C0/+0x900…/+0xA00/+0xA40` *as sends* is correct and no placeholder should be written.
**But do not read that as "these registers can stay ignored":** they are the amplitude / pitch /
filter envelopes, and leaving them unread is why every KN5000 note in MAME is flat-topped. That
is GAP CAL-1's job, not this one, and it is the single largest remaining output-path defect.

*(Honest limit: what IC303's audio bus physically is between the chip and the DSPs — one stereo
pair or more — is not established here. The service-manual page names `BCK`, `SDOR`, `SDOF`,
which is not enough to decide, and I did not read the schematic. The firmware argument above is
independent of that: whatever the bus is, the sub-CPU never programs a per-voice send onto it.)*

---

## 3. (c) HEADROOM

### 3.1 What the hardware path actually is — MEASURED / INFERRED

```
IC304-307 wave ROMs -> IC303 TC183C230002 (64 voices)
                          -> IC311 DS3613GF (DSP1) + IC310 MN19413 (DSP2)
                          -> IC313 PCM69AU, 18-bit STEREO DAC, one serial bus
                          -> IC312/IC314 M5218AFP op-amps -> FAJ board -> power amp
```

* **64 voices, hard bound.** The register address' channel field is 6 bits, and the firmware's
  hardware-voice pool is 64 × 0x47 bytes at `0x04308E` (asm L22632-22633 etc.).
* **All voices sum into ONE stereo pair before the DAC** — there is one DAC and no
  sample-rate/format converter on the path.
* **There is NO digital master volume.** The 13 global registers are written exactly once at
  boot and never again (MEASURED live, `kn5000-audit-output.md` §1.5), and the KN5000's
  `MAIN VOLUME` is documented as **analog** (`kn5000-docs/hardware-architecture.md:83`) — i.e.
  downstream of the DAC. **The digital domain therefore has a fixed full scale that the
  firmware and chip must live inside.** That is the whole reason a headroom rule is needed at
  all, and it is why the rule must not be a global attenuation: attenuating digitally would
  give away signal-to-noise that the analog volume control cannot give back.
* **What IC303 does internally when its 64-voice sum overflows is NOT derivable.** The chip is
  undumped and the firmware never computes with a mix scale. Say so; do not invent one.

### 3.2 What the emulation does today — MEASURED, this pass

Dense passage: accompaniment started, LH chord C2-E2-G2, RH C4-E4-G4-C5-E5-G5, 25 s, WAV
captured (`concur.wav`, 47 s, 3ch/48 kHz, audio on ch1/ch2).

| measurement | value |
|---|---|
| output peak | **32767 on both channels; 48 samples pinned at full scale** |
| loudest 1-s RMS | 13402 (−7.8 dBFS) |
| **pre-limiter voice sum, peak** (recovered by inverting the softclip analytically) | **2.804 × full scale = +8.96 dB** |
| samples whose pre-limiter sum exceeds full scale | **12 718 / 2 256 001 = 0.564 %** |
| non-silent samples below 0.75 × FS | **95.6 %** |
| samples the present limiter actually compresses (knee at `acc` = 1.0714) | **0.401 %** |
| ch1 vs ch2 | **identical** — confirming pan is hard-centred today |

So the limiter is being driven ~9 dB into its tanh region and reaching its asymptote. It never
wraps (the softclip is bounded to (−1,1)), so this is soft saturation, not hard clipping — but
9 dB of gain reduction on peaks is audible pumping.

The present code (`kn5000_tonegen.cpp:1723-1732`) is also self-contradictory, as
`kn5000-audit-output.md` GAP 7 recorded: `x = HEADROOM * acc / 32768` with `HEADROOM = 0.70`
applies to **every** sample, so the advertised "passes through unchanged below the knee" never
happens and the whole instrument is 3.1 dB down.

**Important caveat, stated up front:** these peaks are inflated by **GAP LIFE-1**. The
concurrency probe shows the gated-voice count ramping 0 → 64 and then **staying at 64** — the
firmware never frees a voice because `status_r` never reports silence, so the render sums up to
64 permanently-gated voices where the hardware would have a handful. **The headroom rule must
therefore be re-measured after LIFE-1 lands; anything calibrated against today's numbers is
calibrated against a bug.** That coupling is the single most important thing in this section.

### 3.3 THE HEADROOM RECOMMENDATION

**Principle: the headroom belongs upstream, in the level law — not in a global trim.** The
firmware's own declared per-voice ceiling is `0xFF` (`LABEL_026FDD` clamps to `0xFF00`/`0xFF80`;
`LABEL_023328` clamps every level to `[0, 0xFF]`), while a real patch at a normal velocity
programs `0xE5` = 229 (MEASURED, Piano at the driver's velocity 100). **Real notes sit below
the firmware's own maximum by construction**; that gap *is* the hardware's per-voice margin,
and it only exists in the render if `REF` is the firmware's ceiling 255 rather than the
observed 231 (GAP 4). Setting `REF = 231` and clamping to 1.0, as today, throws that margin
away by pinning every level ≥ 231 to full scale.

Concretely, in order:

1. **`REF = 255.0`** (the firmware's declared maximum) instead of 231, with the gain clamp kept.
   Firmware-derived, and it restores ~10 % of per-voice margin that is currently clipped flat.
   Must be re-fitted *together with* GAP CAL-1's dB/step, never before.
2. **Make the pass-through a real pass-through**: drop the unconditional `HEADROOM` factor
   (`x = float(acc) / 32768.0f`). MEASURED justification: 95.6 % of the non-silent
   dense-passage samples are already below 0.75 × FS and only 0.564 % exceed full scale, so the
   ×0.70 trim is costing 3.1 dB on essentially the entire programme to protect half a percent
   of it.
3. **Keep the soft knee, raise it**: `K = 0.85`, tanh above. Bounded to (−1,1), no wrap, no hard
   corner; a single note and a small chord are then bit-for-bit unattenuated. The knee value is
   **CALIBRATED** — IC303's own saturation point is undumped — but it is *bounded* by the
   measurements: it must be ≥ the level a single full-scale voice reaches (so single notes stay
   linear) and low enough that the 0.56 % of over-scale samples are compressed rather than
   wrapped.
4. **Do NOT divide by the voice count, and do NOT auto-gain.** No hardware mechanism for it
   exists (no global level register is ever written, §3.1), and it would make a single note
   change loudness depending on what else is sounding — the opposite of faithful.
5. **Pan must not add peak.** The §1.7 balance law has `max(gL) = max(gR) = 1.0`, so
   implementing stereo can only *reduce* per-channel peaks. Do not adopt a constant-power law
   normalised to centre; it would add 3 dB to hard-panned voices and make this worse.
6. **Re-measure after GAP CAL-1 and GAP LIFE-1.** With the EG running, a held note spends most
   of its life at its sustain level (Piano: 64/255) rather than at its attack peak (229/255),
   so the *sustained* sum in a dense passage falls dramatically — the flat-topped render is
   itself a large part of today's +9 dB. With LIFE-1 fixed, the voice count falls from a stuck
   64 to whatever is really sounding. **Both changes reduce the peak; neither has landed. The
   correct order is CAL-1 → LIFE-1 → re-measure → then set K.**

Expected effect of (2)+(3) alone, MEASURED against the captured passage: the instrument gets
3.1 dB louder overall, single notes and small chords become exactly linear (they are not today),
and the fraction of samples the limiter touches goes from **0.401 %** (today's effective knee at
`acc` = 1.0714) to **1.276 %** (`K` = 0.85, no trim) — i.e. ~0.9 % more material enters gentle
compression, and in exchange nothing at all is attenuated that is not near the rail. That trade
is the right one: it stops paying a constant 3.1 dB tax on 100 % of the programme to protect
0.56 % of it. (Same caveat as above: both figures come from a capture that includes the LIFE-1
stuck voices, so they are an upper bound on the real density.)

---

## 4. Corrections this pass makes to existing notes/docs

| where | claim | status |
|---|---|---|
| `kn5000-docs/tone-generator.md:107-108,135-136,481-482` | `+0x840`/`+0x880` = "Pan Left/Right, 0=silent, 0x3C=center, 0x78=full" | **FALSIFIED** (§1.6). They are EG segments 1 and 2. |
| `notes/tg-voice-register-semantics.md:107,123,151` | "KN5000 analog: grp0x08 bank1/2, 0=silent/0x3C=center/0x78=full" | **FALSIFIED**; the KN7000 pan hunt should not use it as a template. |
| `kn5000-audit-output.md` §0.1 / §4.1 | "There is no per-voice PAN in the IC303 register stream … hard-centre pan is CORRECT" | **CORRECTED**: no pan in *group 8/9/10*, right — but pan exists, in `+0x180`. Hard-centre is a defect, not a correct model. |
| `kn5000-audit-registers.md` GAP 6 | `+0x180` = "7-bit centred parameter, pan is the leading reading, INFERRED" | **UPGRADED to MEASURED** (§1.2-§1.4), with the source byte and the CC-10 path identified. |
| `notes/kn5000-firmware-sample-tables.md` §2.2 | `partial_block[+0x01]` = "partial flags {00,18,40,58,7f,…}" | **DECODED**: it is the patch's PAN (§1.3). |
| `kn5000-docs/sound-parameter-protocol.md:140` | CC 0x9D = `Voice_CC_SetDelayFeedback` @ +0x8E | offset right, **name wrong**: it is the `+0x180` hard-pan override (0 = use pan, 1/2 = force the ends). |
| `kn5000-docs/audio-subsystem.md:1068` | "Pan … written to channel offset +0x08 … via `EnvTranspose_UpdateLoop`" | **WRONG**: CC 10 is stored at chan `+0x76` (`0x041376`) and applied by `LABEL_032E1E`. |
| `kn5000-tonegen.cpp:560-568` pan comment | "There is no evidence-based per-voice pan source yet" | **SUPERSEDED** — there is one, and this note is it. |

---

## 5. Reproducing every measurement

```bash
SP=<scratchpad>
cp -r $SP/nvram2 $SP/nvpan          # isolated PRE-INIT nvram (PMEM play screen, RIGHT1=Piano)
cd ~/compartilhado/kn7000-emulator

# 1. RAM+register dump on a held C4  (§1.4 probe 1)
PP_OUT=$SP/panprobe.txt PP_T0=22 timeout 300 ./kn7000 kn5000 -rompath roms \
  -window -nomaximize -skip_gameinfo -nvram_directory $SP/nvpan \
  -autoboot_script $SP/panprobe.lua -autoboot_delay 0 -sound none

# 2. CAUSAL poke-then-play  (§1.4 probe 2)
PP_OUT=$SP/panprobe2.txt PP_T0=22 timeout 300 ./kn7000 kn5000 ... \
  -autoboot_script $SP/panprobe2.lua ...

# 3. voice concurrency + dense-passage WAV  (§3.2)
CC_OUT=$SP/concur.txt CC_T0=22 timeout 420 ./kn7000 kn5000 ... \
  -autoboot_script $SP/concur.lua ... -wavwrite $SP/concur.wav
```

Scripts and outputs are committed under `notes/audit/data-output/`.
The Lua tap handle **must** be kept in a global or Lua GC silently disables it.

ROM-side statistics (§1.3) — stdlib Python, interleave the Table-Data ROM in **16-bit** words
(`ROM_LOAD32_WORD` at +0/+2), then read `partial_block[+0x01]` at
`region_off` from `notes/data/kn5000-patch-partials.tsv`; the alignment self-checks against the
TSV's `fine` (`[+0x02]`) and `set` (`[+0x03]`) columns, 1046/1046 each.
Regenerate with `tools/kn5000_pan_stats.py`.

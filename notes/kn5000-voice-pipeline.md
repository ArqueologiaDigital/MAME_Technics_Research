# KN5000 voice pipeline — how per-instrument waveform selection is encoded in the IC303 register writes

Author: autonomous deep-RE + live-capture pass, 2026-07-23. Requested by Felipe Sanches.
**Investigation only.** No `src/` edits, no rebuild. All MAME instrumentation was runtime-only
(lua write/read *taps* + RAM reads in an isolated scratchpad rundir with a **copy** of the
pre-init nvram); `kn7000-emulator/nvram` was never touched and the repo is unchanged apart from
this note.

Resolves the "+0x440 wave-number is 0 yet instruments sound different" paradox by tracing the
whole pipeline and validating it live. **Supersedes / reconciles** the contradictory earlier
notes:
* `kn5000-tone-record.md` (correct that +0x440=0 is genuine, but its §4 "identity lives only in
  the timbre/pitch registers, the delivery carries no wave selection" is imprecise — the
  identity is carried, concretely, by register **+0x040**);
* `kn5000-real-sample-select.md` §1 (the "24-bit START/LOOP **sample-ROM addresses** in the
  oscillator records select the instrument") — **this class of claim is REJECTED here**: those
  24-bit values are sub-CPU RAM pointers (0x02xxxx / 0x05xxxx / 0x07xxxx all lie inside the
  sub-CPU's own 0x000000–0x0FFFFF DRAM, **not** the waveform ROM) and, decisively, they **never
  reach IC303** — the chip is driven ONLY through 0x100000/0x100002 and I captured the entire
  note-on write stream (below): no 24-bit address is ever latched. This is exactly the
  "the 24-bit values are sample addresses" false pattern the task warned about.

Evidence labels: **MEASURED** (read from the RUNNING machine / ROM bytes / disasm),
**PROVEN-BY-CONSTRUCTION** (follows directly from a traced code path), **INFERRED**, **SPECULATIVE**.

Sources:
* sub-CPU disasm `kn5000-roms-disasm/archive/asl/subcpu/kn5000_subprogram_v142.asm` (v142 = the
  BIOS the driver loads); symbol map `kn5000-roms-disasm/symbols/subcpu_symbols_reference.txt`.
* live capture on the built driver `/home/fsanches/compartilhado/kn7000_mame_build/kn7000`
  (2026-07-23 21:29), roms `kn7000-emulator/roms`, isolated copy of pre-init nvram
  (`kn7000_mame/nvram/kn5000/nvram1+2`, boots to the play screen; RIGHT1=Piano, RIGHT2=Brass,
  LEFT=Modern E.P.).
* HLE `kn7000_mame/src/mame/matsushita/kn5000_tonegen.{cpp,h}`; driver `kn5000.cpp`.

---

## 0. TL;DR — the answer

The governing principle holds: **IC303 (TC183C230002) sees only register writes** (address latch
0x100000, data 0x100002). I dumped the full ordered (reg,data) note-on stream and the RAM
structures behind it. The per-instrument identity reaches the chip in **register +0x040** — NOT
the +0x440 "wave number".

* **+0x040 (group0.bank1) = `{ high nibble = partial CLASS/output-bus, low byte = multisample
  KEY-ZONE index }`.** Its value is literally `record[0]` — the first word of the note's active
  key-zone *partial record* — deposited by the voice builder into scratch `0x0451CE` and bursted
  to reg +0x040 by `ToneGen_WriteVoiceParams`. This is the KN5000 analogue of the KN7000 "aux
  word" (zone in the low byte, bank in the high bits) documented in
  `notes/wave-select-decode-and-donor-plan.md §1`.
* **The timbre triple +0x0C0 / +0x140 / +0x500 is CONSTANT per instrument** (across all notes)
  and disambiguates instruments that overlap in zone/bank.
* **+0x440 / +0x480 ("wave number", osc1/osc2) = 0x0000 for every ordinary PCM voice** — a legacy
  index-resolver output that the PCM voices bypass (both of its code paths bail; §4). This is the
  paradox, resolved: the chip does not address its samples through +0x440; it addresses them
  through +0x040 (+ the note register +0x400 for pitch, + the timbre triple).
* `ptr[0]+0x02` (Piano 0x00 / Brass 0x38 / Modern-E.P. 0x06 — **all three confirmed LIVE**) is the
  tone's **multisample-SET index**; it is consumed by `LABEL_032682`→`LABEL_03248B` to pick the
  partial set, which determines the `record[0]` (hence +0x040) words the chip then receives.

So the HLE must (and the shipped one already does) select the waveform from **register inputs
only**. The one concrete improvement: it currently keys on the **high byte** of +0x040 and
**discards the low byte** (the key-zone), collapsing every multisample split of an instrument to
one waveform. §7.

---

## 1. Memory structures — MEASURED

### 1.1 The voice descriptor (per allocated voice)
`LABEL_02B4E3` (0x02B4E3), the note-on voice-program entry, is called with `A = voice`(0..63) and
forms `XIZ = 0x04308E + voice*0x47` — a **71-byte voice descriptor**. Sibling note/key descriptors
live at `0x2942 + idx*0x47` (`LABEL_02B576`). Relevant descriptor fields (all
**PROVEN-BY-CONSTRUCTION** from `LABEL_02B576`, asm L26926-26969):

| desc off | meaning | how set |
|---|---|---|
| +0x01 | flags word; accumulates the partial-CLASS nibble (7000/5000/3000/1000/4000) & mod bits | `LABEL_023849`, `LABEL_023A05` |
| +0x03 | zone index | L26930 |
| +0x04 | note | L26933 |
| +0x0f | **current partial-record pointer** (record whose [0]→reg +0x040) | `LABEL_022A3F..AE7`, `LABEL_02399D` |
| +0x13 | tone-header pointer (`LABEL_032AE0` result) | L26964 |
| +0x17 | per-part sub-block ptr | L26967 |
| +0x1b/+0x1f | **partial-SET pointer** (`LABEL_032682`→`03248B` result) | L26969 / `LABEL_023849` reads +0x1f |
| +0x23 | **part_base** = `0x041368 + part*0x11F` | L26943-26947 |
| +0x27 | **tonerec** = `part_base + 0x6E + zone*0x25` | L26948-26961 |

### 1.2 The tonerec (delivered tone/patch record) — MEASURED live
`tonerec = 0x041368 + part*0x11F + 0x6E`. First 0x18 bytes = six 4-byte little-endian partial
pointers `ptr[0..5]`; then a trailer (`tonerec[+0x1a]` = the legacy bank field). Live dump at a
note-on (isolated pre-init nvram; **RIGHT1=Piano p0, RIGHT2=Brass p1, LEFT=E.P. p2**):

```
PART 0 (Piano) part_base=0x041368 part_base[+0x0a]=0x0004 tonerec=0x0413D6 tonerec[+0x1a]=0x0000
  ptrs: p0=0x05253A p1=0x076ABA p2=0x077923 p3=0x077923 p4=0x077923 p5=0x077923
  ptr0 bytes: 00 00 00 01 00 00   => ptr0+0x02 = 0x00
PART 1 (Brass) part_base=0x041487 part_base[+0x0a]=0x0004 tonerec=0x0414F5 tonerec[+0x1a]=0x0000
  ptrs: p0=0x05B66C p1=0x077121 p2=0x078247 ...
  ptr0 bytes: 00 40 38 00 00 00   => ptr0+0x02 = 0x38
PART 2 (E.P.)  part_base=0x0415A6 part_base[+0x0a]=0xC000 tonerec=0x041614 tonerec[+0x1a]=0x0000
  ptrs: p0=0x0532B7 p1=0x076B49 p2=0x077A5E p3=0x077A6D p4=0x077A31 p5=0x077A7C
  ptr0 bytes: 00 40 06 00 00 00   => ptr0+0x02 = 0x06
```

**`ptr0+0x02` = Piano 0x00 / Brass 0x38 / Modern-E.P. 0x06 — all three MEASURED LIVE**, matching the
task's anchor exactly (previously only Piano was live-confirmed).

Caveat on `ptr[2..5]` (correcting `kn5000-real-sample-select.md`): their 15-byte targets sit in
sub-CPU DRAM (0x077xxx / 0x078xxx). Their internal 24-bit "START/LOOP" words point back into
sub-CPU DRAM (0x02xxxx), **not** into the waveform ROM, and — proven by the note-on capture in §5
— **no such 24-bit value is ever written to IC303**. They are firmware-side envelope/LFO/partial
tables, not chip sample addresses.

### 1.3 The 44-byte tonegen scratch struct — MEASURED
`0x0451CC..0x0451F7` (44 bytes). The voice builder chain fills it; `ToneGen_WriteVoiceParams`
bursts it verbatim to IC303 (§3). Base+0x10 = `0x0451DC` = the osc1 wave word → reg +0x440, which
pins the base at 0x0451CC.

---

## 2. `ptr[0]+0x02` — the parse and its consumers (the task's starting point)

`ptr[0]` is the tonerec's first delivered partial pointer; `ptr[0]+0x02` is the byte
0x00/0x38/0x06. It is read in **`LABEL_032682` (0x032682)** — the partial-SET resolver — asm
L34747-34770 (**MEASURED**):

```
LABEL_032682:
    LD L,(XBC+001h) ; IYL = ptr[0]+0x01
    LD C,(XBC+002h) ; C   = ptr[0]+0x02   <-- the instrument multisample-set index
    LD IXL,A        ; A   = note/context arg
    ...             ; pack IY=+0x01, HL/C=+0x02, IX=note
    CALR LABEL_03248B ; resolve the partial set → pointer stored to desc+0x1b/+0x1f
```

So `ptr[0]+0x02` is **not** a wave number and **not** a register value directly. It is the
tone's **multisample-set selector**: `LABEL_032682`/`03248B` use it (with `ptr[0]+0x01` and the
note) to choose which family of partial records this voice draws from. The chosen set is stored
in the voice descriptor (+0x1b/+0x1f) and is what `LABEL_023849` (§3.1) then walks per key-zone to
fetch the `record[0]` word that becomes register **+0x040**. In short: `ptr[0]+0x02` selects the
sample family → that family's zone records set +0x040 → the chip addresses its sample from +0x040.
(**MEASURED** for the read; **PROVEN-BY-CONSTRUCTION** for the downstream link via desc+0x1f →
`LABEL_023849`.)

---

## 3. Struct → register transform

### 3.1 Where each register value is computed
`LABEL_02B4E3` runs a ~17-function pre-compute chain (asm L26813-26846), each writing part of the
0x0451CC struct, then `LDA XBC,0451CCh; CALL ToneGen_WriteVoiceParams` (L26849). The chain:
`LABEL_023849` (partial-type/zone → +0x040), `023A05`/`023A4A`/`023AD0` (pitch accumulators →
+0x400/+0x140), `024102`/`024444`/`024664`/`0248D5` (timbre/level), **`024BE3`** (wave-number
resolver → +0x440/+0x480; §4), `024F41`…`026637` (envelope/level/pan bus gains).

`ToneGen_WriteVoiceParams` (0x02D101, asm L29565+) — the burst, one ADD-offset per struct field
(**MEASURED**, full table):

| struct off | reg +off | group.bank | HLE reg_idx | role | per-instrument? |
|---|---|---|---|---|---|
| +0x02 | **+0x040** | 0.1 | 1 | **class nibble + key-zone byte** (=`record[0]`) | **YES (primary)** |
| +0x04 | +0x080 | 0.2 | 2 | velocity (bit15 latch set here, cleared at +0x3EF) | no (per-velocity) |
| +0x06 | **+0x0C0** | 0.3 | 3 | timbre/level/filter word | **YES (constant/instr)** |
| +0x08 | +0x100 | 1.0 | 4 | coarse pitch/portamento | no |
| +0x0A | **+0x140** | 1.1 | 5 | secondary pitch/detune word | **YES (constant/instr)** |
| +0x0C | +0x180 | 1.2 | 6 | expression | no |
| +0x0E | +0x400 | 4.0 | 8 | note log-pitch (~0x100/semitone) | no (per-note) |
| +0x10 | +0x440 | 4.1 | 9 | wave number osc1 = `wavenum \| (tonerec[+0x1a]&0xC0)` | **0 (bypassed)** |
| +0x12 | +0x480 | 4.2 | 10 | wave number osc2 | **0 (bypassed)** |
| +0x14 | +0x4C0 | 4.3 | 11 | level/key const (0x4400 obs) | no |
| +0x16 | **+0x500** | 5.0 | 12 | modulation/tone word | **YES (constant/instr)** |
| +0x18..+0x2A | +0x800..+0xA40 | 8/9/10 | 20.. | L/R + effect-send bus gains, envelope | no (level) |
| (voice+0) | +0x000 | 0.0 | 0 | key-on command `0x8100` (written near the end) | gate |

### 3.2 How +0x040 gets the class nibble + zone byte — MEASURED
`LABEL_023849` (0x023849) fetches the active partial record by **key-zone** and dispatches on
descriptor byte bits 5/6/7 into six near-identical builders (asm L14295-14361). Each builder does
`XBC = set_base + zone*stride; LD (desc+0x0f),XBC; ORW (desc+0x001),<CLASS>; LD WA,(XBC); LD
(0451CEh),WA` — i.e. **+0x040 = `record[0]` = the first word of the (instrument-family, key-zone)
partial record**, and stamps a CLASS constant into the descriptor:

| builder | record stride | CLASS OR const (→ desc+0x01) | observed +0x040 high nibble |
|---|---|---|---|
| 022A3F | 0x0F | **7000** | Piano = 0x7x |
| 022A61 | 0x0C | 5000 | — |
| 022A83 | 0x0D | 3000 | Guitar = 0x3x |
| 022AA4 | 0x0A | 1000 | Brass = 0x1x |
| 022AC5 | 0x06 | 4000 | Organ = 0x4x |
| 022AE7 | 0x04 | 0000 | Strings = 0x0x |

The CLASS constants (7/5/3/1/4/0) match the measured +0x040 high nibbles one-for-one — but note
the OR goes into **desc+0x01** (used for internal pitch math), while +0x040 itself takes
`record[0]` whose own high nibble already carries the same class (data + code agree). The default
+003==0 path `LABEL_02399D` (L15959) does the same `LD (0451CEh),WA` with an optional bank-doubling
when `RAM 0x041343` bit2 is set (L15969-15976). **PROVEN-BY-CONSTRUCTION.** Key consequence: the
**low byte of +0x040 is the multisample key-zone index** — it steps as the played note crosses
split points (verified live, §5), while the high nibble stays fixed per instrument.

---

## 4. Why +0x440 = 0 — MEASURED gate-by-gate (reconfirmed live)

`LABEL_024BE3` (0x024BE3) chooses between two wave-number mechanisms, then bails:
* **Primary** requires `tonerec[+0x1a] != 0` (asm L17878 `CPW (XWA+01ah),0000h; JRL Z,024DBE`).
  MEASURED `tonerec[+0x1a]=0` for Piano/Brass/E.P. → always diverts.
* **Fallback** `LABEL_024DBE` requires `part_base[+0x0a]` **bit15** (L18047 `BIT 0fh; JRL Z`).
  MEASURED: Piano/Brass `part_base[+0x0a]=0x0004` (bit15 clear → skip); E.P. `=0xC000` (bit15
  **set** → E.P. *does* enter the fallback), but the fallback validates the candidate against ROM
  table 0x2126 whose records all demand `note==0x1A` — so for an ordinary C4 it still returns 0.
* Result: the wave word `0x0451DC`/`DE` keeps its init **0** → reg +0x440/+0x480 = **0x0000**.

Live-reconfirmed for every captured voice below. The +0x440 register is a legacy/secondary
selector the KN5000's PCM multisample voices do not use.

---

## 5. LIVE per-instrument (reg,data) capture — the DIFF

Method: two write-taps on the sub-CPU bus — 0x100000 latches the register address, 0x100002 the
data — reconstructing the exact ordered stream the chip receives; per channel I snapshot the
identity registers at each key-on (`reg g0.b0.chN = 0x8100`). (Tap handles must be kept in globals
or MAME GC's them silently — an early false "0 writes" was exactly that.) Keys pressed across the
keyboard; the default nvram sounds **Piano (RIGHT1)** on the keyed range (RIGHT2/LEFT are not keyed
by the default split — see §8).

**Piano, this session, one note-on burst (C4), full ordered stream (voice 0):**
```
+040=0000? no -> reg=0x0040 d=7007 ; 0x0080 d=8C.. (vel) ; 0x00C0 d=7400 ; 0x0100 d=244E ;
0x0140 d=6FDA ; 0x0180 d=00.. ; 0x0400 d=<note> ; 0x0440 d=0000 ; 0x0480 d=0000 ;
0x04C0 d=4400 ; 0x0500 d=2C68 ; 0x0800 d=FF7F ; 0x0000 d=8100 (KEY-ON) ; 0x0840.. bus gains
```
**Piano across notes** (high nibble constant 0x70, low byte = key-zone stepping with pitch; the
0x10 bit distinguishes osc1/osc2; timbre triple constant):

| note | +040 osc1 | +040 osc2 | +0C0 | +140 | +500 | +440 | +480 |
|---|---|---|---|---|---|---|---|
| C2 | 7001 | 7011 | 7400 | 6FDA | 2C68 | 0000 | 0000 |
| C4 | 7007 | 7017 | 7400 | 6FDA | 2C68 | 0000 | 0000 |
| E4 | 7008 | 7018 | 7400 | 6FDA | 2C68 | 0000 | 0000 |
| C5 | 700A | 701A | 7400 | 6FDA | 2C68 | 0000 | 0000 |

The C4 value **7007 / 7400 / 6FDA / 2C68** matches the panel-selected Piano fingerprint measured in
`kn5000-wave-number.md §2` exactly — cross-validating both the nvram and the capture method.

**Per-instrument fingerprint DIFF** (Piano = live this session; Brass/Guitar/Strings/Organ = live,
panel-selected, `kn5000-wave-number.md §2`; **all instruments +0x440/+0x480 = 0**):

| instr | +040 (class·zone) | +0C0 | +140 | +500 | +440 | +480 |
|---|---|---|---|---|---|---|
| PIANO   | **70**·07 | 7400 | 6FDA | 2C68 | 0000 | 0000 |
| BRASS   | **10**·07 | 5A00 | 66D8 | 007F | 0000 | 0000 |
| GUITAR  | **30**·02 | 5A00 | 6FD7 | 2C60 | 0000 | 0000 |
| STRINGS | **00**·77 | 7F00 | 7F58 | 7F7F | 0000 | 0000 |
| ORGAN   | **40**·02 | 5A00 | 66C7 | 7F7F | 00C0 | 0040 |

Where instrument identity lands: **the high nibble of +0x040** (class/bus: 7/1/3/0/4), plus the
**+0x0C0 / +0x140 / +0x500** triple, are jointly distinct for all five. +0x040's low byte adds the
per-key multisample zone. Organ is the only one that even sets the +0x440 *bank* bits (0x00C0), and
its wave *byte* is still 0. **Predict-then-check:** predicted +0x440 would carry the wave → **MISS**
(0 for all); predicted +0x040 would carry class+zone and the timbre triple would be instrument-
constant → **HIT** (both confirmed live).

---

## 6. Conclusion — how IC303 selects its waveform from register inputs

Reconciling +0x440=0: the chip does **not** address its PCM through the +0x440 "wave number"
(a legacy resolver output the multisample voices bypass, §4). It addresses it through the
**combination it does receive**, primarily **register +0x040**:

* **+0x040 = the sample-directory index**: `{ bits[15:12] = bank/class, bits[7:0] = key-zone /
  multisample index }`. Piecewise-constant across the keyboard, stepping only at split points
  (MEASURED, §5) — the textbook signature of a multisample zone selector, and the direct KN5000
  analogue of the KN7000 "aux word" (`wave-select-decode-and-donor-plan.md §1`: bits[7:0]=zone,
  bits[13:12]=bank). The custom LSI dereferences an in-ROM directory from this word to reach the
  PCM start/loop/root (that directory lives in the undumped IC304-306; format unknown, and **not
  needed** — the HLE keys playback on (bank,zone) directly).
* **+0x400 = the note log-pitch** (continuous, ~0x100/semitone) — the playback rate, independent of
  the zone selection.
* **+0x0C0 / +0x140 / +0x500 = the timbre/filter/detune triple** — instrument-constant; they
  disambiguate instruments that share a bank/zone range and set the filter character.

This is fully within the chip boundary: everything above is a register the chip receives. The
firmware's RAM tonerec/partial structures are just how those register values are *computed*; they
never cross to the chip.

---

## 7. Fix proposal (register-inputs only; NOT implemented here)

The shipped `select_waveform_index` (`kn5000_tonegen.cpp` L635) already respects the boundary — it
hashes the **high bytes** of regs[1]/[3]/[5]/[12] (= +0x040/+0x0C0/+0x140/+0x500). Two register-only
refinements, in priority order:

1. **Use the full +0x040 word, not just its high byte.** Today `s1 = (regs[1]>>8)&0xFF` discards
   `regs[1] & 0xFF` — the **key-zone** — so every multisample split of an instrument collapses to
   one waveform (all piano notes → same wave). Fold the low byte in, e.g. key on
   `bank = (regs[1]>>12)&0xF`, `zone = regs[1]&0xFF`, and use `(bank,zone)` as the primary
   selector (mirrors the working KN7000 (bank,zone) playback path), with the +0x0C0/+0x140/+0x500
   high bytes as a secondary disambiguator. This makes an instrument's timbre track the keyboard
   splits the firmware actually programs.
2. **Keep +0x440/+0x480 out of selection** (they are 0 / bank-only). Retain the existing
   `resolve_waveform_rom` fallback for the hypothetical day the resolver emits a nonzero wave.

No RAM peeking, no sub-CPU structures — the selection stays addressable from the register stream
alone, consistent with §6. (The real per-zone PCM remains blocked on the NO_DUMP IC304-306; this
is a *selection* fix, not a fidelity fix.)

---

## 8. Reproduction & honest gaps

Run (isolated; nothing committed but this note):
```
SP=<scratchpad>; cp kn7000_mame/nvram/kn5000/nvram{1,2} $SP/run/nvram/kn5000/
cd kn7000-emulator && timeout 300 kn7000 kn5000 -rp roms -window -skip_gameinfo \
  -nvram_directory $SP/run/nvram -autoboot_delay 0 -autoboot_script $SP/vp_cap5.lua \
  -seconds_to_run 45 -nothrottle
```
Lua technique: `space:install_write_tap(0x100000,0x100001,...)` (addr) +
`install_write_tap(0x100002,0x100003,...)` (data), **store the returned handles in globals**;
`space:read_u8/u16/u32` for RAM. The play screen is reached by ~t=5 s once the keybed FIFO is being
polled (`kbd` read-tap on 0x110000 goes non-zero); press only after that.

Gaps / not-yet-done (honest):
* **Brass/E.P. register fingerprints were not re-captured LIVE this session** — the default nvram
  split sounds only Piano on the 61-key bed (RIGHT2/LEFT are not keyed by the default split). Brass
  is cited from the prior panel-selected live capture; E.P.'s register fingerprint is the one value
  I have only structurally (RAM: `ptr0+0x02=0x06`, `part_base[+0x0a]=0xC000` → it takes the §4
  fallback path). To close this, force RIGHT2/LEFT part-on (panel or a temporary hook) and re-run
  the §5 tap — the prediction is Brass +0x040 high nibble 0x1x and a non-7 E.P. class.
* The in-ROM sample directory format that IC303 dereferences from +0x040 is unknown (lives in the
  undumped IC304-306). Not required for the HLE, which keys on (bank,zone) directly.
* `LABEL_03248B` (the innermost partial-set resolver `ptr0+0x02` feeds) was traced to its inputs,
  not exhaustively through its body — sufficient to establish `ptr0+0x02` = multisample-set index.

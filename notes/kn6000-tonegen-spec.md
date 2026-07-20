# KN6000/KN6500 tone generator — architecture comparison and device spec

> Produced 2026-07-20, answering Felipe's question: *"do the KN6000/KN6500 use the same
> tone generator, and could one device be shared by all models?"*
> Method: static RE of both firmwares, NOT part-number reasoning. Every claim below cites
> a firmware address. Companion: `notes/sound-cross-model-kn6000-kn6500.md` (hardware
> inventory), `notes/tg-voice-register-semantics.md` (the KN7000 decode).

All addresses are MN10300 CPU addresses. KN7000 lib-ROM code is at program-ROM file
offset `0x3B9000` → CPU `0x4C000000`. KN6000 image = `kn7000_scratchpad_snapshot/kn6000_prog.bin`,
file offset = addr − `0x48400000`.

## 0. The answer in one line

**Different part numbers, same architecture.** The two firmwares are re-targets of one
source tree, and their tone-generator driver layers are demonstrably the same code with a
re-tuned constant table. A shared base class is justified and has been implemented
(`src/mame/matsushita/kn_tonegen.{cpp,h}`); what differs between models is *numbering and
sizing*, not behaviour.

**The decisive datum:** the KN6000's TG write primitive at `0x4849465B` is **byte-identical**
to the KN7000's TG-A leg at `0x4C036F7C` — the same 20 bytes,
`81 f8c510 fc8700000598 fae0ffff fc8302000598`. The KN7000's writer is that same routine
with a chip-select branch (`cmp 0x40,d0`) wrapped around it. The KN7000's two-chip path is
literally a parameterised generalisation of the KN6000's one-chip path.

## 1. Comparison table

| # | Point | KN7000 (`C1BB00000709` ×2) | KN6000 (`D82398GD001` ×1) | Verdict |
|---|---|---|---|---|
| (a) | Write primitive | `TgVoiceRegWrite` entry **0x4C036F6B**: `d0`=slot, `d1`=class<<16, data on stack → `asl 20,d0; or d1,d0; or data,d0` → packed word; then `mov d0,d1; lsr 16,d1; movhu d1,(0x98050000); and 0xffff,d0; movhu d0,(0x98050002)` | Writer **0x4849465B**: packed word pre-assembled by callers (`asl 20,d0; or 0x000CDDDD,d0`), then the identical latch sequence | **SAME** — 20 bytes byte-identical at KN7000 `0x4C036F7C` / KN6000 `0x4849465B`. Same address-halfword-to-+0 / data-halfword-to-+2 discipline, same packed word `(slot<<20)｜(class<<16)｜data`, so **addr halfword = (slot<<4)｜index** on both |
| (a′) | Second addressing mode | `asl 18` variant at **0x4C036FD9** (channel in a 2-bit-lower field, global/channel regs), 24 sites | `asl 18` variant present, 14 sites (e.g. **0x48493FA8, 0x484940A2, 0x48494171**, class `0x0802`) | **SAME** |
| (b) | Register file / EG shape | 16 halfword regs per voice, four 4-reg banks. Amp EG = r0/r1/r2 `[rate\|level]` pairs; gate r3; pitch EG r4/r5/r6; depth r7; filter EG r8/r9/rA; rB. Boot reset `0xFF80/0xFF00` → r0/r1 (**0x4C0371BC/0x4C0371CC**); damp `0xA280/0xA200` (**0x4C037220/30**), `0x7F80/0x7F00` (**0x4C037298/0x4C0372A5**); mute `0xC000`; release burst = regs **{0,1,4,5,8,9}** | Same 16 regs, four 4-reg banks, same `[rate\|level]` pairs, **identical literal constants**: `0xFF80/0xFF00` → r4/r5 (0x484946DC region), `0xA280/0xA200` → r4/r5 (**0x484947B3**), `0x7F80/0x7F00` → r4/r5 (**0x48494817, 0x4849487B**), `0xC000` → r5/r6 (**0x484946DC**); release burst = regs **{4,5,8,9,C,D}** | **SHIFTED-BUT-ISOMORPHIC** — identical semantics AND identical constants, but the EG banks sit at 4/8/C instead of 0/4/8, and the **gate register moves r3 → r0**. Not a uniform rotation: a re-assignment |
| (b′) | Gate value | `0x87FF` note-on at class **0x0003** (`0x4C037378`, `TgVoiceGateOn`); `0x8000` key-up | `0x87FF` note-on at class **0x0000** (`0x484948D7`: `asl 20,d0; or 0x87ff,d0`, no class OR ⇒ index 0); live capture shows `0x0000=0x8000` key-up | **SAME value, DIFFERENT index** |
| (c) | Pitch encoding | Gate-on reads shadow rec **+0x54**: `and 0x00018000,d0; or 0x4000,d0; d1=0x30000000` ⇒ class **0x3000\|bit16** (`0x4C03738D`). Runtime pitch class **0x2400/0x2401**, `pitch18 = ((cls&1)<<16)\|data` | Gate-on reads shadow rec **+0x7C**: `and 0x00018000,d0; or 0x58004000,d0` ⇒ class **0x5800\|bit16**, data base 0x4000 (`0x484948E0`) | **Mechanism SAME** (byte-for-byte the same idiom, 17th pitch bit in class bit 0); **plane number DIFFERENT** |
| (c′) | "Group shifted one bit" hypothesis | plane = class>>10, 6-bit channel at bits 4–9 | callers provably build `slot<<20` ⇒ slot at addr bit 4, 4-bit index — **same split** | **FALSIFIED.** A 7-bit channel would put KN7000 plane 0x0C at `0x6000` and 0x09 at `0x4800`; observed is `0x5800`. The bitfield split is identical; only plane *numbering* is remapped. The live-capture `0x800B/0x8400/0x8804/0x8C0F` vs `0x400B/0x4400/0x4804/0x4C0F` relation is a **local** remap of planes 0x10–0x13 → 0x20–0x23, not a global shift |
| (c″) | Plane inventory | 0x00–0x14, 0x1F, **0x20** (send matrix `0x8000\|row<<8\|part<<4\|reg`), **0x28** (`0xA000..0xA008` global bank), 0x2C, 0x30, 0x3F | 0x00–0x19, **0x20–0x24** (`0x8000/0x8400/0x8800/0x8C00/0x9000`), **0x28** (`0xA000/0xA002/0xA004`) | **SHIFTED-BUT-ISOMORPHIC** — the two *structural* planes match exactly: plane **0x20 = per-channel send/output matrix** and plane **0x28 = global bank** at the SAME numbers. Only per-voice parameter planes below 0x20 are re-assigned (KN6000 has ~5 more) |
| (d) | Voice slots / strides | **128 slots**. Lib voice record `0x500AF940 + slot*0xB4` → ends exactly at `0x500B5340` (the known part-record base). Shadow register image `0x500CA0B0 + slot*0x84` → ends `0x500CE2B0`, just below the TG gate `0x500CE380` | **64 slots**. Lib voice record `0x502858F8 + slot*0xB4` (`0x48493248`, `0x484934E3`) — **same 0xB4 stride**. Shadow image `0x50043100 + slot*0xA0` (`0x484946D4`, `0x48494764`) → `+64*0xA0 = 0x50045900`, exactly the next independently-observed RAM base (17 refs) | **SHIFTED-BUT-ISOMORPHIC** — same two-table model, same lib stride 0xB4; 128 vs 64 slots; shadow stride 0x84 vs 0xA0 |
| (d′) | Part model | 34 parts (`0x22` bound in `TgPartKeyEvent`), part tone block stride `0x130` | `cmp 0x22,d1/d2` at the part loop (`0x48494654`); stride `0x130` is the most-used mulu constant (61 sites) | **SAME** |
| (e) | Chips addressed | Writer branches `cmp 0x40,d0; bge` → slot<0x40 ⇒ TG A (`0x98050000/2`), else `and 0x3f,d0` ⇒ TG B (`0x98040000/2`). Plus a TG-B-only variant (`0x4C036FB6`) and a broadcast variant (`0x4C036FD9`) | **No branch at all** — single window `0x98050000/2`. `0x9804` appears once, in the unrelated Device-A module (`0x4851045D`) | **SHIFTED-BUT-ISOMORPHIC, and the key structural finding** — the KN6000 writer *is* the KN7000's TG-A leg, byte-identical; the KN7000 wraps it in a chip select from slot bit 6 |
| — | Init strobe | `0x98040010` ×3 and `0x98050010` ×3 | **0 sites** | **DIFFERENT** — KN6000 has no equivalent init strobe |
| — | Wave-ROM readback | `0x98050006/8/A` window, 3 sites | same window, 5 sites | **SAME protocol** |

## 2. What is NOT established (do not build on these)

- **KN6000's runtime pitch plane.** The *init/gate-on* pitch plane is proven 0x5800 with the
  identical 18-bit mechanism. Whether KN6000 also has a *separate runtime bend* plane (the
  analogue of KN7000's 0x2400 vs 0x3000 pair) is **INCONCLUSIVE**; the live capture only ever
  saw 0x5800.
- **The full per-voice plane correspondence below 0x20.** It is a remap, not a shift, and three
  points are pinned (send matrix 0x20↔0x20, global bank 0x28↔0x28, pitch 0x3000↔0x5800). The
  remaining ~20 planes are **INCONCLUSIVE** without a per-plane live sweep on KN6000.
- **Whether the index re-assignment (gate r3→r0, EG banks +4) is silicon or firmware
  convention.** The evidence is unambiguous about *what* is written but cannot by itself
  distinguish "different chip register map" from "same chip, different bank chosen". Leaning
  to a real chip-map difference, because the same literal damp constants land on different
  indices — but flagged.
- **Whether KN6000's 64 slots are 64 voices ×1 element or 32 ×2 elements.** The KN7000's
  even/odd companion-block pairing has no confirmed KN6000 counterpart. **INCONCLUSIVE**.

## 3. What a future `kn6000_tonegen_device` needs

Already provided by the shared base (`kn_tonegen.{cpp,h}`), no work required: the envelope
state machine and rate→seconds law, per-voice state, the gate-follow key coupling, the
effect-send/return gains, the synthetic wave pack, the audio stream and rendering. Voice
count is a constructor parameter — pass **64**.

To be written in the derived device:
1. **`tg_write()` decode** for the KN6000 numbering. Known today: gate at index **0**
   (`0x87FF` on / `0x8000` up), EG banks at **4/8/C** as `[rate|level]` pairs, mute `0xC000`,
   pitch plane **0x5800** with `pitch18 = ((cls&1)<<16)|data`, send matrix plane **0x20**,
   global bank plane **0x28**. Address split is the same: `(slot<<4)|index`, `cls = addr & 0xFC0F`.
   **Mark the plane map PROVISIONAL** until a per-plane live sweep fills in §2's gaps.
2. **Single window**: one TG at `0x98050000/2`; no chip select, no init strobe. In the driver's
   `io_w`, call `tg_write(0, ...)` only.
3. **Machine config**: 64 voices; kn6000/kn6500 share one device (their audio sections are
   identical apart from KN6500's two extra wave ROMs).

### Blockers that make the device useless until resolved — do NOT ship it before these

- **Wave ROMs undumped**: 4× `QSIGX3C640xx` (KN6000) / 6× (KN6500). The same service-test
  readback window (`0x98050006/8/A`) that works on the KN7000 exists here, so a hardware
  software-dump is possible.
- **Table mask ROMs IC13/IC14 undumped** (`QSIGX3C16008/16007`; KN6500 `C3FBMD000069/68`).
  The TG sample maps most likely live there — without them even a perfect register model
  has nothing to play.
- **KN6000 note→pitch routine un-reversed.** Register-diffing failed (documented dead ends in
  `sound-cross-model-kn6000-kn6500.md`): pitch is multisample + firmware-computed. The
  efficient path is static RE of the KN6000 analogue of the KN7000's `0x4844812D`. Standing
  decision: **do not enable kn6000/kn6500 sound with a guessed pitch.**

## 4. Suggested next step

A per-plane live sweep on the KN6000 (it already boots to its play screen and its TG voice
engine runs on key presses with no gate fix — see the dynamic-capture section of
`sound-cross-model-kn6000-kn6500.md`) would convert §2's INCONCLUSIVE rows into a complete
plane map. Reuse `tools/stage2_tg_diagnostic.lua`. That, plus the note→pitch RE, is the whole
remaining gap between here and a working KN6000 tone generator — the *architecture* question
is now settled.

---

# ★ RESOLVED 2026-07-20 — the device SHIPPED and the KN6000 SINGS

Everything in §2 ("What is NOT established") and §3's blocker list is settled or
re-characterised below. `kn6000_tonegen_device` exists
(`src/mame/matsushita/kn6000_tonegen.{cpp,h}`), is wired into `kn6000(machine_config)`,
and the KN6000 plays **musically correct pitch**, live-verified.

Method note: §4 proposed a per-plane LIVE sweep. That turned out to be the slower route.
The firmware **enumerates its own register map**, so the static route gave a *complete*
map in one read, and the live capture then confirmed it register-for-register.

## 1. THE COMPLETE PER-PLANE MAP (was: "~20 planes INCONCLUSIVE")

The note-on routine at **0x484948CB** is a straight blit of the 0xA0-byte shadow register
image (`0x50043100 + slot*0xA0`) into the chip: one `call 0x4849465B` per register, each
with its destination OR-ed in as a literal. Reading the literals off in order yields the
whole map, and **every byte of the 0xA0-byte record is accounted for** — which is what
makes it a map rather than a sample:

| cls | shadow src | width | meaning |
|---|---|---|---|
| 0x0000 idx 0 | (literal 0x87FF) | — | **GATE** — 0x87FF note-on, 0x8000 key-up |
| 0x0001–0x000F | +0x02..+0x2A | u16 | per-voice registers 1..15 (see banks below) |
| 0x0400 / 0x0401 | +0x2C / +0x2E | u16 | |
| **0x5000** | **+0x74** | u32 | **18-bit pitch** — high half extends the class nibble |
| 0x5400 | +0x78 | u32 | pitch companion |
| 0x5800 | +0x7C | u32 | gate-on pitch INIT (`and 0x00018000; or 0x58004000`) |
| 0x0800–0x080D | +0x30..+0x3E | u16 | |
| 0x1000–0x3000 | +0x40..+0x60 | u32 | |
| **0x4000** | **+0x64** | u16 | **per-voice LEVEL** (default full = 0x3FFF) |
| 0x4400–0x4C00 | +0x68..+0x70 | u32/u16 | |
| 0x5C00–0x6400 | +0x80..+0x88 | u32 | |
| 0x8000–0x9000 | +0x8C..+0x9C | u32 | **per-voice wave/sample params** |

### Envelope banks — CONFIRMED by literal, not by position
`0x484947B3` writes the same `0xA280/0xA200` damp pair the KN7000 writes to its r0/r1,
and `0x484946DC` writes the same `0xC000` mute — to **cls 0x0004/0x0005/0x0006**. So the
amplitude EG is at 4/5/6, the three banks sit at 4/8/C (KN7000: 0/4/8), and the release
burst hits {4,5,8,9,C,D} where the KN7000 hits {0,1,4,5,8,9} — the first two registers of
each of three banks in both cases. The gate is the one register that genuinely moved:
r3 → r0.

## 2. ★ FALSIFIED: "plane 0x20 = send matrix on both chips"

§1 row (c″) called plane 0x20 and plane 0x28 "the two *structural* planes [that] match
exactly". **The 0x20 half is wrong.** The note-on blit sources cls 0x8000–0x9000 from
shadow +0x8C..+0x9C, i.e. on the KN6000 those are **per-voice wave/sample parameters**,
not a per-channel send matrix. (The live capture even said so and was misread: its
`0x800B/0x8400/0x8804/0x8C0F` quartet carries *identical data* to the KN7000's
`0x400B/0x4400/0x4804/0x4C0F` — same default patch, per-voice both times.)

The send matrix appears instead in the **0xA0xx** family — `0xA0F8 / 0xA178 / 0xA188 /
0xA198 / 0xA1A8 / 0xA1B8 / 0xA1C8 / 0xA1E8`, the same `row<<8 | part<<4 | reg` shape,
rebased onto plane 0x28. Which row means which effect bus is **still unverified**, so the
shipped device deliberately does NOT drive the effect-send gains from it (see §5).

## 3. THE NOTE→PITCH ROUTINE — dissolved, not reversed

§3 listed "KN6000 note→pitch routine un-reversed" as a blocker and the earlier recon
declared KN6000 pitch "not extractable by simple register-diffing". Both stand as
statements about the *chip registers* — and both are beside the point, because the KN6000
never had to be reversed at all. It is the **same trick the KN7000 already uses**: the
firmware computes the musical pitch itself and publishes it in a voice record.

The KN6000's record initialiser at **0x48493D80** writes, from a halfword `pitch16` arg:

```
movhu (0x20,sp),d0; asr 8,d0; extbu d0; or 0x80,d0; movbu d0,(8,a1)   ; +0x08 = 0x80|(pitch16>>8)
movhu (0x20,sp),d0; movhu d0,(0xa,a1)                                 ; +0x0A = base pitch16
movhu (0x20,sp),d0; movhu d0,(0xc,a1)                                 ; +0x0C = notePitch16
```

Field-for-field the KN7000's layout (+0x07 part, +0x08 active|note, +0x0A base pitch16,
+0x0C notePitch16, +0x10 velocity, +0x3C/40/44 element pointers), at the same 0xB4 stride.

### ★ THE ONE REAL TRAP: two 0xB4 arrays, only one indexed by slot
The obvious array — the **library** array at `0x502858F8` — is indexed by *note-event
element*, NOT by voice slot. Live-measured: playing C4 then C5 filled library records
**00/01 both times**, while the notes went to TG slots 0/1 then 2/3. Reading it by slot
gives the wrong record (or an inactive one) and silently poisons the pitch.

The array to read is **`0x5027AF28`**, a per-TG-SLOT **copy** the firmware makes at
note-on (`0x48492F20`: destination `mulu slot,0xB4; add 0x5027AF28`, source
`mulu libidx,0xB4; add 0x502858F8`, then a 0x2D-word block copy). Indexing *that* by slot
reproduces the KN7000's record-index == slot identity exactly.

**KN6500 equivalents** (its build shifted the RAM layout; both located the same way, via
the note-on record copy at 0x48492E07): per-slot record **0x5027AF1C**, shadow image
**0x500430AC**.

## 4. LIVE VERIFICATION

`tools/kn6000_tg_probe.lua` (new) taps the single TG window, locks onto the first slot of
a note's burst, and samples the voice record **at the note-on pitch write**:

```
NOTE 60 -> slot 0 : +0x08 = BC (active, note 60)  +0x0C = 3C80 -> MIDI 60.000
NOTE 72 -> slot 2 : +0x08 = C8 (active, note 72)  +0x0C = 4880 -> MIDI 72.000
```

and the ordered write burst matches the static blit map register-for-register, including
the universal key-up `0x0000=8000` and the voice-steal `0x0005/0x0006=C000`.

**Audio (the real test)** — `-wavwrite` capture, FFT of the loudest window:

| note | expected | measured | error |
|---|---|---|---|
| C4 (60) | 261.63 Hz | **261.72 Hz** | +0.01 semitone |
| G4 (67) | 392.00 Hz | **392.14 Hz** | +0.01 semitone |
| C5 (72) | 523.25 Hz | **523.44 Hz** | +0.01 semitone |

Correct across more than an octave — so this is real resolved pitch, not a coincidence at
one anchor. Timbre is the placeholder sine (wave ROMs still undumped); pitch, polyphony,
note timing and the 7-parameter amplitude envelope are the firmware's own.

**KN7000 not regressed:** reverb/keybed oracle **c3b67ea711ce3c00f8ae2af1e07651cb**,
bit-identical across three runs (twice pre-publish, once on the final published binary).

## 5. WHAT THE SHIPPED DEVICE DELIBERATELY DOES NOT DO

- **Effect-send matrix**: not decoded (§2 — the 0xA0xx row map is unverified). The gains
  keep their defaults rather than being driven from a guess.
- **Aux/mode word**: the analogue of the KN7000's cls 0x1C02 gate-follow marker is not
  identified, so every voice is treated as MANAGED. Safe here, because the KN6000 writes a
  **universal** key-up gate for all voice classes — nothing can hang waiting for a release.
- **Record type**: the KN6000's +0x02 values (1/8 plus flags 0x0100/0x0800, written at
  0x48492FF0) are not mapped onto the KN7000's {04,08,10,20,40} release classes, so the
  resolve reports "unknown" rather than guessing.
- **Even/odd companion pairing**: still unconfirmed (§2), so the managed-release rule
  releases only the written voice, never a `{v&~1, v|1}` pair.
- **Pitch/filter envelopes**: cached, not modelled (same state as the KN7000).

## 6. STILL BLOCKED

- **Wave ROMs undumped** (4× / 6× `QSIGX3C640xx`) and **IC13/IC14 table mask ROMs
  undumped** — the timbre stays a placeholder. Unchanged, and it never blocked the device:
  pitch/polyphony/envelope are all real without them.
- **★ KN6500 emits ZERO tone-generator writes on a key-bed press** (live-probed). Its
  voice engine never starts — a boot/enable-gate difference from the KN6000, NOT a decode
  problem. Its device and record binding (§3) are in place and correct; the machine stays
  `MACHINE_NO_SOUND` until that gate is found. **This is the next thing to chase.**

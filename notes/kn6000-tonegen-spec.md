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

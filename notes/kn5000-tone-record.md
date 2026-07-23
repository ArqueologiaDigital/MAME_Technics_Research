# KN5000 tone record (tonerec) — why the sub-CPU wave-number resolver emits 0

Author: autonomous RE + live-capture pass, 2026-07-23. Requested by Felipe Sanches.
**Investigation only** — no `src/` edits, no committed code changes. All MAME breakpoints /
watchpoints were runtime-only (lua autoboot scripts in a scratchpad dir); the repo is
untouched apart from this note. The shipped timbre-palette code (`kn5000_tonegen.cpp`) was
NOT modified.

Builds on `notes/kn5000-wave-number.md` (the register fingerprint + the "wave 0 for every
instrument" measurement), `notes/kn5000-tonegen-register-semantics.md`.

Evidence labels: **MEASURED** (read from the RUNNING machine / ROM bytes / disasm),
**INFERRED** (deduction from measured facts), **SPECULATIVE**.

Sources:
* sub-CPU disasm `kn5000-roms-disasm/archive/asl/subcpu/kn5000_subprogram_v142.asm`
  (v142 = the default BIOS the driver loads, `kn5000.cpp` L1142; label `LABEL_02XXXX`
  encodes the runtime RAM address 0x02XXXX — code runs decompressed in sub RAM).
* live capture on the published `kn5000` driver (`~/compartilhado/kn7000-emulator/kn7000`,
  built 2026-07-23 18:19), isolated pre-initialised nvram (`nvram/kn5000/nvram2`) that
  boots to the play screen: **RIGHT1 = Piano, RIGHT2 = Bigband Brass, LEFT = Modern E.P.1**.
* `kn5000.cpp` `subcpu_mem` / `maincpu_mem` memory maps.

---

## 0. TL;DR — the delivery link is NOT empty; wave-0 is the firmware's own output

**The premise "the tone record isn't delivered, so the resolver has nothing to look up" is
FALSIFIED by live capture.** The tone record, the per-partial parameter data it points to,
and the resolver's own ROM tables are ALL correctly present in sub-CPU RAM. MAME delivers
the main-CPU→sub-CPU payload. The wave-number register is 0 because the firmware's
wave-number **resolver is a secondary path that is gated OFF** for the KN5000's ordinary PCM
multisample voices, and even on the one class that does reach it (Organ) the resolver's
lookup tables return 0. The per-instrument identity travels through the tonerec's
partial-parameter pointers into the pitch/timbre registers — not through the +0x440
wave-number register.

Concretely, MEASURED at a C4 note-on on Piano (identical for Brass / Modern E.P.):

| fact | value | how |
|---|---|---|
| `LABEL_024BE3` (wave-resolver caller) hits | **2** (osc1+osc2) | bp count |
| `LABEL_02177E` (the resolver) hits | **0** | bp count |
| `LABEL_024DBE` (fallback path) hits | **2** | bp count |
| wave-word scratch `0x0451DC` writes | **0x0000** ×4 | wp on 0x0451DC |
| `tonerec[+0x1a]` (primary-path gate) | **0x0000** | RAM dump |
| `part_base[+0x0a]` bit15 (fallback gate) | **0** (word = 0x0004) | RAM dump |
| tonerec first 0x18 bytes | **six live 4-byte partial pointers** | RAM dump |
| resolver tables 0x2126 / 0x24E6 / 0xF48C | **populated, non-zero** | RAM dump |

So **both** wave-number code paths bail before computing anything, and +0x440 / +0x480 keep
the init value 0. This reproduces `kn5000-wave-number.md` §2 exactly, and now explains it.

---

## 1. Where tonerec lives, its layout, how it is selected — MEASURED

`LABEL_024BE3` (asm L17865) is the per-voice wave-number resolver-caller. It is entered with
`XWA = vptr` (a per-voice/per-note descriptor) and pulls, from vptr:

```
vptr+0x23 -> part_base   (LD XWA,(XWA+023h); LD (XSP+004h),XWA)   ; the PART block
vptr+0x27 -> tonerec     (LD XWA,(XWA+027h); LD (XSP+008h),XWA)   ; the TONE-ZONE record
vptr+0x04 -> note-index  (LD A,(XWA+004h);   LD (XSP+010h),A)
vptr+0x03 -> keyscale    (LD A,(XWA+003h);   LD (XSP+012h),A)
vptr+0x00 -> tone id     (used as resolver arg C = LD A,(XWA))
```

Both pointers point INTO a resident per-part block. The pointer arithmetic is built in
`LABEL_02B576` (asm L26944-26961), MEASURED:

```
part_base (vptr+0x23) = 0x041368 + part*0x11F
tonerec   (vptr+0x27) = 0x041368 + part*0x11F + 0x6E + zone*0x25
```

* **base 0x041368** in sub-CPU DRAM (mapped `map(0x000000,0x0fffff).ram()`, `kn5000.cpp`
  L451). MEASURED: this block is densely populated per part.
* **part stride 0x11F**, three parts observed (RIGHT1 / RIGHT2 / LEFT at part 0/1/2).
* **tone-zone records: 0x25 bytes each, starting at part_base+0x6E**, several zones
  (key-splits) per part.

The `+0x1a` field the task cited is `tonerec[+0x1a]`; the primary path ORs
`tonerec[+0x1a] & 0xC0` (a 2-bit bank) into the resolved wave number (`LABEL_024CAB`
L17939-17962, `AND WA,00c0h; OR WA,(XSP+00eh); LD (0451DCh),WA`).

### tonerec is POPULATED — MEASURED (part 0 / Piano, zone 0 @ 0x0413D6)
```
0413D6: 3A 25 05 00 | BA 6A 07 00 | 23 79 07 00 | 23 79 07 00 | 23 79 07 00 | 23 79 07 00 | 00 00 ...
        ptr=0x0005253A  0x00076ABA   0x00077923   0x00077923   0x00077923   0x00077923   +0x18..0x24 = 0
```
Six 4-byte partial pointers (+0..+0x17), then a small trailer that is all-zero here — so
`tonerec[+0x1a] = 0`. The pointers are LIVE: `0x0005253A` holds a real voice-parameter
record (envelope / filter / tuning bytes: `00 00 00 01 … 54 15 80 48 21 7F FB … 64 4A 32 4E
00 2E 0F 06 …`), and `0x00076ABA` / `0x00077923` hold further LFO / envelope-segment tables
(MEASURED dumps). This is the decoded tone/patch definition; it is **present**, not stale.

---

## 2. Delivery path — MEASURED that it WORKS (this is the key negative result)

The sub-CPU has no access to the Table Data ROM (that ROM sits on the MAIN-CPU bus,
`maincpu_mem` `map(0x800000,0x9fffff).rom().region("table_data")`, `kn5000.cpp` L445). The
tone definition therefore must reach the sub-CPU over the inter-CPU latch
(`map(0x120000,0x12ffff)` → `subcpu_latch_r`/`maincpu_latch_w`, IC22/IC23). The decoded
result of that transfer is the data in §1: the partial-parameter records at `0x05xxxx` /
`0x07xxxx` and the tonerec pointer array in the 0x041368 block.

**All of it is present in RAM after boot.** Therefore:

* the main-CPU→sub-CPU tone payload transfer **is** modelled and **does** run (not the empty
  link);
* the `table_data` / `custom_data` ROM regions are mapped and read (their decoded voice
  parameters are in sub RAM); nothing is unmapped or mis-read here;
* there is no strap/config gate suppressing the transfer.

So of the task's three candidates — (a) a missing MAME transfer / unmapped ROM, (b) a
strap/config gate, (c) genuine firmware state — **(a) and (b) are ruled out by measurement.**
This is (c): the firmware, given inputs that are all correctly present, genuinely emits wave
0. (This retires the `kn5000-wave-number.md` §2 lead "the main-CPU→sub-CPU tone-record
pipeline does not deliver a populated tonerec" — it DOES.)

---

## 3. WHY the resolver emits 0 — MEASURED gate-by-gate

`LABEL_024BE3` chooses between two wave-number mechanisms and a bail:

### 3a. Primary path — requires `tonerec[+0x1a] != 0`
```
L17877  LD XWA,(XSP+008h)          ; tonerec
L17878  CPW (XWA+01ah),0000h
L17879  JRL Z, LABEL_024DBE        ; tonerec[+0x1a]==0  -> divert to fallback
```
MEASURED `tonerec[+0x1a] = 0` for Piano/Brass/Modern-E.P. → **always diverts.** Only tone
classes whose record carries a non-zero bank field take this path — per
`kn5000-wave-number.md` §2 that was **Organ alone** (its +0x440 showed 0x00C0, i.e. the bank
bits, but the **wave byte itself was still 0** — the resolver returned 0 even there; see §3c).

### 3b. Fallback path (`LABEL_024DBE`, L18043) — requires `part_base[+0x0a]` bit15
```
L18044  LD XWA,(XSP+004h)          ; part_base
L18045  LD WA,(XWA+00ah)           ; part_base[+0x0a]
L18047  BIT 0fh, WA
L18048  JRL Z, LABEL_024E66        ; bit15 clear -> skip osc1 wave, go to osc2
```
and the osc2 half (`LABEL_024E66`, L18093) gates identically on the SAME field:
```
L18094  LD XWA,(XSP+004h); LD WA,(XWA+00ah); BIT 0fh,WA; JRL Z, LABEL_024F3C
```
MEASURED `part_base[+0x0a] = 0x0004` → **bit15 clear on BOTH halves** → neither
`LABEL_033E02`(the wave-region lookup) nor `LABEL_02177E`(the refiner) is called; `0x0451DC`
(osc1 → reg +0x440) and `0x0451DE` (osc2 → reg +0x480) stay at the init 0. This is why the
resolver bp count was 0 while 024DBE was 2.

`part_base[+0x0a]` is written as a per-voice PITCH accumulator, not a discrete flag
(`LABEL_023A8E` L16063: `+0x0a = part_base[+0x06] + [0x293E]`; `LABEL_023A05` L16005 a longer
variant). part_base[+0x06] = 0x24D4 and [0x293E] = 0 (MEASURED), so even a fully-computed
value would be ≈0x24D4 — **bit15 still clear**. So bit15 of this field is a pitch-range /
tone-class discriminator that is naturally clear for ordinary audible voices; the fallback
resolver is reached only for a minority tone class (high-range / special), not for normal
PCM voices. INFERRED (from the field's writers + the measured magnitude).

### 3c. Even when reached, the resolver returns 0 — MEASURED (tables) + prior MEASURED (Organ)
The resolver `LABEL_02177E` (L12300) validates a candidate wave against table 0x2126
(5-byte records): it requires `record[+2] == note` and `record[+3] == F4AC[keyscale]`.
Live dump of 0x2126:
```
002126: 01 3F 1A 00 FF | 02 00 1A 00 FF | 03 01 1A 00 FF | 04 02 1A 00 FF | ...
```
Every record has `+2 = 0x1A`, `+3 = 0x00`. So the resolver only validates a wave when the
`note` argument (vptr+0x04) equals **0x1A** and `F4AC[keyscale]` equals 0; for any other
note-index it falls through to the keyscale-recursion / "invalid" branch. Combined with the
prior MEASURED fact (`kn5000-wave-number.md` §2) that Organ — the one instrument that DOES
reach the resolver — still produced a **zero wave byte**, this shows the resolver returns 0
for ordinary note-ons even when it runs. Tables 0x24E6 / 0xF48C / 0xF4AC are likewise loaded
and non-zero (dumped), so this is not an unloaded-table artifact. **INFERRED:** these tables
are a small, special-purpose zone map (26 = 0x1A entries), not the general per-instrument
wave selector.

---

## 4. Emulation gap vs firmware behaviour — determination

**Firmware behaviour, not an emulation gap (task option c).** Grounded in §2 (tonerec,
partial-param data and resolver tables all present) and §3 (both wave paths bail on gates
that are legitimately clear for these voices; the resolver itself returns 0 when reached):

* No missing main→sub transfer — the payload is delivered and decoded (§2). MEASURED.
* No unmapped / mis-read ROM region — `table_data` (0x800000, IC1/IC3) and `custom_data`
  (0x300000, IC19) are mapped in `maincpu_mem`; their decoded voice parameters are in sub
  RAM. MEASURED (data present).
* No strap/config gate involved. MEASURED (transfer completes on the normal boot).
* The wave-number register +0x440 is **genuinely 0** for the KN5000's ordinary PCM voices.
  The instrument's real identity is the tonerec's partial-parameter records (§1), which the
  firmware programs into the pitch/zone register +0x040 (low nibble = multisample zone, per
  `kn5000-tonegen-register-semantics.md`) and the timbre registers +0x0C0/+0x140/+0x500 —
  exactly the per-instrument fingerprint `kn5000-wave-number.md` §2 measured. INFERRED
  (strong): the +0x440 "wave number" is a secondary/legacy selector, not the PCM-voice one.

This corroborates, from the delivery side, the wave-number note's predict-then-check MISS:
the wave index does not vary per instrument because for these voices it is not the mechanism.

---

## 5. Concrete fix proposal (NOT implemented) — with the evidence that redirects it

**Do NOT chase a "populate the tonerec field so the resolver emits a real wave" fix — the
evidence says it is a dead end:**

* Forcing the primary path by making `tonerec[+0x1a] != 0` does not help: Organ already takes
  that path and the resolved wave byte is still 0 (§3c). MEASURED (prior note).
* Forcing the fallback by setting `part_base[+0x0a]` bit15 would call `LABEL_033E02` +
  `LABEL_02177E`, but those validate against the 0x2126 table that demands `note == 0x1A`
  (§3c); for an ordinary C4 note-index they return the invalid/0 result. So +0x440 would
  stay ≈0 (at most the `tonerec[+0x1a]&0xC0` bank bits). Predicted outcome: **still not a
  real, instrument-dependent wave number.** INFERRED from the measured table contents.

**The fidelity-bearing lever is the tonerec's partial-parameter records, plus the missing
sample ROMs — evidenced:**

1. **Decode the partial-parameter records** the tonerec points at (`0x05xxxx`/`0x07xxxx`,
   §1) in the HLE. These carry the true per-partial multisample zone, envelope, filter and
   tuning that the firmware turns into the +0x040/+0x0C0/+0x140/+0x500 register writes. The
   shipped palette already keys off the resulting register fingerprint; a faithful model
   would read the source records directly. Expected observable: the multisample-zone nibble
   in reg +0x040 varies per instrument (it already does — `r1` high/low differ per
   instrument, `kn5000-wave-number.md` §2), while +0x440 legitimately stays 0.
2. **The literal PCM is in NO_DUMP IC304-306** (`kn5000.cpp` ROM warnings
   "kn5000_waveform_rom.ic304/305/306 NO GOOD DUMP KNOWN"). Until those chips are dumped, no
   amount of firmware-side work yields the true timbre — this is the actual blocker, not the
   wave-number transfer.

**What I would NOT change:** the shipped single-cycle timbre-palette
(`kn5000_tonegen.cpp`) is a reasonable stand-in given (1)+(2); this investigation confirms
its premise (wave 0 is real; select timbre from the firmware's real registers) and does not
justify a palette reversal. The palette reversal remains the owner's call and is out of
scope here.

---

## 6. Reproduction (all runtime-only; nothing committed but this note)

Isolated run, published binary, pre-init nvram (boots to play screen ≈ t=22s — earlier
key-presses land pre-boot on a black LCD and never reach note-on):
```
cp nvram/kn5000/nvram{1,2} <RUNDIR>/nvram/kn5000/
kn7000 kn5000 -rp roms -window -skip_gameinfo -debug -debugger none \
  -nvram_directory <RUNDIR>/nvram -autoboot_delay 0 -autoboot_script <lua> \
  -seconds_to_run 26          # press KEY2 mask 0x001 (C4) at t>=22
```
lua technique: `sub.debug:bpset(addr,"1","temp=temp+1; g")` for path counts;
`sub.spaces["program"]:read_u8/u16` for RAM dumps (frame-notifiers do NOT fire while a
halting breakpoint is stopped, and the debugger symbol `xwa` is rejected — read banked regs
`XWA0..3` from `device.state` or dereference RAM directly, which is what this pass did).

## 7. Open threads (honest)
* The exact semantics of `part_base[+0x0a]` bit15 and `tonerec[+0x1a]` as tone-class
  discriminators — inferred, not exhaustively proven; would confirm by capturing an Organ /
  drawbar voice (the class that sets them) and diffing.
* The partial-parameter record format at `0x05xxxx` (envelope/filter/zone field offsets) —
  the next concrete RE step for a faithful (non-palette) tonegen, gated ultimately on the
  IC304-306 dump.

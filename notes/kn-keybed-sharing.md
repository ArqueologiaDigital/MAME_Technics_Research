# Can the KN5000 and KN7000 keybed scanning share a `kn_keybed_base_device`?

Assessment date 2026-07-23. Paper design only — no src edited, no build run (two other
agents held the src/build tree). Mirrors the discipline of the tonegen/cpanel base
assessments. Verdict up front:

## VERDICT: (c) NOT WORTH IT — keep both keybeds inline; do NOT extract a base device.

The two keybeds share a *data convention* (61 keys, C2..C7, key 0 = MIDI 36, a 16-bit
`low=key / high=velocity` word) but almost no *code*, and the little code they have runs
through **structurally opposite mechanisms**. A base could only be made to fit by forcing
one model to change its input mechanism — a behaviour change, which is exactly what the
tonegen/cpanel bases did NOT have to do (those shared hundreds of lines of *proven byte-
identical* mechanism). Here the honest shared surface is ~5 lines of concept. This is the
"a clean 60-line share beats a forced 150-line share" case, resolved as: share nothing.

Scope note that makes this a *two-implementation* question, not a seven-model one:
**KN6000, KN6500, KN2400, KN2600 are all `kn7000_state` with INPUT `kn7000`** (SYST rows
kn7000.cpp:2300-2313 — all five list ioports `kn7000`). They already reuse the KN7000
keybed (kbd_push / kbd_key / the FIFO / the MIDI bridge / the KEYS0..3 bed) with **zero
duplication**. KN1500 is a TLCS-900 machine with no keybed HLE at all (grep: only
kn5000*.cpp and kn7000.cpp contain any keybed code). So the entire duplication in the tree
is exactly **KN5000 (kn5000.cpp / kn5000_state) vs the KN7000 family (kn7000.cpp)** — one
pair. A base would deduplicate one pair, at the cost below.

---

## Structural diff (MEASURED — line numbers cited)

| Aspect | KN5000 (kn5000.cpp) | KN7000 family (kn7000.cpp) | Shared? |
|---|---|---|---|
| Input mechanism | **Polled scan**: 1 ms `emu_timer` -> `keybed_scan()` reads 6 ioports, manual edge-detect vs `m_keybed_prev[61]` (L314-346, timer L633-634) | **Event-driven**: `PORT_CHANGED_MEMBER` per key -> `kbd_key()` INPUT_CHANGED (L1354-1357); MAME does the edge-detect | **NO — opposite paradigms** |
| Prev-state array | `m_keybed_prev[61]` (L204), save_item L623, reset fill L632/661 | none (MAME holds prior port state) | NO |
| ioport bed | `required_ioport_array<6> m_keybed` "KEY%u", **6 ports x 12 bits** (L169; ports L535-620); PORT_CODE only, **no PORT_GM_NOTE, no PORT_CHANGED** | 4 ports "KEYS%u" **16 bits** (L1528-1594); every key has **PORT_GM_NOTE + PORT_CHANGED_MEMBER**, KN_KEYPC adds PORT_CODE for the two middle octaves | NO — different tag/width/markup because the mechanisms differ |
| Note index | `raw_note = port*12 + bit`, 0..60 (L323) | `idx` passed as PORT_CHANGED param, 0x00..0x3C (L1529+) | Convention same (0..60, +36 = MIDI); origin differs |
| Base MIDI note | raw + 0x24 = 36 (L332) | idx + 36 (L482,504) | **Same (36)** |
| 16-bit word | note-on `(vel<<8)｜(raw｜0x80)` → **bit7 SET = make**; note-off `0xFF00｜raw` → **bit7 CLEAR, vel 0xFF** (L330/338) | note-on `(vel<<8)｜idx` → **bit7 CLEAR = make**; note-off `(0xFF<<8)｜(idx｜0x80)` → **bit7 SET, vel 0xFF** (L468, kbd_push; encoding at L1356/509) | **NO — bit7 make/break polarity is OPPOSITE** |
| Velocity | fixed `KEYBED_VELOCITY = 100` (L207); no velocity source | fixed `0x64` for PC keys (L1356) **+ real MIDI velocity via bridge** (L501/509) | Partial (both have a fixed bed; only KN7000 has a live source) |
| Push target | `m_tonegen->push_keybed_event(word)` → `std::queue` inside the **KN5000 tonegen device**, read back over MMIO **0x110000/0x110002** (kbd_data_r/kbd_status_r, kn5000_tonegen.cpp:236-255; mapped L375-376) | `m_kbd_fifo[64]` **in the driver**, read at **0x98050004** (L464-465, read L986-987) + `m_tonegen->key_context/key_break()` gate-follow coupling (L472-473) | **NO — different owner, address, and side-effects** |
| MIDI→keybed bridge | none (KN5000 MIDI IN goes to firmware SIO, kn5000.cpp L834+) | `kbd_midi_rx()` running-status parser + `m_kbd_midi_uart` device (L489-510, decls 486-488) | **NO — KN7000-only** |
| tonegen gate-follow | not called from keybed | `key_context`/`key_break` (base method kn_tonegen.h:134-135) called in kbd_push | KN7000-only |

MEASURED logic-line counts (excluding the ioport macro blocks, which cannot merge — see
below): KN5000 ≈ 43 lines (scan 33 + decls/timer/save/reset ≈ 10); KN7000 ≈ 42 lines
(kbd_push 9 + kbd_midi_rx ~25 + kbd_key 4 + FIFO decl/read 4). ioport blocks: KN5000 ≈ 86
lines, KN7000 ≈ 67 lines.

---

## Why the four "seams" the task hoped for do not line up

1. **Shared skeleton (scan → edge-detect → event).** INFERRED-then-CHECKED: the task
   premise assumed *both* edge-detect against a previous state. **They do not.** Only KN5000
   edge-detects (its own `m_keybed_prev` loop). The KN7000 has **no scan timer and no prev
   array** — MAME's `PORT_CHANGED_MEMBER` delivers make/break directly. The single largest
   candidate for sharing (the scan/edge-detect engine) **exists on exactly one of the two
   models**. There is nothing to factor out; there is one implementation, not two.

2. **Note/keycode mapping.** This is the *one* place they agree: both are a 61-key C2..C7
   compass with key 0 = MIDI 36. But agreement on a two-number convention (count 61, base
   36) does not need a class — it needs two constants, which each driver already spells
   locally. Reconcilable, but not worth a device to hold two integers.

3. **Velocity.** Both have a fixed-velocity bed (100 vs 0x64); only KN7000 has a live
   (MIDI) source. A base "supporting both" would carry the MIDI bridge that only one
   derived class ever uses — abstraction that pays rent on one side only.

4. **The push seam.** This *is* clean as a virtual — but it is also the **only** thing, and
   it is not a thin adapter over shared upstream code: the two sides differ in **owner**
   (tonegen queue vs driver FIFO), **address** (0x110000 vs 0x98050004), **make/break
   polarity** (bit7 opposite), and **side-effects** (KN7000 additionally drives
   key_context/key_break). When the only shared thing is the seam itself and everything
   feeding it diverges, the base is an empty shell.

---

## What a base WOULD force (the design that argues against itself)

To host a `kn_keybed_base_device` you would have it own the ioport bed + a
`virtual push_event(uint8_t idx, uint8_t vel, bool make) = 0` seam. But the bed can only be
owned once, so it must pick ONE mechanism:

* Pick **PORT_CHANGED + GM_NOTE** (the KN7000 bed): then **KN5000 must abandon its 1 ms
  scan timer**. That deletes the modeled IC303 scan latency that kn5000.cpp:313 explicitly
  documents ("matching real IC303 hardware scan rate"), renames KEY0..5→KEYS0..3, drops its
  PORT_CODE-only layout, and reroutes its output away from the tonegen `std::queue`/0x110000
  MMIO path its firmware reads. That is a **behaviour change on KN5000**, exactly what this
  refactor is forbidden to introduce.
* Pick **the polled 6×12 bed** (the KN5000 bed): then the KN7000 family loses PORT_CHANGED
  and gains a scan timer + prev array it never had — a behaviour change on five systems, and
  it strands the MIDI bridge (which is push-driven, not scanned).

Either way the base saves at most the ~70-90 ioport-macro lines of ONE model while forcing
the OTHER to change mechanism. Contrast the tonegen base (kn_tonegen.*, 227+230 lines of
mechanism proven *byte-identical* across chips — kn_tonegen.h header) and the cpanel base
(kn_cpanel.*, 125+278). Those shared the *mechanism*; here the mechanism is precisely what
differs. Forcing a base would be net-negative maintenance: a shell class plus a behaviour
regression to re-litigate.

---

## The constructive alternative (NOT part of this behaviour-preserving refactor)

If reducing divergence is later judged worthwhile, the low-risk move is **not** a shared
device but a **one-directional convergence of KN5000 onto the KN7000 pattern**, filed as its
own task with its own re-validation: give KN5000 a PORT_CHANGED + GM_NOTE bed and a driver
FIFO, matching kn7000.cpp. That would make a base trivial afterward — but it *is* a
behaviour change (loses the IC303 scan-latency model, changes the 0x110000 read contract)
and must be proven against the KN5000 firmware's keybed reader, so it cannot ride along
under a "preserve behaviour" banner. Recommendation: leave both inline until/unless that
convergence is independently done and validated. Do not build the base speculatively.

---

## If the executor nonetheless proceeds — mandatory A/B test + revert guard

(Stated for completeness, per the tonegen discipline. The verdict is *do not proceed*; this
is the gate that any attempt must pass, and it will expose the behaviour change above.)

**A/B test (run BEFORE and AFTER, diff must be empty):**
1. `./mame kn7000` with `-debug`; tap `0x98050004` reads (or LOG_KEYBED). Play **C4** (idx
   0x18 / KEYCODE_Z). Confirm the FIFO delivers `0x6418` on make and `0xFF98` on break —
   the exact words the pre-refactor build produced (keybed-fifo-makebreak.md §Verification).
   Confirm the TG still emits its note-on write (audible C4 = 262 Hz per the sound-subsystem
   memory).
2. `./mame kn5000` with `-debug`; tap `push_keybed_event`/0x110000. Play middle-C-octave
   key; confirm the tonegen queue receives note-on `(100<<8)|(raw|0x80)` and note-off
   `0xFF00|raw` **with KN5000's polarity unchanged**, and the IC303 read path at
   0x110000/0x110002 still returns them ready→data.
3. Repeat #1 across **kn6000, kn6500, kn2400, kn2600** (same kn7000_state) — the FIFO word
   for a played key must be byte-identical to pre-refactor.
4. `./mame -validate` must pass for **all seven** systems, and each must still boot to its
   normal screen.

**Revert guard:** if ANY of (the FIFO/queue word, the make/break polarity, the read
address/owner, the TG note-on write, a boot, or -validate) differs from the pre-refactor
capture on ANY of the seven systems, **revert the extraction entirely** — the keybeds go
back inline. There is no partial-credit landing: the value of a base here was never large
enough to justify shipping a behaviour delta.

---

## Bottom line
- **Shareable code, behaviour-preserving:** effectively none (~5 lines of shared *concept*:
  61 keys, base MIDI 36, a 16-bit key/velocity word).
- **Blockers to a base:** opposite make/break polarity, different push owner+address, one
  model polls while the other is event-driven, MIDI bridge on one side only, GM_NOTE on one
  side only. Unifying forces a mechanism/behaviour change on KN5000 (or on five KN7000-family
  systems).
- **Models a base would serve:** only KN5000 + the KN7000 family — and the KN7000 family
  *already* shares one implementation (all `kn7000_state`), so the base would dedupe exactly
  one pair. KN1500 has no keybed.
- **Recommendation:** keep both keybeds inline. Do not extract `kn_keybed_base_device`. If
  divergence must shrink, first converge KN5000 onto the KN7000 pattern as a separate,
  re-validated task; only then is a base cheap — and even then marginal.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>

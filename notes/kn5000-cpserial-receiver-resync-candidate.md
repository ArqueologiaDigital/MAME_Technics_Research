# CP-serial receiver resync (option B) — CANDIDATE, ADJUDICATED **INERT**, deliberately not landed

**Date:** 2026-07-21. **Companion patch:** `kn5000-cpserial-receiver-resync-candidate.patch`
(the exact change that was built and measured; applies to this tree).
**Repros:** `kn5000-cpserial-repros/` (deterministic, byte-identical across runs).
**Sibling adjudication:** `kn5000-cpserial-livelock-guard-candidate.{md,patch}` (option C).

This is **option B** of the three-option plan in
`KN7000/side-quests/findings/kn5000_button_mapping_findings.md`. It was implemented, built and put
through three independent verification passes (repro acceptance, no-regression, adversarial). It is
**not** in `src/` and **not** in `notes/upstream-patches/`, because it failed the acceptance bar in
the most awkward possible way: **it is a bit-for-bit no-op on every known repro.** The submission
hold on `kn5000-30` therefore **stays**.

## What it does

In `tmp94c241_serial_device::sioclk()`, remember the receive gate state seen at the previous rising
receive-clock edge, and on a **closed→open transition only**, restart the byte:

```cpp
const bool ext_clock = ((m_serial_mode & 0x03) == 0) && BIT(m_serial_control, 0);
if (ext_clock && !m_rx_gate_open)
{
    m_rx_clock_count = 8;
    m_rx_shift_register = 0;
}
m_rx_gate_open = ext_clock;
```

plus the `bool m_rx_gate_open` member, its `save_item`, and `m_rx_gate_open = false` in
`device_reset()`. 49 lines, 44 of them comment.

The `scNcr_w` hard constraint is satisfied **structurally and by measurement**: `m_rx_gate_open` is
a flip-flop sampled at rising edges, so the ISR's mid-byte `SC1CR` rewrite (IOC already 1) is an
open→open write and cannot trigger the reset. Instrumented: `wnop_open` (open→open register
rewrites) counted 331…5892 across runs while `resync` stayed 0. Zero false triggers, ever.

## Why it was written

`kn5000-30` (b17fb8b) gated the RX latch on the external clock, killing 521 phantom bytes. It also
created a **mid-byte gate-close race**: `m_rx_clock_count` is stranded at 1..7, the
`(m_rx_clock_count != 8)` term in `timer_callback`'s `need_clock` stays true forever, the internal
baud generator free-runs (1.4M–3.2M dead edges), those edges retrigger the cpanel's 50 µs sliding
idle detector faster than it can expire, INTA is never re-asserted, **the link is dead for the
session**. Option C removed the free-run but never restored framing (`ll_exit_clean = 0` across 342
strand exits), so B — restore the byte boundary — was supposed to be the step that actually fixes
the panel.

## ★ The finding: B never executes, because the wedge destroys its own precondition

This is a proof from the source, corroborated by measurement in three passes:

1. A strand means `m_rx_clock_count ∈ 1..7` with the gate shut.
2. `timer_callback` (line ~574) → `need_clock` contains `(m_rx_clock_count != 8)` → the baud
   generator free-runs forever.
3. `sioclk()` forwards every edge to the panel unconditionally (lines 137/256).
4. `kn5000_cpanel::sioclk()` (lines 464-467) re-arms its 50 µs idle timer on **every** edge while a
   TX is pending. The free-run period is 16–32 µs at every BRCR value the firmware uses
   (`ldio 0xd7` = 0x28/0x24/0x14 → 31250/62500/250000 Hz; the divisor is never 0, so the timer is
   never disabled).
5. → `idle_detect` never fires → no INTA → `INTA_HANDLER` never runs → `or 0xd5,0x01` (IOC=1) never
   executes → **the gate never reopens**.
6. B triggers only on closed→open. That transition never happens.

Measured corroboration in every wedged run: `wclose = wopen + 1`, `wclose_mid = 1..3`,
`wopen_mid = 0` — the mid-byte close is always the **last** gate event of the session.

**B is the cure and C is the key to the room.** Shipping B alone ships dead code.

## Measured results (empty nvram, one boot, screens read as PNGs)

Clean-B binary vs. the pre-change build, on the three deterministic repros:

| repro | pre-B | B | identical? | `resync` | `rx_final` | `tmr_dead` |
|---|---|---|---|---|---|---|
| `a1` | DEAD (0 px on 4 liveness presses) | DEAD | **bit-identical**, all 6 PNGs | 0 | 5 | 1,709,587 |
| `b1` | DEAD | DEAD | **bit-identical** | 0 | 7 | 1,430,763 |
| `b3` | DEAD | DEAD | **bit-identical** | 0 | 4 | 3,201,370 |
| `ph007` | DEAD | DEAD | **bit-identical** | 0 | 6 | 1,396,729 |
| `ph017` / `ph033` / `ph050` | LIVE, clean | LIVE, clean | **bit-identical** | 0 | 8 | 0 |
| `soak` (444 presses) | — | LIVE, clean | — | 0 | 8 | 0 |

Plus a 38-press two-panel-half playing session (45 snapshots, 191 emulated s): **all 45 PNGs
byte-identical** between the B build and the published `kn5000-30` build
(md5 `52818738929b4056179d115d8ca1ad7f`). Every counter matched digit for digit too.

**`exit_midbyte = 0` in the clean-B runs is VACUOUS, not a pass.** There is no strand *exit* to
classify because the gate never reopens. The honest numbers are `resync` (times B's body ran: 0)
and `rx_final_count` (5 / 7 / 4 / 6 — the receiver ends the session still misframed).

**Instrument-visibility proof (the kn5000-30 mistake, not repeated):** the same `resync` counter
reads **1** on `a1` and **3** on `b3` when option C is enabled alongside. It is not a blind zero.

## What makes B reachable — and the strictly better variant, B′

Two ways to give B a door to walk through:

* **B + C**: land the livelock guard too, so the free-run stops, INTA returns, the ISR sets IOC=1,
  and B's transition happens.
* **B′ — "hold in reset" (recommended over B+C if this route is ever taken)**: model RXE=0 holding
  the counter in reset for the **whole** shut window rather than releasing it at the reopen:

  ```cpp
  if (!ext_clock)
  {
      m_rx_clock_count = 8;
      m_rx_shift_register = 0;
  }
  ```
  at the same point in `sioclk()`. Then `(m_rx_clock_count != 8)` can never be true while the gate
  is shut, so **the free-run cannot start and C becomes unnecessary by construction** — one `if`,
  no second patch, no `m_rx_gate_open` member. Measured: B′ alone produces snapshot md5s
  **bit-identical to B+C** on `a1`, `b1` and `b3`; it satisfies the same `scNcr_w` constraint (it
  never acts while the gate is open) and is inert on healthy runs.

## ★ But B+C and B′ FAIL the acceptance bar too — reproducible counterexample on `b3`

The implementer measured only `a1`, where both variants look like a clean win (DISK → DISK MENU,
PIANO → the SOUND PIANO list with real names). The adversarial pass ran `b3` (220 presses, drifting
interval), and both variants reproduce **option C's rejection symptom**:

| `b3` | strands | `tmr_dead` | `PHASE_HIST` | what is on the screen |
|---|---|---|---|---|
| pre-B | 1 | 3,201,370 | 3:7 7:326 | frozen HOME, no transpose, tempo 120 — dead but coherent |
| **B′** | 3, all recovered, `rx_final=8` | 0 | **3:36 6:16** 7:982 | **phantom `<Db>` transpose on a FIRST boot from an empty nvram dir**; MENU:DISK and MENU:SOUND both dead; "LIVE PIANO" opens **LEFT / ORCHESTRAL PAD**; final HOME renders with blank PMEM/RHYTHM/tempo fields |
| **B+C** | 3 | 0 | 3:36 6:16 7:982 | **bit-identical to B′** — same six snapshot md5s |

Deterministic on repeat. Control: `soak` (444 presses, 4 emulated minutes, **zero** strands) is
perfectly clean — so it is not press count or press rate, it is **the strand recoveries**:
3 recovered strands ⇒ phantom transpose + false dispatch; 0 strands ⇒ perfect.

**Why:** a byte-boundary resync restores **bit** framing but not **packet** framing. Each strand
still *loses a whole panel byte*, which shifts the (header, state) pairing of the panel's 2-byte
packets — exactly the mechanism `kn5000-30`'s own comment blames for the phantom transpose. In
`b3`, 73 real panel-clocked bits (`drop_ext`) are still discarded, and no receiver-side change can
recover data that was never delivered. `b3`'s 52 off-phase byte starts (`PHASE_HIST` buckets 3 and
6) survive the resync.

**So the counters pass and the instrument still lies.** That is the same trade C was rejected for.

## Acceptance criteria, adjudicated

| # | criterion | verdict |
|---|---|---|
| 1 | the repros die (`a1`,`b1`,`b3` end with a LIVE panel, proven by pixel diff) | **FAIL 3/3** — all still dead, bit-identical to pre-change; positive control present (pre-B reproduces each failure) |
| 2 | framing actually resyncs; every strand exit CLEAN | **FAIL 3/3** — `resync = 0`, `rx_final ∈ {4,5,6,7}`; `exit_midbyte = 0` is vacuous (`wclose = wopen + 1`) |
| 3 | no false events | PASS **but vacuously** (B is inert). The reachable variants B+C / B′ **FAIL** it on `b3` |
| 4 | phantoms stay zero (`drop_int/8 == tx_bytes == cpanel_recv`) | **PASS** — exact on every live run (3777/3777/3777 on the playing session; 1085, 734, 2289 elsewhere); on wedged runs the identity is unmeasurable (dead edges inflate `drop_int`) and the valid substitute `latch == rise_ext − drop_ext` holds exactly |
| 5 | phase sweep, phase 0.33 bit-identical to pre-change | PASS, **vacuously** — all five phases are bit-identical, including the two that wedge |
| 6 | no collateral | **PASS** — `-validate` clean for kn5000/kn1500/kn7000/kn6000/kn6500/kn2400/kn2600 (0 errors, 0 warnings; bogus-driver positive control exits 5); KN7000 boots to its play screen; KN1500 identical to pre-change; sound names (kn5000-29) and tempo wheel (kn5000-25) intact (120→122→121→122) |

**Verdict: FAIL. Not landed.**

## Secondary finding: the faithfulness argument is wired to the wrong signal

The brief justifies B with *"on silicon RXE=0 holds the receive bit counter in reset"*. True — but
the emulated gate is **IOC**, not RXE, and the claim that the v10 firmware always moves the two
together is **false**. In `v10/maincpu/ui/cpanel_routines.s`, IOC is written **alone** at :220,
:238-239, :776, :810, :830, :846, :883, :928, :954-955, :1034-1035. In `INTA_HANDLER`, IOC is set at
:682 but RXE only at :686; on the way out, RXE is cleared at :662 and IOC at :663.

While the gate only *suppresses* latching, that skew is harmless. But B **changes the meaning of the
gate edge** from "resume" to "restart", so the IOC↔RXE skew becomes load-bearing: at 250 kHz a bit
is 4 µs and four instructions at 16 MHz is ~1–2 µs — a fraction of a bit time, inside the window
that decides whether a packet collides. **Therefore: if a receiver-side resync is ever landed, the
RXE gate (SC1MOD bit 5, currently unmodelled) must land before or with it, not as a cosmetic
follow-up afterwards.** (Disassembly warning: the inline comments at :99, :107 and :686 are stale
UART-era mislabels — "parity" / "parity addition". 0xd5 is SC1CR and 0xd6 is SC1MOD per
`sfr_tmp94c241.s:133-136`; the RXE annotations at :183/635/662/1027/1049/1149 are the consistent
ones.)

## Verdict and disposition

1. **Do not land B alone.** It is provably inert; landing it would lift a submission hold on the
   strength of a change that does nothing, add a `save_item` (invalidating existing savestates) for
   zero behaviour, and make the unmodelled IOC/RXE skew load-bearing.
2. **Do not land B+C or B′ on `a1`-only evidence.** Both reproduce option C's rejection symptom on
   `b3`: false button events, including a phantom `<Db>` on a first boot from empty NVRAM.
   Any future acceptance gate for this area **must include `b3`**.
3. **Go to option A** (`KN7000/side-quests/pending/kn5000_cpserial_sender_handshake.txt`). The
   residue that defeats every receiver-side variant is **loss**, not misframe: `drop_ext` real
   panel-clocked bits are discarded and cannot be reconstructed. A sender that re-arms instead of
   clocking while the CPU's receiver is shut never loses a byte, so there is nothing to resync.
4. **Keep B′ as the belt-and-braces to land *with* A**, where it should be measurably inert (no
   strands to recover) and is the right model of RXE holding the counter in reset. If it is not
   inert once A lands, A is incomplete.
5. `kn5000-30`'s **submission hold stays**.

## Correction to a shared artefact

Any file named `…/scratchpad/optC/kn7000_cleanC_backup` is **not** a pristine pre-change build
despite its name — its `a1` output is bit-identical to the option-C runs. The trustworthy
pre-change reference is the published `kn7000-emulator/kn7000`
(md5 `52818738929b4056179d115d8ca1ad7f`).

## Instrumentation worth rebuilding (it settled every question here)

The instrumented build is gone with its scratchpad, but its probes are the reason this pass is
conclusive. If this area is touched again, rebuild these:

* **`PHASE_HIST` — the non-tautological framing oracle.** The *sender's* own bit position
  (`kn5000_cpanel::m_tx_clock_count`) sampled at the instant the CPU *begins* assembling a byte.
  Intact framing = one bucket. C-only smeared it to `2:368`; B′/B+C keep 7 dominant but leave 52
  off-phase starts on `b3`. This is the probe that is not a tautology.
* **`RX_LAST` / `CPTX_LAST`** — last 64 bytes received vs. sent. Direct proof of rotation: under
  C-only the CPU read `10 80 10 00 …` where the panel sent `02 00 02 20 …`, a 3-bit rotation =
  exactly `8 − 5`.
* **`drop_int / tx_bytes / cpanel_recv`** — kn5000-30's phantom arithmetic (only valid on live runs;
  dead edges inflate `drop_int`).
* **`wclose / wopen / wnop_open`** — the gate seen at the *register write*, independent of the edge
  sampling, so it sees the hazard even with the fix disabled and proves the transition-only property.
* Note again that a `phantom` counter is a **tautology** in this build: `sioclk()` only latches when
  the gate is open, so "a byte latched with the gate shut" is impossible to count.

## Tree state at the time of writing

Reverted and proven: `git status --porcelain` shows no `src/` modification, `grep -rn
"m_rx_gate_open\|KN5B" src/` is empty, and the rebuilt binary is **byte-identical**
(md5 `52818738929b4056179d115d8ca1ad7f`) to the published host copy at `kn7000-emulator/kn7000`, so
the overlay, the build tree and the published binary all agree and `publish-binary.sh` had nothing
to do. `kn7000-emulator/nvram` was never touched; every run used an isolated empty nvram directory,
was `timeout`-wrapped, ran sequentially and rendered to a visible window.

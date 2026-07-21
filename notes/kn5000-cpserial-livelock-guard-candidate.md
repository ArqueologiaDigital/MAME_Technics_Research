# CP-serial livelock guard — CANDIDATE, ADJUDICATED **NOT READY**, deliberately not landed

> **Entry point for this whole investigation: `kn5000-cpserial-INDEX.md`.** Read it first if you are
> coming in cold — it carries the current state, and this document was written before options B and A
> were adjudicated, so its forward-looking recommendations are superseded.

**Date:** 2026-07-21. **Companion patch:** `kn5000-cpserial-livelock-guard-candidate.patch`
(applies cleanly to this tree; verified with `git apply --check`).

This is **option C** of the three-option plan recorded in
`KN7000/side-quests/findings/kn5000_button_mapping_findings.md`. It was implemented, built,
and put through three independent verification passes. It is **not** in `src/`, and it is
**not** in `notes/upstream-patches/`, because it failed the acceptance bar. This note exists
so the next person does not have to re-derive any of it.

## What it does

Qualifies the RX term in `tmp94c241_serial_device::timer_callback`'s `need_clock`:

```cpp
const bool rx_needs_internal_clock = (m_rx_clock_count != 8) && rx_latch_enabled();
```

plus a shared `rx_latch_enabled()` predicate in the header, used on both the `sioclk()` RX
gate and here.

## Why it was written

kn5000-30 (b17fb8b) gated the RX latch on the external clock, killing 521 phantom bytes. It
also created a **mid-byte gate-close race**: if the firmware clears IOC while the panel is
still shifting a byte in, `m_rx_clock_count` is stranded at 1..7, `(m_rx_clock_count != 8)`
is then permanently true, and the internal baud generator free-runs forever (measured
663,146 … 3,221,718 dead edges). Those dead edges retrigger the cpanel's 50 µs sliding idle
detector faster than it can expire, so INTA is never re-asserted and **the panel link is
dead for the rest of the session**.

## The structural fact everybody should know before touching this

`timer_callback` already returns early at `tmp94c241_serial.cpp:503` on

```cpp
if ((m_serial_mode & 3) == 0 && BIT(m_serial_control, 0)) return;
```

which is **character-for-character** the predicate `rx_latch_enabled()` wraps, and lines
504–551 are pure comment. So at the `need_clock` line `rx_latch_enabled()` is provably
`false` and `rx_needs_internal_clock` is a compile-time-constant `false`.

**Option C is therefore exactly equivalent to deleting the `(m_rx_clock_count != 8)` term.**
Three independent readers converged on this. Two consequences:

1. It is why C provably cannot truncate a TX byte or drop a command byte — the removed term
   could never advance RX anyway, and the TX terms are untouched. Measured: `tx_bytes ==
   cpanel recv` in 22/22 runs.
2. The candidate's header comment ("Single definition shared by `sioclk()`'s RX gate and by
   `timer_callback()`'s guard, so the two can never drift apart") is an **overclaim** and must
   be corrected before this is ever landed. The predicate that actually makes the term dead —
   the early return at line 503 — is still a *duplicated literal*, not `rx_latch_enabled()`.
   Two copies remain; the invariant is unenforced.

## Adjudication: FAILED, on two counts

### 1. It does not remove the wedge (reproducible counterexample)

C removes the **free-run** in every stranded case (cpanel edges 1.4 M–3.2 M → 16 k–33 k; the
panel queue always drains to 0; INTA keeps flowing). It does **not** always remove the
user-visible wedge. Config `b3` (220 presses on a drifting interval, natural — no forcing):
with the guard on, all four instrument-free pixel-liveness presses changed **0 pixels**. The
panel was dead for the rest of the session anyway, with `dead=3638` and `ll_worst=0.055 s` —
the guard barely had to act and the panel still died.

**There are two kill mechanisms, and C addresses only one.** Framing loss alone is sufficient
to kill the panel. "The wedge is rarer" is not the bar.

### 2. It does not produce a *recoverable* misframe — and the misframe is destructive

Across every stranded run, in all three verification passes: **`ll_exit_clean = 0`**. 239
strand exits in the skeptic's runs, 103 in the repro pass, **every single one**
`MIDBYTE-REOPEN`, with `rx_count` still stranded (4, 5, 6 or 7) at FINAL. A 106-second idle
soak does not resync it. The receiver never recovers framing on its own.

Because C keeps the link electrically alive while permanently misframed, real panel bytes are
decoded rotated and dispatched as **genuine button presses the user never made**. Measured on
the clean (non-instrumented) build, from freshly emptied NVRAM dirs — so *not* the unrelated
second-boot `<Db>` power-down-NMI defect:

| run | with the guard | pre-C, same input |
|---|---|---|
| `a1` | `♩=120 <Db>` phantom transpose + spurious RIGHT1/RIGHT2 OCTAVE popup | frozen play screen, **no transpose** |
| `a1soak` | `<D >` — the phantom transpose keeps *accumulating* | — |
| `b3` | `<G >` (+7 semitones) | **no transpose** |
| `b1` | MENU:DISK → ENTERTAINER; ORCHESTRAL PAD → STRINGS & VOCAL | — |

A second pass independently saw the same class: a DRUM KITS press opening the RIGHT1/RIGHT2
OCTAVE dialog, a JAZZ COMBO press triggering a **PANEL MEMORY recall** (tempo 120 → 80, all
three parts rewritten), and a `<B >` transpose on a fresh-NVRAM first boot.

`phantom = 0` throughout — C does **not** reintroduce phantom *bytes*. The false events come
from misframed *real* bytes. But "MENU:DISK opens ENTERTAINER" is the kn5000-30 bug's own
symptom description returning through a different mechanism, and it would read as a
regression of kn5000-30.

`b1` is the one that settles it: **6 presses during boot + 33 presses at 2 Hz** — ordinary
playing, not hammering. Felipe's ground truth ("the original KN5000 control panel does not
get corrupted by button presses during the boot sequence") is still violated after C.

**The trade C offers is: pre-C = link dead, machine inert but coherent; with C = link alive,
machine spontaneously recalls panel memories, changes tempo and transposes itself.** For an
instrument Felipe plays, that is the worse of the two.

## What C *did* prove (keep this — it is real, and B will want it)

- **Provably safe / inert when healthy.** `dead = 0` in all 13 healthy runs plus all 7 of the
  regression pass's runs. `GUARD` vs `NOGUARD` A/B is **pixel-identical** on the clean path
  (phase 0.33 bit-identical; 21/21 snapshots identical on the button-map sweep; 7/7 on S3).
- **TX integrity perfect**, 22/22 runs, including all four stranded ones.
- **The free-run really is gone** wherever it occurs, deterministically.
- Guard suppression fires **iff** a strand exists (`dead>0 ⟺ ll_enter>0`, 22/22).
- The phantom-byte suppression from kn5000-30 is exact and undisturbed: `drop_int / 8 ==
  tx_bytes == cpanel_recv` in every run (304/345/809/738/697/894), i.e. exactly one phantom
  prevented per command byte, zero leakage.
- Note the counter `phantom` is a **tautology** in this build — `sioclk()` only latches when
  `rx_latch_enabled()`, so "a byte latched with the gate shut" is structurally impossible to
  count. A zero from that probe is not evidence. The arithmetic above is the real evidence.

## Verdict and disposition

> **★ 2026-07-21, LATER THE SAME DAY — THE DISPOSITION BELOW IS SUPERSEDED. Both halves of it are
> now false.** It said: land C *with* option B. Since then B was built and measured to be a
> **bit-for-bit no-op** (the wedge destroys B's own precondition, so the resync never fires), and
> the reachable variants **B+C and B′ reproduce C's own rejection symptom on `b3`** — false button
> events, including a phantom `<Db>` on a first boot from an empty NVRAM. So "B actually restores
> framing" is wrong, and "C+B is a shippable pair" is wrong. Option A was then built and is a
> **regression** as well. **C remains REJECTED and is not part of any current plan.** The live
> candidate is **A′**:
> `KN7000/side-quests/pending/kn5000_cpserial_sender_handshake_prime.txt`. Current state for the
> whole arc: `kn5000-cpserial-INDEX.md`.
>
> **What is still true and worth taking from this document:** the *mechanism* (a mid-byte gate
> reopen strands `m_rx_clock_count`, the baud generator free-runs, its dead edges starve the
> cpanel's 50 µs sliding idle detector, INTA never returns); the **342 strand exits with
> `ll_exit_clean = 0`**, every one a `MIDBYTE-REOPEN`, which is the proof the receiver *never*
> recovers framing on its own; and the warning that a guard which keeps a permanently misframed
> link **alive** makes the instrument dispatch button presses nobody made.

**C is a guard, not a cure, and it must not ship — alone or paired.** ~~Land it *with* option B
(the closed→open receiver resync that actually restores framing), as a two-patch pair, or land B
first.~~ If it is ever landed at all, the comment must say plainly: *removes the free-running
clock; the misframe that follows is permanent and will dispatch false button events, including a
phantom transpose.*

Roadmap briefs: `KN7000/side-quests/pending/kn5000_cpserial_receiver_resync.txt` (B — **built,
INERT**), `KN7000/side-quests/pending/kn5000_cpserial_sender_handshake.txt` (A — **built,
REGRESSION**), and `KN7000/side-quests/pending/kn5000_cpserial_sender_handshake_prime.txt`
(**A′ — the live one, not started**).

## Tree state at the time of writing

Reverted and proven: `git status --porcelain` empty, `grep -rn "KN5CG" src/` empty, and the
rebuilt binary is **byte-identical** (md5 `52818738929b4056179d115d8ca1ad7f`) to the published
host copy at `kn7000-emulator/kn7000`. `kn7000-emulator/nvram` was never touched.

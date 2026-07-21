# CP-serial sender handshake (option A) — CANDIDATE, ADJUDICATED **REGRESSION**, not landed

**Date:** 2026-07-21. **Companion patch:** `kn5000-cpserial-sender-handshake-candidate.patch`
(528 lines, 6 files, +268/−11 — the exact change that was built and measured; applies to this tree).
**Repros:** `kn5000-cpserial-repros/` (deterministic, byte-identical across runs), including the two
new counterexamples `x_sim2.lua` and `pfx3.lua` that this pass added.
**Sibling adjudications:** `kn5000-cpserial-livelock-guard-candidate.{md,patch}` (option C, rejected),
`kn5000-cpserial-receiver-resync-candidate.{md,patch}` (option B, inert).

This is **option A** of the three-option plan in
`KN7000/side-quests/findings/kn5000_button_mapping_findings.md` — the *sender-side* handshake, the
one the plan called the fidelity endgame because it removes the loss instead of recovering from it.
It was implemented, built, verified three ways, and it is **not** in `src/` and **not** in
`notes/upstream-patches/`, because an adversarial pass found a **deterministic counterexample in
which A is worse than the build we ship**. The submission hold on `kn5000-30` therefore **stays**.

## What it does

Four rules, three of them uncontroversial:

1. **Fan out the receiver state.** `tmp94c241_serial_device` gains a `devcb_write_line
   m_rx_ready_cb`, plumbed exactly like the existing `m_tx_start_cb`, pushed from a new
   `update_rx_ready()` in `scNcr_w` / `scNmod_w` / `device_reset`. The predicate is the **AND**:
   ```cpp
   ((m_serial_mode & 0x03) == 0) && BIT(m_serial_control, 0) && BIT(m_serial_mode, 5)   // mode0 && IOC && RXE
   ```
   This was checked against the firmware, not assumed: **RXE (SC1MOD bit 5) is set at exactly one
   site in v10** (`or_sd8b_im 0xd6,0x20`, `cpanel_routines.s:686`, inside `INTA_HANDLER`) and
   cleared at `:99/:183/:635/:662/:1027/:1049/:1149`; IOC is written alone at eleven sites. On
   arming IOC comes first and RXE last, on teardown RXE goes first — so the AND brackets exactly
   the window in which a slave-clocked bit can survive. That part is right and is worth keeping.
2. **Re-arm instead of clocking** — `self_clock_callback` returns without moving SCLK while the
   receiver is closed (the 250 kHz timer is periodic, so returning *is* the retry).
3. **Hold the shift register on the CPU's own command clock** — a second loss path nobody had
   named: since `kn5000-30` the CPU does not latch while it is clocking a command out (IOC=0), so
   the panel's queued response bits were being shifted into a receiver that was not listening.
4. **Model the bus request** — `m_bus_request` drives PF.6 (`kn5000.cpp`: `portf_read` becomes
   `m_cpanel->sclk_level() ? 0x40 : 0x00`), which is what `CPanel_SM_StartTX:781-787` samples.

…and one rule added late, during the implementer's own tuning, which is where it all goes wrong:

5. **"Only ask for a bus that is free"** — `idle_detect_callback` defers the INTA request while the
   receiver is still armed (`kn5000_cpanel.cpp:1049-1055`, bounded at 250 × 20 µs):
   ```cpp
   if (m_cpu_rx_ready && m_idle_retries < CP_IDLE_MAX_RETRIES)
   { m_idle_retries++; m_idle_detect_timer->adjust(attotime::from_usec(20)); return; }
   ```
   It was added because without it the `a1` repro showed 5 mid-byte gate closes and with it, 0.

Plus liveness valves: a 500 µs stall → `abandon_inta_cycle()` (rewind the byte, re-run the
handshake) and a 100 ms hard deadline for a stall that happens *after* bits are already on the wire.

## ★ The finding: two deterministic regressions against the shipped build

Both were reproduced independently in the land phase, with byte-identical snapshot md5s, against
the pristine published binary (md5 `52818738929b4056179d115d8ca1ad7f`).

### 1. Two buttons pressed at the same instant kills the panel (`x_sim2.lua`)

PIANO (`CPR_SEG2 0x01`) + ORCHESTRAL PAD (`CPR_SEG1 0x02`) pressed **simultaneously**, held 0.12 s,
every 0.6 s, 20 times from t=30 s. No boot presses.

| build | liveness snapshots | verdict |
|---|---|---|
| pristine `52818738…` | `8c6ce9f5 8c6ce9f5 d553df01 8b22e7e7 046fb4d6 8c95cdb0` | **LIVE**, all four presses correct |
| clean A `9f851a4c…` | `7322ac60` ×6 | **DEAD** |

The dead machine is frozen on **ENTERTAINER → VOCAL REVERB, VOLUME : 84 selected, PANIC visible**,
with the ENTERTAINER LED lit — a page *neither pressed button can reach*. That is a **false button
dispatch**, i.e. the exact symptom class that got option C rejected, now produced by option A.

Counters (`X_sim2`): `strand_entry` 28 · `strand_exit_mid` **28 (100 % MIDBYTE-REOPEN)** ·
`rx_final` 6 · `PHASE_HIST` **`1:55 7:224` — two buckets** · `cp_abandon` 32 · `max_rearm`
**25 000 ticks = 100 ms** · 2.80 s of cumulative stall. On `x_multi` (8 buttons at once) it is worse:
`tmr_dead` **1 509 252** (the kn5000-30 free-run back at full strength), `cp_qmax` **466** (vs the
invariant 21 the design argued for), phantom arithmetic **BROKEN**.

### 2. Three presses from a cold boot turn a sound name into an error (`pfx3.lua`)

SPLIT POINT → EXIT → AUTO PLAY CHORD → EXIT → SPLIT POINT, then read the home screen:

| snapshot | pristine | clean A |
|---|---|---|
| home settled | `0e1f6502` | `0e1f6502` (identical) |
| AUTO PLAY CHORD | `cc44b8d8` / `ec5e144c` | identical |
| **SPLIT POINT with APC on** | **`521cfd38`** → `RIGHT1 Piano` | **`bfe7e4cb`** → `RIGHT1 Sound Name Error` |

Everything else on the screen — RIGHT2, LEFT, PMEM, rhythm, ♩=120, every LED — is identical; the
diff is the RIGHT1 name text alone. This is a `kn5000-29` regression, deterministic, three presses
from power-on.

★ **And every headline counter reads clean in that very run**: `drop_ext = 0`, `strand_entry = 0`,
`strand_exit_mid = 0`, `tmr_dead = 0`, `PHASE_HIST = 7:152` (single bucket), `cp_qmax = 21`,
phantom arithmetic HOLDS, `bprime_FIRED = 0`. The instrument built for option A cannot see option
A's own regression. Read that sentence again before trusting any counter in this area.

## ★ Root cause isolated to rule 5, in two independent configurations

The instrumented build carries a `KN5A_NOIDLEWAIT=1` knob that disables **only** the
`idle_detect_callback` deferral above. With it set:

| repro | A as built | A with rule 5 disabled |
|---|---|---|
| `x_sim2` | `7322ac60` ×6, DEAD, `strand_entry` 28 | `8c6c… d553… 8b22… 046f… 8c95…` = **the pristine screens**, `strand_entry` 0 |
| `pfx3` | `bfe7e4cb` "Sound Name Error" | **`521cfd38` "Piano"** = the pristine screen |

Mechanism, from the instrumented logs: deferring until `rdy` drops re-phases the INTA request to
fire *the instant the receiver closes* — which is the middle of `CPanel_SM_RXByteN`'s teardown
(`FC47C9`, `cpanel_routines.s:1027`), several instructions before the firmware is actually done.
The panel then holds mid-byte with `m_session_clocked == true`, so its deadline is the **100 ms**
one; `m_rx_clock_count != 8` keeps the internal baud generator free-running meanwhile; at 100 ms
`abandon_inta_cycle()` **rewinds a byte the CPU has already taken k bits of**; INTA re-arms with the
receive counter still stranded → misframed byte → teardown mid-byte again → **metronomic livelock at
100 ms**.

**A's escape hatch manufactures the very misframe the whole option was designed to avoid.** The
governing fact of this saga — *the residue is LOSS, not misframe* — is exactly what rule 5 plus the
`abandon` valve violate: they convert a stall into a restart of a byte that was already partly
delivered.

## Why the confirmatory verifications could not see it

* **`drop_ext == 0` is very nearly a TAUTOLOGY under A.** The counter increments on a non-timer
  rising edge arriving while `ext_clock = (mode==0 && IOC)` is false. Under A the panel emits an
  edge only when `IOC && RXE`, tested in the same callback with no CPU execution in between, so
  `receive_armed() ⟹ ext_clock` by construction. It reads 0 in every dead run above. A's
  acceptance criterion — "zero dropped panel-clocked edges" — is **unfalsifiable as written**.
* **`bprime_FIRED == 0` does not mean "A drops nothing".** In `X_sim2BP`, `bprime_calls = 2096`,
  `bprime_FIRED = 0`, in a run with 28 mid-byte strands and 28 MIDBYTE-REOPENs. B′ is structurally
  blind to this failure mode; its zero proves nothing about A's completeness.

The load-bearing numbers in this area are `strand_entry`, `strand_exit_mid`, the `PHASE_HIST`
bucket count, `tmr_dead`, `cp_qmax`, `max_rearm` — and, above everything, the pixel diff.

## What A genuinely does fix (recorded honestly)

* The **phase dependence is abolished**: `ph000/ph007/ph017/ph033/ph050` all produce byte-identical
  liveness screens under A (ph050 differs by a blinking caret), where the shipped build is DEAD on
  ph000 and DEAD-plus-false-ENTERTAINER on ph007.
* `a1`, `b1`, `b3` and the 444-press soak are all **LIVE** under A; all three are DEAD on the
  shipped build.
* Boot-window presses take effect and stop poisoning later packets (`bootwin.lua`: A is
  bit-identical to pristine, and the presses register).
* `-validate` rc=0 for kn5000, kn1500, kn7000, kn6000, kn6500, kn2400, kn2600; KN7000 and KN1500
  boot screens bit-identical to pristine.

So A moves the trigger and widens the working envelope — but it does not remove the fault, and where
it now hits, it hits harder (dead panel *and* false dispatch, where the shipped build was merely
correct).

## Route forward

1. **A′ = A without rule 5.** Two independent repros say the deferral is the whole regression, and
   with it disabled `x_sim2` and `pfx3` both return the pristine screens with `strand_entry = 0`.
   That is two data points, not a verification: rule 5 was added to remove `a1`'s 5 mid-byte closes,
   so A′ must be re-measured against the **whole** suite (a1/b1/b3/phase sweep/soak/x_sim2/x_multi/
   pfx3) before anyone believes it.
2. **The mid-byte teardown at `FC47C9` is untouched by any of this.** The CPU withdraws the grant
   between edges; a polite sender cannot see that coming. Either the panel must be able to finish a
   byte the CPU stopped listening to (receiver-side: hold the counter in reset — that is B′, still
   inert on its own), or the model of the teardown instant itself is wrong.
3. **Delete the `abandon_inta_cycle()` rewind, or guard it.** Re-sending bits already taken is the
   false-event generator. At minimum it must not run once `m_session_clocked` is true, and it must
   not run at all when `m_tx_clock_count == 0` with an empty queue (it currently would re-transmit a
   byte that was fully delivered).
4. **Do not re-add the INTA re-pulse while stalled.** The implementer tried it and it killed `b3`:
   `INTA_HandleCountdown:697-698` *decrements the firmware's receive-ring write pointer* on an
   unexpected INTA, parking the state machine in `CPanel_SM_RXByteN` forever.
5. Two latent hazards found by review, neither observed firing, both worth fixing whenever this
   file is next touched: `kn5000_cpanel_device::timer_callback()` still clocks SCLK unconditionally
   (dead today only because `set_baudrate()` is never called), and the `abandon` rewind above.

## Tree state at the time of writing

`git checkout -- src/` was run; `git status --porcelain` shows no `src/` modification and
`grep -rn "m_cpu_rx_ready\|m_bus_request\|KN5A" src/` is empty. The tree was rebuilt afterwards and
the resulting binary is **byte-identical** to the published host copy
(`kn7000-emulator/kn7000`, md5 `52818738929b4056179d115d8ca1ad7f`), so `publish-binary.sh` had
nothing to do. `kn7000-emulator/nvram` was never touched; every run used an isolated empty nvram
directory, was `timeout`-wrapped, ran sequentially and rendered to a visible window on `:0`.

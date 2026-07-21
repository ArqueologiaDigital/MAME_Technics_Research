# Measurement discipline for the KN5000 control-panel serial link

> **State of the investigation: `kn5000-cpserial-INDEX.md`.** That file says what is shipped, what is
> broken and what was rejected. **This file is the method** — how to verify a change to this link so
> that the verification is worth something. It is the most transferable thing the arc produced.

**Date:** 2026-07-21. Written after the third change in a row was cleared by instruments that could
not see the failure it introduced. Work on this link is **PAUSED at Felipe's request**; this note is
here so that whoever resumes does not have to rediscover why the previous three green boards were
worthless.

Companion files: `kn5000-cpserial-repros/README.md` (what to run and how),
`kn5000-cpserial-sender-handshake-instrumentation.patch` (the probes), and — for the evidence behind
every claim here — `KN7000/side-quests/findings/kn5000_button_mapping_findings.md`.

---

## The pattern, three times

| | the change | what its verification measured | what it actually did |
|---|---|---|---|
| 1 | `kn5000-30` (b17fb8b), shipped and blogged as a cure | phantom bytes **521 → 0**, `sent == received` | introduced a phase-dependent mid-byte strand that **kills the panel for the session** |
| 2 | option **C**, the livelock guard | the wedge gone in **4/4** swept phases | kept a permanently misframed link *alive*, so the instrument **dispatched button presses nobody made** |
| 3 | option **A**, the sender handshake | *"zero dropped panel-clocked edges, every configuration"* | a counter that **cannot increment under A**; it read 0 with the panel dead |

Each time the instrument was pointed at the property the author was thinking about, and each time
the defect lived somewhere the instrument was structurally unable to look. Felipe's hardware
testimony — a man looking at the screen of an instrument he plays — is what started the first two
corrections; the third came from an adversarial pass whose only job was to break the change, applying
that same testimony as its acceptance bar.

---

## The rules

### 1. Prove the instrument can SEE the failure before reporting its absence

A blind probe's zero is indistinguishable from a real one. Before a counter's `0` is allowed into a
verdict, show that same counter reading non-zero in a configuration where the event is known to
happen. Option B's pass did this correctly and it is the reason B's adjudication survived review:
`resync = 0` was only reported *after* the same counter had been shown reading **1** on `a1` and
**3** on `b3` with the guard enabled alongside.

### 2. The positive control is the published pre-change binary — nothing else

`/home/fsanches/compartilhado/kn7000-emulator/kn7000`, md5 **`52818738929b4056179d115d8ca1ad7f`**.
Every claim of the form "the candidate fixes X" needs the same schedule run on that binary in the
same pass, not a remembered result.

Two traps, both hit in this project:

* **`optC/kn7000_cleanC_backup` (or anything named `optC`) is the OPTION C BUILD.** Comparing a
  candidate against it yields a false PASS. Its `a1` output is bit-identical to the option-C runs.
* **A runtime "disable the fix" knob is not a pre-change control until it is validated as one.**
  The option-A instrumented build carries `KN5A_PRE=1`, which disables the panel-side rules and
  announces `MODE=PRE (option A DISABLED)`. On `a1` and `b3` it reproduced the pristine binary's
  screens exactly (`d9f02718`×6 and `f2b583c5`×6). **On `b1` it did not**: the pristine binary is
  DEAD (`f2b583c5`×6) and `KN5A_PRE=1` is **LIVE**, byte-identical to full option A
  (`a2a6784c a2a6784c f60cd095 fa5d8a38 046fb4d6 8c95cdb0` — run `optA/runs/PRE_b1` vs `pre_b1`).
  *Hypothesis, not established:* the knob gates the four panel-side sites but not the serial
  device's `rx_ready` fan-out, and in a race whose outcome turns on sub-bit-time phase even an
  otherwise inert addition can flip the result. **What would settle it:** re-run both twice to
  exclude nondeterminism, then bisect the ungated serial-side additions. Until then, use the knob to
  localise a mechanism, never to certify a baseline.

  (The *instrumentation* itself did test outcome-neutral where it was checked: `x_multi` and `x_sim2`
  give the same six snapshot md5s on the instrumented and the clean option-A build, and `x_sim2`
  repeated on the clean build is byte-identical. Neutral on three schedules is not neutral in
  general.)

### 3. A criterion that cannot fail is not a pass

Option A's headline acceptance criterion — **zero dropped panel-clocked edges** — is a tautology
under option A. The panel emits a clock edge only when `IOC && RXE`, tested in the same callback,
while the RX latch gate is the weaker `IOC` alone; `receive_armed()` therefore implies `ext_clock`
by construction and `drop_ext` cannot increment. It read a clean `0` in the run where the panel was
dead and the machine was sitting on a page neither pressed button can reach.

The older sibling of the same mistake: the `phantom` counter is a tautology *in every build since
kn5000-30* — `sioclk()` only latches when the gate is open, so "a byte latched with the gate shut"
is structurally impossible to count. The load-bearing evidence for that property is the arithmetic
**`drop_int / 8 == tx_bytes == cpanel_recv`**, exact on every live run, and it is only meaningful on
a live run: dead edges inflate `drop_int`.

**Before celebrating a green number, write down what would have made it red, and confirm that case
was actually run.**

### 4. A vacuous pass — one that passes only because the change is inert — is not a pass

Two of option B's six acceptance criteria passed **only** vacuously — "no false events" (B is a
no-op, so of course there are none) and "phase 0.33 bit-identical" (all five phases were
bit-identical, *including the two that wedge*) — and a third vacuity was caught inside a FAIL:
`exit_midbyte = 0` classifies nothing when there is no reopen, so "every strand exit was clean"
would have been precisely the counter-driven false clearance that let kn5000-30 ship. Score vacuity
explicitly, in the same column as the verdict. B's own adjudication did this, and that is why it is
trustworthy.

### 5. Liveness is a PIXEL DIFF, never a counter

Every repro ends with the same four liveness presses (`MENU:DISK`, `MENU:SOUND`, `PIANO`,
`ORCHPAD`) around six snapshots. **If the PNGs are byte-identical, the panel is dead**, whatever the
log says. Option C looked healthy on every counter it had while the panel was dead. Option A's
`pfx3` run reports `drop_ext = 0`, `strand_entry = 0`, `strand_exit_mid = 0`, `tmr_dead = 0`,
`PHASE_HIST 7:152` (single bucket), `cp_qmax = 21`, phantom arithmetic HOLDS and `bprime_FIRED = 0`
— a clean sweep on a build you can watch render `RIGHT1 Sound Name Error` where the shipped build
renders `RIGHT1 Piano`.

And read the *content*, not only the diff: a link that is alive but misframed dispatches events
nobody generated. Under option C, `b1` had `MENU:DISK` opening ENTERTAINER and ORCHESTRAL PAD
opening STRINGS & VOCAL; `a1` grew a phantom `<Db>` transpose and `b3` a `<G >`; and a second pass,
from a different press set, saw a JAZZ COMBO press trigger a **PANEL MEMORY recall** that rewrote
all three parts and moved the tempo from 120 to 80. "Different from the dead frame" is not "right".

### 6. Measure what the change BROKE, not what it fixed

`kn5000-30` is correct about everything it claims and still should not have shipped as a cure. The
missing question is always the same: *what could this change make worse, and did we run that?* In
practice that means the candidate must be run on schedules the **shipped build handles correctly**,
not only on the ones it fails — which is what turned up option A's two counterexamples.

### 7. A proxy diagnostic must itself be validated — the B′ check was blind, and that was ours

The B′-inertness diagnostic ("if option A is complete, the receiver-side resync B′ should never
fire") was **proposed in this project by the main agent as a sharp self-check for A. It is not
one.** Measured in `x_sim2` on the A+B′ build: `bprime_calls = 2096`, `bprime_FIRED = 0` — in a run
containing **28 mid-byte strands and 28 MIDBYTE-REOPENs**, with the panel dead. B′ is structurally
incapable of seeing the sender-side failure mode, so its zero proves nothing. Recorded plainly
because naming our own errors is why this record is worth reading.

A proxy is only evidence if you can state the failure it would catch *and* demonstrate it catching
one.

### 8. Felipe's hardware testimony outranks anything measured here

> "the original KN5000 control panel does not get corrupted by button presses during the boot
> sequence."

He owns and plays a real KN5000 and has been right **3/3** against confident, well-instrumented
wrong analyses in this project. Therefore the wedge is an **emulation bug**, and *"it is faithful
hardware behaviour"* is not an admissible conclusion. A candidate that ends in "the real machine
probably does this too" has failed, not passed.

---

## The probe catalogue

Rebuild these with `kn5000-cpserial-sender-handshake-instrumentation.patch` (apply the option-A
candidate patch first). They print one `KN5A| ...` summary block per run at `device_stop()`.

**Trustworthy — these can be embarrassed:**

| probe | what it is | why it cannot be satisfied by construction |
|---|---|---|
| `PHASE_HIST` | the *sender's* own bit position (`m_tx_clock_count`) sampled when the CPU **begins** assembling a byte | intact framing = ONE bucket; it is sampled on the panel's side of the link, so no receiver-side change can force it |
| `strand_entry` / `strand_exit_mid` / `strand_exit_cln` | the receive gate sampled at the **register write**, not at an edge | sees the hazard even with the fix disabled; `wclose = wopen + 1` is the signature of a wedged session |
| `tmr_dead` | free-running baud-generator edges | kn5000-30's livelock signature; `x_multi` under A: 1,509,252 |
| `cp_qmax` | deepest the panel's TX queue got | A's design argued it could not exceed 21; `x_multi` reached **466** |
| `max_rearm` | longest single wait for the bus grant (4 µs ticks) | |
| `cp_hold` | falling edges where the panel held its shift register because the receiver was shut | 7,424–10,224 real bits per run that the shipped build silently destroys |
| **the pixel diff** | six snapshot PNGs per run | the only instrument a human can check against a photograph of the real machine |

**Not trustworthy as written:**

| probe | why |
|---|---|
| `drop_ext` | tautology under option A (rule 3). Its own summary label still says *"must be 0 under A"* — that label is wrong; fix it before reusing the patch. |
| `phantom` | tautology in every build since kn5000-30 |
| `bprime_calls` / `bprime_FIRED` | blind to the sender-side failure mode (rule 7). Its label says *"must be 0 (else A incomplete)"* — also wrong. |
| `b_lat_int` (option-C era) | `timer_callback` returns early whenever `ext_clock` is true, so an internally-clocked edge can never reach the latch |
| `exit_midbyte` under a receiver-side change | vacuous when there is no reopen to classify |

`drop_int / tx_bytes / cpanel_recv` is trustworthy **only on a live run**. Under option A it reads
`BROKEN` on `x_multi` and `x_flood` (both degenerate runs) and also on `x_boot` (a run with zero
strands and a single-bucket histogram) — that last combination is unexplained and is a reason to
treat the arithmetic as a corroborating check, not a gate criterion.

---

## The gate template for the next candidate (A′ or anything else)

1. **Build two binaries and keep both:** the candidate, and the instrumented superset. Record md5s.
2. **Run the whole suite on the published pristine binary first**, in the same pass, on this box.
   Never carry a baseline over from a previous session's notes.
3. **Suite:** `a1`, `b1` (= `ph000`), **`b3`**, `ph007`, `ph017`, `ph033`, `ph050`, `soak`,
   `a1soak`, `bootwin`, `s4`, **`x_sim2`**, `x_multi`, **`pfx3`**. `b3` is mandatory: `a1` alone
   passes variants that `b3` kills. `x_sim2` and `pfx3` are mandatory: they are configurations the
   **shipped build handles correctly** and option A broke.
4. **Judge on the pixel diff first.** Only then look at counters, and only the trustworthy ones.
5. **Score vacuity in the verdict column.** "PASS (vacuous)" is not a pass.
6. **Delete the tautological criteria from the acceptance list** — `drop_ext == 0` and
   `bprime_FIRED == 0` above all.
7. **Run at least one schedule the shipped build handles perfectly**, and one adversarial schedule
   nobody has run before. Every variant that failed in this arc passed the short repro first.
8. **Regression-check the neighbours**: `-validate` for all seven Technics systems (a bogus driver
   must exit 5, otherwise the check itself is vacuous), KN7000 and KN1500 boot screens,
   kn5000-29 sound names (`pfx3` covers this) and the kn5000-25 tempo wheel.
9. **Revert and prove it**: `git status --porcelain` empty, a targeted `grep -rn` for the
   candidate's own identifiers empty, and the rebuilt binary byte-identical to the published one.

---

## Two things that are not measurement problems, recorded here so they are not misdiagnosed as one

* **A second boot against a reused nvram directory grows a spurious `<Db>` transpose** with no input
  at all. That is an unrelated power-down/NVRAM-ordering defect (the same one that blocks the splash
  quest), not the serial link. Always use an empty private nvram directory; the workaround for a
  normal session is `rm -f nvram/kn5000/nvram2` (not the whole directory). Never attribute a
  second-boot `<Db>` to this link.
* **The residue is LOSS, not misframe.** A byte the receiver never got cannot be reconstructed by
  any receiver-side change: a resync restores *bit* framing while leaving *packet* framing — the
  (header, state) pairing — shifted. This is not a measurement rule, it is the fact that killed the
  entire receiver-side family, and any new candidate should be checked against it before it is
  built.

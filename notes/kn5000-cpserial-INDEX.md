# KN5000 control-panel serial — INDEX / entry point

**Read this first.** The investigation behind it spans a 1,150-line findings doc, three candidate
`.md`/`.patch` pairs, 15 deterministic repro scripts, five briefs and five blog posts. This file is
a map and a state snapshot, not a retelling: every claim below is developed somewhere else, and the
pointer is given. Nothing here is new evidence.

**Date of this snapshot: 2026-07-21.**
**★ WORK IS PAUSED AT FELIPE'S REQUEST** ("Let's stop for now. Make sure you save documentation of
everything we discovered so far."). The next candidate (A′) is **defined but not started** — its
brief is `KN7000/side-quests/pending/kn5000_cpserial_sender_handshake_prime.txt`. Do not build it on
a cron tick or an idle-time pass without Felipe saying go.

---

## The state, in one paragraph

`kn5000-30` (commit **b17fb8b**, *"gate CP-serial RX on the external clock"*) is **shipped in our
tree** and is **correct about what it fixes**: it removed 521 phantom RX bytes per run and with them
the scrambled button mapping Felipe originally reported. It is also **incomplete, and it introduced
a regression of its own**: the RX gate can reopen *mid-byte*, stranding `m_rx_clock_count`, so
`need_clock` stays true, the internal baud generator free-runs, its dead edges keep retriggering the
cpanel's 50 µs sliding idle detector faster than it can expire, INTA is never re-asserted, and **the
panel link dies for the rest of the session**. Before the fix the counter self-cleared within eight
edges; the net trade is *521 phantoms that always scrambled but always self-healed* for *zero
phantoms plus a phase-dependent session-killer*. `kn5000-30` is therefore under **⛔ SUBMISSION
HOLD**, reaffirmed three times. **Three completion candidates were built, verified three ways each,
and all three were rejected** — C (livelock guard) is a guard that keeps a permanently misframed
link alive and makes the instrument dispatch button presses nobody made; B (receiver resync) is a
bit-for-bit no-op because the wedge destroys its own precondition; A (sender handshake) fixes every
previously known repro and then loses to the shipped build on two deterministic schedules, one of
them three presses long. **Next = A′ = A minus its late "only ask for a bus that is free" deferral
(rule 5) and minus/guarding the `abandon_inta_cycle()` rewind.** Two half-measurements say A′ works;
that is two data points, not a verification.

---

## Two separate bugs. Do not merge them.

1. **The CP-serial bug** (this index): phantom bytes → *fixed*; mid-byte gate-close wedge → *open*.
2. **The second-boot `<Db>` transpose** — **UNRELATED**. A *virgin* NVRAM grows `<Db>` on its own
   **second** boot with **zero input**. Leading hypothesis, **not proved**: MAME's exit path calls
   `eat_all_cycles()` before `nvram_save()`, so the firmware's power-down transaction never runs and
   the saved SRAM is a mid-life snapshot that restores as transpose +1. **This is the same defect as
   the scheduled splash-animation quest** (`KN7000/side-quests/pending/kn5000_splash_animation.txt`).
   Workaround: `rm -f nvram/kn5000/nvram2` before launch (**not** the whole dir). What would settle
   it: instrument the power-down transaction and show it does/does not execute before the save.
   **Never attribute a second-boot `<Db>` to the serial link.** Detail: findings doc, the
   "ADDENDUM: I am still seeing `<Db>`" section; blog Part 72.

---

## The governing insight (why an entire family of fixes is dead)

**THE RESIDUE IS LOSS, NOT MISFRAME.**

A byte the receiver never got cannot be reconstructed by *any* receiver-side change. A resync
restores **bit** framing while leaving **packet** framing — the (header, state) pairing the panel
protocol depends on — shifted. That single fact killed the whole receiver-side family (B, B′, and
C's "keep it alive and it will recover" premise), and it is also what option A violated in its own
liveness valve: `abandon_inta_cycle()` rewinds a byte the CPU has *already taken k bits of*, i.e. it
converts a stall into a restart of a partly-delivered byte and **manufactures the very misframe A
existed to prevent**.

Any future candidate must be judged against this first: *does it prevent the loss, or does it try to
recover from it?*

---

## The four candidates, with causes of death

| | what it is | verdict | one-line cause of death | adjudication |
|---|---|---|---|---|
| **C** | livelock guard — stop the baud generator free-running while stranded | **REJECTED** | removes the free-run but **not the wedge**, and by keeping a permanently misframed link *alive* it makes the instrument dispatch **false button presses nobody made** (phantom transposes, an unrequested PANEL MEMORY recall changing tempo 120→80, MENU:DISK opening ENTERTAINER). `ll_exit_clean = 0` across **342** strand exits (239 + 103), every one `MIDBYTE-REOPEN`. | `kn5000-cpserial-livelock-guard-candidate.{md,patch}` |
| **B** | receiver resync on the closed→open gate transition | **INERT** | a **bit-for-bit no-op**: the wedge destroys B's own precondition — after a strand INTA never returns, the ISR never sets IOC=1, so the closed→open transition never happens. `wclose = wopen + 1` in every wedged run. | `kn5000-cpserial-receiver-resync-candidate.{md,patch}` |
| **B′** | B, made reachable (hold the counter in reset for the whole shut window) | **not landable alone** | the right receiver-side *model*, but it recovers from loss instead of preventing it; its reachable variants still dispatch false presses on `b3`. **Also structurally blind to A's failure mode** — see the measurement rules. | same doc, §"What makes B reachable" |
| **A** | sender-side handshake (polite sender + modelled PF.6 bus request) | **REGRESSION** | its late rule-5 deferral re-phases the INTA request into the middle of `CPanel_SM_RXByteN`'s teardown; the panel holds mid-byte on the 100 ms deadline and `abandon_inta_cycle()` rewinds a partly-taken byte. `x_sim2` LIVE→**DEAD + false ENTERTAINER dispatch**; `pfx3` `RIGHT1 Piano`→**`RIGHT1 Sound Name Error`** (kn5000-29 regression). | `kn5000-cpserial-sender-handshake-candidate.{md,patch}` |
| **A′** | A minus rule 5, minus/guarding the abandon-rewind | **NOT STARTED** | — | brief: `KN7000/side-quests/pending/kn5000_cpserial_sender_handshake_prime.txt`; design: the A candidate doc §"Route forward" |

All three `.patch` files were verified `git apply --check` clean against HEAD on 2026-07-21.

### Worth KEEPING from A (do not throw it away and start over)

* The **`IOC && RXE` fan-out** from `tmp94c241_serial` to the cpanel HLE — a real fidelity gain,
  checked against the firmware rather than assumed.
* The **shift-register hold** on the CPU's own command clock — `cp_hold` shows **7,424–10,224 real
  bits per run** that the shipped build destroys.
* The **PF.6 bus request** (`m_bus_request` → `portf_read`), which is what `CPanel_SM_StartTX:781-787`
  actually samples.
* Under A the phase dependence is *abolished* and `a1`/`b1`/`b3`/the 444-press soak all go DEAD→LIVE.

### NEVER re-add

* **The INTA re-pulse while stalled.** It kills `b3`: `INTA_HandleCountdown:697-698` *decrements the
  firmware's receive-ring write pointer* on an unexpected INTA, parking the state machine in
  `CPanel_SM_RXByteN` forever.

### The open question nothing has touched

**The CPU tears its receiver down MID-BYTE, BETWEEN EDGES, at `FC47C9`** (`cpanel_routines.s:1027`).
No polite sender can see that coming. Either the panel must be able to finish a byte the CPU stopped
listening to (receiver-side: hold the counter for the whole shut window — that is B′, inert alone),
or **our model of *when* the teardown happens is wrong**. That is the next real question, and it is
untouched by C, B and A alike.

---

## The measurement rules this investigation learned the hard way

**A counter reading healthy while the screen visibly regresses has now happened THREE times.**
`kn5000-30` measured what it fixed and never what it broke. Option C passed two confirmatory reviews
and died to a skeptic. Option A's headline number read a clean zero with the panel dead.

* **Liveness is a PIXEL DIFF.** If the liveness snapshot PNGs are byte-identical, the panel is dead,
  no matter what any counter says. Never infer screen state from the log.
* **`b3` is MANDATORY in any acceptance gate.** `a1` alone passes variants that `b3` kills. The
  minimum honest gate is a1 / b1 / b3 / the ph000–ph050 phase sweep / soak / `x_sim2` / `x_multi` /
  `pfx3`, scored on pixels.
* **The `phantom` counter is a TAUTOLOGY post-kn5000-30.** The load-bearing evidence is the
  arithmetic **`drop_int / 8 == tx_bytes == cpanel_recv`**.
* **`drop_ext == 0` is a TAUTOLOGY under option A.** The panel emits an edge only when `IOC && RXE`,
  tested in the same callback, while the RX latch gate is the weaker `IOC` alone — so it cannot
  increment. It read 0 in runs where the panel was dead and dispatching false presses. A's stated
  acceptance criterion was **unfalsifiable as written**; delete it from any successor's gate.
* **`bprime_FIRED == 0` is BLIND, and that was the main agent's error.** B′-inertness was proposed
  in this project as a sharp self-check for A; it is not one. Measured: `bprime_calls = 2096`,
  `bprime_FIRED = 0` in an A run containing **28 mid-byte strands and 28 MIDBYTE-REOPENs**. B′ is
  structurally incapable of seeing the sender-side failure mode. Recorded honestly because that is
  the norm here.
* **Prove the instrument can SEE the event before reporting its absence.** A blind probe's zero looks
  exactly like a real one. That mistake is what let `kn5000-30` ship as a cure and what nearly landed
  option C.
* **Prefer** `strand_entry`, `strand_exit_mid`, the `PHASE_HIST` bucket count, `tmr_dead`, `cp_qmax`,
  `max_rearm` — and above all the pixel diff.
* **The S1–S5 scenario table is INDICATIVE ONLY.** Two later passes could not reproduce S3/S4 as
  tabulated and the press sets were never captured. It appears in blog Part 73 as if settled; it is
  not a regression suite. `notes/kn5000-cpserial-repros/` is.
* **RXE vs IOC.** The receiver-resync brief's premise — "the firmware moves them together" — is
  **FALSIFIED**: `cpanel_routines.s` writes IOC **alone at eleven sites**, so the skew is
  load-bearing and **RXE must come first**. RXE is set at exactly one site (`:686`) and cleared at
  seven (`:99/:183/:635/:662/:1027/:1049/:1149`). The disassembly's "parity" comments at
  `:99/:107/:686` are **stale UART-mode mislabels**; the RXE annotations at
  `:183/635/662/1027/1049/1149` are the consistent ones.
* **Hygiene for every run:** `-skip_gameinfo`, a visible `-window` on `:0` (never `-video none`), an
  **empty private nvram dir**, `timeout`-wrapped, run sequentially (8 cores; fanning out MAME makes
  the box unusable). Boot completes at ~20 emulated s; a settled fresh boot shows **no transpose box**.

---

## Felipe's ground truth — it outranks anything measured here

> "the original KN5000 control panel does not get corrupted by button presses during the boot
> sequence."

Felipe owns and plays a real KN5000 and has been right **3/3** against confident, well-instrumented
wrong analyses in this project. Therefore **the wedge is an EMULATION BUG**, and *"it is faithful
hardware behaviour"* is **not an admissible conclusion**. Any candidate that ends in "the real
machine probably does this too" has failed, not passed.

---

## The map — what to read, and when

### Start here (in this order, and usually you can stop after 2)

| # | file | read it when |
|---|---|---|
| 1 | **this file** | orienting cold |
| 2 | `KN7000/side-quests/findings/kn5000_button_mapping_findings.md` (~1,150 lines) | you need the evidence. **Six chronological sections**: root cause → kn5000-30 fix → the `<Db>` addendum → the dropped-byte test → option C → option B → option A. **Its TL;DR at lines 9–26 is the FIRST pass's conclusion** and predates everything above; read the section headers before believing any single passage. |
| 3 | `notes/kn5000-cpserial-sender-handshake-candidate.md` | you are about to implement A′. This is the most current candidate doc and contains the A′ definition, the FC47C9 question, the tautology and blindness notes, and the route forward. |

### Candidates (each `.md` = adjudication, each `.patch` = the exact build)

* `notes/kn5000-cpserial-livelock-guard-candidate.{md,patch}` — **option C**. Rejected. ⚠ Its
  "verdict and disposition" still recommends landing C *with* B; both halves of that are now false
  (B is inert; B+C/B′ reproduce C's own false-dispatch symptom on `b3`). Read it for the mechanism
  and the 342-strand-exit measurement, not for its recommendation.
* `notes/kn5000-cpserial-receiver-resync-candidate.{md,patch}` — **option B**. Inert. ⚠ Its §3 says
  "go to option A" (A has since been built and rejected) and its §4 recommends the **B′-inertness
  diagnostic, which is invalid** (see the measurement rules). Read it for *why* the wedge is
  unreachable from the receiver side, and for its instrumentation section — which is the pattern the
  A instrumentation should follow.
* `notes/kn5000-cpserial-sender-handshake-candidate.{md,patch}` — **option A**. Regression. Current
  and accurate. ⚠ The `.patch` is the **clean** build; the measurements came from an instrumented
  superset carrying the `KN5A_NOIDLEWAIT=1` knob.

### Repros — the real regression suite

`notes/kn5000-cpserial-repros/` — 15 lua schedules + `gen.py` + `run.sh` + a README that encodes the
method rules. Deterministic: repeat runs produce byte-identical snapshot PNGs.

* Wedge repros: `a1` (90 presses), `b1` = `ph000` (ordinary playing), `b3` (220 presses, drifting
  interval — **the mandatory one**), `ph007`.
* Controls: `ph017` / `ph033` (bit-identity control) / `ph050` clean; `soak` (444 presses) clean;
  `a1soak` (never resynchronises on its own).
* **Candidate-killers** added by the A pass: `x_sim2` (two buttons at the same instant), `pfx3`
  (three presses from cold boot), `x_multi` (8 simultaneous), plus `bootwin` and `s4`.
* Simultaneous-press schedules must `table.sort` their action list — otherwise later buttons of a
  group are pressed and released inside one dispatch, invisibly to the panel's 2-scan / 14 ms filter.

### Briefs (the task queue)

`KN7000/side-quests/pending/`

* **`kn5000_cpserial_sender_handshake_prime.txt`** — **A′, the live candidate**, written to be picked
  up cold. Nothing in it has been built. This is the brief to read if the work resumes.
* `kn5000_cpserial_sender_handshake.txt` — option A: the historical record of a rejected approach.
  ⚠ Its `kn5000_cpanel.cpp:1049-1055` citations are **option-A-build line numbers** (see below).
* `kn5000_cpserial_receiver_resync.txt` — option B. Its inner `★★★ STATUS` block is superseded by
  the `★★★★ UPDATE` block at the top; read the top block first.
* `kn5000_splash_animation.txt` — **same shutdown-ordering defect as the second-boot `<Db>`**.
* `kn5000_sound_name_error_long_session.txt` — separate, current, unrelated to the wedge.
* Index of all of them: `KN7000/side-quests/README.md`.

### Upstream

`notes/upstream-patches/README.md` — the kn5000 series. The **⛔ SUBMISSION HOLD on kn5000-30** is
recorded in three places (section header ~line 105, the patch's table row ~line 235, and the PR-split
list). The patch itself is `notes/upstream-patches/kn5000-30-cpserial-rx-phantom-byte-gate.patch`.
**Do not submit kn5000-30 alone**: it would export a worse bug than it fixes, and mainline's PR5
KN5000 panel almost certainly has the original phantom bug too.

### Blog (the public narrative, `~/compartilhado/mame-blog`, device `kn7000`)

| part | title | covers |
|---|---|---|
| 71 | The buttons that hallucinated | the phantom-byte root cause and kn5000-30. **Carries two errata**; the second one's prescription (option B) was later proven inert. |
| 72 | The tell that belonged to another bug | the `<Db>` is a separate power-down defect. ⚠ Contains a falsified claim that the driver "already carries" a checksum write tap — it was **removed** in `b1cf7db` (kn5000-29); only a stale comment survives. Its byte-loss *location* claim is also falsified (see Part 73). |
| 73 | The trade nobody priced | the wedge, and the trade kn5000-30 makes. ⚠ Presents S1–S5 as settled, and forecasts option B as the fix. |
| 74 | The fix that never ran | option B is inert. Current. |
| 75 | The counter that could not fail | option A's regression and the tautological counter. Current; closes by promising a Part 76. |

### Live status

`notes/AUTONOMOUS-STATUS.md` — latest tick has the full option-A adjudication. **Its "NEXT = A′" is
not an instruction to proceed while the work is paused.**

---

## Artefact identities (get these wrong and you will measure the wrong thing)

* **Pristine pre-change reference binary:** `/home/fsanches/compartilhado/kn7000-emulator/kn7000`,
  md5 **`52818738929b4056179d115d8ca1ad7f`**. This is the shipped build *including* kn5000-30.
* **`optC/kn7000_cleanC_backup` (or anything named `optC`) is the OPTION C BUILD — NOT a pre-change
  reference.** Comparing a candidate against it yields a false PASS.
* **Line-number trap:** every citation of `kn5000_cpanel.cpp:10xx` for option A — notably the rule-5
  deferral at **`:1049-1055`** — refers to the **option-A patched tree**, i.e. after applying
  `kn5000-cpserial-sender-handshake-candidate.patch`. On the shipped tree those lines are unrelated
  code. Anchors that *are* valid on the shipped tree: `tmp94c241_serial.cpp:189`, `:503`,
  `need_clock` at **`:526`** (some docs say 552/574 — stale), `kn5000_cpanel.cpp:1017`,
  `tmp94c241.h:121`, `kn5000.cpp:732`. `set_baudrate()` is declared, defined and **called from
  nowhere**.
* **Instrumentation:** `notes/kn5000-cpserial-sender-handshake-instrumentation.patch`. The probes
  that made all three adjudications possible (`strand_entry`/`wclose_mid`, `strand_exit_mid`,
  `PHASE_HIST`, `tmr_dead`, `cp_qmax`, `cp_hold`, `cp_abandon`, `max_rearm`, `bprime_calls/FIRED`)
  **and the `KN5A_NOIDLEWAIT=1` knob that isolated rule 5** — 459 lines across `kn5000_cpanel.cpp`,
  `tmp94c241_serial.cpp` and `tmp94c241_serial.h`, recovered from the session scratchpad on
  2026-07-21. **A′ cannot be verified to this record's standard without them.** Read the patch's own
  header for which probes are load-bearing and which read a vacuous zero.

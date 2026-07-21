# KN5000 control-panel-serial repros (deterministic, byte-identical across runs)

> **Entry point for the whole investigation: `../kn5000-cpserial-INDEX.md`** — what is shipped, what
> is broken, what was tried and rejected, and which of these repros are mandatory in a gate (`b3` is).
> **How to judge a result: `../kn5000-cpserial-measurement-discipline.md`** — three changes in a row
> were cleared by instruments that could not see the failure they introduced; that file is why.

These are the press schedules that reproduce the `kn5000-30` mid-byte gate-close wedge, together
with the adversarial schedules that later rejected options C, B and A. They were found and
cross-checked by independent verification passes on 2026-07-21 and are kept here because they had
been living in ephemeral session scratchpads. Every one of them is **deterministic**: a repeat run
produces byte-identical snapshot PNGs (verified — `x_sim2` run twice on the same build gives the
same six md5s).

Work on this link is **PAUSED at Felipe's request** (2026-07-21). Nothing here needs running; it is
kept so that the next pass does not have to reinvent it.

---

## How to run one

```
./run.sh <name> <lua> <binary> [ENV=VAL ...]
```

for example

```
cd notes/kn5000-cpserial-repros
./run.sh a1_pristine a1.lua /home/fsanches/compartilhado/kn7000-emulator/kn7000
./run.sh a1_cand     a1.lua /home/fsanches/compartilhado/kn7000_mame_build/kn7000
```

`run.sh` is the contract, and every one of its clauses is there because it has burned somebody:

```
timeout 900 "$BIN" kn5000 -rompath ./roms -skip_gameinfo -window \
  -nvram_directory "$RUN/nvram" -snapshot_directory "$RUN/snap" \
  -autoboot_script "$LUA" -pluginspath ./plugins
```

* **a fresh, EMPTY, private nvram directory every run** (`run.sh` does `rm -rf` then `mkdir`).
  ★ A **second** boot against a reused nvram directory grows a spurious `<Db>` transpose box with
  **zero input**. That is an unrelated power-down / NVRAM-ordering defect (blog Part 72; the same
  defect that blocks the splash-animation quest), **not** the serial link — never attribute a
  second-boot `<Db>` to a change here. Never point `-nvram_directory` at `kn7000-emulator/nvram`:
  that is Felipe's live state. (Outside this harness the workaround is
  `rm -f nvram/kn5000/nvram2` — that one file, not the whole directory.)
* **`-skip_gameinfo`** — without it the autoboot script never loads, and you get a clean-looking run
  that did nothing.
* **a visible `-window` on `DISPLAY=:0`** — `-video none` is forbidden in this project; Felipe
  watches autonomous runs.
* **`timeout`-wrapped**, and **run sequentially**: this box has 8 cores and fanning out MAME
  instances makes it unusable.
* Output lands in `$OUTBASE/<name>/` (default `/tmp/kn5000-cpserial-repros/`): `out.log`, the
  private `nvram/`, and `snap/kn5000/*.png`. `run.sh` prints the snapshot md5s for you.

Boot completes at ~20 emulated seconds; a settled fresh boot shows **no transpose box**. Most
schedules end at 45–90 emulated seconds (`a1soak` 164, `soak` 223, `x_long` ~275).

---

## How to read the result — the rules that have burned this project three times

**Liveness is a PIXEL DIFF.** Every schedule except `pfx3` ends with the same four liveness presses
and six snapshots:

```
pre   pre2   [MENU:DISK] disk   [MENU:SOUND] sound   [PIANO] piano   [ORCHPAD] orch
```

* six **identical** md5s = the panel is **DEAD**, whatever any counter says;
* frames that differ but land on a page **neither pressed button can reach** = the link is alive and
  **misframed**, which is worse: the instrument is dispatching button presses nobody made. Option C
  was rejected for exactly that — an unrequested PANEL MEMORY recall that changed the tempo from 120
  to 80, and `MENU:DISK` opening ENTERTAINER;
* a healthy run shows 5–6 distinct frames, with `pre` == `pre2`.

Read the PNGs with an image viewer or the Read tool. Never infer screen state from the log.

**Then, and only then, the counters** — and only the ones that can be embarrassed: `strand_entry`,
`strand_exit_mid`, the `PHASE_HIST` bucket count, `tmr_dead`, `cp_qmax`, `max_rearm`, `cp_hold`.
`drop_ext == 0` is a **tautology** under option A, `phantom == 0` is a tautology in every build
since kn5000-30, and `bprime_FIRED == 0` is **blind**; each of those read a perfect zero in a run
that visibly regressed. The full argument, with the measurements that falsified each of them, is in
`../kn5000-cpserial-measurement-discipline.md`. Counters need the instrumented build
(`../kn5000-cpserial-sender-handshake-instrumentation.patch`); the schedules themselves run on any
build.

---

## Artefact identities — get these wrong and you measure the wrong thing

| what | identity |
|---|---|
| **pristine pre-change reference** (the shipped build, *including* kn5000-30) | `/home/fsanches/compartilhado/kn7000-emulator/kn7000`, md5 **`52818738929b4056179d115d8ca1ad7f`** |
| the build tree's binary | `/home/fsanches/compartilhado/kn7000_mame_build/kn7000` — the same md5 while `src/` is reverted, and something else the moment it is not. **Check the md5; do not assume.** |
| ⚠ `optC/kn7000_cleanC_backup`, or anything named `optC` | the **OPTION C** build, *not* a pre-change reference. Its `a1` output is bit-identical to the option-C runs, so comparing a candidate against it yields a **false PASS**. |
| the instrumented option-A build | rebuild from `../kn5000-cpserial-sender-handshake-candidate.patch` + `../kn5000-cpserial-sender-handshake-instrumentation.patch`. `KN5A_PRE=1` disables the panel-side option-A rules, but it is **not** a validated pre-change control — it diverges from the pristine binary on `b1`. See the discipline note. |

Snapshot md5s in the tables below are for this ROM set and this MAME tree, truncated to the first 8
hex digits the way `run.sh` prints them. **If a pristine run does not reproduce its fingerprint,
stop and find out why before measuring anything else.**

---

## The suite

### Core wedge repros and controls (the kn5000-30 pass)

| lua | what it does | shipped build |
|---|---|---|
| `a1.lua` | 90 presses at 0.15 s from t=30 s, sound-group buttons only, no boot presses | **strands at t=31.141644, rx_count=5, LINK DEAD** — `d9f02718` ×6 |
| `b1.lua` (= `ph000.lua`, byte-identical files) | 6 presses during boot + 33 presses at 2 Hz — **ordinary playing**, not hammering | **strands at rx_count=7, LINK DEAD** — `f2b583c5` ×6 |
| **`b3.lua`** | 220 presses on a drifting interval, so one run sweeps many phases | **strands at rx_count=4, LINK DEAD** — `f2b583c5` ×6 |
| `ph007.lua` | boot-window press phase +0.07 s | **strands at rx_count=6, LINK DEAD** |
| `ph017.lua` / `ph033.lua` / `ph050.lua` | boot-window phase +0.17 / +0.33 / +0.50 s | clean. `ph033` is the **bit-identity control**: anything claimed behaviour-neutral must be byte-identical here — `2b300120 c616410f f60cd095 fa5d8a38 d4324146 95421443` |
| `soak.lua` | 444 presses over 223 emulated s | clean, zero strands — rules out press count and press rate as the trigger |
| `a1soak.lua` | `a1`, then a long idle, then liveness | never resynchronises on its own |
| `bootwin.lua` | the 6 boot-window presses of `b1` **and nothing else**, then settle + liveness (5 snapshots) | presses take effect, clean — isolates the boot-window property from the late burst |
| `s4.lua` | the S4 shape: 4 boot-window presses + 33 late | LIVE |

Only the boot-window press times differ across `ph000/007/017/033/050`; their late bursts are
identical. That is what makes the sweep a phase experiment and not a load experiment.

### Candidate-killers (the option-A pass) — configurations the SHIPPED build handles correctly

These matter most: a candidate is not allowed to break what already works.

| lua | what it does | shipped build | option A |
|---|---|---|---|
| **`x_sim2.lua`** | **two buttons at the same instant** (PIANO + ORCHESTRAL PAD), held 0.12 s, 20× at 0.6 s from t=30 s | **LIVE**, all four liveness presses correct — `8c6ce9f5 8c6ce9f5 d553df01 8b22e7e7 046fb4d6 8c95cdb0` | **DEAD** `7322ac60` ×6, frozen on ENTERTAINER → VOCAL REVERB, a page neither button can reach; `strand_entry` 28, `strand_exit_mid` 28, `PHASE_HIST 1:55 7:224` |
| **`pfx3.lua`** | **three presses from a cold boot** — SPLIT POINT / AUTO PLAY CHORD / SPLIT POINT, each with an EXIT, then a ±12-detent TEMPO/PROGRAM wheel sweep | `RIGHT1 Piano` — `home_after` = `521cfd38` | **`RIGHT1 Sound Name Error`** = `bfe7e4cb`, a kn5000-29 regression, with every other pixel identical |
| `x_multi.lua` | 8 buttons in 8 different segments pressed together, 30× at 0.6 s | **LIVE** — `085ef139 085ef139 579bdc0e 45d21291 23987114 f96d251b` | **DEAD** `484418d3` ×6; `tmr_dead` 1,509,252, `cp_qmax` 466, `strand_entry` 83, phantom arithmetic BROKEN |

`pfx3` is the exception to the liveness convention: 10 snapshots (settled home, two per press,
`home_after`, and two around the wheel sweep, which doubles as the kn5000-25 tempo-wheel regression
check). The load-bearing frame is `home_after`.

`x_sim2`, `x_multi`, `x_sim3` and `x_sim4` press several buttons at the same instant, so they
`table.sort` their action list. **Without that, the second and later buttons of a simultaneous group
are pressed and released inside one dispatch, i.e. invisibly to the panel's 2-scan / 14 ms
confirmation filter.** Copy that pattern in any new simultaneous-press schedule.

### Adversarial extras (option-A skeptic pass)

Written to attack option A from angles nobody had tried, and preserved here because they exist and
because `x_flood` is cited in the findings document. The result column says exactly what was
measured and on which build, so nothing has to be taken on faith.

| lua | what it does | what was measured |
|---|---|---|
| `x_flood.lua` | 200 presses at 20 Hz (0.05 s apart, held 0.03 s) | **kills the shipped build too** — only two distinct frames in six (`7af13431` ×3, `aed2c20f` ×3) — and kills option A (`strand_entry` 82, `tmr_dead` 1,040,155, `cp_qmax` 36, arithmetic BROKEN). A stress case, **not** a discriminator. |
| `x_rate075.lua` / `x_rate100.lua` / `x_rate125.lua` | rate sweep between `a1` (0.15 s, survives A) and `x_flood` (0.05 s, dies): 160 presses at 0.075 / 0.100 / 0.125 s | option A LIVE at all three; `strand_entry` 0 / 0 / 8, `tmr_dead` 0. **Never run on the shipped build.** |
| `x_boot.lua` | heavy pressing **through the whole boot** (64 presses, t=2 s → 20.9 s, 0.3 s apart) — the configuration Felipe's ground truth is about | option A: 0 strands, `PHASE_HIST 7:374` single bucket, `cp_qmax` 21, 4 distinct frames. Its phantom arithmetic reads BROKEN with zero strands, which is **unexplained** and is one more reason not to gate on that arithmetic. **Never run on the shipped build.** |
| `x_rhythm.lua` | rhythm running — so the CPU transmits panel commands almost continuously with the receiver closed — and 40 presses across it | option A LIVE, 0 strands, `cp_qmax` 21, `tmr_dead` 0 |
| `x_sim3.lua` / `x_sim4.lua` | the `x_sim2` minimisation: 3 and 4 buttons at the same instant, same cadence | both **LIVE** under option A while 2-at-once and 8-at-once are DEAD — non-monotonic in load, so it is a race, not a threshold |
| `x_rhythm2.lua` | rhythm never stopped, 120 presses at 0.25 s | **written, never run** — no recorded result on any build |
| `x_menu.lua` | 24 menu enter/exit pairs; each repaints the LCD and reprograms LEDs, i.e. a burst of CPU→panel commands with the receiver closed | **written, never run** |
| `x_long.lua` | ~4 emulated minutes of drifting-interval presses (~350) | **written, never run.** Degradation in this family shows up late: option C's `b3` only died at 220 presses |
| `x_idle.lua` | `a1`'s burst, then a long idle, then liveness | **written, never run** (`a1soak` covers the same idea) |

---

## The mandatory gate

Any change to this link is measured on the **whole** list below, on the candidate **and** on the
pristine binary, in the same pass, on this box:

```
a1   b1(=ph000)   b3   ph007   ph017   ph033   ph050   soak   a1soak
bootwin   s4   x_sim2   x_multi   pfx3
```

* **`b3` is mandatory.** `a1` alone passes variants that `b3` kills — that is how option C nearly
  landed, and how both reachable variants of option B were caught.
* **`x_sim2` and `pfx3` are mandatory.** They are the configurations the shipped build handles
  correctly and option A broke. A candidate that only re-runs the failures and never checks the
  successes is the mistake this project has now made three times.
* **`ph033` is the bit-identity control** for any change claimed to be behaviour-neutral.
* Judge on the pixel diff first. Score any criterion that passed *vacuously* — because the change
  was inert, or because it could not have failed — as a non-pass.

### A′ expectations already in hand (two data points, not a verification)

Option A with its rule-5 deferral disabled (`KN5A_NOIDLEWAIT=1`), which is what A′ is, returned
**exactly the pristine screens** on both counterexamples:

| repro | option A | A with rule 5 off | pristine |
|---|---|---|---|
| `x_sim2` | `7322ac60` ×6, DEAD | `8c6ce9f5 8c6ce9f5 d553df01 8b22e7e7 046fb4d6 8c95cdb0`, `strand_entry` 0, `PHASE_HIST 7:296` | identical to the middle column |
| `pfx3` | `bfe7e4cb` "Sound Name Error" | `521cfd38` "Piano" | `521cfd38` "Piano" |

Rule 5 existed because `a1` showed 5 mid-byte gate closes without it and 0 with it, so A′ has to be
measured on the whole suite before anyone believes it.

---

## Generators

* `gen.py` — the phase-sweep generator behind `ph000` … `ph050`, `a1`, `b1`, `b3`, `soak` and
  `a1soak`. Takes a JSON config as `argv[1]` and writes the lua to stdout:

  ```
  ./gen.py '{"bootwin": [[14.0,0],[14.7,1]],
             "late": {"start":34,"interval":0.5,"count":33,"pool":"right"}}' > my.lua
  ```

  Keys: `bootwin` (list of `[time, button-index]`), `late` (`start`/`interval`/`count`/`pool` =
  `right`/`left`/`both`), `drift` (`start`/`iv0`/`step`/`count`), `soak`
  (`start`/`interval`/`count`), plus `hold`, `skew`, `tend`. Every generated script ends with the
  same liveness tail, so runs are directly comparable across configurations.
* `gen_adversarial.py` — the skeptic pass's generator, preserved byte-identical from the scratchpad.
  It is not parameterised: running it rewrites **all** the `x_*` schedules, and it carries a comment
  above each family explaining what that family attacks. It writes into a `lua/` subdirectory next
  to itself, so it will not clobber the checked-in copies unless you point it here deliberately.

---

## Gotchas

* Actions must be emitted in strictly increasing time order. The harness dispatches from an
  `emu.register_periodic` callback comparing against
  `mac.time.seconds + mac.time.attoseconds/1e18` — **`machine.time.seconds` alone is an INTEGER**,
  a silent breakage this project has hit before.
* Simultaneous presses need `table.sort` (see above).
* Two ROMs of this driver are flagged `NEEDS REDUMP` / `NO GOOD DUMP KNOWN`; the "machine might not
  run correctly" banner at the top of every log is expected and unrelated.
* `-pluginspath ./plugins` is kept for parity with the project's other runners; these schedules do
  not need the layout plugin.

# DSP probe designs for the WSA1R monitor — and why all seven were refused

**2026-09-14.** Seven probe-microcode experiments were designed, one per open decode axis, then
put through an adversarial verification pass whose instruction was to *refute*.
**All seven came back unsound.** That is the result, and it is a useful one: the flaw lists are a
redesign queue, and three objections recur in every single design.

* `probe-designs-2026-09-14.json` — the complete output: per axis the probe, what it
  discriminates, its negative control, and the verifiers' `flaws` and `fixes` lists.
* Source design doc: `../HARDWARE-CUSTOM-DSP-PROGRAMS-WSA1R.md` Part B.
* The instrument these were written for: `../WSA1R-SYSEX-MONITOR-BUILD.md`.

⚠ **These critiques are agent output, not measurements.** Each one cites a file and a line; treat
a `fix` as a claim to check, not as a finding. What follows is the shape, not an endorsement.

| axis | words gated | verdict | the objection that kills it |
|---|---|---|---|
| `bit11` | 99 | ✗ | the stimulus does not exist — two pairs of the eleven body words are *the same word*, and nothing moves the pointer, so the input never sweeps and `A1 == A0` follows for every true reading |
| `src11` | 110 | ✗ | the A/B logic is inverted; in unit 1 both arms read `accb` and predict the identical capture |
| `modes` | 106 | ✗ | the criterion cannot come out negative — the DSP is a send/return insert, so the dry note reaches the output at the same frequency in *every* run, NOP null included |
| `class6` | 18 | ✗ | the vehicle does not exist on the only machine we have: `kernel.dsm`, the one program that ever executes in play, has **zero** class-6 words |
| `act` | 45 | ✗ | the word under test has no ACTION field — both candidates set `hi12` bit 11, the format escape — and the body is built from the KN5000's kernel, not the WSA1R's |
| `rqgf` | 4 | ✗ | wrong CPU (below), and GF has no readback path even in principle |
| `f31` | 9 | ✗ | the success case *is* the status quo: the adopted ALU already treats f31 1,3,4,5,6,7 as ADD, so the headline outcome re-confirms rather than decodes |

## The three objections that recur in all seven

1. **★ WRONG CPU.** The monitor is patched into `qsigcwsa1ax.ic12` = **CPU 1**. The µPD6383s hang
   off **CPU 2**'s ports (`wsa1.cpp`: `P7` = DSPD0-7, `P5.3` = C/D, chip selects on `P5.4`/`P5.5`/
   `P2.7`). Between them is only the IC24/IC25 octal-latch mailbox, speaking CPU 2's existing
   protocol. So `LOAD`, `POKE`, `RUN` and any DSP-side `DUMP` are **not extensions of PEEK** —
   they are a second agent, on the other processor, reached over a link whose command set we would
   have to join. `WSA1R-SYSEX-MONITOR-BUILD.md` already said this; seven independent reviews
   agreeing is worth recording.
2. **★ THERE IS NO AUDIO READBACK IN EMULATION.** Six 16 Mbit wave mask ROMs are `NO_DUMP`, so
   `wsa1r` produces no audio in MAME at all. Every design whose observable is "capture the insert
   return" is unrunnable in the emulator — and running the *emulator's* DSP model to decide what
   the *chip's* instructions mean is circular anyway. On Felipe's real unit the path is
   DAC → analogue → ADC with no digital out, so only step **count** and monotone **order** survive;
   absolute values do not.
3. **★ NO BEACON, OR A BEACON THAT SHARES THE HYPOTHESIS.** Several designs read their positive
   control *through* the idiom under test, so "the poke never arrived", "the idiom does not read
   the table" and "the instruction is inert" are one observation. This is RULE 15 again: prove the
   instrument can see the failure before reporting its absence.

⚠ A fourth, narrower one worth carrying: **none of the words in these bodies is in the 45-word
proven-resident set** (`wsa1/dsp/analysis/runtime-resident-iram-words.txt`). They come from effect
bodies the shipped firmware never uploads, so a body that emits nothing exonerates no word.

## What this changes about the plan

The monitor's next milestone was `LOAD`/`POKE`/`RUN`/`DUMP`. Objection 1 says that is not a
milestone but a **separate project on CPU 2**, and objection 2 says the readback it was designed
around does not exist in the emulator. Before any of these probes is worth redesigning, the
cheap prerequisite is the one `rqgf` names as its own step 0 and costs nothing:

> **Render the service manual's effects-board pages at ≥300 dpi and read IC30 pins 83-88.**

`service-manuals-are-image-only` is a standing lesson here — `pdftotext` returns nothing and has
produced two false negatives already. Three outcomes: wired to a latch/port (both `RQ`/`GF`
searches armed, and the addresses known); strapped (degraded); not connected (the axis is dead on
this board — and the honest report is then *"unavailable on the WSA1R"*, never *"the chip has no
COND field"*).

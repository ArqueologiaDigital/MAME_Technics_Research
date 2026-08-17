# P9 — the KN5000 Feature Presentation plays one song and stops

*2026-08-15. Every number here has a committed log beside it; every address was verified against
the ROM or the runtime stack rather than taken from a label.*

## What P9 said, and what is actually true

The task queue recorded: *"after `3fd44f3` the demo plays 19.26 → 131.5 s then `transport`
(0x0420) goes 04→00. That is beat 171 of 292 = 58 % of the song."*

Measured on the current build, three runs, deterministic to the timestamp:

| claim | measured |
|---|---|
| stalls at 131.5 s | plays to **139.47 s** |
| transport → `00` | `04` → **`0x0C`** (terminal STOP) → `00` |
| a stall | **a correct, guarded STOP command** |
| sub-tick frozen at `00` | frozen at **`0x18`** |

**The stop is not a bug.** It is a normal end-of-song STOP, executed correctly at every level.

## The defect, in one sentence

**The demo countdown timer is armed once and never re-armed, so after the first song ends
nothing starts the next one.**

`notes/p9-demotimer-2026-08-15.log`, `notes/p9-democountdown` run:

```
t=23.99  DRAM[0x0D2F] <- 12      (already counting; 15→13 immediately before)
t=24.19  DRAM[0x0D2F] <- 10      ← at 10 the firmware parses the slide and calls PlaySong
  ...    one write every ~100 ms, all from PC=0xF86C01
t=25.56  DRAM[0x0D2F] <-  0      ← 13 writes total
t=40…160 never written again
```

The machine stays in state `0x8D38 = 0xE4` (Feature Presentation) the whole time — it never
leaves the presentation, it just has no live timer.

## The stop chain, fully traced

Every link verified; the dispatch table was read out of the ROM.

```
event queue
  0xF4E720   command dispatcher      cp L,1 → call 0xf3cac1   (2→f4382a, 3→f437fa, 4→f4384c)
  0xF3CAC1   end-of-playback teardown; six cleanup calls; clears 0x22FC
  0xF59AB9   public STOP thunk       push XIZ / call / pop XIZ / ret
  0xF5ADCA   dispatcher              index = bit2 of 0x041e|0x0421|0x0420 → table at 0xF5ADF9
  0xF5AF9D   handler for index 0x1C  (table entry reads 0x00F5AF9D — verified)
  f5afc3     ld (0x0420),0x0c        ★ the terminal STOP, t=139.47
```

Ordering, from the write tap: transport `0x0C` at **139.47**, AccPlayMode `0x00` at **139.50**
(from `0xF3CB3E`) — the stop causes the accompaniment shutdown, not the reverse. A later,
separate actor writes `0x10` at 139.64 from `0xEF0FA5`.

## What it is NOT

* **Not stuck audio.** Active voices go `0x1CE0` → `0x0000` exactly at the stop and stay clear
  for 59 s (`notes/p9-parts-vs-voices-2026-08-15.log`). The firmware keeps polling the tone
  generator 36,000 times. **P9 and P3 ("stuck EG voices") are different bugs.**
* **Not blocked on the undumped waveform ROMs.** `kn5000-docs/ssf-presentation.md` attributes
  the stall to parts that never finish *because* waveform ROMs are missing. Contradicted: zero
  active voices, and the timer — not the parts — is what fails to restart.
* **Not an idle-demo problem.** There is no idle-triggered demo; the timer lives *inside* the
  presentation. A 300 s idle run showing "no demo" tested something that does not exist.

## Corrections this investigation forced

1. `ssf-presentation.md` labels `0x10420` "sequencer part active flags, `0xFFFF` = all 16 parts
   active". A write tap shows every write to `0x10420-0x10421` occurs in one burst at
   t=24.19–24.40 and never again, with values (`0x64`, `0x98`, `0x50`, `0x27`, `0x1E`) that look
   like stream data, not flags. **The label does not match behaviour and needs re-deriving.**
2. My own first reading of that location was wrong too: the alternating `0x00XX`/`0xXX00` values
   are byte writes to the two addresses separately, seen through a 16-bit tap. `0x044A` is
   `0x4A` and `0x04` side by side, not a mask.
3. The docs' "the Demo Timer System (song cycling) works correctly in MAME" is not reproduced.

## The arming path (traced 2026-08-15)

```
0xF843E6   call 0xf86b7c            demo-start path; around it, two event posts via
                                    0xFA49B7 with 0x01e000ac / 0x01e000ad, and a write to 0x28A4
  0xF86B7C  (reached by calr from here)
    0xF86D86  ld (0x0d2f),0x0f      ← Demo_ResetCountdownTimer, all two instructions of it
    0xF86D8B  ret                   ← what the write tap reports (prefetch offset)
```

Runtime stack at the arming write gives the return address `0x00F843EA`, i.e. the call at
`0xF843E6`. This runs **once**, at t=23.72. The ticker that decrements is a different routine,
`0xF86C01`.

⚠ A static search for callers of `0xF86D86` returned **zero** — no absolute `call` and no 24-bit
reference exists anywhere in the image, because it is entered by `calr`.

✅ **RESOLVED 2026-08-17 — that conclusion was a tooling limit, not a property of the firmware.**
`calr` encodes a *displacement*, not an address, so searching for the target's bytes cannot find it;
searching for the displacement can. `tools/tlcs900_callers.py` decodes both forms and reports:

```
callers of 0xF86D86
  no absolute CALL sites
  1 relative CALR site  [1e disp16]:  0xF86CB6   (disp +205)
```

This *refines* rather than contradicts the runtime stack dump above: `0xF86B7C` is the routine
entered from `0xF843E6`, and `0xF86CB6` is the `calr` inside its body. The tool is validated on two
known cases in each direction (absolute `0xEF08DB → 0xF86A9F`, relative `0xEF0580 → 0xEF083E`).

★ **The lesson generalises beyond this note**: "static caller search does not work in these ROMs"
has been recorded several times in this project and used to justify falling back to runtime stack
dumps. It is half true — it does not work if you search for absolute addresses only. Decode `calr`
and it works. (The MN10300 side has its own version of this trap: callers enter at *entry+2*
because `call` performs the register save — see `notes/FINDINGS-mn10300-caller-search.md`.)

## Next step

The arming routine and its caller are now known, and neither runs a second time. What remains is
to find what *should* invoke `0xF86B7C` (or `0xF86D86` directly) when a song ends. Two concrete
leads:

1. The teardown at `0xF3CAC1` makes six calls — `f3dfff`, `fe118d`, `fdf5f5`, `f3f179`,
   `f6e63a`, `fc8dce`. If one is meant to re-arm the countdown it is either not running or
   failing a guard. Disassemble each and look for a path to `0xF86B7C`.
2. `0xF843E6` sits beside two event posts through `0xFA49B7` (`0x01e000ac`, `0x01e000ad`). If
   song-end is supposed to post a similar event that re-enters the demo-start path, tapping
   `0xFA49B7`'s argument would show whether that event is ever posted.

A note on stopping here: this is a good handoff point. The defect is stated, the arming path is
traced end to end, and the remaining question is a bounded search over six known routines.

## Method notes worth keeping

* The live stack is **XSSP**, not XNSP — the CPU runs in system mode, and TLCS-900 has no
  register called `SP`. Guessing cost a full run that produced no output at all.
* **Static caller searches do not work in this ROM**: routines are entered by `calr` and jump
  tables, which encode displacements, not addresses. Zero references to `0xF5AF9C` exist.
* Write-tap ranges must be **word-aligned** on this 16-bit bus, and the byte lane must be
  selected from the mask or two addresses get conflated.
* The reported PC is a **prefetch neighbourhood**, not the writing instruction: the tap said
  `0xF5AFC8`, the writer is `0xF5AFC3`.
* Rigs: `kn5000_p9_stall.lua` (when), `kn5000_p9_writer.lua` (who + call stack),
  `kn5000_demotimer.lua` (guard state), `kn5000_stuckparts.lua` (parts vs voices),
  `kn5000_partsmask.lua`, `kn5000_democountdown.lua` (timer arming).

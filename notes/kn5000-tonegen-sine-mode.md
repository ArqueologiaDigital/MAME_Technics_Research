# KN5000 tone generator: diagnostic sine render mode (2026-08-05)

`TGMODE` bit 0, live from the MAME menu (Machine Configuration):
`0 = PCM from wave ROM (normal)`, `1 = Sine test tone (no wave ROM PCM)`.

## What it is

A second way to produce a voice's RAW SAMPLE, and nothing else. The two modes differ at
exactly one `if` in `sound_stream_update()`; note on/off, voice allocation, pitch tracking,
the amplitude EG, the TVF, panning, the mixer and the R2s silence interlock are literally the
same code. That is what makes the A/B mean something.

* The sine has its own **Q32 phase accumulator**, not `wave_offset` — that has only 16
  integer bits and is re-based by the loop wrap, so it cannot free-run as a phase.
* Its increment comes from the **absolute frequency** `update_pitch()` already computes.
  `pitch_step` is a CHUNK-RELATIVE resampling ratio (`freq * pitch_period_q16 / 48000`), so
  reusing it would give the wrong note, differently wrong per instrument. `update_pitch()`
  now computes that frequency before its early returns; `pitch_step` itself is untouched.
* `SINE_PEAK = 16384` matches the wave ROM's typical **RMS**, not its peak: the PCM is
  peak-normalised (median chunk peak 32713) with a 5.38 dB median crest factor.

## Regression gate

PCM output is **bit-identical** before and after the change: same binary options,
`-seconds_to_run 70`, 20,160,006 audio bytes, zero differing. Two runs of one binary are also
bit-identical, so the emulator is deterministic and the comparison is meaningful.
⚠ Do NOT compare two runs that were bounded by wall-clock `timeout` instead of
`-seconds_to_run` — they end at different machine times and diverge harmlessly.

## First result (KN5000 Feature Demo)

Fair window 26-38 s, where both modes are producing audio at comparable level:

| mode | L rms | R rms | L clicks (step > 8000) | R clicks |
|---|---|---|---|---|
| PCM  | 1131 | 1871 | **675** | **925** |
| SINE | 1201 | 2226 | **0** | **0** |

Same envelopes, same pitches, same mixer, same voice allocation up to this point — and the
discontinuities vanish completely. **The glitches come from the PCM sample path (data,
addressing, loop points or interpolation), not from the machinery around it.**

## Known limitation, foreseen by design

After ~t=40 s the demo goes quiet in SINE mode while PCM keeps playing (a steady ~6 rms
residual = one held voice). This is the predicted voice-allocation divergence: voices whose
PCM probe finds silence are skipped in PCM mode and get `eg_running` cleared, but they SOUND
in sine mode, so the silence interlock holds `eg_running` set — and `eg_running` is what
`status_r()` reports back to the firmware's voice manager. **A sine-mode capture is a
faithful proxy for the pitch/envelope/mix machinery, NOT for voice allocation.** Use the
window where both modes are active.

## Not settled

* Absolute pitch for voices with `true_note < 0` (demo / rhythm / sequencer) rests on the
  `0x3524` reg[8] anchor, which is a convenience rather than a measurement — the per-chunk
  root pitch is undecoded. Those sines may be octaves off. Only keybed/MIDI notes
  (`true_note >= 0`) give a trustworthy absolute Hz.
* `pitch_offset` still comes from `resolve_note_group()`, which is gated on the wave-ROM
  directory, so sine pitch is not totally ROM-independent.

---

# Update 2026-08-05 (later): sine mode found an ENVELOPE bug

## Correction to the note above

The first version of this note said "a PCM recording decays, a constant sine never does",
and treated the sine's failure to go silent as a limitation of the diagnostic. **Felipe
pointed out that is backwards: a sine with a proper envelope DOES decay.** He is right, and
the corrected reading is the whole point of building the mode.

## Voice allocation is now shared

`has_pcm_data` was being short-circuited in sine mode so every voice sounded. That was wrong:
the probe answers an ALLOCATION question ("did this voice resolve to a real recording"), not a
rendering one. It now runs in both modes. MEASURED: the per-second voice census is byte-for-byte
identical between PCM and sine from t=24 to t=31.

The firmware also runs identically in both modes — beat clock, transport, watchdog and the
0x0425/0x0426 counters match at every sampled timestamp — so nothing is stalling it.

## What actually stops sine mode at ~t=37

A per-voice envelope dump of the stuck state (VERBOSE = LOG_CENSUS):

```
v14 key=1 eg_run=1 eg_lvl= 50.00 tgt= 50.00 step=0.041059 seg=2 env=255 sil=0 gain=0.000139
v37 key=1 eg_run=1 eg_lvl= 54.00 tgt= 54.00 step=0.232267 seg=2 env=255 sil=0 gain=0.000165
v40 key=1 eg_run=1 eg_lvl= 66.00 tgt= 66.00 step=1.562500 seg=2 env=255 sil=0 gain=0.000278
v23 key=1 eg_run=0 eg_lvl=204.00 tgt= 98.00 step=0.000000 seg=1 env=  0 sil=641187
v35 key=1 eg_run=0 eg_lvl=197.00 tgt=134.00 step=0.000000 seg=1 env=  0 sil=638421
```

**Type A (v14/v37/v40): the amplitude EG never reaches silence.** Each has reached its target
in the FINAL segment (`eg_level == eg_target`, `seg=2`, so no further segment loads) and holds
there forever with a gain of about -77 dB — small, but not zero. At `SINE_PEAK` that is ~2 LSB,
and the silence interlock's threshold is 0.5 LSB, so the voice is never declared silent,
`eg_running` never clears, and the key is never released (`key=1` forever).

In PCM mode this is INVISIBLE: by that point the recording itself has decayed into the noise
floor, so the product goes under 0.5 LSB and the interlock fires. **PCM decay was masking an
envelope that never terminates.** That is a real bug in shared machinery, and exactly the class
of defect the sine mode was built to expose.

**Type B (v23/v35/v38):** the documented `env_level == 0` rhythm hand-off voices. Silent in both
modes, so `eg_running` clears correctly — but they stay `active=1 key_on=1` forever with the EG
frozen (`step=0`, level 197-204, target 98-134, never moving). A second stuck state, lower
priority because it is inaudible.

## Next

Fix the envelope, not the sine. Candidates, in order:
 1. Should the final EG segment continue to its target and then to TRUE zero? `eg_level_to_gain`
    already special-cases level 0 as true silence, so the law expects zero to be reachable.
 2. Is `seg=2` really terminal, or should a fourth phase / release be armed when the target is
    reached with the key still down?
 3. Why is the key never released for these voices — is the firmware's key-off suppressed
    because `eg_running` is still set (a feedback loop), or was it never going to send one?
    `keyoffcmd` freezes at 578 in sine mode versus 1732 in PCM, so this is worth answering
    before changing EG semantics.

⚠ Any EG change alters PCM audio too. Establish the PCM bit-identity baseline
(`-seconds_to_run 70`) BEFORE touching it, and expect that baseline to move — deliberately.

---

# Update 2026-08-05 (diagnostic pass): the feedback loop is REFUTED

Felipe asked for the diagnostic before any envelope change. Two results, one negative and
one that inverts the working picture.

## 1. The status_r() feedback loop is NOT the cause

`status_r()` documents the mechanism plainly: IC303 has no note-off input, so the firmware
generates `0x7E00` (FREE) from the active-voice bitmap, that bitmap IS the `eg_running`
latch, and the latch clears only on genuine rendered silence — "while a key is down the EG
sits at its programmed sustain level, so the interlock never arms and the voice is
structurally unreclaimable, for any hold duration."

That reads like a closed loop, so it was tested rather than believed. `TGMODE` bit 1 reports
a voice silent as soon as its last EG segment reaches its target, breaking the loop at
exactly one point.

| run | 28-36 s rms | 40-55 s rms |
|---|---|---|
| PCM | 2254 | **748** (still playing) |
| sine | 2713 | 4.3 (stalled) |
| sine + loop broken | 2699 | **1.2** (still stalled) |

The probe DOES free the stuck voices — the residual falls from 4.3 to 1.2 — and the demo
still does not resume. **Breaking the loop changes nothing. The hypothesis is dead.**

## 2. The sub-CPU is BUSIER in sine mode, not blocked

PC histogram, 44-50 s, the stalled window (the tone generator is on the sub-CPU bus):

```
PCM mode : 020CB9 30.5%  020CFA 20.9%  020CB6 17.2%  020D02 14.6%  020CFE 7.6%  020CFC 6.0%
           -> 96.8% inside 020CB6..020D02, a ~0x4C-byte tight loop = the idle wait
SINE mode: 01F8D5 2.6%  035ADF 2.3%  01F861 2.3%  03D0C5 2.3%  01FB03 2.3%  035AC8 2.3% ...
           -> no address above 2.6%, execution spread across the map
```

This is the opposite of "the firmware is stuck waiting". In PCM mode the sub-CPU sits in its
idle loop; in sine mode it is running a great deal of code and never settles. So the stall is
not a block on a busy voice — something is giving the sub-CPU continuous work.

## Where to look next

* Identify the PCM-mode idle loop at `020CB6..020D02` (sub-CPU). Knowing what it waits on
  names the condition sine mode fails to reach.
* Find what sine mode makes the sub-CPU do instead — the spread suggests an allocator or
  retry path running continuously. `035AC8/035AD9/035ADF` and `01F861/01F8D5/01FB03` recur
  and are the first two clusters to disassemble.
* Only after that, revisit the envelope. The Type A stuck voices (EG parked at its final
  target ~-77 dB, never silent) are still a real defect masked by PCM decay — but they are
  now demonstrably NOT what stops the demo.

---

# Update 2026-08-05 (experiment): the maincpu keeps sending; the sub-CPU stops REPLYING

## Correction to the previous update

"The sub-CPU is BUSIER in sine mode, not blocked" was WRONG, and the error was in reading the
histogram. The flat 2.0-2.6% spread is not work scattered across the map — it is seven
instructions of ONE ~70-instruction non-nested loop, sampled uniformly (~1.3%/instruction,
multi-cycle ones at 2.0-2.6%). **The sub-CPU is IDLE in sine mode.** Each of the four service
calls in Audio_Main_Loop returns immediately because its queue reads empty. This does not rest
on the sampling: none of those PCs sits in a loop that can run twice in one pass without first
consuming a queue entry.

The PCM-mode loop at 0x020CB6 is a genuine wait — on Port D bit 4 = the MSTAT1 pin driven by
the maincpu's Port Z bit 1, inside INTERCPU_DMA_SEND_CHUNK, the sub->main path. PCM has traffic
to send and waits on the handshake; sine has nothing to send and never enters it.

Load base VERIFIED: file offset 0 of `kn5000_subprogram_v142.rom` = sub-CPU **0x00EF00**
(3267/3278 existing symbols land on instruction boundaries there; ~36% at 0).

## The experiment

Every inter-CPU latch byte logged with a timestamp (LOG_LATCH_DATA), both directions, both
modes, `-seconds_to_run 50`. Bytes per second:

```
  t     PCM main->sub  sub->main   |  SINE main->sub  sub->main
 33          434        140        |        434        140
 35          615        150        |        615        150
 36          906        160        |        906        120
 37          809        190        |        809          0     <-- replies stop dead
 38          444        140        |        444          0
 41         1266        260        |        489          0
 47          419        140        |        424          0
```

* **main->sub is IDENTICAL through t=39 and healthy thereafter.** The maincpu keeps delivering
  commands at full rate in sine mode. It is not the victim, and it has not stalled.
* **sub->main collapses to EXACTLY ZERO at t=37** and never recovers, while PCM continues at
  140-260 bytes/s.

## And the sub-CPU is not dropping the work either

Reading the DSP command ring live (sub-CPU DRAM) across the same window:

```
        ringlevel(0x4366)   gate(0x448C)   0x3B60 / 0x3B62
PCM     10 from t=37        0              DIVERGE (rd runs ahead, gap grows to 0x1E0)
SINE    0 always            0              EQUAL every second
```

So in sine mode the ring is **fully drained every pass** and the truncated-packet gate never
latches. The sub-CPU receives the same commands and consumes all of them. It simply produces
no replies. (Note this is the opposite of the ring-starvation guess, and PCM is the mode with
a standing backlog of 10 bytes — unexplained, and possibly worth a look on its own.)

## Where that leaves it

Delivery and consumption are both healthy and identical. The divergence is downstream of
both: **the sub-CPU stops generating sub->main traffic at t=37 while still processing input.**

Next, and unchanged from the analysis: put hit counters on the sub-CPU voice bookkeeping —
Voice_Retire_ToFreePool 0x021E31, Voice_Demote_Decayed 0x021E83, Voice_Reset_Engine 0x021ECB,
and the `ld (0x100002),0x7e00` FREE write at 0x021F94 — in both modes across t=25-50 s. That
path is fed by the tone-generator status readback at 0x02102B, which is the ONLY route in the
whole image from rendered sample values back into sub-CPU control flow, so it is the only
place the two modes can legally diverge. If the retire/demote counters go to zero in sine mode
before t=37 while PCM keeps ticking, the software free pool starved.

⚠ Also unresolved: what generates the sub->main traffic in PCM mode is still unidentified
(probably 0x035D59, a reply from the DSP command dispatcher, by elimination — untraced).
Identifying it would say directly what stopped.

---

# Update 2026-08-05 (settled): the SUB->MAIN HANDSHAKE, not the voice pool

Two hypotheses were on the table: **H1** the software voice pool starves (a sine never renders
silence -> `eg_running` never clears -> voices are never returned to the free pool -> the sub
has nothing left to say), and **H2** the sub->main handshake times out (the sub busy-waits on
MSTAT1 in `INTERCPU_DMA_SEND_CHUNK` with a 60001-poll limit; if it started timing out, sub->main
would read exactly zero).

**H2 SURVIVES. H1 IS DEAD.** The sub-CPU wants to send just as often as in PCM mode; every
single attempt times out.

## The discriminating measurement

Opcode-execution counters on the sub-CPU (Lua read taps, the program is in DRAM and cannot be
patched), both modes, `-seconds_to_run 52`, summed over t=39..50 s:

| | entries to 0x020CB0 | MSTAT1 polls | timeout-loop spins | bytes sent |
|---|---|---|---|---|
| **PCM**  | 207 | 207 | **0** | 2070 |
| **SINE** | 157 | 9,430,339 | **9,428,854** | **0** |

* PCM: the grant is present on the **first** poll, 207 times out of 207. That is the null, and
  it can fail — it does, in the other column.
* SINE: 9,428,854 / 157 = **60,056 spins per entry**, i.e. the full `cp HL,0xea60` limit
  (60001) on **every** entry. Not one send gets through, and the sub still asks 13x/s — the
  same rate as PCM's 13-21/s. It is not out of work; it is not being let in.
* The 60001-poll timeout costs ~2 M cycles a go. At 13/s that is the whole 20 MHz CPU, which
  is why the voice bookkeeping and the tone-generator status readback also fall to zero from
  t=38: **consequences of the stall, not its cause.**

## Why the grant never comes

`MSTAT1` = MainCPU Port Z bit 1 -> SubCPU Port D bit 4. It means "MainCPU ready to accept a
sub->main header". Main clears it the instant it accepts one (`res 1,(0x68)` @ **0xEF35C4**)
and raises it again only when the payload DMA has completed and been dispatched
(`set 1,(0x68)` @ **0xEF366C / 0xEF367E**, in the DMA-done ISR at 0xEF35E8).

Event trace of the last healthy transaction and the fatal one (sine, t=36.7):

```
36.72577 SUB  enter SEND_CHUNK
36.72577 SUB->MAIN byte 68            header: channel 3, payload (0x68 & 0x1f)+1 = 9
36.72580 MAIN reads latch 68 PC=EF3542   <== header read by the INT0 ISR
36.72580 MAIN MSTAT1 1->0   PC=EF35C7    main is now busy receiving
36.72582 SUB->MAIN byte 2B            payload 1
36.72582 SUB->MAIN byte 30            payload 2
36.72583 MAIN reads latch 30 PC=EF3542   <== *** READ AS A HEADER ***
36.72583 SUB->MAIN byte 7F .. 02      payload 3..9 (delivered, nobody expecting them)
36.76224 SUB  enter SEND_CHUNK        -> MSTAT1 already 0 -> 60001 spins -> gives up, forever
```

**A payload byte was taken for a header.** `0x30` re-armed the receive DMA for
`(0x30 & 0x1f)+1 = 17` bytes; only 7 of the 9-byte payload were left. The DMA never completes,
so the DMA-done ISR never runs, so `set 1,(0x68)` never executes. Verified in the stuck state
at t=36.84 and unchanged at t=50:

```
MAIN 05E2=01 (rx state = mid-receive)  05E4=30 (header)  PZ=ED (MSTAT1=0)
SUB  PD=67 (MSTAT1 in = 0)             10E8=00
```

PCM control at t=50: `05E2=00` (idle), `PZ=EF` (MSTAT1=1), `PD=77`. The maincpu's own stuck-
handshake watchdog (0xEF36A8, and 0xEF36F0) never fires — worth a look separately.

So the render mode is not the defect; it shifts the interleaving and loses a race that the
inter-CPU receive path already had. **The bug is in the MainCPU INT0 ISR / micro-DMA
arbitration on the sub->main channel** (ISR at 0xEF3525 reads the latch at 0xEF353D while the
micro-DMA is also armed on the same interrupt), not in the tone generator.

## Three methodology corrections — these bit, hard

1. **`ioport_field:set_value()` TOGGLES a `PORT_CONFNAME` field, it does not assign it.**
   MAME persists the live value in `cfg/kn5000.cfg`, so `set_value(1)` gives
   `saved_value XOR 1`. Two parallel runs each rewrite that file at exit, so the mode a script
   selects depends on which run exited last. Drive `TGMODE` from the **cfg file** and print
   `ioport.ports[":TGMODE"]:read()` every second — a mode label that is not read back is not
   evidence. (One pass of this investigation ran with the two modes silently swapped.)
2. **`cfg/kn5000.cfg` also carries `AREA=2`**, not the MAME default 6. With the default
   region the demo does **not** stall in either mode within 52 s. The region DIP is part of
   the reproduction recipe.
3. **tlcs900 `RDOP` prefetches PC+3.** A Lua read tap placed on an instruction's own address
   counts the *previous* instruction, not that one. Put the tap at **target+3**, and filter on
   the byte lane in `mem_mask` (the program space is 16 bits wide).

`LOG_HANDSHAKE` (VERBOSE bit 3, default off) now logs MSTAT/SSTAT transitions with a
timestamp and PC, which is the cheapest way back into this.

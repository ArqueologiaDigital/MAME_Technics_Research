# KN5000 IC311 (uPD6383GF): a four-channel mixer program of our own

Question: can a program written from the decoded word forms run on the MAME core and put four sample streams,
each at its own volume, on the KN5000's speakers? Research plan: technics-docs
`kn5000-dsp-sample-playback-research.md`. The program that will run on the instrument is
technics-anotherworld `kn5000cnv/tools/dspmix.py`; this directory holds the test version and the harness runs.

**Answer (2026-10-23): yes, in the emulator.** `mix4_test.py` mixes four D-RAM cells, which the harness drives as
sines of 220, 330, 440 and 660 Hz, at volume 0.5 each. The kept frames present exactly that sum on DO1, and the
speakers carry the four tones, with everything else 35 dB below them:

| measurement (run `h8`, 3 s after the program is applied)   | value                            |
|------------------------------------------------------------|----------------------------------|
| frames kept / discarded                                    | all kept: 0 traps, 0 partials    |
| speaker level before the program (0 - 6.7 s)               | peak 0                           |
| speaker level with it                                      | rms 5793, peak 13781             |
| 220 / 330 / 440 / 660 Hz over the median bin               | 157.1 / 157.4 / 156.1 / 157.1 dB |
| energy outside the four tones, speaker (48 kHz)            | -34.7 dB                         |
| energy outside the four tones, DO1 itself (44.1 kHz, `h7`) | -50.4 dB                         |

The speaker's higher residual comes from the tone generator, which holds each 44.1 kHz return sample on its
48 kHz stream (`kn5000_tonegen.cpp`, `lrck_edge`). The DSP's own output is clean to the window's leakage.

## What the core's model required of the program

Each item was found on this program and measured with the trace below:

1. **The D-RAM pointer is set only by the per-unit CALL.** No decoded word loads it (`000.1.NN.000` does not).
   The CALL (`404.1.0E.015`, END OF BLOCK class 1, the unit in `addr8`) jumps to I-RAM 84 and rebases the
   pointer to `DRAM_UNIT_BASE` 0x05. Without it, a walk of +4 a frame drifted the reads across D-RAM: DO1 was
   0 on most logged frames (run `h2`).
2. **The return lands at the CALL + 2.** The word after a CALL is skipped, so the presentation word goes one
   word later (run `h4`, trace slots 0, 84..91, 2).
3. **A HOLD step skips the multiply** (`exec_alu`: no product when `hi12[3:1]` is HOLD). The first multiply of
   a chain is a LOAD step; the stale product it loads is overwritten by the next word.
4. **The presentation multiplies the accumulator by a level in D-RAM 0x06** (0x86 for unit 1). With a sine in
   0x06, DO1 carried products of the sines (110, 550, 770, 990 Hz; runs `h3`..`h5`). 0x06 holds 0x7FFFFF.
5. **The input stage deposits the tone generator's mix** at the pointer's value at frame start + 2 and + 5
   (`IN_LATCH_L_OFF`/`_R_OFF`); here that is 0x0C and 0x0F. No sample cell may be there.
6. **Coefficients scale as Q1.22**: product = coef x L >> 6, datum = acc >> 16, so 0x400000 is unity and
   0x200000 is 0.5.

`UPD6383_PRESENT_ASIS=1` makes the two presentation words (`E30.C.00.404` unit 0 -> DO1, `A3C.D.9F.287`
unit 1 -> DO2) count as decoded and present the accumulator through that level, without their own undecoded
arithmetic. Without it every frame holding them is discarded and DO stays 0.

## Files

| file             | question it answers / what it does                                                                  |
|------------------|-----------------------------------------------------------------------------------------------------|
| `upd6383_asm.py` | builds `UPD6383_TESTPROG` files from the decoded word forms (library)                               |
| `mix4_test.py`   | writes the mixer test program: `python3 mix4_test.py OUT.txt 300000 [LOG]`                          |
| `run_test.sh`    | runs a test program on the KN5000 DSP1 build: `./run_test.sh OUT.txt DIR [SECONDS]`                 |
| `tones.py`       | does the speaker capture carry the four tones, and nothing else? `python3 tones.py DIR/out.wav 7.0` |
| `dolog.py`       | does DO1 itself? needs `LOG` = 1: `python3 dolog.py DIR/run.log`                                    |
| `dspcfg.lua`     | sets DSPCFG (the IC311 insert) to `DSPCFG_VALUE` from the autoboot script                           |
| `subram_use.lua` | which sub-CPU DRAM the firmware writes after boot (`SR_FROM`/`SR_TO`)                               |

To reproduce `h8` (needs the DSP1 build: `ARCHOPTS=-DKN5000_ENABLE_DSP1=1 BUILD_TREE=... ./build.sh`; the
binary used was md5 `ee376e17c5b92cbc8958eb201d6c9ec8`):

    python3 mix4_test.py ~/compartilhado/tmp/kn5000dsp/mix4g.txt 300000
    ./run_test.sh ~/compartilhado/tmp/kn5000dsp/mix4g.txt ~/compartilhado/tmp/kn5000dsp/h8 10
    python3 tones.py ~/compartilhado/tmp/kn5000dsp/h8/out.wav 7.0

`h7` is the same with `LOG` = 1 and 7.0 s, read by `dolog.py`. The per-word trace is
`UPD6383_TRACE_FRAME=300010 UPD6383_TRACE_DETAIL=1 EXTRA=-log ./run_test.sh ...`; it is written to
`error.log` in `~/compartilhado/kn7000-emulator` ("TIME-ORDERED FRAME TRACE").

`-wavwrite` on the KN5000 writes three channels: the first is silent, the last two are the speakers.

## Limits

This is the emulator's model of the chip. It is not the chip. Items 1, 2 and 4 are the core's readings of
words whose arithmetic is not decoded: the CALL and its rebase are modelled from the shipped kernel, and the
presentation's level is its reading of `w73`. The program cannot be confirmed until it runs on a KN5000.

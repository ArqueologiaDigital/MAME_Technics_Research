# The effects DSP at 60 MHz, and what the KN7000's "noise" is (2026-10-21)

Two pieces of work from `notes/PLAN-2026-10-21-dsp-emulation.md`: step S3 (the clock, OVERLAY-GAPS G5) and the
noise Felipe hears in MAME (G19, D12, D2).

## The scripts

| script           | question it answers                                                                                             |
|------------------|-----------------------------------------------------------------------------------------------------------------|
| `oracle_only.sh` | does a binary still give the gate's KN7000 audio oracle (`tools/gate.sh` ORACLE_MD5), without running the gate? |

Every run's scratch goes under `~/compartilhado/tmp/dsp-noise/`, never `/tmp`.

## S3: 60 MHz

`kn7000.cpp` now runs the ADSP-21065L at 60 MHz (it was 66). The evidence for 60 is in the plan (section 1.2, "How
SDRDIV pins the clock"). Checked on the new binary, md5 `7336efbe70796a0e7de82ac3f8aed1c1`, against the published
66 MHz binary, md5 `3077b137f86844bbb8515d25c2d19008`:

| check                                             | 66 MHz                    | 60 MHz                            |
|---------------------------------------------------|---------------------------|-----------------------------------|
| `oracle_only.sh EMU OUT` (gate's audio oracle)    | `5069aeda`, = ORACLE_MD5  | `5069aeda`, = ORACLE_MD5          |
| DSPTONE `test/run_mame.sh` (technics-roms-disasm) | 10 of 10 (its README)     | 10 of 10; dead flag max 0         |
| Another World `probes/cnv/run_round3.sh OUT keys` | `keys-results-2026-10-21` | the same event log, line for line |

The two binaries' oracle WAVs are identical byte for byte, so the gate needs no re-baseline. In Another World's
run the DSP mode's intro is at -41 dBFS and the event log reports "|mix| max 925824, dead 0" as at 66 MHz. The
dead flag is 893's `0x500066D8` in both the DSPTONE and the Another World runs (`-bios v13`).

Run:

```sh
notes/dsp-noise-2026-10-21/oracle_only.sh ~/compartilhado/kn7000-emulator ~/compartilhado/tmp/dsp-noise/gor
EMU=<emu dir> technics-roms-disasm/kn7000/tools/dsptone/test/run_mame.sh ~/compartilhado/tmp/dsp-noise/dsptone
EMU=<emu dir> technics-anotherworld/kn7000/probes/cnv/run_round3.sh ~/compartilhado/tmp/dsp-noise/aw keys
```

`oracle_only.sh` repeats the gate's recipe exactly: the published `nvram/` minus IC23, the kn7000 liveness run
(which writes nvram the oracle run then reads), IC23 cleared again, then `money.lua` for 22 s. Without the liveness
run first the same binaries give `3f7a5dd2` instead (both clocks alike): the oracle depends on that nvram.

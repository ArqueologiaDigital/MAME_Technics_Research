# Light DSP checks behind PLAN-2026-10-21-dsp-emulation.md

Two questions the plan needed measured rather than read from the code. Both run on the published emulator
(`~/compartilhado/kn7000-emulator/kn7000`, md5 `3077b137f86844bbb8515d25c2d19008`, overlay `a9e822a`), BIOS
default (v16), no media, fresh nvram and cfg, `-nothrottle -sound none`.

| script          | question it answers                                                                               |
|-----------------|---------------------------------------------------------------------------------------------------|
| `g3_state.lua`  | G3: after a save state is loaded in a new session, does the effects DSP's kernel still run?      |
| `dsp_alive.lua` | does the SHARC kernel run on this machine at 30 s, and how many frames a second?                 |
| `run_checks.sh` | runs both: `./run_checks.sh OUT [machine...]` (OUT under `~/compartilhado/tmp/`, never `/tmp`)    |

## The signals

- **G3** reads DM `0xC003`, where the panel reverb (unit 0) stores its I6 pointer every frame: it changes every
  frame while the kernel runs and stands still when it does not (the same signal as DSPTONE's `tone_tap.lua`).
  Ten samples over one second before the save (the control: it must move) and ten over the first second after
  the load in a new session. Pass = at least 9 distinct values of 10 after the load.
- **Alive** counts the kernel's writes to IOSTAT (DM `0x2F`; rec04 writes it twice a frame, FLAG4 high at the
  frame's start and low at its end) for one emulated second from t = 30 s. A running kernel at 44.1 kHz gives
  88,200; a SHARC still held in host boot gives 0, with its PC at the reset vector `0x8004`. The PC samples fall
  at video-frame times, which are a whole number of DSP frames apart (735), so they all land at one point of
  the frame: they show where the kernel is at that point, not that it is stuck.

## Results, 2026-10-21

```
G3 save t=30.000 distinct=10 of 10 values=2581B,24402,235A7,2218E,21333,201F9,644D0,63675,6225C,61401 pc=807A x10
G3 load t=30.967 distinct=1 of 10 values=602C7 x10 pc=807A x10
ALIVE kn7000 t0=30.000 t1=31.000 iostat_writes=88200 per_s=88200.0 pc=807A x8
ALIVE kn6000 t0=30.000 t1=31.000 iostat_writes=88200 per_s=88200.0 pc=8089 x8
ALIVE kn6500 t0=30.000 t1=31.000 iostat_writes=88200 per_s=88200.0 pc=8D40 x8
ALIVE kn2400 t0=30.000 t1=31.000 iostat_writes=0 per_s=0.0 pc=8004 x8
```

- **G3 is confirmed by a run**: the kernel stops after a state load (one value of DM `0xC003` in ten samples). The
  cause is the one OVERLAY-GAPS G3 names from the code: `m_dsp_running` is not saved, so `dsp_audio_tick`
  returns before raising IRQ0. The G3 pair reproduced bit for bit on a second run (`run_checks.sh`, same values).
- **KN6000 and KN6500 run the kernel** at the fixed 44.1 kHz tick (they inherit the KN7000's DSP and keep the
  fixed timer, `m_kn7000_timing = false`). The KN6500's sample point falls inside unit 9's program (PM `0x8D40`).
- **KN2400 never releases the SHARC**: no frame at 30 s, PC at the reset vector. Its firmware does not complete a
  host boot of the 21065L the machine inherits; which DSP the KN2400 really has is not identified.

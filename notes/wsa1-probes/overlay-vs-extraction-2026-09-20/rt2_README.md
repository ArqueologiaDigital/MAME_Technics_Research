# sched.lua -- IS THE SX-WSA1R's RTOS SCHEDULER ENTERED AT ALL?

Suggested permanent home: `kn7000_mame/notes/wsa1-probes/`.
⚠ THIS DIRECTORY IS SCRATCH. It must be committed; /tmp does not survive a reboot.

## The question it answers

prom_a's IRQ_Epilogue at 0xF857B7 decides, on EVERY interrupt return, whether to
run the task scheduler. It decides by reading TLCS-900 control register 0x3C,
INTNEST, the interrupt nesting counter (unidasm -arch tlcs900, base 0xF80000):

    f857b7  push WA
    f857b8  ldc  WA,cr3C          <- INTNEST
    f857bb  cp   WA,1
    f857bd  jr   Z,0xf857c1       <- outermost interrupt: go to the scheduler
    f857bf  pop  WA
    f857c0  reti                  <- otherwise: just return, no reschedule
    f857c1  xor  WA,WA
    f857c3  ldc  cr3C,WA          <- zero it
    f857cc..f857d2  push XHL/XWA/XBC/XDE/XIX/XIY/XIZ
    f857d3  jrl  0xf85715         <- Kernel_Dispatch

Kernel_Dispatch itself re-reads it (f85715 `ldc WA,cr3C` / `or WA,WA` /
`jr NZ,0xf85763`) and refuses to reschedule unless it is 0, and the soft-timer
service brackets its callbacks with `inc` (f8576c) / `dec` (f8579d) on the same
register.

So: if cr 0x3C is not a real counter that the CPU increments on interrupt
acceptance and decrements on RETI, `cp WA,1` can never match and the RTOS is
never entered.

## The signal read

CPU 1 PROGRAM-SPACE reads. An opcode fetch goes through the space, so a read tap
counts executions:

  * `0xF857BE-0xF857BF` -- the `jr Z` operand: reached on BOTH paths, the denominator.
  * `0xF857D2-0xF857D3` -- inside the push block that only the INTNEST==1 branch
    reaches. The nearest unrelated code is 0x12 bytes away, clear of RDOP()'s
    4-byte prefetch (tlcs900.cpp).

Ranges are word-aligned: `install_read_tap` throws on an odd range. The taps are
held in a GLOBAL (`TAPS`); a local is garbage-collected and silently stops firing.

## Run it

    WORKING (overlay):
      ~/compartilhado/kn7000_mame_build/kn7000 wsa1r \
        -rompath ~/compartilhado/kn7000-emulator/roms -window -skip_gameinfo \
        -seconds_to_run 20 -autoboot_script sched.lua -autoboot_delay 0

    STALLING (upstream extraction, branch technics-wsa1-driver):
      /tmp/claude-1000/wsa1drv/wsa1 wsa1r -rompath <symlink rompath> -window \
        -str 130 -seconds_to_run 130 -autoboot_script sched.lua -autoboot_delay 0

(The extraction's ROM_LOAD names differ from the overlay's, so it needs its own
rompath of SYMLINKS. Never copy a ROM image.)

## What the numbers mean

PASS = `scheduler` tracks `epilogue` 1:1.

Measured 2026-09-20:

    overlay      t=22 s   epilogue 35150   scheduler 35127    ratio 1.000
    extraction   t=147 s  epilogue  9708   scheduler     0    ratio 0

Zero, not late: 9,708 epilogue arrivals and not one reschedule. The overlay needs
one arrival to enter. This is immune to the extraction's 16x-slow timebase, which
is why it is the right instrument for separating "late" from "never".

CAUSE: `grep -c intnest /tmp/claude-1000/wsa1drv/src/devices/cpu/tlcs900/tlcs900.h`
returns 0. Upstream's 900tbl.hxx p_CR16 decodes only the DMA registers and sends
everything else -- including 0x3C -- to `m_dummy`, the shared "illegal register
reference" scratch word, which nothing increments.

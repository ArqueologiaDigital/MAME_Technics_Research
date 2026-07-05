# Boot performance & the main-CPU clock

Investigation of the "slow boot / screen slowly fills with green" behaviour.

## The green fill is NOT a failed image decode

Measured facts (probes in the MN10300 core + driver, boot traced to ~44 s):

- The LCD framebuffer is 640x240 8bpp at workram 0x500D4080, resolved through a
  256-entry CLUT at 0x50031490 (0x00BBGGRR). **Palette index 0x0C = 0x0038FF68 =
  bright green (R68 G FF B38)** -- this is the colour the whole screen fills with
  during boot and the colour of the central "picture" box on normal screens.
- The **picture flash at 0x57800000 is NEVER accessed during boot** (a counting
  read handler over the whole 8 MB window logged 0 reads in 45 emulated seconds).
  So the green is not a mis-mapped/undumped background image being decoded from
  garbage -- the firmware simply doesn't fetch a boot picture. Index 0x0C is the
  framebuffer's default/background fill.
- The boot hot loop (PC sampling: ~41% of cycles at 0x4840FB40-0x4840FCC8, ~15%
  at 0x48486xxx) is a legitimate decompressor. Instrumenting its memory reads
  shows it reads **valid, varied data** from workram (0x50173Dxx source,
  0x50173Bxx 16-bit table, 0x50173A08 dest) -- not constant 0x00/0xFF garbage.
  It is decoding real UI resources, not "chewing invalid data".

Conclusion: the green screen and the multi-second boot are both normal firmware
behaviour (background clear + a lot of real resource decompression), NOT a bug
from a wrong image address or an invalid-data decode loop.

(Caveat on tooling: `unidasm` mis-decodes MN10300 opcode 0xF4 `movbu (di,am),dn`
as 1 byte instead of 2, desyncing addresses after it -- so the loop's internal
disassembly is unreliable; the measurements above come from live execution.)

## Why it *looked* slow: the CPU clock was a 10 MHz placeholder

Boot is ~400M CPU cycles of real work. At the old 10 MHz placeholder that is
~40 emulated seconds; throttled, ~40 wall seconds. The real clock is higher.

### The clock, from the service manual (SCHEMATIC DIAGRAM-1, MAIN 1/5)

- Main CPU: **IC4 = MN103002A** (MN10300 / AM33 32-bit micro-controller).
- Reference crystal: **X1 = 16.0 MHz** (part `H0J160500026`). The `H0J<freq*10>`
  code family is consistent across the board's other crystals:
  X102 `H0J177`=17.73 MHz, X103 `H0J240`=24.0 MHz, X104 `H0J143`=14.32 MHz
  (17.73 and 14.32 are the PAL/NTSC colour-subcarrier x4 video clocks).
- Clock generator: **IC6 = C02BZ0000667** (pins XIN/XOUT + crystal, FRSEL/S1/S2
  select, SSCLK output). SSCLK -> R36 47R -> **IC11 = TC7WH74 D-flip-flop wired
  /2**, which clocks peripherals. The CPU is not the /2 branch (8 MHz would be
  absurd for a 2003 flagship that boots in ~12-15 s).
- Other oscillators on the board: X105 50 MHz and X103 24 MHz feed the DSP /
  tone-generator clock section (CLK1/CLK12/CLK13); X1101 4 MHz is the CPL panel
  sub-CPU; audio master is 11.2896 MHz (256 x 44.1 kHz).

### Chosen value: 32 MHz (16 MHz x2 internal PLL)

The AM33 runs the 16 MHz reference through its internal PLL. x2 = 32 MHz is the
common config and matches the measured workload: 400M cycles / 32 MHz ~= 12.5 s,
which is the real machine's boot time. Set in the driver as `16_MHz_XTAL * 2`.

Verified: full boot, panel handshake, and home-screen render all intact at
32 MHz; boot now reaches home in ~12-13 emulated seconds. Host sustains ~46M
cycles/s (measured), so throttled real-time playback is achievable.

### CONFIRMED by firmware MIDI-baud cross-check (2026-07-05)

The peripheral clock is pinned to 16.000 MHz exactly, and fc = 32 MHz confirmed:
- The MIDI init at 0x484B2793 programs SC1/SC2 (0x34000810/0x34000820) to 8N1
  (control = 0x0085 / 0x1181), with SC1's clock-source field CK = 0x5 =
  "Timer-3 underflow / 8".
- The timer setup at 0x484B2691 sets TM3MD = 0x80 (count enable, source = IOCLK)
  and TM3BR = 0x3F (63) (reload byte from ROM table 0x4874C4F4). SC2's own
  divisor at 0x3400082D is also 0x3F.
- MIDI baud is exactly 31250, so with baud = IOCLK / (8 * (TM3BR+1)):
    31250 = IOCLK / (8 * 64) = IOCLK / 512  =>  IOCLK = 16.000 MHz exactly.
  Inverting the real MN10300 driver's formula at each candidate: 16 MHz needs
  TM3BR = 0x3F (matches!), 32 MHz would need 0x7F, 40/48 MHz 0x9F/0xBF -- so
  only 16 MHz IOCLK fits.
- fc = 2 x IOCLK = 32.000 MHz (schematic /2 peripheral branch via IC11; the
  MN10300 IOCLK = fc/2 convention). This upgrades the previously-inferred 32 MHz
  to a cross-checked result. The only remaining assumption is the fc = 2*IOCLK
  ratio, which rests on the schematic /2 topology + the MN10300 convention +
  the boot-timing match (400M cycles / 32 MHz ~= 12.5 s = real boot time).

Driver: `MN10300(config, m_maincpu, 16_MHz_XTAL * 2)`.

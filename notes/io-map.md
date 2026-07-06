# KN7000 I/O register map (from firmware static analysis)

Every absolute I/O access (`movbu`/`movhu`/`mov`/`bset`/`bclr`/`btst` to a
`(0xADDR)` operand outside the ROM/RAM ranges) in both code regions of
`kn7000_program.rom`, tabulated by bank. Access width is inferred from the
instruction (`movbu`=8, `movhu`=16, `mov`=32, bit-ops=bit); the count is how
many distinct code sites touch that register. This is what the MAME driver's
memory map should decode.

**112 distinct I/O registers** across the banks below.

## `0x20000000` — small register block (0x20000070 is the port the reset code writes 0x30/0x03 to)

| register | width | access sites |
|----------|-------|--------------|
| `0x20000000` | 16 | movhu×1 |
| `0x20000004` | 16 | movhu×1 |
| `0x20000008` | 16 | movhu×1 |
| `0x2000000C` | 16 | movhu×1 |
| `0x20000010` | 16 | movhu×1 |
| `0x20000014` | 16 | movhu×1 |
| `0x20000018` | 16 | movhu×1 |

## `0x32000000` — system / timers (0x40/0x42 loaded with 0x497/0xEA6 timing values at reset; 0x800 is a 32-bit counter, read 78x)

| register | width | access sites |
|----------|-------|--------------|
| `0x32000010` | 16 | movhu×1 |
| `0x32000020` | 16 | movhu×12 |
| `0x32000022` | 16 | movhu×2 |
| `0x32000024` | 16 | movhu×2 |
| `0x32000026` | 16 | movhu×16 |
| `0x32000028` | 16 | movhu×3 |
| `0x3200002A` | 16 | movhu×2 |
| `0x3200002C` | 16 | movhu×1 |
| `0x3200002E` | 16 | movhu×12 |
| `0x32000040` | 16 | movhu×5 |
| `0x32000042` | 16 | movhu×3 |
| `0x32000800` | 32 | mov×78 |
| `0x32000804` | 32 | mov×4 |
| `0x32000808` | 32 | mov×4 |
| `0x3200080C` | 16 | movhu×4 |

## `0x34000000` — large peripheral register block (58 regs)

The `0x108..0x280` dense 16-bit writes are the LCD/display controller (+ the
interrupt-controller array `0x148..0x178`). The **byte sub-block `0x800..0x82d`
is a multi-channel USART/SIO ASIC** — three channels at `+0x10` stride, each with
`cfg(base)` / `ctrl(+4)` / `TX(+8)` / `RX(+9)` / `status(+C)`:

* **`0x34000800` = the control-panel serial link** (CPL/CPC/CPR/CPSD sub-CPUs),
  ISR `0x484ACC13`, ICR `0x34000168` — see the Control Panel Protocol doc.
* **`0x34000810` = MIDI port 1** (ISR `0x484B1E86`, ICR `0x34000148`).
* **`0x34000820` = MIDI port 2** (ISR `0x484B2037`, ICR `0x34000150`).

Full per-register list below.

| register | width | access sites |
|----------|-------|--------------|
| `0x34000108` | 16 | movhu×2 |
| `0x3400010C` | 16 | movhu×2 |
| `0x34000110` | 16 | movhu×2 |
| `0x34000114` | 16 | movhu×2 |
| `0x34000118` | 16 | movhu×7 |
| `0x3400011C` | 16 | movhu×5 |
| `0x34000120` | 16 | movhu×2 |
| `0x34000124` | 16 | movhu×2 |
| `0x34000128` | 16 | movhu×2 |
| `0x34000130` | 16 | movhu×2 |
| `0x34000134` | 16 | movhu×2 |
| `0x34000138` | 16 | movhu×2 |
| `0x3400013C` | 16 | movhu×9 |
| `0x34000140` | 16 | movhu×5 |
| `0x34000144` | 16 | movhu×5 |
| `0x34000148` | 16 | movhu×8 |
| `0x3400014C` | 16 | movhu×6 |
| `0x34000150` | 16 | movhu×8 |
| `0x34000154` | 16 | movhu×6 |
| `0x3400015C` | 16 | movhu×4 |
| `0x34000160` | 16 | movhu×10 |
| `0x34000164` | 16 | movhu×9 |
| `0x34000168` | 16 | movhu×25 |
| `0x3400016C` | 16 | movhu×6 |
| `0x34000170` | 16 | movhu×14 |
| `0x34000174` | 16 | movhu×2 |
| `0x34000178` | 16 | movhu×8 |
| `0x34000200` | 16 | movhu×1 |
| `0x34000280` | 16 | movhu×15 |
| `0x34000800` | 16 | movhu×49 |
| `0x34000804` | 8 | movbu×1 |
| `0x34000808` | 8 | movbu×11 |
| `0x34000809` | 8 | movbu×2 |
| `0x3400080C` | 16 | movhu×1 |
| `0x34000810` | 16 | movhu×5 |
| `0x34000814` | 8 | movbu×1 |
| `0x34000818` | 8 | movbu×7 |
| `0x34000819` | 8 | movbu×1 |
| `0x3400081C` | 16 | movhu×1 |
| `0x34000820` | 16 | movhu×5 |
| `0x34000824` | 8 | movbu×1 |
| `0x34000828` | 8 | movbu×7 |
| `0x34000829` | 8 | movbu×5 |
| `0x3400082C` | bit | btst×8 |
| `0x3400082D` | 8 | movbu×1 |
| `0x34001000` | 8 | movbu×1 |
| `0x34001002` | 8 | movbu×1 |
| `0x34001003` | 8 | movbu×1 |
| `0x34001010` | 8 | movbu×11 |
| `0x34001012` | 8 | movbu×1 |
| `0x34001013` | 8 | movbu×1 |
| `0x34001071` | 8 | movbu×1 |
| `0x34001080` | 8 | movbu×1 |
| `0x34001082` | bit | bclr×3, bset×4, movbu×3 |
| `0x34001090` | 16 | movhu×1 |
| `0x34001092` | 16 | movhu×4 |
| `0x340010A2` | 16 | movhu×3 |
| `0x34004002` | 8 | movbu×1 |

## `0x36008000` — bit-mapped control / GPIO port - every access is bset/bclr/btst. 0x36008004 is toggled 125x (chip selects / strobes / resets)

| register | width | access sites |
|----------|-------|--------------|
| `0x36008004` | bit | bclr×52, bset×73, mov×1, movbu×4 |
| `0x36008005` | bit | bset×1 |
| `0x36008024` | bit | bclr×3, bset×18, movbu×2 |
| `0x36008025` | bit | bclr×3, bset×12, movbu×1 |
| `0x36008044` | bit | bclr×1, movbu×2 |
| `0x36008064` | bit | bclr×11, bset×8, movbu×2 |
| `0x36008065` | bit | bclr×2, movbu×1 |
| `0x36008084` | bit | btst×3 |

## `0x98000000` — SOUND subsystem, several sub-blocks: 0x98040000 & 0x98050000 are PARALLEL 16-bit register sets (0x00..0x10) = the dual tone generators (main TG IC203/204 + sub TG IC207/208); 0x98020000 byte regs; 0x98070000; 0x98010000/0x98060000 byte control

| register | width | access sites |
|----------|-------|--------------|
| `0x98000000` | 16 | movhu×1 |
| `0x98010000` | 8 | movbu×3 |
| `0x98020004` | 8 | movbu×10 |
| `0x98020008` | 8 | movbu×5 |
| `0x9802000A` | 8 | movbu×4 |
| `0x9802000E` | 8 | movbu×13 |
| `0x98040000` | 16 | movhu×5 |
| `0x98040002` | 16 | movhu×6 |
| `0x98040004` | 16 | movhu×3 |
| `0x98040006` | 16 | movhu×3 |
| `0x98040008` | 16 | movhu×1 |
| `0x9804000A` | 16 | movhu×1 |
| `0x98040010` | 16 | movhu×3 |
| `0x98050000` | 16 | movhu×3 |
| `0x98050002` | 16 | movhu×4 |
| `0x98050004` | 16 | movhu×6 |
| `0x98050006` | 16 | movhu×3 |
| `0x98050008` | 16 | movhu×1 |
| `0x9805000A` | 16 | movhu×1 |
| `0x9805000C` | 16 | movhu×6 |
| `0x9805000E` | 16 | movhu×3 |
| `0x98050010` | 16 | movhu×3 |
| `0x98060000` | 8 | movbu×6 |
| `0x98070000` | 16 | movhu×14 |

## Register-indirect bases

Some peripherals are addressed through an address register loaded with an
immediate base (`mov 0xBASE, aN` then `mov ..,(aN)`), so they don't appear as
absolute operands above. Bases seen in the code include `0x20000000`,
`0x20000070`, `0x24000000`, `0x28000000`/`0x28400000`/`0x28401000`,
`0x2C000000`, and `0x98010000` — likely DMA/bus windows or bulk-transfer
ports (e.g. wave ROM / SD / video). These need data-flow tracing to pin down.

## Boot execution trace (mn10300_sim)

Running the firmware from reset in the `mn10300_sim` interpreter
(`kn7000_disassembly/tools/mn10300_sim.py`) executes **3.06 million instructions
coherently** before reaching the first region we can't model. The boot's
hardware-init I/O sequence (22 registers) is:

1. GPIO/control `0x36008024=0xFE`, `0x36008044=0x02`, `0x36008004=0x02`,
   `0x36008064=0xBF`, then a reset pulse (`bset`/`bclr 0x20` on `0x36008004`)
2. `0x20000070` ← `0x30` then `0x03`
3. Timers: `0x32000040=0x497`, `0x32000042=0xEA6`, `0x32000028=0x865`, then a
   read-modify-write of `0x32000020` (`|0x804`), `0x32000010=0x400`
4. Reads `0x98070000` (sound status), reprograms the `0x32000020`-`0x3200002E`
   timer block, repeats the GPIO init, then `0x34000280=0xFFFF`, `0x98060000=0xFF`

**Memory regions discovered by execution** (not in the static map above):
work RAM extends past `0x50298000` (>2.5 MB), and there are device windows at
`0x90000000` and `0x8C000000` (the boot copies data from the top of the program
ROM into them) — likely the LCD V-RAM / video / wave-DMA windows.

### How far the boot gets

Once those device windows are backed with scratch RAM, the interpreter runs
**4,589,920 instructions** — completing hardware init and BSS setup and entering
the **MILK kernel in code region 2** (`0x487B8xxx`) — before it makes its first
call into the self-loaded library ROM (`0x4C03CC4E`, from kernel code at
`0x487B8D52`). That call is the hard frontier: with `--hle-lib` the library calls
are stubbed (return 0), and the kernel diverges after only **2** of them
(`0x4C03CC4E` d1=`0x15`, then `0x4C03BB8F` d0=`0x1F4`), because it immediately
uses their return values (pointers). So the library/kernel ROM at `0x4C000000` is
required from the very start of kernel initialisation. **NB:** that ROM is **not
undumped** — the boot self-loads it from the program flash into `0x8C000000`
(aliased to `0x4C000000`); see [`library-rom-loading.md`](library-rom-loading.md)
and [`library-rom-api.md`](library-rom-api.md).

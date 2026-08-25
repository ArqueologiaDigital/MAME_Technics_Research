#!/usr/bin/env python3
"""What does the SX-WSA1's CPU 1 RESET write to each port, and at which address?

QUESTION THIS ANSWERS.  src/mame/matsushita/wsa1.cpp seeds its CPU-1 port
shadows with the values the firmware's own RESET writes, and the floppy block
comment leans on two of them:

  * PB bit 3 IDLES LOW, which is what makes PortB3_Pulse (0xFE594C) a genuine
    low-high-low pulse and therefore consistent with an active-high TC input;
  * PA bit 3 comes up HIGH, which is what makes "PA bit 3 is an active-high
    drive motor enable" an awkward reading -- operation 7, issued before a
    transfer, sets a pin that RESET already set.

Both are quoted with ROM addresses in the driver, so they have to be
re-derivable.  This script disassembles the `ldio <sfr>,<imm8>` run in CPU 1's
RESET port block straight out of the ROM image and asserts the four
instructions the driver names.

    python3 wsa1_port_reset_writes.py [path/to/qsigcwsa1ax.ic12]

Default path is ../../../kn7000_mame_build/roms/wsa1r/qsigcwsa1ax.ic12 relative
to this file.  The A image is mapped at 0xF80000 on CPU 1 (wsa1.cpp's
cpu1_map), so file offset = address - 0xF80000.

Exit status is non-zero if any assertion fails.
"""

import os
import sys

BASE = 0xF80000
START, END = 0xF826A9, 0xF82800          # RESET through the end of the port/timer block

# TMP95C061 internal I/O addresses, from wsa1-roms-disasm/include/tmp95c061_sfr.inc
SFR = {
    0x01: "P1",   0x04: "P1CR",  0x06: "P2",    0x09: "P2FC",
    0x0d: "P5",   0x0e: "P5CR",  0x0f: "P5FC",  0x10: "P6",
    0x11: "P7",   0x12: "P6",    0x13: "P7",    0x15: "P6FC",
    0x16: "P7CR", 0x17: "P7FC",  0x18: "P8",    0x19: "P9",
    0x1a: "P8CR", 0x1b: "P8FC",  0x1e: "PA",    0x1f: "PB",
    0x20: "TRUN", 0x22: "TREG0", 0x23: "TREG1", 0x24: "T01MOD",
    0x25: "TFFCR", 0x26: "TREG2", 0x27: "TREG3", 0x28: "T23MOD",
    0x2c: "PACR", 0x2d: "PAFC",  0x2e: "PBCR",  0x2f: "PBFC",
    0x71: "INTE45", 0x79: "INTETC01", 0x7c: "DMA0V",
}

# The four instructions the driver names, address -> (sfr, value)
EXPECT = {
    0xF826D6: (0x1e, 0xf9),   # ldio PA,0xF9    -- PA bit 3 comes up HIGH
    0xF826DC: (0x2c, 0x0e),   # ldio PACR,0x0E  -- PA bits 1, 2, 3 are outputs
    0xF826DF: (0x1f, 0xf3),   # ldio PB,0xF3    -- PB bits 2 and 3 come up LOW
    0xF826E5: (0x2e, 0x0c),   # ldio PBCR,0x0C  -- PB bits 2 and 3 are outputs
}


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    default = os.path.join(here, "..", "..", "..", "kn7000_mame_build",
                           "roms", "wsa1r", "qsigcwsa1ax.ic12")
    path = sys.argv[1] if len(sys.argv) > 1 else default

    with open(path, "rb") as f:
        rom = f.read()

    if len(rom) != 0x80000:
        print("error: %s is %d bytes, expected 524288" % (path, len(rom)))
        return 2

    found = {}
    addr = START
    print("CPU 1 RESET, every `ldio <sfr>,<imm8>` in 0x%06X-0x%06X:" % (START, END))
    while addr < END:
        off = addr - BASE
        if rom[off] == 0x08:                       # ldio <8-bit io>,<imm8>
            sfr, val = rom[off + 1], rom[off + 2]
            name = SFR.get(sfr, "SFR_%02X" % sfr)
            print("  0x%06X  08 %02x %02x   ldio %-9s 0x%02X" % (addr, sfr, val, name + ",", val))
            found[addr] = (sfr, val)
            addr += 3
        else:
            addr += 1

    fails = 0
    print()
    for a in sorted(EXPECT):
        want = EXPECT[a]
        got = found.get(a)
        ok = (got == want)
        fails += 0 if ok else 1
        print("  [%s] 0x%06X ldio %s,0x%02X" %
              ("PASS" if ok else "FAIL", a,
               SFR.get(want[0], "SFR_%02X" % want[0]), want[1]),
              "" if ok else ("-- found %r" % (got,)))

    # The two facts the driver's floppy block comment actually rests on.
    pa = found.get(0xF826D6, (0, 0))[1]
    pb = found.get(0xF826DF, (0, 0))[1]
    for cond, text in (((pa >> 3) & 1 == 1, "PA bit 3 comes up HIGH  (PA = 0x%02X)" % pa),
                       ((pb >> 3) & 1 == 0, "PB bit 3 comes up LOW   (PB = 0x%02X)" % pb)):
        fails += 0 if cond else 1
        print("  [%s] %s" % ("PASS" if cond else "FAIL", text))

    print("\n%d check(s) failed" % fails)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

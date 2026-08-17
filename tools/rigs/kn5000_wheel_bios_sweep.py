#!/usr/bin/env python3
"""Which KN5000 program-ROM revisions put the encoder scan table at 0x8E94?

QUESTION ANSWERED
-----------------
The TEMPO/PROGRAM data-wheel HLE deposits a 3-byte scan-table entry plus a
terminator at main-CPU DRAM 0x8E94.  0x8E94 was read out of the v10 firmware.
The kn5000 driver, however, offers EIGHT BIOS options (v3..v10, six of them
dumped), and DRAM layout is not stable across them.  This probe answers:

  * for each dumped program ROM, where is the encoder scan table really?
  * is 0x8E94 live memory in the revisions that use a different table?

SIGNAL BEING READ
-----------------
Each revision contains exactly three references to its own scan-table address,
all in the 0xFB0000-0xFD0000 code region:

  1. the poll's own load                  (Encoder_ValueScanAndSync)
  2. the address helper   "f1 lo hi 33 0e" = LDA XHL,(imm16); RET
  3. the idle-discipline clear "f1 lo hi 00 ff" = LD (imm16),0xFF

The helper + clear pair uniquely identifies the table, so we enumerate every
`LDA XHL,(imm16); RET` in the code region and keep the one whose address also
has a matching `LD (imm16),0xFF`.

PASS/FAIL
---------
The wheel HLE as written is correct only for revisions whose table == 0x8E94.
Any revision reported with a different table is a revision where the poke is
BOTH inert (the firmware polls elsewhere) AND unsound (it writes into whatever
that revision keeps at 0x8E94).

RUN
---
    python3 tools/rigs/kn5000_wheel_bios_sweep.py [rom_dir]

Default rom_dir: ~/compartilhado/kn5000_original_roms/kn5000

RESULT RECORDED 2026-08-17 (see the adversarial review of the wheel PR):

    v5  -> 0x8DD4   helper 0xFC6047   ** 0x8E94 is a LIVE variable (LD (0x8E94),0x05 @0xFC64D3)
    v6  -> 0x8DD4   helper 0xFC638E   ** 0x8E94 is a LIVE variable (LD (0x8E94),0x05 @0xFC681A)
    v7  -> 0x8DF8   helper 0xFC6484   ** table moved; 0x8E94 not directly referenced
    v8  -> 0x8E94   helper 0xFC6C4F   OK
    v9  -> 0x8E94   helper 0xFC6C4F   OK
    v10 -> 0x8E94   helper 0xFC6C4F   OK   (ROM_DEFAULT_BIOS)
"""

import os
import re
import sys

# The 2MB program ROM is mapped at 0xE00000..0xFFFFFF on the main CPU.
BASE = 0xE00000
CODE_LO, CODE_HI = 0xFB0000, 0xFD0000
POKE_ADDR = 0x8E94  # what src/mame/matsushita/kn5000.cpp hardcodes

ROMS = [
    "kn5000_v5_program.rom",
    "kn5000_v6_program.rom",
    "kn5000_v7_program.rom",
    "kn5000_v8_program.rom",
    "kn5000_v9_program.rom",
    "kn5000_v10_program.rom",
]


def find_table(data):
    """Return (table_addr, helper_addr) for the encoder scan table, or None."""
    for m in re.finditer(rb"\xf1(.)(.)\x33\x0e", data, re.S):
        helper = BASE + m.start()
        if not (CODE_LO <= helper < CODE_HI):
            continue
        table = (data[m.start() + 2] << 8) | data[m.start() + 1]
        clear = bytes([0xF1, table & 0xFF, table >> 8, 0x00, 0xFF])
        if clear in data:  # the idle-discipline "LD (table),0xFF"
            return table, helper
    return None


def refs_to(data, addr):
    """Every `f1 lo hi` direct-addressing reference to a 16-bit DRAM address."""
    pat = bytes([0xF1, addr & 0xFF, addr >> 8])
    return [BASE + m.start() for m in re.finditer(re.escape(pat), data)]


def main():
    rom_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser(
        "~/compartilhado/kn5000_original_roms/kn5000")

    bad = 0
    for name in ROMS:
        path = os.path.join(rom_dir, name)
        if not os.path.exists(path):
            print("%-28s MISSING (%s)" % (name, path))
            continue
        data = open(path, "rb").read()

        found = find_table(data)
        if found is None:
            print("%-28s no encoder scan table found" % name)
            bad += 1
            continue
        table, helper = found

        note = "OK" if table == POKE_ADDR else "** MISMATCH **"
        print("%-28s table=0x%04X helper=0x%06X  %s" % (name, table, helper, note))

        if table != POKE_ADDR:
            bad += 1
            others = refs_to(data, POKE_ADDR)
            if others:
                bytes_at = []
                for a in others:
                    o = a - BASE
                    bytes_at.append("%06X:%s" % (a, data[o:o + 5].hex(" ")))
                print("%-28s   0x%04X IS LIVE HERE: %s"
                      % ("", POKE_ADDR, "  ".join(bytes_at)))
            else:
                print("%-28s   0x%04X has no direct reference in this revision"
                      % ("", POKE_ADDR))

    print()
    print("revisions incompatible with a hardcoded 0x%04X poke: %d" % (POKE_ADDR, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

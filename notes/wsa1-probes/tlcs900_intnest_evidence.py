#!/usr/bin/env python3
"""
tlcs900_intnest_evidence.py -- WHICH FIRMWARES TOUCH THE TLCS-900 INTERRUPT
NESTING COUNTER, AND IN WHICH DIRECTION?

The question this answers
-------------------------
Control register INTNEST is the TLCS-900's interrupt nesting counter: the CPU
increments it when it accepts an interrupt and decrements it on RETI, so a
handler can ask "am I the outermost interrupt?" without keeping its own count.
MAME had no such register -- 900tbl.hxx's p_CR16 decoded only the DMA counters
and sent everything else to m_dummy, the shared "illegal register reference"
scratch word.

Implementing it changes behaviour for EVERY tlcs900 machine, so before adding
the increment we had to know, per firmware, whether it reads the register,
writes it, or ignores it.  This script answers that from the ROM bytes, not
from a reading of the disassembly.

    a firmware that READS it    -- its control flow depends on the count
    a firmware that only WRITES -- the count cannot be observed; adding the
                                   hardware increment cannot change its behaviour
    a firmware that ignores it  -- unaffected either way

Control-register number, by core generation:

    0x3C   TLCS-900/H    TMP96C141, TMP95C061, TMP95C063
    0x7C   TLCS-900/H1   TMP94C241

Those two numbers are what the DMA register layout forces.  MAME decodes the
/H at DMAS 0x00-0x0C, DMAD 0x10-0x1C, DMAC 0x20-0x2C, DMAM 0x22-0x2E and the
/H1 at DMAS 0x00-0x0C, DMAD 0x20-0x2C, DMAC 0x40-0x4C, DMAM 0x42-0x4E -- the
/H1 map is the same registers for EIGHT channels instead of four, which pushes
INTNEST from 0x3C to 0x7C.  The output below is the confirmation: the SX-WSA1R
firmware (TMP95C061) uses 0x3C and never 0x7C, the KN5000 firmware (TMP94C241)
uses 0x7C and never 0x3C, and each uses its own family's DMA numbers alongside.

How it reads the ROM
--------------------
LDC on the TLCS-900 is a register-prefix opcode followed by 0x2E or 0x2F and
then the control-register number:

    prefix 0xC8-0xCF   8-bit  register   (LDCBRR)
    prefix 0xD8-0xDF   16-bit register   (LDCWRR)
    prefix 0xE8-0xEF   32-bit register   (LDCLRR)
    second byte 0x2E   ldc <cr>,R        -- WRITE to the control register
    second byte 0x2F   ldc R,<cr>        -- READ from the control register

Verified against the disassembly: prom_a 0xF85715 is `d8 2f 3c` (read) and
0xF8E9A8 is `db 2e 3c` (write), matching wsa1-roms-disasm's
`m_ldc_reg_cr` / `m_ldc_cr_reg` at those addresses.

This is a flat byte scan, so it can produce false positives inside data: a
three-byte coincidence in a font or a sample table looks like an LDC.  That is
why the summary only claims the two 16-bit numbers, which land in code and
whose counts agree exactly with the disassembled kernels; treat the full table
as a lead, not a census.

Run it
------
    python3 notes/wsa1-probes/tlcs900_intnest_evidence.py            # default ROM sets
    python3 notes/wsa1-probes/tlcs900_intnest_evidence.py FILE...    # any ROMs
    python3 notes/wsa1-probes/tlcs900_intnest_evidence.py --all      # every CR, not just INTNEST

Result recorded 2026-08-25 (the numbers the C++ comments quote):

    wsa1_prom_a.ic12     cr 0x3C  4 reads, 6 writes   the RTOS kernel + SWI7 dispatch
    wsa1_prom_c.ic28     cr 0x3C  4 reads, 5 writes   the same kernel, second CPU
    wsa1_prom_b.ic13     cr 0x3C  none
    wsa1_prom_d.bin      cr 0x3C  none
    kn5000 v7/v9/v10     cr 0x7C  0 reads, 6 writes   ** WRITE-ONLY **
    kn5000 subprogram    cr 0x7C  0 reads, 6 writes   ** WRITE-ONLY **
    kn5000 subcpu boot   cr 0x7C  none
    hd-ae5000            cr 0x7C  none

The KN5000 line is the decision this script was written for.  Its firmware runs
the same RTOS as the SX-WSA1R but keeps the nesting depth in a RAM word at
(1475) and only MIRRORS it into cr 0x7C -- TaskSched_TimerTick increments the
RAM word and writes the register, INTT3_CheckNesting compares the RAM word
against 1, INTT3_EnterScheduler zeroes both.  Nothing on that machine ever
reads the register back, so giving the TMP94C241 a real INTNEST that the
hardware increments cannot change what the KN5000 does.
"""

import os
import sys

# prefix byte range -> the operand width that LDC form moves
GROUPS = (
    ("byte", 0xC8, 0xCF),
    ("word", 0xD8, 0xDF),
    ("long", 0xE8, 0xEF),
)

# control register number of INTNEST, per core generation
INTNEST = {0x3C: "TLCS-900/H  (TMP96C141/TMP95C061/TMP95C063)",
           0x7C: "TLCS-900/H1 (TMP94C241)"}

SHARED = os.path.expanduser("~/compartilhado")

DEFAULT_ROMS = [
    (SHARED + "/wsa1-roms-disasm/original_ROMs/wsa1_prom_a.ic12", "TMP95C061"),
    (SHARED + "/wsa1-roms-disasm/original_ROMs/wsa1_prom_b.ic13", "TMP95C061"),
    (SHARED + "/wsa1-roms-disasm/original_ROMs/wsa1_prom_c.ic28", "TMP95C061"),
    (SHARED + "/wsa1-roms-disasm/original_ROMs/wsa1_prom_d.bin",  "TMP95C061"),
    (SHARED + "/kn5000-roms-disasm/original_ROMs/kn5000_v7_program.rom",     "TMP94C241"),
    (SHARED + "/kn5000-roms-disasm/original_ROMs/kn5000_v9_program.rom",     "TMP94C241"),
    (SHARED + "/kn5000-roms-disasm/original_ROMs/kn5000_v10_program.rom",    "TMP94C241"),
    (SHARED + "/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom", "TMP94C241"),
    (SHARED + "/kn5000-roms-disasm/original_ROMs/kn5000_subcpu_boot.ic30",   "TMP94C241"),
    (SHARED + "/kn5000-roms-disasm/original_ROMs/hd-ae5000_v2_06i.ic4",      "TMP94C241"),
]


def scan(path):
    """-> {(width, cr, 'R'|'W'): [file offsets]}"""
    data = open(path, "rb").read()
    hits = {}
    for i in range(len(data) - 2):
        second = data[i + 1]
        if second != 0x2E and second != 0x2F:
            continue
        prefix = data[i]
        for width, lo, hi in GROUPS:
            if lo <= prefix <= hi:
                key = (width, data[i + 2], "W" if second == 0x2E else "R")
                hits.setdefault(key, []).append(i)
                break
    return hits


def main(argv):
    show_all = "--all" in argv
    args = [a for a in argv if not a.startswith("--")]
    roms = [(a, "?") for a in args] if args else DEFAULT_ROMS

    print("TLCS-900 LDC control-register scan -- INTNEST is cr 0x3C (/H) or 0x7C (/H1)")
    print()
    missing = []
    for path, part in roms:
        if not os.path.exists(path):
            missing.append(path)
            continue
        hits = scan(path)
        print("== %s   [%s]  %d bytes" % (os.path.basename(path), part, os.path.getsize(path)))
        rows = sorted(hits) if show_all else \
            sorted(k for k in hits if k[0] == "word" and k[1] in INTNEST)
        if not rows:
            print("     no INTNEST access" if not show_all else "     no LDC found")
        for width, cr, rw in rows:
            offs = hits[(width, cr, rw)]
            tag = "  <-- INTNEST, %s" % INTNEST[cr] if (width == "word" and cr in INTNEST) else ""
            print("     %-4s cr=0x%02X %s  n=%-3d  at %s%s" % (
                width, cr, "write" if rw == "W" else "read ", len(offs),
                ", ".join("0x%X" % o for o in offs[:8]) + (" ..." if len(offs) > 8 else ""),
                tag))
        print()

    if missing:
        print("NOT FOUND (skipped):")
        for m in missing:
            print("   ", m)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

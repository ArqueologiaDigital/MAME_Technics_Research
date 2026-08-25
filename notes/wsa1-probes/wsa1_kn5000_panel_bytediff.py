#!/usr/bin/env python3
"""Does the WSA1's serial-channel-1 module share BYTES with the KN5000's
control-panel driver?

QUESTION THIS ANSWERS
  The SX-WSA1 and the KN5000 both carry a Mitsubishi M37471M2196S panel MCU
  (technics_roms/roms/wsa1/PROVENANCE.md).  If the WSA1's SC1 module
  (prom_b 0xF5A800-0xF5B44D) is the panel link, the obvious question is
  whether Technics reused the KN5000's driver code.  This script answers it
  by BYTES, not by shape: it reports the longest common substrings between
  the WSA1 module and the whole KN5000 v10 main-CPU program ROM, and it
  separately reports whether the KN5000's CPanel_* window shares anything.

  Run it before transplanting any KN5000 understanding.  A previous pass in
  this tree was burned by a routine that was 80 of 81 bytes identical to the
  KN5000 where the one differing byte was the peripheral base -- so "similar"
  is not a result; a byte count is.

WHAT COUNTS AS PASS
  Nothing.  This is a measurement, not a gate.  It prints numbers.

USAGE
  python3 wsa1_kn5000_panel_bytediff.py
"""
import sys, os

WSA1_PROM_B = "/home/fsanches/compartilhado/wsa1-roms-disasm/original_ROMs/wsa1_prom_b.ic13"
WSA1_PROM_A = "/home/fsanches/compartilhado/wsa1-roms-disasm/original_ROMs/wsa1_prom_a.ic12"
KN5000_MAIN = "/home/fsanches/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_v10_program.rom"

# WSA1 prom_b is linked at 0xF00000; the SC1 module is 0xF5A800..0xF5B44D code.
SC1_LO, SC1_HI = 0xF5A800, 0xF5B44E
PROM_B_BASE = 0xF00000
# KN5000 main program ROM is 2 MiB linked at 0xE00000 (0xFC3E65 -> 0x1C3E65).
KN_BASE = 0xE00000
# The KN5000 panel driver, from kn5000-roms-disasm/symbols/maincpu_v10_symbols_reference.txt:
#   CPanel_InitDispatchTable 0x00FC3E65 ... CPanel_DecEventPtr 0x00FC4C29 (ends where
#   ToneGen_IncrementWrap128 begins at 0x00FC4C34)
KN_CPANEL_LO, KN_CPANEL_HI = 0xFC3E65, 0xFC4C34


def load(p):
    with open(p, "rb") as f:
        return f.read()


def common_runs(a, b, minlen):
    """All maximal common substrings of length >= minlen, via a rolling index."""
    idx = {}
    for i in range(len(b) - minlen + 1):
        idx.setdefault(b[i:i + minlen], []).append(i)
    out = []
    i = 0
    while i <= len(a) - minlen:
        best = (0, -1)
        for j in idx.get(a[i:i + minlen], ()):
            n = minlen
            while i + n < len(a) and j + n < len(b) and a[i + n] == b[j + n]:
                n += 1
            if n > best[0]:
                best = (n, j)
        if best[0]:
            out.append((i, best[1], best[0]))
            i += best[0]
        else:
            i += 1
    return out


def main():
    for p in (WSA1_PROM_B, KN5000_MAIN):
        if not os.path.exists(p):
            sys.exit("missing: " + p)
    pb = load(WSA1_PROM_B)
    pa = load(WSA1_PROM_A)
    kn = load(KN5000_MAIN)
    sc1 = pb[SC1_LO - PROM_B_BASE:SC1_HI - PROM_B_BASE]
    print("WSA1 SC1 module  0x%06X-0x%06X  %d bytes" % (SC1_LO, SC1_HI - 1, len(sc1)))
    print("KN5000 v10 main program ROM      %d bytes (base 0x%06X)" % (len(kn), KN_BASE))
    print()

    for minlen in (16, 12, 8):
        runs = common_runs(sc1, kn, minlen)
        tot = sum(r[2] for r in runs)
        print("--- common substrings >= %d bytes: %d runs, %d bytes total (%.2f%% of the module)"
              % (minlen, len(runs), tot, 100.0 * tot / len(sc1)))
        for i, j, n in sorted(runs, key=lambda r: -r[2])[:12]:
            in_cp = KN_CPANEL_LO <= KN_BASE + j < KN_CPANEL_HI
            print("    WSA1 0x%06X  KN5000 0x%06X  %4d bytes%s"
                  % (SC1_LO + i, KN_BASE + j, n, "   <-- inside CPanel_*" if in_cp else ""))
        print()

    # And the reverse question, restricted to the KN5000 panel driver window:
    cp = kn[KN_CPANEL_LO - KN_BASE:KN_CPANEL_HI - KN_BASE]
    for name, img, base in (("prom_b", pb, PROM_B_BASE), ("prom_a", pa, 0xF80000)):
        runs = common_runs(cp, img, 8)
        tot = sum(r[2] for r in runs)
        print("--- KN5000 CPanel_* window (%d bytes) vs WSA1 %s, runs >= 8: %d runs, %d bytes"
              % (len(cp), name, len(runs), tot))
        for i, j, n in sorted(runs, key=lambda r: -r[2])[:8]:
            print("    KN5000 0x%06X  WSA1 0x%06X  %4d bytes" % (KN_CPANEL_LO + i, base + j, n))
        print()


if __name__ == "__main__":
    main()

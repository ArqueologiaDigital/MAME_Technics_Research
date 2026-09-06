#!/usr/bin/env python3
"""Analyse a captured WSA1R DSP host-bus upload (the LOG_DSPUP stream).

QUESTION THIS ANSWERS: does the emulated WSA1R's bit-banged upload to its three
uPD6383GF DSPs (IC5/IC6/IC30) actually flow through the modelled port bus to the
right destinations, in the documented P7 5-byte-group framing?  This is the first
verifiable step toward a real DSP device (notes/HANDOFF-wsa1-dsp-device-build in
kn5000-roms-disasm/wsa1) -- the capture must match the statically-extracted
microcode (wsa1_dsp_isa_crossval.py) before any device executes it.

HOW THE CAPTURE IS PRODUCED (wsa1.cpp dsp_capture(), gated on LOG_DSPUP):
  1. In src/mame/matsushita/wsa1.cpp set  #define VERBOSE (LOG_LINKLOST|LOG_DSPUP)
  2. ./build.sh
  3. ./kn7000 wsa1r -rompath roms -window -skip_gameinfo -nomax \\
         -seconds_to_run 30 -log
  4. grep '^\\[:\\] dspup:' error.log > dspcap.log     (or 'dspup:' -- the tag)
  5. python3 tools/rigs/wsa1_dsp_capture.py dspcap.log
  Then revert VERBOSE to (LOG_LINKLOST).

MEASURED 2026-09-06 (30 s boot):
  17,859 bytes captured -- dest0/IC6 10,830, dest1/IC5 6,173, dest2/IC30 856.
  dest0 stream carries 540 value-group leads (0x0A) and 82 address-group leads
  (08 01) -- the documented P7 framing (FINDINGS-prom_c-p7-group-and-naming.md:
  opcode-1 address group `08 01 .. 21`, opcode-0/5 value group `0A .. K`).  So
  the transport model is correct: the real upload reaches the right DSPs in the
  right framing.  De-framing the groups back to the pool records/microcode words
  is the next RE step (the framing gate in the HANDOFF).
"""
import collections
import re
import sys

LINE = re.compile(r"dspup: dest(\d) (CMD|DAT) ([0-9A-Fa-f]{2})")


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    per = collections.defaultdict(list)      # dest -> [(cd, byte), ...]
    for ln in open(sys.argv[1]):
        m = LINE.search(ln)
        if m:
            per[int(m.group(1))].append((m.group(2), int(m.group(3), 16)))

    total = sum(len(v) for v in per.values())
    names = {0: "IC6", 1: "IC5", 2: "IC30"}
    print("total captured bytes: %d" % total)
    for d in sorted(per):
        b = [x[1] for x in per[d]]
        n0a = sum(1 for x in b if x == 0x0A)
        n0801 = sum(1 for i in range(len(b) - 1) if b[i] == 0x08 and b[i + 1] == 0x01)
        print("  dest%d / %-4s  %6d bytes   value-groups(0x0A) %4d   addr-groups(08 01) %4d"
              % (d, names.get(d, "?"), len(b), n0a, n0801))
        print("      first 32: %s" % " ".join("%02X" % x for x in b[:32]))


if __name__ == "__main__":
    sys.exit(main())

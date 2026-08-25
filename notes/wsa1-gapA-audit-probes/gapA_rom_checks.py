#!/usr/bin/env python3
"""Adversarial re-derivation of the GAP A (0x0010C000 register) claims, from ROM BYTES.

Run:  python3 gapA_rom_checks.py [path/to/wsa1_prom_c.ic28]
Default ROM path: ../../../wsa1-roms-disasm/original_ROMs/wsa1_prom_c.ic28  (READ ONLY)

prom_c is CPU 2's program EPROM, loaded at 0xF80000, so file offset = addr - 0xF80000.

Each section answers ONE question that a GAP A claim rests on.  Every section
prints PASS/FAIL and the value it measured, so a later reader can see the number
and not just the verdict.  Nothing here reads the .s listing -- bytes only.

  1  Voice_OutputLevel_Table (0xFDDE2B, 256 u16), register 0x0080 bits 11..0.
     Q: does T[16e+m] == 128*e + round(128*log2(1+m/16)) hold for ALL 256 entries,
        and is 2*T[255] really 0x0FF4 (the "0 dB" point the driver decode prints)?
  2  Voice_Reg080_NoteField_Table (0xFDD2AB, 128 u16), register 0x0080 bits 14..12.
     Q: is it floor(2*(n mod 12)/3) << 12 for every one of the 128 note numbers,
        and does every entry stay below 0x8000 so the three fields TILE?
  3  Voice_CC_VolumeCurve (0xFDF3F1, 128 s16), the CC7/CC11 input to the level.
     Q: is it 32 counts per halving of the CONTROLLER value, and is 127 -> 0?
        (This is what makes "larger = louder" a measurement and not a preference.)
  4  Voice_LevelPair_AttackCurve (0xFDEF74, 101 u8) and Voice_EnvelopeRate_Table
     (0xFDF03E, 101 u8), the two halves of register 0x0800.
     Q: 101 bytes each, one descending 0xFF..0x09, one monotone 0x00..0x7F?
  5  Detune_Scale_Curve (0xFDF123, 51 u8), read by BOTH detune wrappers.
     Q: 51 bytes, 0x00..0x7F, non-decreasing?

WHAT A NUMBER MEANS.  Section 1 is the only thing that pins the register 0x0080
decode's dB-per-count and its 0 dB reference; if section 1 FAILs, the driver's
"%+.2f dB" line is wrong.  Sections 1 and 2 together are what "the three fields
tile exactly" means.  Section 3 fixes the SIGN of the level (which way is loud).
"""
import struct, math, sys, os

DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "../../../wsa1-roms-disasm/original_ROMs/wsa1_prom_c.ic28")
BASE = 0xF80000
fails = 0

def rd(d, addr, n):
    o = addr - BASE
    assert 0 <= o and o + n <= len(d), "address outside prom_c"
    return d[o:o+n]

def check(name, ok, detail):
    global fails
    if not ok:
        fails += 1
    print(("PASS " if ok else "FAIL ") + name + "  " + detail)

def main(path):
    d = open(path, "rb").read()
    print("rom %s  %d bytes" % (path, len(d)))

    # 1 -- the output-level table
    T = list(struct.unpack("<256H", rd(d, 0xFDDE2B, 512)))
    bad = [(i, T[i]) for e in range(16) for m in range(16)
           for i in [16*e+m]
           if T[i] != 128*e + int(math.floor(128*math.log2(1+m/16) + 0.5))]
    check("1a T[16e+m] == 128e + round(128*log2(1+m/16))",
          not bad, "mismatches=%d of 256" % len(bad))
    check("1b 2*T[255] == 0x0FF4 (the decode's 0 dB point)",
          2*T[255] == 0x0FF4, "T[255]=%d (0x%X), 2*T[255]=0x%04X" % (T[255], T[255], 2*T[255]))
    check("1c 2*T fits in bits 11..0", max(T)*2 < 0x1000, "max 2*T = 0x%04X" % (max(T)*2))
    check("1d T monotone non-decreasing",
          all(T[i] <= T[i+1] for i in range(255)), "T[0]=%d T[255]=%d" % (T[0], T[255]))
    print("     span = %.2f dB at 6.0206/256 dB per count" % (2*T[255] * 6.0206/256.0))

    # 2 -- the 3-bit note field
    N = list(struct.unpack("<128H", rd(d, 0xFDD2AB, 256)))
    bad = [n for n in range(128) if N[n] != ((2*(n % 12))//3) << 12]
    check("2a N[n] == floor(2*(n mod 12)/3) << 12", not bad, "mismatches=%d of 128" % len(bad))
    check("2b every entry < 0x8000 and a multiple of 0x1000",
          all(v < 0x8000 and (v & 0x0FFF) == 0 for v in N),
          "distinct=%s" % sorted(set(N)))

    # 3 -- the CC volume curve
    C = list(struct.unpack("<128h", rd(d, 0xFDF3F1, 256)))
    check("3a C[127] == 0 (full CC contributes no attenuation)", C[127] == 0, "C[127]=%d" % C[127])
    halvings = [(v, C[v]) for v in (64, 32, 16, 8, 4, 2, 1)]
    ok = all(C[v] == -32*k for k, v in enumerate([64, 32, 16, 8, 4, 2, 1], start=1))
    check("3b 32 counts per halving of the controller value", ok, "%s" % halvings)
    check("3c curve non-decreasing, max 0", all(C[i] <= C[i+1] for i in range(127)) and max(C) == 0,
          "C[0]=%d max=%d" % (C[0], max(C)))

    # 4 -- the two halves of register 0x0800
    A = rd(d, 0xFDEF74, 101)
    R = rd(d, 0xFDF03E, 101)
    check("4a attack curve 101 bytes descending 0xFF..0x09",
          all(A[i] >= A[i+1] for i in range(100)) and A[0] == 0xFF and A[-1] == 0x09,
          "first=0x%02X last=0x%02X" % (A[0], A[-1]))
    check("4b rate table 101 bytes monotone 0x00..0x7F",
          all(R[i] <= R[i+1] for i in range(100)) and R[0] == 0x00 and R[-1] == 0x7F,
          "first=0x%02X last=0x%02X" % (R[0], R[-1]))

    # 5 -- the detune curve both wrappers read
    D = rd(d, 0xFDF123, 51)
    check("5a detune curve 51 bytes, 0x00..0x7F, non-decreasing",
          all(D[i] <= D[i+1] for i in range(50)) and D[0] == 0 and D[-1] == 0x7F,
          "first=0x%02X last=0x%02X knees at [16]=0x%02X [32]=0x%02X" % (D[0], D[-1], D[16], D[32]))

    print("\nFAILURES: %d" % fails)
    return 1 if fails else 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT))

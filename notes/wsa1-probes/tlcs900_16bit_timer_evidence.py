#!/usr/bin/env python3
"""tlcs900_16bit_timer_evidence.py -- re-derive, from the ROMs, everything the
16-bit-timer (INTTR4) work claims about how the TMP95C061's timer 4 is
programmed on the two Technics machines that use that CPU.

QUESTION IT ANSWERS
  "MAME's tmp95c061.cpp never counts the 16-bit timers, so INTTR4 can never
   fire.  What exactly does the firmware ask for, and what rate must a correct
   implementation produce?"

Every assertion below is a byte read out of an original ROM image plus one
arithmetic step.  Nothing is taken from the emulator.

RUN
  python3 notes/wsa1-probes/tlcs900_16bit_timer_evidence.py
  (add --roms DIR if technics_roms is not at the default path)

WHAT "PASS" MEANS
  the bytes at the quoted address are exactly the quoted instruction encoding.
  ldio (io8),imm8   = 08 <io> <imm>
  ldw  (io8),imm16  = 0a <io> <lo> <hi>
  A vector check reads a little-endian 32-bit pointer out of the 0xFFFF00 page.

⚠ THE NULL.  A raw scan for `08 <reg> <imm>` over a 512 KB image fires inside
data and inside the middle of longer instructions.  On prom_a it yields 317
hits for the sixteen timer registers, of which 17 are real -- a ~5% signal
rate.  Two hits that an earlier pass quoted were checked with unidasm and are
NOT instructions:
    0xF8C89D "T45CR=0x02"  is the middle of  0xF8C89C sub (XIZ+0x08),0x0002
    0xFA0C71 "INTET76=0x8F" is the middle of 0xFA0C6F and C,0x08
                                             0xFA0C72 jrl z,0xFA0D04
and on the KN1500 all four INTET76 candidates (file offsets 0x18B922,
0x18DFD2, 0x18F228, 0x1C704C) are the middle of `cp W,0x08` / `cp L,0x08` /
`bit 0x08,WA` followed by a `jrl`.  This script therefore checks only
sequences whose surrounding instruction boundaries were established with
    sh notes/wsa1-probes/wsa1_dis.sh a 0xADDR
    /home/fsanches/compartilhado/mame/unidasm FILE -arch tlcs900 -basepc HEX
It does not re-run the disassembler; it pins the byte sequences those runs
validated, so that a re-dump or a different image is caught immediately.
"""

import argparse, os, sys

# TMP95C061 internal-I/O addresses (wsa1-roms-disasm/include/tmp95c061_sfr.inc)
TRUN, T01MOD, TREG0, TREG1 = 0x20, 0x24, 0x22, 0x23
TREG4L, TREG4H, TREG5L, TREG5H = 0x30, 0x31, 0x32, 0x33
T4MOD, T4FFCR, T45CR = 0x38, 0x39, 0x3a
TREG6L, TREG6H, TREG7L, TREG7H = 0x40, 0x41, 0x42, 0x43
T5MOD, T5FFCR = 0x48, 0x49
INTET54, INTET76 = 0x75, 0x76

fails = []

def check(name, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + name + (("   " + detail) if detail else ""))
    if not cond:
        fails.append(name)

def ldio(io, imm):
    return bytes((0x08, io, imm))

def ldw(io, imm16):
    return bytes((0x0a, io, imm16 & 0xff, imm16 >> 8))

def at(img, off, expect, what):
    got = img[off:off + len(expect)]
    check(what, got == expect,
          "expect %s got %s" % (expect.hex(" "), got.hex(" ")))

def vec(img, base, v):
    return int.from_bytes(img[(0xFFFF00 + v) - base:(0xFFFF00 + v) - base + 4], "little") & 0xFFFFFF


def wsa1(roms):
    path = os.path.join(roms, "wsa1", "wsa1_os_v2.ic12")
    img = open(path, "rb").read()
    base = 0xF80000
    print("\n=== SX-WSA1R, CPU1 program ROM IC12 (prom_a), base 0x%06X ===" % base)
    check("image is 512 KB", len(img) == 0x80000, "%d bytes" % len(img))

    # --- the 8-bit timer block, for the phiT256 tap that defect #1 is about ---
    o = 0xF826E8 - base
    at(img, o + 0x00, ldio(TRUN, 0x00),   "0xF826E8  ldio TRUN,0x00")
    at(img, o + 0x03, ldio(T01MOD, 0x0D), "0xF826EB  ldio T01MOD,0x0D  (timer 1 clk sel 3 = phiT256)")
    at(img, o + 0x09, ldio(TREG0, 0x0F),  "0xF826F1  ldio TREG0,0x0F")
    at(img, o + 0x0c, ldio(TREG1, 0x1C),  "0xF826F4  ldio TREG1,0x1C")

    # --- the 16-bit timer block ---
    o = 0xF82703 - base
    seq = [(0x00, ldio(T4MOD, 0x05),  "0xF82703  ldio T4MOD,0x05   (bits[1:0]=01 -> phiT1)"),
           (0x03, ldio(T4FFCR, 0x00), "0xF82706  ldio T4FFCR,0x00"),
           (0x06, ldio(T45CR, 0x00),  "0xF82709  ldio T45CR,0x00"),
           (0x09, ldio(TREG4L, 0x01), "0xF8270C  ldio TREG4L,0x01"),
           (0x0c, ldio(TREG4H, 0x00), "0xF8270F  ldio TREG4H,0x00   -> TREG4 = 0x0001"),
           (0x0f, ldio(TREG5L, 0x09), "0xF82712  ldio TREG5L,0x09"),
           (0x12, ldio(TREG5H, 0x3D), "0xF82715  ldio TREG5H,0x3D   -> TREG5 = 0x3D09 = 15625"),
           (0x15, ldio(T5MOD, 0x02),  "0xF82718  ldio T5MOD,0x02    (bits[1:0]=10 -> phiT4)"),
           (0x18, ldio(T5FFCR, 0x00), "0xF8271B  ldio T5FFCR,0x00"),
           (0x1b, ldio(TREG6L, 0x98), "0xF8271E  ldio TREG6L,0x98"),
           (0x1e, ldio(TREG6H, 0x3A), "0xF82721  ldio TREG6H,0x3A   -> TREG6 = 15000"),
           (0x21, ldio(TREG7L, 0x98), "0xF82724  ldio TREG7L,0x98"),
           (0x24, ldio(TREG7H, 0x3A), "0xF82727  ldio TREG7H,0x3A   -> TREG7 = 15000"),
           (0x27, ldio(TRUN, 0xB7),   "0xF8272A  ldio TRUN,0xB7     (bit7 pre, bit4 T4RUN, bit5 T5RUN)")]
    for d, e, w in seq:
        at(img, o + d, e, w)

    at(img, 0xF827CE - base, ldio(INTET54, 0x03),
       "0xF827CE  ldio INTET54,0x03  (INTTR4 priority 3, INTTR5 priority 0 = off)")

    # INTET76 is never written -> INTTR6/INTTR7 stay at priority 0 forever.
    hits = [i for i in range(len(img) - 2) if img[i] == 0x08 and img[i + 1] == INTET76]
    check("prom_a has exactly one `08 76 xx` byte hit, and it is not an instruction",
          hits == [0xFA0C71 - base],
          "hits at %s" % ["0x%06X" % (base + h) for h in hits])
    at(img, 0xFA0C6F - base, bytes.fromhex("cbcc08768f00"),
       "0xFA0C6F  and C,0x08 / jrl z,...  <- the whole of that hit")

    # vectors
    v = {n: vec(img, base, a) for n, a in
         (("INTTR4", 0x50), ("INTTR5", 0x54), ("INTTR6", 0x58), ("INTTR7", 0x5c),
          ("INTT1", 0x44), ("INT7", 0x38))}
    check("vector 0x50 INTTR4 -> 0xF82EA2 (the sequencer tick)", v["INTTR4"] == 0xF82EA2,
          "0x%06X" % v["INTTR4"])
    check("vectors 0x54/0x58/0x5C all -> 0xF82D09, the unused-vector hang",
          v["INTTR5"] == v["INTTR6"] == v["INTTR7"] == 0xF82D09,
          "0x%06X 0x%06X 0x%06X" % (v["INTTR5"], v["INTTR6"], v["INTTR7"]))
    at(img, 0xF82D09 - base, bytes((0x68, 0xfe)),
       "0xF82D09  jr T,0xF82D09  <- that stub really is an infinite loop")

    # the handler's beat length
    at(img, 0xF82EB1 - base, bytes((0x83, 0x3f, 0x60)),
       "0xF82EB1  cp (XHL),0x60  -> 96 ticks per beat")

    fc = 28_000_000                   # notes/FINDINGS-system-clock.md, lever B
    treg5 = 0x3D09
    rate = fc / 8 / treg5
    bpm = rate * 60 / 96
    check("INTTR4 rate at fc=28 MHz, phiT1=fc/8, TREG5=15625 is 224.0 Hz = 140.0 BPM",
          abs(rate - 224.0) < 1e-9 and abs(bpm - 140.0) < 1e-9,
          "%.4f Hz, %.4f BPM" % (rate, bpm))
    wrong = fc / 128 / treg5
    print("      NULL: with MAME's current phiT1 = m_timer_pre>>7 = fc/128 the same")
    print("            registers give %.4f Hz = %.4f BPM -- 16x slow (defect #1)."
          % (wrong, wrong * 60 / 96))


def kn1500(roms):
    path = os.path.join(roms, "kn1500",
                        "technics_qsigt3c16079_5y68-j079_japan_9649eai.ic15")
    img = open(path, "rb").read()
    base = 0xE00000            # kn1500.cpp: ROM_REGION "prog" mapped 0xE00000-0xFFFFFF
    print("\n=== SX-KN1500, IC15 program mask ROM, base 0x%06X ===" % base)
    check("image is 2 MB", len(img) == 0x200000, "%d bytes" % len(img))

    o = 0xFE5FB5 - base
    seq = [(0x00, ldio(T4MOD, 0x05),  "0xFE5FB5  ldio T4MOD,0x05   (bits[1:0]=01 -> phiT1)"),
           (0x03, ldio(T4FFCR, 0x00), "0xFE5FB8  ldio T4FFCR,0x00"),
           (0x06, ldio(T5MOD, 0x02),  "0xFE5FBB  ldio T5MOD,0x02"),
           (0x09, ldio(T5FFCR, 0x00), "0xFE5FBE  ldio T5FFCR,0x00"),
           (0x0c, ldio(T45CR, 0x00),  "0xFE5FC1  ldio T45CR,0x00"),
           (0x0f, ldw(TREG4L, 0x0001), "0xFE5FC4  ldw (TREG4),0x0001   <- ONE 16-bit store"),
           (0x13, ldw(TREG5L, 0x3D09), "0xFE5FC8  ldw (TREG5),0x3D09   = 15625, same as the WSA1"),
           (0x17, ldio(TRUN, 0xFF),   "0xFE5FCC  ldio TRUN,0xFF     (every timer running)")]
    for d, e, w in seq:
        at(img, o + d, e, w)

    at(img, 0xFE6075 - base, ldio(0x73, 0x30), "0xFE6075  ldio INTET10,0x30")
    at(img, 0xFE6078 - base, ldio(INTET54, 0x03),
       "0xFE6078  ldio INTET54,0x03  (INTTR4 priority 3, INTTR5 off) -- same as the WSA1")

    v = {n: vec(img, base, a) for n, a in
         (("INTTR4", 0x50), ("INTTR5", 0x54), ("INTTR6", 0x58), ("INTTR7", 0x5c),
          ("INTT0", 0x40))}
    check("vector 0x50 INTTR4 -> 0xFE6515", v["INTTR4"] == 0xFE6515, "0x%06X" % v["INTTR4"])
    check("vectors 0x54/0x58/0x5C share the INTT0 stub 0xFE619C",
          v["INTTR5"] == v["INTTR6"] == v["INTTR7"] == v["INTT0"] == 0xFE619C,
          "0x%06X" % v["INTTR5"])

    # the handler is the same routine as the WSA1's, down to the direct-page slots
    at(img, 0xFE6522 - base, bytes((0x83, 0x3f, 0x60)),
       "0xFE6522  cp (XHL),0x60  -> 96 ticks per beat here too")
    at(img, 0xFE6534 - base, bytes((0xf0, 0x95, 0xca)),
       "0xFE6534  bit 2,(0x95)   -> same transport byte as WSA1 0xF82EC3")
    at(img, 0xFE6575 - base, bytes((0xf0, 0x94, 0xca)),
       "0xFE6575  bit 2,(0x94)   -> same transport byte as WSA1 0xF82EDA")

    fc = 24_000_000            # kn1500.cpp:56  TMP95C061(config, m_maincpu, 24_MHz_XTAL)
    rate = fc / 8 / 0x3D09
    bpm = rate * 60 / 96
    check("★ the SAME TREG5 on a 24 MHz part gives exactly 120.0 BPM",
          abs(rate - 192.0) < 1e-9 and abs(bpm - 120.0) < 1e-9,
          "%.4f Hz, %.4f BPM" % (rate, bpm))
    print("      That is the cross-machine check on the tap: one register value,")
    print("      two different fc, and BOTH land on a round default tempo only if")
    print("      T4MOD bits[1:0]=01 means phiT1 = fc/8 and the period is TREG5.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--roms", default="/home/fsanches/compartilhado/technics_roms/roms")
    a = ap.parse_args()
    wsa1(a.roms)
    kn1500(a.roms)
    print("\n%d checks failed" % len(fails))
    for f in fails:
        print("  FAILED: " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

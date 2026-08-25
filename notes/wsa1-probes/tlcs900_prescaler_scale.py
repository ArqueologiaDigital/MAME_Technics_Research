#!/usr/bin/env python3
"""tlcs900_prescaler_scale.py -- fix the ABSOLUTE scale of the TLCS-900 timer
prescaler (the value of K in phiT1 = fc/K) from three Technics ROM sets.

QUESTION IT ANSWERS
  MAME carries two mutually inconsistent prescalers for the same CPU family:
      tmp94c241.cpp:1400-1403   T1,T4,T16,T256 = shifts 3, 5, 7, 11  -> phiT1 = fc/8
      tmp95c061.cpp:683-689     T1,T4,T16,T256 = shifts 7, 9, 11, 15 -> phiT1 = fc/128
      tmp95c063.cpp:263-269     same as tmp95c061
  Both are fed by an identical `m_timer_pre += m_cycles`, so the shift IS the
  divisor: which one is right?

  ⚠ THE RATIO IS NOT THE ANSWER.  Both files use T1:T4:T16:T256 = 1:4:16:256, so
  any firmware check that only compares one tap against another cancels K and
  fits BOTH.  That includes the `muls WA,0x06D6` (1750) MIDI tempo-tracker
  constant at WSA1 prom_a 0xFA5553, which wsa1-roms-disasm/notes/
  FINDINGS-system-clock.md quotes as adjudicating the scale: worked through
  self-consistently it predicts 64*TREG1 = 1792 under EITHER K.  (That table's
  "28672" mixes K=128 for timer 1 with K=8 for timer 4.)

  What DOES fix K is the sequencer TEMPO DIVIDE, because it ties an absolute
  musical tempo to fc:

      the 16-bit timer 4 runs on phiT1 (T4MOD bits[1:0] = 01), is cleared by a
      TREG5 match (T4MOD bits[3:2] = 01) and raises INTTR4 once per cycle
      (TREG4 = 1).  The INTTR4 handler counts 96 ticks to the beat.  So
          beat = 96 * TREG5 * K / fc      and     BPM = 60*fc / (96*K*TREG5)
      The firmware computes TREG5 = C / (64 * BPM) with a per-machine 32-bit
      constant C, hence
          C = 40 * fc / K
      One equation per machine, each with an independently known fc.

RUN
    python3 notes/wsa1-probes/tlcs900_prescaler_scale.py
    (--wsa1 / --kn1500 / --kn5000 override the image paths)

WHAT "PASS" MEANS
  the quoted bytes are at the quoted address in the quoted image, and the
  arithmetic above lands on K = 8 exactly (no rounding).

SIGNALS READ, and what a value means
  ldio (io8),imm8   = 08 <io> <imm>       ldw (io8),imm16 = 0a <io> <lo> <hi>
  T01MOD  bits[3:2] = 11 -> timer 1 counts phiT256
  T4MOD   bits[1:0] = 01 -> timer 4 counts phiT1
          bits[3:2] = 01 -> counter cleared by the TREG5 match
  SCnMOD  bits[1:0] = 01 -> that UART is clocked by the baud-rate generator
                     = 11 -> external SCLK (BRnCR then means nothing)
  BRnCR   bits[5:4] = 00 -> tap 0 = fc/4; bits[3:0] = N; UART oversamples /16
                            => bit rate = fc / (64 * N)
"""

import argparse, os, struct, sys

fails = []

def check(name, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + name + (("   " + detail) if detail else ""))
    if not cond:
        fails.append(name)

def at(img, base, addr, expect, what):
    off = addr - base
    got = img[off:off + len(expect)]
    check(what, got == expect, "got %s" % got.hex(" "))

def le32(img, base, addr):
    return struct.unpack_from("<I", img, addr - base)[0]


# ---------------------------------------------------------------- SX-WSA1R --
def wsa1(path):
    base = 0xF80000                      # prom_a occupies 0xF80000-0xFFFFFF
    img = open(path, "rb").read()
    print("\n=== SX-WSA1R, prom_a (IC12), base 0x%06X ===" % base)
    check("image is 512 KB", len(img) == 0x80000, "%d bytes" % len(img))

    at(img, base, 0xF826EB, bytes((0x08, 0x24, 0x0D)),
       "0xF826EB  ldio T01MOD,0x0D   timer 1 clock select = 3 = phiT256")
    at(img, base, 0xF826F4, bytes((0x08, 0x23, 0x1C)),
       "0xF826F4  ldio TREG1,0x1C    = 28 = fc in MHz")
    at(img, base, 0xF82703, bytes((0x08, 0x38, 0x05)),
       "0xF82703  ldio T4MOD,0x05    timer 4 on phiT1, cleared by TREG5")
    at(img, base, 0xF8270C, bytes((0x08, 0x30, 0x01)),
       "0xF8270C  ldio TREG4L,0x01   TREG4 = 1 -> one INTTR4 per counter cycle")
    at(img, base, 0xF8272A, bytes((0x08, 0x20, 0xB7)),
       "0xF8272A  ldio TRUN,0xB7     bit7 prescaler, bit4 timer 4")
    at(img, base, 0xF827CE, bytes((0x08, 0x75, 0x03)),
       "0xF827CE  ldio INTET54,0x03  INTTR4 enabled at priority 3")
    check("vector 0x50 (INTTR4) -> 0xF82EA2", le32(img, base, 0xFFFF50) == 0xF82EA2,
          "0x%06X" % le32(img, base, 0xFFFF50))
    at(img, base, 0xF82EB1, bytes((0x83, 0x3F, 0x60)),
       "0xF82EB1  cp (XHL),0x60     -> 96 INTTR4 ticks per beat")

    # fc: prom_a's MIDI init writes BR0CR = 0x0E with SC0MOD = 0x29 (BRG).
    at(img, base, 0xFA58F2, bytes((0x08, 0x52, 0x29)),
       "0xFA58F2  ldio SC0MOD,0x29   UART fed by the baud-rate generator")
    at(img, base, 0xFA58F8, bytes((0x08, 0x53, 0x0E)),
       "0xFA58F8  ldio BR0CR,0x0E    N = 14, tap 0 -> bit rate = fc/896")
    fc = 31250 * 64 * 14
    check("fc from the MIDI divisor is 28,000,000", fc == 28_000_000, "%d" % fc)

    # the tempo divide
    at(img, base, 0xFAA373, bytes((0x32, 0x40, 0x00)), "0xFAA373  ld DE,0x0040     (x64)")
    at(img, base, 0xFAA376, bytes((0xDA, 0x40)),       "0xFAA376  mul XWA,DE")
    at(img, base, 0xFAA378, bytes((0x42, 0x00, 0x3B, 0x58, 0x08)),
       "0xFAA378  ld XDE,0x08583B00 = 140,000,000   <- C")
    at(img, base, 0xFAA37D, bytes((0xD8, 0x52)),       "0xFAA37D  div XDE,WA")
    at(img, base, 0xFAA38D, bytes((0xF0, 0x32, 0x52)), "0xFAA38D  ld (TREG5),DE")
    return ("SX-WSA1R  TMP95C061", fc, 140_000_000)


# ---------------------------------------------------------------- SX-KN1500 -
def kn1500(path):
    base = 0xE00000                      # kn1500.cpp: "prog" region at 0xE00000
    img = open(path, "rb").read()
    print("\n=== SX-KN1500, IC15 program mask ROM, base 0x%06X ===" % base)
    check("image is 2 MB", len(img) == 0x200000, "%d bytes" % len(img))

    at(img, base, 0xFE5F9D, bytes((0x08, 0x24, 0xED)),
       "0xFE5F9D  ldio T01MOD,0xED   timer 1 clock select = 3 = phiT256")
    at(img, base, 0xFE5FA9, bytes((0x08, 0x23, 0x18)),
       "0xFE5FA9  ldio TREG1,0x18    = 24 = fc in MHz")
    at(img, base, 0xFE5FB5, bytes((0x08, 0x38, 0x05)),
       "0xFE5FB5  ldio T4MOD,0x05    timer 4 on phiT1, cleared by TREG5")
    at(img, base, 0xFE5FC4, bytes((0x0A, 0x30, 0x01, 0x00)),
       "0xFE5FC4  ldw (TREG4),0x0001")
    at(img, base, 0xFE5FC8, bytes((0x0A, 0x32, 0x09, 0x3D)),
       "0xFE5FC8  ldw (TREG5),0x3D09 = 15625, the same constant as the WSA1")
    check("vector 0x50 (INTTR4) -> 0xFE6515", le32(img, base, 0xFFFF50) == 0xFE6515,
          "0x%06X" % le32(img, base, 0xFFFF50))
    at(img, base, 0xFE6522, bytes((0x83, 0x3F, 0x60)),
       "0xFE6522  cp (XHL),0x60     -> 96 INTTR4 ticks per beat here too")

    # fc: the boot's read-modify-write of BR1CR, with SC1MOD = 0x29 (BRG).
    at(img, base, 0xFE6001, bytes((0x08, 0x56, 0x29)),
       "0xFE6001  ldio SC1MOD,0x29   UART fed by the baud-rate generator")
    at(img, base, 0xFE6007, bytes((0xC0, 0x57, 0x3C, 0xCF)),
       "0xFE6007  and (BR1CR),0xCF   clears bits 5:4 -> tap 0 = fc/4")
    at(img, base, 0xFE600E, bytes((0x81, 0x21)),       "0xFE600E  ld A,(XBC)")
    at(img, base, 0xFE6010, bytes((0xC9, 0xCC, 0xF0)), "0xFE6010  and A,0xF0")
    at(img, base, 0xFE6013, bytes((0xC9, 0xCE, 0x0C)),
       "0xFE6013  or A,0x0C         -> BR1CR N = 12, bit rate = fc/768")
    fc = 31250 * 64 * 12
    check("fc from the MIDI divisor is 24,000,000", fc == 24_000_000, "%d" % fc)
    check("...which is the 24_MHz_XTAL kn1500.cpp already instantiates", fc == 24_000_000)

    # the tempo divide -- the same routine as the WSA1's, instruction for instruction
    at(img, base, 0xFA6D80, bytes((0x32, 0x40, 0x00)), "0xFA6D80  ld DE,0x0040     (x64)")
    at(img, base, 0xFA6D83, bytes((0xDA, 0x40)),       "0xFA6D83  mul XWA,DE")
    at(img, base, 0xFA6D85, bytes((0x42, 0x00, 0x0E, 0x27, 0x07)),
       "0xFA6D85  ld XDE,0x07270E00 = 120,000,000   <- C")
    at(img, base, 0xFA6D8A, bytes((0xD8, 0x52)),       "0xFA6D8A  div XDE,WA")
    at(img, base, 0xFA6D9A, bytes((0xF0, 0x32, 0x52)), "0xFA6D9A  ld (TREG5),DE")
    return ("SX-KN1500 TMP95C061", fc, 120_000_000)


# ---------------------------------------------------------------- SX-KN5000 -
def kn5000(path):
    base = 0xE00000                      # kn5000.cpp:628  "program" at 0xE00000, mask 0x1FFFFF
    img = open(path, "rb").read()
    print("\n=== SX-KN5000, main program ROM (v10), base 0x%06X ===" % base)
    check("image is 2 MB", len(img) == 0x200000, "%d bytes" % len(img))

    # TMP94C241 SFR addresses differ from the TMP95C061's.
    at(img, base, 0xEF042D, bytes((0x08, 0x84, 0x1D)),
       "0xEF042D  ldio T01MOD,0x1D   timer 1 clock select = 3 = phiT256")
    at(img, base, 0xEF0439, bytes((0x08, 0x89, 0x10)),
       "0xEF0439  ldio TREG1,0x10    = 16 = fc in MHz  (2 * 8_MHz_XTAL, kn5000.cpp:1203)")
    at(img, base, 0xEF0442, bytes((0x08, 0x98, 0x05)),
       "0xEF0442  ldio T4MOD,0x05    timer 4 on phiT1, cleared by TREG5")
    at(img, base, 0xEF044B, bytes((0x0A, 0x90, 0x01, 0x00)), "0xEF044B  ldw (TREG4),0x0001")
    at(img, base, 0xEF044F, bytes((0x0A, 0x92, 0x09, 0x3D)),
       "0xEF044F  ldw (TREG5),0x3D09 = 15625, the same constant AGAIN")

    at(img, base, 0xFCA34A, bytes((0x32, 0x40, 0x00)), "0xFCA34A  ld DE,0x0040     (x64)")
    at(img, base, 0xFCA34D, bytes((0xDA, 0x40)),       "0xFCA34D  mul XWA,DE")
    at(img, base, 0xFCA34F, bytes((0x42, 0x00, 0xB4, 0xC4, 0x04)),
       "0xFCA34F  ld XDE,0x04C4B400 = 80,000,000    <- C")
    at(img, base, 0xFCA361, bytes((0xD8, 0x52)),       "0xFCA361  div XDE,WA")
    at(img, base, 0xFCA371, bytes((0xF1, 0x92, 0x00, 0x52)),
       "0xFCA371  ld (TREG5L),DE   (TMP94C241 SFR 0x92)")
    # fc here is NOT derived from a UART: the KN5000's MIDI lives on the SUB CPU.
    # It is the board's 8 MHz crystal through the documented internal doubler,
    # corroborated by TREG1 = 16 under the "TREG1 = fc in MHz" rule that the two
    # UART-derived machines above establish.
    return ("SX-KN5000 TMP94C241", 16_000_000, 80_000_000)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wsa1", default="/home/fsanches/compartilhado/wsa1-roms-disasm/"
                                      "original_ROMs/wsa1_prom_a.ic12")
    ap.add_argument("--kn1500", default="/home/fsanches/compartilhado/technics_roms/roms/"
                                        "kn1500/technics_qsigt3c16079_5y68-j079_japan_9649eai.ic15")
    ap.add_argument("--kn5000", default="/home/fsanches/compartilhado/kn5000-roms-disasm/"
                                        "original_ROMs/kn5000_v10_program.rom")
    a = ap.parse_args()

    rows = []
    for fn, p in ((wsa1, a.wsa1), (kn1500, a.kn1500), (kn5000, a.kn5000)):
        if not os.path.exists(p):
            print("SKIP  %s: no such image" % p)
            continue
        rows.append(fn(p))

    print("\n=== C = 40 * fc / K, solved for K ===")
    print("%-22s %12s %14s %8s" % ("machine", "fc", "C", "K"))
    for name, fc, C in rows:
        K = 40 * fc / C
        print("%-22s %12d %14d %8s" % (name, fc, C, ("%g" % K)))
        check("%s gives K = 8 exactly" % name, K == 8.0, "K = %r" % K)

    print("""
=== what that means for the code ===
  phiT1 = fc/8  =>  the prescaler shift for T1 is 3, and the family's
  1:4:16:256 ratio makes T4/T16/T256 shifts 5, 7 and 11.
  That is what tmp94c241.cpp:1400-1403 already does, and it is 16x away from
  tmp95c061.cpp:683-689 / tmp95c063.cpp:263-269 (shifts 7, 9, 11, 15).

=== THE NULL ===
  Every fc above except the KN5000's comes from the UART rule
  "tap 0 = fc/4, then /16".  Call that tap divisor U.  Then
      31250 = fc / (16*U*N)      =>  fc = 500000 * U * N
      C     = 40 * fc / K        =>  K  = 2U
  The firmware fixes only K = 2U.  U = 2 would give K = 4 (shifts 2,4,6,10) and
  U = 8 would give K = 16 (shifts 4,6,8,12); both refit every ROM constant here
  with every fc halved or doubled.  What breaks the tie:
    * U = 4 is what tmp94c241_serial.cpp:303-318 implements, and on the KN5000
      SUB CPU it yields 31250.000 exactly from BR1CR = 0x0A at 2*10_MHz_XTAL.
    * the KN5000 MAIN CPU's fc is an 8 MHz crystal through the documented
      internal doubler -- a board fact, not a UART inference -- and with
      C = 80,000,000 that alone forces K = 8.
    * TREG1 = fc in MHz holds on all three machines (28 / 24 / 16), which only
      makes design sense if it normalises the INTT1 tick to a round rate:
      1e6/(256*K) = 488.28 Hz at K = 8, and 488.28 Hz is the rate the WSA1's
      own `muls WA,0x06D6` (1750) tempo tracker rounds to 500.  At K = 4 or 16
      that becomes 976.6 or 244.1 Hz, and the 1750 constant no longer follows.
  A databook page for either the timer prescaler or the baud-rate generator, or
  one stopwatch on real hardware (set the metronome to 120 BPM and time 60
  beats), would settle U directly.
""")
    print("FAILURES: %d" % len(fails))
    for f in fails:
        print("  " + f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())

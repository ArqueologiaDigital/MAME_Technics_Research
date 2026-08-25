#!/usr/bin/env python3
"""ADVERSARIAL PROBES for the gap-F report ("the read-back path at 0x0010C000+4").

Run:  python3 notes/wsa1-gapF-probes/gapF_refutation_probes.py

SIGNAL BEING READ: raw bytes of wsa1-roms-disasm/original_ROMs/*.  BASE = 0xF80000,
the same base the evidence base's own notes/prom_c_voice_sweep_checks.py uses.
Nothing here reads prom_c/wsa1_prom_c.s, so a listing error cannot propagate.

WHAT EACH PROBE ANSWERS, and what a PASS looks like:

 P1  Is Dev10C_PollBankAndRetire (0xFA68DC) the only code that reads the device's
     +4 DATA port?  PASS = exactly one of the 0x0010C000 immediate loads is
     followed by a +4 pointer step (`inc 4,XBC` e9 64 / `inc 4,XWA` e8 64), and it
     is 0xFA68FC.  (Report sec.1 asserts "the only reader ... in either image".)

 P2  How many sites store the immediate 0x8100 / 0x7E00 through a register-indirect
     `ld (Xrr[,d]),imm16`?  The report's sec.4 table lists THREE of each.
     PASS = the report's six addresses appear.  ⚠ The interesting part is what
     ELSE appears: 0x8100 has SEVEN sites in prom_c, four of them on register
     blocks 0x0540 / 0x0580 / 0x05C0 -- so 0x8100 is not a block-0-only word.

 P2b No `ld r16,0x8100/0x7E00` exists in prom_c, so P2's immediate-store census is
     complete for those two words (a value loaded into a register first would have
     escaped it).

 P3  Where is the loop counter that fixes the channel count at 64?  Both the report
     (sec.5a) and wsa1.cpp's existing comment cite `ldb d,0x40` at prom_c 0xFB810E.
     PASS = 0xFB810E decodes as `33 40 08` = ld HL,0x0840.  The `24 40` = ld D,0x40
     is at 0xFB8116.  BOTH CITATIONS ARE WRONG BY 8 BYTES.

 P4  Which instructions `set 0x02,<byte reg>` in prom_c?  Report sec.2 says flag
     bit 2 "is never set anywhere in the machine" today, i.e. that 0xFA6632 is its
     only producer.  15 such instructions exist; only 0xFA6632 lies in the voice
     module 0xFA6528-0xFA6EF9.  The global claim is NOT established by this.

 P5  The record-field stores report sec.2 depends on.  Report sec.2 says
     "rec[+0x15] is permanently 0".  It is NOT: the allocator writes 0xFF into it
     at 0xFA6CC3 on every note-on, and it is 0 at note-off only because
     ChanRec_Release zeroed it at 0xFA6598 -- a consequence of READ 1's stub, not
     READ 2's.  0xFA65CD also shows sub_FA65BD's guard is `flags & 0x03`, so the
     RELEASED bit (0x01, stored at 0xFA6594) blocks it: the 0xFA62DA(rec, ..., 6)
     call the report predicts is never reached.

 P6  Does the allocator arm the 0x0087BF mask itself at 0xFA6D39-0xFA6D41?
     PASS = yes (report sec.1's star claim CONFIRMED; the evidence base's
     FINDINGS-prom_c-voice-readback.md sec.2 lists only three mask sites and
     misses this fourth one).

 P7  Both producers of voicerec[+0x29] -- the computed word Dev10C_WriteReg_c
     sends to BLOCK 0 -- build it as an OR whose HIGH BYTE is a shifted parameter.
     So a computed block-0 word CAN in principle equal 0x7E00 or 0x8100, which the
     report's proposed model would read as FREE / GATE.  Printed for inspection.
"""
import os

ROMS = "/home/fsanches/compartilhado/wsa1-roms-disasm/original_ROMs"
IMGS = [("prom_a", "wsa1_prom_a.ic12"), ("prom_b", "wsa1_prom_b.ic13"),
        ("prom_c", "wsa1_prom_c.ic28"), ("prom_d", "wsa1_prom_d.bin")]
BASE = 0xF80000
img = {n: open(os.path.join(ROMS, f), "rb").read() for n, f in IMGS}
R16 = "WA BC DE HL IX IY IZ SP".split()


def find(d, pat):
    out, i = [], 0
    while True:
        i = d.find(pat, i)
        if i < 0:
            return out
        out.append(i)
        i += 1


print("P1 -- readers of the +4 DATA port")
readers, loads = [], 0
for name in ("prom_a", "prom_b", "prom_c", "prom_d"):
    for o in find(img[name], bytes([0x00, 0xC0, 0x10, 0x00])):
        loads += 1
        win = img[name][o:o + 24]
        if bytes([0xE9, 0x64]) in win or bytes([0xE8, 0x64]) in win:
            readers.append((name, BASE + o - 1))
print("   0x0010C000 immediate loads, all four images: %d" % loads)
print("   of which followed by a +4 pointer step: %d" % len(readers))
for n, a in readers:
    print("     %-7s 0x%06X" % (n, a))
print()

print("P2 -- `ld (Xrr[,d]),imm16` stores of the two lifecycle words")
for val in (0x8100, 0x7E00):
    hits = []
    for name in ("prom_a", "prom_b", "prom_c", "prom_d"):
        d = img[name]
        lo, hi = val & 0xFF, val >> 8
        for o in range(len(d) - 6):
            if 0xB0 <= d[o] <= 0xB7 and d[o+1] == 0x02 and d[o+2] == lo and d[o+3] == hi:
                hits.append((name, BASE + o, "ld (X%s),0x%04X" % (R16[d[o]-0xB0], val)))
            if 0xB8 <= d[o] <= 0xBF and d[o+2] == 0x02 and d[o+3] == lo and d[o+4] == hi:
                hits.append((name, BASE + o, "ld (X%s+0x%02X),0x%04X" % (R16[d[o]-0xB8], d[o+1], val)))
    print("   0x%04X : %d site(s)" % (val, len(hits)))
    for n, a, t in hits:
        print("     %-7s 0x%06X  %s" % (n, a, t))
print()

print("P2b -- `ld r16,imm16` loads of the same two words in prom_c")
d = img["prom_c"]
n2 = 0
for val in (0x8100, 0x7E00):
    for o in range(len(d) - 3):
        if 0x30 <= d[o] <= 0x37 and d[o+1] == (val & 0xFF) and d[o+2] == (val >> 8):
            print("     0x%06X  ld %s,0x%04X" % (BASE + o, R16[d[o]-0x30], val)); n2 += 1
print("   total: %d  (0 = P2 is a complete census for these two words)" % n2)
print()

print("P3 -- the channel-count loop counter")
print("     0xFB810E: %s" % d[0xFB810E-BASE:0xFB810E-BASE+3].hex(" "), "= ld HL,0x0840  <-- NOT the counter")
print("     0xFB8116: %s" % d[0xFB8116-BASE:0xFB8116-BASE+2].hex(" "), "= ld D,0x40     <-- the counter")
print("     0xFB8140: %s" % d[0xFB8140-BASE:0xFB8140-BASE+2].hex(" "), "= dec 1,D       (loop bottom)")
print()

print("P4 -- `set 0x02,<byte reg>` in prom_c")
sites = [BASE + o for o in range(len(d) - 3)
         if 0xC8 <= d[o] <= 0xCF and d[o+1] == 0x31 and d[o+2] == 0x02]
print("   %d site(s); in the voice module 0xFA6528-0xFA6EF9: %s"
      % (len(sites), [hex(a) for a in sites if 0xFA6528 <= a <= 0xFA6EF9]))
print("   all: %s" % ", ".join(hex(a) for a in sites))
print()

print("P5 -- the record-field stores")
for a, n, what in ((0xFA6846, 4, "ld (XBC+0x12),0x00   VoiceSubsystem_Init"),
                   (0xFA6CC0, 3, "ld (XDE+0x13),A      allocator  (note table says 'not written')"),
                   (0xFA6CC3, 4, "ld (XDE+0x15),0xFF   allocator  <-- NOT 'permanently 0'"),
                   (0xFA6CCA, 3, "ld (XDE+0x16),C      allocator  (note table says 'not written')"),
                   (0xFA6CDC, 4, "ld (XDE+0x12),0x88   allocator, held arm"),
                   (0xFA6D07, 4, "ld (XDE+0x12),0x08   allocator, not-held arm"),
                   (0xFA6594, 4, "ld (XIX+0x12),0x01   ChanRec_Release"),
                   (0xFA6598, 4, "ld (XIX+0x15),0x00   ChanRec_Release  <-- what really zeroes it"),
                   (0xFA65CD, 3, "and C,0x03           sub_FA65BD guard: RELEASED blocks it too")):
    print("     0x%06X  %-14s  %s" % (a, d[a-BASE:a-BASE+n].hex(" "), what))
print()

print("P6 -- the allocator's arm of the 0x0087BF mask")
for a, n, what in ((0xFA6D01, 2, "or (XBC),HL   0x0087C7 hold SET      (note lists this)"),
                   (0xFA6D37, 2, "and (XBC),WA  0x0087C7 hold CLEAR    (note lists this)"),
                   (0xFA6D39, 5, "lda XBC,0x0087bf                    (note does NOT list this)"),
                   (0xFA6D3E, 3, "add XBC,(XIZ+0xe3)"),
                   (0xFA6D41, 2, "or (XBC),HL   0x0087BF ARMED HERE"),
                   (0xFA6EE9, 2, "and (XBC),WA  0x0087C7 hold CLEAR    (note lists this)")):
    print("     0x%06X  %-18s  %s" % (a, d[a-BASE:a-BASE+n].hex(" "), what))
print()

print("P7 -- the two producers of voicerec[+0x29], the computed word that lands on BLOCK 0")
for a, n, what in ((0xFAA395, 3, "ld BC,0x0010"),
                   (0xFAA398, 2, "sub DE,BC"),
                   (0xFAA39C, 3, "sll 0x08,IY     -> DE = (param - 16) << 8"),
                   (0xFAA3A1, 6, "ld BC,HL / or BC,IX / or BC,DE"),
                   (0xFAA3AC, 3, "ld (XWA+0x29),BC"),
                   (0xFAA499, 3, "sll 0x09,IX"),
                   (0xFAA4AA, 3, "sll 0x0c,DE"),
                   (0xFAA4B8, 3, "ld (XWA+0x29),BC")):
    print("     0x%06X  %-18s  %s" % (a, d[a-BASE:a-BASE+n].hex(" "), what))
print("   => the HIGH BYTE of the block-0 computed word is a shifted parameter, so")
print("      param 0x8E gives 0x7E00 and param 0x91 gives 0x8100 when the OR'd low")
print("      bits are zero.  The report's model treats those two words as lifecycle")
print("      commands wherever they appear on block 0.  UNTESTED COLLISION RISK.")

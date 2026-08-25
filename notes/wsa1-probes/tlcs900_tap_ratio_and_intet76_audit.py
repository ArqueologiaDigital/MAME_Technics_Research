#!/usr/bin/env python3
"""Adversarial audit of three claims made for the tmp95c061 timer fix (8ec12c6).

Run:  python3 notes/wsa1-probes/tlcs900_tap_ratio_and_intet76_audit.py

CLAIM 1 -- "the firmware's 1750 tempo-tracker constant adjudicates the prescaler
tap scale: it fits tmp94c241's fc/8 scale to 2.3% and misses tmp95c061's old
scale by 16.4x."  REFUTED here.  The constant is a ratio between TWO taps of the
SAME prescaler (phiT256 for timer 1, phiT1 for timer 4), and both candidate
scales differ by a UNIFORM factor of 16, so the ratio is identical -- 256 -- in
both.  Both predict 1792.  The published 28672 was produced by pairing
tmp95c061's phiT256 (32768) with tmp94c241's phiT1 (8): two devices' scales in
one formula.  The 1750 constant is CONSISTENT WITH the fix, it does not select it.

CLAIM 2 -- "INTET76 is never written, so the deliberate-hang vectors 0x54/0x58/
0x5C (0xF82D09 = `jr T,self`) are unreachable."  HOLDS, but the published scan
covered one encoding (`08 76 ii`) in one image (prom_a).  CPU1 also executes
prom_b, and internal I/O 0x76 can also be written by `0a 76 ii ii`, by
`0a 75 ii ii` (a word store at 0x75 lands its high byte on 0x76), by the
`f0 76 ..` 8-bit-direct operand prefix and by `f1 76 00 ..`.  This script scans
all five encodings across all four WSA1 images and the KN1500 image and prints
the candidates; every one of them gates to data or to a `cp X,0x08` / `jrl`
pair when disassembled (see the report for the gated listing).

CLAIM 3 -- "no micro-DMA vector aliases INTTR4-7."  HOLDS.  tlcs900_process_hdma
matches (DMAVn & 0x1f) << 2 against the vector map, so DMAVn values with
(V & 0x1f) in 0x14..0x17 would consume INTTR4..INTTR7 instead of dispatching
them.  Prints every such write for gating.
"""
import sys

ROMS = {
 'wsa1 prom_a ic12': ('/home/fsanches/compartilhado/technics_roms/roms/wsa1/wsa1_os_v2.ic12', 0xF80000),
 'wsa1 prom_b ic13': ('/home/fsanches/compartilhado/technics_roms/roms/wsa1/wsa1_os_v2.ic13', 0xF00000),
 'wsa1 prom_c ic28': ('/home/fsanches/compartilhado/technics_roms/roms/wsa1/wsa1_os_v2.ic28', 0xF80000),
 'wsa1 prom_d ic21': ('/home/fsanches/compartilhado/technics_roms/roms/wsa1/wsa1_os_v2.ic21', 0x000000),
 'kn1500 ic15':      ('/home/fsanches/compartilhado/kn7000-emulator/roms/kn1500/'
                      'technics_qsigt3c16079_5y68-j079_japan_9649eai.ic15', 0xE00000),
}
fail = 0

def claim1():
    global fail
    print("== CLAIM 1: does the 1750 constant select a tap scale? ==")
    # TREG5 = 7 * A * (D_phiT256 / D_phiT1):  24 MIDI clk/beat, TREG1=28, 96 PPQN
    for name, sh in (("tmp94c241  shifts 3,5,7,11", (3, 11)),
                     ("tmp95c061  shifts 7,9,11,15", (7, 15)),
                     ("hypothetical /2  4,6,8,12", (4, 12))):
        d1, d256 = 1 << sh[0], 1 << sh[1]
        pred = 7.0 * d256 / d1
        print(f"   {name:30s} phiT256/phiT1 = {d256//d1:5d}   predicts {pred:8.1f}"
              f"   err vs 1750 = {100*(pred-1750)/1750:+.2f}%")
    if (1 << 15) // (1 << 7) != (1 << 11) // (1 << 3):
        print("   FAIL: the two scales do NOT share a tap ratio"); fail += 1
    else:
        print("   -> identical ratio in every uniform rescale: the constant CANNOT discriminate.")
    print(f"   published 28672 = 7 * {28672//7} = 7 * 32768/8  <- mixed-device denominator\n")

def claim2():
    pats = {b'\x08\x76': 'ld (0x76),imm8',
            b'\x0a\x76': 'ldw (0x76),imm16',
            b'\x0a\x75': 'ldw (0x75),imm16 -> high byte lands on 0x76',
            b'\xf0\x76': '(0x76) 8-bit-direct operand prefix',
            b'\xf1\x76\x00': '(0x0076) 16-bit-direct operand prefix'}
    print("== CLAIM 2: every encoding that can write INTET76 (0x76) ==")
    for name, (p, base) in ROMS.items():
        d = open(p, 'rb').read()
        print(f"   {name}")
        for pat, desc in pats.items():
            hits, i = [], 0
            while True:
                i = d.find(pat, i)
                if i < 0: break
                hits.append(base + i); i += 1
            if hits:
                print(f"      {desc:44s} {len(hits):3d}  "
                      + ' '.join(hex(h) for h in hits[:12])
                      + (' ...' if len(hits) > 12 else ''))
    print("   (gate each with notes/wsa1-probes/wsa1_dis.sh before believing it)\n")

def claim3():
    print("== CLAIM 3: DMAV writes that would alias INTTR4..INTTR7 ==")
    print("   dangerous when (V & 0x1f) in {0x14,0x15,0x16,0x17}  (vector = (V&0x1f)<<2)")
    for name, (p, base) in ROMS.items():
        d = open(p, 'rb').read()
        for reg in range(0x7c, 0x80):
            i = 0
            while True:
                i = d.find(b'\x08' + bytes([reg]), i)
                if i < 0: break
                v = d[i + 2]
                if (v & 0x1f) in (0x14, 0x15, 0x16, 0x17):
                    print(f"      {name} {hex(base+i)}  DMAV{reg-0x7c}=0x{v:02x}"
                          f" -> vector 0x{4*(v&0x1f):02x}")
                i += 1
    print("   (all WSA1 hits gate to data tables or to `cp X,0x08` / `jrl` pairs)\n")

def boot_bytes():
    global fail
    print("== the boot writes both machines make, re-read from the images ==")
    checks = [
      ('wsa1 prom_a ic12', 0xF826EB, '08 24 0d', 'T01MOD = 0x0D  (timer 1 clock select 3 = phiT256)'),
      ('wsa1 prom_a ic12', 0xF826F4, '08 23 1c', 'TREG1  = 0x1C = 28'),
      ('wsa1 prom_a ic12', 0xF82703, '08 38 05', 'T4MOD  = 0x05  (bits[1:0]=01 = phiT1)'),
      ('wsa1 prom_a ic12', 0xF8270C, '08 30 01', 'TREG4L = 0x01'),
      ('wsa1 prom_a ic12', 0xF82712, '08 32 09', 'TREG5L = 0x09'),
      ('wsa1 prom_a ic12', 0xF82715, '08 33 3d', 'TREG5H = 0x3D  -> TREG5 = 15625'),
      ('wsa1 prom_a ic12', 0xF8272A, '08 20 b7', 'TRUN   = 0xB7  (bit7 pre, bit5 T5RUN, bit4 T4RUN)'),
      ('wsa1 prom_a ic12', 0xF827CE, '08 75 03', 'INTET54= 0x03  (INTTR4 prio 3, INTTR5 prio 0)'),
      ('wsa1 prom_a ic12', 0xF82D09, '68 fe',    'vec 0x54/58/5C target = jr T,self  (DELIBERATE HANG)'),
      ('wsa1 prom_a ic12', 0xF82EB1, '83 3f 60', 'INTTR4 handler wraps its counter at 0x60 = 96 PPQN'),
      ('wsa1 prom_a ic12', 0xFA5553, 'd8 09 d6 06', 'muls WA,0x06D6 = 1750  (the tempo tracker)'),
      ('wsa1 prom_a ic12', 0xFA5559, '30 35 47', 'ld WA,0x4735 = 18229 -> 120.00 BPM'),
      ('kn1500 ic15',      0xFE5FB5, '08 38 05', 'T4MOD  = 0x05'),
      ('kn1500 ic15',      0xFE5FC4, '0a 30 01 00', 'ldw (TREG4),0x0001'),
      ('kn1500 ic15',      0xFE5FC8, '0a 32 09 3d', 'ldw (TREG5),0x3D09 = 15625'),
      ('kn1500 ic15',      0xFE5FCC, '08 20 ff', 'TRUN   = 0xFF'),
      ('kn1500 ic15',      0xFE6078, '08 75 03', 'INTET54= 0x03'),
    ]
    for img, addr, want, meaning in checks:
        p, base = ROMS[img]
        d = open(p, 'rb').read()
        n = len(want.split())
        got = d[addr-base:addr-base+n].hex(' ')
        ok = (got == want)
        if not ok: fail += 1
        print(f"   [{'PASS' if ok else 'FAIL'}] {img} {hex(addr)} = {got:12s}  {meaning}")
    print()

def rates():
    print("== the rates those registers imply, and what was MEASURED ==")
    for mach, fc, treg5, bpmname in (("wsa1  ", 28e6, 15625, "boot"),
                                     ("wsa1  ", 28e6, 18229, "runtime 0x4735"),
                                     ("kn1500", 24e6, 15625, "boot")):
        for D, tag in ((8, 'fc/8  (this fix)'), (16, 'fc/16 (2x alt)'),
                       (4, 'fc/4  (2x alt)'), (128, 'fc/128 (upstream)')):
            hz = fc / D / treg5
            print(f"   {mach} fc={fc/1e6:4.0f}MHz TREG5={treg5:5d} {bpmname:14s}"
                  f" {tag:18s} -> {hz:8.2f} Hz = {hz/96*60:9.2f} BPM")
        print()
    print("   MEASURED (tlcs900_timer_rate_refutation.lua, 2026-08-25):")
    print("     wsa1r  INTTR4 224.0 Hz for t<12s, then 192.0 Hz;  tick(0x80) 488.0 Hz")
    print("     kn1500 INTTR4 192.0 Hz for t<3s (then its known boot failure)")
    print("   Both match the fc/8 row exactly.  Note that fc/4 and fc/16 also land on")
    print("   round tempos (280/240 and 70/60): the round-tempo argument pins the tap")
    print("   only up to a power of two.  What excludes those is fc itself.\n")

if __name__ == '__main__':
    claim1(); boot_bytes(); rates(); claim2(); claim3()
    print(f"{'FAILURES: %d' % fail if fail else 'byte-level checks: all PASS'}")
    sys.exit(1 if fail else 0)

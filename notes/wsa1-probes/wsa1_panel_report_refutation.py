#!/usr/bin/env python3
"""Adversarial re-derivation of the "SC1 is the control panel" report (commit d2f173b).

QUESTION IT ANSWERS: which of that report's load-bearing numbers survive an
independent derivation from the ROM bytes, and which are wrong?  Nothing here
imports the report's own probes -- every number is recomputed from the images.

    python3 wsa1_panel_report_refutation.py            # prints CONFIRM / REFUTE / NOTE
    python3 wsa1_panel_report_refutation.py --selftest # same, exits non-zero on regression

WHAT EACH SECTION MEASURES
  A  the >=16-byte common-substring diff, AND the whole-prom_b null the report
     never ran.  The null is the result: of 4399 such runs between prom_b and
     the KN5000 ROM, exactly 8 land in the KN5000 panel driver and all 8 come
     from the SC1 module.  That is a bijection, not a cluster.
  B  the size of the KN5000 panel-driver window.  The report says 2,767 bytes /
     0.13%; 0xFC4C34-0xFC3E65 is 3,535 bytes / 0.169%, and the report's own
     wsa1_kn5000_panel_bytediff.py prints 3535.
  C  the two strap variant group tables at prom_a 0xF8A109 / 0xF8A189, reversed
     through the firmware's own index rule ((a&0xC0)>>1)|(a&0x1F) taken from
     Panel_DrainInboundQueue 0xF8A0A3-0xF8A0AC.
  D  the four analogue curve tables.  The report calls 0xD1 "the one curve" with
     a dead zone; 0xD2's table has one too.
  E  the button shadow index.  The report states 0x2B20 + (addr&0x0F) + 0x10;
     the ROM makes the +0x10 CONDITIONAL on address bit 6 (0xF5B0FD-0xF5B10D).
  F  Dev7A_StartDma's ten command bytes scored against the uPD765 command set,
     with the null the report never gave.  Opcodes 10/10; directions 7/10, not
     the reported 9/10 -- there are three SCAN commands, not one.

SIGNALS READ
  prom_b  0xF5A800-0xF5B44D  the SC1 module          (base 0xF00000)
  prom_a  0xF8A109 / 0xF8A189   variant group tables (base 0xF80000)
  prom_a  0xF89AB4 / 0xF89B34 / 0xF89C34 / 0xF89CB4  the four analogue curves
  prom_a  0xFE596A             Dev7A_StartDma
  KN5000  0xFC3E65-0xFC4C33    CPanel_InitDispatchTable .. CPanel_DecEventPtr
                               (from kn5000-roms-disasm/symbols/maincpu_v10_symbols_reference.txt)
"""
import sys
from collections import defaultdict

WSA1 = '/home/fsanches/compartilhado/wsa1-roms-disasm/original_ROMs/'
KN5K = '/home/fsanches/compartilhado/technics_roms/roms/kn5000/kn5000_v10_program.rom'
A = open(WSA1 + 'wsa1_prom_a.ic12', 'rb').read(); A_BASE = 0xF80000
B = open(WSA1 + 'wsa1_prom_b.ic13', 'rb').read(); B_BASE = 0xF00000
K = open(KN5K, 'rb').read();                      K_BASE = 0xE00000

SC1_LO, SC1_HI = 0xF5A800, 0xF5B44E     # the module, end-exclusive
CP_LO,  CP_HI  = 0xFC3E65, 0xFC4C34     # KN5000 panel driver, end-exclusive

fails = []
def confirm(ok, msg):
    """`ok` means THE MEASUREMENT CAME OUT AS THIS SCRIPT EXPECTS -- which for some
    lines means the report was right and for others means it was wrong.  A FAIL
    here is a regression in the ROM/tooling, not a verdict about the report."""
    print(("ok    " if ok else "FAIL  ") + msg)
    if not ok: fails.append(msg)
def note(msg): print("NOTE     " + msg)


def maximal_runs(hay, hay_base, needle_rom, k=16):
    """Every maximal common substring >= k bytes between `hay` and `needle_rom`."""
    idx = defaultdict(list)
    for i in range(len(needle_rom) - k + 1):
        idx[needle_rom[i:i+k]].append(i)
    out, i = [], 0
    while i <= len(hay) - k:
        g = hay[i:i+k]
        if g in idx:
            best = None
            for j in idx[g][:200]:
                n = k
                while i+n < len(hay) and j+n < len(needle_rom) and hay[i+n] == needle_rom[j+n]: n += 1
                b = 0
                while i-b-1 >= 0 and j-b-1 >= 0 and hay[i-b-1] == needle_rom[j-b-1]: b += 1
                if best is None or n+b > best[0]: best = (n+b, i-b, j-b)
            out.append(best); i = best[1] + best[0]
        else:
            i += 1
    ded = []
    for m in out:
        if ded and m[1] < ded[-1][1] + ded[-1][0]: continue
        ded.append(m)
    return ded


print("=" * 74)
print("A. the diff, and the null the report never ran")
print("=" * 74)
mod = B[SC1_LO-B_BASE:SC1_HI-B_BASE]
runs = maximal_runs(mod, SC1_LO, K)
tot = sum(r[0] for r in runs)
for n, i, j in runs:
    print(f"    {n:3d} B   wsa1 0x{SC1_LO+i:06X}   kn5000 0x{K_BASE+j:06X}")
confirm(len(runs) == 8 and tot == 154,
        f"module vs KN5000: {len(runs)} runs >=16B, {tot} bytes  (report: 8 / 154)")
confirm(all(CP_LO <= K_BASE+j < CP_HI for _, _, j in runs),
        "all of them land inside the KN5000 panel driver")

allruns = maximal_runs(B, B_BASE, K)
inpanel = [r for r in allruns if CP_LO <= K_BASE+r[2] < CP_HI]
insc1   = [r for r in inpanel if SC1_LO <= B_BASE+r[1] < SC1_HI]
note(f"whole 512 KiB prom_b vs the KN5000 ROM: {len(allruns)} runs >=16B, "
     f"{sum(r[0] for r in allruns)} bytes")
confirm(len(inpanel) == 8 and len(insc1) == 8,
        f"of those, {len(inpanel)} land in the panel driver and {len(insc1)} of them are "
        "in the SC1 module -- A BIJECTION, which is stronger than the report claimed")
edge = [r for r in allruns if B_BASE+r[1] == SC1_HI-1]
confirm(len(edge) == 1,
        "a 9th run >=16B begins at the module's LAST byte (wsa1 0xF5B44D -> kn5000 0xFC3E4E, "
        "ending exactly at the panel driver's first byte) -- the count 8 is window-sensitive")

print()
print("=" * 74)
print("B. the size of the KN5000 panel-driver window")
print("=" * 74)
size = CP_HI - CP_LO
confirm(size == 3535,
        f"0xFC3E65-0xFC4C33 is {size} bytes = {100*size/len(K):.3f}% of the 2 MiB ROM "
        f"-- the report says 2,767 bytes / 0.13%")

print()
print("=" * 74)
print("C. the two strap variant tables (index rule from prom_a 0xF8A0A3)")
print("=" * 74)
def groups(tab_addr):
    t = A[tab_addr-A_BASE:tab_addr-A_BASE+128]
    m = {}
    for a in range(0xC0, 0xE0):                       # panel id 11 only
        v = t[((a & 0xC0) >> 1) | (a & 0x1F)]
        if v != 0x20: m[a] = v
    return m
v1, v2 = groups(0xF8A109), groups(0xF8A189)
btn1 = sorted(a for a in v1 if a < 0xD0); ana1 = sorted(a for a in v1 if a >= 0xD0)
btn2 = sorted(a for a in v2 if a < 0xD0); ana2 = sorted(a for a in v2 if a >= 0xD0)
note("V1 buttons  " + " ".join("%02X" % a for a in btn1) + "   analogue " + " ".join("%02X" % a for a in ana1))
note("V2 buttons  " + " ".join("%02X" % a for a in btn2) + "   analogue " + " ".join("%02X" % a for a in ana2))
confirm(len(btn1) == 11 and len(btn2) == 9 and set(btn1)-set(btn2) == {0xC6, 0xCA},
        f"button segments: {len(btn1)} vs {len(btn2)}, missing in V2 = "
        + " ".join("0x%02X" % a for a in sorted(set(btn1)-set(btn2))))
confirm(ana1 == [0xD0, 0xD1, 0xD2, 0xD3, 0xD7] and ana2 == [0xD3, 0xD7],
        "analogue: V1 = D0 D1 D2 D3 D7 (four pots + encoder), V2 = D3 D7 (one pot + encoder)")
led1 = A[0xF8C8AC-A_BASE:0xF8C8AC-A_BASE+8]
led2 = A[0xF8C8B7-A_BASE:0xF8C8B7-A_BASE+8]
confirm(list(led1) == [0xC0,0xC1,0xC2,0xC4,0xC5,0xC9,0xCC,0xCD]
        and list(led2) == [0xC1,0xC2,0xC9,0xCA,0xCB,0xCC,0xC3,0x00],
        "LED wire tables: V1 = " + " ".join("%02X" % x for x in led1)
        + " | V2 = " + " ".join("%02X" % x for x in led2))
note("Panel_RefreshLeds 0xF8C456 does `ld B,0x08` and steps 8 registers in BOTH variants, "
     "so V2's 8th entry 0x00 IS emitted on the wire -- 'seven registers' is a count of "
     "non-zero entries, not of what the firmware sends")

print()
print("=" * 74)
print("D. the four analogue curves -- is 0xD1 really 'the one' with a dead zone?")
print("=" * 74)
def longest_run(t):
    best = (0, None, None); cur = 1
    for i in range(1, len(t)):
        if t[i] == t[i-1]: cur += 1
        else:
            if cur > best[0]: best = (cur, t[i-1], i-cur)
            cur = 1
    if cur > best[0]: best = (cur, t[-1], len(t)-cur)
    return best
curves = {0xD3: (0xF89AB4, 128), 0xD2: (0xF89B34, 128), 0xD0: (0xF89C34, 128), 0xD1: (0xF89CB4, 256)}
plateaus = {}
for wire, (addr, n) in sorted(curves.items()):
    t = A[addr-A_BASE:addr-A_BASE+n]
    L, val, at = longest_run(t)
    plateaus[wire] = (L, val)
    note(f"wire 0x{wire:02X}  table 0x{addr:06X}  {n} entries  span {min(t)}..{max(t)}  "
         f"longest plateau = {L} x 0x{val:02X} at index {at}")
confirm(plateaus[0xD1] == (18, 0x80),
        "0xD1's curve is 256 entries with an 18-entry plateau at 0x80 -- as reported")
confirm(plateaus[0xD2][0] == 13 and plateaus[0xD2][1] == 0x40,
        f"but 0xD2's curve ALSO has a centre plateau ({plateaus[0xD2][0]} entries at "
        f"0x{plateaus[0xD2][1]:02X}, its own midpoint) -- so 'the one curve' is FALSE, "
        "there are TWO centre-detented controls in variant 1")
note("and the substitute values the V2 gate writes are 0xD0 -> 0x00 (0xF89A30), "
     "0xD1 -> 0x80 (0xF899FA), 0xD2 -> 0x40 (0xF89A61): a minimum and two midpoints. "
     "0xD3's handler at 0xF89A8B has NO (0xC4) test -- it is present on both machines.")

print()
print("=" * 74)
print("E. the button shadow index at prom_b 0xF5B0FD")
print("=" * 74)
shape = B[0xF5B0FD-B_BASE:0xF5B10F-B_BASE]
want = bytes([0xC8,0xCC,0x4F, 0x43,0x20,0x2B,0x00,0x00, 0xC8,0x33,0x06, 0x66,0x03,
              0xC8,0xCA,0x30, 0xC8,0x87])
confirm(shape == want,
        "SC1_RxOp0 does `and W,0x4F / ld XHL,0x2B20 / bit 6,W / jr Z / sub W,0x30 / add L,W`, "
        "i.e. index = (addr & 0x0F) | ((addr & 0x40) >> 2) -- the report's "
        "'0x2B20 + (addr&0x0F) + 0x10' states a CONDITIONAL as unconditional "
        "(it happens to be right for the 0xC0..0xCF buttons, which all have bit 6 set)")

print()
print("=" * 74)
print("F. Dev7A_StartDma's ten codes vs the uPD765 command set, with a null")
print("=" * 74)
CMD = {0x02:('READ TRACK',0x40), 0x03:('SPECIFY',0x00), 0x04:('SENSE DRIVE ST',0x00),
       0x05:('WRITE DATA',0xC0), 0x06:('READ DATA',0xE0), 0x07:('RECALIBRATE',0x00),
       0x08:('SENSE INT ST',0x00), 0x09:('WRITE DELETED',0xC0), 0x0A:('READ ID',0x40),
       0x0C:('READ DELETED',0xE0), 0x0D:('FORMAT TRACK',0x40), 0x0F:('SEEK',0x00),
       0x11:('SCAN EQUAL',0xE0), 0x19:('SCAN LOW/EQ',0xE0), 0x1D:('SCAN HIGH/EQ',0xE0)}
legal = {}
for op, (nm, fl) in CMD.items():
    sub = [0]
    for b in (0x80, 0x40, 0x20):
        if fl & b: sub = sub + [s | b for s in sub]
    for s in sub: legal[op | s] = nm
# read the ten immediates straight out of the routine: `d8 cf <lo> 00` = cp WA,imm16
obs = []
o = 0xFE596A - A_BASE
for i in range(o, o + 0x50):
    if A[i] == 0xD8 and A[i+1] == 0xCF and A[i+3] == 0x00:
        obs.append(A[i+2])
CPU_TO_FDC = {0x05, 0x09, 0x0D, 0x11, 0x19, 0x1D}
grpA = set(obs[:3])                     # -> Dev7A_Dma_RamToDevice 0xFE59D2
grpB = set(obs[3:])                     # -> Dev7A_Dma_DeviceToRam 0xFE59BB
ok_op = ok_dir = 0
for b in obs:
    nm = legal.get(b)
    if nm: ok_op += 1
    want_d = 'A' if (b & 0x1F) in CPU_TO_FDC else 'B'
    got_d = 'A' if b in grpA else 'B'
    if want_d == got_d: ok_dir += 1
    print(f"    0x{b:02X}  {nm or 'NOT A LEGAL COMMAND':16s} dir want={want_d} got={got_d}"
          + ("" if want_d == got_d else "   MISMATCH"))
p = len(legal) / 256
confirm(len(obs) == 10 and ok_op == 10,
        f"ten codes read from the ROM, {ok_op}/10 are legal uPD765 command bytes "
        f"(only {len(legal)}/256 byte values are; P(ten arbitrary bytes all legal) = {p**10:.2g})")
confirm(ok_dir == 7,
        f"directions: {ok_dir}/10, NOT the reported 9/10 -- there are THREE SCAN commands "
        "(0xD1/0xD9/0xDD) in the device->RAM group, and each needs a CPU->FDC data phase")

print()
print("=" * 74)
print(f"REGRESSIONS: {len(fails)}   (0 = every measurement reproduced)")
for f in fails: print("  - " + f)
# The gate is REGRESSION, not agreement with the report: it fails if any measured
# value moves, whether that value agreed with the report or contradicted it.
sys.exit(1 if fails else 0)

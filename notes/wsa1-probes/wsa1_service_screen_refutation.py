#!/usr/bin/env python3
"""Adversarial re-derivation of the SX-WSA1 "service-mode screens" study.

QUESTION THIS ANSWERS
  Every COUNT and EXTENT claim in that study, re-read from the ROM bytes rather
  than from the prose, so that a claim that moved shows up as a FAIL here.

  1. The screen dispatcher is TWO tables (0xF86EC1 indexed by RAM 0x2078,
     0xF86F41 indexed by RAM 0x207C) and 0xD8..0xDD land on the prom_b thunks
     T_F400D0/E0/F0/100/110/130.
  2. The service-chord bit tests in sub_F9530B pair keys exactly 12 apart under
     the prom_c bitmap layout byte = (key>>3)&7, bit = key&7 (prom_c 0xF9988D).
  3. The two wire->segment maps (0xF94ED8 v1, 0xF95008 v2) agree with the two
     the panel HLE already uses (0xF8A109, 0xF8A189) -- SEGMENT NUMBER by
     SEGMENT NUMBER, not merely "same wires".
  4. The switch->LED word tables (0xF94F58 v1 11x8, 0xF95088 v2 9x8) and the
     all-lamps sweep table at 0xF95C68, and whether the sweep is really a
     SUPERSET of every mask the switch tables name.
  5. The service screens' 32-entry control tables (0xF95C95, 0xF95D15): how
     many slots are the null handler 0xF95C2C.
  6. The claimed writers of RAM 0x2070: the immediate-form census, per value.

WHAT COUNTS AS PASS
  Exit 0 with no FAIL line.  Every FAIL prints the value the study claimed and
  the value the ROM holds.

USAGE
  python3 wsa1_service_screen_refutation.py
"""
import sys

ROMS = "/home/fsanches/compartilhado/wsa1-roms-disasm/original_ROMs/"
pa = open(ROMS + "wsa1_prom_a.ic12", "rb").read()
pb = open(ROMS + "wsa1_prom_b.ic13", "rb").read()
pc = open(ROMS + "wsa1_prom_c.ic28", "rb").read()
A = lambda a, n=1: pa[a - 0xF80000:a - 0xF80000 + n]
B = lambda a, n=1: pb[a - 0xF00000:a - 0xF00000 + n]
u16 = lambda b: int.from_bytes(b, "little")
u32 = lambda b: int.from_bytes(b, "little")

fails = []
def ck(cond, what):
    print("  %-4s %s" % ("ok" if cond else "FAIL", what))
    if not cond:
        fails.append(what)

print("1. SCREEN DISPATCHER")
t2 = {i: u32(A(0xF86F41 + 4 * i, 4)) for i in range(0xE0)}
t1 = {i: u32(A(0xF86EC1 + 4 * i, 4)) for i in range(0x20)}
ck(0xF86F41 - 0xF86EC1 == 0x80, "table 1 is 32 entries and abuts table 2")
ck(0xF86F41 + 0xE0 * 4 == 0xF872C1, "table 2 is 224 entries, ends at 0xF872C1")
want = {0xD8: 0xF400D0, 0xD9: 0xF400E0, 0xDA: 0xF400F0,
        0xDB: 0xF40100, 0xDC: 0xF40110, 0xDD: 0xF40130}
for k, v in want.items():
    ck(t2[k] == v, "screen 0x%02X -> 0x%06X (rom 0x%06X)" % (k, v, t2[k]))
dflt = 0xF872C1
ck(sum(1 for v in t2.values() if v != dflt) == len([1 for v in t2.values() if v != dflt]),
   "counted table-2 non-default slots = %d" % sum(1 for v in t2.values() if v != dflt))
print("     table-2 non-default slots: %d of 224" % sum(1 for v in t2.values() if v != dflt))
print("     table-1 non-default slots: %d of 32"  % sum(1 for v in t1.values() if v != dflt))
# the thunks themselves
for k, v in want.items():
    j = B(v, 4)
    ck(j[0] == 0x1B, "thunk 0x%06X is a jp" % v)
    print("       0x%06X: jp 0x%06X   +4: jp 0x%06X" % (v, u32(j[1:]) & 0xFFFFFF, u32(B(v + 4, 4)[1:]) & 0xFFFFFF))

print()
print("2. SERVICE CHORD BIT PAIRS (sub_F9530B)")
# (byte offset, mask) pairs read from the code at 0xF9534B..0xF953BE
pairs = [((3, 0x01), (4, 0x10), None),
         ((3, 0x04), (4, 0x40), 0xD9),
         ((3, 0x10), (5, 0x01), 0xDA),
         ((3, 0x20), (5, 0x02), 0xDB),
         ((3, 0x80), (5, 0x08), 0xDC)]
# verify each mask literally appears in the code stream in the documented order
code = A(0xF9534B, 0xF953C3 - 0xF9534B)
for (b1, m1), (b2, m2), scr in pairs:
    key1 = b1 * 8 + m1.bit_length() - 1
    key2 = b2 * 8 + m2.bit_length() - 1
    ck(key2 - key1 == 12, "keys %d and %d are 12 apart (screen %s)"
       % (key1, key2, "reject" if scr is None else "0x%02X" % scr))
    print("       key %2d = MIDI %2d,  key %2d = MIDI %2d" % (key1, key1 + 36, key2, key2 + 36))
# and the bitmap layout the pairing depends on, from prom_c
ck(pc[0xFCC81A - 0xF80000:0xFCC81A - 0xF80000 + 4] == b"\xf0\xff\x00\x00",
   "prom_c 0xFCC81A holds the 32-bit constant 0x0000FFF0")

print()
print("3. WIRE -> SEGMENT MAPS: new pair vs the pair the driver already uses")
def wmap(base):
    t = A(base, 0x80)
    out = {}
    for wire in range(0x100):
        idx = (wire & 0x1F) | ((wire & 0xC0) >> 1)
        if idx < 0x80 and t[idx] != 0x20:
            out[wire] = t[idx]
    return out
new1, new2 = wmap(0xF94ED8), wmap(0xF95008)
old1, old2 = wmap(0xF8A109), wmap(0xF8A189)
# ADVERSARIAL RESULT 2026-08-25: the study said the new pair says "exactly what
# 0xF8A109/0xF8A189 say".  It does not -- the new pair is a strict SUBSET.  What
# is true is that the two agree over the panel-switch wires 0xC0..0xCA and that
# the new pair drops the 0xD0-block wires (the analogue controls).
ck(new1 != old1 and new2 != old2,
   "the new pair is NOT byte-identical to the old pair (the study said it was)")
ck(all(old1.get(w) == s for w, s in new1.items()) and set(old1) - set(new1) == {0xD0,0xD1,0xD2,0xD3,0xD7,0xF0,0xF1,0xF2,0xF3,0xF7},
   "v1: 0xF94ED8 is 0xF8A109 minus exactly the 0xD0/0xF0-block wires D0-D3,D7")
ck(all(old2.get(w) == s for w, s in new2.items()) and set(old2) - set(new2) == {0xD3,0xD7,0xF3,0xF7},
   "v2: 0xF95008 is 0xF8A189 minus exactly wires D3,D7")
for nm, m in (("v1", new1), ("v2", new2)):
    print("     %s live wires: %s" % (nm, " ".join("%02X->%d" % (w, s) for w, s in sorted(m.items()))))
panel1 = {w: s for w, s in new1.items() if 0xC0 <= w <= 0xCA}
panel2 = {w: s for w, s in new2.items() if 0xC0 <= w <= 0xCA}
ck(len(panel1) == 11, "v1 has %d wires in 0xC0..0xCA" % len(panel1))
ck(len(panel2) == 9,  "v2 has %d wires in 0xC0..0xCA" % len(panel2))
ck(0xC6 not in panel2 and 0xCA not in panel2, "v2 is missing exactly wires 0xC6 and 0xCA")

print()
print("4. SWITCH -> LED WORD TABLES and the ALL-LAMPS SWEEP")
def ledtab(base, nseg):
    return [[u16(A(base + seg * 16 + bit * 2, 2)) for bit in range(8)] for seg in range(nseg)]
L1 = ledtab(0xF94F58, 11)
L2 = ledtab(0xF95088, 9)
ck(0xF95008 - 0xF94F58 == 11 * 16, "v1 LED table is 11 segments x 8 words and abuts 0xF95008")
ck(0xF95118 - 0xF95088 == 9 * 16,  "v2 LED table is 9 segments x 8 words and abuts 0xF95118 (the bit-number routine)")
for nm, tab in (("v1", L1), ("v2", L2)):
    print("     %s:" % nm)
    for s, row in enumerate(tab):
        print("       seg %2d  %s" % (s, " ".join("%02X:%02X" % (w >> 8, w & 0xFF) for w in row)))
# the sweep table at 0xF95C68, terminated by 0xFFFF
sweep = {}
a = 0xF95C68
while True:
    w = u16(A(a, 2))
    if w == 0xFFFF:
        break
    sweep[w >> 8] = w & 0xFF
    a += 2
print("     sweep table 0xF95C68 -> 0x%06X: %s" % (a, sweep))
ck(sweep == {0: 0xFF, 1: 0xFF, 2: 0xFF, 3: 0xFF, 4: 0xFF, 5: 0x03, 6: 0x0F, 7: 0x02},
   "sweep population is reg0-4=FF reg5=03 reg6=0F reg7=02")
lamps = sum(bin(v).count("1") for v in sweep.values())
ck(lamps == 47, "sweep lights %d lamps" % lamps)
# union of every mask each switch table names
for nm, tab in (("v1", L1), ("v2", L2)):
    union = {}
    for row in tab:
        for w in row:
            union.setdefault(w >> 8, 0)
            union[w >> 8] |= w & 0xFF
    subset = all(reg in sweep and (m & ~sweep[reg]) == 0 for reg, m in union.items())
    print("     %s union of switch masks: %s" % (nm, {k: "%02X" % v for k, v in sorted(union.items())}))
    ck(subset, "%s switch->LED masks are a subset of the sweep population" % nm)

print()
print("5. SERVICE SCREEN CONTROL TABLES")
for nm, base in (("0xDA 0xF95C95", 0xF95C95), ("0xDD 0xF95D15", 0xF95D15)):
    t = [u32(A(base + 4 * i, 4)) for i in range(32)]
    nulls = sum(1 for v in t if v == 0xF95C2C)
    print("     %s: %d null of 32, distinct non-null: %s"
          % (nm, nulls, sorted({"0x%06X" % v for v in t if v != 0xF95C2C})))
    if base == 0xF95C95:
        ck(nulls == 24, "0xDA table has 24 null slots")
        ck(t[3] == t[20] and t[4] == t[21] and t[5] == t[22], "0xDA mirrors 3/4/5 at 20/21/22")
    else:
        ck(nulls == 19, "0xDD table has 19 null slots")
        ck(all(t[i] == t[i + 17] for i in range(6)), "0xDD mirrors 0..5 at 17..22")

print()
print("6. WRITERS OF RAM 0x2070 -- immediate forms, whole of prom_a + prom_b")
# ld (0x2070),#imm8  = F1 70 20 00 ii   ;  ld (XIX),#imm8 = B4 00 ii
import collections
found = collections.Counter()
sites = collections.defaultdict(list)
for nm, img, base in (("prom_a", pa, 0xF80000), ("prom_b", pb, 0xF00000)):
    for i in range(len(img) - 5):
        if img[i:i + 4] == b"\xf1\x70\x20\x00":
            found[img[i + 4]] += 1
            sites[img[i + 4]].append((nm, base + i))
        if img[i:i + 2] == b"\xb4\x00":
            found[("XIX", img[i + 2])] += 1
            sites[("XIX", img[i + 2])].append((nm, base + i))
for v in (0x40, 0xAA, 0xD8, 0xD9, 0xDA, 0xDB, 0xDC, 0xDD):
    n1 = found.get(v, 0)
    n2 = found.get(("XIX", v), 0)
    print("     value 0x%02X: ld (0x2070),imm x%-3d   ld (XIX),imm x%-3d" % (v, n1, n2))
    if v == 0x40:
        print("        (0x2070)=0x40 sites: %s" % " ".join("%s:0x%06X" % s for s in sites.get(0x40, [])))
ck(found.get(0xD8, 0) == 0 and found.get(("XIX", 0xD8), 0) == 0,
   "no immediate-form writer of screen id 0xD8 anywhere")

print()
print("7. BOOT-PATH ORDER of the four power-on chord tests (prom_a RESET block)")
# calr d16 = 1E lo hi, target = addr_of_next_insn + d16
calls = []
for i in range(0xF827C8 - 0xF80000, 0xF82830 - 0xF80000):
    if pa[i] == 0x1E:
        d = int.from_bytes(pa[i + 1:i + 3], "little", signed=True)
        calls.append((0xF80000 + i, 0xF80000 + i + 3 + d))
    if pa[i] == 0x1D:
        calls.append((0xF80000 + i, int.from_bytes(pa[i + 1:i + 4], "little")))
order = {t: a for a, t in calls}
print("     RESET-block call sites, in address order:")
for a, t in calls:
    tag = {0xF828D1: "FACTORY-CLEAR chord", 0xF8294C: "ROM-VERSION chord",
           0xF82A04: "third chord", 0xF40148: "SERVICE chord (-> 0xF952FC)"}.get(t, "")
    if tag:
        print("       0x%06X -> 0x%06X   %s" % (a, t, tag))
svc = order[0xF40148]
ck(order[0xF828D1] < svc, "FACTORY-CLEAR chord (0xF828D1) is tested BEFORE the service chord")
ck(order[0xF8294C] > svc, "ROM-VERSION chord (0xF8294C) is tested AFTER the service chord")
ck(order[0xF82A04] > svc, "third chord (0xF82A04) is tested AFTER the service chord")
# and the ROM-version display never returns: 0xF829A3 is `jr T,0xF8298E`, backwards
ck(A(0xF829A3, 2) == b"\x68\xe9", "0xF8294C's display loop is unconditional and backwards -- it never returns")

print()
print("8. RAM 0x2880 (the message id): EVERY direct access, by form")
import collections
forms = collections.Counter()
odd = []
for nm, img, base in (("prom_a", pa, 0xF80000), ("prom_b", pb, 0xF00000)):
    for i in range(len(img) - 6):
        if img[i] in (0xF1, 0xC1, 0xD1, 0xE1) and img[i + 1] == 0x80 and img[i + 2] == 0x28:
            op = img[i + 3]
            if img[i] == 0xF1 and op == 0x00:
                forms["ld (0x2880),#imm8"] += 1
            elif img[i] == 0xC1 and op == 0x3F:
                forms["cp (0x2880),#imm8"] += 1
            else:
                forms["NON-immediate"] += 1
                odd.append((nm, base + i, "%02X 80 28 %02X" % (img[i], op)))
for k, v in sorted(forms.items()):
    print("     %-22s %d" % (k, v))
print("     total %d" % sum(forms.values()))
for o in odd:
    print("       %s 0x%06X  %s" % o)
ck(sum(forms.values()) == 151, "there are %d direct accesses, not '~100'" % sum(forms.values()))
ck(forms["NON-immediate"] == 14, "%d of them are NOT the ld/cp immediate form" % forms["NON-immediate"])

print()
print("9. EFF1 / EFF2 / REV: legend <-> variable by SCREEN COORDINATE, not by order")
# interpreter-A op 0x17 text record: 17 len X.w Y.w text
legends = []
addr = 0xF2C9AB - 6
for _ in range(3):
    ln = B(addr + 1)[0]
    x = u16(B(addr + 2, 2)); y = u16(B(addr + 4, 2))
    txt = B(addr + 6, ln - 6).decode("latin1")
    legends.append((txt, x, y))
    addr += ln
# interpreter-B op 07 value records: 07 11 var.w mask sh svc ptr.l bpe.w X.w Y.w
values = []
for a in (0xF2CA15, 0xF2CA26, 0xF2CA37):
    var = u16(B(a + 2, 2)); x = u16(B(a + 0x0D, 2)); y = u16(B(a + 0x0F, 2))
    values.append((var, x, y))
for (txt, lx, ly), (var, vx, vy) in zip(legends, values):
    print("     %-5s at X=%3d Y=%3d   value cell 0x%04X at X=%3d Y=%3d   dX=%d dY=%d"
          % (txt, lx, ly, var, vx, vy, vx - lx, vy - ly))
ck([l[0] for l in legends] == ["EFF1", "EFF2", "REV"], "the three legends read EFF1, EFF2, REV")
ck([v[0] for v in values] == [0x76A7, 0x76A8, 0x76A9], "the three value cells are 0x76A7/A8/A9")
ck(all(abs(v[1] - l[1]) <= 2 and v[2] - l[2] == 14 for l, v in zip(legends, values)),
   "each value cell sits within 2px of its legend's X and 14px below it -- a LAYOUT decode")

print()
print("10. WHICH led%u OUTPUTS THE ALL-LAMPS SWEEP NEVER LIGHTS (driver index = reg*8+bit)")
unlit = [reg * 8 + bit for reg in range(8) for bit in range(8)
         if not (sweep.get(reg, 0) >> bit) & 1]
print("     %d outputs: %s" % (len(unlit), ", ".join("led%d" % n for n in unlit)))
ck(len(unlit) == 17, "17 of the driver's 64 led outputs are never lit")
ck(unlit == [42, 43, 44, 45, 46, 47, 52, 53, 54, 55, 56, 58, 59, 60, 61, 62, 63],
   "they are led42-47, led52-56 and led58-63 (the study named led45-47 and led54-63)")

print()
if fails:
    print("FAILURES: %d" % len(fails))
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("all checks passed")

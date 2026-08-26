#!/usr/bin/env python3
"""Does the MAIN ROM's own switch->LED adjacency table agree with the SX-WSA1R
CP1/CP2 schematic?  READ-ONLY; touches nothing but the ROM images.

QUESTION IT ANSWERS
  The panel matrix decoded from the service manual (see wsa1_sch_TRACE.md) claims
  a POPULATION: 6 columns x 8 rows on CP1 minus one missing cell (SW24 at SEG2/SW7),
  plus 4 + 2 + 5 switches on CP2 columns SEG7/SEG8/SEG9.  That is 47 + 11 = 58.
  prom_a's variant-2 switch->LED word table at 0xF95088 is 9 segments x 8 bits of
  u16, and a switch that does not exist gets 0x0000.  If the schematic reading is
  right, the table's zero pattern must be exactly the schematic's empty cells --
  a claim that can fail, loudly, on any off-by-one in either axis.

  It also answers "which way round are the packet bits?".  A reversed bit order
  (bit b = SW(7-b)) would put SEG8's two switches at bits 6,7 and SEG2's hole at
  bit 0.  The four service keys 2/3/4/5 CANNOT settle this -- they sit on rows
  SW2..SW5, a set that is symmetric under reversal.  The zero pattern can.

RUN
  python3 notes/wsa1-probes/wsa1_sch_vs_rom_matrix.py
"""
ROMS = "/home/fsanches/compartilhado/wsa1-roms-disasm/original_ROMs/"
pa = open(ROMS + "wsa1_prom_a.ic12", "rb").read()
A = lambda a, n=1: pa[a - 0xF80000:a - 0xF80000 + n]
u16 = lambda b: int.from_bytes(b, "little")

fails = []
def ck(cond, what):
    print("  %-4s %s" % ("ok" if cond else "FAIL", what))
    if not cond:
        fails.append(what)

# The 9 rows of the variant-2 table are the 9 WIRED segments in ascending order.
# 6 and 10 are the dead stubs on IC1 (pins 40 and 33) -- schematic II-29.
SEGS = [0, 1, 2, 3, 4, 5, 7, 8, 9]
tab = {SEGS[r]: [u16(A(0xF95088 + r * 16 + b * 2, 2)) for b in range(8)] for r in range(9)}

# What the schematic draws, as (segment -> set of populated switch rows).
SCHEMATIC = {
    0: set(range(8)),               # SW1..SW8   PLAY/EDIT MODE, BANK, RE-MAP
    1: set(range(8)),               # SW9..SW16  number keys 0..7
    2: set(range(7)),               # SW17..SW23 8,9,+/-,ENTER,PAGEv,PAGE^,COMPARE  (SW24 NOT FITTED)
    3: set(range(8)),               # SW25..SW32
    4: set(range(8)),               # SW33..SW40
    5: set(range(8)),               # SW41..SW48
    7: set(range(4)),               # SW57..SW60 MENU PART/SYSTEM/MIDI/DISK
    8: set(range(2)),               # SW65 "1~6", SW66 RESET
    9: set(range(5)),               # SW73..SW77
}

print("variant-2 switch->LED table, prom_a 0xF95088, rows relabelled by IC1 SEG number")
for s in SEGS:
    print("  SEG%-2d %s" % (s, " ".join("%04X" % w for w in tab[s])))
print()

for s in SEGS:
    live = {b for b, w in enumerate(tab[s]) if w != 0x0000}
    ck(live == SCHEMATIC[s], "SEG%-2d populated bits %s == schematic %s"
       % (s, sorted(live), sorted(SCHEMATIC[s])))

total = sum(len({b for b, w in enumerate(tab[s]) if w}) for s in SEGS)
ck(total == 58, "table populates %d positions; parts list III-5 has 47 (S1~23,25~48) + 11 (S57~60,65,66,73~77) = 58" % total)

# Bit order: these three are the discriminators against a reversed row order.
ck(tab[2][7] == 0 and tab[2][0] != 0, "SEG2's single hole is at bit 7, not bit 0  -> bit b = IC1 SWb")
ck(tab[8][0] and tab[8][1] and not any(tab[8][2:]), "SEG8 occupies bits 0,1 (not 6,7)")
ck(tab[9][4] and not any(tab[9][5:]), "SEG9 occupies bits 0..4 (not 3..7)")

# Segment order: SEG6/SEG10 are unwired, so no row may look like an unwired column.
ck(all(any(tab[s]) for s in SEGS), "every one of the 9 rows is populated -- consistent with 6 and 10 being the dropped pair")

print()
print("FUNCTIONAL GROUPING (the table's word is a lamp (register<<8)|mask)")
groups = {}
for s in SEGS:
    for b, w in enumerate(tab[s]):
        if w:
            groups.setdefault(w, []).append((s, b))
for w in sorted(groups):
    print("  %04X  reg%d mask %02X   %s" % (w, w >> 8, w & 0xFF,
          " ".join("%d/%d" % p for p in groups[w])))

# The two catch-all words split the panel exactly where the schematic's own printed
# legends change: numeric entry vs LCD navigation.
NUMBER = {(1, b) for b in range(8)} | {(2, b) for b in range(4)} | {(3, b) for b in (5, 6, 7)}
LCDKEY = {(2, b) for b in (4, 5, 6)} | {(3, b) for b in range(5)} \
       | {(4, b) for b in range(8)} | {(5, b) for b in range(8)} | {(9, b) for b in range(5)}
ck(set(groups.get(0x0608, [])) == NUMBER,
   "0x0608 covers exactly keys 0..7, 8, 9, +/-, ENTER and SEG3 bits 5..7")
ck(set(groups.get(0x0604, [])) == LCDKEY,
   "0x0604 covers exactly PAGEv/PAGE^/COMPARE, both 5-key LCD columns and the 16 under-LCD keys")

lamp_bits = set()
for w in groups:
    for i in range(8):
        if (w & 0xFF) & (1 << i):
            lamp_bits.add(((w >> 8), i))
print()
print("  distinct lamp bits referenced by the variant-2 table: %d" % len(lamp_bits))
print("  ", sorted(lamp_bits))
ck(len(lamp_bits) == 18, "18 distinct lamp bits -- the rack's parts list has 18 lamps "
   "(D116-119, D120-123, D130, D131, D138-141, D160-163)")

print()
print("FAILURES: %d" % len(fails))
for f in fails:
    print("  -", f)
raise SystemExit(1 if fails else 0)

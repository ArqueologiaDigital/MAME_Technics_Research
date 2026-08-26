#!/usr/bin/env python3
"""Which led%u output is which SX-WSA1R panel lamp?  READ-ONLY, ROM bytes only.

QUESTION IT ANSWERS
  src/mame/layout/wsa1r.lay binds 14 of the rack's 18 lamps to named outputs.
  Every one of those bindings rests on a single claim about prom_a: that the
  u16 in the variant-2 switch->LED table at 0xF95088 is

      (LED REGISTER INDEX << 8) | (LED BIT MASK)

  and that a button which HAS its own indicator is given its own indicator.
  This script asserts the first claim from the INSTRUCTIONS, not from the shape
  of the numbers, and then prints the resulting lamp map.

  It also re-asserts the two things the map is checked against: the all-lamps
  sweep table (which must be a superset) and the 18-lamp count.

WHAT IS NOT PROVEN HERE
  Which of {reg2 bit0, reg2 bit1, reg3 bit0, reg3 bit1} is which REALTIME
  CREATOR ring lamp.  The SET is fixed (RESET lights reg2 mask 0x03, "1~6"
  lights reg3 mask 0x03, and the schematic puts four ring lamps on CP2); the
  ORDER is not, and the layout leaves those four unbound on purpose.

RUN
  python3 notes/wsa1-probes/wsa1_lamp_identification.py
"""

ROMS = "/home/fsanches/compartilhado/technics_roms/roms/wsa1/"
pa = open(ROMS + "wsa1_os_v2.ic12", "rb").read()      # prom_a, base 0xF80000
pb = open(ROMS + "wsa1_os_v2.ic13", "rb").read()      # prom_b, base 0xF00000
A = lambda a, n=1: pa[a - 0xF80000:a - 0xF80000 + n]
B = lambda a, n=1: pb[a - 0xF00000:a - 0xF00000 + n]
u16 = lambda b: int.from_bytes(b, "little")

fails = []


def ck(cond, what):
    print("  %-4s %s" % ("ok" if cond else "FAIL", what))
    if not cond:
        fails.append(what)


print("1. THE ENCODING, from the code that consumes the table")
print("   sub_F94E1C is the PANEL SW&LED CHECK decoder; these are its bytes.")

# f94e88: 45 58 4f f9 00     ld XIY,0x00f94f58        (variant 1 table)
# f94e93: 45 88 50 f9 00     ld XIY,0x00f95088        (variant 2 table)
ck(A(0xF94E88, 5) == bytes.fromhex("45584ff900"), "0xF94E88 loads the variant-1 table 0xF94F58")
ck(A(0xF94E93, 5) == bytes.fromhex("4588 50f9 00".replace(" ", "")),
   "0xF94E93 loads the variant-2 table 0xF95088")

# f94e9c: eb ee 04           sll 0x04,XHL     -- index * 16, i.e. 8 x u16 per segment row
ck(A(0xF94E9C, 3) == bytes.fromhex("ebee04"), "0xF94E9C `sll 4,XHL`: 16 bytes = 8 u16 per row")

# f94eb5: 93 20              ld WA,(XHL)      -- W = high byte, A = low byte
ck(A(0xF94EB5, 2) == bytes.fromhex("9320"), "0xF94EB5 `ld WA,(XHL)` loads the word into WA")

# f94ebb: c9 d1              xor A,A          -- on release only the MASK is cleared, W kept
ck(A(0xF94EBB, 2) == bytes.fromhex("c9d1"),
   "0xF94EBB `xor A,A` clears only the LOW byte on release, so the low byte is the DATA")

# f94ebd: 1d 70 06 f4        call 0xf40670
ck(A(0xF94EBD, 4) == bytes.fromhex("1d7006f4"), "0xF94EBD calls the thunk 0xF40670")

# f40670: 1b 46 c8 f8        jp 0xf8c846      -- the UNGUARDED entry of Panel_SetLedRegister
ck(B(0xF40670, 4) == bytes.fromhex("1b46c8f8"),
   "0xF40670 is `jp 0xF8C846`, Panel_SetLedRegister's unguarded entry")

# f8c85c: 44 b7 c8 f8 00     ld XIX,0x00f8c8b7   (variant 2 register->wire table)
# f8c861: c3 03 f0 e1 20     ld W,(XIX+W)        -- W INDEXES the table: W is the REGISTER
ck(A(0xF8C85C, 5) == bytes.fromhex("44b7c8f800"), "0xF8C85C loads the variant-2 register->wire table")
ck(A(0xF8C861, 5) == bytes.fromhex("c303f0e120"),
   "0xF8C861 `ld W,(XIX+W)`: W indexes the register->wire table, so W IS THE REGISTER")

# f8c879: ld (XIZ+IX),W ; f8c888: ld (XIZ+IX),A   -- [wire][data] into the queue at 0x2BA0
ck(A(0xF8C879, 5) == bytes.fromhex("f307f8f040"), "0xF8C879 queues W as the WIRE ADDRESS byte")
ck(A(0xF8C888, 5) == bytes.fromhex("f307f8f041"), "0xF8C888 queues A as the DATA byte")

wire_v2 = A(0xF8C8B7, 8)
ck(wire_v2 == bytes([0xC1, 0xC2, 0xC9, 0xCA, 0xCB, 0xCC, 0xC3, 0x00]),
   "register->wire (variant 2) = C1 C2 C9 CA CB CC C3 00")

print()
print("   => the table word is (register << 8) | bit mask, and the driver's output")
print("      index is register*8 + bit.")

print()
print("2. THE LAMP MAP that follows, for the 14 one-to-one positions")

SEGS = [0, 1, 2, 3, 4, 5, 7, 8, 9]
tab = {SEGS[r]: [u16(A(0xF95088 + r * 16 + b * 2, 2)) for b in range(8)] for r in range(9)}

# switch legends, from the CP1/CP2 P.C. Diagram's own printed text (PDF p.32)
LEGEND = {
    (0, 0): "PLAY MODE SOUND", (0, 1): "PLAY MODE COMBI",
    (0, 2): "EDIT MODE SOUND", (0, 3): "EDIT MODE COMBI",
    (0, 4): "BANK USER 1", (0, 5): "BANK USER 2",
    (0, 6): "BANK ROM/EXT", (0, 7): "BANK RE-MAP",
    (7, 0): "MENU PART", (7, 1): "MENU SYSTEM",
    (7, 2): "MENU MIDI", (7, 3): "MENU DISK",
    (8, 0): "REALTIME CREATOR 1~6", (8, 1): "REALTIME CREATOR RESET",
}

# what the layout binds, and what this script is here to justify
EXPECT = {
    (0, 0): ("led8",  "D116 PLAY MODE SOUND"),
    (0, 1): ("led9",  "D117 PLAY MODE COMBI"),
    (0, 2): ("led10", "D118 EDIT MODE SOUND"),
    (0, 3): ("led11", "D119 EDIT MODE COMBI"),
    (0, 4): ("led0",  "D120 BANK USER 1"),
    (0, 5): ("led1",  "D121 BANK USER 2"),
    (0, 6): ("led2",  "D122 BANK ROM/EXT"),
    (0, 7): ("led3",  "D123 BANK RE-MAP"),
    (7, 0): ("led32", "D160 MENU PART"),
    (7, 1): ("led33", "D161 MENU SYSTEM"),
    (7, 2): ("led40", "D162 MENU MIDI"),
    (7, 3): ("led41", "D163 MENU DISK"),
}

for (seg, bit), (want, lamp) in sorted(EXPECT.items()):
    w = tab[seg][bit]
    reg, mask = w >> 8, w & 0xFF
    single = mask and not (mask & (mask - 1))
    idx = reg * 8 + (mask.bit_length() - 1)
    ck(single and ("led%d" % idx) == want,
       "SEG%d/SW%d %-22s -> reg%d bit%d = led%-3d %s"
       % (seg, bit, LEGEND[(seg, bit)], reg, mask.bit_length() - 1, idx, lamp))

# The two family indicators: each is the ONLY lamp its family has, so the
# catch-all word names it.
ck(tab[2][6] == 0x0604, "COMPARE (SEG2/SW6, printed legend) carries reg6 bit2 -> led50")
ck(all(tab[1][b] == 0x0608 for b in range(8)) and tab[2][2] == 0x0608,
   "every number key carries reg6 bit3 -> led51, the MIDI/NUMBER PAD indicator")
ck(tab[3][5] == tab[3][6] == tab[3][7] == 0x0608,
   "SEG3 bits 5..7 (-1, +1, EXIT) are in the SAME numeric family as the number pad")

# The ring: a SET, not an order.
ck(tab[8][1] == 0x0203 and tab[8][0] == 0x0303,
   "RESET lights reg2 mask 0x03 and 1~6 lights reg3 mask 0x03 = four ring lamps, 2 + 2")
ring = set()
for w in (tab[8][0], tab[8][1]):
    for i in range(8):
        if (w & 0xFF) & (1 << i):
            ring.add((w >> 8) * 8 + i)
ck(ring == {16, 17, 24, 25},
   "the ring SET the ROM names is led%s -- the ORDER is NOT decoded, so those four "
   "stay unbound" % sorted(ring))

print()
print("3. CROSS-CHECKS")
lamp_bits = set()
for row in tab.values():
    for w in row:
        if w:
            for i in range(8):
                if (w & 0xFF) & (1 << i):
                    lamp_bits.add((w >> 8, i))
ck(len(lamp_bits) == 18, "the variant-2 table references exactly 18 distinct lamp bits")

# The all-lamps sweep at 0xF95C68 is [data][reg] pairs terminated by 0xFFFF.
sweep, off = {}, 0
while True:
    data, reg = A(0xF95C68 + off)[0], A(0xF95C68 + off + 1)[0]
    if data == 0xFF and reg == 0xFF:
        break
    sweep[reg] = data
    off += 2
ck(sweep == {0: 0xFF, 1: 0xFF, 2: 0xFF, 3: 0xFF, 4: 0xFF, 5: 0x03, 6: 0x0F, 7: 0x02},
   "the all-lamps sweep table at 0xF95C68 is reg0..4=FF reg5=03 reg6=0F reg7=02 (47 bits)")
ck(all((sweep.get(r, 0) >> b) & 1 for r, b in lamp_bits),
   "every one of the 18 rack lamp bits is inside that 47-bit sweep")
ck(sum(bin(v).count("1") for v in sweep.values()) == 47,
   "the sweep is 47 bits -- the UNION over both variants, not the rack's 18")

print()
print("FAILURES: %d" % len(fails))
for f in fails:
    print("  -", f)
raise SystemExit(1 if fails else 0)

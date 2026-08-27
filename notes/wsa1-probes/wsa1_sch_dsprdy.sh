#!/bin/sh
# wsa1_sch_dsprdy.sh -- re-derive CPU 2's PORT 9 nets from the service manual,
# and census every read of SFR 0x19 in the four ROMs.
#
# QUESTION IT ANSWERS: "what is CPU 2's P9 bit 3, and what level does it idle
# at?"  The driver used to leave port 9 unbound on the grounds that no schematic
# net had been read for the pin.  One had not been LOOKED for; it is there.
#
# Part 1 renders the two crops that show it.  Part 2 lists the firmware sites
# that read the port, which is what makes the level matter.
#
# Source (never leaves the machine):
#   ~/compartilhado/KN7000/service_manual/SX-WSA1R Service Manual.pdf
# The PNGs are regenerable and are NOT committed.
#
#   sh wsa1_sch_dsprdy.sh [outdir]
set -e
OUT=${1:-/home/fsanches/compartilhado/KN7000/tmp-dir/wsa1-sch-dsprdy}
SM="/home/fsanches/compartilhado/KN7000/service_manual/SX-WSA1R Service Manual.pdf"
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$OUT"

# ---- part 1: the schematic ------------------------------------------------
# PDF page 20 = sheet II-9/10, "MAIN (A)/MB2 P.C. Diagram", right half.  IC2 is
# the SUB microcomputer; page 19 (the left half) carries IC1, the MAIN one, and
# is where anyone who looks at "the TMP95C061" first lands.
pdftoppm -f 20 -l 20 -r 300 -png -gray "$SM" "$OUT/hi" 2>/dev/null

# whole chip, to confirm the designator and the (SUB) subtitle
python3 "$HERE/wsa1_sch_crop.py" "$OUT/hi-20.png" "$OUT/ic2.png"      500 1750 1800 2800 1
# pins 16-25, where the port 9 nets are
python3 "$HERE/wsa1_sch_crop.py" "$OUT/hi-20.png" "$OUT/ic2_p9.png"   500 2230  950 2440 5

cat <<'TXT'

READ OFF ic2_p9.png (IC2 TMP95C061AF, MICROCOMPUTER (SUB), left pin column):

    pin 18  VREF   <- +5D through R38 220
    pin 19  VCC    <- +5D
    pin 20  AN0    <- +5D            same node as pin 19, junction dot on both
    pin 21  AN1    <- JOYX through R180 1K, 0.1 uF to ground
    pin 22  AN2    <- JOYY through R181 1K, 0.1 uF to ground
    pin 23  P93    <- net DSPRDY, R79 4.7K UP to the VREF node, 0.22 uF to gnd
    pin 24  AM16   pin 25 CLK

and on ic2.png, pins 2-9 are P70-P77 carrying DSPD0-DSPD7 -- the byte path the
same routine writes with `ld (0x0013),(XIZ+0x08)`.

CONCLUSION: P9 bit 3 and P9 bit 0 both idle HIGH on the board.  An unbound MAME
port read returns 0, which is the wrong level, not a neutral one.

TXT

# ---- part 2: who reads SFR 0x19 -------------------------------------------
python3 - <<'PY'
roms = {
    'prom_a (ic12)': ('wsa1_os_v2.ic12', 0xF80000),
    'prom_b (ic13)': ('wsa1_os_v2.ic13', 0xF00000),
    'prom_c (ic28)': ('wsa1_os_v2.ic28', 0xF80000),
    'prom_d (ic21)': ('wsa1_os_v2.ic21', 0x000000),
}
base_dir = '/home/fsanches/compartilhado/technics_roms/roms/wsa1/'
print("reads of SFR 0x19 (PORT 9).  The scan is opcode-anchored, so it is an upper")
print("bound; all 19 hits were then confirmed to be instruction boundaries with")
print("  sh wsa1_dis.sh c 0xF9A190 400 0   ->  0xF9A19F 1DD 219 257 293 2D1")
print("  sh wsa1_dis.sh c 0xF9A320 416 0   ->  0xF9A347 382 3BB 3F6 42F 46A")
print("  sh wsa1_dis.sh c 0xF9A4B0 400 0   ->  0xF9A4DD 518 551 58C 5C5 600")
print("  sh wsa1_dis.sh c 0xFB0500  60 8   ->  0xFB050B")
print("each of which disassembles linearly from a point outside the hit.\n")
for name, (f, base) in roms.items():
    d = open(base_dir + f, 'rb').read()
    hits = []
    for i in range(len(d) - 2):
        if d[i] == 0xc0 and d[i+1] == 0x19 and 0x20 <= d[i+2] <= 0x27:
            hits.append(('ld r,(0x19)  ', base + i))
        if d[i] == 0xf0 and d[i+1] == 0x19 and 0xc8 <= d[i+2] <= 0xcf:
            hits.append(('bit n,(0x19) ', base + i))
    print("%-14s %d" % (name, len(hits)))
    for k, a in hits:
        print("     %s 0x%06X" % (k, a))
PY

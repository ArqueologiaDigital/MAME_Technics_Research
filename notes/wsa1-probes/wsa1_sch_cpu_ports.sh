#!/bin/sh
# wsa1_sch_cpu_ports.sh -- re-render the service-manual crops behind every
# port-pin, chip-select and crystal claim wsa1.cpp makes.
#
# QUESTION IT ANSWERS: "which net is on which pin of IC1 and IC2, which device
# does each chip-select output enable, and do those agree with what the
# firmware alone said?"  The driver reads these crops by eye; this script is
# the recipe that puts the same pixels in front of the next reader.
#
# Source (never leaves the machine, image-only -- pdftotext returns nothing):
#   ~/compartilhado/KN7000/service_manual/SX-WSA1R Service Manual.pdf
#   ORDER NO. EMiD951604, (c) 1995 Matsushita Electric Industrial.
# Needs poppler's pdftoppm and python3-pil.  The PNGs are regenerable and are
# NOT committed.
#
#   sh wsa1_sch_cpu_ports.sh [outdir]
#
# PAGES (1-based, as pdftoppm counts):
#   19  MAIN (A)/MB2, sheet II-7/II-8    IC1 (MAIN), IC12, IC13, IC14
#   20  MAIN (A)/MB2, sheet II-9/II-10   IC2 (SUB), IC7, IC8 uPD72070, IC16
#                                        (X1 28 MHz), IC17, IC18
#   21  MAIN (B),     sheet II-11/II-12  IC3 L7A1429, IC27, IC28, IC21, IC22
#   22  MAIN (B),     sheet II-13/II-14  IC4 tone generator, X4 33.8688 MHz
#   23  MAIN (C)/HP,  sheet II-15/II-16  IC5/IC6/IC30 DSPs, the six wave ROMs
set -e
OUT=${1:-/home/fsanches/compartilhado/KN7000/tmp-dir/wsa1-sch-cpu-ports}
SM="/home/fsanches/compartilhado/KN7000/service_manual/SX-WSA1R Service Manual.pdf"
HERE=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$OUT"
[ -f "$SM" ] || { echo "not found: $SM" >&2; exit 2; }

for p in 19 20 21 22 23; do
    [ -f "$OUT/p$p-$p.png" ] || pdftoppm -f $p -l $p -r 400 -png "$SM" "$OUT/p$p" 2>/dev/null
done

# The fractions below are of each page's own width/height at -r 400 (6617x4678).
crop() { # page name x0 y0 x1 y1 scale
    python3 - "$OUT" "$@" <<'PY'
import sys, glob, os
from PIL import Image
out, page, name = sys.argv[1], int(sys.argv[2]), sys.argv[3]
x0,y0,x1,y1,sc = (float(v) for v in sys.argv[4:9])
src = glob.glob(os.path.join(out, 'p%d-*.png' % page))[0]
im = Image.open(src); w, h = im.size
c = im.crop((int(w*x0), int(h*y0), int(w*x1), int(h*y1)))
if sc != 1.0:
    c = c.resize((int(c.width*sc), int(c.height*sc)), Image.LANCZOS)
c.save(os.path.join(out, name)); print(name, c.size)
PY
}

crop 19 ic1_left_ports.png   0.62 0.18 0.90 0.60 1.0
crop 19 ic1_bottom_ports.png 0.715 0.42 0.815 0.58 2.6
crop 19 ic12_ic13.png        0.40 0.55 0.78 0.85 1.0
crop 20 ic2_dsp_control.png  0.175 0.44 0.225 0.53 5.0
crop 20 ic2_data_and_midi.png 0.09 0.545 0.20 0.63 2.4
crop 20 ic2_bottom_ports.png 0.185 0.68 0.30 0.86 2.4
crop 20 ic2_p27_dsp2cs.png   0.32 0.53 0.47 0.64 2.0
crop 20 ic8_fdc.png          0.38 0.44 0.58 0.72 1.9
crop 20 ic17_ic18.png        0.03 0.40 0.20 0.66 1.6
crop 21 ic27_ic21.png        0.29 0.16 0.75 0.90 1.0
crop 22 ic4_tone_generator.png 0.30 0.15 0.70 0.85 1.0
crop 22 ic4_host_port.png    0.495 0.60 0.60 0.87 2.6
crop 23 dsp_and_wave_roms.png 0.00 0.00 1.00 1.00 0.30
crop 23 ic30_dsp2.png        0.47 0.55 0.60 0.83 2.4
crop 23 ic5_dsp1.png         0.80 0.36 0.90 0.46 3.2
crop 23 ic6_dsp0.png         0.81 0.66 0.90 0.83 3.2
crop 20 link_latches.png     0.13 0.22 0.38 0.42 2.0
crop 20 fdmon_driver.png     0.53 0.68 0.63 0.80 3.4
crop 20 fdd_connector.png    0.60 0.50 0.72 0.72 2.6
crop 20 ic1_sc1_serial.png   0.58 0.33 0.73 0.44 2.6

cat <<'TXT'

WHAT TO READ OFF EACH CROP.  Every line below is quoted in
src/mame/matsushita/wsa1.cpp next to the code it justifies.

ic1_left_ports / ic1_bottom_ports -- IC1 TMP95C061AF "MICROCOMPUTER (MAIN)"
    pin  2 P70 MSTAT0 (R149 1K)   pin 33 PA1  FS1  (R151 0R)
    pin  3 P71 MSTAT1 (R150 1K)   pin 34 PA2  FS2  (R152 0R)
    pin  4 P72 SSTAT0             pin 35 PA3  FDMON(R153 0R)
    pin  5 P73 SSTAT1             pin 36 INT4 HDINT
    pin  6 P74 LCDOFF             pin 37 INT5 FDINT
    pin  7 P75 MUTE               pin 38 PB2  FDRST
    pins 8,9 P76,P77 no net       pin 39 PB3  FDTC
    pin 11 TXD0 MIDI1OUT          pin 40 INT6 tied to +5D
    pin 12 RXD0 MIDI1IN           pin 41 INT7 FDDRQ
    pin 13 P82  MIDI1SNS          pin 42 PB6  HDIORDY
    pins 14-16 TXD1/RXD1/SCLK1    pin 43 INT0 SIFINT
    (the control panel link)      pin 32 PA0  grounded
  ⚠ THE LEFT COLUMN IS EASY TO READ ONE ROW OUT.  MSTAT0 is on pin 2, not
    pin 1: pin 1 is P65 and its line goes to IC39, a TC7S14F.  Three
    independent firmware facts confirm the alignment used above -- P7CR = 0x33
    makes P70/P71/P74/P75 outputs, the power-fail NMI sets P7 bits 4 and 5
    (LCDOFF and MUTE), and the link's busy input is P7 bit 3 (SSTAT1).

ic12_ic13 -- IC12 QSIGCWSA1AX (/OE = PROMACS) and IC13 QSIGCWSA1BX (PROMBCS),
    "4M BIT PROGRAMMED EP ROM", drawn A1..A18 -> A0..A17 with D0..D15: x16.

ic2_dsp_control / ic2_data_and_midi / ic2_bottom_ports / ic2_p27_dsp2cs --
  IC2 TMP95C061AF "MICROCOMPUTER (SUB)"
    pins 2-9 P70-P77 DSPD0-DSPD7   pin 32 PA0  SSTAT0 (R162 1K)
    pin 11 TXD0 MIDI2OUT           pin 33 PA1  SSTAT1 (R163 1K)
    pin 12 RXD0 MIDI2IN            pin 34 PA2  MSTAT0
    pin 13 P82  MIDI2SNS           pin 35 PA3  MSTAT1
    pin 20 AN0  +5D                pin 36 INT4 KBEVNT
    pin 21 AN1  JOYX (R180 1K)     pin 37 PB1  DSP2RST2
    pin 22 AN2  JOYY (R181 1K)     pin 38 PB2  DSPRST
    pin 23 P93  DSPRDY (R79 4.7K)  pin 39 PB3  DSP0RST2
    pin 64 P27  DSP2CS (R189 1K)   pin 40 PB4  DSP1RST2
    pin 91 P53  DSPCD  (R166 1K)   pin 41 PB5  DSPWR
    pin 92 P54  DSP0CS (R167 1K)   pin 42 PB6  DSPRD
    pin 93 P55  DSP1CS (R179 1K)   pin 43 INT0 IFINT
  ⚠ P54/P55: DSP0CS and DSP1CS cross other lines between the label row and the
    pins on this scan.  The pair lands on P54/P55; which is which is read from
    the label order and agrees with the firmware's destination index.

ic8_fdc -- IC8 D72070GF3BE "FLOPPY DISK CONTROLLER", crystal X5 = 24 MHz on
    XA1/XA2/XB.  DS0, INDEX, DIR, STEP, SIDE, WDATA, WGATE, TRK0, WPRT, RDATA
    and READY carry nets; ME0-ME3, the motor enables, do not.

ic17_ic18 -- IC17 D74HC139GS and IC18 D74HC138GS on CPU 1's bus.  IC18 takes
    A = A16, B = A17, C = A18, G1 = A19, /G2A = /G2B = CS0:
      Y1 LCDCS 0x790000   Y2 FDDAK 0x7A0000   Y3 FDCS 0x7B0000
      Y4 MIF   0x7C0000   Y6 HDCS  0x7E0000   Y0/Y5/Y7 no net

ic27_ic21 -- IC27 D74HC139GS.  1E = SCS0, 1DA = SA14, 1DB = SA15:
      1Y0 SMIF 0x100000  1Y1 WFICS 0x104000  1Y2 KSCS 0x108000
      1Y3 SGCS 0x10C000
    2E = SCS2, 2DA = SA19, 2DB = SA20:
      2Y1 SFLSHCS 0xE80000  2Y2 PROMDCS 0xF00000  2Y3 PROMCCS 0xF80000
      2Y0 (0xE00000) no net
    and IC21 QSIGCWSA1DX "4M BIT PROGRAMMED EP ROM" on PROMDCS, SA1..SA18,
    SD0..SD15 -- the fourth EPROM's designator, printed twice on the sheet.

ic4_tone_generator / ic4_host_port -- IC4 TC183C230002 "TONE GENELATOR LSI"
    [sic].  X4 = 33.869 MHz (33.8688 = 768 x 44100).  LRCK, BCK, SDO0-SDO7.
    Two 21-bit wave buses ADX0-20 / ADY0-20 with NOEX0-3 -> XCS0-3 and
    NOEY0-3 -> YCS0-3.  MD0-MD15 <-> SD0-SD15, NRD <- SRD, NWR <- SWR,
    NAD <- SA1, and TWO chip selects: NSGCE <- SGCS, NKSCE <- KSCS.  ROWFI and
    DWFI0-DWFI12 on pins 25-40 are the input from IC3.  KS0-KS3, KF0-KF3,
    KB0-KB4, LEL, LER on the left edge are the key-scan matrix, and KBEVNT
    leaves this die for CPU 2's INT4.

link_latches -- the inter-processor mailbox is two octal latches:
    IC24 D74HC374GS  D <- SD0..SD7 (CPU 2)  Q -> D0..D7 (CPU 1)
                     CK <- SIFINT           /OE <- MIF OR RD
    IC25 D74HC374GS  D <- D0..D7 (CPU 1)    Q -> SD0..SD7 (CPU 2)
                     CK <- IFINT            /OE <- SMIF OR SRD
    IC26 D74HC32GS   SIFINT = SMIF OR SWR,  IFINT = MIF OR WR
  So each direction is ONE BYTE deep with no full/empty flag, and each
  interrupt is the far side's own write strobe.

fdmon_driver / fdd_connector -- FDMON drives R57/R58 into Q10 (2SB709AR),
    whose collector drives Q9 (2SD601AQ) through R59/R60; Q9's collector, with
    R61 10K to +5D, is CN6 pin 3.  CN6 is the FDD: 1 INDEX, 2 DS0, 3 MOT,
    4 DIR, 5 STP, 6 WDT, 7 WE, 8 TRKO, 9 WPRT, 10 RDT, 11 SIDE, 12 DCH,
    13 +5D, 14/15 E.  Two inverting stages, so FDMON LOW = motor ON.

ic1_sc1_serial -- IC1 pins 14/15/16 are TXD1/RXD1/SCLK1 through R29 220,
    R30 1K and R31 220, the control panel link.  No pull-up is drawn on SCLK1
    at this resolution.

dsp_and_wave_roms / ic30_dsp2 / ic5_dsp1 / ic6_dsp0 -- MAIN (C)/HP.
    Three D6383GF-3BA on one shared 8-bit host bus: D0-D7 <- DSPD0-DSPD7,
    /WRITE <- DSPWR, /READ <- DSPRD, C/D <- DSPCD, RDY -> DSPRDY, /RST <-
    DSPRST, and per chip /CS and /RST2:
      IC6  DSP0CS DSP0RST2      IC5  DSP1CS DSP1RST2      IC30 DSP2CS DSP2RST2
    Six 16 Mbit wave mask ROMs, each A0..A19 + BYTE with TGD0..TGD15 (1M x 16):
    IC43/IC44/IC45 on the Y bus, IC47/IC48/IC49 on the X bus.
TXT

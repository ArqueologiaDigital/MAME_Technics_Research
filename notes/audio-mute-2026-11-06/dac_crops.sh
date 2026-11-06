#!/bin/sh
# dac_crops.sh -- question: which converter is IC311, how is it wired to the outputs, and where does
# MAIN OUT tap the sound?  Renders the service manual crops the README's reading comes from, plus
# Figure 40 of the PCM1738 data sheet to compare the I/V wiring with.  Needs pdftoppm (poppler).
#
#   sh dac_crops.sh [SERVICE_MANUAL_PDF] [PCM1738_PDF] [OUTDIR]
#
# Defaults: ~/compartilhado/KN7000/service_manual/technics_sx-kn7000_keyboard.pdf (ORDER NO.
# EMID0207013C0); the PCM1738 data sheet SBAS174C (https://www.ti.com/lit/ds/symlink/pcm1738.pdf,
# 664,916 bytes when fetched on 2026-11-06) at $TMPDIR/pcm1738.pdf; OUTDIR $TMPDIR/dac-crops.
# Coordinates are PDF points of the manual's 1191 x 842 pages.
set -eu
SM=${1:-$HOME/compartilhado/KN7000/service_manual/technics_sx-kn7000_keyboard.pdf}
DS=${2:-${TMPDIR:-$HOME/compartilhado/tmp}/pcm1738.pdf}
OUT=${3:-${TMPDIR:-$HOME/compartilhado/tmp}/dac-crops}
mkdir -p "$OUT"
crop() {   # name page dpi x y w h
	pdftoppm -r "$3" -f "$2" -l "$2" -x $(($4 * $3 / 72)) -y $(($5 * $3 / 72)) \
		-W $(($6 * $3 / 72)) -H $(($7 * $3 / 72)) -png -singlefile "$SM" "$OUT/$1"
	echo "$OUT/$1.png  (page $2)"
}
# 1. MAIN 3/5 (diagram 6): IC311 C0FBBK000025, all 28 pin names = the PCM1738's (RST 1 .. VCC3 28)
crop 1_ic311_pinout     110 400  60 200 300 160
# 2. MAIN 3/5: IOUTL- (26) -> IC314 pin 2, IOUTL+ (25) -> IC314 pin 5; IOUTR- (16) -> IC313 pin 2,
#    IOUTR+ (17) -> IC313 pin 5
crop 2_ic311_to_iv      110 300 240 150 180 250
# 3. MAIN 3/5: IC314's two I/V outputs into IC315 (- from IOUTL-, + from IOUTL+), then R339 into
#    IC316's inverting input (R347 47K feedback): the inverting mixer making MIXOUTL
crop 3_iv_balanced_mix  110 300 330 150 380 130
# 4. FAJ 2/2 (diagram 12): MAIN OUT JK508 / JK509 fed by IC511 from bus lines d / e
crop 4_main_out         122 200   0 150 420 240
# 5. FAJ 1/2 (diagram 11): lines d / e leave SUML / SUMR (after C505 / C506) ahead of the series
#    SPSW FETs Q502 / Q503 (each between a 39K / 100K divider and IC506)
crop 5_faj_sum_spsw     120 150 100 380 1091 360
if [ -f "$DS" ]; then
	pdftoppm -r 110 -f 31 -l 31 -png -singlefile "$DS" "$OUT/6_pcm1738_fig40"
	echo "$OUT/6_pcm1738_fig40.png  (data sheet page 31)"
else
	echo "no data sheet at $DS: fetch https://www.ti.com/lit/ds/symlink/pcm1738.pdf"
fi

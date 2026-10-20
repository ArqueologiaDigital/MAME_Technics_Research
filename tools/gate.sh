#!/usr/bin/env bash
# gate.sh -- the one check that has to stay green.
#
# WHY THIS EXISTS: over one week in August 2026, six separately-published claims turned
# out to be false the moment anything was re-run -- a source-coverage figure inflated 5x,
# two audio-oracle baselines that no longer reproduced (and disagreed with each other),
# "zero .byte code", "all LABEL_* replaced", three synthetic files shipping as chip dumps,
# and a DSP evidence script that had rotted. None were found by looking; they surfaced on
# first re-run. This script is the standing re-run.
#
#   ./tools/gate.sh              # everything
#   ./tools/gate.sh --static     # no emulator: validate + verifyroms only (seconds)
#   ./tools/gate.sh --model kn7000
#
# Exit 0 only if every check passed. Any failure exits 1 with a summary.
#
# ⚠ Deliberately uses -window, not -video none: the project rule is that a human can
#   always see what a rig is doing. It does mean this needs a display.
set -uo pipefail

EMU_DIR="${EMU_DIR:-/home/fsanches/compartilhado/kn7000-emulator}"
RIGS="$(cd "$(dirname "$0")" && pwd)/rigs"
# Resolve every repo path HERE, before the cd to $EMU_DIR further down -- a relative
# dirname "$0" after that cd resolves against the emulator directory and silently breaks.
DEMO_RIG="${DEMO_RIG:-$RIGS/../../notes/kn5000-demo-probes/demo_max.lua}"  # overridable for fault-injection
ONLY=""
STATIC=0
while [ $# -gt 0 ]; do
	case "$1" in
		--static) STATIC=1 ;;
		--model) ONLY="$2"; shift ;;
		*) echo "usage: $0 [--static] [--model NAME]"; exit 2 ;;
	esac
	shift
done

cd "$EMU_DIR" || { echo "gate: no emulator at $EMU_DIR"; exit 1; }
[ -x ./kn7000 ] || { echo "gate: no binary at $EMU_DIR/kn7000"; exit 1; }

# Per-model expectations, measured 2026-08-14 on binary 74035784 B; kn6000 re-measured
# 2026-10-18 (see below).
#   model:min_distinct
# min_distinct is a FLOOR just under the observed value, so a real regression trips it
# while ordinary UI variation does not. Observed: kn7000 12, kn5000 20, kn6000 9,
# kn6500 8, kn2400 4, kn2600 4.
#   ⚠ kn2400/kn2600 sit at 4 because they render almost nothing -- a known defect, not a
#   healthy baseline. Raise their floor when the text path is fixed.
#   kn1500 has no screen device (SVG/HD44780) so the probe reports SKIP.
#   kn6000 draws 7 since its table ROM became the fonts-only placeholder (921bbdd; the earlier
#   borrowed KN7000 table also drew KN7000 bitmaps). Same value with the pre-resync build
#   (notes/overlay-upstream-sync/SYNC-2026-10-18.md); the screen at t=25 is a correct play
#   screen. Floor 6.
MODELS="kn7000:11 kn5000:18 kn6000:6 kn6500:7 kn2400:4 kn2600:4 kn1500:0"

# Re-baselined 2026-10-18 from 780de131e33a4a0c99d092b57a074247: the old value had already
# drifted before the upstream resync (the pre-resync build gives this one too), and nothing in the
# resync changed it. Evidence: notes/overlay-upstream-sync/SYNC-2026-10-18.md, "Gate attribution".
# Re-baselined 2026-10-19 from 4c3a522a63f4e86fe9f7d7c8d94f5dbe: the firmware now finds the real
# rhythm ROM IC18 (and IC19) instead of the synthetic rhythm resource. The new binary with the old
# memory picture there restored by Lua taps gives 4c3a522a again, bit for bit, so nothing else moved.
# Evidence: notes/pr-port-2026-10-19/oracle_attribution.sh and that folder's README.
# Re-baselined 2026-10-20 from bd02a9c15b580d6b4b4c0a42f78a1fcb: the effects DSP's own reads of MSGR0-7 now return the
# stored value (sharc.cpp iop65l_r, e04a567), as on Felipe's unit (passes 6 and 7), so effects 58-61 keep their ring-3
# pointer. The new binary with those reads forced back to 0 by a Lua tap gives bd02a9c1 again, bit for bit; only
# seconds 16-17, the held note, differ. Evidence: notes/dsp-probe-2026-10-20/oracle_attribution_msgr.sh and README.md.
# Re-baselined 2026-10-20 from 028bb1dbead8b06d04f565cb30dc9a32: the KN7000's timing as measured on Felipe's unit (DSP
# probe pass 8, 5dd2c40): TM4 drives the 1 kHz tick (1.0005 ms), the DSP handshake comes once per frame, FLAG3
# alternates. One build per step (3c2f89d6, f99f8521, 8a1fe2a4); wav_shift.py: the held note starts 0.19-0.27 ms
# earlier and, aligned, matches to 0.01% (TM4, handshake) and 0.21% (FLAG3: ring 3 now scrolls). Evidence:
# notes/dsp-probe-2026-10-20/README.md, "The unit's timing in the emulator".
# Re-baselined 2026-10-20 from 8a1fe2a44e064f94ff935242fd717cb4: the KN7000's voices play the dumped wave ROMs and the
# strap reports hardware subtype 1 (G13, 595d83a). The held C4 is 262.31 Hz (+4.5 cents, was 260.13, -9.9), 3.4 dB
# louder, starts 9.4 ms earlier and has a tail; no clipping; only seconds 0 and 16-21 differ. The merge with the SPORT
# DMA registers (58175d5) gives the same hash as G13 alone. Evidence: notes/g13-waves-2026-10-20/README.md.
ORACLE_MD5="dbe3683b25d0e26f823ddbb1fa78bb56"

# KN5000 demo-audio oracle. Added 2026-08-15 because the gate passed 16/16 on a
# detect_period change it structurally COULD NOT SEE: its kn7000 oracle is the wrong machine,
# and its kn5000 liveness check sits at the home screen with no notes playing.
# Baseline measured on the binary with the N>256 bound; deterministic across two runs.
# Re-baselined 2026-10-18 from 4c8671b68f446cd3f6c10c8784e7748f (rms 499.8). It had drifted to
# 6e7c3531... before the resync, and the rebase onto upstream ec20df4a93b moved it to this value
# (rms 500.1): upstream core changes, not overlay ones (same SYNC notes section).
KN5000_DEMO_MD5="8bbe54f787f43c4fd82ea25b9486f38d"

PASS=0; FAIL=0; SKIP=0
FAILED=""
ok()   { echo "  PASS  $1"; PASS=$((PASS+1)); }
bad()  { echo "  FAIL  $1"; FAIL=$((FAIL+1)); FAILED="$FAILED
    $1"; }
skip() { echo "  SKIP  $1"; SKIP=$((SKIP+1)); }

echo "== static =="
if timeout 120 ./kn7000 -validate >/dev/null 2>&1; then ok "-validate"; else bad "-validate"; fi
if timeout 180 ./kn7000 -listxml >/dev/null 2>&1; then ok "-listxml"; else bad "-listxml"; fi

for entry in $MODELS; do
	m="${entry%%:*}"
	[ -n "$ONLY" ] && [ "$m" != "$ONLY" ] && continue
	# "best available" is a pass: BAD_DUMP entries are declared, not accidents.
	out=$(timeout 200 ./kn7000 "$m" -rompath ./roms -verifyroms 2>&1)
	if echo "$out" | grep -qE 'romset .* is (good|best available)'; then
		ok "verifyroms $m"
	else
		bad "verifyroms $m -- $(echo "$out" | tail -1)"
	fi
done

[ "$STATIC" -eq 1 ] && { echo; echo "static only: $PASS passed, $FAIL failed"; [ "$FAIL" -eq 0 ] || exit 1; exit 0; }

# The KN7000's IC23 backup SRAM is an nvram device since 2026-10-20 (nvram/kn7000/ic23): left in
# place, whatever the previous run (or Felipe) saved there would carry into the next run. The
# emulator runs below use a throwaway copy of nvram/ without it, so IC23 starts blank as the RAM
# placeholder did when the baselines were measured, and the published folder is not written.
NV=$(mktemp -d)
cp -r nvram/. "$NV/" 2>/dev/null
rm -f -- "${NV:?}/kn7000/ic23"

echo
echo "== liveness (does it boot and draw?) =="
for entry in $MODELS; do
	m="${entry%%:*}"; min="${entry##*:}"
	[ -n "$ONLY" ] && [ "$m" != "$ONLY" ] && continue
	line=$(LIVENESS_AT=25 LIVENESS_MIN="$min" timeout 260 ./run.sh "$m" \
		-window -nothrottle -seconds_to_run 27 -nvram_directory "$NV" \
		-autoboot_script "$RIGS/liveness.lua" 2>&1 | grep -m1 '^LIVENESS')
	case "$line" in
		*PASS*) ok "liveness $m  (${line#LIVENESS $m })" ;;
		*SKIP*) skip "liveness $m  -- no screen device" ;;
		"")     bad "liveness $m -- no LIVENESS line (crash, or never reached t=25)" ;;
		*)      bad "liveness $m  (${line#LIVENESS $m })" ;;
	esac
done

echo
echo "== audio oracle (kn7000 keybed + reverb) =="
if [ -n "$ONLY" ] && [ "$ONLY" != kn7000 ]; then
	skip "oracle -- --model $ONLY"
else
	# The recipe is pinned in rigs/README.md. Uses the SD image in place (read-only):
	# copying it costs 121 MB per run and has filled the scratch filesystem before.
	W=$(mktemp -d)/o.wav
	C=$(mktemp -d)
	rm -f -- "${NV:?}/kn7000/ic23"   # the liveness run above saved one; start blank again
	timeout 500 ./run.sh kn7000 -window -nothrottle -seconds_to_run 22 \
		-autoboot_script "$RIGS/money.lua" -wavwrite "$W" \
		-cfg_directory "$C" -nvram_directory "$NV" -harddisk sdcard_from_real_kn7000.img >/dev/null 2>&1
	if [ ! -s "$W" ]; then
		bad "oracle -- no wav produced"
	else
		got=$(md5sum "$W" | cut -d' ' -f1)
		if [ "$got" = "$ORACLE_MD5" ]; then
			ok "oracle md5 $got"
		else
			bad "oracle md5 $got != $ORACLE_MD5 (audio path changed -- re-baseline deliberately, in its own commit)"
		fi
	fi
	rm -rf "$(dirname "$W")" "$C"
fi

echo
echo "== kn5000 demo audio (the tone generator actually playing) =="
if [ -n "$ONLY" ] && [ "$ONLY" != kn5000 ]; then
	skip "kn5000 demo oracle -- --model $ONLY"
elif [ ! -f "$DEMO_RIG" ]; then
	bad "kn5000 demo oracle -- rig missing at $DEMO_RIG"
else
	D=$(mktemp -d)
	rm -f nvram/kn5000/nvram1     # 1 MB of work DRAM is persisted as NVRAM; stale state changes the run
	out=$(timeout 560 ./run.sh kn5000 -window -nothrottle -seconds_to_run 90 \
		-wavwrite "$D/demo.wav" -cfg_directory "$D" -nvram_directory "$D" \
		-snapshot_directory "$D" -autoboot_script "$DEMO_RIG" 2>&1)
	# PRECONDITION 1 -- the stimulus must have fired. The demo needs DEMO -> LEFT 4 -> LEFT 2;
	# pressing DEMO alone leaves transport at 0x00 and the machine silent, and a comparison of
	# two silent captures once got mistaken for a bit-identical pass.
	if ! echo "$out" | grep -q 'transport=04'; then
		bad "kn5000 demo -- stimulus never fired (transport never reached 0x04)"
	elif [ ! -s "$D/demo.wav" ]; then
		bad "kn5000 demo -- no wav produced"
	else
		# PRECONDITION 2 -- the capture must be audible, on the channels that carry audio.
		# Channel 0 is ALWAYS silent on this machine; the audio is on channels 1 and 2.
		lvl=$(python3 - "$D/demo.wav" <<-'PYEOF'
			import struct, sys, wave
			w = wave.open(sys.argv[1]); n, ch = w.getnframes(), w.getnchannels()
			s = struct.unpack("<%dh" % (n * ch), w.readframes(n))
			r = [ (sum(float(v) * v for v in s[c::ch]) / max(n, 1)) ** 0.5 for c in range(ch) ]
			print("%.1f" % max(r[1:] if ch > 1 else r))
		PYEOF
		)
		if [ "${lvl%%.*}" -lt 100 ] 2>/dev/null; then
			bad "kn5000 demo -- capture is silent or near-silent (max rms $lvl on ch1/ch2)"
		else
			got=$(md5sum "$D/demo.wav" | cut -d' ' -f1)
			if [ "$got" = "$KN5000_DEMO_MD5" ]; then
				ok "kn5000 demo oracle md5 $got  (rms $lvl)"
			else
				bad "kn5000 demo oracle md5 $got != $KN5000_DEMO_MD5 (rms $lvl) -- the tone-generator path changed; re-baseline deliberately"
			fi
		fi
	fi
	rm -rf "$D"
fi

rm -rf -- "${NV:?}"

echo
echo "== $PASS passed, $FAIL failed, $SKIP skipped =="
if [ "$FAIL" -gt 0 ]; then
	echo "failures:$FAILED"
	exit 1
fi
exit 0

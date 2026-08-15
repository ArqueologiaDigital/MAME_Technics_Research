#!/usr/bin/env bash
# rig.sh -- run one Lua measurement rig, reproducibly, by name.
#
# WHY THIS EXISTS: `tools/rigs/` holds 109 rigs, and the command to run one was documented
# only inside each rig's own header comment. Fourteen of those headers said:
#
#     ./run.sh kn5000 ... -autoboot_script tools/rigs/kn5000_p9_stall.lua
#
# which cannot work. `run.sh` lives in the EMULATOR directory and cd's to itself, so
# `tools/rigs/...` resolves against a directory that has no `tools/` in it.
#
# MEASURED 2026-08-15, because the first draft of this comment guessed and guessed wrong:
# MAME does **not** quietly run on without the rig. It exits **rc=3** with
# `Fatal error: Error loading autoboot script ...: file error`. So the real cost of those
# fourteen headers is a documented command that dies on contact, not a silent bad
# measurement -- annoying and wrong, but self-announcing. Recorded here so nobody re-derives
# a scarier story than the evidence supports.
#
# What this script actually buys, then: one runnable entry point for all 109 rigs, an
# absolute rig path that cannot suffer the bug above, the project's four hard-won launch
# rules applied by default, and a printed reproduce-line for every number a rig produces.
#
#   ./tools/rig.sh kn5000_p9_stall                  # infers the machine, 30 s
#   ./tools/rig.sh kn5000_p9_stall kn5000 -s 150
#   ./tools/rig.sh money kn7000 -s 22 -w /tmp/o.wav
#   ./tools/rig.sh liveness kn6000 -- -snapshot_directory /tmp/x
#
# Anything after `--` is passed to MAME verbatim. Rig-specific settings are read from the
# environment by the rigs themselves, so they just work:
#
#   P9_PRESS_AT=20 ./tools/rig.sh kn5000_p9_writer -s 150
#
# On exit it prints the exact, copy-pasteable command it ran. Quote a number from a rig and
# you can paste the recipe next to it -- which is the project rule this script exists to make
# cheap rather than virtuous.
set -uo pipefail

REPO="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
RIGS="$REPO/tools/rigs"
EMU_DIR="${EMU_DIR:-/home/fsanches/compartilhado/kn7000-emulator}"

SECS=30
WAV=""
LOG=""
TMO=""
USER_CFG=0
KEEP=0
EXTRA=()

usage() {
	cat <<'EOF'
usage: rig.sh <rig> [machine] [options] [-- extra mame args]

  <rig>       name in tools/rigs (with or without .lua), or a path to any .lua
  [machine]   kn7000 kn5000 kn6000 kn6500 kn2400 kn2600 kn1500
              (default: from a "-- rig-machine:" header, else the filename prefix,
               else kn7000 -- the choice is always printed)

  -s SECS     -seconds_to_run          (default 30)
  -w FILE     -wavwrite FILE
  -l FILE     write the run log here   (default: <tmpdir>/rig.log, path printed)
  -t SECS     hard timeout             (default: 8*SECS + 120)
  --user-cfg  use Felipe's REAL cfg/nvram instead of fresh throwaway ones
  --keep      keep the temp directory and print its path
  -h          this
EOF
}

[ $# -ge 1 ] || { usage; exit 2; }
case "$1" in -h|--help) usage; exit 0 ;; -*) echo "rig: first argument must be a rig name" >&2; usage; exit 2 ;; esac
RIG="$1"; shift

MACHINE=""
if [ $# -gt 0 ] && [ "${1#-}" = "$1" ]; then MACHINE="$1"; shift; fi

while [ $# -gt 0 ]; do
	case "$1" in
		-s) SECS="$2"; shift ;;
		-w) WAV="$2"; shift ;;
		-l) LOG="$2"; shift ;;
		-t) TMO="$2"; shift ;;
		--user-cfg) USER_CFG=1 ;;
		--keep) KEEP=1 ;;
		-h|--help) usage; exit 0 ;;
		--) shift; EXTRA=("$@"); break ;;
		*) echo "rig: unknown option $1" >&2; usage; exit 2 ;;
	esac
	shift
done

# ---- resolve the rig -------------------------------------------------------------------
# Resolve to an ABSOLUTE path before any cd. This is the whole point of the script: MAME is
# launched from $EMU_DIR, so a repo-relative -autoboot_script silently resolves to nothing.
case "$RIG" in
	*/*|*.lua) RIG_PATH="$(readlink -f "$RIG")" ;;
	*)         RIG_PATH="$RIGS/$RIG.lua" ;;
esac
[ -f "$RIG_PATH" ] || { echo "rig: no such rig: $RIG_PATH" >&2; exit 1; }
RIG_NAME="$(basename "$RIG_PATH" .lua)"

# ---- resolve the machine ---------------------------------------------------------------
# Order: explicit argument > "-- rig-machine:" header > filename prefix > kn7000.
# Whichever wins is printed, because a rig pointed at the wrong driver usually still runs
# and still produces output -- it is just measuring a different instrument.
WHY=""
if [ -n "$MACHINE" ]; then
	WHY="given on the command line"
else
	MACHINE="$(grep -m1 -oE '^--[[:space:]]*rig-machine:[[:space:]]*[a-z0-9]+' "$RIG_PATH" \
		| grep -oE '[a-z0-9]+$')"
	if [ -n "$MACHINE" ]; then
		WHY="from the rig's rig-machine: header"
	else
		case "$RIG_NAME" in
			kn5000*) MACHINE=kn5000 ;;
			kn6500*) MACHINE=kn6500 ;;
			kn6_*|kn6000*) MACHINE=kn6000 ;;
			kn24_*|kn2400*) MACHINE=kn2400 ;;
			kn2600*) MACHINE=kn2600 ;;
			kn1500*) MACHINE=kn1500 ;;
			*) MACHINE=kn7000 ;;
		esac
		WHY="guessed from the filename -- pass one explicitly if this is wrong"
	fi
fi

[ -d "$EMU_DIR" ] || { echo "rig: no emulator directory at $EMU_DIR" >&2; exit 1; }
[ -x "$EMU_DIR/run.sh" ] || { echo "rig: no run.sh at $EMU_DIR" >&2; exit 1; }

TMP="$(mktemp -d)"
[ -n "$LOG" ] || LOG="$TMP/rig.log"
LOG="$(readlink -f "$LOG")"
[ -n "$WAV" ] && WAV="$(readlink -f "$WAV")"
[ -n "$TMO" ] || TMO=$(( SECS * 8 + 120 ))

# ---- assemble ---------------------------------------------------------------------------
# -window, never -video none: the project rule is that a human can always see what a rig is
# doing. This costs a display and is deliberate.
ARGS=(-window -nothrottle -seconds_to_run "$SECS" -autoboot_script "$RIG_PATH")
[ -n "$WAV" ] && ARGS+=(-wavwrite "$WAV")

if [ "$USER_CFG" -eq 1 ]; then
	# RULE 20: a private -cfg_directory HIDES user-reported bugs. Felipe's "organ notes cut
	# short" was a persisted PORT_CONFNAME probe of ours deleting held notes -- and every rig
	# ran with a private cfg, so every rig contradicted him, for a day. When chasing something
	# a HUMAN reported on the real UI, reproduce the human's environment.
	CFGNOTE="USER cfg/nvram (reproduces Felipe's environment -- correct for chasing a user-reported bug)"
else
	ARGS+=(-cfg_directory "$TMP" -nvram_directory "$TMP" -snapshot_directory "$TMP")
	CFGNOTE="fresh throwaway cfg/nvram in $TMP (deterministic; ⚠ CANNOT reproduce a user-reported UI bug -- use --user-cfg for that)"
fi
ARGS+=("${EXTRA[@]+"${EXTRA[@]}"}")

echo "rig      : $RIG_NAME"
echo "  path   : $RIG_PATH"
echo "  machine: $MACHINE   ($WHY)"
echo "  cfg    : $CFGNOTE"
[ "$MACHINE" = kn5000 ] && [ "$USER_CFG" -eq 0 ] && \
	echo "  note   : the driver persists 1 MB of work DRAM as nvram1; the fresh -nvram_directory"
[ "$MACHINE" = kn5000 ] && [ "$USER_CFG" -eq 0 ] && \
	echo "           above sidesteps it, so this run does not inherit the previous run's RAM."
echo "  log    : $LOG"
[ -n "$WAV" ] && echo "  wav    : $WAV"
echo "  timeout: ${TMO}s for a ${SECS}s run"
echo

cd "$EMU_DIR" || exit 1
timeout "$TMO" ./run.sh "$MACHINE" "${ARGS[@]}" >"$LOG" 2>&1
RC=$?

echo
if [ "$RC" -eq 124 ]; then
	echo "rig: ⚠ TIMED OUT after ${TMO}s -- the log may be truncated. Raise it with -t."
elif [ "$RC" -ne 0 ]; then
	echo "rig: ⚠ exited $RC"
fi

# MAME already fatals (rc=3) on a missing or syntactically broken rig -- verified, see the
# header. This turns that into a one-line diagnosis instead of a fatal buried in a log the
# caller then has to go read.
if grep -qiE "cannot open|error loading|Lua error" "$LOG"; then
	echo "rig: ★ THE RIG DID NOT LOAD -- MAME ran without it. Output is meaningless:"
	grep -iE "cannot open|error loading|Lua error" "$LOG" | head -3 | sed 's/^/     /'
	RC=1
fi

echo "--- reproduce ---"
printf '  cd %s && timeout %s ./run.sh %s' "$EMU_DIR" "$TMO" "$MACHINE"
for a in "${ARGS[@]}"; do printf ' %q' "$a"; done
printf '\n'

if [ "$KEEP" -eq 1 ]; then
	echo "--- kept: $TMP"
else
	# Never delete a log the caller asked for by name, or one inside the temp dir they can
	# still want; print the tail instead so a short run needs no second command.
	case "$LOG" in "$TMP"/*) cp "$LOG" "${TMPDIR:-/tmp}/rig-$RIG_NAME.log" 2>/dev/null && \
		echo "--- log kept at ${TMPDIR:-/tmp}/rig-$RIG_NAME.log" ;; esac
	rm -rf "$TMP"
fi

exit "$RC"

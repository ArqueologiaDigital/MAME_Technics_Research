#!/bin/bash
# dis_sharc.sh IMAGE 0xPMADDR [COUNT_WORDS] [BASE_PMADDR]
#   -- disassemble effects-DSP (ADSP-21065L SHARC) program memory from a PM image file.
#
# SHARC companion to dis.sh (same per-invocation-tempfile + dd-offset discipline).
#
# IMAGE format: one 48-bit PM word per 8-byte LITTLE-ENDIAN slot -- the format
# unidasm -arch sharc consumes (8 bytes per opcode). This is what both existing
# producers emit:
#   * a live-MAME Lua dump:  f=io.open("pm.bin","wb")
#       dsp=manager.machine.devices[":dsp"]
#       pm=dsp.spaces["program"]              -- SHARC PM space
#       for a=0x8000,0x8DFF do f:write(string.pack("<I8", pm:read_u64(a))) end
#     (the running kernel lives at PM 0x8000-0x8DFF; see notes/dsp-effect-execution-chain.md)
#   * the record-pool extracts kn7000_disassembly/build/dsp/recNN_pm_XXXX.bin
#     (gen_dsp_records.py repacks the flash's 6-byte MSW-first stream into these slots).
# A raw 6-byte MSW-first stream is NOT accepted directly -- repack it first
# (see repack_pm48() in kn7000_disassembly/tools/gen_dsp_records.py).
#
# BASE_PMADDR = the PM word address of the FIRST slot in IMAGE (default 0x8000,
# correct for both producers above). COUNT_WORDS default 32.
#
# Examples:
#   tools/dis_sharc.sh live_pm_8000.bin 0x8004            # vector table (IDLE; JUMP ...)
#   tools/dis_sharc.sh live_pm_8000.bin 0x847c 8          # the reverb float recursion
#   tools/dis_sharc.sh ../kn7000_disassembly/build/dsp/rec04_pm_8000.bin 0x8020 3   # kernel ISR
UNI=/home/fsanches/compartilhado/mame-sony-video/unidasm
IMG="$1"; AH="$2"; COUNT=$(( ${3:-32} )); BASE=$(( ${4:-0x8000} ))
if [ -z "$IMG" ] || [ -z "$AH" ] || [ ! -f "$IMG" ]; then
	echo "usage: dis_sharc.sh IMAGE 0xPMADDR [COUNT_WORDS] [BASE_PMADDR=0x8000]" >&2
	exit 1
fi
OFF=$(( (AH - BASE) * 8 ))
if [ "$OFF" -lt 0 ]; then echo "PMADDR $2 is below image base $(printf 0x%X "$BASE")" >&2; exit 1; fi
TMP=$(mktemp /tmp/dis_sharc.XXXXXX) || exit 1
trap 'rm -f "$TMP"' EXIT
dd if="$IMG" of="$TMP" bs=1 skip="$OFF" count=$(( COUNT * 8 )) 2>/dev/null
if [ ! -s "$TMP" ]; then echo "empty extract -- PMADDR beyond image end?" >&2; exit 1; fi
"$UNI" "$TMP" -arch sharc -basepc "$AH" 2>/dev/null

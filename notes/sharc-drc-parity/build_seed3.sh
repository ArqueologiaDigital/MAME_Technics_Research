#!/bin/bash
# THIRD control, and the one the 19-machine run showed was missing.
#
# WHY IT EXISTS
#   Seed 1 perturbs the MODE1.ALUSAT tail, which lives in sharcdrc.cpp. It moved
#   5 of 19 machines. For the other 14 that proves nothing about the instrument:
#     * the 6 interpreter machines CANNOT be affected by a DRC-only seed, so their
#       match under seed 1 is structural, not evidence;
#     * the 8 DRC machines that matched may simply not overflow a fixed-point ALU
#       op in the window.
#   Either way, "the PR changes nothing on those 14" rests on a comparison never
#   shown to be sensitive to SHARC arithmetic on them.
#
# WHAT IT SEEDS
#   The plain fixed-point add, +1, in BOTH engines at once:
#     compute.hxx      Rn = Rx + Ry   (interpreter)
#     sharcdrc.cpp     Rn = Rx + Ry   (native emission)
#   compute.hxx is NOT touched by the submission, which is the point: this is a test
#   of the instrument, not of the change. A machine that still matches upstream with
#   its SHARC's most common arithmetic op wrong is a machine whose framebuffer this
#   harness cannot use to detect anything.
#
#   differs -> the comparison is sensitive to SHARC arithmetic on that machine
#   matches -> it is not, and that machine's ALL MATCH above carries no weight
set -uo pipefail
cd ~/compartilhado/mame-pr-kn7000drv
A=src/devices/cpu/sharc/compute.hxx
B=src/devices/cpu/sharc/sharcdrc.cpp
git checkout -q -- "$A" "$B"
python3 - "$A" "$B" <<'PY'
import sys
a, b = sys.argv[1], sys.argv[2]
s = open(a).read()
old = "\tuint32_t r = REG(rx) + REG(ry);\n\n\tCLEAR_ALU_FLAGS();\n\tSET_FLAG_AV_ADD(r, REG(rx), REG(ry));"
assert s.count(old) == 1, f'interpreter anchor found {s.count(old)} times'
s = s.replace(old, old.replace("REG(rx) + REG(ry);", "REG(rx) + REG(ry) + 1;", 1))
open(a, 'w').write(s)
t = open(b).read()
oldb = "\t\t\t\t\t\t\tUML_ADD(block, I8, REG(rx), REG(ry));"
assert t.count(oldb) == 1, f'DRC anchor found {t.count(oldb)} times'
t = t.replace(oldb, oldb + "\n\t\t\t\t\t\tUML_ADD(block, I8, I8, 1);")
open(b, 'w').write(t)
print('seeded +1 into the fixed add of both engines')
PY
[ $? = 0 ] || { echo "SEED3 FAILED"; git checkout -q -- "$A" "$B"; exit 1; }
SRC=src/mame/konami/gticlub.cpp,src/mame/konami/hornet.cpp,src/mame/konami/nwk-tr.cpp,src/mame/konami/zr107.cpp,src/mame/sega/model2.cpp
rm -f build/linux_gcc/bin/x64/Release/mame_shsat3/*.a shsat3
if timeout 5400 make SUBTARGET=shsat3 SOURCES=$SRC REGENIE=1 -j8 > /tmp/build_shsat3.log 2>&1; then
	cp -f shsat3 /tmp/mame-sharc-seed3 && echo "shsat3 OK $(stat -c%s /tmp/mame-sharc-seed3) bytes"
else
	echo "shsat3 FAIL -- see /tmp/build_shsat3.log"; grep -m5 'error:' /tmp/build_shsat3.log
fi
git checkout -q -- "$A" "$B"
echo "sources restored: $(git status --porcelain -- "$A" "$B" | wc -l) modified"
echo SEED3-BUILD-DONE

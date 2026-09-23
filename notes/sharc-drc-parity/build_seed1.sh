#!/bin/bash
# THE POSITIVE CONTROL for the SHARC A/B.
#
# A framebuffer that matches proves nothing unless a framebuffer CAN differ. This
# builds a third binary identical to the submission's except that the MODE1.ALUSAT
# saturation tail -- the one change of the five that alters what an EXISTING 21062
# machine computes -- is inverted: it saturates when ALUSAT is CLEAR and wraps when
# it is set. Any machine that executes an overflowing fixed-point ALU op must then
# draw something different from the upstream binary.
#
#   differs  -> the A/B can see this code path; the real binary matching is evidence
#   matches  -> the machine never overflows a fixed-point ALU op, and the A/B is
#               BLIND to that commit. An honest negative, not a pass.
set -uo pipefail
cd ~/compartilhado/mame-pr-kn7000drv
F=src/devices/cpu/sharc/sharcdrc.cpp
git checkout -q -- "$F"
python3 - "$F" <<'PY'
import sys, re
p = sys.argv[1]
s = open(p).read()
# Flip the three ALUSAT gates. Each reads "TEST MODE1,ALUSAT" then skips the clamp on
# Z (bit clear); inverting to NZ saturates exactly when the mode says not to.
n = 0
out = []
lines = s.split('\n')
for i, l in enumerate(lines):
    if 'UML_JMPc(block, uml::COND_Z,' in l and i > 0 and 'MODE1_ALUSAT' in lines[i-1]:
        l = l.replace('uml::COND_Z', 'uml::COND_NZ'); n += 1
    elif 'UML_MOVc(block, uml::COND_NZ, I0, 0x7fffffff);' in l and 'MODE1_ALUSAT' in lines[i-1]:
        l = l.replace('uml::COND_NZ', 'uml::COND_Z'); n += 1
    out.append(l)
assert n == 3, f'expected 3 ALUSAT gates, flipped {n}'
open(p, 'w').write('\n'.join(out))
print(f'seeded {n} inverted ALUSAT gates')
PY
[ $? = 0 ] || { echo "SEED FAILED"; git checkout -q -- "$F"; exit 1; }
SRC=src/mame/konami/gticlub.cpp,src/mame/konami/hornet.cpp,src/mame/konami/nwk-tr.cpp,src/mame/konami/zr107.cpp,src/mame/sega/model2.cpp
rm -f build/linux_gcc/bin/x64/Release/mame_shsat/*.a shsat
if timeout 5400 make SUBTARGET=shsat SOURCES=$SRC REGENIE=1 -j4 > /tmp/build_shsat.log 2>&1; then
	cp -f shsat /tmp/mame-sharc-seeded && echo "shsat OK $(stat -c%s /tmp/mame-sharc-seeded) bytes"
else
	echo "shsat FAIL -- see /tmp/build_shsat.log"; grep -m5 'error:' /tmp/build_shsat.log
fi
git checkout -q -- "$F"
echo "source restored: $(git status --porcelain -- "$F" | wc -l) modified"
echo SEEDED-BUILD-DONE

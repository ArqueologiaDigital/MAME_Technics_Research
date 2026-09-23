#!/bin/bash
# SECOND positive control, sharper than the first.
#
# Seed 1 inverted the ALUSAT gate, so it fires when the mode bit is CLEAR. A
# difference under it proves only that an overflowing fixed-point ALU op executes --
# not that MODE1.ALUSAT is ever SET, which is the only condition under which the
# submission's tail does anything at all.
#
# Seed 2 leaves the gate exactly as the submission writes it and corrupts only the
# VALUE it clamps to: 0 instead of 0x7FFFFFFF / 0x80000000. So
#   differs from the PR binary -> the ALUSAT-SET overflow path really executes, and
#                                 the PR binary matching upstream is evidence
#   matches the PR binary       -> these machines never take that path in the window
#                                 measured, and the A/B is blind to that commit.
set -uo pipefail
cd ~/compartilhado/mame-pr-kn7000drv
F=src/devices/cpu/sharc/sharcdrc.cpp
git checkout -q -- "$F"
python3 - "$F" <<'PY'
import sys
p = sys.argv[1]
s = open(p).read()
n = 0
lines = s.split('\n')
for i, l in enumerate(lines):
    # the saturating value is produced by XOR of the sign-extended wrapped result
    # with 0x80000000; replacing the mask with 0 makes the clamp write 0 or -1
    # instead, which is wrong in exactly the place the commit touches.
    if 'UML_XOR(block, dst, I8, 0x80000000);' in l or 'UML_XOR(block, REG(fa), I8, 0x80000000);' in l:
        lines[i] = l.replace('0x80000000', '0x00000000'); n += 1
    elif 'UML_MOVc(block, uml::COND_NZ, I0, 0x7fffffff);' in l and 'MODE1_ALUSAT' in lines[i-1]:
        lines[i] = l.replace('0x7fffffff', '0x00000000'); n += 1
assert n == 3, f'expected 3 clamp values, changed {n}'
open(p, 'w').write('\n'.join(lines))
print(f'seeded {n} corrupted clamp values')
PY
[ $? = 0 ] || { echo "SEED2 FAILED"; git checkout -q -- "$F"; exit 1; }
SRC=src/mame/konami/gticlub.cpp,src/mame/konami/hornet.cpp,src/mame/konami/nwk-tr.cpp,src/mame/konami/zr107.cpp,src/mame/sega/model2.cpp
rm -f build/linux_gcc/bin/x64/Release/mame_shsat2/*.a shsat2
if timeout 5400 make SUBTARGET=shsat2 SOURCES=$SRC REGENIE=1 -j4 > /tmp/build_shsat2.log 2>&1; then
	cp -f shsat2 /tmp/mame-sharc-seed2 && echo "shsat2 OK $(stat -c%s /tmp/mame-sharc-seed2) bytes"
else
	echo "shsat2 FAIL -- see /tmp/build_shsat2.log"; grep -m5 'error:' /tmp/build_shsat2.log
fi
git checkout -q -- "$F"
echo "source restored: $(git status --porcelain -- "$F" | wc -l) modified"
echo SEED2-BUILD-DONE

#!/bin/bash
# Why does the floppy commit fail to link when the tip, with the same N82077AA,
# does not?
#
# The answer is NOT the generated device list -- the regenerated project lists
# upd765.o correctly, and the object exists. It is the static ARCHIVE:
# upd765.cpp never changes across these commits, so its object stays older than
# liboptional.a from the previous commit's build, and make leaves the archive
# alone. This prints the two timestamps that show it, then rebuilds with the
# archives removed.
#
# ⚠ An earlier version of this script deleted only the generated project and
# reported PASS. That was a false positive: the run happened to inherit an
# archive that already contained upd765 from the tip's build. Deleting the
# archive is what the experiment has to control.
set -u
cd ~/compartilhado/mame-pr-kn7000drv
C=$(git rev-list --reverse upstream/master..technics-kn7000-driver-final | while read -r r; do
	[ "$(git log -1 --format=%s "$r")" = "matsushita/kn7000: add the floppy disk controller" ] && echo "$r"; done | head -1)
echo "testing $C"
git checkout -q --detach "$C"
O=build/linux_gcc/obj/x64/Release/src/devices/machine/upd765.o
A=build/linux_gcc/bin/x64/Release/mame_kn/liboptional.a
[ -f "$O" ] && [ -f "$A" ] && {
	echo "  object  $(date -r "$O" +%F\ %T)  $O"
	echo "  archive $(date -r "$A" +%F\ %T)  $A"
	ar t "$A" | grep -q upd765 && echo "  archive ALREADY holds upd765 -- this run cannot test anything" \
	                           || echo "  archive lacks upd765, as expected"
}
rm -f build/linux_gcc/bin/x64/Release/mame_kn/*.a build/linux_gcc/bin/x64/Release/*.a kn
rm -rf build/projects build/generated/mame/kn build/kn.flt
if timeout 3000 make SUBTARGET=kn SOURCES=src/mame/matsushita/kn7000.cpp REGENIE=1 -j8 > /tmp/floppy_clean.log 2>&1; then
	echo "RESULT: links once the archives are removed -> stale archive, not the commit"
	ar t "$A" | grep -c upd765 | xargs echo "  upd765 entries now in liboptional.a:"
else
	echo "RESULT: still fails -> the commit is genuinely broken"
	grep -E 'undefined reference|error' /tmp/floppy_clean.log | head -5
fi
git checkout -q technics-kn7000-driver-final

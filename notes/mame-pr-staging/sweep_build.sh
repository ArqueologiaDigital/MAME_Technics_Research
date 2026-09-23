#!/bin/bash
# Build every commit of the stack, so the history is bisectable.
# REGENIE=1 is required: without it a commit that adds a new source file links
# against a stale project and reports a false failure.
cd ~/compartilhado/mame-pr-kn7000drv
out=/tmp/sweep_out.txt; : > $out
for c in $(git rev-list --reverse upstream/master..polish-replay); do
	git checkout -q --detach "$c"
	# The STATIC ARCHIVES must go, or a commit that introduces a device links
	# without it. The device's own source never changes across these commits, so
	# its object is OLDER than liboptional.a from the previous commit's build,
	# and make considers the archive up to date -- it is rebuilt from the object
	# LIST, but only when something in it looks newer. Measured: upd765.o at
	# 23:41, liboptional.a at 04:13, and eleven "undefined reference to
	# upd765_family_device" on three commits in a row. Objects are kept, so this
	# costs a re-archive and a link, not a rebuild.
	rm -f build/linux_gcc/bin/x64/Release/mame_kn/*.a \
	      build/linux_gcc/bin/x64/Release/*.a kn
	rm -rf build/projects build/generated/mame/kn build/kn.flt
	if timeout 3000 make SUBTARGET=kn SOURCES=src/mame/matsushita/kn7000.cpp REGENIE=1 -j8 \
	     > /tmp/sweep_$c.log 2>&1; then r=OK; else r=FAIL; fi
	printf '%s %-55.55s build=%s\n' "$(git rev-parse --short "$c")" "$(git log -1 --format=%s "$c")" "$r" | tee -a $out
done
git checkout -q polish-replay
echo DONE | tee -a $out

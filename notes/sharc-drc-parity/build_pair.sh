#!/bin/bash
# Build two binaries carrying the five SHARC drivers: one at upstream/master and
# one at the submission's tip, so every existing SHARC machine can be run on both.
set -uo pipefail
cd ~/compartilhado/mame-pr-kn7000drv
SRC=src/mame/konami/gticlub.cpp,src/mame/konami/hornet.cpp,src/mame/konami/nwk-tr.cpp,src/mame/konami/zr107.cpp,src/mame/sega/model2.cpp
TIP=technics-kn7000-driver

build () {   # $1 = git ref, $2 = subtarget, $3 = output binary
	git checkout -q --detach "$1" || return 1
	rm -f build/linux_gcc/bin/x64/Release/mame_$2/*.a build/linux_gcc/bin/x64/Release/*.a "$2"
	rm -rf build/projects/linux_gcc/mame_$2 "build/generated/mame/$2" "build/$2.flt"
	if timeout 5400 make SUBTARGET=$2 SOURCES=$SRC REGENIE=1 -j8 > "/tmp/build_$2.log" 2>&1; then
		cp -f "$2" "$3" && echo "$2 OK  $(git rev-parse --short HEAD)  $(stat -c%s "$3") bytes"
	else
		echo "$2 FAIL $(git rev-parse --short HEAD)  -- see /tmp/build_$2.log"
		grep -m5 'error:' "/tmp/build_$2.log"
	fi
}

build upstream/master shbase /tmp/mame-sharc-base
build "$TIP"          shpr   /tmp/mame-sharc-pr
git checkout -q "$TIP"
echo BUILDS-DONE

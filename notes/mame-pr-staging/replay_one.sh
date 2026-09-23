#!/bin/bash
# Run by `git rebase -i --exec` after each pick: fold this session's polish into
# the commit that was just replayed, according to which files that commit owns.
set -euo pipefail
S=~/compartilhado/mame-pr-kn7000drv-staging/final2
R=~/compartilhado/mame-pr-kn7000drv-staging/replay_polish.py
cd ~/compartilhado/mame-pr-kn7000drv
subj=$(git log -1 --format=%s)
files=""
case "$subj" in
  "cpu/mn10300: add an execution core")
	files="src/devices/cpu/mn10300/mn10300.cpp src/devices/cpu/mn10300/mn10300.h" ;;
  "cpu/sharc: add the ADSP-21065L")
	files="src/devices/cpu/sharc/sharc.cpp src/devices/cpu/sharc/sharc.h src/devices/cpu/sharc/sharcdrc.cpp" ;;
  "matsushita: add the KN6000 and KN7000 control panel devices")
	files="src/mame/matsushita/kn6000_cpanel.cpp src/mame/matsushita/kn6000_cpanel.h src/mame/matsushita/kn7000_cpanel.cpp src/mame/matsushita/kn7000_cpanel.h src/mame/matsushita/kn_cpanel.cpp src/mame/matsushita/kn_cpanel.h" ;;
  "matsushita: add the KN6000 and KN7000 tone generators")
	files="src/mame/matsushita/kn6000_tonegen.cpp src/mame/matsushita/kn6000_tonegen.h src/mame/matsushita/kn7000_tonegen.cpp src/mame/matsushita/kn7000_tonegen.h src/mame/matsushita/kn_tonegen.cpp src/mame/matsushita/kn_tonegen.h" ;;
  "matsushita/kn7000: add the control panel artwork")
	files="src/mame/layout/kn7000.lay" ;;
esac
if [ -n "$files" ]; then
	for f in $files; do cp "$S/$(basename "$f")" "$f"; done
	echo "REPLAY  $subj  <- $(echo "$files" | wc -w) file(s)"
fi
if git show --stat --format= HEAD | grep -q 'matsushita/kn7000\.cpp'; then
	python3 "$R" src/mame/matsushita/kn7000.cpp | sed 's/^/REPLAY  /'
fi
if ! git diff --quiet; then
	git add -A && git commit --amend --no-edit --quiet
fi

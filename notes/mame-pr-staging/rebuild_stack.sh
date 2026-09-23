#!/bin/bash
# Rebuild the PR stack commit by commit, with this session's polish folded in.
#
# QUESTION IT ANSWERS
#   "How do the worktree edits reach the commit that owns each file, when
#    kn7000.cpp is split across five commits?"
#
#   Replaying the original diffs conflicts, because the polish rewrites the very
#   lines the later commits' hunks use as context. So this does not replay
#   diffs at all: for each commit it checks out that commit's TREE, applies the
#   polish deterministically to that tree, and re-commits with the original
#   message and author. Every commit's content is therefore a pure function of
#   (original tree, polish pairs) -- nothing can half-apply.
#
# PASS  the rebuilt tip's tree must equal the pre-replay worktree (asserted at
#       the end), and every commit must still build (swept separately).
set -euo pipefail
S=~/compartilhado/mame-pr-kn7000drv-staging/final2
R=~/compartilhado/mame-pr-kn7000drv-staging/replay_polish.py
STAGES=~/compartilhado/mame-pr-kn7000drv-staging/sharc_stages
MSGS=~/compartilhado/mame-pr-kn7000drv-staging/sharc_msgs
cd ~/compartilhado/mame-pr-kn7000drv

ORDER=(94aaed10c1b 71314062f43 62e66b54b83 b1e19b95e01 efcbb3c0ccf 50e43616968 \
       d9b4ba6c117 9f2f72ba9a8 bcf33138beb 24d6ccb1459 9582437bf1e)

# Each commit's TREE is a full snapshot, so reading it back restores the
# UNPOLISHED copy of every file an earlier commit already introduced. The polish
# is therefore re-applied CUMULATIVELY: OWNED grows as the stack is replayed, and
# at each step every file already in it is refreshed from final2/. The set must
# be built from the commits themselves rather than globbed off the index --
# globbing also catches the UPSTREAM sharc files, which would silently move the
# 21065L work into whichever commit ran first.
declare -a OWNED=()

owned_files () {
	case "$1" in
	  "cpu/mn10300: add an execution core")
		echo "src/devices/cpu/mn10300/mn10300.cpp src/devices/cpu/mn10300/mn10300.h" ;;
	  "matsushita: add the KN6000 and KN7000 control panel devices")
		echo "src/mame/matsushita/kn6000_cpanel.cpp src/mame/matsushita/kn6000_cpanel.h src/mame/matsushita/kn7000_cpanel.cpp src/mame/matsushita/kn7000_cpanel.h src/mame/matsushita/kn_cpanel.cpp src/mame/matsushita/kn_cpanel.h" ;;
	  "matsushita: add the KN6000 and KN7000 tone generators")
		echo "src/mame/matsushita/kn6000_tonegen.cpp src/mame/matsushita/kn6000_tonegen.h src/mame/matsushita/kn7000_tonegen.cpp src/mame/matsushita/kn7000_tonegen.h src/mame/matsushita/kn_tonegen.cpp src/mame/matsushita/kn_tonegen.h" ;;
	  "matsushita/kn7000: add the control panel artwork")
		echo "src/mame/layout/kn7000.lay" ;;
	  *) echo "" ;;
	esac
}

git checkout -q -B polish-replay upstream/master
for c in "${ORDER[@]}"; do
	subj=$(git log -1 --format=%s "$c")
	git read-tree -u --reset "$c"

	# The SHARC change is not one commit: ~750 of its lines alter the SHARED
	# 2106x core that Model 2/3, Hornet, gticlub and zr107 execute, behind a
	# subject that promises a new variant. split_sharc.py cuts it into five
	# cumulative stages, each applied to PRISTINE upstream, so a reviewer sees
	# the shared-core changes apart from the device. Stage 5 reproduces the
	# branch exactly -- that is the split's acceptance test.
	if [ "$subj" = "cpu/sharc: add the ADSP-21065L" ]; then
		for k in 1 2 3 4 5; do
			git checkout -q upstream/master -- src/devices/cpu/sharc/
			git apply "$(ls "$STAGES"/stage$k-*.patch)"
			# read-tree above restored the UNPOLISHED copies of everything an
			# earlier commit introduced, so refresh them here too -- otherwise the
			# first SHARC commit carries the MN10300 cleanup.
			for f in "${OWNED[@]:-}"; do
				[ -n "$f" ] && cp "$S/$(basename "$f")" "$f"
			done
			git add -A
			git commit -q -F "$MSGS/$k.txt"
			printf '%-58s %s\n' "$(git log -1 --format=%s)" "$(git rev-parse --short HEAD)"
		done
		OWNED+=(src/devices/cpu/sharc/sharc.cpp src/devices/cpu/sharc/sharc.h \
		        src/devices/cpu/sharc/sharcdrc.cpp src/devices/cpu/sharc/sharcfe.cpp \
		        src/devices/cpu/sharc/sharcfe.h src/devices/cpu/sharc/sharcops.hxx)
		continue
	fi

	for f in $(owned_files "$subj"); do OWNED+=("$f"); done
	for f in "${OWNED[@]:-}"; do
		[ -n "$f" ] && cp "$S/$(basename "$f")" "$f"
	done
	# Only the five commits that actually touch the driver get the replay:
	# kn7000.cpp already exists upstream, so running it everywhere would put
	# driver changes into the CPU-core commit.
	if git show --stat --format= "$c" | grep -q 'matsushita/kn7000\.cpp'; then
		python3 "$R" src/mame/matsushita/kn7000.cpp >/dev/null
	fi
	git add -A
	# The artwork commit's own body described an end state two later commits
	# changed, so it is re-worded rather than carried over verbatim.
	if [ "$subj" = "matsushita/kn7000: add the control panel artwork" ]; then
		git commit -q -F "$MSGS/../msg_artwork.txt"
	else
		git commit -q -C "$c"
	fi
	printf '%-58s %s\n' "$subj" "$(git rev-parse --short HEAD)"
done

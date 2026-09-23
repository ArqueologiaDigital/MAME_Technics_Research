#!/usr/bin/env python3
"""Split the single SHARC change into five reviewable commits.

QUESTION IT ANSWERS
  "This commit says 'add the ADSP-21065L', but most of it changes the SHARED
   2106x core that Model 2/3, Hornet, gticlub and zr107 all execute. How does a
   reviewer see the shared-core changes separately from the new device?"

METHOD
  Each of the diff's hunks is assigned to one group. Stage k's file content is
  then produced by applying the hunks of groups 1..k to PRISTINE UPSTREAM --
  one application per stage, never a cumulative chain, so no stage inherits
  another's offsets. Every hunk's context is upstream context, which is what
  makes the subsets apply at all.

  The groups are ordered so each one builds: the parameterisation first (the
  variant needs its virtuals), then the interpreter fallback (the native
  implementations below remove cases that would otherwise abort), then the
  ops, then ALUSAT, then the device.

RUN   python3 split_sharc.py <full.diff> <outdir>
PASS  prints the per-stage hunk counts; every hunk must be assigned, and the
      last stage's patch must reproduce the branch's own file content.
"""
import os
import re
import sys

# hunk number (in file order, as split_sharc.py numbers them) -> group
GROUPS = {
    1: 'variant-base-parameterisation',
    2: 'interpreter-fallback',
    3: 'fixed-point-ops',
    4: 'alusat',
    5: 'adsp21065l',
}
# Hunks are assigned by CONTENT, not by index: an index map silently mis-assigns
# everything after any hunk that appears or disappears, which happened once.
# Each rule is (file suffix, regex over the hunk text) -> group; the first match
# wins, and a hunk matching no rule is a hard error.
RULES = [
    # 5: the new device and the host-upload notification it needs
    ('sharc.cpp', r'DEFINE_DEVICE_TYPE\(ADSP21065L|adsp21065l_device::adsp21065l_device|notify_pm_written', 5),
    ('sharc.h',   r'adsp21065l_device|notify_pm_written|Host code-upload', 5),
    # 4: MODE1.ALUSAT in the DRC's fixed-point ALU
    ('sharcdrc.cpp', r'alusat|ALUSAT', 4),
    # 3: the fixed-point ops themselves, in both engines
    ('sharcops.hxx', r'.', 3),
    ('sharcdrc.cpp', r'compute_avg|signed average|SAT MR|TOGGLE|fixed-point multiplier|MULS|DMULS|ASTAT_MU|ASTAT_MV', 3),
    ('sharc.h',      r'compute_avg', 3),
    # 2: run an unimplemented compute/shift op through the interpreter
    ('sharcdrc.cpp', r'unimplemented_compute|unimplemented_shiftimm|compute_fallback', 2),
    ('sharc.h',      r'unimplemented_compute|unimplemented_shiftimm|fixed_alusat_tail', 2),
    # 1: let a variant place its internal memory elsewhere
    ('sharc.cpp',  r'.', 1),
    ('sharc.h',    r'.', 1),
    ('sharcdrc.cpp', r'.', 1),
    ('sharcfe.cpp',  r'.', 1),
    ('sharcfe.h',    r'.', 1),
]


def group_of(path, text):
    base = path.split('/')[-1]
    import re as _re
    for suffix, pat, g in RULES:
        if base == suffix and _re.search(pat, text, _re.I):
            return g
    return None


def hunks(path):
    """Yield (n, file, text) for each hunk, plus the per-file headers."""
    lines = open(path, encoding='utf-8').read().split('\n')
    out, headers = [], {}
    f, hdr, cur, n = None, [], None, 0
    for l in lines:
        if l.startswith('diff --git '):
            if cur:
                out.append((n, f, '\n'.join(cur)))
                cur = None
            hdr = [l]
            f = None
        elif l.startswith(('index ', '--- ', '+++ ', 'new file', 'old mode', 'new mode',
                           'similarity', 'rename ')) and cur is None:
            hdr.append(l)
            if l.startswith('+++ b/'):
                f = l[6:]
                headers[f] = '\n'.join(hdr)
        elif l.startswith('@@'):
            if cur:
                out.append((n, f, '\n'.join(cur)))
            n += 1
            cur = [l]
        elif cur is not None:
            cur.append(l)
    if cur:
        out.append((n, f, '\n'.join(cur)))
    return out, headers


def main():
    src, outdir = sys.argv[1], sys.argv[2]
    hs, headers = hunks(src)
    assign = {}
    for n, f, t in hs:
        g = group_of(f, t)
        assert g is not None, 'unassigned hunk %d in %s' % (n, f)
        assign[n] = g
    os.makedirs(outdir, exist_ok=True)
    for k in sorted(GROUPS):
        want = {n for n, g in assign.items() if g <= k}
        byfile = {}
        for n, f, t in hs:
            if n in want:
                byfile.setdefault(f, []).append(t)
        parts = []
        for f in sorted(byfile):
            parts.append(headers[f])
            parts.extend(byfile[f])
        p = os.path.join(outdir, 'stage%d-%s.patch' % (k, GROUPS[k]))
        open(p, 'w').write('\n'.join(parts).rstrip('\n') + '\n')
        print('stage %d %-32s %3d hunks -> %s' % (k, GROUPS[k], len(want), os.path.basename(p)))


if __name__ == '__main__':
    main()

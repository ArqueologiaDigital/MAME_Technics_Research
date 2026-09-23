#!/usr/bin/env python3
"""Build the per-machine result table in results-<date>/README.md from the raw logs.

WHY IT EXISTS
  The table is the summary a reader trusts, so it must not be typed. It is derived
  from the three ab_run.sh logs.

THE BUG IT NOW GUARDS AGAINST
  The first version matched `(MATCH|DIFFERS.*)$`. ab_run.sh prints "MATCH (6 frames)",
  so the MATCH branch could not reach end-of-line and NEITHER branch matched: every
  MATCH silently became "?" while the DIFFERS rows looked perfect. A summary that
  loses exactly the rows carrying the result is worse than no summary, so this now
  asserts that every expected machine was parsed from every log, and that the
  base-vs-PR log really is all MATCH before it says so.

RUN   python3 make_results_table.py <results-dir>
"""
import re, sys

D = sys.argv[1] if len(sys.argv) > 1 else 'results-2026-09-24'
ORDER = ("gticlub slrasslt gradius4 nbapbp jetwave midnrun windheat doa gunblade "
         "pltkids rchase2 vstriker zerogun hangplt daytona motoraid vcop vcop2 vf2").split()
SHARC = set(ORDER[:14])          # the rest are Model 2O/2A/2C: Fujitsu TGP, no SHARC

def parse(path, label):
    txt = open(path).read()
    return {m.group(1): m.group(2) for m in re.finditer(
        r'^\s+(\w+)\s+base_exit=\S+\s+%s_exit=\S+\s+(MATCH|DIFFERS)' % label, txt, re.M)}

logs = {'pr':    (f'{D}/ab-base-vs-pr.log', 'pr'),
        'seed1': (f'{D}/ab-base-vs-seed1-alusat-gate.log', 'seed1'),
        'seed3': (f'{D}/ab-base-vs-seed3-fixed-add.log', 'seed3')}
res = {}
for key, (path, label) in logs.items():
    res[key] = parse(path, label)
    missing = [g for g in ORDER if g not in res[key]]
    assert not missing, f'{key}: these machines did not parse out of {path}: {missing}'
assert set(res['pr'].values()) == {'MATCH'}, 'base vs PR is not all MATCH: ' + repr(res['pr'])

print('| machine | has SHARC | base vs PR | seed 1 (ALUSAT gate) | seed 3 (fixed add) |')
print('|---|---|---|---|---|')
for g in ORDER:
    print('| `%s` | %s | %s | %s | %s |' % (
        g, 'yes' if g in SHARC else '**no**', res['pr'][g], res['seed1'][g], res['seed3'][g]))

sens = sorted(g for g in SHARC if res['seed3'][g] == 'DIFFERS' or res['seed1'][g] == 'DIFFERS')
blind = sorted(SHARC - set(sens))
print()
print('-- %d of %d SHARC machines have a working sensitivity control; blind: %s'
      % (len(sens), len(SHARC), ', '.join(blind) or 'none'))
print('-- non-SHARC machines all unmoved by the SHARC-arithmetic seed: %s'
      % all(res['seed3'][g] == 'MATCH' for g in ORDER if g not in SHARC))

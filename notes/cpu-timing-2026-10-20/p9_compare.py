#!/usr/bin/env python3
# p9_compare.py UNIT_JSON MAME_JSON [--md] -- pass 9 (the CPU timing probe) test by test: the unit against MAME.
#
# Both files are check_cpu_probe.py --json output (technics-roms-disasm kn7000/tools/cnv_romdump, release
# 2026-10-20-cputime). Prints, per test, ns per operation on the unit and in MAME, the difference in %, and the
# cycles at 64 MHz; then the summary: how many tests are within 3 % and 10 %, and the worst ones. Tests whose
# unit value is unreliable (fewer than 4 clean runs) are marked and left out of the summary.
import json, sys

def ns_per_op(t):
    v = t.get('ns_per_op')
    return v

def main(argv):
    md = '--md' in argv
    a = [x for x in argv if not x.startswith('--')]
    unit, mame = (json.load(open(p)) for p in a[:2])
    rows, diffs = [], []
    for name, tu in unit['tests'].items():
        tm = mame['tests'].get(name)
        u = ns_per_op(tu)
        m = ns_per_op(tm) if tm else None
        if u is None or m is None:
            continue
        clean = tu['runs'].get('clean', 0)
        d = 100.0 * (m - u) / u if u else 0.0
        flag = '' if clean >= 4 else 'unreliable (%d clean)' % clean
        rows.append((name, f'{u:.1f}', f'{m:.1f}', f'{d:+.1f}', f'{u / 15.62:.2f}', f'{m / 15.62:.2f}', flag))
        if not flag:
            diffs.append((abs(d), name, d))
    hdr = ('test', 'unit ns', 'MAME ns', 'diff %', 'unit cyc', 'MAME cyc', 'note')
    w = [max(len(str(r[i])) for r in rows + [hdr]) for i in range(len(hdr))]
    line = lambda r: '| ' + ' | '.join(str(r[i]).ljust(w[i]) for i in range(len(hdr))) + ' |'
    print(line(hdr))
    print('|' + '|'.join('-' * (x + 2) for x in w) + '|')
    for r in rows:
        print(line(r))
    diffs.sort(reverse=True)
    n = len(diffs)
    print()
    print(f'{n} tests compared: {sum(1 for d in diffs if d[0] <= 3)} within 3 %, {sum(1 for d in diffs if d[0] <= 10)} within 10 %')
    print('worst: ' + ', '.join(f'{nm} {d:+.1f}%' for _, nm, d in diffs[:12]))

if __name__ == '__main__':
    main(sys.argv[1:])

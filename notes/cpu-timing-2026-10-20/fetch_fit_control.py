#!/usr/bin/env python3
# fetch_fit_control.py -- the control-flow part of the fetch model (mn10300_timing.h section 3): which refill rules
# after a jump reproduce pass 9's call/return and branch tests on the unit?
#
# Simulates the same queue as the core (8 bytes, 2.1 bytes per cycle) on the tests' instruction sequences, laid out
# at their addresses in the release binary (romdump_cputime.s, from the map of a run_test.sh --cputime build:
# cfc_lp 0x502BCCE0, ct_rf 0x502BCB7F, ct_r0 0x502BCB79, CtTwin 0x502BCF65 ...), under variants:
#   W   = cycles before the block after a jump target's arrives (FQ_HOLD),
#   nt  = an untaken Bcc as a fixed 1.75 cycles, or 1 cycle and nt bytes of fetch (FQ_UNTAKEN),
#   ovl = whether a transfer slower than a taken branch (call, return) fetched during its extra cycles.
# Prints the best variants by the worst test and by the sum over the tests, against the unit's cycles (hard-coded
# below, from pass9-check-2026-10-20.txt). The core uses W = 0.75, nt = 2 bytes, ovl on; in MAME that gave FLLG -4 %,
# FLSH +12.5 %, JMP -9 %, the call/return tests within 2 % (pass9_unit_vs_mame.md).
B = 2.1; Q = 8.0
def run(seq, W, nt, ovl, reps=40):
    t = 0.0; q = 8.0; hold = 0.0; xfer_prev = True; lastE = 3.0
    times = []
    for _ in range(reps):
        t0 = t
        for (a, L, E, kind) in seq:
            if xfer_prev:
                q = 8.0 - (a & 7)
                if ovl: q = min(Q, q + B * max(0.0, lastE - 3.0))
                hold = W
            if q < L:
                need = L - q
                t += hold + need / B; q += need; hold = 0.0
            q -= L
            e = E
            if kind == 'N':
                if nt == 'fixed': e = 1.75
                else: e = 1.0; q -= nt
            t += e
            fill = max(0.0, e - hold); hold = max(0.0, hold - e)
            q = min(Q, q + B * fill)
            xfer_prev = (kind == 'X'); lastE = e
        times.append(t - t0)
    return times[-1]

def cfc(target):            # cfc_lp at ...CCE0: 4 x (mov a0,d0 (2B, F1 D?); calls (a1) (2B)), add -1,d2; bne
    s = []; a = 0x502BCCE0
    for i in range(4):
        s.append((a, 2, 1, 'n')); a += 2
        s.append((a, 2, 4, 'X')); a += 2
        s += target
    s += [(a, 2, 1, 'n'), (a + 2, 2, 3, 'X')]
    return s
RF = [(0x502BCB7F, 3, 4, 'X')]
TW = 0x502BCF65
def twin(long):
    s = [(TW, 1, 1, 'n'), (TW + 1, 3, 1, 'n'), (TW + 4, 6, 2, 'n')]
    if not long:
        return s + [(TW + 10, 2, 1, 'N'), (TW + 12, 2, 1, 'n'), (TW + 14, 2, 3, 'X'), (0x502BCFD9, 1, 1, 'n'), (0x502BCFDA, 3, 4, 'X')]
    s += [(TW + 10, 2, 3, 'X')]
    a = 0x502BCF75
    for k in range(7):
        s += [(a, 6, 2, 'n'), (a + 6, 2, 3, 'X')]
        a += 12
    return s + [(a, 6, 2, 'n'), (a + 6, 6, 2, 'n'), (a + 12, 2, 1, 'N'), (a + 14, 2, 1, 'n'), (a + 16, 1, 1, 'n'), (a + 17, 3, 4, 'X')]
def callpair(target, tlen, texec):     # 8 x call d16 (5B, 5) at ...CB20 + target
    s = []; a = 0x502BCB20
    for i in range(8):
        s.append((a, 5, 5, 'X')); a += 5
        s.append((target, tlen, texec, 'X'))
    return s + [(a, 2, 1, 'n'), (a + 2, 2, 3, 'X')]
def stream(L, E, kind, n=16, a=0x502BC900):
    s = []
    for i in range(n):
        s.append((a, L, E, kind)); a += L
    return s + [(a, 2, 1, 'n'), (a + 2, 2, 3, 'X')]

unit = {'CALF': 9.02, 'CAL0': 10.02, 'CALS': 9.01, 'CRET': 9.02, 'FLLG': 60.06, 'FLSH': 10.01, 'BEQ': 1.75, 'BRA': 3.0, 'JMP': 3.5, 'BNE': 3.0}
def evaluate(W, nt, ovl):
    loop = run([(0x502BC900, 2, 1, 'n'), (0x502BC902, 2, 3, 'X')], W, nt, ovl)
    crt = (run(cfc(RF), W, nt, ovl) - loop) / 4            # mov + calls + retf, less the loop's share
    res = {'CRET': crt,
           'FLLG': run(cfc(twin(True)), W, nt, ovl) / 4 - crt,
           'FLSH': run(cfc(twin(False)), W, nt, ovl) / 4 - crt,
           'CALF': (run(callpair(0x502BCB7F, 3, 4), W, nt, ovl) - loop) / 8,
           'CAL0': (run(callpair(0x502BCB79, 3, 5), W, nt, ovl) - loop) / 8,
           'CALS': None,
           'BEQ': (run(stream(2, 1, 'N'), W, nt, ovl) - loop) / 16,
           'BRA': (run(stream(2, 3, 'X'), W, nt, ovl) - loop) / 16,
           'JMP': (run(stream(3, 3, 'X', a=0x502BC928), W, nt, ovl) - loop) / 16,
           'BNE': None}
    # CALS: calls (a1) (2B, 4) + rets (2B, 5) at ct_rs ...CB82, 8 pairs from ccs_lp ...CB60
    s = []; a = 0x502BCB60
    for i in range(8):
        s += [(a, 2, 4, 'X'), (0x502BCB82, 2, 5, 'X')]; a += 2
    res['CALS'] = (run(s + [(a, 2, 1, 'n'), (a + 2, 2, 3, 'X')], W, nt, ovl) - loop) / 8
    res['BNE'] = res['BRA']
    return res
best = []
for W in (0.0, 0.25, 0.5, 0.75, 1.0):
    for nt in ('fixed', 1.5, 2.0, 2.5):
        for ovl in (False, True):
            r = evaluate(W, nt, ovl)
            err = max(abs(r[k] - unit[k]) / unit[k] for k in unit)
            tot = sum(abs(r[k] - unit[k]) / unit[k] for k in unit)
            best.append((err, W, nt, ovl, r, tot))
line = lambda e: (f'max err {100*e[0]:.1f}%, sum {100*e[5]:.0f}%, W={e[1]} nt={e[2]} ovl={e[3]}: ' +
                  ' '.join(f'{k}={e[4][k]:.2f}' for k in unit))
print('by the worst test:')
for e in sorted(best, key=lambda x: x[0])[:4]:
    print('  ' + line(e))
print('by the sum over the tests (FLLG, the firmware routine, weighs in):')
for e in sorted(best, key=lambda x: x[5])[:4]:
    print('  ' + line(e))
print('the core\'s choice (the MAME run, pass9_unit_vs_mame.md, is what counts: the core differs from this sketch in detail):')
for e in best:
    if e[1] == 0.75 and e[2] == 2.0 and e[3]:
        print('  ' + line(e))

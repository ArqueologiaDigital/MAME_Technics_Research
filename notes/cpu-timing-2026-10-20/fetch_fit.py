#!/usr/bin/env python3
# fetch_fit.py [UNIT_JSON] -- fit the fetch-queue model of mn10300_timing.h (section 3) to pass 9's straight-line tests.
#
# Question: what fetch rate and queue size make a run of 3-byte instructions cost 1.25 cycles each and of 6-byte ones
# 2.75 (the unit), while 1-2 byte ones cost 1 and the loops (add -1,d0; bne) 4 and (add 512,a0; add -1,d0; bne) 5?
# Model: a queue of Q bytes refilled at B bytes per cycle; an instruction waits until all its bytes are in; a taken
# branch leaves the queue holding the target's 8-byte block (the tests' loops are 8-aligned: 8 bytes). Each test is 16
# copies of the instruction, then add -1,d0 (2 bytes, 1 cycle) and bne (2 bytes, 3 cycles taken), as in
# romdump_cputime.s. The unit's cycles come from UNIT_JSON (check_cpu_probe.py --json of the unit's CPUTIME.BIN;
# default: the private technics_roms copy). Prints the best (B, Q) and what it predicts per test.
import json, sys

UNIT = sys.argv[1] if len(sys.argv) > 1 else \
    '/home/fsanches/compartilhado/technics_roms/roms/kn7000/real_dump_v1.3_b893/pass9-run1/cpu_time.json'
u = json.load(open(UNIT))
MHZ = u['core_mhz']
cyc = lambda name: u['tests'][name]['ns_per_op'] * MHZ / 1000.0

def body(L, E, k=16):
    return [(L, E)] * k + [(2, 1), (2, 'T')]

# (test, body, cycles per turn measured)
TESTS = [
    ('ADD',  body(1, 1), 16 * cyc('ADD') + 4),
    ('AND',  body(2, 1), 16 * cyc('AND') + 4),
    ('LSRI', body(3, 1), 16 * cyc('LSRI') + 4),
    ('MI16', body(3, 1), 16 * cyc('MI16') + 4),
    ('MI32', body(6, 2), 16 * cyc('MI32') + 4),
    ('LOOP', [(2, 1), (2, 'T')], cyc('LOOP')),
    ('LPW5', [(4, 1), (2, 1), (2, 'T')], cyc('LPW5')),
]

def turn(b, B, Q, q0=8, taken=3, turns=20):
    t = 0.0
    for _ in range(turns):
        q, t = q0, 0.0
        for L, E in b:
            if q < L:
                s = (L - q) / B
                t += s
                q += s * B
            q -= L
            e = taken if E == 'T' else E
            t += e
            q = min(Q, q + B * e)
    return t

best = []
for B in [x / 20 for x in range(30, 90)]:
    for Q in (4, 6, 8, 10, 12, 16):
        err = sum(abs(turn(b, B, Q) - m) / m for _, b, m in TESTS)
        best.append((err, B, Q))
best.sort()
err, B, Q = best[0]
print(f'best: B = {B} bytes/cycle, Q = {Q} bytes (sum of relative errors {err:.4f}); next: ' +
      ', '.join(f'B={b} Q={q} ({e:.4f})' for e, b, q in best[1:4]))
rows = [('test', 'unit cycles/turn', 'model', 'per instruction, unit', 'model')]
for name, b, m in TESTS:
    p = turn(b, B, Q)
    k = 16 if len(b) > 3 else 1
    sub = 4 if k == 16 else 0
    rows.append((name, f'{m:.2f}', f'{p:.2f}', f'{(m - sub) / k:.3f}', f'{(p - sub) / k:.3f}'))
w = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
for j, r in enumerate(rows):
    print('| ' + ' | '.join(r[i].ljust(w[i]) for i in range(len(r))) + ' |')
    if j == 0:
        print('|' + '|'.join('-' * (x + 2) for x in w) + '|')

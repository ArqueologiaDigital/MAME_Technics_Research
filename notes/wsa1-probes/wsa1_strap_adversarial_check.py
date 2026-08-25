#!/usr/bin/env python3
"""Adversarial re-derivation of the "PB bit 0 is the model-variant strap" claim.

QUESTION IT ANSWERS: do the load-bearing numbers in the PB-bit-0 strap report
survive a census built on MAME's OWN TLCS-900 disassembler rather than on raw
byte patterns?  The existing wsa1_port_strap_census.py / wsa1_directpage_census.py
scan raw bytes, so they fire inside data tables; this script decodes the images
with `unidasm -arch tlcs900` and counts only lines that decoded as instructions.

    python3 wsa1_strap_adversarial_check.py

Every check prints PASS / FAIL / NOTE and the script exits non-zero on a FAIL.

WHAT EACH CHECK MEANS
  1  the strap routine's bytes at 0xF82882 are exactly as reported
  2  PBCR (SFR 0x2E) is written EXACTLY ONCE, 0x0C, so PB bit 0 is an input for
     the whole run.  (The report asserted the reset value but never checked for
     a later rewrite; `08 2e 79` at 0xFB1AB9 is a data-table false positive.)
  3  P7CR (SFR 0x16) is written EXACTLY ONCE, 0x33, so P7 bit 1 really is an
     output.  (`08 16 21` at 0xF8C0A4 sits inside a block that 0xF8C09B loads
     as a DATA pointer -- `ld XIY,0x00f8c0a4` -- so it is not an instruction.)
  4  (0x0000C4) has exactly one producer in prom_a+prom_b
  5  extent of the (0xC4) tests, INCLUDING the two prom_b sites the report omits
  6  the P7-bit-1 restore sites -- six, not four; two of them are timeouts
  7  uniqueness of the (0xC4) shape in the 8-bit direct page of CPU 1
"""
import re, subprocess, sys, collections, tempfile, os

ROMS = '/home/fsanches/compartilhado/technics_roms/roms/wsa1/'
UNIDASM = '/home/fsanches/compartilhado/mame/unidasm'
IMAGES = {'a': ('wsa1_os_v2.ic12', 0xF80000),
          'b': ('wsa1_os_v2.ic13', 0xF00000),
          'c': ('wsa1_os_v2.ic28', 0xF80000)}
LINE = re.compile(r'^([0-9a-f]{6}): ((?:[0-9a-f]{2} )+)\s+(.*)$')
fails = []

# ---------------------------------------------------------------------------
# ADJUDICATED DATA FALSE POSITIVES.  A linear sweep resyncs inside data tables
# and emits plausible-looking instructions there.  Each address below was
# checked by hand and is DATA, with the reason recorded.  Nothing else in this
# script is allowed to discard a hit.
# ---------------------------------------------------------------------------
DATA_FP = {
    0xFA23F2: "prom_a display-list table: 10-byte records `0a XX 00 YY 00 XX 00 ZZ 00 02` "
              "with XX ascending 0x74,0x84,0x85,0x9C,0xAC,0xC4,0xD4,0xEC,0xFC,0x114",
    0xF281D4: "prom_b display-list table, same `0a nn 00 vv` record shape",
    0xF28224: "prom_b display-list table", 0xF2827E: "prom_b display-list table",
    0xF28FBA: "prom_b display-list table", 0xF2900A: "prom_b display-list table",
    0xF29064: "prom_b display-list table", 0xF34339: "prom_b display-list table",
    0xF39339: "prom_b display-list table",
    0xF785EB: "prom_b font/pad region, surrounded by 0xFF/0x00 filler",
    0xFB1AB9: "prom_a stride table: 4-byte records `00 nn ee 77 / 00 nn 2e 78 / ...`; "
              "the preceding real instruction is `reti` at 0xFB1AB3",
    0xF8C0A4: "prom_a DATA BLOCK -- 0xF8C09B does `ld XIY,0x00f8c0a4` then calr 0xF8C16D, "
              "i.e. the address is loaded as a pointer to data, not executed",
}


def check(ok, label, detail=''):
    print(('PASS  ' if ok else 'FAIL  ') + label + (('  -- ' + detail) if detail else ''))
    if not ok:
        fails.append(label)


def note(label, detail=''):
    print('NOTE  ' + label + (('  -- ' + detail) if detail else ''))


def raw(tag):
    fn, base = IMAGES[tag]
    return open(ROMS + fn, 'rb').read(), base


def disasm(tag):
    """Linear sweep with MAME's own disassembler; returns [(addr, text)]."""
    fn, base = IMAGES[tag]
    out = subprocess.run([UNIDASM, ROMS + fn, '-arch', 'tlcs900',
                          '-basepc', '%x' % base],
                         capture_output=True, text=True).stdout
    res = []
    for line in out.splitlines():
        m = LINE.match(line)
        if m:
            res.append((int(m.group(1), 16), m.group(3)))
    return res


print('=' * 74)
print('1. the strap routine itself')
print('=' * 74)
d, base = raw('a')
want = bytes.fromhex('2101' 'f01fc8' '6e02' '2102' 'f0c441' '0e')
got = d[0xF82882 - base:0xF82882 - base + len(want)]
check(got == want, 'bytes at 0xF82882 == ld A,1 / bit 0,(PB) / jr NZ / ld A,2 / ld (0xC4),A / ret',
      got.hex())
# the routine is called once, by a calr from the boot sequence
import struct
callers = [base + i for i in range(len(d) - 3)
           if d[i] == 0x1e and base + i + 3 + struct.unpack('<h', d[i + 1:i + 3])[0] == 0xF82882]
check(callers == [0xF827D8], 'called by exactly one calr, from the boot sequence',
      ' '.join('%06X' % c for c in callers))

print()
print('=' * 74)
print('2/3. the direction registers are written ONCE (the report never checked)')
print('=' * 74)
da = disasm('a')
db_ = disasm('b')
for sfr, name, expect in ((0x2e, 'PBCR', 0x0c), (0x16, 'P7CR', 0x33)):
    sites = [(a, t) for a, t in da + db_
             if re.match(r'^(ld \(0x%02x\),0x[0-9a-f]{2}$|res |set |and \(0x%02x\)|or \(0x%02x\))'
                         % (sfr, sfr, sfr), t)]
    sites = [(a, t) for a, t in sites if ('(0x%02x)' % sfr) in t]
    for a, t in sites:
        if a in DATA_FP:
            note('discarding %06X %s' % (a, t), DATA_FP[a])
    sites = [(a, t) for a, t in sites if a not in DATA_FP]
    check(len(sites) == 1 and ('0x%02x' % expect) in sites[0][1],
          '%s written exactly once, value 0x%02X' % (name, expect),
          '; '.join('%06X %s' % s for s in sites))

print()
print('=' * 74)
print('4/5. producers and consumers of (0x0000C4)')
print('=' * 74)
prod = [(a, t) for a, t in da + db_ if '(0xc4)' in t and not t.startswith('cp ')]
note('raw non-cp hits on (0xC4): %d, of which %d are adjudicated data'
     % (len(prod), sum(1 for a, _ in prod if a in DATA_FP)))
prod = [(a, t) for a, t in prod if a not in DATA_FP]
check(len(prod) == 1 and prod[0][0] == 0xF8288B,
      'exactly one producer of (0xC4) in prom_a+prom_b',
      '; '.join('%06X %s' % s for s in prod))
tests_a = [a for a, t in da if t.startswith('cp (0xc4),')]
tests_b = [a for a, t in db_ if t.startswith('cp (0xc4),')]
# the two prom_a sites the linear sweep desyncs past, both real: they are entries
# in the dispatch table at 0xF8C2AE (pointers at 0xF8C2BA and 0xF8C2C6).
tests_a = sorted(set(tests_a) | {0xF8C4D8, 0xF8C707})
note('prom_a (0xC4) test sites: %d' % len(tests_a))
note('prom_b (0xC4) test sites: %d' % len(tests_b),
     ' '.join('%06X' % a for a in tests_b) + '  (thunk-reached: T_F4400C, T_F409C8)')
check(len(tests_a) == 109, 'prom_a test count is the reported 109')
check(len(tests_b) == 2,
      'prom_b adds 2 MORE real test sites -- the report says the extent is 109, it is 111')
imm = collections.Counter(t.split(',')[1] for a, t in da + db_ if t.startswith('cp (0xc4),'))
check(set(imm) == {'0x01', '0x02'}, 'the byte is only ever compared with 1 or 2', str(dict(imm)))
lo, hi = min(tests_a), max(tests_a)
note('prom_a extent 0xF8288B..%06X = %.1f%% of 512 KiB'
     % (hi, 100.0 * (hi - 0xF8288B) / 0x80000))
check(not [a for a in tests_a if 0xF8E000 <= a <= 0xF8FFFF],
      'no (0xC4) test anywhere in the link block 0xF8E000-0xF8FFFF')

print()
print('=' * 74)
print('6. P7 bit 1 -- the report says it is restored in FOUR places')
print('=' * 74)
setp7 = [a for a, t in da if t == 'set 1,(0x13)']
resp7 = [a for a, t in da if t == 'res 1,(0x13)']
note('res 1,(P7): ' + ' '.join('%06X' % a for a in resp7))
note('set 1,(P7): ' + ' '.join('%06X' % a for a in setp7))
check(sorted(setp7) == [0xF8E258, 0xF8E5A8, 0xF8E5D6, 0xF8E5EB, 0xF8E663, 0xF8E68C],
      'there are SIX restore sites, not four')
# 0xF8E258 and 0xF8E68C are the expiry arms of deadline loops on the 488 Hz tick
for site, loop, ticks in ((0xF8E258, 0xF8E23C, 0x09C4), (0xF8E68C, 0xF8E671, 0x01F4)):
    body = dict(da)
    ok = any(t == 'cp BC,0x%04x' % ticks for a, t in da if loop <= a < site)
    check(ok, '0x%06X is the expiry arm of a %d-tick (%.2f s) deadline loop'
          % (site, ticks, ticks / 488.28), 'so "neither a timeout" is refuted')

print()
print('=' * 74)
print('7. is the (0xC4) shape unique in the 8-bit direct page of CPU 1?')
print('=' * 74)
T = collections.Counter(); W = collections.Counter()
for a, t in da + db_:
    for h in re.findall(r'\(0x([0-9a-f]{2})\)', t):
        n = int(h, 16)
        if n < 0x80:
            continue
        if a in DATA_FP:
            continue
        if t.startswith(('cp ', 'bit')):
            T[n] += 1
        elif t.startswith(('ld (', 'res', 'set', 'inc', 'dec', 'and (', 'or (', 'xor (', 'chg')):
            W[n] += 1
for n, c in T.most_common(5):
    note('0x%02X  tests=%d producers=%d' % (n, c, W[n]))
# the discriminator is not the test count -- (0xC6) has more.  It is the ratio:
# one producer against a hundred consumers.
rivals = [n for n, c in T.items() if c >= 20 and W[n] <= 1 and n != 0xC4]
check(not rivals and T[0xC4] >= 100 and W[0xC4] == 1,
      'no other direct-page byte on CPU 1 has >=20 tests and <=1 producer',
      'rivals=%s ; (0xC4) tests=%d producers=%d' % (rivals, T[0xC4], W[0xC4]))

print()
print('=' * 74)
print('FAILURES: %d' % len(fails))
for f in fails:
    print('  - ' + f)
sys.exit(1 if fails else 0)

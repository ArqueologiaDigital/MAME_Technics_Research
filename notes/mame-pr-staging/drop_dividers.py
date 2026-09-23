"""Drop the header's section dividers; keep the three that carry an address.

QUESTION IT ANSWERS
  "mn10300.h is still at 21.5% comment lines. What is left, and is any of it
   avoidable?"

  Fifteen of the fifty-five are `// ---- section ----` dividers. Measured across
  five comparable upstream CPU headers -- mn10200.h, m6502.h, sh4.h, upd78k0.h,
  h8.h -- the divider count is ZERO in every one. They are this file's own habit,
  not a MAME convention, so removing them is justified by the null rather than by
  taste. A blank line separates a section just as well.

  The three that name a peripheral's base address keep that information, as a
  plain comment without the rule.

RUN   python3 drop_dividers.py       (from the PR worktree root)
PASS  prints the new density; the file must still compile.
"""
import re

P = 'src/devices/cpu/mn10300/mn10300.h'

KEEP = {
    '// ---- on-chip interrupt controller (INTC) @ 0x34000100 ------------------':
        '// On-chip interrupt controller (INTC) @ 0x34000100.',
    '// ---- on-chip serial (SIO): three channels @ 0x34000800/0x810/0x820 -----':
        '// On-chip serial (SIO): three channels @ 0x34000800/0x810/0x820.',
    '// ---- on-chip 16-bit timers @ 0x34001080 (TM4/TM5 pair) -----------------':
        '// On-chip 16-bit timers @ 0x34001080 (TM4/TM5 pair).',
}

lines = open(P, encoding='utf-8').read().split('\n')
out, kept, dropped = [], 0, 0
for l in lines:
    s = l.strip()
    if re.match(r'^//\s*-{3,}', s):
        if s in KEEP:
            out.append(l[:len(l) - len(l.lstrip())] + KEEP[s]); kept += 1
        else:
            dropped += 1
        continue
    out.append(l)
open(P, 'w').write('\n'.join(out))
n = sum(1 for l in out if l.lstrip().startswith(('//', '/*', '*')))
print('kept %d informative, dropped %d bare' % (kept, dropped))
print('mn10300.h %d/%d = %.1f%%' % (n, len(out), 100.0 * n / len(out)))

#!/usr/bin/env python3
"""Find comments that were cut off mid-sentence.

QUESTION IT ANSWERS
  "Did trimming the comments leave any of them hanging?"

  Reducing a file's comment density by keeping the first line or two of each
  block is mechanical and fast, and it silently produces things like

      // The CPU host-boots the SHARC through an index register at 0x98000000 and a
      uint16_t dsp_data_r(offs_t offset, uint16_t mem_mask);

  which reads as carelessness to anybody reviewing the diff.  The compiler
  cannot see it and neither can a density measurement -- the file is within
  budget and every line is still valid C++.

HOW IT DECIDES
  A single-line comment (one whose next line is NOT another comment, i.e.
  the last line of its block) is suspect when it ends in a way no finished
  sentence does:
    * a function word -- "and", "the", "to", "which", "per", ...
    * an open bracket, a comma, a dash, an arrow, a colon, an operator

  Section rules like `// --- Program flash ----` are exempt.

  It is a HEURISTIC and it is tuned to over-report rather than under-report:
  a trailing "the" is nearly always a truncation, but a comment may legitimately
  end in a colon when the code below is the list.  Read each hit; do not
  sed the output.

RUN
  python3 tools/check_truncated_comments.py FILE [FILE...]
  python3 tools/check_truncated_comments.py src/mame/matsushita/*.cpp

PASS CRITERION
  No output.  Exits 1 when anything is reported, so it can gate a commit.
"""
import re
import sys

# Words no finished sentence ends on.
FUNCTION_WORDS = set("""
the a an and or but is are was were to of in on at with that which for from its
his their this these those by as it we they he she not no so if when where while
than then per plus via into onto over under about after before during since until
unless because each both either neither only also just still yet even more most
less least very much many few several all any some such same other another into
""".split())

# A trailing ':' is NOT here: MAME comments routinely end with one to introduce
# the code below. Including it made this fire on merged upstream files, which is
# the null that says a rule is too loose.
TRAILING = (',', '--', '(', '->', '&&', '||')


def is_rule(body):
    """A section divider, not a sentence.

    Both the bare `// ----------` and the titled `// --- Work RAM ------`,
    whose trailing dashes are decoration rather than a dangling clause.
    """
    if not body:
        return False
    if set(body) <= set('-=*_ /'):
        return True
    return bool(re.search(r'[-=*_]{3,}\s*$', body))


def check(path):
    lines = open(path, encoding='utf-8', errors='replace').read().split('\n')
    hits = []
    for i, l in enumerate(lines):
        s = l.strip()
        if not s.startswith('//'):
            continue
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ''
        if nxt.startswith('//'):
            continue                       # not the last line of its block
        body = s[2:].strip()
        if not body or is_rule(body):
            continue
        words = body.split()
        if not words:
            continue
        # A finished sentence is finished, whatever its last word happens to be.
        if body.rstrip().endswith(('.', '!', '?', '.)', ':')):
            continue
        last = words[-1].lower().strip('.,;:')
        if last in FUNCTION_WORDS or body.endswith(TRAILING):
            hits.append((i + 1, s, nxt))
    return hits


def main():
    if len(sys.argv) < 2:
        sys.exit('usage: check_truncated_comments.py FILE [FILE...]')
    total = 0
    for path in sys.argv[1:]:
        for ln, comment, nxt in check(path):
            total += 1
            print('%s:%d: %s' % (path, ln, comment))
            print('    NEXT: %s' % nxt[:100])
    if total:
        print('\n%d comment(s) look truncated.' % total)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())

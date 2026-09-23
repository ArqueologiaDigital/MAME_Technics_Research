#!/usr/bin/env python3
"""Replay this session's comment/style polish onto one kn7000.cpp.

QUESTION IT ANSWERS
  "The driver is split across five commits; how do I apply the same cleanup to
   each of the five versions of kn7000.cpp without hand-editing five files?"

  The polish is a list of (old, new) text replacements, harvested straight out
  of the scripts that performed it -- centralise_fw.py, inline_edits.py,
  final_polish.py, complete_hanging_comments.py -- rather than retyped, so the
  replay cannot drift from what was actually done.

  On an EARLIER commit the file does not yet contain the later features, so
  replacements belonging to those features legitimately find nothing. This
  script therefore applies each pair OPTIONALLY and prints how many fired.

POSITIVE CONTROL (why the counts are printed)
  Run with --selftest: it takes the file as of the LAST commit of the stack and
  applies every pair. All pairs must fire, and the result must be byte-identical
  to the polished working-tree file. If that fails, the harvest is incomplete and
  no other layer can be trusted either.

RUN
  python3 replay_polish.py --selftest <head_version.cpp> <polished.cpp>
  python3 replay_polish.py <file_to_polish.cpp>
"""
import os
import sys

STAGING = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = ['centralise_fw.py', 'centralise_fw_tail.py', 'inline_edits.py', 'final_polish.py',
           'complete_hanging_comments.py', 'review_fixes.py',
           'review_fixes_2.py', 'restore_upstream_docs.py',
           'driver_dsp_sram.py', 'dsp_clock_60mhz.py',
           'last_defects.py', 'header_trim.py',
           'drop_firmware_addresses.py',
           'sharc_sram_extent.py', 'fix_memory_window.py',
           'sharc_mvmu_and_naming.py', 'fix_includes.py', 'split_mn103002a.py',
           'relocate_peripheral_docs.py', 'mn10300_ivar.py',
           'tg_voice_record_comment.py', 'trim_internal_map_comment.py']
TARGET = 'src/mame/matsushita/kn7000.cpp'


class _Stub:
    """Stands in for a file so a harvested script runs past its own I/O."""
    def read(self):
        return ''
    def write(self, _):
        return None


def _stub_open(*a, **k):
    return _Stub()


TRANSFORMS = []


def harvest():
    """Execute each polish script with edit()/cut() stubbed out, collecting the
    replacements it would make to kn7000.cpp, in order."""
    pairs = []

    def edit(path, ps):
        if path == TARGET:
            pairs.extend(ps)

    def edit_all(path, ps):
        if path == TARGET:
            pairs.extend(ps)          # 3-tuples; apply_pairs replaces them all

    def cut(old, new=''):
        pairs.append((old, new))

    import ast
    for name in SCRIPTS:
        mark = len(pairs)
        src = open(os.path.join(STAGING, name), encoding='utf-8').read()
        tree = ast.parse(src, name)
        # Drop each script's OWN edit/cut/shift definitions so the stubs above
        # are what its calls reach; keep everything else, including the `global
        # s` bookkeeping centralise_fw.py does around cut().
        tree.body = [n for n in tree.body
                     if not (isinstance(n, ast.FunctionDef)
                             and n.name in ('edit', 'edit_all', 'cut', 'shift'))]
        g = {'__name__': '__harvest__', 're': __import__('re'), 's': '',
             'edit': edit, 'edit_all': edit_all, 'cut': cut, 'print': lambda *a, **k: None,
             'open': _stub_open}
        try:
            exec(compile(tree, name, 'exec'), g)
        except (IOError, SystemExit):
            pass          # the script tried to write, or guarded its raw-I/O
                          # section against the harvest; we only wanted its pairs
        # centralise_fw.py applies one group through a plain loop over CLEAN
        # rather than through cut(), so pick that list up directly.
        for pair in g.get('CLEAN', []):
            pairs.append(pair)
        # A script may declare GUARD: its pairs then apply only to a file that
        # already contains that marker. Without it, a helper defined for a later
        # commit lands in an earlier one that has no caller for it, which is a
        # -Werror=unused-function build failure on every commit in between.
        if callable(g.get('TRANSFORM')):
            TRANSFORMS.append(g['TRANSFORM'])
        if g.get('GUARD'):
            for i in range(mark, len(pairs)):
                pairs[i] = ('__guard__', g['GUARD']) + tuple(pairs[i])
    return pairs


def shift(text, n):
    out = []
    for line in text.split('\n'):
        if n < 0:
            out.append(line[min(-n, len(line) - len(line.lstrip('\t'))):])
        else:
            out.append(('\t' * n + line) if line.strip() else line)
    return '\n'.join(out)


def apply_pairs(s, pairs):
    fired = 0
    missed = []
    for pair in pairs:
        if pair[0] == '__guard__':
            if pair[1] not in s:
                continue                  # this file has no caller; skip the pair
            pair = pair[2:]
        if len(pair) == 3:
            old, new, want = pair
            got = s.count(old)
            if got:
                s = s.replace(old, new)
                fired += 1
            else:
                missed.append(old)
            continue
        old, new = pair
        for d in (0, -1, 1, -2, 2):
            cand = shift(old, d)
            if cand in s:
                s = s.replace(cand, shift(new, d), 1)
                fired += 1
                break
        else:
            missed.append(old)
    for t in TRANSFORMS:
        s = t(s)
    return s, fired, missed


def main():
    pairs = harvest()
    if sys.argv[1] == '--selftest':
        head, polished = sys.argv[2], sys.argv[3]
        s, fired, missed = apply_pairs(open(head, encoding='utf-8').read(), pairs)
        want = open(polished, encoding='utf-8').read()
        print('pairs harvested: %d   fired: %d   missed: %d' % (len(pairs), fired, len(missed)))
        for m in missed:
            print('  MISSED: %r' % m.strip()[:88])
        if s == want:
            print('SELFTEST PASS: replay reproduces the polished file byte-for-byte')
            return 0
        print('SELFTEST FAIL: replay differs from the polished file')
        import difflib
        d = list(difflib.unified_diff(want.split('\n'), s.split('\n'),
                                      'polished', 'replayed', lineterm='', n=1))
        print('\n'.join(d[:80]))
        return 1
    path = sys.argv[1]
    s, fired, missed = apply_pairs(open(path, encoding='utf-8').read(), pairs)
    open(path, 'w').write(s)
    print('%s: %d/%d pairs applied' % (path, fired, len(pairs)))
    return 0


if __name__ == '__main__':
    sys.exit(main())

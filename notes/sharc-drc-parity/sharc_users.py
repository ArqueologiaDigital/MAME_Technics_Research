#!/usr/bin/env python3
"""Which MAME machines execute code that a given branch MODIFIES in the SHARC core?

WHY
  The Technics KN7000 submission modifies exactly one piece of shared code: the
  SHARC 2106x core (sharc.cpp/.h, sharcdrc.cpp, sharcfe.cpp/.h, sharcops.hxx).
  Everything else it touches is new files nothing else references. So the blast
  radius is "every machine with an ADSP2106x", and the useful split is by whether
  that machine runs the RECOMPILER, since most of the changes are recompiler-side.

⚠ CORRECTED 2026-09-24. The first version of this script attributed every machine in
a FILE that instantiates a SHARC to the SHARC. That is wrong for src/mame/sega/model2.cpp,
which holds four board generations: only **Model 2B** has an ADSP21062 (one
`ADSP21062(config, ...)` call, model2.cpp:2840, in a model2b_state config). Model 2O and
2A use a Fujitsu TGP and Model 2C a TGPx4. 55 of that file's 90 machines have no SHARC at
all, and the old totals counted every one of them.
  Caught by measurement, not by re-reading: alusat_probe.lua reported "NO DEVICE EXPOSES
MODE1" on daytona, motoraid, vcop, vcop2 and vf2 -- which is exactly why the probe says
that instead of printing nothing.
  A machine is now counted only if its machine_config instantiates ADSP21062, closed
transitively, the same way the recompiler set is closed.

METHOD, and the three traps it exists to avoid
  1. An in-class DECLARATION (`void foo(machine_config &) ATTR_COLD;`) looks like
     a definition to a naive regex; brace-matching from it then captures the NEXT
     function's body and mis-attributes everything. Only `Type::name(` counts.
  2. `//m_dsp[0]->enable_recompiler();` is commented out in hornet.cpp:1622.
     Comments are stripped before searching.
  3. A config that calls another config INHERITS its recompiler setting, so the
     set has to be closed transitively.

RUN   python3 sharc_users.py <mame-worktree> [git-ref] [--roster]
      --roster additionally prints one TSV line per PARENT set (the only sets you
      can actually acquire and launch): file, engine, set, status, year,
      manufacturer, title.
PASS  every machine line parses; the DRC config set matches the stripped call
      sites; totals are printed so a miscount is visible.
"""
import re, subprocess, sys, collections

ARGV = [a for a in sys.argv[1:] if not a.startswith('--')]
ROSTER = '--roster' in sys.argv
ROOT = ARGV[0] if len(ARGV) > 0 else '.'
REF = ARGV[1] if len(ARGV) > 1 else 'upstream/master'
FILES = ['src/mame/konami/gticlub.cpp', 'src/mame/konami/hornet.cpp',
         'src/mame/konami/nwk-tr.cpp', 'src/mame/konami/zr107.cpp',
         'src/mame/sega/model2.cpp']

def show(p):
    return subprocess.run(['git', '-C', ROOT, 'show', f'{REF}:{p}'],
                          capture_output=True, text=True).stdout

def strip_comments(s):
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    return re.sub(r'//[^\n]*', '', s)

GAME = re.compile(
    r'^\s*(?:GAMEL|GAME|SYST|CONS|COMP)\s*\(\s*[^,]+,\s*(\w+)\s*,\s*(\w+)\s*,\s*(\w+)\s*,([^\n]*)', re.M)
# definitions only: Type::name(machine_config
DEF = re.compile(r'^\s*(?:void|static\s+void)\s+\w+::(\w+)\s*\(\s*machine_config\s*&', re.M)

def macro_text(src, start):
    i = src.find('(', start)
    depth, j = 0, i
    while j < len(src):
        if src[j] == '(': depth += 1
        elif src[j] == ')':
            depth -= 1
            if depth == 0: return src[i:j]
        j += 1
    return src[i:]

grand = collections.Counter()
roster = []
for path in FILES:
    src = show(path)
    if not src:
        print(f'!! could not read {path}'); continue
    clean = strip_comments(src)

    bodies = {}
    for m in DEF.finditer(clean):
        i = clean.find('{', m.end())
        if i < 0: continue
        depth, j = 0, i
        while j < len(clean):
            if clean[j] == '{': depth += 1
            elif clean[j] == '}':
                depth -= 1
                if depth == 0: break
            j += 1
        bodies[m.group(1)] = clean[i:j]

    def close(seed):
        cur = set(seed)
        while True:
            add = {n for n, b in bodies.items() if n not in cur
                   and any(re.search(r'\b%s\s*\(\s*config\s*\)' % o, b) for o in cur)}
            if not add: return cur
            cur |= add

    direct = {n for n, b in bodies.items() if 'enable_recompiler()' in b}
    drc = close(direct)

    # A machine has a SHARC only if its config instantiates one. In model2.cpp that is
    # a small minority of the file.
    sharc_direct = {n for n, b in bodies.items() if 'ADSP21062(' in b or 'ADSP21065L(' in b}
    sharc = close(sharc_direct)

    # cross-check: number of stripped call sites must equal len(direct)
    sites = len(re.findall(r'enable_recompiler\(\)', clean))
    rows = []
    meta = {}
    for m in GAME.finditer(src):
        text = macro_text(src, m.start())
        quoted = re.findall(r'"((?:[^"\\]|\\.)*)"', text)
        year = re.match(r'\(\s*([^,]+?)\s*,', text)
        meta[m.group(1)] = (year.group(1) if year else '?',
                            quoted[-2] if len(quoted) >= 2 else '?',
                            quoted[-1] if len(quoted) >= 1 else '?')
        rows.append((m.group(1), m.group(2), m.group(3),
                     'NOT_WORKING' not in text))
    by = collections.defaultdict(list)
    skipped = 0
    for name, parent, cfg, works in rows:
        if cfg not in sharc:
            skipped += 1
            continue
        by['DRC' if cfg in drc else 'INTERP'].append((name, parent, cfg, works))
    grand['no_sharc'] += skipped

    print('== %s   %d machines   %d enable_recompiler() call site(s) in %d config(s)'
          % (path, len(rows), sites, len(direct)))
    print('   %d of %d machines have a SHARC (%d configs instantiate one)'
          % (len(rows) - skipped, len(rows), len(sharc)))
    print('   direct: %s' % (sorted(direct) or 'none'))
    if drc - direct:
        print('   inherited: %s' % sorted(drc - direct))
    for grp in ('DRC', 'INTERP'):
        lst = by.get(grp, [])
        if not lst: continue
        ok = sorted({n for n, p, c, w in lst if p == '0' and w})
        bad = sorted({n for n, p, c, w in lst if p == '0' and not w})
        clones = sorted({n for n, p, c, w in lst if p != '0'})
        for n in ok + bad:
            y, co, title = meta.get(n, ('?', '?', '?'))
            roster.append((path.split('/')[-1], grp, n,
                           'WORKING' if n in ok else 'NOT_WORKING', y, co, title))
        grand[grp] += len(lst); grand[grp + '_parents'] += len(ok) + len(bad)
        grand[grp + '_working'] += len(ok)
        print('   %-6s %3d machines (%d parent, %d clone)' % (grp, len(lst), len(ok) + len(bad), len(clones)))
        if ok:
            print('          WORKING parent sets : %s' % ' '.join(ok))
        if bad:
            print('          NOT_WORKING parents : %s' % ' '.join(bad))
    print()

print('TOTAL  DRC %d machines / %d parent sets (%d working)   INTERP %d machines / %d parent sets (%d working)'
      % (grand['DRC'], grand['DRC_parents'], grand['DRC_working'],
         grand['INTERP'], grand['INTERP_parents'], grand['INTERP_working']))
print('       %d machines in these files have NO SHARC and are excluded' % grand['no_sharc'])

if ROSTER:
    print()
    print('-- parent-set roster (file, engine, set, status, year, manufacturer, title)')
    for r in sorted(roster, key=lambda r: (r[1], r[3] != 'WORKING', r[2])):
        print('\t'.join(r))
    print('-- %d parent sets' % len(roster))

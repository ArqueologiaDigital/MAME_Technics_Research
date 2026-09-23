#!/usr/bin/env python3
"""Which MAME machines execute code that a given branch MODIFIES in the SHARC core?

WHY
  The Technics KN7000 submission modifies exactly one piece of shared code: the
  SHARC 2106x core (sharc.cpp/.h, sharcdrc.cpp, sharcfe.cpp/.h, sharcops.hxx).
  Everything else it touches is new files nothing else references. So the blast
  radius is "every machine with an ADSP2106x", and the useful split is by whether
  that machine runs the RECOMPILER, since most of the changes are recompiler-side.

METHOD, and the three traps it exists to avoid
  1. An in-class DECLARATION (`void foo(machine_config &) ATTR_COLD;`) looks like
     a definition to a naive regex; brace-matching from it then captures the NEXT
     function's body and mis-attributes everything. Only `Type::name(` counts.
  2. `//m_dsp[0]->enable_recompiler();` is commented out in hornet.cpp:1622.
     Comments are stripped before searching.
  3. A config that calls another config INHERITS its recompiler setting, so the
     set has to be closed transitively.

RUN   python3 sharc_users.py <mame-worktree> [git-ref]
PASS  every machine line parses; the DRC config set matches the stripped call
      sites; totals are printed so a miscount is visible.
"""
import re, subprocess, sys, collections

ROOT = sys.argv[1] if len(sys.argv) > 1 else '.'
REF = sys.argv[2] if len(sys.argv) > 2 else 'upstream/master'
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

grand = collections.Counter()
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

    direct = {n for n, b in bodies.items() if 'enable_recompiler()' in b}
    drc = set(direct)
    while True:
        add = {n for n, b in bodies.items() if n not in drc
               and any(re.search(r'\b%s\s*\(\s*config\s*\)' % o, b) for o in drc)}
        if not add: break
        drc |= add

    # cross-check: number of stripped call sites must equal len(direct)
    sites = len(re.findall(r'enable_recompiler\(\)', clean))
    rows = [(m.group(1), m.group(2), m.group(3),
              'NOT_WORKING' not in m.group(4)) for m in GAME.finditer(src)]
    by = collections.defaultdict(list)
    for name, parent, cfg, works in rows:
        by['DRC' if cfg in drc else 'INTERP'].append((name, parent, cfg, works))

    print('== %s   %d machines   %d enable_recompiler() call site(s) in %d config(s)'
          % (path, len(rows), sites, len(direct)))
    print('   direct: %s' % (sorted(direct) or 'none'))
    if drc - direct:
        print('   inherited: %s' % sorted(drc - direct))
    for grp in ('DRC', 'INTERP'):
        lst = by.get(grp, [])
        if not lst: continue
        ok = sorted({n for n, p, c, w in lst if p == '0' and w})
        bad = sorted({n for n, p, c, w in lst if p == '0' and not w})
        clones = sorted({n for n, p, c, w in lst if p != '0'})
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

#!/usr/bin/env python3
"""How much real code do the Technics control-panel devices share?

QUESTION IT ANSWERS
    "Could wsa1_cpanel be a specialization of a generic technics_cpanel base, the way
    kn6000_cpanel and kn7000_cpanel already specialize kn_cpanel_base_device?"

    Architectural similarity is easy to assert and easy to be wrong about: every one of these
    devices is "a panel MCU scanning a matrix and answering a main CPU over a serial link", and
    that sentence is true of panels that share no code at all.  So this measures three things
    that a shared base class would actually have to capture:

      1. TEXT overlap of the implementation with comments and strings stripped -- the crude
         upper bound on what could be lifted;
      2. shared METHOD names, which is where a common protocol would show;
      3. the PROTOCOL CONSTANTS each one is built on -- frame length, attention mechanism,
         serial peripheral.  Two devices can score high on (1) and (2) and still be
         unfactorable if (3) differs, because the base would have to be parameterized on
         everything that matters.

USAGE
    notes/cpanel-overlap/measure_overlap.py [src-dir]
    src-dir defaults to src/mame/matsushita/

RESULT (2026-09-20, overlay tree)  -- see README.md beside this file for the reading.
"""
import difflib, pathlib, re, sys, itertools

SRC = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else 'src/mame/matsushita')
NAMES = ['kn_cpanel', 'kn5000_cpanel', 'kn6000_cpanel', 'kn7000_cpanel', 'wsa1_cpanel']

def strip(s):
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    s = re.sub(r'//[^\n]*', '', s)
    s = re.sub(r'"(?:[^"\\\n]|\\.)*"', '""', s)
    return [l.strip() for l in s.splitlines() if l.strip()]

def methods(s):
    """Out-of-line definitions only: <class>_device::<name>(.

    An earlier version also matched in-class declarations with a general
    "type name(" pattern, which captured `if`, `switch`, `return` and every
    macro invocation and made the overlap look several times larger than it is.
    If a count here looks generous, check what it counted.
    """
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    s = re.sub(r'//[^\n]*', '', s)
    return set(re.findall(r'\b\w+_device::(\w+)\s*\(', s))

code = {}
for n in NAMES:
    p = SRC / (n + '.cpp')
    code[n] = strip(p.read_text()) if p.exists() else []

print("=== 1. text overlap, comments and string bodies stripped (difflib ratio) ===")
print("    %-16s %s" % ('', '  '.join('%-14s' % n for n in NAMES)))
for a in NAMES:
    row = []
    for b in NAMES:
        r = 1.0 if a == b else difflib.SequenceMatcher(None, code[a], code[b]).ratio()
        row.append('%-14s' % ('%5.1f%%' % (100 * r)))
    print("    %-16s %s" % (a, '  '.join(row)))

print("\n=== 2. method names in common with wsa1_cpanel ===")
wm = methods((SRC / 'wsa1_cpanel.cpp').read_text())
print("    wsa1_cpanel defines %d: %s" % (len(wm), ', '.join(sorted(wm))))
for n in NAMES:
    if n == 'wsa1_cpanel':
        continue
    p = SRC / (n + '.cpp')
    if not p.exists():
        continue
    om = methods(p.read_text())
    common = sorted(wm & om)
    print("    %-16s %2d shared: %s" % (n, len(common), ', '.join(common) or '-'))

print("\n=== 3. protocol constants each device is built on ===")
PROBES = [('serial peripheral', r'\bSC1\b|\bSIO\b|sio\d|serial channel \d|channel 1'),
          ('attention line',    r'\bINT6\b|group 0x1A|\batn\b'),
          ('frame length rule', r'0x2A81|7-byte|seven byte|frame\[|m_len'),
          ('LED frame',         r'led_frame|panel_led_frame'),
          ('normSeg space',     r'normSeg|norm_seg|port_seg|seg_wire_addr')]
for n in NAMES:
    p = SRC / (n + '.cpp')
    if not p.exists():
        continue
    s = p.read_text()
    hits = [label for label, rx in PROBES if re.search(rx, s, re.I)]
    print("    %-16s %s" % (n, ', '.join(hits) or '-'))

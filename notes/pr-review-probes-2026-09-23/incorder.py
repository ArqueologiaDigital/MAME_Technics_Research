#!/usr/bin/env python3
"""Measure adherence to MAME's documented include-group order in src/mame drivers.

Question answered: of the src/mame driver .cpp files that include emu.h and at
least one src/devices header and one local header, how many put the local
headers BEFORE the src/devices headers (the documented order), and how many put
them after?  Also reports fully-monotonic group ordering.

Usage: python3 incorder.py <mame-root> [file ...]
Rank per docs/source/contributing/cxx.rst "Structural organization".
"""
import os, re, sys

root = sys.argv[1]
INC = re.compile(r'^\s*#\s*include\s+([<"])([^">]+)[>"]')
DEVDIRS = ('bus/','cpu/','imagedev/','machine/','sound/','video/')

def rank(name, angle, srcdir):
    if name == 'emu.h': return 0
    if angle: return 7
    if name.endswith('.lh'): return 10
    if name in ('logmacro.h',): return 11
    if name.startswith(DEVDIRS): return 2
    if name.startswith('formats/'): return 4
    if '/' not in name:
        if os.path.exists(os.path.join(srcdir, name)): return 1
        if os.path.exists(os.path.join(root,'src/emu',name)): return 3
        if os.path.exists(os.path.join(root,'src/lib/util',name)): return 5
        return 9
    return 9

files = sys.argv[2:]
if not files:
    files = []
    base = os.path.join(root,'src/mame')
    for d,_,fs in os.walk(base):
        for f in fs:
            if f.endswith('.cpp'): files.append(os.path.join(d,f))
files.sort()

tot = both = local_first = dev_first = mono = nonmono = 0
offenders = []
for p in files:
    try: txt = open(p, encoding='utf-8', errors='replace').read()
    except OSError: continue
    seq = []
    for line in txt.split('\n'):
        m = INC.match(line)
        if m: seq.append(rank(m.group(2), m.group(1)=='<', os.path.dirname(p)))
    if not seq or seq[0] != 0: continue
    tot += 1
    core = [r for r in seq if r in (1,2)]
    if 1 in core and 2 in core:
        both += 1
        if core.index(1) < core.index(2): local_first += 1
        else: dev_first += 1
    known = [r for r in seq if r != 9]
    if known == sorted(known): mono += 1
    else:
        nonmono += 1
        offenders.append(p)

print(f"src/mame .cpp files starting with emu.h            : {tot}")
print(f"  ... having BOTH local and src/devices includes   : {both}")
print(f"      local group first (documented order)         : {local_first}")
print(f"      src/devices group first                      : {dev_first}")
print(f"  group sequence fully non-decreasing              : {mono}")
print(f"  group sequence out of order                      : {nonmono}")
if len(sys.argv) > 2:
    for p in offenders: print("   OUT-OF-ORDER:", p)

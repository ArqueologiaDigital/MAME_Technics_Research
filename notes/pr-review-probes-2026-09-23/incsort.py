#!/usr/bin/env python3
"""Companion NULL: within the src/devices include group, how many src/mame
driver .cpp files sort the paths alphabetically?  Same rank() as incorder.py."""
import os, re, sys
root = sys.argv[1]
INC = re.compile(r'^\s*#\s*include\s+([<"])([^">]+)[>"]')
DEVDIRS = ('bus/','cpu/','imagedev/','machine/','sound/','video/')
files=[]
for d,_,fs in os.walk(os.path.join(root,'src/mame')):
    for f in fs:
        if f.endswith('.cpp'): files.append(os.path.join(d,f))
files.sort()
tot=srt=uns=0; bad=[]
for p in files:
    txt=open(p,encoding='utf-8',errors='replace').read()
    dev=[m.group(2) for m in (INC.match(l) for l in txt.split('\n')) if m and not m.group(1)=='<' and m.group(2).startswith(DEVDIRS)]
    if len(dev)<2: continue
    tot+=1
    if dev==sorted(dev): srt+=1
    else: uns+=1; bad.append(p)
print(f"src/mame .cpp with >=2 src/devices includes : {tot}")
print(f"  alphabetically sorted                     : {srt} ({100*srt/tot:.1f}%)")
print(f"  not sorted                                : {uns} ({100*uns/tot:.1f}%)")
print("  kn7000.cpp in the unsorted set            :", any(p.endswith('matsushita/kn7000.cpp') for p in bad))
print("  kn5000.cpp in the unsorted set            :", any(p.endswith('matsushita/kn5000.cpp') for p in bad))

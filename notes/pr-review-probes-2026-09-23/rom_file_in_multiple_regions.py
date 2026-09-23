#!/usr/bin/env python3
# Q: how often is one ROM file loaded into more than one region in a set?
#
# A (NULL over upstream/master, measured 2026-09-23): 420 sets.
#
#    This is a NULL, and it exists to stop a "defect" being filed against a
#    MAME convention. A second-pass adversarial review flagged the KN7000 ROM
#    definitions for exactly this shape -- IC16/IC17 appearing as two files in
#    two regions, an empty ROMREGION_ERASEFF table_data on kn2400. The number
#    above says the shape is ordinary upstream, so nothing was changed.
#
#    Written by a review subagent; kept because it changed what I did.
#
# RUN
#    git archive upstream/master src/mame | tar -x -C <scratch>
#    cd <scratch> && python3 rom_file_in_multiple_regions.py
#    (the root is hardcoded to "src/mame", relative to the working directory)
#
import re,os,collections
root="src/mame"
pat=re.compile(r'ROM(?:X)?_LOAD[A-Z0-9_]*\s*\(\s*"([^"]+)"')
startr=re.compile(r'ROM_START\(\s*([A-Za-z0-9_]+)')
regr=re.compile(r'\bROM_REGION[A-Z0-9_]*\s*\(\s*[^,]+,\s*"([^"]+)"')
endr=re.compile(r'ROM_END')
hits=0; ex=[]
for dp,dn,fn in os.walk(root):
    for f in fn:
        if not f.endswith(".cpp"): continue
        p=os.path.join(dp,f)
        txt=open(p,encoding="utf8",errors="replace").read().split("\n")
        cur=None;reg=None;d=None
        for i,l in enumerate(txt,1):
            m=startr.search(l)
            if m: cur=m.group(1); d=collections.defaultdict(set); reg=None; continue
            if cur is None: continue
            if endr.search(l):
                for nm,regs in d.items():
                    if len(regs)>1:
                        hits+=1; ex.append(f"{p}:{cur}: {nm} -> {sorted(regs)}")
                cur=None; continue
            mr=regr.search(l)
            if mr: reg=mr.group(1); continue
            mm=pat.search(l)
            if mm and reg: d[mm.group(1).lower()].add(reg)
print("same file loaded into >1 region in one set:",hits)
for e in ex[:12]: print("  ",e)

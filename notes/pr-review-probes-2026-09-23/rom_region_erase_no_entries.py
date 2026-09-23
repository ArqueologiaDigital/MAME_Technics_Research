#!/usr/bin/env python3
# Q: how many ROM_REGIONs carry an ERASE flag and no ROM entries at all?
#
# A (NULL over upstream/master, measured 2026-09-23): 2447 of 108045 regions (2.3%).
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
#    cd <scratch> && python3 rom_region_erase_no_entries.py
#    (the root is hardcoded to "src/mame", relative to the working directory)
#
import re,os
root="src/mame"
startr=re.compile(r'ROM_START\(')
endr=re.compile(r'ROM_END')
regr=re.compile(r'\bROM_REGION[A-Z0-9_]*\s*\(\s*([^,]+),\s*"([^"]+)"\s*,\s*([^)]*)\)')
loadr=re.compile(r'\bROM(X?)_(LOAD|COPY|FILL|IGNORE|CONTINUE|RELOAD)')
n_empty=0; n_total=0; ex=[]
for dp,dn,fn in os.walk(root):
    for f in fn:
        if not f.endswith(".cpp"): continue
        p=os.path.join(dp,f)
        txt=open(p,encoding="utf8",errors="replace").read().split("\n")
        inside=False; pend=None; pendline=0
        for i,l in enumerate(txt,1):
            if startr.search(l): inside=True; pend=None; continue
            if not inside: continue
            if endr.search(l):
                if pend: n_empty+=1; ex.append(f"{p}:{pendline}: {pend}")
                inside=False; pend=None; continue
            m=regr.search(l)
            if m:
                if pend: n_empty+=1; ex.append(f"{p}:{pendline}: {pend}")
                n_total+=1
                pend=m.group(2)+" flags="+m.group(3).strip() if "ERASE" in m.group(3) else None
                pendline=i
                continue
            if loadr.search(l):
                pend=None
print("regions with ERASE flag and NO rom entries:", n_empty, "of", n_total, "total regions")
for e in ex[:15]: print(" ", e)

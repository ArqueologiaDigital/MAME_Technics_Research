#!/usr/bin/env python3
# Q: do several ROM files share one chip's .icNN suffix inside a single set?
#
# A (NULL over upstream/master, measured 2026-09-23): 1275 sets across upstream src/mame do exactly that.
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
#    cd <scratch> && python3 rom_name_split_across_regions.py
#    (the root is hardcoded to "src/mame", relative to the working directory)
#
import re,os,sys,collections
root="src/mame"
pat=re.compile(r'ROM_(?:LOAD|LOADX|LOAD16_WORD|LOAD16_BYTE|LOAD32_WORD|LOAD32_BYTE|LOAD64_WORD|LOAD16_WORD_SWAP|LOAD32_WORD_SWAP)[A-Z0-9_]*\s*\(\s*"([^"]+)"')
start=re.compile(r'ROM_START\(\s*([A-Za-z0-9_]+)')
end=re.compile(r'ROM_END')
hits=0
for dp,dn,fn in os.walk(root):
    for f in fn:
        if not f.endswith(".cpp"): continue
        p=os.path.join(dp,f)
        try: lines=open(p,encoding="utf8",errors="replace").read().split("\n")
        except: continue
        cur=None; names=[]
        for i,l in enumerate(lines):
            m=start.search(l)
            if m: cur=m.group(1); names=[]; continue
            if cur and end.search(l):
                d=collections.defaultdict(set)
                for nm in names:
                    if "." in nm:
                        base,ext=nm.rsplit(".",1)
                        if re.fullmatch(r'(ic|u|ud|uc)\d+[a-z]?',ext):
                            d[ext].add(base)
                for ext,bases in d.items():
                    if len(bases)>1:
                        print(f"{p}:{cur}: .{ext} <- {sorted(bases)}")
                        hits+=1
                cur=None; continue
            if cur:
                mm=pat.search(l)
                if mm: names.append(mm.group(1).lower())
print("total",hits)

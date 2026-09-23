#!/usr/bin/env python3
"""Two more NULLs for the kn7000.cpp include block.

(1) Of src/mame drivers that include BOTH a layout (.lh) header and a C++
    standard-library header, how many put <stdlib> BEFORE the .lh (the order
    docs/source/contributing/cxx.rst prescribes)?
(2) How often do src/mame drivers put a trailing // comment on an #include line?
"""
import os, re, sys
root = sys.argv[1]
INC = re.compile(r'^\s*#\s*include\s+([<"])([^">]+)[>"](.*)$')
files=[]
for d,_,fs in os.walk(os.path.join(root,'src/mame')):
    for f in fs:
        if f.endswith('.cpp'): files.append(os.path.join(d,f))
files.sort()
both=std_first=lh_first=0
tot_files=0; files_with_cmt=0; tot_inc=0; cmt_inc=0
per_file_cmt={}
for p in files:
    txt=open(p,encoding='utf-8',errors='replace').read()
    seq=[]; ncmt=0; ninc=0
    for line in txt.split('\n'):
        m=INC.match(line)
        if not m: continue
        ninc+=1
        seq.append(('std' if m.group(1)=='<' else ('lh' if m.group(2).endswith('.lh') else 'other')))
        if re.match(r'\s*//', m.group(3) or ''): ncmt+=1
    if not ninc: continue
    tot_files+=1; tot_inc+=ninc; cmt_inc+=ncmt
    per_file_cmt[p]=(ncmt,ninc)
    if ncmt: files_with_cmt+=1
    if 'std' in seq and 'lh' in seq:
        both+=1
        (std_first if seq.index('std')<seq.index('lh') else lh_first)
        if seq.index('std')<seq.index('lh'): std_first+=1
        else: lh_first+=1
print(f"drivers with BOTH a <stdlib> include and a .lh include : {both}")
print(f"  <stdlib> before the .lh (documented order)           : {std_first}")
print(f"  .lh before the <stdlib>                              : {lh_first}")
print()
print(f"src/mame .cpp with >=1 #include                        : {tot_files}")
print(f"  files with any trailing // comment on an #include     : {files_with_cmt} ({100*files_with_cmt/tot_files:.1f}%)")
print(f"  total #include lines / of them commented             : {tot_inc} / {cmt_inc} ({100*cmt_inc/tot_inc:.2f}%)")
for name in ('matsushita/kn7000.cpp','matsushita/kn5000.cpp'):
    for p,(c,n) in per_file_cmt.items():
        if p.endswith(name): print(f"  {name:28s} commented {c}/{n} include lines")

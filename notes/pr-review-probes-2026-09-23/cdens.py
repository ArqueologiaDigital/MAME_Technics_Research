#!/usr/bin/env python3
"""Comment-line density for C/C++ headers.

Question answered: what fraction of a header's non-blank lines are comment-only
lines?  Reported both including and excluding the MAME license/copyright banner
(the first contiguous run of comment lines at the top of the file), because that
banner is mandatory boilerplate every file carries and inflates short files.

Usage: cdens.py FILE...        (prints TSV: total blank commentonly trailing code pct_all pct_nobanner path)
"""
import sys, re

def classify(path):
    try:
        lines = open(path, encoding='utf-8', errors='replace').read().split('\n')
    except Exception:
        return None
    if lines and lines[-1] == '':
        lines.pop()
    in_block = False
    kinds = []   # 'blank' | 'comment' | 'code' | 'code+comment'
    for ln in lines:
        s = ln.strip()
        if in_block:
            kinds.append('comment')
            if '*/' in s:
                in_block = False
                rest = s.split('*/', 1)[1].strip()
                if rest and not rest.startswith('//'):
                    kinds[-1] = 'code+comment'
            continue
        if not s:
            kinds.append('blank'); continue
        if s.startswith('//'):
            kinds.append('comment'); continue
        if s.startswith('/*'):
            if '*/' in s:
                rest = s.split('*/', 1)[1].strip()
                kinds.append('code+comment' if rest else 'comment')
            else:
                in_block = True
                kinds.append('comment')
            continue
        # code line; does it carry a trailing comment?
        has = False
        # crude string-aware scan
        i, n, instr, ch = 0, len(ln), False, ''
        while i < n:
            c = ln[i]
            if instr:
                if c == '\\': i += 2; continue
                if c == ch: instr = False
            else:
                if c in '"\'': instr = True; ch = c
                elif c == '/' and i+1 < n and ln[i+1] == '/':
                    has = True; break
                elif c == '/' and i+1 < n and ln[i+1] == '*':
                    has = True
                    if '*/' not in ln[i+2:]: in_block = True
                    break
            i += 1
        kinds.append('code+comment' if has else 'code')
    return kinds

def banner_len(kinds):
    """length of the leading comment/blank banner (license + file header)"""
    i = 0
    while i < len(kinds) and kinds[i] in ('comment', 'blank'):
        i += 1
    return i

print('\t'.join('total blank comment trailing code pct_all pct_nobanner path'.split()))
for p in sys.argv[1:]:
    k = classify(p)
    if k is None: continue
    total = len(k)
    blank = k.count('blank'); com = k.count('comment'); tr = k.count('code+comment')
    code = k.count('code')
    nb = total - blank
    pct_all = 100.0*com/nb if nb else 0
    b = banner_len(k)
    k2 = k[b:]
    nb2 = len(k2) - k2.count('blank')
    pct_nb = 100.0*k2.count('comment')/nb2 if nb2 else 0
    print(f'{total}\t{blank}\t{com}\t{tr}\t{code}\t{pct_all:.1f}\t{pct_nb:.1f}\t{p}')

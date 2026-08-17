import re,sys
src=open('/home/fsanches/compartilhado/mame-pr/src/mame/matsushita/kn7000.cpp').read()
# strip line continuations of the macro
src=src.replace('\\\n','\n')
cur=None; regions=[]
for line in src.splitlines():
    l=line.strip()
    m=re.match(r'ROM_START\((\w+)\)', l)
    if m: print(f'\n### SET {m.group(1)}')
    m=re.match(r'ROM_REGION(32_LE|16_LE|32_BE|16_BE)?\(\s*(0x[0-9a-fA-F]+)\s*,\s*"(\w+)"', l)
    if m:
        cur=(m.group(3), int(m.group(2),16), m.group(1) or '')
        print(f'  REGION {cur[0]:<18} size {cur[1]:#010x}  {cur[2]}')
        continue
    m=re.match(r'(ROMX?_LOAD(32_WORD|16_WORD|32_BYTE)?)\(\s*"([^"]+)"\s*,\s*(0x[0-9a-fA-F]+)\s*,\s*(0x[0-9a-fA-F]+)\s*,\s*(.*)', l)
    if m:
        kind, fn, off, ln, rest = m.group(1), m.group(3), int(m.group(4),16), int(m.group(5),16), m.group(6)
        nodump = 'NO_DUMP' in rest
        crc = re.search(r'CRC\((\w+)\)', rest)
        sha = re.search(r'SHA1\((\w+)\)', rest)
        # address span consumed
        if kind.endswith('32_WORD'): span = ln*2
        elif kind.endswith('16_WORD') or kind.endswith('32_BYTE'): span = ln*4
        else: span = ln
        end = off+span
        ok = end <= cur[1]
        print(f'    {kind:<16} {fn:<28} off {off:#08x} len {ln:#08x} span {span:#08x} end {end:#08x} '
              f'{"FITS" if ok else "OVERFLOW!!"} {"NO_DUMP" if nodump else (crc.group(1)+"/"+sha.group(1)[:8] if crc else "??")}')

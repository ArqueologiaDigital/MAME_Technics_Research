#!/usr/bin/env python3
# Q: is +0x40000000 a systematic address-space alias on these machines, or is
#    the 0x90000000 window a device window in its own right?
# Method: decode every MN10300 operand that carries a 32-bit ADDRESS (address-reg
#    immediate, abs32 memory operand), bucket by 1 MB page, and pair each page P
#    in 0x40000000-0x7FFFFFFF with P+0x40000000.
import re,struct,sys,collections,os
BASE=0x48400000
ADDR=[(rb'\xfc[\xdc-\xdf]',2,'mov imm32,aN'),
      (rb'\xfc[\xd8-\xdb]',2,'cmp imm32,aN'),
      (rb'\xfc[\x80-\x8f]',2,'st (abs32)'),
      (rb'\xfc[\xa0-\xaf]',2,'ld (abs32)'),
      (rb'\xfe[\x00-\x03]',3,'bset/bclr (abs32)')]
DATA=[(rb'\xfc[\xcc-\xcf]',2,'mov imm32,dN')]
def scan(img,pats):
    h=collections.defaultdict(list)
    for pat,off,kind in pats:
        for m in re.finditer(pat,img):
            i=m.start()
            if i+off+4>len(img): continue
            h[struct.unpack('<I',img[i+off:i+off+4])[0]].append((BASE+i,kind))
    return h
for f in sys.argv[1:]:
    img=open(f,'rb').read(); a=scan(img,ADDR); d=scan(img,DATA)
    print('===',os.path.basename(f))
    pages=collections.Counter()
    for v,l in a.items(): pages[v>>20]+=len(l)
    print('  1MB pages with >=2 ADDRESS-context operands, and their +0x40000000 partner:')
    print('   %-12s %6s   %-12s %6s'%('cached P','hits','uncached P+0x40M','hits'))
    for p in sorted(pages):
        if 0x400<=p<0x800 and (pages[p]>=2 or pages[p+0x400]>=2):
            print('   0x%08X %6d   0x%08X %6d'%(p<<20,pages[p],(p+0x400)<<20,pages[p+0x400]))
    print('  uncached-only pages (0x80000000+) with >=2 hits and no cached partner:')
    for p in sorted(pages):
        if p>=0x800 and pages[p]>=2 and pages[p-0x400]==0:
            print('   0x%08X %6d'%(p<<20,pages[p]))
    print('  --- 0x90000000-0x903FFFFF: every operand, by context ---')
    for v in sorted(set(list(a)+list(d))):
        if 0x90000000<=v<0x90400000:
            print('   0x%08X  ADDR x%-3d DATA x%-3d  %s'%(v,len(a.get(v,[])),len(d.get(v,[])),
                  ', '.join('0x%08X %s'%s for s in a.get(v,[])[:5])))

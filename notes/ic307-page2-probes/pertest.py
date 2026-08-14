"""Is page 2's 48% detect_period fallback a defect ON MATERIAL THAT PLAYS?

Split every IC307 page-2 chunk into REFERENCED (some zone table names it) vs
UNREFERENCED, and compare fallback rates. NULL: if the fallback rate is the same in
both halves, referencing tells us nothing and the split is not evidence.
"""
import sys, collections
sys.path.insert(0,'/home/fsanches/compartilhado/kn7000_mame/tools')
import kn5000_period_oracle as O
rom=O.load_rom()
dirs={p:O.page_dir(rom,p) for p in range(4)}
# referenced entries per page, from the exhaustive raw-ROM walk (walkB.py)
import struct
SC='/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/d0e1b1c2-9dd7-40da-b88c-9bcc60bcc85a/scratchpad/'
img=open(SC+'table_data.bin','rb').read()
BASE=0x050000
u8=lambda s: img[s-0x020000]
u16=lambda s: struct.unpack_from('<H',img,s-0x020000)[0]
u32=lambda s: struct.unpack_from('<I',img,s-0x020000)[0]
ref=collections.defaultdict(set)   # page -> entries (bank1 only)
for i in range(487):
    p=0x077914+15*i
    flags=u8(p);ptrA=u32(p+1)+BASE;ptrB=u32(p+5)+BASE;ptrC=u32(ptrA)+BASE
    stride=6 if flags&0x80 else 4
    slots=[u8(ptrC+k) for k in range(128)]
    Emap=[u8(ptrA+4+s) for s in range(max(slots)+1)]
    for E in range(max(Emap)+1):
        w=u16(ptrB+stride*E); c=(w>>12)&0xF
        if (c>>2)&1: ref[c&3].add(w&0xFFF)

print(f"{'page':>4} {'chunks':>7} {'referenced':>11} {'unrefd':>7} | {'fallback REF':>14} {'fallback UNREF':>16} {'fallback ALL':>13}")
for p in range(4):
    d=dirs[p]; R=ref[p]
    stats={'ref':[0,0],'unref':[0,0]}
    for idx,(start,n) in enumerate(d):
        per=O.detect_period(rom,start,n)
        fb = (per == (n<<16))            # the "P = N" fallback
        k='ref' if idx in R else 'unref'
        stats[k][0]+=1; stats[k][1]+=1 if fb else 0
    nr,fr=stats['ref']; nu,fu=stats['unref']
    tot=nr+nu; ft=fr+fu
    pr=f"{fr}/{nr} = {100.0*fr/nr:.1f}%" if nr else "n/a"
    pu=f"{fu}/{nu} = {100.0*fu/nu:.1f}%" if nu else "n/a"
    pt=f"{ft}/{tot} = {100.0*ft/tot:.1f}%"
    print(f"{p:>4} {tot:>7} {nr:>11} {nu:>7} | {pr:>14} {pu:>16} {pt:>13}")

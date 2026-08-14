"""Exhaustive enumeration of every wave-select (+0x040) word the SET descriptors can emit.
Independent re-derivation from the raw table_data image -- does NOT trust the TSVs."""
import struct, collections
SC='/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/d0e1b1c2-9dd7-40da-b88c-9bcc60bcc85a/scratchpad/'
img=open(SC+'table_data.bin','rb').read()
BASE=0x050000                 # rel-offset base (sub addr)
def off(sub): return sub-0x020000
def u8(sub): return img[off(sub)]
def u16(sub): return struct.unpack_from('<H',img,off(sub))[0]
def u32(sub): return struct.unpack_from('<I',img,off(sub))[0]

SETBASE=0x077914; NSETS=487; STRIDE=15
cls_hist=collections.Counter()
cls_entries=collections.defaultdict(set)
raw_cls_hist=collections.Counter()      # over the RAW ptrB arrays 0..maxE
setcls=collections.defaultdict(set)
for i in range(NSETS):
    p=SETBASE+STRIDE*i
    flags=u8(p); ptrA=u32(p+1)+BASE; ptrB=u32(p+5)+BASE; ptrC=u32(ptrA)+BASE
    stride=6 if (flags&0x80) else 4
    slots=[u8(ptrC+k) for k in range(128)]
    maxslot=max(slots)
    Emap=[u8(ptrA+4+s) for s in range(maxslot+1)]
    for key in range(128):
        E=Emap[slots[key]]
        w=u16(ptrB+stride*E)
        c=(w>>12)&0xF; e=w&0xFFF
        cls_hist[c]+=1; cls_entries[c].add(e); setcls[i].add(c)
    for E in range(max(Emap)+1):
        w=u16(ptrB+stride*E); raw_cls_hist[(w>>12)&0xF]+=1
print("=== per-class census over ALL 487 SETs x 128 keys (62336 lookups) ===")
for c in sorted(cls_hist):
    es=cls_entries[c]
    print(f"class {c}: {cls_hist[c]:6d} key-lookups  {len(es):4d} distinct entries  max 0x{max(es):03X} (=> needs {max(es)+1} slots)")
print()
print("class-6 entries actually referenced:", ' '.join(f"{e:03X}" for e in sorted(cls_entries[6])))
print()
print("=== control: does the top nibble ever exceed 7? ===", {k:v for k,v in raw_cls_hist.items() if k>7} or "NO -- class field is 0..7 only")
print("raw ptrB record scan class histogram:", dict(sorted(raw_cls_hist.items())))
print()
print("=== IC307 declared page slots vs class demand (bank1: classes 4,5,6,7 -> pages 0,1,2,3) ===")
decl={0:198,1:168,2:1072,3:57}
for c in (4,5,6,7):
    need=max(cls_entries[c])+1
    print(f"  class {c} -> page {c&3}: firmware needs {need:5d}, directory declares {decl[c&3]:5d}   {'EXACT' if need==decl[c&3] else f'MISMATCH x{decl[c&3]/need:.2f}'}")
for c in (0,1,2,3):
    print(f"  class {c} -> undumped bank0 page {c&3}: firmware needs {max(cls_entries[c])+1:5d}")

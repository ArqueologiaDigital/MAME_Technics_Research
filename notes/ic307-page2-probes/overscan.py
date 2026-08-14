"""Scan the RAW ptrB partial-record arrays past the key-map's reach.
The footage/drawbar path (WaveSel_StageB_Build_Reg040_Footage_RoutingTable, v142 asm
L16515) indexes ptrB by an E taken from a ROUTING TABLE, not from ptrA[4+ptrC[key]],
so records above max(Emap) are reachable and must be counted."""
import struct, collections
SC='/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/d0e1b1c2-9dd7-40da-b88c-9bcc60bcc85a/scratchpad/'
img=open(SC+'table_data.bin','rb').read()
BASE=0x050000
def off(s): return s-0x020000
def u8(s): return img[off(s)]
def u16(s): return struct.unpack_from('<H',img,off(s))[0]
def u32(s): return struct.unpack_from('<I',img,off(s))[0]
SETBASE=0x077914;N=487;ST=15
info={}
ptrBs=[]
for i in range(N):
    p=SETBASE+ST*i
    flags=u8(p);ptrA=u32(p+1)+BASE;ptrB=u32(p+5)+BASE;ptrC=u32(ptrA)+BASE
    stride=6 if flags&0x80 else 4
    slots=[u8(ptrC+k) for k in range(128)]
    Emap=[u8(ptrA+4+s) for s in range(max(slots)+1)]
    info[i]=(flags,stride,ptrA,ptrB,ptrC,max(Emap))
    ptrBs.append((ptrB,i))
# where does each ptrB array end? next structure start above it
bounds=sorted(set([b for b,_ in ptrBs]+[u32(SETBASE+ST*i+1)+BASE for i in range(N)]+[0x07AD9D,0x084E6F,0x08D8A3,0x08F8A3,0x08FEBD,0x0A0000]))
S6=[62,103,107,137,252,253,277,278,279,280,282,283]
print("=== class-6 SETs: raw ptrB array walked to the next structure ===")
allc6=set()
for i in S6:
    flags,stride,ptrA,ptrB,ptrC,maxE=info[i]
    nxt=min(b for b in bounds if b>ptrB)
    navail=(nxt-ptrB)//stride
    words=[u16(ptrB+stride*E) for E in range(navail)]
    cls=collections.Counter((w>>12)&0xF for w in words)
    ent6=sorted({w&0xFFF for w in words if (w>>12)&0xF==6})
    allc6|=set(ent6)
    print(f"SET {i:3d} ptrB={ptrB:06X} stride={stride} maxE(keymap)={maxE:3d} records-to-next-struct={navail:3d} (next={nxt:06X})")
    print(f"         class hist over full array: {dict(sorted(cls.items()))}")
    print(f"         class-6 entries: {' '.join('%03X'%e for e in ent6)}")
print()
print("union of class-6 entries over the FULL ptrB arrays:",len(allc6),"max 0x%03X"%max(allc6))
print("entries >= 0x097:",[hex(e) for e in sorted(allc6) if e>=0x097] or "NONE")

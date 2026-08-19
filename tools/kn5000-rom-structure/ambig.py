from collections import Counter, defaultdict
ROM="/home/fsanches/compartilhado/kn5000_original_roms/kn5000/"
ev=open(ROM+"kn5000_table_data_rom_even.ic3","rb").read()
od=open(ROM+"kn5000_table_data_rom_odd.ic1","rb").read()
n=len(ev)//2
region=bytearray(4*n)
for k in range(n):
    region[4*k+0]=ev[2*k]; region[4*k+1]=ev[2*k+1]
    region[4*k+2]=od[2*k]; region[4*k+3]=od[2*k+1]
region=bytes(region)
BASE=0x050000
def off(S): return S-0x020000
def u8(S): return region[off(S)]
def u16(S): return region[off(S)]|region[off(S)+1]<<8
def u32(S): return int.from_bytes(region[off(S):off(S)+4],'little')
def sv(v): return v-0x10000 if v>=0x8000 else v
SETB=0x077914
sel2C=defaultdict(set)          # selector -> set of C
sel2CP=defaultdict(set)         # selector -> set of (C, pan-field)
selpan=defaultdict(set)
keyweight=Counter()
for i in range(487):
    S=SETB+15*i
    flags=u8(S); ptrA=u32(S+1)+BASE; ptrB=u32(S+5)+BASE
    st=6 if (flags&0x80) else 4
    root=u8(S+11); basep=u16(S+12)
    setterm = basep - ((root<<8)+0x80)
    ptrC=u32(ptrA)+BASE
    for key in range(128):
        E=u8(ptrA+4+u8(ptrC+key))
        rec=ptrB+st*E
        sel=u16(rec)
        trim = sv(u16(rec+4)) if st==6 else 0
        C = setterm + trim
        b2=u8(rec+2)
        pan = ((b2>>4)&7) if (b2&0x80) else None
        sel2C[sel].add(C)
        sel2CP[sel].add((C,pan))
        selpan[sel].add(pan)
        keyweight[sel]+=1
amb=[s for s in sel2C if len(sel2C[s])>1]
print("selectors:", len(sel2C), " ambiguous (more than one C):", len(amb))
fixed=0; partial=0; nofix=0
for s in amb:
    # does the pan field separate the C values?  i.e. is C a function of (sel,pan)?
    m=defaultdict(set)
    for C,p in sel2CP[s]:
        m[p].add(C)
    if all(len(v)==1 for v in m.values()):
        fixed+=1
    elif max(len(v) for v in m.values()) < len(sel2C[s]):
        partial+=1
    else:
        nofix+=1
print(f"  of those, (selector,pan) makes C single-valued : {fixed}")
print(f"           (selector,pan) reduces the ambiguity  : {partial}")
print(f"           (selector,pan) does not help          : {nofix}")
print()
kw_amb=sum(keyweight[s] for s in amb)
kw_fix=sum(keyweight[s] for s in amb if all(len(v)==1 for v in (lambda m: m)( (lambda: None)() ) ) ) if False else 0
# key-weighted
kwf=0
for s in amb:
    m=defaultdict(set)
    for C,p in sel2CP[s]: m[p].add(C)
    if all(len(v)==1 for v in m.values()): kwf+=keyweight[s]
print(f"key-weight of ambiguous selectors: {kw_amb} of {sum(keyweight.values())}; resolved by pan: {kwf}")

#!/usr/bin/env python3
"""Is the head of page 2 'full-amplitude audio' (content-map §2.3) or table data?
   Plus: are page-2 chunk boundaries real edits, or slices of one continuous stream?"""
import struct, statistics, bisect, collections
ROM="/home/fsanches/compartilhado/technics_roms/roms/kn5000/kn5000_waveform_rom.ic307"
rom=open(ROM,'rb').read(); PAGE=0x100000; GRAN=16
def s16(o,c): return struct.unpack_from("<%dh"%c,rom,o)
def stats(o,nb,label):
    c=nb//2; x=s16(o,c)
    rms=(sum(v*v for v in x)/c)**.5
    sc=sum(1 for k in range(c-1) if (x[k]<0)!=(x[k+1]<0))
    hi=sum(1 for v in x if abs(v)>8000)
    print(f"  {label:38s} rms {rms:8.1f}  peak {max(abs(v) for v in x):6d}  "
          f"sign-flips/1KB {sc/(nb/1024):7.1f}  |v|>8000: {100*hi/c:5.1f}%")
print("BYTE CHARACTER (interpreted as s16le, the PCM format):")
stats(0x200000,0x10C0,"page2 DIRECTORY 0x200000+0x10C0")
stats(0x2010C0,0x2694-0x10C0,"page2 PARAM AREA 0x2010C0..0x202694")
stats(0x2026A0,0x4000,"page2 PCM just after   0x2026A0")
stats(0x000000,0x0318,"page0 DIRECTORY 0x000000+0x0318")
stats(0x000318,0x1A30-0x318,"page0 PARAM AREA")
stats(0x001A30,0x4000,"page0 PCM just after")
stats(0x280000,0x4000,"page2 PCM mid-page 0x280000")

print("\nPARAM BLOCK ENDS JUST BEFORE THE FIRST PCM BYTE (per page):")
def dirs(p):
    b=p*PAGE; n=struct.unpack_from("<H",rom,b)[0]//4
    pp=[struct.unpack_from("<H",rom,b+i*4)[0] for i in range(n)]
    wo=[struct.unpack_from("<H",rom,b+i*4+2)[0] for i in range(n)]
    return b,n,pp,wo
for p in range(4):
    b,n,pp,wo=dirs(p)
    print(f"  page {p}: dir ends 0x{n*4:04X}  last param_ptr 0x{max(pp):04X}  "
          f"first PCM 0x{min(wo)*GRAN:06X}  slack {min(wo)*GRAN-max(pp)} bytes")

print("\nARE PAGE-2 CHUNK BOUNDARIES REAL EDITS? (|x[end]-x[start_next]| vs typical |dx| inside)")
for p in (0,2,3):
    b,n,pp,wo=dirs(p)
    s=sorted(set(wo)); jumps=[]; inner=[]
    for w in s[1:200]:
        o=b+w*GRAN
        a,c=struct.unpack_from("<2h",rom,o-2)   # last sample of prev chunk, first of this
        jumps.append(abs(c-a))
        x=struct.unpack_from("<32h",rom,o)
        inner+= [abs(x[k+1]-x[k]) for k in range(31)]
    print(f"  page {p}: median |step| ACROSS a chunk boundary {statistics.median(jumps):7.0f}   "
          f"median |step| INSIDE chunks {statistics.median(inner):7.0f}   ratio "
          f"{statistics.median(jumps)/max(1,statistics.median(inner)):.2f}")

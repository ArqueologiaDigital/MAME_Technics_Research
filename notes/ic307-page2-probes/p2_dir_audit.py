#!/usr/bin/env python3
"""LINE 3 -- is IC307 page 2's 1072-entry directory real, or a false positive?

Re-implements the six acceptance checks of kn5000_tonegen.cpp::parse_page_directories()
WITHOUT short-circuiting, so every entry is graded against every check independently.
Read-only; touches nothing but the ROM file.
"""
import struct, sys, collections

ROM = "/home/fsanches/compartilhado/technics_roms/roms/kn5000/kn5000_waveform_rom.ic307"
PAGE = 0x100000
GRAN = 16

rom = open(ROM, "rb").read()
print(f"rom {len(rom)} bytes")

def u16(off): return struct.unpack_from("<H", rom, off)[0]

def audit(base, label):
    head = u16(base)
    print(f"\n=== {label}  base 0x{base:06X}  head=0x{head:04X} ===")
    c1 = (head != 0) and (head % 4 == 0)
    n = head // 4
    c2 = (n * 4 <= PAGE - 4)
    print(f"  check1 head!=0 and head%4==0 : {c1}   n={n}")
    print(f"  check2 n*4 <= PAGE-4         : {c2}   (n*4={n*4}, bound={PAGE-4})")
    if not c1:
        return None
    pp = [u16(base + i * 4) for i in range(n)]
    wo = [u16(base + i * 4 + 2) for i in range(n)]
    p3 = sum(1 for i in range(n) if i == 0 or pp[i] >= pp[i-1])
    p4 = sum(1 for i in range(n) if pp[i] >= n * 4)
    p5 = sum(1 for i in range(n) if wo[i] * GRAN < PAGE)
    p6 = sum(1 for i in range(n) if u16(base + pp[i]) == wo[i])
    print(f"  check3 param_ptr monotonic   : {p3}/{n}")
    print(f"  check4 param_ptr >= n*4      : {p4}/{n}   (n*4=0x{n*4:04X})")
    print(f"  check5 wave_off*16 < 1MB     : {p5}/{n}")
    print(f"  check6 backref u16[pp]==wo   : {p6}/{n}")
    return dict(n=n, pp=pp, wo=wo, base=base)

pages = {}
for p in range(4):
    pages[p] = audit(p * PAGE, f"page {p}")

# ---------- structural anatomy of page 2 ----------
d = pages[2]
n, pp, wo, base = d["n"], d["pp"], d["wo"], d["base"]
print("\n=== page 2 anatomy ===")
print(f"  distinct param_ptr values : {len(set(pp))} of {n}")
print(f"  distinct wave_off values  : {len(set(wo))} of {n}")
print(f"  distinct (pp,wo) pairs    : {len(set(zip(pp,wo)))} of {n}")
print(f"  param_ptr range           : 0x{min(pp):04X}..0x{max(pp):04X}")
print(f"  wave_off  range           : 0x{min(wo):04X}..0x{max(wo):04X}  "
      f"(bytes 0x{min(wo)*16:06X}..0x{max(wo)*16:06X})")
print(f"  strictly increasing pp    : {sum(1 for i in range(1,n) if pp[i]>pp[i-1])} of {n-1} steps")
print(f"  equal pp steps            : {sum(1 for i in range(1,n) if pp[i]==pp[i-1])}")
print(f"  wave_off non-decreasing   : {sum(1 for i in range(1,n) if wo[i]>=wo[i-1])} of {n-1} steps")
print(f"  wave_off back-steps       : {[i for i in range(1,n) if wo[i]<wo[i-1]][:20]}")
dupwo = collections.Counter(wo)
shared = {k:v for k,v in dupwo.items() if v > 1}
print(f"  wave_offs used by >1 entry: {len(shared)} offsets, {sum(shared.values())} entries")
print(f"    biggest sharers: {sorted(shared.items(), key=lambda kv:-kv[1])[:8]}")

# chunk extents by the driver's own rule (min strictly-greater wave_off, else page end)
srt = sorted(set(wo))
import bisect
lens = []
for w in wo:
    j = bisect.bisect_right(srt, w)
    end = srt[j] * GRAN if j < len(srt) else PAGE
    lens.append(max(0, (end - w * GRAN) // 2))
lens_s = sorted(lens)
print(f"  chunk length samples: min {min(lens)} med {lens_s[len(lens)//2]} "
      f"mean {sum(lens)/len(lens):.1f} max {max(lens)}")
print(f"  zero-length chunks  : {sum(1 for L in lens if L==0)}")
print(f"  chunks < 32 samples : {sum(1 for L in lens if L<32)}")
print(f"  length histogram (samples -> count), top 12: "
      f"{collections.Counter(lens).most_common(12)}")

# overlap of PCM with the directory / param block
dir_end = n * 4
param_hi = max(pp)
first_pcm = min(wo) * GRAN
print(f"  directory occupies 0x0000..0x{dir_end:04X}")
print(f"  highest param_ptr   0x{param_hi:04X}")
print(f"  first PCM byte      0x{first_pcm:06X}   gap after last param_ptr: {first_pcm-param_hi} bytes")
print(f"  entries whose PCM starts inside the directory : {sum(1 for w in wo if w*GRAN < dir_end)}")
print(f"  entries whose PCM starts inside the param area: {sum(1 for w in wo if dir_end <= w*GRAN <= param_hi)}")
print(f"  last PCM byte addressed: 0x{max(wo)*GRAN:06X} of 0x{PAGE:06X}")

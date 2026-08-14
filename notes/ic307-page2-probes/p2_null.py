#!/usr/bin/env python3
"""NULL CONTROL for the page-2 directory: how often does the six-check parser accept
a window of NON-directory data? Slides the parser over every even offset of IC307 and
of three unrelated 1-4 MB ROMs, plus shuffled and synthetic-random data.

A criterion that cannot fail is not evidence -- so this also reports which of the six
checks are VACUOUS for u16 inputs.
"""
import struct, sys, random, collections
PAGE = 0x100000
GRAN = 16

def parse(buf, base, page=PAGE, maxn=None):
    """Return n if the six checks accept at `base`, else None (early exit)."""
    if base + 2 > len(buf): return None
    head = buf[base] | (buf[base+1] << 8)
    if head == 0 or head & 3: return None                 # 1
    n = head >> 2
    if n * 4 > page - 4: return None                      # 2
    if base + n*4 > len(buf): return None
    prev = -1
    for i in range(n):
        o = base + i*4
        pp = buf[o] | (buf[o+1] << 8)
        wo = buf[o+2] | (buf[o+3] << 8)
        if pp < prev: return None                         # 3
        if pp < n*4: return None                          # 4
        if wo * GRAN >= page: return None                 # 5
        if base + pp + 1 >= len(buf): return None
        if (buf[base+pp] | (buf[base+pp+1] << 8)) != wo: return None   # 6
        prev = pp
    return n

# ---- vacuity of the checks for u16 fields ----
print("VACUITY (u16 fields, PAGE=0x100000):")
print(f"  check2 fails only if n*4 > 0x{PAGE-4:X}; max u16 head 0xFFFC -> n*4 = {0xFFFC} "
      f"-> can check2 EVER fail? {0xFFFC > PAGE-4}")
print(f"  check5 fails only if wo*16 >= 0x{PAGE:X}; max u16 wo 0xFFFF -> 0x{0xFFFF*16:X} "
      f"-> can check5 EVER fail? {0xFFFF*16 >= PAGE}")

files = {
 "ic307 (wave, the dump)": "/home/fsanches/compartilhado/technics_roms/roms/kn5000/kn5000_waveform_rom.ic307",
 "ic14 (rhythm data 4MB)": "/home/fsanches/compartilhado/technics_roms/roms/kn5000/kn5000_rhythm_data_rom.ic14",
 "ic19 (custom data 1MB)": "/home/fsanches/compartilhado/technics_roms/roms/kn5000/kn5000_custom_data_rom.ic19",
 "v10 program (2MB)":      "/home/fsanches/compartilhado/technics_roms/roms/kn5000/kn5000_v10_program.rom",
}
for label, path in files.items():
    buf = open(path, "rb").read()
    hits = []
    for base in range(0, len(buf) - 4, 2):
        n = parse(buf, base)
        if n: hits.append((base, n))
    big = [h for h in hits if h[1] >= 50]
    print(f"\n{label}: {len(buf)} bytes, {len(range(0,len(buf)-4,2))} candidate bases")
    print(f"  accepted: {len(hits)}   with n>=50: {len(big)}   with n>=1000: "
          f"{len([h for h in hits if h[1]>=1000])}")
    print(f"  n histogram of accepts: {collections.Counter(n for _,n in hits).most_common(10)}")
    print(f"  accepts with n>=20: {[(hex(b), n) for b, n in hits if n >= 20][:12]}")

# ---- shuffled / random controls on a page-2-sized buffer ----
rom = open(files["ic307 (wave, the dump)"], "rb").read()
p2 = bytearray(rom[0x200000:0x300000])
rng = random.Random(20260814)
for trial, mk in (("byte-shuffled page 2", lambda: bytes(rng.sample(list(p2), len(p2)))),
                  ("uniform random 1MB",   lambda: bytes(rng.getrandbits(8) for _ in range(PAGE)))):
    b = mk()
    hits = [(o, parse(b, o)) for o in range(0, len(b)-4, 2)]
    hits = [(o, n) for o, n in hits if n]
    print(f"\n{trial}: accepted {len(hits)}; max n {max((n for _,n in hits), default=0)}")

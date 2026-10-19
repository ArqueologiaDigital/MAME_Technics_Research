#!/usr/bin/env python3
"""Where does each KN7000 firmware version keep the addresses kn7000.cpp depends on?

kn7000.cpp was written against v16 (build 941) and uses five of its addresses. Each moves
between builds, so the driver keeps a per-BIOS table (kn7000_bios_info). This script
produces it.

  quick, sched  The two interrupt entry points in the library the boot copies out of the
                program flash to 0x8C000000 and runs at 0x4C000000: the quick dispatcher
                (every level but 6; v16 0x4C03DDA0) and the scheduler entry (level 6, the
                system tick; v16 0x4C03DE26). The overlay's MN10300 core sends each level
                to a fixed vector, so these have to be right or the firmware hangs.
  tg_recbase    The library's per-slot voice-record array (v16 0x500AF940), from which
                tg_pitch_resolve/tg_type_resolve read a note's pitch and voice class.
  sd_aud, sd_snd  The SD audio and SD sound play-state bytes (v16 0x500063E6 and
                0x500063D9) that light the SD play LED.

Method.
  - Handlers: in v16 the library starts at program offset 0x3B8FD1 (copied from
    0x487B8FD1 by InitializeBlock27 0x484D7BBD). Take 64 bytes there, 0x86 bytes at the
    quick dispatcher and 64 at the scheduler entry, and find each, once, in every other
    image. A handler is at 0x4C000000 + (its offset - the library's offset).
  - Work RAM: for every place v16's code holds the address as a 32-bit immediate, take
    the 12 bytes before and the 8 after, and find that context, once, in the other image.
    The 4 bytes between are that version's address. Every matched site has to agree.
v14 is searched in its surviving upper half (image offset 0x200000). Its SD code is in the
undumped lower half, so its SD bytes print as "-"; v14 cannot boot anyway.

    python3 tools/kn7000_bios_addresses.py [ROMDIR]    # default ~/compartilhado/technics_romsets/kn7000
    python3 tools/kn7000_bios_addresses.py --ram 0x5000775C   # also any other v16 work-RAM address

`--ram` (repeatable) adds a column for a v16 work-RAM address a probe wants to read in every
version; the checks under notes/pr-port-2026-10-19/ use it for the rhythm window cache.

Prints one row per BIOS, in ROM_SYSTEM_BIOS order, with the number of agreeing sites for
each work-RAM address. It fails if a handler is missing or not unique, if the scheduler
entry is not 0x86 bytes past the quick one, or if two sites disagree.
"""
import argparse, os, struct, sys
from collections import Counter

ap = argparse.ArgumentParser(description="per-BIOS firmware addresses for kn7000.cpp")
ap.add_argument("romdir", nargs="?", default=os.path.expanduser("~/compartilhado/technics_romsets/kn7000"))
ap.add_argument("--ram", action="append", default=[], type=lambda x: int(x, 0),
                help="another v16 work-RAM address to find in every version")
args = ap.parse_args()
ROMDIR = args.romdir
BIOSES = [  # (name, build, even file, odd file, image offset of the files)
    ("sp7001", 942, "kn7000_program_even_sp7001_b942.ic17", "kn7000_program_odd_sp7001_b942.ic16", 0),
    ("v16", 941, "kn7000_program_even_v1.6_b941.ic17", "kn7000_program_odd_v1.6_b941.ic16", 0),
    ("v15", 935, "kn7000_program_even_v1.5_b935.ic17", "kn7000_program_odd_v1.5_b935.ic16", 0),
    ("v14", 929, "kn7000_program_even_v1.4_b929_upper.ic17", "kn7000_program_odd_v1.4_b929_upper.ic16", 0x200000),
    ("v13", 893, "kn7000_program_even_v1.3_b893.ic17", "kn7000_program_odd_v1.3_b893.ic16", 0),
]
V16_LIB, V16_QUICK, V16_SCHED = 0x3B8FD1, 0x3DDA0, 0x3DE26
V16_RAM = {"tg_recbase": 0x500AF940, "sd_aud": 0x500063E6, "sd_snd": 0x500063D9}
V16_RAM.update({f"{a:#010x}": a for a in args.ram})
BEFORE, AFTER = 12, 8


def image(even, odd, base):
    """Interleave the two 16-bit chips as the CPU sees them (ROM_GROUPWORD | ROM_SKIP(2)),
    at their place in the 4 MB program image (the rest left zero)."""
    e = open(os.path.join(ROMDIR, even), "rb").read()
    o = open(os.path.join(ROMDIR, odd), "rb").read()
    out = bytearray(base + len(e) * 2)
    for i in range(0, len(e), 2):
        out[base + 2 * i:base + 2 * i + 2] = e[i:i + 2]
        out[base + 2 * i + 2:base + 2 * i + 4] = o[i:i + 2]
    return bytes(out)


def all_at(hay, needle, start=0):
    r, i = [], hay.find(needle, start)
    while i >= 0:
        r.append(i)
        i = hay.find(needle, i + 1)
    return r


def once(hay, needle, what, start):
    r = all_at(hay, needle, start)
    if len(r) != 1:
        sys.exit(f"{what}: {'not found' if not r else 'found more than once'}")
    return r[0]


def counterpart(v16, other, value, start, what):
    votes = Counter()
    for site in all_at(v16, struct.pack("<I", value)):
        pre, post = v16[site - BEFORE:site], v16[site + 4:site + 4 + AFTER]
        hits = [i + BEFORE for i in all_at(other, pre, start)
                if other[i + BEFORE + 4:i + BEFORE + 4 + AFTER] == post]
        if len(hits) == 1:
            votes[struct.unpack_from("<I", other, hits[0])[0]] += 1
    if len(votes) > 1:
        sys.exit(f"{what}: sites disagree: {', '.join(f'{v:#x} x{n}' for v, n in votes.items())}")
    return votes.most_common(1)[0] if votes else (None, 0)


v16 = image(*BIOSES[1][2:5])
pat = {
    "lib": v16[V16_LIB:V16_LIB + 64],
    "quick": v16[V16_LIB + V16_QUICK:V16_LIB + V16_QUICK + 0x86],
    "sched": v16[V16_LIB + V16_SCHED:V16_LIB + V16_SCHED + 64],
}
print(f"{'bios':7} {'build':5} {'library':>10} {'quick':>10} {'scheduler':>10} "
      + " ".join(f"{k:>16}" for k in V16_RAM))
for name, build, even, odd, base in BIOSES:
    im = image(even, odd, base)
    at = {k: once(im, p, f"{name} {k}", base) for k, p in pat.items()}
    quick = 0x4C000000 + at["quick"] - at["lib"]
    sched = 0x4C000000 + at["sched"] - at["lib"]
    if sched - quick != 0x86:
        sys.exit(f"{name}: scheduler entry is {sched - quick:#x} past the quick dispatcher, not 0x86")
    ram = []
    for k, v in V16_RAM.items():
        a, n = counterpart(v16, im, v, base, f"{name} {k}")
        ram.append(f"{a:#010x} x{n:<3}" if a is not None else "-")
    print(f"{name:7} {build:5} {0x48400000 + at['lib']:#010x} {quick:#010x} {sched:#010x} "
          + " ".join(f"{r:>16}" for r in ram))

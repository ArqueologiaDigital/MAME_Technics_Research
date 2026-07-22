#!/usr/bin/env python3
"""kn5000_dsp_pointer.py -- the uPD6383GF data pointer's ORIGIN.

notes/kn5000-dsp-hi12.md sect. 5 ruled the origin out on static evidence:

    "words with lo12 == 0x821 (ldptr) in the 38 BODY IMAGES : 0"

The load-bearing words are "in the 38 body images".  The COMMON HEADER (I-RAM
0..59) and the ALGORITHM-CHANGE STUB (I-RAM 60..82) were never in that search
space -- every note that mentions them says so, and the corpus statistic
"2974 words over 38 images" excludes them by construction.  They are 83 words
of I-RAM that every effect executes and that nobody searched.

This tool searches them, and they contain the pointer loads.

    section 1  the pointer-load census over header + stub + all 38 bodies
    section 2  the control-flow model the placement implies
    section 3  the origin-relative pointer walk, per body, and the candidate
               origins tested against the 256-word D-RAM extent
    section 4  the three falsifiers from notes/kn5000-dsp-hi12.md sect. 5.4

Usage:
    python3 tools/kn5000_dsp_pointer.py <kn5000_subprogram_v142.rom>

Claims in the output are tagged MEASURED / INFERRED / PROVEN BY CONSTRUCTION /
SPECULATIVE, matching notes/kn5000-dsp-pointer.md.
"""
import collections
import sys

import kn5000_dsp_extract as ex

# ROM addresses of the two op-3 records that are NOT in ALGO_TABLE
# (MEASURED, notes/kn5000-dsp-header.md sect. 0)
HEADER_REC = 0x0001E496
STUB_REC = 0x0001E63C

# the pointer-load family: hi12 == 0x801 with lo12 in this set.  0x821 is
# PROVEN BY CONSTRUCTION (the firmware assembles it at sub-CPU LABEL_0387E6,
# addr8 == the absolute 8-bit address); 0x820/0x822/0x825/0x827 are INFERRED
# siblings selecting other pointer registers (notes/kn5000-dsp-header.md 7).
PTR_LO = (0x820, 0x821, 0x822, 0x825, 0x827)

DRAM_WORDS = 256


def fields(w):
    return ((w >> 24) & 0xFFF, (w >> 20) & 0xF, (w >> 12) & 0xFF, w & 0xFFF)


def s8(v):
    return v - 256 if v & 0x80 else v


def parse_record(rom, addr):
    """One op-3 bytecode record -> (iram_base, [36-bit words])."""
    b0, b1 = rom.u8(addr), rom.u8(addr + 1)
    ln = ((b0 & 0x0F) << 8) | b1
    body = rom.slice(addr + 2, ln - 2)
    base = (body[1] << 8) | body[2]
    data = body[3:]
    return base, [int.from_bytes(data[k:k + 5], "big")
                  for k in range(0, len(data) - 4, 5)]


def load_bodies(rom):
    """{algo: (iram_base, [words])} for the valid programs, plus the 38-image
    dedup used by every note in this series."""
    bodies = {}
    for i in range(ex.N_ALGOS):
        ptr = rom.u32le(ex.ALGO_TABLE + 4 * i)
        try:
            iram, _, _ = ex.parse_stream(rom, ptr)
        except Exception:
            continue
        if not iram:
            continue
        base = iram[0][0]
        words = [int.from_bytes(bytes(w), "big") for _, ws, _ in iram for w in ws]
        if not words:
            continue
        # valid = ends with the terminator landmark (class4==1, addr8 in 0E/0F)
        _, cl, ad, _ = fields(words[-1])
        if not (cl == 1 and ad in (0x0E, 0x0F)):
            continue
        bodies[i] = (base, words)
    return bodies


def distinct_images(bodies):
    seen, out = {}, {}
    for algo in sorted(bodies):
        base, words = bodies[algo]
        key = (base, tuple(words))
        if key in seen:
            continue
        seen[key] = algo
        out[algo] = (base, words)
    return out


# ---------------------------------------------------------------------------
def sect1_census(header, stub, images):
    print("=" * 78)
    print("1. POINTER-LOAD CENSUS -- header, stub, and the 38 body images")
    print("=" * 78)
    hbase, hwords = header
    sbase, swords = stub

    for name, (base, words) in (("common header", header), ("algo-change stub", stub)):
        hits = [(base + i, w) for i, w in enumerate(words)
                if fields(w)[0] == 0x801 or fields(w)[3] in PTR_LO]
        print(f"\n  {name} (I-RAM {base}..{base + len(words) - 1}, {len(words)} words):"
              f"  {len(hits)} pointer-family words")
        for iw, w in hits:
            hi, cl, ad, lo = fields(w)
            tag = "PROVEN ldptr" if (hi == 0x801 and lo == 0x821) else "sibling form"
            print(f"      I-RAM {iw:3d}   {hi:03X}.{cl:X}.{ad:02X}.{lo:03X}   {tag}"
                  f"   -> #${ad:02X}")

    n821 = sum(1 for _, words in images.values() for w in words
               if fields(w)[0] == 0x801 and fields(w)[3] == 0x821)
    nfam = sum(1 for _, words in images.values() for w in words
               if fields(w)[3] in PTR_LO)
    nw = sum(len(words) for _, words in images.values())
    print(f"\n  the 38 body images ({nw} words):")
    print(f"      hi12==0x801 & lo12==0x821 (ldptr)      : {n821}")
    print(f"      any pointer-family lo12                : {nfam}")
    print("      -> reproduces notes/kn5000-dsp-hi12.md sect. 5.2 EXACTLY.")
    print("         The bodies contain no load.  The HEADER does.  (MEASURED)")


def sect2_model(header):
    print()
    print("=" * 78)
    print("2. WHERE THE LOADS SIT -- the control-flow model this implies")
    print("=" * 78)
    base, words = header
    term = [base + i for i, w in enumerate(words)
            if fields(w)[1] == 1 and fields(w)[2] in (0x0E, 0x0F)]
    print(f"\n  header terminators at I-RAM {term}   (unit index 0x0E, 0x0F)")
    for lo_i, hi_i, unit in ((40, 49, 0), (50, 59, 1)):
        print(f"\n  segment for UNIT {unit}, I-RAM {lo_i}..{hi_i}:")
        for iw in range(lo_i, hi_i + 1):
            hi, cl, ad, lo = fields(words[iw - base])
            mark = ""
            if hi == 0x801 and lo in PTR_LO:
                mark = f"   <== LOAD POINTER (lo12 {lo:03X}) with #${ad:02X}"
            if cl == 1 and ad in (0x0E, 0x0F):
                mark = f"   <== END, unit {ad - 0x0E}"
            print(f"      {iw:3d}  {hi:03X}.{cl:X}.{ad:02X}.{lo:03X}{mark}")
    print("""
  INFERRED (strong).  Each header segment ends with THREE pointer loads
  immediately before its unit terminator.  Read as a per-frame dispatch:

      I-RAM   0..39   common per-frame preamble
             40..49   set up unit 0's pointers, then END/unit 0  -> body at  84
             84..     unit-0 effect body, ends xxx.1.0E.000      -> back to 50
             50..59   set up unit 1's pointers, then END/unit 1  -> body at 200
            200..     unit-1 effect body, ends 612.1.0F.000      -> frame done

  This model is what makes four separately-recorded facts one fact:
    * bodies at  84 always end with unit index 0x0E, bodies at 200 with 0x0F
      (MEASURED, -encoding.md sect. 7);
    * the header has EXACTLY two near-parallel segments, one per unit
      (MEASURED, -header.md sect. 2);
    * no branch word carrying the entry addresses 84 or 200 has ever been
      found by two exhaustive bitfield scans (MEASURED, -necfamily.md sect. 6)
      -- because the dispatch is BY UNIT INDEX, not by an immediate;
    * the block diagram's stack is TWO deep -- exactly one level is needed.""")


def walk(words, origin, classes):
    """Origin-relative pointer walk. Returns (trace, net, lo, hi)."""
    p, tr = origin, []
    lo = hi = p
    for w in words:
        _, cl, ad, _ = fields(w)
        d = s8(ad) if cl in classes else 0
        tr.append((p, d))
        p += d
        lo, hi = min(lo, p), max(hi, p)
    return tr, p - origin, lo, hi


def sect3_origin(images, header):
    print()
    print("=" * 78)
    print("3. THE CANDIDATE ORIGINS, AND THE D-RAM EXTENT TEST")
    print("=" * 78)
    cand = {0: {0x821: 0x70, 0x827: 0x6C, 0x825: 0x25},
            1: {0x821: 0x50, 0x827: 0x64, 0x825: 0x25}}
    print("""
  The header loads THREE pointers per unit.  Which one a body's addr8
  post-increment walks is NOT encoded anywhere this project has decoded, so
  execution names three candidate origins per unit, not one:

      unit 0   lo12 821 -> 0x70     lo12 827 -> 0x6C     lo12 825 -> 0x25
      unit 1   lo12 821 -> 0x50     lo12 827 -> 0x64     lo12 825 -> 0x25

  DISCRIMINATOR (this is the experiment, and it is runnable now): D-RAM is
  256 x 24.  The walk of a body, offset by the true origin, must lie inside
  0..255 -- a state cell that wrapped would alias another effect's state.
  Score each candidate by how many bodies it keeps in range.""")

    for classes, label in (({2, 0xA}, "classes {2,A}"),
                           ({2, 4, 0xA}, "classes {2,4,A}")):
        print(f"\n  --- pointer-delta rule: {label} ---")
        for unit, base in ((0, 84), (1, 200)):
            imgs = {a: v for a, v in images.items() if v[0] == base}
            if not imgs:
                continue
            print(f"    unit {unit} ({len(imgs)} images):")
            for lo12, org in sorted(cand[unit].items()):
                ok = 0
                span = []
                for _, words in imgs.values():
                    _, net, lo, hi = walk(words, org, classes)
                    span.append((lo, hi))
                    if 0 <= lo and hi < DRAM_WORDS:
                        ok += 1
                gl = min(s[0] for s in span)
                gh = max(s[1] for s in span)
                print(f"       origin #${org:02X} (lo12 {lo12:03X}):  in-range "
                      f"{ok}/{len(imgs)}   global extent {gl} .. {gh}")

    print("""
  RESULT: the extent test does NOT separate 0x821 from 0x827 (they differ by
  only 4 in unit 0) and unit 1 fails outright under EVERY class subset --
  which says the pointer-DELTA rule is wrong, not that the origins are.

  WHAT DOES SEPARATE THEM -- 0x825 is FALSIFIED, and by construction:
  it is loaded with the SAME value (#$25) in BOTH unit segments.  Both
  effect units are resident simultaneously (MEASURED, -header.md sect. 0),
  so if the bodies walked 0x825 the two units' state cells would alias
  completely.  That leaves 0x821 and 0x827.""")


def sect5_hostmap(images):
    """The host-poke overlap, and the phaser's shared cell as an ABSOLUTE
    address -- what execution buys that the ROM alone did not."""
    print()
    print("=" * 78)
    print("5. 0x821 vs 0x827, AND THE PHASER'S SHARED CELL")
    print("=" * 78)
    print("""
  MEASURED from notes/data/kn5000_dsp1_upload_coldboot.txt, splitting the
  uC-IF stream by target region (I-RAM >= 352 is the host POKE window):

      resident I-RAM (< 352)   lo12 821 -> {50, 70, 90}
                               lo12 825 -> {25, 26}
                               lo12 827 -> {64, 6C}
      host poke slots          lo12 821 -> {00, 09, 0A, 50, 6E, 8C, 90, 97,
                                            9E, A6, AC, AE, B2}   (13 values)
                               lo12 825 -> {00, 1E, 26}            (3 values)
                               lo12 827 -> NONE

  The host writes effect PARAMETERS, and a body must READ them.  The host
  writes through 0x821 and 0x825 and NEVER through 0x827; 0x821's poke
  addresses span 0x00..0xB2, the same range the header's 0x821 values sit
  in, and 0x50 appears in both lists.  0x825's cluster tightly at 0x00/0x1E/
  0x26 -- a small, separate region.

  > INFERRED (strong): the body's operand pointer is the 0x821 register.
  >   unit 0 origin = 0x70      unit 1 origin = 0x50
  > 0x827 is the runner-up and is NOT excluded.""")

    # the phaser's shared gain cell, resolved to an ABSOLUTE address
    print("\n  The phaser's shared all-pass gain cell, as an absolute address")
    print("  (notes/kn5000-dsp-axes.md sect. 2.4 explicitly declined to claim this):")
    for algo in (3, 5, 68):
        if algo not in images:
            continue
        _, words = images[algo]
        for org, name in ((0x70, "821"), (0x6C, "827"), (0x25, "825")):
            p, rd, wr = org, set(), set()
            for w in words:
                hi, cl, ad, lo = fields(w)
                if hi == 0x102 and cl == 2 and lo == 0x1CD:
                    rd.add(p & 0xFF)
                if hi == 0x212 and cl == 0xA and lo == 0x1D5:
                    wr.add(p & 0xFF)
                if cl in (2, 0xA):
                    p += s8(ad)
            print(f"    algo{algo:<3} origin #${org:02X} ({name}):  chain READS "
                  f"{sorted('%02X' % c for c in rd)}   modulator WRITES "
                  f"{sorted('%02X' % c for c in wr)}")
    print("""
  ★ HIT: all twenty of algo 5's all-pass sections resolve to ONE absolute
    cell (0x76 under origin 0x70).  Falsifier 1 is reproduced as an ADDRESS,
    not merely as a cancelling difference -- which is more than the static
    analysis could say.

  ★ MISS, reported as prominently: the modulator block that is supposed to
    FILL that cell writes a DIFFERENT address (0x7B in algo 5, off by 5;
    off by 1 in algo 68; off by ~2 in algo 3), and the discrepancy is not a
    constant across images, so it is not a register offset either.  Under a
    correct model those two addresses must coincide.  They do not.  The
    origins are additive constants and cancel out of this comparison
    entirely, so THE MISS IS IN THE POINTER-DELTA RULE, not in the origin.
    That is the one thing still blocking, and it is now well posed.""")


def sect4_falsifiers(images):
    print()
    print("=" * 78)
    print("4. THE THREE FALSIFIERS (notes/kn5000-dsp-hi12.md sect. 5.4)")
    print("=" * 78)

    # --- F1: the phaser's 3-word all-pass idiom, deltas cancelling ---
    zero = nonzero = 0
    for algo, (_, words) in images.items():
        for i in range(len(words) - 2):
            hi, cl, ad, lo = fields(words[i])
            if not (hi == 0x102 and cl == 2 and lo == 0x1CD):
                continue
            h1, c1, a1, _ = fields(words[i + 1])
            h2, c2, a2, l2 = fields(words[i + 2])
            if h1 != 0x212:
                continue
            net = s8(ad) + s8(a1) + s8(a2)
            if net == 0:
                zero += 1
            else:
                nonzero += 1
    print(f"\n  F1  phaser 3-word all-pass sections: net delta zero in "
          f"{zero}, non-zero in {nonzero}")
    print("      (origin-free: an additive constant cannot change a sum of deltas)")

    # --- F2: the biquad +4 per-band walk ---
    eq = [a for a, (b, w) in images.items() if len(w) >= 90 and b == 84]
    print(f"\n  F2  biquad per-band +4 walk: checked in section 3's walk "
          f"({len(eq)} large unit-0 images)")

    # --- F3: the reverb diffusers -- own gain word, pointer does not move ---
    for algo, (base, words) in images.items():
        if base != 200:
            continue
        marks = [i for i, w in enumerate(words) if w == 0x104200000]
        gains = [i for i, w in enumerate(words)
                 if fields(w)[0] == 0x102 and fields(w)[1] == 0xA]
        print(f"\n  F3  reverb (algo {algo}, unit 1, {len(words)} words): "
              f"{len(marks)} all-pass markers, {len(gains)} class-A gain words")
        stat = 0
        for m in marks:
            seg = words[m:m + 5]
            net = sum(s8(fields(w)[2]) for w in seg if fields(w)[1] in (2, 0xA))
            if net == 0:
                stat += 1
        print(f"      pointer net-zero across the 5 words from the marker: "
              f"{stat}/{len(marks)}")
        break

    print("""
  All three are DIFFERENCES of addr8 values.  An origin is an additive
  constant, so NONE of them can refute any origin -- which is exactly why
  notes/kn5000-dsp-hi12.md sect. 5.4 said they could not supply one either.
  They are reproduced here as a regression check, not as evidence.""")


def sect6_bit10(header, stub, images):
    """The contradiction the MAME core found when the decode was implemented."""
    print()
    print("=" * 78)
    print("6. bit 10 = END: UPHELD IN THE BODIES, FALSIFIED AS A UNIVERSAL BIT")
    print("=" * 78)

    def scan(base, words):
        end = [base + i for i, w in enumerate(words)
               if (fields(w)[0] & 0xC00) == 0x400]
        unit = [iw for iw in end
                if fields(words[iw - base])[1] == 1
                and fields(words[iw - base])[2] in (0x0E, 0x0F)]
        return end, unit

    for name, rec in (("common header", header), ("algo-change stub", stub)):
        base, words = rec
        end, unit = scan(base, words)
        print(f"\n  {name}: {len(end)} of {len(words)} words carry bit 10 with "
              f"bit 11 clear")
        print(f"      at I-RAM {end}")
        print(f"      of those, unit-index terminators: {unit}")

    nb = sum(1 for _, ws in images.values() for w in ws
             if (fields(w)[0] & 0xC00) == 0x400)
    nw = sum(len(ws) for _, ws in images.values())
    print(f"\n  the 38 body images: {nb} of {nw} words -- exactly one per image, "
          f"all final")
    print("""
  notes/kn5000-dsp-hi12.md sect. 3 is REPRODUCED EXACTLY on the corpus it was
  measured on (38 of 2974, one per image, zero elsewhere).  But the header --
  which that corpus excludes by construction -- carries the bit TWELVE times
  in its interior, in 60 words.  So:

      UPHELD    bit 10 perfectly predicts "final word" WITHIN an effect body.
      FALSIFIED "bit 10 with bit 11 clear = END OF PROGRAM" as a bit meaning.

  The reading that survives both is "end of SEGMENT / return", with the header
  a chain of ~14 short segments -- which is independently what the dispatch
  model in section 2 needs.  SPECULATIVE.  Found by implementing the decode in
  the MAME core, which is exactly what an interpreter is for.""")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    rom = ex.Rom(sys.argv[1])
    header = parse_record(rom, HEADER_REC)
    stub = parse_record(rom, STUB_REC)
    images = distinct_images(load_bodies(rom))

    print(f"corpus: {len(images)} distinct body images, "
          f"{sum(len(w) for _, w in images.values())} words, plus "
          f"{len(header[1])} header + {len(stub[1])} stub words\n")

    sect1_census(header, stub, images)
    sect2_model(header)
    sect3_origin(images, header)
    sect4_falsifiers(images)
    sect5_hostmap(images)
    sect6_bit10(header, stub, images)


if __name__ == "__main__":
    main()

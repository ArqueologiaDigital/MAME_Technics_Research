#!/usr/bin/env python3
"""kn5000_dsp_biquad.py -- the PARAMETRIC EQ biquad as a Rosetta Stone for the
NEC uPD6383GF effects DSP (KN5000 IC311), plus a corpus-wide test of the
"class4 is an address-space selector" hypothesis.

Everything printed here is MEASURED.  The interpretation lives in
notes/kn5000-dsp-biquad.md.

Sections:
    sections   find the 9-word PEQ section in every image, near-miss tolerant,
               and print the per-image band/channel counts
    section    word-by-word dump of the section and of the two channel setups
    cursor     the signed-addr8 cursor arithmetic and the three-way agreement
               microcode / channel delta / host T1 stride
    hostxref   cross-check the section against the host parameter map (T1/T2)
    class4     is class4 an address-space selector?  addr8 behaviour per class,
               the class-1 prediction test against the DRAM label
    rewind     the section-terminating 647 word across all PEQ-bearing images

Usage:
    python3 tools/kn5000_dsp_extract.py <kn5000_subprogram_v142.rom> /tmp/progs
    python3 tools/kn5000_dsp_biquad.py <kn5000_subprogram_v142.rom> /tmp/progs \\
            [<kn5000_v10_program.rom>] [section ...]

Reuses tools/kn5000_dsp_extract.py, kn5000_dsp_coeffs.py, kn5000_dsp_params.py
and kn5000_dsp_class2.py.  Nothing here re-implements the bytecode parsing, the
field split or the effect-topology labels.
"""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kn5000_dsp_class2 as K          # noqa: E402  (fl/fmt/load_progs/IMG_CAT)

PEQ = 39                                # PARAMETRIC EQ, the reference image
SECTION_LEN = 9


def s8(a):
    """addr8 read as a signed 8-bit displacement."""
    return a - 256 if a > 127 else a


def distinct_images(progs):
    """first algorithm slot of each byte-identical program image."""
    seen = {}
    for a in sorted(progs):
        seen.setdefault(tuple(progs[a]), a)
    return sorted(seen.values())


def find_sections(words, ref, maxdiff=1):
    """All start indices where a SECTION_LEN window differs from ref in at most
    `maxdiff` words.  The blunt instrument -- byte-identical matching -- is what
    produced the retracted "4 bands" claim, so the default is tolerant."""
    out = []
    for i in range(len(words) - SECTION_LEN + 1):
        d = [k for k in range(SECTION_LEN) if words[i + k] != ref[k]]
        if len(d) <= maxdiff:
            out.append((i, d))
    return out


# ---------------------------------------------------------------- sections

def sec_sections(progs, imgs, ref):
    print("=== the 9-word PEQ section, near-miss tolerant search "
          "(<=1 differing word)\n")
    print(f"{'algo':>4} {'name':22} {'n':>2}  starts / differing word index")
    total = 0
    for a in imgs:
        hits = find_sections(progs[a], ref)
        if not hits:
            continue
        total += len(hits)
        nm = K.IMG_CAT.get(a, ("?",))[0]
        det = "  ".join(f"{i}{'' if not d else '(w' + ','.join(map(str, d)) + ')'}"
                        for i, d in hits)
        print(f"{a:>4} {nm:22} {len(hits):>2}  {det}")
    print(f"\n{total} sections over {len(imgs)} distinct images")

    print("\n-- how the answer depends on the tolerance (the '4 bands' trap):")
    print(f"   {'algo':>4} {'name':22} {'d=0':>4} {'d=1':>4} {'d=2':>4}")
    for a in imgs:
        h = [len(find_sections(progs[a], ref, maxdiff=d)) for d in (0, 1, 2)]
        if h[2]:
            print(f"   {a:>4} {K.IMG_CAT.get(a, ('?',))[0]:22}"
                  f" {h[0]:>4} {h[1]:>4} {h[2]:>4}")


# ---------------------------------------------------------------- section

def sec_section(progs, ref):
    w = progs[PEQ]
    hits = [i for i, _ in find_sections(w, ref)]
    print("=== PARAMETRIC EQ (algo 39), 105 words\n")
    print("-- the section, and the variants of its last word")
    for k in range(SECTION_LEN):
        var = sorted({K.fmt(w[i + k]) for i in hits})
        print(f"   [{k}] {K.fmt(ref[k])}   class {K.fl(ref[k])[1]:X}"
              f"   variants over the 10 sections: {' '.join(var)}")

    print("\n-- channel 0 setup (words 0..4) vs channel 1 setup (words 50..58)")
    for i in list(range(0, 5)):
        print(f"   ch0 [{i:3d}] {K.fmt(w[i])}")
    print()
    for i in list(range(50, 59)):
        print(f"   ch1 [{i:3d}] {K.fmt(w[i])}")

    print("\n-- minimal pairs between the two setups (same hi12/class4/lo12):")
    for i in range(0, 5):
        for j in range(50, 59):
            hi, c, a1, lo = K.fl(w[i])
            hj, d, a2, lj = K.fl(w[j])
            if (hi, c, lo) == (hj, d, lj) or (lo == lj and c == d):
                print(f"   [{i:3d}] {K.fmt(w[i])}   vs   [{j:3d}] {K.fmt(w[j])}"
                      f"    addr8 delta {s8(a2) - s8(a1):+d} (0x{(a2 - a1) & 0xFF:02X})")

    print("\n-- words unique to the channel-1 setup:")
    c0 = set(w[0:5])
    for j in range(50, 59):
        if w[j] not in c0:
            print(f"   [{j:3d}] {K.fmt(w[j])}")


# ---------------------------------------------------------------- cursor

def sec_cursor(progs, ref):
    print("=== signed-addr8 cursor arithmetic inside the section\n")
    tot = 0
    for k in range(SECTION_LEN):
        h, c, a, lo = K.fl(ref[k])
        if c == 8:
            print(f"   [{k}] {K.fmt(ref[k])}  class 8 -- EXCLUDED "
                  f"(addr8 0x{a:02X} is constant corpus-wide, see class4 section)")
            continue
        tot += s8(a)
        print(f"   [{k}] {K.fmt(ref[k])}  addr8 {s8(a):+3d}   running {tot:+3d}")
    print(f"\n   per-section signed addr8 total (class 8 excluded) = {tot:+d}")

    w = progs[PEQ]
    b0, b1 = K.fl(w[4])[2], K.fl(w[57])[2]
    print(f"\n   channel state base   ch0 = 0x{b0:02X}   ch1 = 0x{b1:02X}"
          f"   delta = {b1 - b0} (0x{b1 - b0:02X})")
    print(f"   5 bands x {tot} = {5 * tot}   vs channel delta {b1 - b0}"
          f"   -> {'AGREE' if 5 * tot == b1 - b0 else 'DISAGREE'}")

    nA = sum(1 for x in ref if K.fl(x)[1] == 0xA)
    print(f"\n   class-A words per section = {nA}   -> 5 bands x {nA} = {5 * nA}"
          f" coefficient words per channel")

    print("\n-- P-consumer check (round two: 647/687 MUST follow a class-A word)")
    for k in range(SECTION_LEN):
        lo = K.fl(ref[k])[3]
        if lo in (0x647, 0x687):
            prev = K.fl(ref[k - 1])[1]
            print(f"   [{k}] lo12 {lo:03X}: predecessor class {prev:X}"
                  f"  {'OK' if prev == 0xA else 'VIOLATION'}")
    hits = [i for i, _ in find_sections(w, ref)]
    bad = sum(1 for i in hits for k in (5, 8) if K.fl(w[i + k - 1])[1] != 0xA)
    print(f"   violations over all {len(hits)} sections x 2 consumers: {bad}")


# ---------------------------------------------------------------- hostxref

def sec_hostxref(argv):
    print("=== cross-check against the host parameter map (needs the main ROM)\n")
    print("From tools/kn5000_dsp_params.py (not re-derived here):")
    print("   algo 39 PARAMETRIC EQ   T1 op 70 -> 00 06 0C 12 18 | 64 68 6C 70 74")
    print("      first  group: 5 addresses, stride 6  -> 5 bands x 6 coefficients")
    print("      second group: 5 addresses, stride 4  -> 5 bands x 4 state words")
    print("   T2: 15 records, op70 operands 0,0,0,1,1,1,2,2,2,3,3,3,4,4,4")
    print("      -> 5 bands x (frequency, Q, gain)\n")
    print("   algo 71 PEQ+CHORUS      T1 op 70 -> 02 12      (2 entries)")
    print("   algo 72 PEQ+S.DELAY     T1 op 70 -> 00 0A      (2 entries)")
    print("   algo 75 PEQ+COMPRESSOR  T1 op 70 -> 00 0F      (2 entries)")
    print("   algo 96 PEQ+COMPR+DIST  T1 op 70 -> 00 13      (2 entries)")
    print("      -> one band, but TWO coefficient bases: the channels do NOT")
    print("         share coefficients in the combination effects.\n")
    print("Run tools/kn5000_dsp_params.py <subprogram.rom> <v10_program.rom>")
    print("and grep for 'algo 39' / 'algo 71' / 'algo 75' to reproduce.")


# ---------------------------------------------------------------- class4

def sec_class4(progs, imgs):
    print("=== TASK 2: is class4 an address-space selector for BODY words?\n")

    h = collections.Counter()
    for a in progs:
        for x in progs[a]:
            h[K.fl(x)[1]] += 1
    print("class4 histogram over all 96 loaded programs:")
    for c in sorted(h):
        print(f"   class {c:X}  {h[c]:>5}")
    print(f"   never observed: {' '.join(f'{c:X}' for c in range(16) if c not in h)}")

    print("\n-- bit 3 of class4 (= bit 23 of the word) as the multiply bit:")
    W = set()
    for a in progs:
        W |= set(progs[a])
    pairs = [(x, x ^ 0x800000) for x in W if (x ^ 0x800000) in W]
    cc = collections.Counter(tuple(sorted((K.fl(x)[1], K.fl(y)[1]))) for x, y in pairs)
    print(f"   {len(pairs)//2} distinct words exist in both bit-3 polarities;"
          f" class pairs: {dict(cc)}")

    print("\n-- addr8 by class4: does the class have a memory operand at all?")
    for c in sorted(h):
        vals = collections.Counter()
        for a in progs:
            for x in progs[a]:
                f = K.fl(x)
                if f[1] == c:
                    vals[f[2]] += 1
        tag = ""
        if len(vals) == 1:
            tag = f"   <-- CONSTANT 0x{next(iter(vals)):02X}: no address operand"
        print(f"   class {c:X}: {len(vals):>3} distinct addr8 over {h[c]:>5} words{tag}")

    print("\n-- PREDICTION (stated before the test): if class4 = 1 selects the")
    print("   external DRAM, then images with no delay memory must contain no")
    print("   class-1 word other than the program terminator.")
    fam = collections.Counter()
    rows = []
    for a in imgs:
        nm = K.IMG_CAT.get(a, ("?", 0, 0, 0, 0))
        c1 = [x for x in progs[a] if K.fl(x)[1] == 1]
        term = progs[a][-1]
        body = [x for x in c1 if x is not term or progs[a].index(x) != len(progs[a]) - 1]
        body = [x for i, x in enumerate(progs[a])
                if K.fl(x)[1] == 1 and i != len(progs[a]) - 1]
        frame = [x for x in body if K.fl(x)[0] == 0x880 and K.fl(x)[2] == 0x30]
        rest = [x for x in body if x not in frame]
        rows.append((a, nm[0], nm[1], len(c1), len(frame), len(rest),
                     sorted({K.fmt(x) for x in rest})))
        for x in rest:
            fam[K.fmt(x)] += 1
    print(f"\n{'algo':>4} {'name':22} {'dram':>4} {'c1':>3} {'880.1.30':>8} "
          f"{'rest':>4}  rest words")
    for a, nm, dram, n1, nf, nr, ws in rows:
        print(f"{a:>4} {nm:22} {dram:>4} {n1:>3} {nf:>8} {nr:>4}  {' '.join(ws)}")
    viol = [(a, nm) for a, nm, dram, _, _, nr, _ in rows if dram == 0 and nr]
    clean = [(a, nm) for a, nm, dram, _, _, nr, _ in rows if dram == 0 and not nr]
    print(f"\n   non-DRAM images with NO non-framing class-1 word: {len(clean)}")
    print(f"      {', '.join(nm for _, nm in clean)}")
    print(f"   non-DRAM images that VIOLATE the prediction: {len(viol)}")
    print(f"      {', '.join(nm for _, nm in viol)}")

    print("\n-- which class-1 word families appear, and where:")
    for wf, n in fam.most_common():
        owners = [K.IMG_CAT.get(a, ('?',))[0] for a, *_ , ws in rows if wf in ws]
        print(f"   {wf}  x{n:<3} {', '.join(owners)}")


# ---------------------------------------------------------------- rewind

def sec_rewind(progs, imgs, ref):
    print("=== the section-terminating word [8] across every PEQ-bearing image\n")
    print(f"{'algo':>4} {'name':22}  terminators in program order")
    for a in imgs:
        hits = [i for i, _ in find_sections(progs[a], ref)]
        if not hits:
            continue
        print(f"{a:>4} {K.IMG_CAT.get(a, ('?',))[0]:22}  "
              + "  ".join(K.fmt(progs[a][i + 8]) for i in hits))
    print("\n   0x03 = +3 (mid-chain, PEQ only).  0xC1 = -63 is the channel-0")
    print("   value in EVERY one-band PEQ combination.  0xAD = -83 is the")
    print("   channel-0 value of the five-band PEQ.  Channel 1 varies per image.")


SECTIONS = {
    "sections": sec_sections, "section": sec_section, "cursor": sec_cursor,
    "hostxref": sec_hostxref, "class4": sec_class4, "rewind": sec_rewind,
}


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    progdir = sys.argv[2]
    want = [a for a in sys.argv[3:] if a in SECTIONS] or list(SECTIONS)
    progs = K.load_progs(progdir)
    if PEQ not in progs:
        sys.exit(f"algo{PEQ} not found in {progdir}; run kn5000_dsp_extract.py first")
    imgs = distinct_images(progs)
    ref = progs[PEQ][5:5 + SECTION_LEN]

    for name in want:
        print("\n" + "=" * 74)
        f = SECTIONS[name]
        if name == "hostxref":
            f(sys.argv)
        elif name in ("sections", "rewind"):
            f(progs, imgs, ref)
        elif name == "class4":
            f(progs, imgs)
        elif name == "section":
            f(progs, ref)
        else:
            f(progs, ref)


if __name__ == "__main__":
    main()

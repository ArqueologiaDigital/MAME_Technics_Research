#!/usr/bin/env python3
"""kn5000_dsp_alu.py -- decode and VERIFY the uPD6383GF `lo12' ALU field.

Companion note: notes/dsp-alu-biquad.md
Mirror of the C++ that ships: src/devices/cpu/upd6383/upd6383.cpp exec_alu().

The PARAMETRIC EQ biquad is the only block in the corpus whose arithmetic is
known INDEPENDENTLY of the DSP -- the sub-CPU designs its coefficients itself
with a tan()-based bilinear designer (notes/kn5000-dsp-biquad-coeffs.md, PROVEN
BY CONSTRUCTION).  So the nine words of one section can be scored against a
transfer function nothing in the DSP was used to compute.  This tool:

  * runs the UNIFORM ALU (one operation per word; the accumulator op is NOT in
    lo12 -- see sect. 7-A8 of the note for the one alternative that also fits)
    on real ROM coefficient banks in exact fixed point;
  * measures the transfer function with a hand-rolled DFT (stdlib only) and
    reports dB/degree error against the biquad those coefficients describe;
  * ABLATES the two non-obvious parts -- the accumulator clear that rides on
    hi12 bit 4, and the one-bit right shift on the tempB path -- so the pass
    criterion is shown to be capable of failing;
  * censuses the lo12 bit fields over the whole corpus.

Usage:
    python3 tools/kn5000_dsp_extract.py <subrom> /tmp/progs
    python3 tools/kn5000_dsp_alu.py <subrom> [sections...]

Sections: verify ablate sweep fields   (default: all)
"""
import os
import sys
import math
import cmath
import collections

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import kn5000_dsp_biquadmap as M            # noqa: E402
import kn5000_dsp_extract as E              # noqa: E402


# ---------------------------------------------------------------------------
# The section under analysis: algo 39 words 5..13, repeated ten times byte for
# byte (5 bands x 2 channels).  MEASURED.
# ---------------------------------------------------------------------------
SECTION = [0x0000A001D3, 0x0212A01412, 0x0202A011D5, 0x0202A011D4,
           0x0202A001D5, 0x01022FF687, 0x0804816415, 0x0212AFF407,
           0x0000203647]

# where each image's 5+1-word biquad blocks start inside its uploaded bank
BLOCK_STARTS = {33: [2, 11], 35: [3, 14], 39: [0, 6, 12, 18, 24], 99: [0, 20]}


def flds(w):
    return ((w >> 24) & 0xFFF, (w >> 20) & 0xF, (w >> 12) & 0xFF, w & 0xFFF)


def s24(v):
    v &= 0xFFFFFF
    return v - 0x1000000 if v & 0x800000 else v


# the four ANCHORED lo12[10:6] source codes and the five anchored lo12[4:0]
# action codes -- see notes/dsp-alu-biquad.md sect. 3
SRC_MEM, SRC_ACC, SRC_TA, SRC_TB = 0x07, 0x10, 0x19, 0x1A
ACT_ST_BUS, ACT_NONE_2, ACT_CAP_TA, ACT_CAP_TB, ACT_NONE_5 = \
    0x07, 0x12, 0x13, 0x14, 0x15

ACC_BITS = 44


def wrap(v):
    v &= (1 << ACC_BITS) - 1
    return v - (1 << ACC_BITS) if v & (1 << (ACC_BITS - 1)) else v


class Alu:
    """THE UNIFORM ALU.

        L    := src[ lo12[10:6] ]   07 mem[ptr]  10 acc  19 tempA  1A tempB
        if hi12 bit 4:  mem[ptr] <- acc ; acc := 0      (store AND CLEAR)
        acc  += P ; P := 0                              (P is CONSUMED)
        lo12[4:0]:  13 -> tempA <- L  14 -> tempB <- L  07 -> mem[ptr] <- L
        if class4 == A:  P := coef[cursor++] * L
        if class4 & 7 == 2:  ptr += (s8)addr8

    Only PSH + ASH == 22 is forced (the coefficient Q formats force it); the
    split is not, and 2..12 are numerically identical.
    """

    def __init__(self, psh=6, shift_on='srcB', clear_on_store=True, total=22,
                 accop='uniform'):
        self.psh = psh
        self.ash = total - psh
        self.shift_on = shift_on            # 'srcB' | 'capB' | 'none'
        self.clear = clear_on_store
        # 'uniform' : acc += P on every word, P consumed by the add
        # 'f31'     : P is NOT consumed and hi12[3:1] selects the accumulator
        #             op (0 -> acc <- P, 1 -> acc += P, 2 -> neither).  The two
        #             are numerically IDENTICAL on the biquad -- see the note's
        #             sect. 7-A8 -- and this switch is here to prove it.
        self.accop = accop

    def datum(self, acc):
        v = acc >> self.ash if self.ash else acc
        return 0x7FFFFF if v > 0x7FFFFF else (-0x800000 if v < -0x800000 else v)

    def run(self, cram, xs):
        mem = [0] * 8
        acc = P = 0
        T = [0, 0]
        out = []
        for x in xs:
            # THE BAND INPUT ARRIVES IN THE ACCUMULATOR.  In the real cascade it
            # arrives in the product register TOO, because the previous band's
            # last word did `acc <- P' without clearing P; the 'f31' variant
            # depends on that and the 'uniform' one must not see it twice.
            acc = x << self.ash
            if self.accop != 'uniform':
                P = x << self.ash
            p = cur = 0
            for w in SECTION:
                hi, c4, ad, lo = flds(w)
                sel, nib = (lo >> 6) & 0x1F, lo & 0x1F

                if sel == SRC_ACC:
                    L = self.datum(acc)
                elif sel == SRC_TA:
                    L = T[0]
                elif sel == SRC_TB:
                    L = (T[1] >> 1) if self.shift_on == 'srcB' else T[1]
                elif sel == SRC_MEM:
                    L = mem[p]
                else:
                    raise RuntimeError("unanchored SRC %02X" % sel)

                if hi & 0x010:
                    mem[p] = self.datum(acc)
                    if self.clear:
                        acc = 0

                if self.accop == 'uniform':
                    acc = wrap(acc + P)
                    P = 0
                else:
                    f31 = (hi >> 1) & 7
                    if f31 == 0:
                        acc = wrap(P)
                    elif f31 == 1:
                        acc = wrap(acc + P)
                    # f31 == 2 (the class-8 word): neither

                if nib == ACT_CAP_TA:
                    T[0] = L
                elif nib == ACT_CAP_TB:
                    T[1] = (L >> 1) if self.shift_on == 'capB' else L
                elif nib == ACT_ST_BUS:
                    mem[p] = L

                if c4 == 0xA:
                    P = wrap((s24(cram[cur]) * L) >> self.psh)
                    cur += 1
                if (c4 & 7) == 2:
                    p += (ad - 256 if ad & 0x80 else ad)
            out.append(self.datum(acc))
        return out


# ---------------------------------------------------------------------------
# the reference: the biquad the coefficients DESCRIBE
#   C-RAM[+0..+5] = b1, b0, b2, A1, A2, make-up ; A2 is Q0.23, the rest Q1.22
#   (MEASURED from the firmware's own scale constants, biquad-coeffs.md sect. 4)
# ---------------------------------------------------------------------------
def ideal_H(cram, f, fs=44100.0):
    b1, b0, b2 = (s24(cram[i]) / 2.0**22 for i in (0, 1, 2))
    A1 = s24(cram[3]) / 2.0**22
    A2 = s24(cram[4]) / 2.0**23
    G = s24(cram[5]) / 2.0**22
    z = cmath.exp(-2j * math.pi * f / fs)
    return G * (b0 + b1 * z + b2 * z * z) / (1 - A1 * z - A2 * z * z)


FREQS = [20, 50, 100, 200, 400, 800, 1600, 3150, 6300, 10000, 16000, 20000]


def dft_at(xs, f, fs=44100.0):
    w = -2j * math.pi * f / fs
    return sum(x * cmath.exp(w * n) for n, x in enumerate(xs))


def banks(rom, algo):
    flat, base0 = [], None
    for base, ws in M.sbank(rom, algo):
        if base is None:
            continue
        if base0 is None:
            base0 = base
        while len(flat) < base - base0:
            flat.append(0)
        flat.extend(ws)
    return [flat[s:s + 6] for s in BLOCK_STARTS.get(algo, []) if s + 6 <= len(flat)]


def all_banks(rom):
    out = []
    for algo, name in ((39, "algo39 PARAMETRIC EQ"), (33, "algo33 OVERDRIVE tone"),
                       (35, "algo35 EXCITER band"), (99, "algo99 PEQ+OVERDR+DELAY")):
        for i, b in enumerate(banks(rom, algo)):
            out.append(("%s band %d" % (name, i), b))
    return out


def measure(alu, cram, nimp=4096, amp=1 << 22):
    ir = alu.run(cram, [amp] + [0] * (nimp - 1))
    out = []
    for f in FREQS:
        want = ideal_H(cram, f)
        if abs(want) < 1e-9:
            continue
        got = dft_at(ir, f) / amp
        if abs(got) == 0.0:
            out.append((f, -999.0, 180.0))      # a total failure is a result
            continue
        out.append((f, 20 * math.log10(abs(got) / abs(want)),
                    math.degrees(cmath.phase(got / want))))
    return out


# ---------------------------------------------------------------------------
def sect_verify(rom):
    print("=== ACCEPTANCE TEST -- the modelled section vs the transfer function the")
    print("    firmware's own bilinear designer describes.  Impulse 2^22, 4096 samples,")
    print("    DFT at %d frequencies 20 Hz .. 20 kHz.\n" % len(FREQS))
    alu = Alu()
    seen, worst = {}, 0.0
    for name, b in all_banks(rom):
        e = measure(alu, b)
        md = max(abs(d) for _, d, _ in e)
        mp = max(abs(p) for _, _, p in e)
        worst = max(worst, md)
        dup = seen.get(tuple(b))
        print("   %-26s max |err| = %8.5f dB  %7.4f deg%s"
              % (name, md, mp, "   (same bank as %s)" % dup if dup else ""))
        seen.setdefault(tuple(b), name)
    print("\n   distinct coefficient banks : %d" % len(seen))
    print("   WORST over all of them     : %.5f dB" % worst)

    print("\n   the residual is QUANTISATION, and here is the evidence: on the worst")
    print("   bank the error falls monotonically with signal level.")
    b = max(all_banks(rom), key=lambda nb: max(abs(d) for _, d, _ in measure(alu, nb[1])))[1]
    for bits in (10, 14, 18, 22):
        e = measure(alu, b, amp=1 << bits)
        print("      impulse 2^%-2d : %8.5f dB" % (bits, max(abs(d) for _, d, _ in e)))


def sect_ablate(rom):
    print("=== ABLATIONS -- a criterion that cannot fail is not a pass\n")
    bl = [b for _, b in all_banks(rom)]

    def worst(alu):
        return max(abs(d) for b in bl for _, d, _ in measure(alu, b, nimp=2048))

    rows = [("full model (total alignment 22, split 6/16)", Alu()),
            ("without the accumulator CLEAR on hi12 bit 4", Alu(clear_on_store=False)),
            ("with the one-bit shift on the tempB CAPTURE", Alu(shift_on='capB')),
            ("without the one-bit shift at all", Alu(shift_on='none')),
            ("total alignment 21 instead of 22", Alu(total=21)),
            ("total alignment 23 instead of 22", Alu(total=23)),
            ("a DIFFERENT split of the same total (2/20)", Alu(psh=2)),
            ("a DIFFERENT split of the same total (12/10)", Alu(psh=12)),
            ("ALT: hi12[3:1] selects the accumulator op", Alu(accop='f31')),
            ("ALT above, but WITHOUT the bit-4 clear", Alu(accop='f31', clear_on_store=False))]
    for tag, alu in rows:
        print("   %-46s %10.5f dB" % (tag, worst(alu)))


def sect_sweep(rom):
    print("=== THE PRODUCT-SHIFT SPLIT.  Only the TOTAL (22) is forced.\n")
    bl = [b for _, b in all_banks(rom)]
    for psh in range(0, 23):
        alu = Alu(psh=psh)
        w = max(abs(d) for b in bl for _, d, _ in measure(alu, b, nimp=1024))
        print("   PSH=%2d ASH=%2d   %12.5f dB" % (psh, 22 - psh, w))


def sect_fields(rom):
    """Census of the lo12 sub-fields over the whole extracted corpus."""
    print("=== lo12 SUB-FIELD CENSUS over every distinct microprogram\n")
    # the five streams that parse to no valid I-RAM image are excluded, exactly
    # as kn5000-roms-disasm/dsp/tools/gen_dsp_disasm.py excludes them
    MALFORMED = {79, 88, 89, 90, 91}
    r = E.Rom(rom)
    seen_img, words = set(), []
    for algo in range(100):
        if algo in MALFORMED:
            continue
        try:
            iram, _c, _o = E.parse_stream(r, r.u32le(E.ALGO_TABLE + 4 * algo))
        except Exception:
            continue
        img = []
        for _addr, ws, _n in iram:
            img.extend(int.from_bytes(b, 'big') & 0xFFFFFFFFF for b in ws)
        key = tuple(img)
        if not img or key in seen_img:
            continue                        # count each DISTINCT image once
        seen_img.add(key)
        words.extend(img)
    if not words:
        print("   (no images parsed -- is this the right sub ROM?)")
        return
    print("   %d words over %d distinct images\n" % (len(words), len(seen_img)))

    src = collections.Counter()
    act = collections.Counter()
    fam = collections.defaultdict(collections.Counter)
    ptr = collections.Counter()
    for w in words:
        hi, c4, ad, lo = flds(w)
        if (lo >> 5) & 1:
            ptr[lo] += 1
            continue
        src[(lo >> 6) & 0x1F] += 1
        act[lo & 0x1F] += 1
        fam[(lo >> 6) & 3][c4] += 1
    print("   bit 5 = the POINTER/CURSOR MODE bit -- %d words, %d values:"
          % (sum(ptr.values()), len(ptr)))
    print("      %s" % " ".join("%03X(%d)" % kv for kv in sorted(ptr.items())))

    ANCH = {0x07: "mem[ptr]", 0x10: "acc", 0x19: "tempA", 0x1A: "tempB"}
    print("\n   lo12[10:6] = the OPERAND SOURCE SELECT (%d codes):" % len(src))
    for k, n in src.most_common():
        print("      %02X %5d   %s" % (k, n, ANCH.get(k, "")))
    AACT = {0x07: "mem[ptr] <- bus", 0x12: "(none)", 0x13: "tempA <- bus",
            0x14: "tempB <- bus", 0x15: "(none)"}
    print("\n   lo12[4:0] = the ACTION (%d codes):" % len(act))
    for k, n in act.most_common():
        print("      %02X %5d   %s" % (k, n, AACT.get(k, "")))
    NAMES = {0: "...00 acc fam", 1: "...01 tempA fam",
             2: "...10 tempB fam", 3: "...11 mem fam"}
    print("\n   grouped by the LOW TWO bits of the source (comparable with the anchors):")
    for k in sorted(fam):
        print("      %-16s %5d   %s" % (NAMES[k], sum(fam[k].values()),
              " ".join("cls%X:%d" % kv for kv in sorted(fam[k].items()))))


SECTIONS = {"verify": sect_verify, "ablate": sect_ablate,
            "sweep": sect_sweep, "fields": sect_fields}


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    rom = sys.argv[1]
    want = sys.argv[2:] or ["verify", "ablate"]
    for name in want:
        fn = SECTIONS.get(name)
        if fn is None:
            sys.exit("unknown section %r (have: %s)" % (name, " ".join(SECTIONS)))
        fn(rom)
        print()


if __name__ == "__main__":
    main()

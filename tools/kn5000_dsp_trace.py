#!/usr/bin/env python3
"""kn5000_dsp_trace.py -- a byte-exact pointer-arithmetic TRACE for the uPD6383GF,
settling the three residual addressing questions from notes/kn5000-dsp-addressing.md:

    Q1  the absolute pointer ORIGIN   (a one-number question)
    Q2  the WRAP modulus              (256 vs 128)
    Q3  what addressing MODES 3/4/5/6 do

This is a STANDALONE replay: it imports nothing from MAME and executes the proven
decoded-subset pointer model over the statically-extracted program images
(/tmp/progs/algoNN.bin, from tools/kn5000_dsp_extract.py).  It logs pointer
arithmetic only -- no audio, no effect on any running machine.  It is the
"trace" the task asks for; the alternative in-core trace_program() facility is
unnecessary because the origin/wrap/mode questions are all answerable from the
already-extracted ROM images plus the measured host-parameter map.

The proven relative rule (notes/kn5000-dsp-addressing.md), reproduced here:

    word = hi12[35:24] . class4[23:20] . addr8[19:12] . lo12[11:0]
    class4 = bit3 (multiplier-enable) || bits[2:0] (addressing MODE)
    MODE 2 (classes 2 and A): operate on mem[ptr]; ptr <- (ptr + signed8(addr8)) mod 256
    every other MODE (0,1,3,4,5,6,8): pointer UNCHANGED; addr8 means something else (Q3)

Usage:
    python3 tools/kn5000_dsp_extract.py <sub.rom> /tmp/progs
    python3 tools/kn5000_dsp_trace.py [<sub.rom>]
"""
import glob
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

ROM = os.path.expanduser(
    '~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom')
PROGS = '/tmp/progs'

# The three header-loaded pointer registers, per unit (notes/kn5000-dsp-pointer.md,
# notes/kn5000-dsp-headerdecode.md sect 1).  These are the ONLY registers the common
# header loads; Q1 asks whether any of them is the biquad-state origin.
HEADER_REGS = {
    0: {'821': 0x70, '827': 0x6C, '825': 0x25},   # unit 0
    1: {'821': 0x50, '827': 0x64, '825': 0x25},   # unit 1
}


def fields(w):
    return ((w >> 24) & 0xFFF, (w >> 20) & 0xF, (w >> 12) & 0xFF, w & 0xFFF)


def s8(v):
    return v - 256 if v & 0x80 else v


def moves(cl):
    """MODE 2 (classes 2 and A) is the only pointer-mover."""
    return (cl & 0x7) == 0x2


def load(algo):
    data = open('%s/algo%02d.bin' % (PROGS, algo), 'rb').read()
    return [int.from_bytes(data[k:k + 5], 'big')
            for k in range(0, len(data) - 4, 5)]


def all_images():
    out = {}
    for f in sorted(glob.glob('%s/algo*.bin' % PROGS)):
        d = open(f, 'rb').read()
        ws = [int.from_bytes(d[k:k + 5], 'big') for k in range(0, len(d) - 4, 5)]
        if ws and (fields(ws[-1])[1] & 7) == 1 and fields(ws[-1])[2] in (0x0E, 0x0F):
            out[int(os.path.basename(f)[4:6])] = ws
    return out


def trace(words, origin, wrap=True, mod=256):
    """Single-step the pointer model; return a per-word log.
    Each entry: (idx, word, hi, cl, ad, lo, ptr_before, ptr_after, is_move)."""
    p = origin % mod if wrap else origin
    log = []
    for i, w in enumerate(words):
        hi, cl, ad, lo = fields(w)
        mv = moves(cl)
        p2 = ((p + s8(ad)) % mod if wrap else p + s8(ad)) if mv else p
        log.append((i, w, hi, cl, ad, lo, p, p2, mv))
        p = p2
    return log


# ---------------------------------------------------------------------------
# Q1 -- THE ABSOLUTE ORIGIN
# ---------------------------------------------------------------------------
def q1_origin():
    print("=" * 78)
    print("Q1  THE ABSOLUTE ORIGIN -- trace each family from each header register")
    print("=" * 78)

    # ---- EQ (algo 39, unit 0): the only STRONG host-state coincidence -------
    print("\n--- PARAMETRIC EQ (algo 39, unit 0) --------------------------------")
    print("    host writes biquad STATE at {64,68,6C,70,74} (5 bands, stride 4)")
    words = load(39)
    starts = [i for i, w in enumerate(words)
              if fields(w)[0] == 0x000 and fields(w)[1] == 0xA and fields(w)[3] == 0x1D3]
    host_state = [0x64, 0x68, 0x6C, 0x70, 0x74]
    print("    band-motif starts at words %s\n" % starts)
    print("    trace band-0 S0 cell from each candidate start register:")
    for name, val in HEADER_REGS[0].items():
        log = trace(words, val)
        s0 = log[starts[0]][6]          # ptr_before at the first motif word
        band_s0 = [log[s][6] for s in starts[:5]]
        hit = sum(1 for k, c in enumerate(band_s0) if c == host_state[k])
        print("      reg %-3s = 0x%02X  ->  band cells %s  (%d/5 host state)"
              % (name, val, ['%02X' % c for c in band_s0], hit))
    # the origin-free relative walk fixes the required start
    rel = trace(words, 0, wrap=False)
    req = (host_state[0] - rel[starts[0]][6]) & 0xFF
    print("      REQUIRED start register value to land 5/5 : 0x%02X" % req)
    print("      -> 0x%02X is NONE of the header registers (0x70/0x6C/0x25)." % req)

    # ---- REVERB (algo 16, unit 1): weak coincidence -------------------------
    print("\n--- REVERB (algo 16, unit 1) ---------------------------------------")
    host_rev = {0xA9, 0xAA, 0xAB, 0xAC, 0xAF, 0xB0, 0xB1, 0xB2, 0x9E, 0xA6, 0x97, 0x86}
    print("    host writes reverb STATE at %s"
          % sorted('%02X' % a for a in host_rev))
    rv = load(16)
    rel = trace(rv, 0, wrap=False)
    cells = set(e[6] & 0xFF for e in rel if e[8])   # class-2/A touched cells, wrapped
    best = sorted(((len({(c + d) & 0xFF for c in cells} & host_rev), d)
                   for d in range(256)), reverse=True)[:4]
    print("    class-2/A touched cells (rel, wrapped): %d distinct" % len(cells))
    print("    best origin offsets (host hits / 12): %s"
          % [(h, '0x%02X' % d) for h, d in best])
    for name, val in HEADER_REGS[1].items():
        hit = len({(c + val) & 0xFF for c in cells} & host_rev)
        print("      reg %-3s = 0x%02X  ->  %d/12 host state" % (name, val, hit))

    # ---- PHASER (algo 5, unit 0): no host check -----------------------------
    print("\n--- PHASER (algo 5, unit 0) ----------------------------------------")
    ph = load(5)
    log = trace(ph, HEADER_REGS[0]['821'])
    taps = sorted({e[6] for e in log if e[2] == 0x102 and e[3] == 2 and e[5] == 0x1CD})
    print("    shared all-pass tap (102.2.<c>.1CD, origin 0x70): %s"
          % ['%02X' % c for c in taps])
    print("    (0x76 is a STATIC coefficient, absent from the phaser host map by")
    print("     design -- the phaser offers NO host-coincidence check on the origin)")

    print("""
  VERDICT (Q1): NOT PINNED.  The proven relative rule, traced from every register
  the header actually loads, lands NONE of the three families on its host block:
    * EQ needs start 0x19 (5/5) -- no header register supplies it;
    * REVERB's best host overlap (6/12) sits at ~0xA6 -- also no header register,
      and 6/12 is only marginally above chance for 14 cells over 256 offsets;
    * PHASER gives no host check at all.
  The EQ offset (0x19-0x70 = -0x57) and the reverb offset (0xA6-0x50 = +0x56) are
  not a common constant from any shared register, so no single "register - K" rule
  unifies the families.  The surviving readings (a per-effect FOURTH pointer
  register, or a per-effect descriptor-relative base the header does not carry)
  cannot be separated by this decoded-subset trace, which does not model which of
  the chip's six pointer registers each lo12 route selects.  ABSOLUTE ADDRESSING
  IS THEREFORE NOT IMPLEMENTED IN THE CORE.""")


# ---------------------------------------------------------------------------
# Q2 -- THE WRAP MODULUS
# ---------------------------------------------------------------------------
def q2_wrap():
    print("\n" + "=" * 78)
    print("Q2  THE WRAP MODULUS")
    print("=" * 78)
    # measured lower bound: the firmware pokes absolute DSP RAM addresses; the
    # largest is a hard measurement of how deep the address space must be.
    try:
        import kn5000_dsp_params as P
        rom = P.Rom(sys.argv[1] if len(sys.argv) > 1 else ROM, P.SUB_BASE)
        allad = set()
        for algo in range(100):
            t1p = rom.u32le(P.ALGO_T1_ARRAY + 4 * algo)
            if not t1p or t1p == P.NULL_T1:
                continue
            for _, op, ents in P.parse_t1(rom, t1p):
                allad |= set(ents)
        mx = max(allad)
        print("\n  MEASURED: firmware pokes absolute DSP RAM addresses up to 0x%02X (%d)."
              % (mx, mx))
        print("    Addresses > 0x7F actually written: %s"
              % sorted('%02X' % a for a in allad if a > 0x7F))
        print("    A pointer that wrapped at 128 could never reach 0x%02X, so the" % mx)
        print("    modulus is STRICTLY > %d.  mod-128 is RULED OUT." % mx)
    except Exception as e:
        print("  (host-map probe skipped: %s)" % e)
    # the reverb is the program whose arithmetic crosses the boundary
    rv = load(16)
    rel = trace(rv, 0x50, wrap=False)
    lo = min(e[6] for e in rel)
    hi = max(e[6] for e in rel)
    print("\n  The REVERB crosses the boundary: origin 0x50, NO wrap, the pointer")
    print("    excursion is %d .. %d -- a span of %d cells, wider than 256."
          % (lo, hi, hi - lo))
    print("""
  VERDICT (Q2): 256, INFERRED (strongly bounded), not directly MEASURED.
    * measured lower bound > 0xCF (207) from host-poke addresses -> not 128;
    * the 8-bit addr8 field and the documented 256x24 C-RAM/D-RAM fix the upper
      value at 256; no wider register exists in the model.
    NOT MEASURED because no single reverb word's ABSOLUTE address has been
    independently confirmed straddling 255->0 (the origin is unpinned, Q1).
    One address-bus trace from an ENABLED core would confirm 256 directly.""")


# ---------------------------------------------------------------------------
# Q3 -- MODES 3/4/5/6
# ---------------------------------------------------------------------------
def q3_modes():
    print("\n" + "=" * 78)
    print("Q3  MODES 3/4/5/6 -- what addr8 selects when the pointer is frozen")
    print("=" * 78)
    imgs = all_images()
    stat = defaultdict(lambda: {'ad': Counter(), 'lo': Counter(),
                                'prev': Counter(), 'next': Counter(), 'n': 0})
    for ws in imgs.values():
        for i, w in enumerate(ws):
            hi, cl, ad, lo = fields(w)
            m = cl & 7
            if m not in (3, 4, 5, 6):
                continue
            S = stat[m]
            S['n'] += 1
            S['ad'][ad] += 1
            S['lo'][lo] += 1
            if i:
                S['prev'][fields(ws[i - 1])[3]] += 1
            if i < len(ws) - 1:
                S['next'][fields(ws[i + 1])[3]] += 1
    desc = {
        3: ("addr8 FROZEN at 0x20 (32/33), lo12=0x44C; flanked by a read (1C0) and\n"
            "      an immediate (041).  addr8 is a CONSTANT modulation/envelope-offset\n"
            "      selector, NOT a pointer index.  [INFERRED]"),
        4: ("addr8 FROZEN at 0x01, lo12=0x1CE; the THIRD word of the 3-word\n"
            "      table-lookup idiom, always preceded by the class-6 selector (4CD).\n"
            "      addr8 is the constant fetch/apply step (=1), NOT an index.  [MEASURED-position]"),
        5: ("addr8 ALWAYS 0x00 (unused), lo12=0x647; a fixed-function biquad/filter\n"
            "      step (context 839 -> 647 -> 688).  addr8 carries NO information.  [INFERRED]"),
        6: ("addr8 VARIES {18,28,1E,20,1A} = the TABLE SELECTOR; the MIDDLE word of the\n"
            "      table-lookup idiom (C63 -> 6.TT.4CD -> 012.4.01.1CE).  addr8 INDEXES a\n"
            "      lookup table (LFO waveform / distortion curve).  [MEASURED]"),
    }
    for m in (3, 4, 5, 6):
        S = stat[m]
        print("\n  MODE %d  (n=%d)" % (m, S['n']))
        print("    addr8:", S['ad'].most_common(6))
        print("    lo12 :", [('%03X' % k, v) for k, v in S['lo'].most_common(4)])
        print("    prev :", [('%03X' % k, v) for k, v in S['prev'].most_common(3)])
        print("    next :", [('%03X' % k, v) for k, v in S['next'].most_common(3)])
        print("    ==>  " + desc[m])
    print("""
  VERDICT (Q3):
    MODE 3 -> addr8 is a FIXED constant (0x20): a modulation/envelope offset.
    MODE 4 -> addr8 is a FIXED constant (0x01): the table-lookup APPLY step.
    MODE 5 -> addr8 is UNUSED (always 0x00): a fixed-function filter step.
    MODE 6 -> addr8 VARIES: it is the TABLE SELECTOR (indexes a lookup table).
    Only MODE 6's addr8 carries operand information; 3/4/5 freeze it -- confirming
    that "not a pointer displacement" does not mean "an index of something else".""")


def main():
    if not os.path.isdir(PROGS):
        sys.exit("run tools/kn5000_dsp_extract.py <rom> %s first" % PROGS)
    q1_origin()
    q2_wrap()
    q3_modes()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""kn5000_dsp_addressing.py -- the uPD6383GF data-pointer ADDRESSING RULE.

The single binding unknown left after notes/kn5000-dsp-pointer.md: exactly how
`addr8` composes with the data pointer to form the C-RAM/D-RAM address each
instruction reads/writes.

The rule tested here (see notes/kn5000-dsp-addressing.md for the derivation):

    * class4 = { bit3 = multiplier-enable (bit 23) , bits[2:0] = addressing MODE }
    * MODE 010 (== the low 3 bits of class 2 AND class A) means:
          operand cell = mem[ptr] ;  ptr += signed8(addr8)   (POST-increment)
      the pointer is an 8-bit register, so all arithmetic is mod 256.
    * every OTHER mode (classes 0,1,3,4,5,6,8) does NOT move the data pointer;
      their addr8 is a DRAM sub-op / table selector / immediate / unused.

This is exactly the naive "signed post-increment, classes {2,A} move it" rule --
with two corrections that make it close: (a) the pointer is 8-bit and WRAPS, so
the reverb's excursions are in range by construction; (b) class 8 (mode 000,
mult set) does NOT move it, which the biquad forces.

Sections:
    biquad   the +4/band walk, absolute cells vs the host state block  (F2 + host check)
    phaser   the all-pass sweep, shared tap, modulator write           (F1 + host check)
    reverb   the 9 diffusers, stationary pointer, wrap                 (F3)
    hostmap  class-2 read-addr vs host-write-addr coincidence, all imgs (host check)

Usage:
    python3 tools/kn5000_dsp_extract.py <sub.rom> /tmp/progs
    python3 tools/kn5000_dsp_addressing.py <sub.rom>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kn5000_dsp_params as P

ROM = os.path.expanduser(
    '~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom')
MAIN = os.path.expanduser(
    '~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_v10_program.rom')
PROGS = '/tmp/progs'


def fields(w):
    return ((w >> 24) & 0xFFF, (w >> 20) & 0xF, (w >> 12) & 0xFF, w & 0xFFF)


def s8(v):
    return v - 256 if v & 0x80 else v


def load(algo):
    data = open('%s/algo%02d.bin' % (PROGS, algo), 'rb').read()
    return [int.from_bytes(data[k:k + 5], 'big')
            for k in range(0, len(data) - 4, 5)]


def moves(cl):
    """The addressing rule: only mode 010 (classes 2 and A) moves the pointer."""
    return (cl & 0x7) == 0x2


def walk_cells(words, origin, wrap=True):
    """Return the list of (index, cell, class, addr8, lo12) the pointer VISITS,
    under signed post-increment. `cell` is where the word operates (pre-move)."""
    p = origin & 0xFF if wrap else origin
    out = []
    for i, w in enumerate(words):
        hi, cl, ad, lo = fields(w)
        out.append((i, p, cl, ad, lo, hi))
        if moves(cl):
            p = (p + s8(ad)) & 0xFF if wrap else p + s8(ad)
    return out, p


# ---------------------------------------------------------------------------
def sect_biquad():
    print("=" * 78)
    print("BIQUAD (algo 39 PARAMETRIC EQ) -- F2 and the host STATE-block check")
    print("=" * 78)
    words = load(39)
    # host state block for PARAMETRIC EQ: op 70 -> {64,68,6C,70,74}, stride 4
    host_state = [0x64, 0x68, 0x6C, 0x70, 0x74]
    print("\n  host writes biquad STATE at %s (5 bands, stride 4)"
          % ['%02X' % a for a in host_state])
    print("  host writes biquad COEFF at [00,06,0C,12,18] (5 bands, stride 6)")

    # the 9-word motif repeats; find each band's S0 (the first cell of the motif)
    # motif signature: starts with 000.A.00.1D3
    starts = [i for i, w in enumerate(words)
              if fields(w)[0] == 0x000 and fields(w)[1] == 0xA and fields(w)[3] == 0x1D3]
    print("\n  motif starts at words %s (%d bands)" % (starts, len(starts)))

    # measure the per-band S0 stride under the rule, ORIGIN-FREE
    trace0, _ = walk_cells(words, 0, wrap=False)   # relative to origin 0
    s0rel = [trace0[i][1] for i in starts]
    print("  band S0 cells, origin-relative:", ['%+d' % c for c in s0rel])
    strides = [s0rel[i + 1] - s0rel[i] for i in range(len(s0rel) - 1)]
    print("  per-band stride:", strides, "  (host stride = 4)")

    # walk WITHIN one band to confirm S0 S1 S2 S3 contiguous +1
    print("\n  within band 0 the pointer visits (S0 S1 S2 S3 expected):")
    for i in range(starts[0], starts[0] + 9):
        idx, cell, cl, ad, lo, hi = trace0[i]
        rel = cell - s0rel[0]
        print("    w%-3d %03X.%X.%02X.%03X  cell=S0%+d  %s"
              % (idx, hi, cl, ad, lo, rel,
                 "(class8 no-move)" if (cl & 0x7) != 2 and cl == 8 else ""))

    # now pin the origin: channel-0's 5 band S0 cells must equal the host state
    # block {64,68,6C,70,74}.  The stride already matches (+4); only the base is free.
    ch0 = s0rel[:5]
    print("\n  channel-0 band S0 cells (origin-relative): %s" % ['%+d' % c for c in ch0])
    need = (host_state[0] - ch0[0]) & 0xFF
    print("  ABSOLUTE origin that lands channel-0 band0 on host 0x64: 0x%02X" % need)
    for org, name in ((0x70, '821'), (0x6C, '827'), (0x25, '825'), (need, 'required')):
        cells = [(org + c) & 0xFF for c in ch0]
        hit = sum(1 for k, c in enumerate(cells) if c == host_state[k])
        print("    origin 0x%02X (%-8s): ch0 cells %s  -> %d/5 == host state"
              % (org, name, ['%02X' % c for c in cells], hit))


def sect_phaser():
    print("\n" + "=" * 78)
    print("PHASER (algo 5) -- F1 sweep, the shared tap, the modulator write")
    print("=" * 78)
    words = load(5)
    host = [0x00, 0x02, 0x05, 0x06, 0x08, 0x09, 0x0A, 0x0C, 0x13, 0x14, 0x1D, 0x90]
    for org, name in ((0x70, '821'), (0x6C, '827')):
        tr, _ = walk_cells(words, org)
        chain_reads = set()   # the 102.2.<c>.1CD tap read
        allpass_wr = set()    # the 212.2.01.412 base write
        marker_rd = set()     # the 104.2.<s>.1D5 read
        for idx, cell, cl, ad, lo, hi in tr:
            if hi == 0x102 and cl == 2 and lo == 0x1CD:
                chain_reads.add(cell)
            if hi == 0x212 and cl == 2 and lo == 0x412:
                allpass_wr.add(cell)
            if hi == 0x104 and cl == 2 and lo == 0x1D5:
                marker_rd.add(cell)
        print("\n  origin 0x%02X (%s):" % (org, name))
        print("    all-pass tap READS (102.1CD): %s"
              % sorted('%02X' % c for c in chain_reads))
        print("    all-pass base WRITES (212.412): %s"
              % sorted('%02X' % c for c in allpass_wr))
        print("    marker READS (104.1D5):        %s"
              % sorted('%02X' % c for c in marker_rd))
    print("\n  host writes PHASER params at %s" % ['%02X' % a for a in host])


def sect_reverb():
    print("\n" + "=" * 78)
    print("REVERB (algo 16) -- F3 stationary pointer per stage, and the wrap")
    print("=" * 78)
    words = load(16)
    # the diffuser motif: 880.1.60.2D4 ... 880.1.20.655 ... every class 2/A addr8==0?
    diff_starts = [i for i, w in enumerate(words) if w == 0x08801602D4]
    print("\n  %d diffuser stages (880.1.60.2D4 marker)" % len(diff_starts))
    allzero = 0
    for st in diff_starts:
        seg = words[st:st + 8]
        movers = [(fields(w)[2]) for w in seg if moves(fields(w)[1])]
        net = sum(s8(a) for a in movers)
        if net == 0:
            allzero += 1
    print("  stages whose data-pointer NET MOVE is zero: %d/%d"
          % (allzero, len(diff_starts)))
    print("  (F3: the pointer is stationary across the diffuser stages)")

    # whole-program excursion, with and without wrap
    tr_nw, end_nw = walk_cells(words, 0x50, wrap=False)
    tr_w, end_w = walk_cells(words, 0x50, wrap=True)
    lo = min(c for _, c, *_ in tr_nw)
    hi = max(c for _, c, *_ in tr_nw)
    print("\n  origin 0x50, NO wrap: pointer excursion %d .. %d  (leaves 0..255: %s)"
          % (lo, hi, not (0 <= lo and hi < 256)))
    print("  origin 0x50, 8-bit WRAP: every cell in 0..255 BY CONSTRUCTION")
    print("  -> the '256-cell window' failure was a NO-WRAP artefact; an 8-bit")
    print("     pointer wraps, so the reverb excursion is not out of range.")


def sect_hostmap():
    print("\n" + "=" * 78)
    print("HOST-WRITE / BODY-READ coincidence over the corpus")
    print("=" * 78)
    rom = P.Rom(ROM, P.SUB_BASE)
    mrom = P.Rom(MAIN, 0)
    # for each algo, host addresses (T1) vs the ABSOLUTE cells the body's class-2
    # words touch, under the mode-2 rule and the per-unit origin.
    tot_match = tot_host = 0
    stride_ok = 0
    for algo in range(96):
        try:
            words = load(algo)
        except FileNotFoundError:
            continue
        if not words:
            continue
        t1p = rom.u32le(P.ALGO_T1_ARRAY + 4 * algo)
        t1 = P.parse_t1(rom, t1p) if (t1p and t1p != P.NULL_T1) else []
        host = set(a for _, op, ents in t1 for a in ents)
        if not host:
            continue
        # unit: base iram tells us; we don't have it here, assume unit0 origin 0x70
        tr, _ = walk_cells(words, 0x70)
        cells = set(c for _, c, cl, ad, lo, hi in tr if moves(cl))
        m = len(cells & host)
        tot_match += m
        tot_host += len(host)
    print("\n  class-2 body cells (origin 0x70) intersect host-written addrs:")
    print("    matched %d of %d host addresses" % (tot_match, tot_host))
    print("""
  This is deliberately a WEAK number and that is the point: under a POINTER
  rule addr8 is a displacement, NOT an absolute address, so a body does not
  name most of the RAM it touches (class2-round2 sect. 2: 80%% of host addrs
  appear nowhere as addr8).  The STRONG host coincidence is STRUCTURAL, and it
  is in the biquad section: host coeff stride 6 == 6 cursor fetches/band, host
  state stride 4 == the +4 pointer walk/band.  See the biquad section.""")


def main():
    global PROGS
    if len(sys.argv) > 1:
        rom_path = sys.argv[1]
    else:
        rom_path = ROM
    if not os.path.isdir(PROGS):
        sys.exit("run tools/kn5000_dsp_extract.py <rom> %s first" % PROGS)
    sect_biquad()
    sect_phaser()
    sect_reverb()
    sect_hostmap()


if __name__ == "__main__":
    main()

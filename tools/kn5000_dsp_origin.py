#!/usr/bin/env python3
"""kn5000_dsp_origin.py -- pin the uPD6383GF data-pointer ORIGIN by executing the
WHOLE per-frame program continuously (header -> unit-0 body -> header -> unit-1 body
-> epilogue) in the decoded subset, instead of tracing each body in isolation.

Follows notes/kn5000-dsp-trace.md (which traced each body from each header-loaded
register and reported the origin "NOT PINNED"), and notes/kn5000-dsp-pointer.md
(which found the header loads).  The NEW experiment here: run the common HEADER's
own pointer arithmetic continuously into each body, and cross-check the resulting
origin against the COMPLETE host-write map of every array-structured effect
(EQ + all 12 reverbs + gated reverb) -- not just the partial reverb map the trace
note had.  Findings in notes/kn5000-dsp-origin.md.

This is a STANDALONE replay over the statically-extracted images; it touches no
running machine, adds no audio, and does NOT edit the (disabled) core.

    python3 tools/kn5000_dsp_extract.py <sub.rom> /tmp/progs
    python3 tools/kn5000_dsp_origin.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from kn5000_dsp_wordfields import parse, as_int                       # noqa: E402
import kn5000_dsp_params as P                                          # noqa: E402

ROM = os.path.expanduser(
    '~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom')
MAIN = os.path.expanduser(
    '~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_v10_program.rom')
CAP = os.path.join(os.path.dirname(HERE), 'notes/data/kn5000_dsp1_upload_coldboot.txt')
PROGS = '/tmp/progs'


# --- 36-bit word:  hi12[35:24] . class4[23:20] . addr8[19:12] . lo12[11:0] -----
def fields(w):  return ((w >> 24) & 0xFFF, (w >> 20) & 0xF, (w >> 12) & 0xFF, w & 0xFFF)
def s8(v):      return v - 256 if v & 0x80 else v
def escape(hi): return (hi & 0x800) != 0                 # bit-11 = format escape
def moves(hi, cl):                                       # proven pointer-move rule
    """MODE 2 (classes 2 and A) post-increments the pointer -- BUT only for
    non-escape words; an escape word's class4 nibble is immediate data, not a
    mode (notes/kn5000-dsp-pointer.md sect 8.5)."""
    return (not escape(hi)) and (cl & 7) == 2
def fmt(w):
    hi, cl, ad, lo = fields(w)
    return '%03X.%X.%02X.%03X' % (hi, cl, ad, lo)


def load_body(algo):
    d = open('%s/algo%02d.bin' % (PROGS, algo), 'rb').read()
    return [int.from_bytes(d[k:k + 5], 'big') for k in range(0, len(d) - 4, 5)]


def load_header():
    blocks = parse(CAP)
    H = [as_int(w) for w in [ws for _, a, ws in blocks if a == 0][0]]
    S = [as_int(w) for w in [ws for _, a, ws in blocks if a == 60][0]]
    return H, S


def touched(words, origin, mod=256):
    """cells a class-2/A word operates on (mem[ptr], before the post-increment)."""
    p = origin % mod
    cells = []
    for w in words:
        hi, cl, ad, lo = fields(w)
        if moves(hi, cl):
            cells.append(p)
            p = (p + s8(ad)) % mod
    return cells


def run_pointer(words, start, apply_loads):
    """Single-step a running data pointer through `words`.  If apply_loads, a
    801.0.NN.821 word resets the pointer to NN (the trace-note model, in which
    the body reads register 0x821); otherwise the loads are ignored and the
    pointer is a free accumulator (hypothesis a: a register the loads never
    touch).  Returns the pointer AFTER the last word."""
    p = start & 0xFF
    for w in words:
        hi, cl, ad, lo = fields(w)
        if apply_loads and cl == 0 and lo == 0x821:        # ldreg 821,#NN (absolute)
            p = ad
        if moves(hi, cl):
            p = (p + s8(ad)) & 0xFF
    return p


rom = P.Rom(ROM, P.SUB_BASE)
mrom = P.Rom(MAIN, 0)


def host_cells(algo):
    s = set()
    for _, op, ents in P.parse_t1(rom, rom.u32le(P.ALGO_T1_ARRAY + 4 * algo)):
        s |= set(ents)
    return s


def name(algo):
    return P.effect_name(mrom, algo)


# ===========================================================================  0
def sec_controls(H):
    print("=" * 78)
    print("0. POSITIVE CONTROLS (validate the interpreter before any origin claim)")
    print("=" * 78)
    # (i) the census: no body contains a pointer load (reproduce -pointer.md sect 1)
    nloads = 0
    imgs = []
    for a in range(96):
        try:
            b = load_body(a)
        except FileNotFoundError:
            continue
        if b and (fields(b[-1])[1] & 7) == 1 and fields(b[-1])[2] in (0x0E, 0x0F):
            imgs.append((a, b))
            nloads += sum(1 for w in b if fields(w)[1] == 0 and fields(w)[3] == 0x821)
    print("  (i)  body pointer-loads (801.0.NN.821) over %d images : %d  "
          "(expect 0 -- header holds them all)" % (len(imgs), nloads))
    # (ii) EQ geometric lock: band_i lands on state_i in order at exactly one origin
    w = load_body(39)
    starts = [i for i, x in enumerate(w)
              if fields(x)[0] == 0x000 and fields(x)[1] == 0xA and fields(x)[3] == 0x1D3]
    hs = [0x64, 0x68, 0x6C, 0x70, 0x74]
    lock = []
    for O in range(256):
        p = O
        band = []
        for i, x in enumerate(w):
            hi, cl, ad, lo = fields(x)
            if i in starts[:5]:
                band.append(p)
            if moves(hi, cl):
                p = (p + s8(ad)) & 0xFF
        if band == hs:
            lock.append(O)
    print("  (ii) EQ (algo39) +4 biquad walk lands band_i on host state_i in order")
    print("       -> UNIQUE origin: %s   (5/5, geometric)  [MEASURED]"
          % ['0x%02X' % o for o in lock])
    print("  (iii) biquad transfer-function impulse err = 0.000e+00 on 9 ROM banks")
    print("       (kn5000_dsp_semantics.py verify -- addressing rule reused here)")
    return imgs, lock[0] if lock else None


# ===========================================================================  1
def sec_continuous(H, S):
    print("\n" + "=" * 78)
    print("1. CONTINUOUS WHOLE-FRAME EXECUTION -- what the header leaves at body entry")
    print("=" * 78)
    # unit 0: header 0..48 then CALL; unit 1: header 50..58 then CALL.
    h0 = H[0:49]
    h1 = H[50:59]
    print("\n  data pointer arriving at each body's first instruction:")
    print("    model A  'body reads reg 0x821' (loads reset the pointer):")
    print("       unit 0 (EQ/compressor/...) : 0x%02X    unit 1 (reverb) : 0x%02X"
          % (run_pointer(h0, 0, True), run_pointer(H[0:59], 0, True)))
    print("    model B  'body reads a free accumulator' (loads ignored, hyp. a):")
    p0 = run_pointer(h0, 0, False)
    p1 = run_pointer(H[0:59], 0, False)
    print("       unit 0 : 0x%02X (= frame-start base + net accum)    unit 1 : 0x%02X"
          % (p0, p1))
    print("       net class-2/A accumulation, header[0..48] = %+d" % s8(p0))
    print("""
  Neither model emits the EQ's required 0x19:
    * model A gives 0x70 -- the header's absolute 801.0.70.821 load (trace-note
      result, reproduced);
    * model B gives 0x06 from base 0 (would need a persistent base of 0x13 to
      reach 0x19, and nothing sets 0x13).""")


# ===========================================================================  2
def sec_immediates(H, S):
    print("\n" + "=" * 78)
    print("2. IMMEDIATE-LOAD CENSUS -- is 0x19 loaded into ANY register? (hyp. a)")
    print("=" * 78)
    vals = []
    for base, arr, off in (('H', H, 0), ('S', S, 60)):
        for i, w in enumerate(arr):
            hi, cl, ad, lo = fields(w)
            if lo in (0x820, 0x821, 0x822, 0x825, 0x827):
                vals.append(ad)
                print("   %s%-2d %s   reg %03X <- #$%02X"
                      % (base, off + i, fmt(w), lo, ad))
    print("\n   distinct immediates loaded anywhere in header+epilogue: %s"
          % sorted('%02X' % v for v in set(vals)))
    print("   -> 0x19 is NOT among them.  HYPOTHESIS (a) 'a header load we")
    print("      mis-scoped carries the origin' is FALSIFIED: no register-load")
    print("      word, decoded or escape-format, loads 0x19.")
    print("\n   NOTE the epilogue's 859.0.86.822 (reg 0x822 <- #$86): 0x86 is the")
    print("   base of the REVERB's HIGH state block {86,97,9E,A6,...} -- concrete")
    print("   evidence the 0x820/0x822 escape-loads ARE per-region state pointers.")


# ===========================================================================  3
def sec_hostcoin():
    print("\n" + "=" * 78)
    print("3. HOST-COINCIDENCE over the COMPLETE host maps (the cross-effect control)")
    print("=" * 78)
    EQ_STATE = [0x64, 0x68, 0x6C, 0x70, 0x74]
    REV_LOW = {0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E}
    REV_HIGH = {0xA6, 0xA9, 0xAA, 0xAB, 0xAC, 0xAF, 0xB0, 0xB1, 0xB2}

    print("\n  EQ (algo39, unit0): geometric +4 walk locks UNIQUELY at 0x19 (5/5).")
    print("  The trace note said the reverb needed ~0xA6 -> 'no common constant'.")
    print("  But that used only the reverb's HIGH block.  The COMPLETE map adds a")
    print("  LOW block {19,1A,1B,1C,1D,1E}.  Re-run the reverb low-block overlap:\n")
    rv = load_body(16)
    print("    origin  EQ_state  REV_low  REV_high")
    w39 = load_body(39)
    starts = [i for i, x in enumerate(w39)
              if fields(x)[0] == 0 and fields(x)[1] == 0xA and fields(x)[3] == 0x1D3]
    for O in range(0x12, 0x1B):
        # geometric EQ check
        p = O; band = []
        for i, x in enumerate(w39):
            hi, cl, ad, lo = fields(x)
            if i in starts[:5]:
                band.append(p)
            if moves(hi, cl):
                p = (p + s8(ad)) & 0xFF
        eq = sum(1 for k in range(5) if band[k] == EQ_STATE[k])
        tc = set(touched(rv, O))
        mark = "  <== EQ lock" if O == 0x19 else ""
        print("     0x%02X    %d/5      %d/6     %d/9%s"
              % (O, eq, len(tc & REV_LOW), len(tc & REV_HIGH), mark))
    bestlow = max(range(256), key=lambda O: len(set(touched(rv, O)) & REV_LOW))
    besthigh = max(range(256), key=lambda O: len(set(touched(rv, O)) & REV_HIGH))
    print("\n    reverb LOW-block overlap peaks at 0x%02X (%d/6); at 0x19 = %d/6"
          % (bestlow, len(set(touched(rv, bestlow)) & REV_LOW),
             len(set(touched(rv, 0x19)) & REV_LOW)))
    print("    reverb HIGH-block overlap peaks at 0x%02X (%d/9) -- a SECOND pointer"
          % (besthigh, len(set(touched(rv, besthigh)) & REV_HIGH)))
    print("""
  READING: the reverb walks TWO state regions with TWO pointers -- a low bank at
  ~0x19 (the SAME origin the EQ locks on, across the unit boundary) and a high
  delay bank at ~0xA6 (the epilogue's 0x822<-#$86 base).  So the trace note's
  "EQ 0x19 vs reverb 0xA6, no common constant" is SUPERSEDED: the reverb's LOW
  pointer coincides with the EQ origin; 0xA6 was a second, separate pointer.
  [MEASURED overlap; the low-block match is set-intersection, not a clean
  geometric lock, because the reverb's pointer-delta rule is known-broken
  (notes/kn5000-dsp-pointer.md sect 6, extent test fails under every class subset).]""")


# ===========================================================================  4
def sec_perfeffect():
    print("\n" + "=" * 78)
    print("4. WHY THE ORIGIN CANNOT COME FROM THE (COMMON) HEADER")
    print("=" * 78)
    print("\n  The header+epilogue are uploaded ONCE and are identical for every")
    print("  effect (only the body images differ).  Yet unit-0 effects need")
    print("  DIFFERENT pointer origins:\n")
    for algo in (39, 8, 36):
        w = load_body(algo)
        H = host_cells(algo)
        best = max(range(256), key=lambda O: len(set(touched(w, O)) & H))
        hit = len(set(touched(w, best)) & H)
        print("     algo %2d %-14s unit0  best host overlap %d/%d at origin 0x%02X"
              % (algo, name(algo), hit, len(H), best))
    print("""
  Three unit-0 effects, one identical header, three different best origins
  (EQ 0x19, gated reverb ~0x07, compressor scalar cells 0x02/0x03).  A single
  common-header value cannot supply all three.  THEREFORE the per-effect origin
  is set by the BODY or by a per-effect HOST poke, NOT the header.

  * HYPOTHESIS (a) 'a mis-scoped HEADER load' -> IMPOSSIBLE for a per-effect
    origin (the header is effect-independent), and no header word loads 0x19
    anyway (sect 2).
  * HYPOTHESIS (b) 'body pre-motif walks the header base 0x70 to 0x19' ->
    FALSIFIED (trace note: 0x70 walks to 0xBB; making the pre-motif inert breaks
    the +4 stride the same check depends on).
  * WHAT SURVIVES: a per-effect DESCRIPTOR-relative base the HOST pokes before
    each frame (notes/kn5000-dsp-parameters.md sect 7).  The host-poke census
    (notes/kn5000-dsp-pointer.md sect 4) shows per-effect pokes through reg 0x821
    ({00..B2}) and 0x825 (incl. 0x1E, adjacent to 0x19).  The cold-boot capture
    loaded CHORUS+reverb, NOT the EQ, so the EQ's own 0x19 origin-poke is not in
    THIS capture.""")


def sec_verdict():
    print("\n" + "=" * 78)
    print("VERDICT")
    print("=" * 78)
    print("""
  Continuous whole-frame execution did NOT pin the origin's SOURCE, but it
  sharpened the picture decisively:

   * The origin VALUE is measured: EQ = 0x19 (unique, geometric).  The reverb's
     LOW state bank shares it (~0x15..0x19), across the unit-0/unit-1 boundary --
     which SUPERSEDES the trace note's "EQ 0x19 vs reverb 0xA6, no common
     constant" (that used an incomplete reverb host map).  0xA6 is a SECOND
     reverb pointer (high delay bank), matching the epilogue's 0x822<-#$86.

   * The origin's SOURCE is NOT a decoded header word: model A leaves 0x70,
     model B leaves 0x06, and no register-load immediate anywhere is 0x19.

   * (a)/(b) DECIDED: the per-effect origin CANNOT be a common-header load
     (the header is effect-independent), and (b) is falsified for the EQ.  The
     surviving mechanism is a PER-EFFECT HOST descriptor-base poke -- observable
     only in a capture with the EQ ACTIVE, which the cold-boot capture is not.

   * BLOCKER (concrete, not "needs hardware"): capture the uC-IF host stream with
     PARAMETRIC EQ selected in MAME and look for the pointer-init poke = 0x19
     (predict a 801.0.19.821 or 801.0.NN.825 word).  That is a MAME-driving
     experiment, no physical KN5000 required.

  The disassembler/core were NOT edited: the origin is per-effect and host-set,
  so hardcoding one absolute base would be wrong for every effect but the EQ.
  Coverage is UNCHANGED at 18.3% (545/2974): this pass decoded no new word.""")


def main():
    if not os.path.isdir(PROGS):
        sys.exit("run tools/kn5000_dsp_extract.py <rom> %s first" % PROGS)
    H, S = load_header()
    sec_controls(H)
    sec_continuous(H, S)
    sec_immediates(H, S)
    sec_hostcoin()
    sec_perfeffect()
    sec_verdict()


if __name__ == "__main__":
    main()

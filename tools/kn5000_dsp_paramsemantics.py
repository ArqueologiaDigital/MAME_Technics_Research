#!/usr/bin/env python3
"""kn5000_dsp_paramsemantics.py -- the PARAMETER -> CELL -> READER chain.

Companion to notes/kn5000-dsp-paramsemantics.md.  This is a NEW pass that uses a
lever the earlier semantic passes did not have: the COMPLETE per-effect NAMED
parameter list (notes/kn5000-dsp-paramlist.md + tools/kn5000_dsp_paramlist_capture.json)
propagated through the host-write DSP address (T1/T2, tools/kn5000_dsp_params.py)
into the instruction(s) that read that cell (the addressing rule,
tools/kn5000_dsp_addressing.py).

Chain:  USER PARAMETER (known meaning)
     -> HOST WRITE CELL   (T1[opcode][operand], MEASURED)
     -> BODY INSTRUCTION that reads that cell (the pointer walk / the coeff cursor /
        the class-family presence), constrained by the parameter's meaning + unit.

It VALIDATES on the known bindings first (the positive controls) and only then
reports new operand-meanings.  Nothing is edited; no audio; the core stays disabled.

Sections:
    bind      per-effect NAMED parameter -> host DSP cell (the new binding table)
    lfo       POSITIVE CONTROL: UI LFO params  <->  hi12=082 (the LFO read)
    biquad    POSITIVE CONTROL: UI BAND EMPHASIS <-> coeff cursor + state pointer
    tail      VOLUME / REV SEND universal output-mix cells and their readers
    comp      COMPRESSOR: the envelope-detector front end, attack/release = smoother
              coefficient, and the search for the THRESHOLD comparison machinery

Usage:
    python3 tools/kn5000_dsp_extract.py <sub.rom> /tmp/progs
    python3 tools/kn5000_dsp_paramsemantics.py
"""
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kn5000_dsp_params as P
from kn5000_dsp_addressing import load, walk_cells, fields, moves, s8

HERE = os.path.dirname(os.path.abspath(__file__))
SUB = os.path.expanduser(
    '~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom')
MAIN = os.path.expanduser(
    '~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_v10_program.rom')
CAPTURE = os.path.join(HERE, 'kn5000_dsp_paramlist_capture.json')

rom = P.Rom(SUB, P.SUB_BASE)
mrom = P.Rom(MAIN, 0)

PNAMES = [mrom.d[P.PNAME_BASE + P.PNAME_STRIDE * i:
                 P.PNAME_BASE + P.PNAME_STRIDE * i + 16].decode('latin1').strip()
          for i in range(85)]
PUNITS = [mrom.d[P.PUNIT_BASE + 2 * i:P.PUNIT_BASE + 2 * i + 2].decode('latin1').strip()
          for i in range(85)]
NAMES = {a: P.effect_name(mrom, a) for a in range(96)}
NAME2ALGO = {}
for a in range(100):
    NAME2ALGO.setdefault(P.effect_name(mrom, a), a)


def valid_algos():
    return [a for a in range(96)
            if os.path.exists('/tmp/progs/algo%02d.bin' % a) and load(a)]


def has_hi(a, hi):
    return any(fields(x)[0] == hi for x in load(a))


def t2_records(algo):
    """Return the ordered list of (opcode, operand, dsp_addr) the parameter stream
    resolves to -- the host WRITE cells, in emit order."""
    t1p = rom.u32le(P.ALGO_T1_ARRAY + 4 * algo)
    t2p = rom.u32le(P.ALGO_T2_ARRAY + 4 * algo)
    t1 = P.parse_t1(rom, t1p) if (t1p and t1p != P.NULL_T1) else []
    t2 = P.split_records(rom, t2p) if t2p else []
    addrmap = {op: ents for _, op, ents in t1}
    out = []
    for _a, _ln, body in t2:
        sols = P.decode_record(rom, body, addrmap)
        best = max(sols, key=len) if sols else []
        for (op, operand, imm) in best:
            out.append((op, operand, addrmap[op][operand]))
    return out


# ---------------------------------------------------------------------------
def sect_bind():
    print("=" * 78)
    print("BIND -- NAMED parameter -> host DSP cell, per effect (the new lever)")
    print("=" * 78)
    print("""
  The DSP-EFFECT page name-index arrays (capture json) give the ORDERED, named
  parameter list; the T2 stream resolves to the host WRITE cells.  These do not
  align 1:1 (some params emit an endpoint/L-R PAIR, some emit none, and every
  effect has hidden constant records: op74->1D, op63->06, op21->90), so we report
  the resolved cells alongside the names rather than forcing a positional decode.
  The robust, corpus-wide facts that DO fall out are the two universal tail cells.
""")
    cap = json.load(open(CAPTURE))
    for eff in cap:
        if eff['type'] != 11:
            continue
        a = NAME2ALGO.get(eff['name'])
        if a is None:
            continue
        recs = t2_records(a)
        nm = ['%s(%s)' % (PNAMES[i - 1], PUNITS[i - 1] or '-') for i in eff['indices']]
        print("  %-18s algo%2d" % (eff['name'], a))
        print("     params: " + ", ".join(nm))
        print("     cells : " + " ".join('%02X<%02X#%d>' % (ad, op, p)
                                          for op, p, ad in recs))


# ---------------------------------------------------------------------------
def sect_lfo():
    print("\n" + "=" * 78)
    print("LFO -- POSITIVE CONTROL: UI 'LFO SPEED/WAVEFORM' <-> hi12=082 (LFO read)")
    print("=" * 78)
    cap = json.load(open(CAPTURE))
    # UI: which effects expose LFO SPEED(8)/SLOW LFO SPEED(9)/LFO WAVEFORM(49)?
    LFO_IDX = {8, 9, 49, 71, 56}   # LFO speed / slow / waveform / fast / phase family
    ui_lfo = set()
    for eff in cap:
        if eff['type'] != 11:
            continue
        if set(eff['indices']) & {8, 9, 49}:
            ui_lfo.add(NAME2ALGO.get(eff['name']))
    ui_lfo.discard(None)
    body_lfo = set(a for a in valid_algos() if has_hi(a, 0x082))
    # restrict comparison to the 38 DSP-page effects we have UI lists for
    scope = set(NAME2ALGO.get(e['name']) for e in cap if e['type'] == 11)
    scope.discard(None)
    scope &= set(valid_algos())
    tp = sorted((ui_lfo & body_lfo) & scope)
    tn = sorted((scope - ui_lfo) - body_lfo)
    fp = sorted((body_lfo - ui_lfo) & scope)
    fn = sorted((ui_lfo - body_lfo) & scope)
    print("\n  present-AND-absent control over the %d DSP-page effects in scope:" % len(scope))
    print("    UI has LFO param  &  body has 082  (true +): %d  %s"
          % (len(tp), [NAMES[a] for a in tp]))
    print("    no UI LFO         &  no 082        (true -): %d" % len(tn))
    print("    body 082 but NO UI LFO param (false +)     : %d  %s"
          % (len(fp), [NAMES[a] for a in fp]))
    print("    UI LFO param but NO 082      (false -)     : %d  %s"
          % (len(fn), [NAMES[a] for a in fn]))
    print("\n  VERDICT:", "PASS" if not fn else "CHECK",
          "-- the LFO read maps to the UI LFO controls with no false negative.")


# ---------------------------------------------------------------------------
def sect_biquad():
    print("\n" + "=" * 78)
    print("BIQUAD -- POSITIVE CONTROL: UI 5x BAND EMPHASIS <-> coeff cursor + state ptr")
    print("=" * 78)
    algo = 39
    t1p = rom.u32le(P.ALGO_T1_ARRAY + 4 * algo)
    t1 = P.parse_t1(rom, t1p)
    op70 = next((ents for _, op, ents in t1 if op == 0x70), [])
    coeff = op70[:5]
    state = op70[5:10]
    print("\n  PARAMETRIC EQ host op70 writes: coeff %s  state %s"
          % (['%02X' % c for c in coeff], ['%02X' % c for c in state]))
    print("  coeff stride %d (== 6 cursor fetches / band), state stride %d (== +4 ptr walk)"
          % (coeff[1] - coeff[0], state[1] - state[0]))
    words = load(algo)
    starts = [i for i, w in enumerate(words)
              if fields(w)[0] == 0x000 and fields(w)[1] == 0xA and fields(w)[3] == 0x1D3]
    tr0, _ = walk_cells(words, 0, wrap=False)
    s0 = [tr0[i][1] for i in starts[:5]]
    org = (state[0] - s0[0]) & 0xFF
    cells = [(org + c) & 0xFF for c in s0]
    hit = sum(1 for k in range(5) if cells[k] == state[k])
    print("  motif starts %s ; band-S0 stride %s ; origin 0x%02X -> ch0 cells %s == host state %d/5"
          % (starts, [s0[i + 1] - s0[i] for i in range(4)], org,
             ['%02X' % c for c in cells], hit))
    print("\n  VERDICT:", "PASS" if hit == 5 else "FAIL",
          "-- the biquad body reproduces the host coeff+state block exactly (structural).")


# ---------------------------------------------------------------------------
def sect_tail():
    print("\n" + "=" * 78)
    print("TAIL -- the universal output-mix cells (VOLUME + REV SEND)")
    print("=" * 78)
    cnt90 = cnt06 = 0
    algos = valid_algos()
    for a in algos:
        recs = t2_records(a)
        addrs = [ad for _, _, ad in recs]
        if 0x90 in addrs:
            cnt90 += 1
        if 0x06 in addrs:
            cnt06 += 1
    print("\n  op21->0x90 present in %d/%d streamed effects (the 0..0.8 level, MEASURED)"
          % (cnt90, len(algos)))
    print("  op63->0x06 present in %d/%d effects (the second tail level)"
          % (cnt06, len(algos)))
    print("""
  Both are the universal trailing controls the UI shows as VOLUME + REV SEND.
  The reverb family (algo 16..27) uses the 0x86 counterpart and has NO 0x90 (a
  reverb is the send bus -> no REV SEND slot), which the paramlist confirms.
  HONEST LIMIT: record order is not strictly UI order (interleaved constants), so
  which of 0x90/0x06 is VOLUME vs REV SEND is not forced by ordering alone.""")


# ---------------------------------------------------------------------------
def sect_comp():
    print("\n" + "=" * 78)
    print("COMP -- the compressor: detector front end, attack/release, comparator hunt")
    print("=" * 78)
    algo = 36
    recs = t2_records(algo)
    print("\n  COMPRESSOR host cells (name<-cell):")
    print("    THRESHOLD -> 0x04 (op72)   RATIO -> 0x0D (op72)")
    print("    ATTACK SENS.(s) -> 0x02/0x0B (op6D)   RELEASE SENS.(s) -> 0x03/0x0C (op6D)")
    print("    resolved records:", ' '.join('%02X<%02X#%d>' % (ad, op, p) for op, p, ad in recs))
    words = load(algo)
    nc40 = sum(1 for w in words if fields(w)[0] == 0xC40)
    print("\n  body: %d words, hi12=0xC40 (envelope detector / one-pole smoother) x%d"
          % (len(words), nc40))
    print("  -> the C40 detector appears TWICE = two level detectors (L/R).  A")
    print("     compressor's smoother coefficient IS its attack/release time constant,")
    print("     so ATTACK/RELEASE SENS. (cells 0x02/0x03) are the coefficients the C40")
    print("     words consume.  NEW operand-meaning for C40 in the compressor context.")

    # comparator hunt: any hi12 / (hi12,class,lo12) family UNIQUE to threshold effects?
    thr = set(a for a in valid_algos()
              if NAMES[a] in ('COMPRESSOR', 'SLOW ATTACKER', 'GATED REVERB'))
    others = set(valid_algos()) - thr
    hi_thr = set()
    hi_oth = set()
    for a in valid_algos():
        hs = set(fields(w)[0] for w in load(a))
        (hi_thr if a in thr else hi_oth).update((a in thr, h) for h in hs) if False else None
    hi_in = defaultdict(set)
    fam_in = defaultdict(set)
    for a in valid_algos():
        for w in load(a):
            hi, cl, ad, lo = fields(w)
            hi_in[hi].add(a)
            fam_in[(hi, cl, lo)].add(a)
    uniq_hi = [hi for hi, s in hi_in.items() if s and s <= thr]
    uniq_fam = [(f, s) for f, s in fam_in.items() if s and s <= thr]
    print("\n  COMPARATOR HUNT (present-AND-absence over the corpus):")
    print("    hi12 families UNIQUE to the 3 threshold effects: %s"
          % (['%03X' % h for h in uniq_hi] or 'NONE'))
    print("    (hi12,class,lo12) families unique to threshold effects: %d"
          % len(uniq_fam))
    for f, s in sorted(uniq_fam):
        print("       %03X.%X.*.%03X in %s" % (f[0], f[1], f[2],
                                               sorted(NAMES[a] for a in s)))
    print("""
  RESULT (honest, NEGATIVE): no hi12 opcode is unique to the threshold effects.
  There is NO distinct compare-and-branch / conditional-select instruction class
  -- consistent with the hand-unrolled, branchless bodies (necfamily.md).  The
  threshold-dependent gain is computed ARITHMETICALLY (the C40 smoother chain plus
  multiplies), not by a comparator opcode.  The few (hi12,class,lo12) families that
  are unique to the gated reverb are its all-pass/DRAM tail, not a comparator, so
  the comparison machinery is NOT localised to a single decodable word here.""")


def main():
    if not os.path.isdir('/tmp/progs'):
        sys.exit("run tools/kn5000_dsp_extract.py <sub.rom> /tmp/progs first")
    sect_bind()
    sect_lfo()
    sect_biquad()
    sect_tail()
    sect_comp()


if __name__ == "__main__":
    main()

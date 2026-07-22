#!/usr/bin/env python3
"""kn5000_dsp_headerdecode.py -- decode the uPD6383GF COMMON HEADER (I-RAM 0..59)
and the trailing block at I-RAM 60..82.

Everything in this series so far has analysed the 38 EFFECT BODY images (2974 words).
Those 2974 words EXCLUDE the 83 words at I-RAM 0..82 BY CONSTRUCTION -- and by
elimination those 83 words must hold the per-sample frame structure, the audio input
and output path, all control flow, and the pointer origins.  This tool mines them,
always with the body corpus as a CONTROL: any pattern claimed for the header is
re-measured over the bodies, because 83 words over-fit trivially.

Inputs:
    <coldboot.txt>   notes/data/kn5000_dsp1_upload_coldboot.txt  (header + block2)
    <subprogram.rom> kn5000_subprogram_v142.rom                  (the body corpus)

Usage:
    python3 tools/kn5000_dsp_headerdecode.py \
        notes/data/kn5000_dsp1_upload_coldboot.txt \
        ~/compartilhado/kn5000-roms-disasm/original_ROMs/kn5000_subprogram_v142.rom

Findings are written up in notes/kn5000-dsp-headerdecode.md.
"""
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kn5000_dsp_wordfields import parse, as_int                    # noqa: E402
from kn5000_dsp_extract import Rom, parse_stream, ALGO_TABLE, PARAM_TABLE, N_ALGOS  # noqa: E402

# 36-bit word: hi12[35:24] . class4[23:20] . addr8[19:12] . lo12[11:0]
def hi12(v):  return (v >> 24) & 0xFFF
def cls(v):   return (v >> 20) & 0xF
def addr8(v): return (v >> 12) & 0xFF
def lo12(v):  return v & 0xFFF
def fmt(v):   return f"{hi12(v):03X}.{cls(v):X}.{addr8(v):02X}.{lo12(v):03X}"

def is_eob(v):
    """END-OF-BLOCK marker: hi12 bit 10 set with bit 11 (format escape) clear.
    This is the definition used throughout the series; words such as 0xC64 have
    bit 10 set but are escape-format and are NOT end-of-block."""
    return (hi12(v) & 0xC00) == 0x400


def load_header(path):
    blocks = parse(path)
    H = [as_int(w) for w in [ws for _, a, ws in blocks if a == 0][0]]
    S = [as_int(w) for w in [ws for _, a, ws in blocks if a == 60][0]]
    patches = [(a, as_int(ws[0])) for _, a, ws in blocks if a in (64, 71)]
    return H, S, patches


def load_bodies(rompath):
    rom = Rom(rompath)
    seen, imgs = set(), []
    for i in range(N_ALGOS):
        try:
            iram, _, _ = parse_stream(rom, rom.u32le(ALGO_TABLE + 4 * i))
            _, co, _ = parse_stream(rom, rom.u32le(PARAM_TABLE + 4 * i))
        except Exception:
            continue
        for a, ws, _ in iram:
            if a not in (84, 200):
                continue                       # 1520/3376 = the malformed slots
            blob = bytes(b for w in ws for b in w)
            if blob in seen:
                continue
            seen.add(blob)
            imgs.append((i, a,
                         [int.from_bytes(blob[k:k + 5], "big")
                          for k in range(0, len(blob), 5)],
                         len(co)))
    return imgs


# --------------------------------------------------------------------------- 1
def sec1_blocks(H, S):
    print("=" * 78)
    print("1. THE HEADER SPLIT INTO END-OF-BLOCK SEGMENTS")
    print("=" * 78)
    seg, segs = [], []
    for i, v in enumerate(H):
        seg.append(i)
        if is_eob(v):
            segs.append(seg)
            seg = []
    if seg:
        segs.append(seg)
    for n, s in enumerate(segs):
        print(f"\n  block {n:2d}   I-RAM {s[0]}..{s[-1]}   ({len(s)} words)")
        for i in s:
            tag = "  <== END OF BLOCK" if is_eob(H[i]) else ""
            unit = ""
            if is_eob(H[i]) and cls(H[i]) == 1 and addr8(H[i]) in (0x0E, 0x0F):
                unit = f"  [unit tag {addr8(H[i]):#04x} -> CALL unit {addr8(H[i]) - 0x0E}]"
            print(f"      {i:3d}  {fmt(H[i])}{tag}{unit}")
    print(f"\n  {len(segs)} blocks in 60 words; "
          f"lengths {[len(s) for s in segs]}")
    print("\n  block at I-RAM 60..82 (23 words), END-OF-BLOCK count = "
          f"{sum(1 for v in S if is_eob(v))}:")
    for i, v in enumerate(S):
        print(f"      {60 + i:3d}  {fmt(v)}")
    return segs


# --------------------------------------------------------------------------- 2
def sec2_control(H, S, imgs):
    print()
    print("=" * 78)
    print("2. CONTROL FLOW -- the register-reuse proof, and the eob census")
    print("=" * 78)

    # 2a. eob census, header vs bodies (the control).
    nb = sum(len(w) for _, _, w, _ in imgs)
    print(f"\n  bodies : {len(imgs)} images, {nb} words")
    per = collections.Counter()
    lastonly = 0
    for i, a, W, _ in imgs:
        hits = [j for j, v in enumerate(W) if is_eob(v)]
        per[len(hits)] += 1
        if hits == [len(W) - 1]:
            lastonly += 1
    print(f"           end-of-block words per image: {dict(per)}")
    print(f"           images whose ONLY eob is the LAST word: {lastonly}/{len(imgs)}")
    print(f"  header : {sum(1 for v in H if is_eob(v))} in 60 words, "
          f"first at {[i for i,v in enumerate(H) if is_eob(v)][0]}")
    print(f"  block2 : {sum(1 for v in S if is_eob(v))} in 23 words")
    print("\n  => a body is ONE block; the header is FOURTEEN blocks; block2 is a"
          "\n     block that never ends -> the frame is closed by hardware, not by code.")

    # 2b. the register-reuse proof.
    print("\n  --- THE REGISTER-REUSE PROOF (PROVEN BY CONSTRUCTION) ---")
    regs = collections.defaultdict(list)
    for i, v in enumerate(H):
        if lo12(v) in (0x820, 0x821, 0x822, 0x825, 0x827):
            regs[lo12(v)].append((i, addr8(v)))
    for r in sorted(regs):
        print(f"      reg {r:#05x} : " +
              "  ".join(f"I-RAM {i} <- #${imm:02X}" for i, imm in regs[r]))
    print("""
      Registers 0x821/0x827/0x825 are each loaded TWICE in the header, at I-RAM
      42-44 (#$70/#$6C/#$25) and again at I-RAM 50-52 (#$50/#$64/#$25).  The two
      effect units are BOTH resident and BOTH run every frame, and neither body
      contains a pointer load (0 of 2974 words), so each body must read the
      register values the header last wrote.  The second load overwrites the
      first.  Therefore unit 0's body MUST execute between I-RAM 44 and I-RAM 50.
      The only word in between that can transfer control is I-RAM 49, and control
      must come back to I-RAM 50.  That is a CALL and a RETURN -- deduced, not
      assumed.""")

    # 2c. the identical-word check.
    body_words = set(v for _, _, W, _ in imgs for v in W)
    print("  --- the call word and the return word are BYTE-IDENTICAL ---")
    for i in (49, 59):
        print(f"      header {i}: {fmt(H[i])}   also occurs in a body: "
              f"{H[i] in body_words}")
    terms = collections.Counter(fmt(W[-1]) for _, a, W, _ in imgs if a == 84)
    print(f"      unit-0 body terminators (36 images): "
          f"{sorted(set(k.split('.',1)[1] for k in terms))}")
    print(f"      unit-1 body terminator          : "
          f"{[fmt(W[-1]) for _, a, W, _ in imgs if a == 200]}")

    # 2d. do untagged eob words transfer?  they cannot.
    print("""
  --- the twelve UNTAGGED end-of-block words are NOT transfers ---
      I-RAM 42..44 must execute (they are the loads the proof above relies on),
      and they are only reachable by falling through I-RAM 41, which is itself an
      end-of-block word (400.A.00.21A).  So the default action after an
      end-of-block word is FALL THROUGH.  bit 10 is therefore not "branch"; the
      transfer is carried by the UNIT TAG (class 1, addr8 0x0E/0x0F).""")


# --------------------------------------------------------------------------- 3
def sec3_io(H, S, patches, imgs):
    print()
    print("=" * 78)
    print("3. THE AUDIO I/O PATH -- candidates, ranked, with the body control")
    print("=" * 78)

    body_cls = collections.Counter(cls(v) for _, _, W, _ in imgs for v in W)
    hd_cls = collections.Counter(cls(v) for v in H)
    s_cls = collections.Counter(cls(v) for v in S)
    print("\n  class4 census (class4 = space selector; bit 3 = multiply/cursor):")
    print(f"    {'class':>5} {'bodies':>7} {'header':>7} {'block2':>7}")
    for c in range(16):
        if body_cls[c] or hd_cls[c] or s_cls[c]:
            mark = "  <- ABSENT from all 2974 body words" if not body_cls[c] else ""
            print(f"    {c:>5X} {body_cls[c]:>7} {hd_cls[c]:>7} {s_cls[c]:>7}{mark}")

    print("\n  --- the host's two per-unit patch slots (MEASURED, from the capture) ---")
    print(f"    I-RAM 64 default : {fmt(S[4])}   (unit tag 0x0E)")
    print(f"    I-RAM 71 default : {fmt(S[11])}   (unit tag 0x0F)")
    for a, v in patches:
        print(f"    host writes I-RAM {a}: {fmt(v)}")
    print("""    lo12 is INVARIANT per slot (0x445 at word 64, 0x446 at word 71) while
    hi12/class/addr8 all vary with the effect selection.  lo12 0x445/0x446 is a
    per-unit route; what the host varies is the operand.  These are the per-unit
    EFFECT-RETURN / wet-level words.  (INFERRED, strong.)""")

    print("\n  --- the header's two parallel opening blocks (MEASURED) ---")
    for pair in ((0, 6), (7, 11)):
        print(f"    block {pair[0]}..{pair[1]}:")
        for i in range(pair[0], pair[1] + 1):
            print(f"        {i:3d}  {fmt(H[i])}")
    print("""    Word-for-word parallel on addr8 0x02 vs 0x01, ending in an
    end-of-block word each.  addr8 0x03 never occurs anywhere in the header, so
    this is a TWO-channel (stereo) structure, not a three-port DI1/DI2/DI3 sweep.
    Best available candidate for the input read+scale stage.  (SPECULATIVE.)""")

    print("\n  --- the per-unit class-5/class-6 twin (MEASURED) ---")
    print(f"    I-RAM 48 (unit 0 block) : {fmt(H[48])}")
    print(f"    I-RAM 56 (unit 1 block) : {fmt(H[56])}")
    print("""    Identical hi12 (0xC64) and addr8 (0xA2); only class differs, 5 for unit 0
    and 6 for unit 1, at the same position in each unit's block, immediately
    before the call.  A per-unit send/route.  (INFERRED.)""")


# --------------------------------------------------------------------------- 4
def sec4_coeffs(imgs, H):
    print()
    print("=" * 78)
    print("4. DOES THE HEADER DRAW ON THE ALGORITHM'S COEFFICIENT BANK?  NO.")
    print("=" * 78)
    diffs = []
    for i, a, W, nco in imgs:
        cur = sum(1 for v in W if cls(v) & 8)
        diffs.append(nco - cur)
    d = collections.Counter(diffs)
    hdrcur = sum(1 for v in H if cls(v) & 8)
    print(f"\n  cursor-fetching words in the header: {hdrcur}")
    print(f"  (coefficients uploaded) - (cursor-fetching body words), all {len(imgs)} images:")
    for k in sorted(d):
        print(f"      {k:>+5}  x{d[k]}")
    print(f"""
  The distribution is centred on 0/+1, never near +{hdrcur}.  If the header's
  {hdrcur} cursor-fetching words drew from the same bank as the body, every
  algorithm would have to ship {hdrcur} extra coefficients.  None does.
  => the header reads a SEPARATE, fixed coefficient bank.  (MEASURED.)""")


# --------------------------------------------------------------------------- 5
def sec5_hi12(H, S, imgs):
    print()
    print("=" * 78)
    print("5. hi12 BITS [9:8] -- refinement of 'all four values exercised'")
    print("=" * 78)
    c = collections.Counter((hi12(v) >> 8) & 3 for _, _, W, _ in imgs for v in W)
    print(f"\n  bodies : {dict(sorted(c.items()))}")
    odd = sorted(set(v for _, _, W, _ in imgs for v in W
                     if ((hi12(v) >> 8) & 3) == 3))
    print(f"  value 3 occurs {c[3]} times in 2974 words, in {len(odd)} distinct word(s): "
          f"{[fmt(v) for v in odd]}")
    print(f"  header : {dict(sorted(collections.Counter((hi12(v) >> 8) & 3 for v in H).items()))}")
    print("""
  [9:8] behaves as a THREE-valued selector {0,1,2}; value 3 is 2 words in 2974
  and is not a fourth mode being exercised.  A 3-way operand-source selector fits
  (the biquad needs three operand sources); a 4-way one does not.  (MEASURED /
  INFERRED.)  This refines '-hi12.md': all four values do appear, but the fourth
  is a singleton, so the field's ARITY is 3.""")


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    H, S, patches = load_header(sys.argv[1])
    imgs = load_bodies(sys.argv[2])
    sec1_blocks(H, S)
    sec2_control(H, S, imgs)
    sec3_io(H, S, patches, imgs)
    sec4_coeffs(imgs, H)
    sec5_hi12(H, S, imgs)


if __name__ == "__main__":
    main()

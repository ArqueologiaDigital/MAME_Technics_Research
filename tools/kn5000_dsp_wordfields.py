#!/usr/bin/env python3
"""kn5000_dsp_wordfields.py -- structural analysis of captured uPD6383GF I-RAM words.

Input: a kn5000_dsp1_upload.txt produced by the kn5000_dsp1 device (see
src/mame/matsushita/kn5000_dsp.cpp).  It records every byte the Sub CPU sends over
the uC-IF (port PZ), grouped into transfers by command byte.

What this does, and deliberately does NOT do:
  * It does NOT assume an opcode layout.  Nothing here decodes an instruction.
  * It DOES ask the questions that must be answered before any decode is possible:
      - a 36-bit word travels in a 5-byte (40-bit) container, so FOUR bits are
        padding.  Which four?  Find bits that are constant across every word.
      - which bit positions actually vary, and how strongly?  A field boundary
        usually shows up as a run of bits with similar entropy.
      - do any words repeat?  Repeated words across different effect programs are
        likely NOPs or common idioms, and a NOP is the single most useful anchor
        when starting a disassembler.

Usage:
    python3 tools/kn5000_dsp_wordfields.py <kn5000_dsp1_upload.txt>
"""
import collections
import re
import sys


def parse(path):
    """Return [(cmd, addr_or_None, [5-byte words])] for uploads that look like
    op3 I-RAM writes: command 0x01, a 16-bit word address, then a body whose
    length is a multiple of 5."""
    text = open(path).read().splitlines()
    out = []
    i = 0
    while i < len(text):
        m = re.match(r"transfer\s+\d+: cmd (0x[0-9A-Fa-f]+)\s+(\d+) bytes", text[i])
        if not m:
            i += 1
            continue
        cmd, n = int(m.group(1), 16), int(m.group(2))
        payload = []
        j = i + 1
        while j < len(text) and re.match(r"\s+[0-9A-F]{4}:", text[j]):
            payload += [int(b, 16) for b in text[j].split(":")[1].split()]
            j += 1
        i = j
        if cmd == 0x01 and n > 2 and (n - 2) % 5 == 0:
            addr = (payload[0] << 8) | payload[1]
            body = payload[2:]
            words = [tuple(body[k:k + 5]) for k in range(0, len(body), 5)]
            out.append((cmd, addr, words))
    return out


def as_int(w):
    return (w[0] << 32) | (w[1] << 24) | (w[2] << 16) | (w[3] << 8) | w[4]


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    blocks = parse(sys.argv[1])
    if not blocks:
        sys.exit("no op3-shaped I-RAM uploads found in that capture")

    allw = [w for _, _, ws in blocks for w in ws]
    print(f"{len(blocks)} I-RAM uploads, {len(allw)} words of 36 bits\n")
    for _, addr, ws in blocks:
        print(f"  addr {addr:>4} .. {addr + len(ws) - 1:>4}   {len(ws):>4} words")

    # --- which bits are constant? (the 4 padding bits must be among them) ---
    ones = [0] * 40
    for w in allw:
        v = as_int(w)
        for b in range(40):
            if v & (1 << b):
                ones[b] += 1
    n = len(allw)
    print(f"\nbit occupancy over {n} words (bit 39 = MSB of byte 0):")
    always0 = [b for b in range(40) if ones[b] == 0]
    always1 = [b for b in range(40) if ones[b] == n]
    print(f"  always 0 : {always0}")
    print(f"  always 1 : {always1}")
    print(f"  -> {len(always0) + len(always1)} constant bits "
          f"({'consistent with 4 padding bits' if len(always0) + len(always1) >= 4 else 'FEWER than the 4 padding bits expected'})")

    print("\n  bit : ones     share  (| = varies, . = constant)")
    for b in range(39, -1, -1):
        share = ones[b] / n
        mark = "." if ones[b] in (0, n) else "|"
        bar = "#" * int(share * 40)
        print(f"  {b:>4} : {ones[b]:>5}  {share:6.3f} {mark} {bar}")

    # --- repeated words: NOP candidates ---
    freq = collections.Counter(as_int(w) for w in allw)
    print("\nmost repeated words (NOP / common-idiom candidates):")
    for v, c in freq.most_common(12):
        pct = 100.0 * c / n
        print(f"  {v:010X}  x{c:<5} {pct:5.1f}%")

    uniq = len(freq)
    print(f"\n{uniq} distinct words out of {n} ({100.0 * uniq / n:.1f}% unique)")


if __name__ == "__main__":
    main()

# ---------------------------------------------------------------------------
# FINDINGS from the first cold-boot capture (2026-07-22), recorded here so the
# next pass starts from them rather than rediscovering them:
#
#   * PACKING CONFIRMED FROM THE DATA. Bits 36-39 are always zero across all
#     573 captured words -- exactly the 4 padding bits. So a 36-bit instruction
#     is right-aligned, big-endian, in its 5-byte container.
#
#   * CAPTURE IS DETERMINISTIC. The 60-word header at I-RAM 0 is uploaded three
#     times per boot and is byte-identical every time.
#
#   * COEFFICIENTS ARE SIGNED Q0.23, big-endian two's complement. The 3-byte
#     (cmd 0x02) words decode to round decimals:
#         400000 = +0.50   399999 = +0.45   4CCCCC = +0.60
#         2CCCCC = +0.35   200000 = +0.25   E00000 = -0.25
#     Round two-decimal constants do not fall out of a wrong alignment, so this
#     confirms the 3-byte grouping independently and fixes the numeric format.
#     THIS IS THE HANDLE FOR THE KN7000 CROSS-CHECK: compare these against the
#     documented KN7000 algorithm constants (kn7000_disassembly/dsp/), and
#     compare delay lengths -- a tap of N milliseconds is the same physical
#     quantity on both instruments even if no opcode encoding is shared.
#
#   * OPCODE FIELD, UNRESOLVED. Bits [35:33] take all 8 values with a skewed
#     distribution (0:211 5:124 4:98 1:54 6:41 2:36 3:8 7:1) and bits [35:32]
#     take 12 of 16 values, top 8 covering 97%. That is consistent with an
#     opcode/class field in the high bits but does NOT establish one -- no
#     instruction has been decoded, and this could equally be a field boundary
#     that happens to sit there. Do not build on it without more evidence.
#
#   * 49% of words are unique (281 distinct of 573); within a single program,
#     70 words hold 48 distinct and 133 words hold 49 distinct. High reuse
#     inside a program, as expected for real microcode.
#
# NEXT: capture with DIFFERENT effect algorithms selected (the ROM holds 100,
# via the pointer table at 0x0001ED7C) and diff the programs. Words common to
# every algorithm are the runtime/housekeeping idiom; words that vary with the
# effect carry the algorithm. That difference is a far better decoding lever
# than bit statistics over one boot.

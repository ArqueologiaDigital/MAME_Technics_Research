#!/usr/bin/env python3
"""Adversarial re-derivation of the GAP A structural claims, from the CONVERTED LISTING.

Run:  python3 gapA_listing_checks.py [path/to/wsa1_prom_c.s]
Default: ../../../wsa1-roms-disasm/prom_c/wsa1_prom_c.s   (READ ONLY, byte-identical
         round-trip of the ROM -- see that tree's assert_byte_identical.py)

The listing is parsed by its per-line address comment (`; FB7161  ld (XBC),DE`),
so what is read is an INSTRUCTION AT AN ADDRESS, never a header's prose.

  1  Dev10C_WriteAllChanRegs (0xFB713A-0xFB732B).
     Q: which staging-struct offset feeds which register block, in EXECUTION order,
        and how many words does the burst actually read?
     Signal: `add BC/DE/IX,0x0NNN` = the register block; the `ld BC,(XIX+0xNN)`
        that follows = the staging offset; word n lives at offset 2n.
     Claim under test: "moves 22 WORDS into 22 registers, register = block*0x40 + chan".
  2  The gate.  Q: is block 0x0080 written twice, bit 15 set then cleared?
     Signal: `set 0x0f,BC` at 0xFB717E and `res 0x0f,BC` at 0xFB7307.
  3  The 22 computed stores over staging words 12..21 (RAM 0xD776..0xD788).
     Q: how many are computed (`stw_da`) versus immediate (`stiw_da`) or OR
        (`ordm16_24`)?  The "22 stores, no third idiom" claim is about the first kind.
  4  HL/DE preservation, which is what makes the 0x0500 / 0x08C0 wrapper reading
     provable.  Q: do 0xFA7602, 0xFA75BA, 0xFA7654, 0xFA5ED3, 0xFA78E8 save HL / DE?
     A routine that never writes a register also preserves it -- both are checked.
  5  The `< 0x6000` guard on register 0x0040's fix-up.
     Q: is `cp HL,0x6000` present in BOTH copies of the fix-up, or only one?
     This is the claim "the fix-up at 0xFA82F0 tests (w & 0xF000) < 0x6000".
  6  sub_FA5ED3's argument bounds -- what names its three arguments.
     Q: what immediates is each argument slot compared against?

WHAT A NUMBER MEANS.  Section 1's map is the whole decode: if a row moved, every
register name in the driver moves with it.  Section 4 is the difference between
"the detune wrapper feeds 0x0500" and "some earlier value does" -- a callee that
does not preserve a register invalidates the read.
"""
import re, sys, os

DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "../../../wsa1-roms-disasm/prom_c/wsa1_prom_c.s")
fails = 0

def check(name, ok, detail):
    global fails
    if not ok:
        fails += 1
    print(("PASS " if ok else "FAIL ") + name + "  " + detail)

def load(path):
    """address -> disassembled text, from the trailing `; ADDR  text` comment."""
    out = {}
    pat = re.compile(r";\s*([0-9A-F]{6})\s\s(.*?)\s*$")
    for line in open(path, encoding="utf-8", errors="replace"):
        m = pat.search(line)
        if m:
            out.setdefault(int(m.group(1), 16), m.group(2))
    return out

def span(ins, lo, hi):
    return [(a, ins[a]) for a in sorted(ins) if lo <= a <= hi]

def main(path):
    ins = load(path)
    print("listing %s  %d addressed instructions" % (path, len(ins)))

    # 1 -- walk the burst writer and pair each block constant with the next struct read
    body = span(ins, 0xFB713A, 0xFB732B)
    pairs, pending = [], None
    for a, t in body:
        m = re.match(r"add (?:BC|DE|IX),0x0?([0-9a-f]{3,4})$", t)
        if m:
            pending = int(m.group(1), 16)
            continue
        if t == "ld (XBC),HL" and pending is None:
            pending = 0x0000                      # `ld (XBC),HL` = select chan + 0
        m = re.match(r"ld (?:BC|DE),\(XIX\+0x([0-9a-f]{2})\)$", t)
        if m and pending is not None:
            pairs.append((pending, int(m.group(1), 16)))
            pending = None
        if t.startswith("ld (XBC),0x8100") and pending is not None:
            pairs.append((pending, None))         # block 0: an inline literal, no word
            pending = None
    print("     execution order (block, struct offset, word):")
    for blk, off in pairs:
        print("       0x%04X  %s" % (blk, "literal 0x8100, no staging word"
                                     if off is None else "+0x%02X  word %2d" % (off, off // 2)))
    words = [off // 2 for _, off in pairs if off is not None]
    check("1a registers written by the burst == 22", len(pairs) == 22, "got %d" % len(pairs))
    check("1b staging WORDS read by the burst == 21 (word 0 is never read)",
          len(words) == 21 and 0 not in words, "words=%s" % sorted(words))
    check("1c blocks are the documented sparse set of 22",
          sorted(b for b, _ in pairs) == [0x000, 0x040, 0x080, 0x0c0, 0x100, 0x140, 0x180,
                                          0x400, 0x440, 0x480, 0x4c0, 0x500, 0x800, 0x840,
                                          0x880, 0x8c0, 0x900, 0x940, 0x980, 0x9c0, 0xa00, 0xa40],
          "")
    ascending = [b for b, _ in pairs] == sorted(b for b, _ in pairs)
    check("1d the burst is NOT issued in ascending register order", not ascending,
          "ascending=%s" % ascending)

    # 2 -- the gate
    check("2a bit 15 SET at 0xFB717E", ins.get(0xFB717E) == "set 0x0f,BC", repr(ins.get(0xFB717E)))
    check("2b bit 15 CLEARED at 0xFB7307", ins.get(0xFB7307) == "res 0x0f,BC", repr(ins.get(0xFB7307)))
    both = [a for a, t in body if t.startswith("ld BC,(XIX+0x04)")]
    check("2c staging word 2 is read twice (gate in, gate out)", len(both) == 3,
          "sites=%s" % [hex(a) for a in both])   # 0xFB717B, 0xFB7304, 0xFB730F

    # 3 -- the byte-pair block group
    kinds = {}
    for a, t in ins.items():
        m = re.match(r"ld \(0x00d7([78][0-9a-f])\),", t)
        if m and 0x76 <= int(m.group(1), 16) <= 0x88 and int(m.group(1), 16) % 2 == 0:
            src = t.split(",", 1)[1]
            kinds.setdefault("immediate" if re.match(r"0x[0-9a-f]+$", src) else "computed",
                             []).append(a)
    check("3a computed stores over staging words 12..21 == 22",
          len(kinds.get("computed", [])) == 22, "computed=%d immediate=%d"
          % (len(kinds.get("computed", [])), len(kinds.get("immediate", []))))

    # 4 -- callee register preservation
    for lo, hi, name in ((0xFA7602, 0xFA7653, "DetuneCurve_LookupSigned"),
                         (0xFA7654, 0xFA766B, "DetuneCurve_LookupUnsigned"),
                         (0xFA75BA, 0xFA7601, "sub_FA75BA"),
                         (0xFA5ED3, 0xFA6025, "sub_FA5ED3"),
                         (0xFA78E8, 0xFA7926, "sub_FA78E8")):
        b = span(ins, lo, hi)
        txt = [t for _, t in b]
        for reg in ("HL", "DE"):
            saved = any(("push %s%s" % (w, reg)) in txt for w in ("", "X")) \
                    and any(("pop %s%s" % (w, reg)) in txt for w in ("", "X"))
            written = any(re.match(r"(ld|add|and|or|sub|sll|srl|cpl|inc|dec|ex)\s+%s\b" % reg, t)
                          for t in txt)
            check("4 %-26s preserves %s" % (name, reg), saved or not written,
                  "push/pop=%s writes=%s" % (saved, written))

    # 5 -- the 0x6000 guard, in both copies of the register-0x0040 fix-up
    a_has = any(t == "cp HL,0x6000" for _, t in span(ins, 0xFA8233, 0xFA8265))
    b_has = any("0x6000" in t for _, t in span(ins, 0xFA82F0, 0xFA8318))
    check("5a copy at 0xFA8233-0xFA8261 HAS the < 0x6000 guard", a_has, "")
    check("5b copy at 0xFA82F0-0xFA8318 does NOT have it (the two are not identical)",
          not b_has, "guard found = %s" % b_has)

    # 6 -- what bounds sub_FA5ED3's arguments
    bounds = [(hex(a), t) for a, t in span(ins, 0xFA5ED3, 0xFA5F00)
              if t.startswith("cp (XIZ") or t.startswith("ld E,(XIZ") or t == "and E,0x3f"]
    print("     sub_FA5ED3 argument bounds: %s" % bounds)
    check("6a arg1 (XIZ+0x08) bounded at 0x21 = 33 parts",
          any(t == "cp (XIZ+0x08),0x21" for _, t in span(ins, 0xFA5ED3, 0xFA5F00)), "")
    check("6b arg2 (XIZ+0x0a) bounded at 0x40 = 64 channels",
          any(t == "cp (XIZ+0x0a),0x40" for _, t in span(ins, 0xFA5ED3, 0xFA5F00)), "")
    check("6c arg3 (XIZ+0x0c) masked to 6 bits = a parameter index",
          ins.get(0xFA5EDA) == "ld E,(XIZ+0x0c)" and ins.get(0xFA5EDD) == "and E,0x3f", "")

    print("\nFAILURES: %d" % fails)
    return 1 if fails else 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT))

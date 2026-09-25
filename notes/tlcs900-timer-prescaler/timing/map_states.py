#!/usr/bin/env python3
"""Join MAME's opcode tables to the databook states, and report the coverage.

MAME names each handler op_<MNEMONIC><SIZE><DST><SRC> -- op_ADCBMI is ADC, byte,
memory, immediate -- and the databook lists the same instructions by mnemonic and
operand form. That naming is the bridge; nothing here parses the book's opcode
patterns, which are far harder to get right.

The point of this script is the coverage number, not the join: any entry it
cannot map is an entry whose timing would have to be invented, which is the thing
being removed. It prints what it could not map rather than filling a default.

Usage: map_states.py <mame-tables.jsonl> <tlcs900-states.jsonl> <out.jsonl>
"""
import json
import sys
from collections import Counter, defaultdict

SIZES = {"B": "state_b", "W": "state_w", "L": "state_l"}
# handlers that dispatch a second opcode byte, or mark an invalid encoding:
# they consume no time of their own
NON_INSTRUCTIONS = {"op_DB", "oC8", "oD8", "op_80", "op_88", "op_90", "op_98",
                    "op_A0", "op_A8", "op_B0", "op_B8", "op_C0", "op_D0",
                    "op_E0", "op_E8", "op_F0"}


def operand_kind(tok):
    tok = tok.strip()
    if not tok:
        return None
    if tok.startswith("("):
        return "M"
    # the jump group writes a bare "mem" where other groups write "(mem)"
    if tok == "mem" or tok.endswith("mem"):
        return "M"
    if tok.startswith("#"):
        return "I"
    if tok in ("cc", "[cc"):
        return "CC"
    return "R"


def operand_forms(raw):
    """Operand-kind strings for one databook operand cell.

    The book marks optional operands with brackets -- "JP [cc,]mem",
    "RLD [A,](mem)" -- and MAME has separate handlers for the forms with and
    without them, so both are produced."""
    raw = (raw or "").strip()
    if not raw:
        return [""]
    if "," not in raw and ".(" in raw:
        raw = raw.replace(".(", ",(", 1)          # one row prints a period
    variants = [raw]
    if "[" in raw and "]" in raw:
        lo, hi = raw.index("["), raw.index("]")
        variants = [raw[:lo] + raw[lo + 1:hi] + raw[hi + 1:], raw[:lo] + raw[hi + 1:]]
    out = []
    for v in variants:
        kinds = "".join(k for k in (operand_kind(t) for t in v.split(",")) if k)
        for form in (kinds, kinds.replace("CC", "", 1), kinds.replace("CC", "R", 1)):
            if form not in out:
                out.append(form)
    return out


def doc_index(doc_rows):
    """(mnemonic, dst-kind, src-kind) -> {size: states}"""
    idx = defaultdict(dict)
    for r in doc_rows:
        mn = (r.get("mnemonic") or "").split("<")[0].strip().upper()
        if not mn:
            continue
        all_kinds = operand_forms(r.get("operands"))
        got = False
        for kinds in all_kinds:
            for letter, key in SIZES.items():
                v = r.get(key)
                if isinstance(v, int):
                    idx[(mn, kinds)][letter] = v
                    got = True
        raw_l = r.get("state_raw") or ""
        if "+2n" in raw_l:
            import re as _re
            m2 = _re.search(r"(\d+)\+2n", raw_l)
            if m2:
                for kinds in all_kinds:
                    idx[(mn, kinds)]["L"] = int(m2.group(1))
                    idx[(mn, kinds)]["L_per_shift"] = 2
                got = True
        if not got:
          raw_l = r.get("state_raw") or ""
          m = None
          if "+2n" in raw_l:
              import re as _re
              m = _re.search(r"(\d+)\+2n", raw_l)
          if m:
              for kinds in all_kinds:
                  idx[(mn, kinds)]["L"] = int(m.group(1))
                  idx[(mn, kinds)]["L_per_shift"] = 2
              got = True
        if not got:
          for kinds in all_kinds:
            # Sizeless instructions -- the jumps, calls and returns -- print one
            # state count with no B/W/L split, sometimes as "taken/not-taken".
            base, taken = parse_sizeless(r.get("state_raw"))
            if base is not None:
                idx[(mn, kinds)]["-"] = base
                if taken is not None:
                    idx[(mn, kinds)]["taken"] = taken
    return idx


def parse_sizeless(raw):
    """"7" -> (7, None);  "9/6 (T/F)" -> (6, 9), i.e. (not-taken, taken)."""
    if not isinstance(raw, str):
        return (raw, None) if isinstance(raw, int) else (None, None)
    t = raw.strip()
    if t.isdigit():
        return int(t), None
    import re as _re
    pairs = _re.findall(r"(\d+)\s*\(", t)
    if len(pairs) >= 2:
        nums = [int(x) for x in pairs]
        return min(nums), max(nums)
    head = t.split("(")[0].strip()
    if "/" in head:
        a, b = (x.strip() for x in head.split("/", 1))
        if a.isdigit() and b.isdigit():
            return int(b), int(a)      # printed taken/not-taken
    return None, None


def parse_opfunc(name, mnemonics):
    """All plausible (mnemonic, size, operand-kinds) splits, longest mnemonic
    first. CPL is both a mnemonic and CP+L, so the caller picks whichever split
    the databook actually has a row for rather than guessing here."""
    body = name[3:] if name.startswith("op_") else name
    if body.endswith("900"):
        body = body[:-3]        # op_SWI900 is SWI in 900 mode
    out = []
    for mn in sorted(mnemonics, key=len, reverse=True):
        if not mn or not body.startswith(mn):
            continue
        rest = body[len(mn):]
        if rest and rest[0] in SIZES:
            out.append((mn, rest[0], rest[1:]))
        out.append((mn, None, rest))
    return out


def main(tables_path, states_path, out_path):
    tables = [json.loads(l) for l in open(tables_path) if l.strip()]
    doc = [json.loads(l) for l in open(states_path) if l.strip()]
    idx = doc_index(doc)
    mnemonics = sorted({k[0] for k in idx}, key=len, reverse=True)

    mapped, unmapped, skipped = [], [], 0
    reasons = Counter()
    for e in tables:
        if e["opfunc"] in NON_INSTRUCTIONS:
            skipped += 1
            continue
        cands = parse_opfunc(e["opfunc"], mnemonics)
        if not cands:
            unmapped.append((e, "no mnemonic")); reasons["no mnemonic"] += 1; continue
        hit = None
        for mn, size, kinds in cands:
            forms = idx.get((mn, kinds))
            if forms is not None and (size is None or size in forms):
                hit = (mn, size, kinds, forms); break
            # The handler's size letter and the book's size column can disagree
            # where one of them is sizeless: op_DJNZB is a byte handler for an
            # instruction the book times by branch taken, and op_MINC1 carries no
            # size letter for a word-only instruction. Accept the other one when
            # it is unambiguous.
            if forms is not None:
                alt = [k for k in forms if k in ("B", "W", "L", "-")]
                if len(alt) == 1:
                    hit = (mn, size, kinds, {size or "-": forms[alt[0]]}); break
            # The handler name carries no operand letters for some instructions
            # (op_LDAW, op_SCCBR): fall back to the mnemonic's only form.
            if not kinds:
                same = [(k, v) for k, v in idx.items() if k[0] == mn]
                want = size if size else "-"
                vals = {v[want] for _, v in same if want in v}
                if len(vals) == 1:
                    form = next(k for k, v in same if want in v)
                    hit = (mn, size, form[1], dict(same[0][1], **{want: vals.pop()})); break
                # handler size letter absent from the book's columns (op_DJNZB on
                # a branch-timed instruction, op_MINC1 on a word-only one):
                # take the single value the book does give
                allv = {v2 for _, v in same for k2, v2 in v.items()
                        if k2 in ("B", "W", "L", "-")}
                if len(allv) == 1 and same:
                    hit = (mn, size, same[0][0][1], {want: allv.pop()}); break
        if hit is None:
            mn, size, kinds = cands[0]
            unmapped.append((e, "no form %s/%s" % (mn, kinds))); reasons["no operand form"] += 1; continue
        mn, size, kinds, forms = hit
        if size is None and "-" in forms:
            states = forms["-"]
        elif size is None:
            vals = sorted(set(v for k, v in forms.items() if k != "taken"))
            if len(vals) != 1:
                unmapped.append((e, "sizeless but %r" % forms)); reasons["sizeless, ambiguous"] += 1; continue
            states = vals[0]
        elif size in forms:
            states = forms[size]
        else:
            unmapped.append((e, "no %s state for %s/%s" % (size, mn, kinds))); reasons["size absent"] += 1; continue
        mapped.append(dict(e, mnemonic=mn, size=size, kinds=kinds, states=states))

    total = len(tables) - skipped
    print("table entries      : %d" % len(tables))
    print("  dispatch/invalid : %d" % skipped)
    print("  real instructions: %d" % total)
    print("  mapped to states : %d  (%.1f%%)" % (len(mapped), 100.0 * len(mapped) / total))
    print("  unmapped         : %d" % len(unmapped))
    for k, v in reasons.most_common():
        print("      %-22s %d" % (k, v))
    print()
    print("worst-covered opfuncs:")
    for name, n in Counter(e["opfunc"] for e, _ in unmapped).most_common(12):
        why = next(r for e, r in unmapped if e["opfunc"] == name)
        print("   %-14s %4d  %s" % (name, n, why))

    if mapped:
        old = sum(e["cycles"] for e in mapped) / len(mapped)
        new = sum(e["states"] for e in mapped) / len(mapped)
        print()
        print("mean cycles now %.2f -> mean states %.2f  (x%.2f)" % (old, new, new / old))

    with open(out_path, "w") as f:
        for e in mapped:
            f.write(json.dumps(e, sort_keys=True) + "\n")
    print("wrote %s" % out_path)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])

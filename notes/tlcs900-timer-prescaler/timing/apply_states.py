#!/usr/bin/env python3
"""Rewrite the cycle counts in MAME's 900tbl.hxx from the databook states.

Only the fourth field of each table entry changes; handlers and operands are
untouched. Entries the join could not reach keep their existing value and are
reported, so nothing is silently defaulted.

Usage: apply_states.py <900tbl.hxx> <mapped-states.jsonl> [--dry-run]
"""
import json
import re
import sys
from collections import Counter

# Named groups still take numbers, so refer to the surrounding text by name too:
# using group(5) for the trailing brace silently produced "0, 86," and dropped
# the brace.
ENTRY = re.compile(
    r"(?P<head>\{\s*&tlcs900_device::(?P<op>[A-Za-z_][A-Za-z0-9_]*)\s*,"
    r"\s*(?P<p1>[A-Za-z0-9_]+)\s*,"
    r"\s*(?P<p2>[A-Za-z0-9_]+)\s*,\s*)(?P<cyc>\d+)(?P<tail>\s*\})")
TABLE = re.compile(r"s_mnemonic(?P<suffix>_[0-9a-f]{2})?\[256\]\s*=")


def main(hxx_path, mapped_path, dry=False):
    want = {}
    for line in open(mapped_path):
        if not line.strip():
            continue
        r = json.loads(line)
        want[(r["table"], r["index"])] = r["states"]

    src = open(hxx_path).read()
    starts = sorted((m.start(), (m.group("suffix") or "")[1:] or "main") for m in TABLE.finditer(src))

    out, pos, changed, kept, delta = [], 0, 0, 0, Counter()
    for i, (tstart, name) in enumerate(starts):
        tend = starts[i + 1][0] if i + 1 < len(starts) else len(src)
        out.append(src[pos:tstart])
        body = src[tstart:tend]
        idx = 0
        pieces, last = [], 0
        for m in ENTRY.finditer(body):
            new = want.get((name, idx))
            if new is not None and new != int(m.group("cyc")):
                pieces.append(body[last:m.start()])
                pieces.append(m.group("head") + str(new) + m.group("tail"))
                last = m.end()
                changed += 1
                delta[new - int(m.group("cyc"))] += 1
            elif new is None:
                kept += 1
            idx += 1
        pieces.append(body[last:])
        out.append("".join(pieces))
        pos = tend
    out.append(src[pos:])
    result = "".join(out)

    print("entries rewritten : %d" % changed)
    print("entries untouched : %d  (no databook row, or already equal)" % kept)
    print("largest increases : %s" % ", ".join("%+d x%d" % kv for kv in delta.most_common(5)))
    if dry:
        print("(dry run, file not written)")
        return
    open(hxx_path, "w").write(result)
    print("wrote %s" % hxx_path)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], "--dry-run" in sys.argv)

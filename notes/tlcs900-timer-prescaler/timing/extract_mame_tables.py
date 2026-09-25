#!/usr/bin/env python3
"""Extract MAME's TLCS-900 opcode tables into JSONL, one row per table entry.

The tables in 900tbl.hxx are the thing the databook timings have to land on:
fifteen arrays of {opfunc, operand1, operand2, cycles} indexed by opcode byte.
This pulls them out so the mapping can be done and checked as data rather than
by editing 2000 lines of C++ by hand.

Usage: extract_mame_tables.py <900tbl.hxx> <out.jsonl>
"""
import json
import re
import sys

ENTRY = re.compile(
    # NB: not all handlers are named op_*; the C8/D8 prefix dispatchers are
    # called oC8/oD8 in MAME's own source, and requiring the prefix silently
    # dropped 18 entries from the main table.
    r"\{\s*&tlcs900_device::(?P<op>[A-Za-z_][A-Za-z0-9_]*)\s*,"
    r"\s*(?P<p1>[A-Za-z0-9_]+)\s*,"
    r"\s*(?P<p2>[A-Za-z0-9_]+)\s*,"
    r"\s*(?P<cyc>\d+)\s*\}")
TABLE = re.compile(r"s_mnemonic(?P<suffix>_[0-9a-f]{2})?\[256\]\s*=")


def main(src_path, out_path):
    src = open(src_path).read()
    starts = [(m.start(), (m.group("suffix") or "")[1:] or "main") for m in TABLE.finditer(src)]
    starts.sort()
    rows = []
    for i, (pos, name) in enumerate(starts):
        end = starts[i + 1][0] if i + 1 < len(starts) else len(src)
        body = src[pos:end]
        entries = list(ENTRY.finditer(body))
        if len(entries) != 256:
            print("  WARNING %-6s parsed %d entries, expected 256" % (name, len(entries)))
        for idx, m in enumerate(entries):
            rows.append({
                "table": name,
                "index": idx,
                "opfunc": m.group("op"),
                "operand1": m.group("p1"),
                "operand2": m.group("p2"),
                "cycles": int(m.group("cyc")),
            })
    with open(out_path, "w") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")

    tables = {}
    for r in rows:
        tables.setdefault(r["table"], 0)
        tables[r["table"]] += 1
    print("tables: %d, entries: %d" % (len(tables), len(rows)))
    print("  " + ", ".join("%s:%d" % kv for kv in sorted(tables.items())))
    real = [r for r in rows if r["opfunc"] not in ("op_DB",)]
    print("non-invalid entries: %d" % len(real))
    prefixes = sorted({r["opfunc"] for r in rows
                       if re.match(r"(op_)?o?[0-9A-F]{2}$", r["opfunc"].replace("op_", "", 1))
                       or re.match(r"o[0-9A-F]{2}$", r["opfunc"])})
    print("prefix dispatchers (not real instructions): %s" % ", ".join(prefixes))
    print("distinct opfuncs: %d" % len({r["opfunc"] for r in rows}))
    print("wrote %s" % out_path)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

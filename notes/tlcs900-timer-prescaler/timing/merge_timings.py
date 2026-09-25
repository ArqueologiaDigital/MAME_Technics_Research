#!/usr/bin/env python3
"""Merge the per-half-page transcriptions into one table, and check them.

The pages were rendered in overlapping halves so no row fell in the split, which
means rows near a boundary appear twice; they are deduplicated here on the cells
that identify an instruction form.

Checks worth failing on, because they catch transcription error rather than
book oddities:
  - "size" (e.g. BW-) must agree with which state slots are filled
  - state counts must be in a sane range
Rows the book itself prints oddly (sizeless RCF/SCF/CCF/ZCF with a single state,
DJNZ whose state splits on a condition rather than a size) are reported
separately, not treated as errors.

Usage: merge_timings.py <rows-dir> <out.jsonl>
"""
import json
import os
import sys
from collections import Counter

SIZELESS_OK = {"RCF", "SCF", "CCF", "ZCF", "NOP", "NORMAL", "MAX", "MIN", "HALT",
               "EI", "DI", "RETI", "RET", "RETD", "SWI", "LDF", "INCF", "DECF"}


def main(rows_dir, out_path):
    rows = []
    for fn in sorted(os.listdir(rows_dir)):
        if not fn.endswith(".jsonl"):
            continue
        for ln, line in enumerate(open(os.path.join(rows_dir, fn)), 1):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            r["_src"] = "%s:%d" % (fn, ln)
            rows.append(r)
    print("read %d rows from %d files" % (len(rows), len(os.listdir(rows_dir))))

    # dedupe: the same instruction form transcribed on both sides of a split
    seen, merged, dupes = {}, [], 0
    for r in rows:
        key = (r.get("mnemonic"), r.get("operands"), r.get("codes"), r.get("state_raw"))
        if key in seen:
            dupes += 1
            continue
        seen[key] = r
        merged.append(r)
    print("deduped %d boundary duplicates -> %d unique rows" % (dupes, len(merged)))

    size_mismatch, odd, bad_state, nonint = [], [], [], []
    for r in merged:
        size = (r.get("size") or "").strip()
        slots = []
        for k in ("state_b", "state_w", "state_l"):
            v = r.get(k)
            if isinstance(v, str):
                # the book prints a few states as text (conditions, formulas);
                # keep them visible rather than coercing them into a number
                if v.strip().isdigit():
                    v = int(v.strip())
                    r[k] = v
                else:
                    nonint.append((r, k, v))
                    v = None
                    r[k] = None
            if v is not None and not (1 <= v <= 40):
                bad_state.append(r)
            slots.append(v)
        if size in ("---", "") or r.get("mnemonic") in SIZELESS_OK:
            if all(v is None for v in slots):
                odd.append(r)
            continue
        if len(size) == 3:
            want = [c != "-" for c in size]
            # a formula cell (e.g. the shifts' "8+2n") is real content, not a
            # missing slot, so count it as filled for this check
            formula = {k for r2, k, _ in nonint if r2 is r}
            have = [(v is not None) or (k in formula)
                    for v, k in zip(slots, ("state_b", "state_w", "state_l"))]
            if want != have:
                size_mismatch.append(r)

    print("size/state slot mismatches : %d" % len(size_mismatch))
    for r in size_mismatch[:10]:
        print("   %-8s %-22s size=%-4s state=%r  [%s]"
              % (r.get("mnemonic"), r.get("operands"), r.get("size"), r.get("state_raw"), r["_src"]))
    print("rows the book prints without per-size states: %d" % len(odd))
    print("implausible state values   : %d" % len(bad_state))
    print("non-numeric state cells    : %d" % len(nonint))
    for r, k, v in nonint[:8]:
        print("   %-8s %-22s %s=%r  [%s]" % (r.get("mnemonic"), r.get("operands"), k, v, r["_src"]))

    vals = [v for r in merged for v in (r.get("state_b"), r.get("state_w"), r.get("state_l")) if v]
    print("state range %d..%d, most common: %s"
          % (min(vals), max(vals), Counter(vals).most_common(6)))
    print("groups: %d, mnemonics: %d"
          % (len({r.get("group") for r in merged}), len({r.get("mnemonic") for r in merged})))

    with open(out_path, "w") as f:
        for r in merged:
            f.write(json.dumps(r, sort_keys=True) + "\n")
    print("wrote %s" % out_path)
    return 1 if (bad_state or len(size_mismatch) > 5) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))

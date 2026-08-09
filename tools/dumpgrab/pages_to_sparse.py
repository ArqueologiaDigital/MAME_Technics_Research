#!/usr/bin/env python3
"""pages_to_sparse.py -- convert a pages JSONL into the sparse-binary + mask contract.

  pages_to_sparse.py pages.jsonl --out dump --base 0x48400000 --size 0x400000

Writes dump.bin, dump.mask and dump.json (the sidecar). Mask bytes carry the number of
frames that voted for the byte, capped at 255, so a later pass can weight by evidence.
If --base/--size are omitted they are taken from the address range present in the file,
rounded out to page boundaries.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dumpfmt  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pages")
    ap.add_argument("--out", required=True, help="output stem (writes .bin/.mask/.json)")
    ap.add_argument("--base", type=lambda s: int(s, 0))
    ap.add_argument("--size", type=lambda s: int(s, 0))
    ap.add_argument("--tool", default="c4-validate/pages_to_sparse.py")
    a = ap.parse_args()

    pages = dumpfmt.load_pages_jsonl(a.pages)
    if not pages:
        raise SystemExit("no pages")
    lo = min(addr for addr, _, _ in pages) & ~0xFF
    hi = max(addr + len(b) for addr, b, _ in pages)
    hi = (hi + 0xFF) & ~0xFF
    base = a.base if a.base is not None else lo
    size = a.size if a.size is not None else hi - base
    data, mask = dumpfmt.pages_to_sparse(pages, base, size)
    open(a.out + ".bin", "wb").write(bytes(data))
    open(a.out + ".mask", "wb").write(bytes(mask))
    rom = dumpfmt.guess_rom_for_base(base)
    meta = {"base": base, "size": size, "rom": rom, "tool": a.tool,
            "pages": sorted({addr & ~0xFF for addr, _, _ in pages})}
    json.dump(meta, open(a.out + ".json", "w"), indent=1)
    known = sum(1 for v in mask if v)
    print("%s.bin/.mask/.json  base 0x%08X size %d  known %d bytes over %d pages"
          % (a.out, base, size, known, len(meta["pages"])))


if __name__ == "__main__":
    sys.exit(main())

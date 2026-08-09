"""dumpfmt.py -- the interchange format shared by the KN7000 debug-screen dump tools.

THE CONTRACT (this is what an extractor must produce and what validate.py consumes)
-----------------------------------------------------------------------------------
A recovered dump is a *sparse image* of a CPU address range, expressed as two files of
identical length plus an optional sidecar:

  <stem>.bin    flat bytes; byte i is the value read at CPU address BASE + i.
                Bytes that were never recovered MUST be written as 0x00 (their value is
                meaningless -- the mask is authoritative).
  <stem>.mask   one byte per data byte: 0x00 = not recovered, 0x01 = recovered.
                (Values >1 are accepted and treated as "recovered with N frame votes",
                which validate.py can bucket with --by-votes.)
  <stem>.json   OPTIONAL sidecar, free-form, but these keys are understood:
                  base        int   CPU address of .bin offset 0            (else --base)
                  rom         str   "program" | "table" (oracle hint)
                  pages       list  [{"addr":int,"frames":int,"src":str}, ...]
                  tool        str   what produced it

Rationale: mask-as-bytes (not a bitmap) keeps it greppable, lets an extractor record a
vote count for free, and costs 4 MB for a 4 MB ROM -- irrelevant here.

ALTERNATIVE INPUT: pages JSONL
------------------------------
A frame-by-frame extractor may find it more natural to emit one JSON object per decoded
page. validate.py accepts that directly via --pages, and pages_to_sparse.py converts it:

  {"addr": 1212612864, "hex": "<512 hex chars>", "known": "<256 chars of 0/1>",
   "frame": "snap0007.png", "conf": [<256 floats, optional>]}

`known` may be omitted (all 256 bytes claimed). `addr` may be a "0x..." string.

ORACLES
-------
  program flash : file kn7000_program.rom, CPU base 0x48400000
  table   flash : file kn7000_table.rom,   CPU base 0x48000000
Addresses past the end of an oracle file have NO ground truth; validate.py counts them
separately and never scores them as right or wrong.
"""

import json
import os

ORACLES = {
    "program": 0x48400000,
    "table": 0x48000000,
}

PAGE = 256


def guess_rom_for_base(base):
    if 0x48400000 <= base < 0x48800000:
        return "program"
    if 0x48000000 <= base < 0x48400000:
        return "table"
    return None


def load_sparse(bin_path, mask_path=None, base=None):
    """Return (data: bytearray, mask: bytearray, base: int, meta: dict)."""
    data = bytearray(open(bin_path, "rb").read())
    if mask_path is None:
        cand = os.path.splitext(bin_path)[0] + ".mask"
        mask_path = cand if os.path.exists(cand) else None
    if mask_path:
        mask = bytearray(open(mask_path, "rb").read())
    else:
        mask = bytearray(b"\x01" * len(data))
    if len(mask) != len(data):
        raise SystemExit(
            "mask length %d != bin length %d" % (len(mask), len(data)))
    meta = {}
    side = os.path.splitext(bin_path)[0] + ".json"
    if os.path.exists(side):
        meta = json.load(open(side))
    if base is None:
        base = meta.get("base")
    if base is None:
        raise SystemExit("no base address: pass --base or provide a .json sidecar")
    return data, mask, int(base), meta


def load_pages_jsonl(path):
    """Return list of (addr, bytes(256), known(list[bool]) )."""
    out = []
    for line in open(path):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        o = json.loads(line)
        addr = o["addr"]
        if isinstance(addr, str):
            addr = int(addr, 0)
        hx = o["hex"]
        b = bytes.fromhex(hx)
        known = o.get("known")
        if known is None:
            k = [True] * len(b)
        else:
            k = [c not in ("0", ".", " ", "_") for c in known]
        if len(k) != len(b):
            raise SystemExit("page %08X: known/hex length mismatch" % addr)
        out.append((addr, b, k))
    return out


def pages_to_sparse(pages, base, size):
    """Merge decoded pages into (data, mask) covering [base, base+size)."""
    data = bytearray(size)
    mask = bytearray(size)
    for addr, b, known in pages:
        for i, v in enumerate(b):
            if not known[i]:
                continue
            off = addr + i - base
            if 0 <= off < size:
                data[off] = v
                if mask[off] < 255:
                    mask[off] += 1
    return data, mask

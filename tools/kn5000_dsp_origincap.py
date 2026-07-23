#!/usr/bin/env python3
"""kn5000_dsp_origincap.py -- decode a uPD6383GF uC-IF capture and locate the
per-effect DATA-POINTER ORIGIN poke.

Background (notes/kn5000-dsp-origin.md): continuous whole-frame execution proved
the data-pointer origin is NOT in the resident program -- the header is
byte-identical across effects yet unit-0 effects need different origins
(PARAMETRIC EQ = 0x19, gated reverb ~ 0x07).  So the origin must be a PER-EFFECT
HOST POKE sent over the uC-IF when that effect is selected.  This tool reads the
capture produced at exit (kn5000_dsp1_upload.{bin,txt}, driven by
tools/kn5000_dsp_origincap.lua with a chosen TYPEIDX) and reports every
pointer-load word in the stream, so the origin poke is READ, not inferred.

The pointer-load family (notes/kn5000-dsp-pointer.md, -header.md sect. 7):
  hi12 == 0x801 (absolute load) or 0x8xx, with lo12 in {820,821,822,825,827};
  addr8 = the loaded 8-bit pointer value.  Textual form: hi12.class4.addr8.lo12.

Each cmd-0x01 transfer is a 16-bit I-RAM word address (2 bytes) followed by
5-byte (36-bit) I-RAM words; other transfers (cmd 0x04, 0x09, 0x0C ...) carry
short setup payloads.  We decode 5-byte-aligned words after a 2-byte address
prefix (the alignment the coldboot capture's header loads validate: it recovers
801.0.70.821 / .6C.827 / .25.825 / .50.821 / .64.827 / .25.825 exactly).

Usage:
  python3 tools/kn5000_dsp_origincap.py <capture.txt> [--ptr 0x19] [--tail N]
  python3 tools/kn5000_dsp_origincap.py <capture.bin> --bin ...   (bin needs .txt too;
      the .txt carries the transfer framing, so pass the .txt)
"""
import argparse
import re
import sys

PTR_LO = {0x820, 0x821, 0x822, 0x825, 0x827}


def fields(w):
    """36-bit word -> (hi12, class4, addr8, lo12)."""
    return ((w >> 24) & 0xFFF, (w >> 20) & 0xF, (w >> 12) & 0xFF, w & 0xFFF)


def wtext(w):
    hi, cl, a8, lo = fields(w)
    return f"{hi:03X}.{cl}.{a8:02X}.{lo:03X}"


def parse_capture_txt(path):
    """Return [(idx, cmd, bytes)] from a upd6383 capture .txt hexdump."""
    transfers = []
    cur = None
    for line in open(path):
        m = re.match(r"transfer\s+(\d+): cmd 0x([0-9A-Fa-f]+)\s+(\d+) bytes", line)
        if m:
            cur = {"idx": int(m.group(1)), "cmd": int(m.group(2), 16),
                   "bytes": bytearray()}
            transfers.append(cur)
            continue
        m = re.match(r"\s*[0-9A-Fa-f]{4}:\s*((?:[0-9A-Fa-f]{2}\s*)+)$", line)
        if m and cur is not None:
            for b in m.group(1).split():
                cur["bytes"].append(int(b, 16))
    return transfers


def ptr_loads(payload):
    """Decode 5-byte I-RAM words after a 2-byte address prefix; return the list
    of (word_index, 36bit_word, fields) whose lo12 is a pointer-load.  Try
    offsets 0..2 and pick the first that tiles into whole 5-byte words."""
    for off in (2, 0, 1):
        n = len(payload) - off
        if n >= 5 and n % 5 == 0:
            words = [int.from_bytes(bytes(payload[off + k:off + k + 5]), "big")
                     for k in range(0, n, 5)]
            hits = [(i, w, fields(w)) for i, w in enumerate(words)
                    if fields(w)[3] in PTR_LO]
            return off, words, hits
    return None, [], []


def body_upload(t):
    """If transfer t is an I-RAM[84..] body upload (cmd 0x01, addr prefix 84),
    return its body bytes (5-byte words), else None."""
    b = t["bytes"]
    if t["cmd"] == 0x01 and len(b) >= 4 and ((b[0] << 8) | b[1]) == 84:
        return bytes(b[2:])
    return None


def leading_ptr(t):
    """The pointer-load word that OPENS a host-poke transfer (word after the
    2-byte I-RAM address prefix), or None.  These frame each effect's
    coefficient upload; the per-effect origin, if any, would be here."""
    b = t["bytes"]
    if t["cmd"] == 0x01 and len(b) >= 7:
        w = int.from_bytes(bytes(b[2:7]), "big")
        if fields(w)[3] in PTR_LO:
            return w
    return None


def map_effects(transfers, progsdir):
    """Match each body upload to its static algoNN image and, for each effect
    block, list the leading pointer-load of every host-poke transfer -- i.e.
    the effect->coefficient-base table.  Proves whether the origin is
    per-effect or a shared constant."""
    import os
    progs = {}
    for f in os.listdir(progsdir):
        m = re.match(r"algo(\d+)\.bin$", f)
        if m:
            progs[int(m.group(1))] = open(os.path.join(progsdir, f), "rb").read()

    bodies = []
    for k, t in enumerate(transfers):
        body = body_upload(t)
        if body is not None:
            match = sorted(a for a, img in progs.items() if img == body)
            bodies.append((k, t["idx"], len(body) // 5, match))

    print(f"# effect-block map: {len(bodies)} body uploads matched to static images\n")
    for bi in range(len(bodies)):
        k0, idx0, nw, match = bodies[bi]
        k1 = bodies[bi + 1][0] if bi + 1 < len(bodies) else len(transfers)
        loads = []
        for t in transfers[k0:k1]:
            w = leading_ptr(t)
            if w is not None:
                loads.append(wtext(w))
        algo = match[0] if len(match) == 1 else f"ambiguous({len(match)})"
        print(f"effect#{bi:2d} algo {str(algo):>13} ({nw:3d}w, t{idx0}): " + "  ".join(loads))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("capture", help="the upd6383 capture .txt")
    ap.add_argument("--ptr", default=None,
                    help="highlight loads whose addr8 == this value (e.g. 0x19)")
    ap.add_argument("--tail", type=int, default=0,
                    help="only report the last N transfers (0 = all)")
    ap.add_argument("--map", default=None, metavar="PROGSDIR",
                    help="effect-block map: match body uploads to algoNN images "
                         "in PROGSDIR (from kn5000_dsp_extract.py) and tabulate "
                         "each block's coefficient-base pointer loads")
    args = ap.parse_args()

    if args.map:
        map_effects(parse_capture_txt(args.capture), args.map)
        return

    target = int(args.ptr, 0) if args.ptr else None
    ts = parse_capture_txt(args.capture)
    if args.tail:
        ts = ts[-args.tail:]

    print(f"# {args.capture}: {len(ts)} transfers"
          + (f" (tail {args.tail})" if args.tail else ""))
    print("# pointer-load family lo12 in {820,821,822,825,827}; "
          "form hi12.class4.addr8.lo12")
    if target is not None:
        print(f"# TARGET: pointer loads carrying addr8 == 0x{target:02X}")
    print()

    target_hits = []
    for t in ts:
        off, words, hits = ptr_loads(t["bytes"])
        if not hits:
            continue
        strs = []
        for wi, w, (hi, cl, a8, lo) in hits:
            s = wtext(w)
            if target is not None and a8 == target:
                s = f"[{s}]"
                target_hits.append((t["idx"], wi, w))
            strs.append(s)
        print(f"transfer {t['idx']:4d} cmd0x{t['cmd']:02X} off{off}: " + "  ".join(strs))

    if target is not None:
        print()
        if target_hits:
            print(f"## FOUND {len(target_hits)} load(s) of 0x{target:02X}:")
            for idx, wi, w in target_hits:
                b = w.to_bytes(5, "big")
                print(f"   transfer {idx} word {wi}: {wtext(w)}  bytes = "
                      + " ".join(f"{x:02X}" for x in b))
        else:
            print(f"## NO pointer load of 0x{target:02X} found in this capture.")


if __name__ == "__main__":
    main()

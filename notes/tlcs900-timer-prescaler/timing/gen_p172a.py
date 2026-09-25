#!/usr/bin/env python3
"""Emit the transcribed rows of TLCS-900 page 172, upper half (section
"(8) Rotate and shift"), as JSONL.

Source image: scratchpad/tlcs/pages/p172-172_a.png  (1700x1144, top half of
the 1700x2200 page scan).  The final row (SRA<W> (mem)) is clipped by the
half-image edge and was read from the full-page scan p172-172.png.
"""
import json, os, sys

OUT = sys.argv[1] if len(sys.argv) > 1 else \
    "/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/333ba2a5-8d03-431a-88e6-27cc62a06548/scratchpad/tlcs/rows/p172a.jsonl"

# (group, size, mnemonic, operands, codes, length, state_raw)
DATA = []
for grp, imm_op, a_op, mem_op in [
    ("RLC", "E8", "F8", "78"),
    ("RRC", "E9", "F9", "79"),
    ("RL",  "EA", "FA", "7A"),
    ("RR",  "EB", "FB", "7B"),
    ("SLA", "EC", "FC", "7C"),
    ("SRA", "ED", "FD", "7D"),
]:
    DATA.append((grp, "BWL", grp,          "#4,r",  "C8+zz+r :%s:#4" % imm_op, "3",   "6.6.8+2n"))
    DATA.append((grp, "BWL", grp,          "A,r",   "C8+zz+r :%s" % a_op,      "2",   "6.6.8+2n"))
    DATA.append((grp, "BW-", grp + "<W>",  "(mem)", "80+zz+mem:%s" % mem_op,   "2+M", "8.8.-"))


def parse_state(raw):
    """Split a State cell into byte/word/long ints; non-numeric -> None."""
    parts = [p.strip() for p in raw.split(".")]
    # "8+2n" contains no period, "6.6.8+2n" -> ['6','6','8+2n']
    out = []
    for p in parts[:3]:
        out.append(int(p) if p.isdigit() else None)
    while len(out) < 3:
        out.append(None)
    return out


os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w") as fh:
    for grp, size, mnem, ops, codes, length, state_raw in DATA:
        b, w, l = parse_state(state_raw)
        fh.write(json.dumps({
            "page": 172,
            "group": grp,
            "size": size,
            "mnemonic": mnem,
            "operands": ops,
            "codes": codes,
            "length": length,
            "state_raw": state_raw,
            "state_b": b,
            "state_w": w,
            "state_l": l,
        }, ensure_ascii=False) + "\n")
print("wrote %d rows to %s" % (len(DATA), OUT))

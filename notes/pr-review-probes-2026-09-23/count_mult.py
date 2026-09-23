#!/usr/bin/env python3
# Q: does the KN7000 effects kernel ever READ the multiplier's MV/MU flags?
#
# Counts, across the disassembled PM words of the whole effect download pool,
# how many instructions use each ASTAT condition and how many name ASTAT at all.
# Answer 2026-09-23: MV is used as a condition 0 times in 6499 words, and ASTAT
# is named in exactly 2 instructions, both BIT TOGGLE ASTAT 0x00100000 (bit 20 =
# FLG1, not a multiplier flag).
#
# POSITIVE CONTROL, and it is the point: the same search finds IF MS x20,
# IF AV x7, IF GE x40, IF LT x34, IF NE x20, IF LE x12, IF EQ x3,
# IF FLAG3_IN x5.  A zero for MV is therefore a real zero and not a broken
# pattern -- which is the only reason the zero can be quoted.
import glob, re, collections, os
INSN = re.compile(r'^[0-9a-f]{4}: ([0-9a-f]{16}) (.*?)\s*$')
d = os.path.expanduser('~/compartilhado/kn7000_disassembly/disasm/dsp')
cnt = collections.Counter(); newpath=0; sat=0; multi=0; other=0; tot=0
ops = collections.Counter()
for p in sorted(glob.glob(os.path.join(d,'rec*.asm'))):
    for line in open(p, encoding='utf-8', errors='replace'):
        m = INSN.match(line)
        if not m: continue
        text = m.group(2).split(';')[0]
        if not re.search(r'\bR\d+ \* R\d+', text): continue   # fixed-point multiply only
        tot += 1
        w = int(m.group(1), 16)
        comp = w & 0x7fffff
        if (w >> 22) & 1:
            multi += 1; continue
        cu = (comp >> 20) & 3
        op = (comp >> 12) & 0xff
        if cu != 1: other += 1; continue
        ops[op] += 1
        if (op & 0x30) == 0x30 and (op & 0xc0) != 0: newpath += 1
        elif (op & 0xf0) == 0x00: sat += 1
        else: other += 1
print("fixed-point multiply instructions in the pool :", tot)
print("  multi-function (opcode bit22)               :", multi)
print("  single-function, NEW DRC MAC path           :", newpath)
print("  single-function, SAT family                 :", sat)
print("  single-function, other/unclassified         :", other)
print("  op-byte histogram (single-function mult):", {hex(k):v for k,v in ops.most_common()})

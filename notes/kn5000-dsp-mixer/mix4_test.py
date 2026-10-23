#!/usr/bin/env python3
"""mix4_test.py OUT.txt [FRAME] [LOG] -- the four-channel mixer test program: four D-RAM cells (0x05, 0x07, 0x08,
0x09, driven by the harness as sines of 220, 330, 440 and 660 Hz, standing in for the samples a host would write)
times four volumes (C-RAM 0..3), summed, presented to DO1 by the output stage's own presentation word.

Three things the core's model fixes, each measured on this program (README.md):
  - the D-RAM pointer is set only by the per-unit CALL (DRAM_UNIT_BASE, 0x05 for unit 0): no decoded word loads
    it, and a program whose walk does not net to zero drifts across frames;
  - the presentation multiplies the accumulator by a level in D-RAM 0x06 (0x86 for unit 1), so that cell holds
    0x7FFFFF and no sample;
  - the input stage deposits the tone generator's mix at (the pointer at frame start) + 2 and + 5, here 0x0C and
    0x0F, which no sample cell may be."""
import sys
from upd6383_asm import ldptr, rstcur, call, mul, acc_step, program, HOLD, PRESENT_UNIT0, DRAM_UNIT_BASE

header = [call(0), HOLD, PRESENT_UNIT0]  # the return lands two words after the CALL
body = [
    ldptr(0x00), rstcur(),
    mul('load', dp=2),           # P0 = vol0 * s0 (0x05; a HOLD step would skip the multiply), then over 0x06
    mul('load'),                 # acc = P0;      P1 = vol1 * s1
    mul('add'),                  # acc += P1;     P2
    mul('add'),                  # acc += P2;     P3
    acc_step('add'),             # acc += P3
    call(0),                     # return
]
vol = 0x200000                   # 0.25 each
b = DRAM_UNIT_BASE
cells = (b, b + 2, b + 3, b + 4)
text = program(header, body=body, cram={0: vol, 1: vol, 2: vol, 3: vol, 4: 0x7FFFFF},
               dram={0x06: 0x7FFFFF},
               sines=[(c, hz, 1 << 21) for c, hz in zip(cells, (220, 330, 440, 660))],
               frame=int(sys.argv[2]) if len(sys.argv) > 2 else 0,
               log=int(sys.argv[3]) if len(sys.argv) > 3 else 4410)
open(sys.argv[1], 'w').write(text)

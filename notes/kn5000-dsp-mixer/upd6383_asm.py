#!/usr/bin/env python3
"""upd6383_asm.py -- build uPD6383GF test programs from the DECODED word forms, as UPD6383_TESTPROG files for the
MAME core's harness (src/devices/cpu/upd6383/upd6383.cpp test_load()).

A 36-bit word is hi12 | class4 | addr8 | lo12 (technics-roms-disasm dsp/instruction-set.md, "Word format"). The
decoded ALU (same file, "THE ALU"): L := src[lo12[10:6]] (07 mem[p], 10 acc, 19 tempA, 1A tempB); class4 == A
multiplies P := coef[cursor++] * L and moves p by the signed addr8; hi12[3:1] picks the accumulator step
(0: acc <- P, 1: acc += P, 2: acc holds); hi12 bit 4 stores acc to mem[p] and clears it, before the ALU.
The product reaches the accumulator one word later.

Used as a library (word(), program()) by the test programs beside it."""

NOP = 0x0002000000                      # 000.2.00.000 -- NOT decoded in the core: it traps, so a frame holding it is discarded
HOLD = 0x0004200015                     # 004.2.00.015: the accumulator unchanged, no multiply, p unchanged (decoded)
FRAME_WAIT = 0x0C00A47407               # C00.A.47.407 at I-RAM 82: the frame terminator, matched exactly
PRESENT_UNIT0 = 0x0E30C00404            # E30.C.00.404 (epilogue w73): unit 0 -> DO1
SRC = {'mem': 0x07, 'acc': 0x10, 'tempA': 0x19, 'tempB': 0x1A}
ACT_NONE = 0x15                         # an action with no side effect (DETERMINED)


def word(hi12, class4, addr8, lo12):
    assert 0 <= hi12 < 0x1000 and 0 <= class4 < 16 and 0 <= lo12 < 0x1000
    return (hi12 << 24) | (class4 << 20) | ((addr8 & 0xFF) << 12) | lo12


def ldptr(nn):
    """801.0.NN.821: the C-RAM pointer <- NN"""
    return word(0x801, 0, nn, 0x821)


def rstcur():
    """801.0.00.021: the coefficient cursor back to its base"""
    return word(0x801, 0, 0, 0x021)


def call(unit=0):
    """404.1.0E.015 (unit 0) / 404.1.0F.015 (unit 1): END OF BLOCK, class 1, the unit in addr8. At stack depth 0 the
    core's frame sequencer calls the unit's body (I-RAM 84 / 200) and rebases the D-RAM pointer to 0x05 | unit << 7
    (DRAM_UNIT_BASE); inside a body the same word returns -- to the CALL's address + 2: the word after a CALL is skipped. The
    accumulator holds."""
    return word(0x404, 1, 0x0E + unit, 0x015)


UNIT0_ENTRY = 84
DRAM_UNIT_BASE = 0x05


def dptr(nn):
    """000.1.NN.000: the D-RAM (state RAM) pointer <- NN"""
    return word(0x000, 1, nn, 0x000)


def mul(step, src='mem', dp=1, store=False):
    """a class-A word: P := coef[cursor++] * src; p += dp; the accumulator takes the PREVIOUS product per step
    ('load' acc <- P, 'add' acc += P, 'hold'). The core skips the multiply on a 'hold' word."""
    op = {'load': 0, 'add': 1, 'hold': 2}[step]
    return word((op << 1) | (0x10 if store else 0), 0xA, dp, (SRC[src] << 6) | ACT_NONE)


def acc_step(step):
    """no multiply (class 2, p unchanged): the accumulator takes the previous product per step"""
    op = {'load': 0, 'add': 1, 'hold': 2}[step]
    return word(op << 1, 0x2, 0, ACT_NONE)


def program(words, cram=None, dram=None, rf=None, sines=(), frame=0, log=0, body=()):
    """the UPD6383_TESTPROG text: words from I-RAM 0, HOLD words up to 81, the terminator at 82; `body', when given,
    from I-RAM 84 (unit 0's entry, reached by call())"""
    assert len(words) <= 82
    out = ['F %d' % frame]
    if log:
        out.append('L %d' % log)
    full = list(words) + [HOLD] * (82 - len(words)) + [FRAME_WAIT]
    out += ['I %X %010X' % (i, w) for i, w in enumerate(full)]
    out += ['I %X %010X' % (UNIT0_ENTRY + i, w) for i, w in enumerate(body)]
    out += ['C %X %06X' % (a, v & 0xFFFFFF) for a, v in sorted((cram or {}).items())]
    out += ['D %X %06X' % (a, v & 0xFFFFFF) for a, v in sorted((dram or {}).items())]
    out += ['R %X %06X' % (a, v & 0xFFFFFF) for a, v in sorted((rf or {}).items())]
    out += ['S %X %g %g' % s for s in sines]
    return '\n'.join(out) + '\n'

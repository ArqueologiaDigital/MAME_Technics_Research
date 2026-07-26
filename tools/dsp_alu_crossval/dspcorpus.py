#!/usr/bin/env python3
"""dspcorpus.py -- load the whole uPD6383 word corpus (kernel + epilogue + bodies)
straight out of the Sub CPU ROM.  Scratchpad-only; touches nothing in
kn5000-roms-disasm/dsp/.
"""
import os
import sys
import collections

TOOLS = "/home/fsanches/compartilhado/kn7000_mame/tools"
ROMS = "/home/fsanches/compartilhado/kn5000-roms-disasm/original_ROMs"
SUB = os.path.join(ROMS, "kn5000_subprogram_v142.rom")
MAIN = os.path.join(ROMS, "kn5000_v10_program.rom")

sys.path.insert(0, TOOLS)
import kn5000_dsp_extract as E          # noqa: E402
import kn5000_dsp_coeffs as C           # noqa: E402


def fields(w):
    return (w >> 24) & 0xFFF, (w >> 20) & 0xF, (w >> 12) & 0xFF, w & 0xFFF


def fmt(w):
    hi, cl, ad, lo = fields(w)
    return "%03X.%X.%02X.%03X" % (hi, cl, ad, lo)


def load():
    rom = E.Rom(SUB)
    try:
        names = C.effect_names(MAIN)
    except Exception:
        names = {}
    imgs = {}
    for i in range(100):
        try:
            iram, _c, _o = E.parse_stream(rom, rom.u32le(E.ALGO_TABLE + 4 * i))
        except Exception:
            continue
        if iram:
            imgs[i] = [int.from_bytes(bytes(w), "big")
                       for _a, ws, _l in iram for w in ws]
    return rom, names, imgs


def kernel_blob(rom, cpu_addr):
    """Decode one canned op-3 record at cpu_addr -> (cmd, iram_addr, [words])."""
    b0 = rom.u8(cpu_addr)
    b1 = rom.u8(cpu_addr + 1)
    op = b0 >> 4
    ln = (((b0 & 0x0F) << 8) | b1) - 2
    assert op == 3, op
    body = rom.slice(cpu_addr + 2, ln)
    cmd = body[0]
    iram_addr = (body[1] << 8) | body[2]
    ws = []
    p = 3
    while p + 5 <= len(body):
        ws.append(int.from_bytes(body[p:p + 5], "big"))
        p += 5
    return cmd, iram_addr, ws


KERNEL_ADDR = 0x01E496       # 60-word common header, I-RAM 0..59
EPILOGUE_ADDR = 0x01E63C     # 23-word output stage, I-RAM 60..82


def distinct_images(imgs, drop_malformed=True):
    """De-duplicate byte-identical images (the 12 reverb presets share one).

    MALFORMED streams are dropped: the word format is MEASURED to have bits
    36..39 always zero, so any image containing such a word is a misaligned
    parse, not a microprogram.  This removes algo 79 ('GEQ', 22/48 bad words)
    and algo 88 ('ROOM', 78/132 bad) -- exactly the two images the generated
    dsp/disasm/ tree also omits.  Leaves 38 images / 2974 words.
    """
    seen = {}
    for a, ws in sorted(imgs.items()):
        if drop_malformed and any((w >> 36) & 0xF for w in ws):
            continue
        key = tuple(ws)
        seen.setdefault(key, []).append(a)
    return seen

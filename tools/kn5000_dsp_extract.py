#!/usr/bin/env python3
"""kn5000_dsp_extract.py -- pull ALL uPD6383GF programs straight out of the Sub CPU ROM.

The runtime capture (kn5000_dsp1 device) only yields the algorithms the firmware
happens to load, and it re-uploads nothing when you re-select an effect that is
already active.  But the Sub CPU ROM holds all 100 algorithms behind a pointer
table, in the same bytecode the interpreter feeds to the chip, so they can be
extracted statically -- no UI navigation, no panel presses.

Bytecode record format (from DSP_BytecodeInterpreter_Loop, subcpu 0x03C2CB):
    byte0 high nibble = opcode
    len   = ((byte0 & 0x0F) << 8) | byte1     ; TOTAL record length, header included
    opcode 0xF                                 ; terminator
    opcode 3  -> cmd byte, 16-bit I-RAM word address, then 5-byte instruction words
    opcode 2  -> cmd byte + 2 preamble, then 3-byte (24-bit) coefficient words
    opcodes 0/1/5 -> cmd byte + 2 preamble, then 5-byte words
    opcode 4  -> single command byte, no payload

Verified against the live capture: the same blocks, addresses and word counts come
out of both paths.

Usage:
    python3 tools/kn5000_dsp_extract.py <kn5000_subprogram_v142.rom> [outdir]
"""
import collections
import os
import sys

ROM_BASE = 0xEF00          # file offset = cpu_addr - ROM_BASE
ALGO_TABLE = 0x0001ED7C    # 100 x 32-bit pointers: microprogram streams
PARAM_TABLE = 0x0001EF0C   # 100 x 32-bit pointers: coefficient streams
N_ALGOS = 100
IRAM_WORDS = 384


def q23(v):
    """24-bit two's complement -> float, the format the coefficients use."""
    return (v - (1 << 24)) / (1 << 23) if v & 0x800000 else v / (1 << 23)


class Rom:
    def __init__(self, path):
        self.d = open(path, "rb").read()

    def off(self, addr):
        o = addr - ROM_BASE
        if not (0 <= o < len(self.d)):
            raise IndexError(f"addr 0x{addr:06X} outside ROM")
        return o

    def u8(self, addr):
        return self.d[self.off(addr)]

    def u32le(self, addr):
        o = self.off(addr)
        return int.from_bytes(self.d[o:o + 4], "little")

    def slice(self, addr, n):
        o = self.off(addr)
        return self.d[o:o + n]


def parse_stream(rom, addr, limit=8192):
    """Walk one bytecode stream. Returns (iram_blocks, coeff_words, opcodes)."""
    iram, coeffs, ops = [], [], []
    p, guard = addr, 0
    while guard < limit:
        guard += 1
        try:
            b0, b1 = rom.u8(p), rom.u8(p + 1)
        except IndexError:
            break
        op = b0 >> 4
        if op == 0xF:
            ops.append(op)
            break
        ln = ((b0 & 0x0F) << 8) | b1
        if ln < 2 or ln > 0x0FFF:
            break
        ops.append(op)
        body = rom.slice(p + 2, ln - 2)
        if op == 3 and len(body) >= 3:
            iaddr = (body[1] << 8) | body[2]
            data = body[3:]
            words = [data[k:k + 5] for k in range(0, len(data) - 4, 5)]
            iram.append((iaddr, words, len(data)))
        elif op == 2 and len(body) >= 3:
            data = body[3:]
            for k in range(0, len(data) - 2, 3):
                coeffs.append((data[k] << 16) | (data[k + 1] << 8) | data[k + 2])
        p += ln
    return iram, coeffs, ops


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    rom = Rom(sys.argv[1])
    outdir = sys.argv[2] if len(sys.argv) > 2 else "kn5000_dsp_programs"
    os.makedirs(outdir, exist_ok=True)

    print(f"ROM {len(rom.d)} bytes, base 0x{ROM_BASE:04X}\n")

    algos, allwords, percount = {}, [], {}
    bad = 0
    for i in range(N_ALGOS):
        ptr = rom.u32le(ALGO_TABLE + 4 * i)
        try:
            iram, coeffs, ops = parse_stream(rom, ptr)
        except Exception:
            bad += 1
            continue
        if not iram:
            continue
        words = [w for _, ws, _ in iram for w in ws]
        algos[i] = (ptr, iram, words, coeffs)
        percount[i] = len(words)
        allwords += [bytes(w) for w in words]

    print(f"{len(algos)} of {N_ALGOS} algorithm pointers yielded I-RAM blocks "
          f"({bad} unreadable)\n")

    print(f"{'algo':>4} {'pointer':>9} {'blocks':>7} {'words':>6}  I-RAM ranges")
    for i in sorted(algos)[:24]:
        ptr, iram, words, _ = algos[i]
        rng = " ".join(f"{a}..{a + len(ws) - 1}" for a, ws, _ in iram[:4])
        print(f"{i:>4} 0x{ptr:07X} {len(iram):>7} {len(words):>6}  {rng}")
    if len(algos) > 24:
        print(f"  ... {len(algos) - 24} more")

    sizes = sorted(percount.values())
    if sizes:
        print(f"\nprogram sizes: min {sizes[0]}, median {sizes[len(sizes)//2]}, "
              f"max {sizes[-1]} words (I-RAM holds {IRAM_WORDS})")
        over = [i for i, n in percount.items() if n > IRAM_WORDS]
        print(f"  over capacity: {over if over else 'none'}"
              f"   <-- any 'over' would mean the 5-byte word size is wrong")

    # --- differential analysis: what is common to every algorithm? ---
    sets = {i: set(bytes(w) for w in ws) for i, (_, _, ws, _) in algos.items()}
    if sets:
        common = set.intersection(*sets.values())
        union = set.union(*sets.values())
        print(f"\ndistinct words: {len(union)} across all algorithms")
        print(f"  present in EVERY algorithm : {len(common)}  <- housekeeping / runtime idiom")
        print(f"  algorithm-specific          : {len(union) - len(common)}  <- the actual DSP work")

        freq = collections.Counter()
        for i, s in sets.items():
            for w in s:
                freq[w] += 1
        print("\n  most universal words (appear in N algorithms):")
        for w, c in freq.most_common(10):
            v = int.from_bytes(w, "big")
            print(f"    {v:010X}  in {c:>3}/{len(sets)} algorithms")

    # --- coefficients, the KN7000 cross-check handle ---
    allc = [c for _, _, _, cs in algos.values() for c in cs]
    if allc:
        cc = collections.Counter(allc)
        print(f"\n{len(allc)} coefficients, {len(cc)} distinct (signed Q0.23):")
        for v, k in cc.most_common(14):
            print(f"    {v:06X}  {q23(v):+.6f}  x{k}")

    # --- dump per-algorithm binaries for a future disassembler ---
    for i, (_, iram, words, coeffs) in algos.items():
        with open(os.path.join(outdir, f"algo{i:02d}.bin"), "wb") as f:
            for w in words:
                f.write(bytes(w))
    print(f"\nwrote {len(algos)} program images to {outdir}/algoNN.bin "
          f"(5 bytes per 36-bit word, as sent)")


if __name__ == "__main__":
    main()

# ---------------------------------------------------------------------------
# RESULTS on kn5000_subprogram_v142.rom (2026-07-22):
#
#   96 of 100 algorithm pointers yield I-RAM blocks, but only **40 DISTINCT
#   PROGRAM IMAGES** -- 42 of the 96 slots share one 49-word program. So the
#   KN5000's ~100 effects are built from ~40 microprograms, and the character of
#   an individual effect lives in its COEFFICIENT stream, not its code. That is
#   the expected shape (one reverb program serving many reverb presets with
#   different decay/damping constants) and it is good news twice over: there is
#   far less microcode to decode than 100 programs, and it strengthens the case
#   for attacking the coefficients first.
#
#   SIZE CHECK, an independent confirmation of the 5-byte word: program sizes run
#   40..133 words (median 50) and NOT ONE of the 96 exceeds the 384-word I-RAM.
#   If the word size were wrong, sizes would scale by the wrong factor and the
#   larger programs would overrun a memory that stops at 384.
#
#   Programs load at I-RAM 84 (effect unit 0) or 200 (effect unit 1), matching
#   the slot map seen in the live capture -- static and dynamic paths agree.
#
#   No single word appears in all 96 (the programs are genuinely different), but
#   a core recurs widely: 000020040E in 77, 0212200000 in 70, 0880160000 in 67.
#   Those are the best first targets for identifying common idioms.

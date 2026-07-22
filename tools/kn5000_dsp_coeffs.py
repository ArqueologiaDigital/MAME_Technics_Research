#!/usr/bin/env python3
"""kn5000_dsp_coeffs.py -- decode the uPD6383GF COEFFICIENT streams (PARAM_TABLE).

Companion to kn5000_dsp_extract.py, which handles the ALGO_TABLE (the I-RAM
microcode).  The 100 PARAM_TABLE pointers at 0x0001EF0C point at a *second*
bytecode stream per effect slot: the one that fills C-RAM/D-RAM and the external
DRAM delay controller.  Since only ~40 distinct microprograms serve ~100 effects,
this stream is where an individual effect's character actually lives.

STREAM SHAPE (measured, all 100 slots)
    Every param stream is a level-1 bytecode stream with the opcode sequence
        [0 4 (0 4)? 5 4 1 2 4 F]
    i.e. one or two type-0 records, a type-5 record, a type-1 record, and a
    type-2 record, separated by bare type-4 command bytes.

    * type 0/1/5 records: 3-byte header/preamble, then a run of 5-BYTE ENTRIES
    * type 2 records    : 3-byte header/preamble, then a run of 3-BYTE words
                          (raw 24-bit C-RAM/D-RAM writes)

FIVE-BYTE ENTRY FORMAT (derived here; see notes/kn5000-dsp-coefficients.md)
        byte0        = mode
        bytes1..3    = 24-bit big-endian payload
        byte4        = selector / destination tag
    mode 0x00  payload is a small value, selector 0x00
    mode 0x0A  payload is a signed Q0.23 COEFFICIENT     ("raw", per the docs)
    mode 0x0B  payload is an INTEGER DELAY LENGTH in DRAM words
    other      parameter-modified entry (payload is a base value the level-2
               translator scales by a user parameter)

    The mode nibble matches the documented level-1 handler-0 three-way branch
    (0x00 = static, 0x0A = raw, else = param-modified).

Usage:
    python3 tools/kn5000_dsp_coeffs.py <kn5000_subprogram_v142.rom> [--csv out.csv]
"""
import collections
import sys

ROM_BASE = 0xEF00
ALGO_TABLE = 0x0001ED7C
PARAM_TABLE = 0x0001EF0C
ROUTING = 0x0001ED6D
N_ALGOS = 100

# See notes/kn5000-dsp-coefficients.md for the sample-rate argument.
FS = 48000.0


def q23(v):
    """24-bit two's complement -> float (signed Q0.23)."""
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


def parse_param_stream(rom, addr, limit=512):
    """Walk one PARAM_TABLE stream.

    Returns dict with:
        entries : list of (record_op, mode, payload24, selector)
        raw24   : list of 24-bit words from type-2 records
        ops     : the opcode sequence
    """
    entries, raw24, ops = [], [], []
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
        if op in (0, 1, 5) and len(body) >= 3:
            data = body[3:]
            for k in range(0, len(data) - 4, 5):
                e = data[k:k + 5]
                entries.append((op, e[0], (e[1] << 16) | (e[2] << 8) | e[3], e[4]))
        elif op == 2 and len(body) >= 3:
            data = body[3:]
            for k in range(0, len(data) - 2, 3):
                raw24.append((data[k] << 16) | (data[k + 1] << 8) | data[k + 2])
        p += ln
    return {"entries": entries, "raw24": raw24, "ops": ops, "ptr": addr}


def load_all(rom):
    """Returns {slot: parsed} for all 100 PARAM_TABLE slots."""
    out = {}
    for i in range(N_ALGOS):
        ptr = rom.u32le(PARAM_TABLE + 4 * i)
        try:
            out[i] = parse_param_stream(rom, ptr)
        except Exception:
            pass
    return out


def coeffs_of(parsed):
    """The mode-0x0A raw Q0.23 coefficients of one slot."""
    return [v for _, m, v, _ in parsed["entries"] if m == 0x0A]


def delays_of(parsed):
    """The mode-0x0B integer delay lengths of one slot."""
    return [v for _, m, v, _ in parsed["entries"] if m == 0x0B]


def ms(n, fs=FS):
    return 1000.0 * n / fs


NAME_ROM_BASE = 0x33568   # kn5000_v10_program.rom, LAST entry of a descending
NAME_STRIDE = 18          # 16-char name + 0x00 0xFF; index 0 = " NO OPERATION "


def effect_names(path):
    """{algo_id: name} from the main-CPU program ROM's descending name table.

    Anchor check: index 20 must read "CONCERT REVERB 1", which is the one
    algorithm-ID<->name pair independently documented (kn5000-docs
    audio-subsystem.md, "0x0014 = algorithm 20 = CONCERT REVERB 1").
    """
    d = open(path, "rb").read()
    n = {}
    for i in range(N_ALGOS):
        a = NAME_ROM_BASE - NAME_STRIDE * i
        n[i] = d[a:a + 16].decode("latin1").strip()
    assert n[20] == "CONCERT REVERB 1", n[20]
    return n


def kn7000_float_set(image, records_tsv):
    """All IEEE-754 floats in (1e-4, 1.0] inside the KN7000 effects-DSP records.

    image        = kn7000_program_decompressed.bin
    records_tsv  = kn7000_disassembly/dsp/records.tsv (col 1 = rom_off, col 3 = len)
    Both endiannesses are tried, because the record payload is byte-swapped
    relative to the SHARC's own word order in places.
    """
    import math
    import struct
    d = open(image, "rb").read()
    out = set()
    for line in open(records_tsv):
        if line.startswith("#"):
            continue
        c = line.split("\t")
        off, n = int(c[1], 16), int(c[3])
        b = d[off:off + n]
        for k in range(0, len(b) - 3, 4):
            for e in ("<", ">"):
                f = struct.unpack(e + "f", b[k:k + 4])[0]
                if math.isfinite(f) and 1e-4 < abs(f) <= 1.0000001:
                    out.add(round(f, 6))
    return out


def compare_kn7000(slots, k7):
    """Correlation test: KN5000 Q0.23 coefficients vs KN7000 SHARC float constants.

    Splits both sets into 'round to 2 decimal places' and 'not round', because
    a match between two round decimals carries almost no information (there are
    only ~100 such values in [0,1]) while a match between two arbitrary
    24-bit/32-bit values would be extraordinary.
    """
    def rnd2(x):
        return abs(abs(x) * 100 - round(abs(x) * 100)) < 1e-6

    k5 = set(round(q23(v), 6) for s in slots.values() for v in s["raw24"])
    k5 |= set(round(q23(v), 6) for s in slots.values()
              for _, m, v, _ in s["entries"] if m == 0x0A and v > 0xFFFF)
    k5r = set(round(abs(x), 2) for x in k5 if rnd2(x))
    k7r = set(round(abs(x), 2) for x in k7 if rnd2(x))
    k5n = set(x for x in k5 if not rnd2(x))
    k7n = set(x for x in k7 if not rnd2(x))
    nonround = sorted(x for x in k7n
                      if any(abs(abs(x) - abs(y)) < 1e-6 for y in k5n))
    return {
        "k5": len(k5), "k7": len(k7),
        "round_k5": len(k5r), "round_k7": len(k7r),
        "round_shared": sorted(k5r & k7r),
        "round_expected_if_independent": len(k5r) * len(k7r) / 100.0,
        "nonround_k5": len(k5n), "nonround_k7": len(k7n),
        "nonround_shared": nonround,
    }


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    rom = Rom(sys.argv[1])
    slots = load_all(rom)
    routing = rom.slice(ROUTING, 5)

    print(f"ROM {len(rom.d)} bytes; routing bytes {routing.hex()} "
          f"(effect units -> DSP1/DSP2)\n")

    ptrs = [rom.u32le(PARAM_TABLE + 4 * i) for i in range(N_ALGOS)]
    print(f"{N_ALGOS} PARAM_TABLE pointers, {len(set(ptrs))} distinct")

    modes = collections.Counter()
    for s in slots.values():
        for _, m, _, _ in s["entries"]:
            modes[m] += 1
    print("\nentry modes:")
    for m, c in sorted(modes.items()):
        print(f"    0x{m:02X}  x{c}")

    allc = [v for s in slots.values() for v in coeffs_of(s)]
    cc = collections.Counter(allc)
    print(f"\n{len(allc)} raw coefficients, {len(cc)} distinct (signed Q0.23):")
    for v, k in cc.most_common(20):
        print(f"    {v:06X}  {q23(v):+.6f}  x{k}")
    print(f"    negatives: {sum(1 for v in allc if v & 0x800000)}")

    alld = [v for s in slots.values() for v in delays_of(s)]
    dc = collections.Counter(alld)
    print(f"\n{len(alld)} delay lengths, {len(dc)} distinct "
          f"(ms @ {FS/1000:.1f} kHz):")
    for v, k in sorted(dc.items()):
        print(f"    {v:6d}  {ms(v):8.3f} ms   x{k}")

    allr = [v for s in slots.values() for v in s["raw24"]]
    rc = collections.Counter(allr)
    print(f"\n{len(allr)} type-2 raw 24-bit words, {len(rc)} distinct; top:")
    for v, k in rc.most_common(10):
        print(f"    {v:06X}  {q23(v):+.6f}  x{k}")

    names = {}
    if "--names" in sys.argv:
        names = effect_names(sys.argv[sys.argv.index("--names") + 1])

    print("\nper-slot summary (id, name, ptr, #coef, delay taps in samples):")
    for i in sorted(slots):
        s = slots[i]
        d = delays_of(s)
        print(f"  {i:>3} {names.get(i, ''):<17} 0x{s['ptr']:07X} "
              f"{len(coeffs_of(s)):>4}  {d}")

    if "--kn7000" in sys.argv:
        j = sys.argv.index("--kn7000")
        k7 = kn7000_float_set(sys.argv[j + 1], sys.argv[j + 2])
        r = compare_kn7000(slots, k7)
        print("\n=== KN5000 <-> KN7000 constant correlation ===")
        for k, v in r.items():
            print(f"  {k}: {v}")

    if "--csv" in sys.argv:
        path = sys.argv[sys.argv.index("--csv") + 1]
        with open(path, "w") as f:
            f.write("slot,ptr,record_op,mode,hex,q23,int,selector\n")
            for i in sorted(slots):
                s = slots[i]
                for op, m, v, sel in s["entries"]:
                    f.write(f"{i},0x{s['ptr']:07X},{op},0x{m:02X},"
                            f"{v:06X},{q23(v):.8f},{v},0x{sel:02X}\n")
        print(f"\nwrote {path}")


if __name__ == "__main__":
    main()

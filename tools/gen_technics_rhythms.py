#!/usr/bin/env python3
# gen_technics_rhythms.py -- synthesize a "Technics Rhythms" resource image for the
# KN7000 ("8 Beat 1" fix, Phase B).
#
# ============================ INTEGRITY STATEMENT ============================
# THIS EMITS A *SYNTHETIC* CONTAINER. It is NOT a dump of the KN7000's rhythm
# data flash (which remains undumped, ~4.1 MB). Per the project integrity
# policy, every byte in the output is either
#   (a) a verbatim copy of REAL dumped bytes (sources below), or
#   (b) an obviously-synthetic placeholder that announces itself (names ending
#       in " ?"), never a fabricated "plausible" value.
#
# REAL bytes reused verbatim:
#   * The intact 0x1248-byte directory prefix of the truncated resource copy in
#     the table flash @0x483E828C (file 0x3E828C of kn7000_table.rom): magic
#     "Technics Rhythms", header (COUNT=0xDD=221), the full 0x800-entry u16BE
#     nametable, all 169 local u24BE subtable offsets, the 8-entry aux table.
#     (The copy was born truncated: only the directory was ever written to
#     flash; all record payloads are missing. Verified byte-by-byte.)
#   * The 8 aux (count-in/metronome) records, byte-copied from the prog-ROM
#     stub resource @0x48729988 (+0x104E..+0x11BA). Justified: the copy's aux
#     offset deltas (0,0x15,0x31,0x54,0x7E,0xAF,0xE7,0x126) and area length
#     (0x16C) are IDENTICAL to the stub's, and the copy's only 2 surviving
#     payload bytes (0x1246/0x1247 = 00 00) match the stub's aux[0].
#   * Each local record's payload = the stub's complete record 0 ("8 Beat 1",
#     +0x11BA, 0x530A bytes: 13-byte name + 0x71-byte header + 20-entry u24BE
#     section table (max +0x4CA2) + sections + embedded "Technics Pads" bank
#     boundary at +0x530A), with ONLY the 13-byte name field rewritten.
#     Where the real inter-record gap (real record size, preserved in the real
#     subtable offsets) is smaller than 0x530A the copy is truncated at the
#     slot boundary (name/header/section-table always survive; min real gap
#     0x1D9E > 0xC6 where sections start).
#
# Names:
#   * The 52 styles whose nametable entries are 0x4000-class resolve through
#     the SECONDARY subtable at table ROM 0x48244F78, which is INTACT in the
#     dump -- the firmware reads it directly, so those 52 display their REAL
#     names ("Country Rock ", "Musette Waltz", "70s Orchestra", ...). This
#     container only preserves the (real) nametable entry values.
#   * The 168 plain-entry styles' real names existed only in the never-dumped
#     rhythm flash. They are emitted as DISTINCT placeholders derived from the
#     byte-verified genre tables (prog 0x48735EE4): "<GENRE-TAG> <slot> ?",
#     e.g. "BALLAD 04 ?". The trailing " ?" marks them as synthetic.
#   * Local record 122 is referenced by no factory ID (its panel ordinal's
#     name resolves via the secondary catalog): named "NO REF 122 ?".
#
# Sources (all byte-verified in the Phase B decode, 2026-07-18):
#   kn7000_table.rom   (table flash dump, base 0x48000000; truncated copy at
#                       file 0x3E828C, secondary subtable at file 0x244F78)
#   kn7000_program_decompressed.bin (program flash, base 0x48400000; stub
#                       resource at file 0x329988 = 0x48729988; genre table at
#                       file 0x335EE4 = 0x48735EE4, count u16 @0x336064,
#                       ID->index formula ((id&0xF00)>>1)|(id&0x7F) from code
#                       0x48435B40-4E / 0x48433C28-38 / 0x48433DBF-CD;
#                       resolver semantics from 0x48433AC4)
#   Full format notes: kn7000_mame/notes/sequenced-playback-and-style-data-
#   rootcause.md (appendix) + the Phase B decode reports.
#
# Deterministic: output depends only on the two input ROM images.
#
# Usage:
#   gen_technics_rhythms.py [--table PATH] [--prog PATH] [--out PATH] [--verify]
# =============================================================================

import argparse
import struct
import sys

# ---- byte-verified layout constants -----------------------------------------
COPY_OFF   = 0x3E828C   # truncated "Technics Rhythms" copy in table ROM
COPY_PREFIX_LEN = 0x1248  # surviving real span (rest of flash erased 0xFF)
SEC_OFF    = 0x244F78   # intact secondary subtable in table ROM
STUB_OFF   = 0x329988   # count=1 stub resource in program image
STUB_AUX_OFF = 0x104E   # stub aux area (8 count-in records), rel to stub base
STUB_AUX_LEN = 0x16C    # ends at +0x11BA == stub record 0
STUB_REC_OFF = 0x11BA   # stub record 0 ("  8 Beat 1   ")
STUB_REC_LEN = 0x530A   # ends at +0x64C4 == next object ("Technics Pads")
GENRE_TABLE = 0x335EE4  # prog file offset of genre table (0x48735EE4)
GENRE_COUNT_OFF = 0x336064
HDR_PTR, NT_PTR, SUB_PTR = 0x18, 0x1B, 0x1E   # u24BE pointers in the resource
AUX_ENTRIES = 8
N_LOCAL = 169           # local subtable entries (record area starts at
                        # subtable + (169+8)*3 = +0x1246, proven self-consistent)
UNREFERENCED_LOCAL = {122}

# 13-char placeholder tags per factory genre ordinal (genre table order).
GENRE_TAG = ["8&16BT", "ROCKPOP", "BALLAD", "JAZZSWG", "BALLRM", "MOVSHOW",
             "ENTRTNR", "ORGANST", "60s70s", "MODDANCE", "SOULRB", "COUNTRY",
             "MARWALTZ", "LATWORLD", "CUSTOM", "MEMORY"]

FALLBACK_NAME = "  8 Beat 1   "   # the prog-ROM default the bug displays


def u16be(b, o): return (b[o] << 8) | b[o + 1]
def u24be(b, o): return (b[o] << 16) | (b[o + 1] << 8) | b[o + 2]


def style_index(style_id):
    """Nametable index for a factory style ID (code 0x48435B40-4E)."""
    return ((style_id & 0xF00) >> 1) | (style_id & 0x7F)


def read_genres(prog):
    """Factory genre list from the byte-verified genre table."""
    n = struct.unpack_from("<H", prog, GENRE_COUNT_OFF)[0]
    genres = []
    for g in range(n):
        o = GENRE_TABLE + g * 0x18
        name = prog[o:o + 16].decode("latin1").strip()
        cnt = prog[o + 0x11]                       # u8 count at +0x11
        lst = struct.unpack_from("<I", prog, o + 0x14)[0] - 0x48400000
        ids = [struct.unpack_from("<I", prog, lst + 4 * i)[0] for i in range(cnt)]
        genres.append((name, ids))
    return genres


def build(table, prog):
    # -- validate the real inputs ---------------------------------------------
    assert table[COPY_OFF:COPY_OFF + 16] == b"Technics Rhythms", "copy magic"
    assert prog[STUB_OFF:STUB_OFF + 16] == b"Technics Rhythms", "stub magic"
    prefix = bytearray(table[COPY_OFF:COPY_OFF + COPY_PREFIX_LEN])

    hdr = u24be(prefix, HDR_PTR)
    count = u16be(prefix, hdr + 2)
    nt = u24be(prefix, NT_PTR)
    sub = u24be(prefix, SUB_PTR)
    assert (hdr, count, nt, sub) == (0x27, 0xDD, 0x33, 0x1033), \
        f"unexpected directory geometry {hdr:#x} {count:#x} {nt:#x} {sub:#x}"

    stub = prog[STUB_OFF:STUB_OFF + STUB_REC_OFF + STUB_REC_LEN]
    template = bytearray(stub[STUB_REC_OFF:STUB_REC_OFF + STUB_REC_LEN])
    assert template[:13] == b"  8 Beat 1   ", "stub record 0 name"
    aux_block = stub[STUB_AUX_OFF:STUB_AUX_OFF + STUB_AUX_LEN]

    # aux tables must agree between stub and copy (byte-real reconstruction)
    stub_aux = [u24be(stub, 0x1036 + 3 * k) for k in range(AUX_ENTRIES)]
    copy_aux = [u24be(prefix, sub + 3 * (N_LOCAL + k)) for k in range(AUX_ENTRIES)]
    assert [a - stub_aux[0] for a in stub_aux] == [a - copy_aux[0] for a in copy_aux], \
        "aux record layout mismatch between stub and copy"
    assert prefix[copy_aux[0]:copy_aux[0] + 2] == aux_block[:2], \
        "surviving copy bytes disagree with stub aux[0]"

    local_offs = [u24be(prefix, sub + 3 * i) for i in range(N_LOCAL)]
    assert all(a < b for a, b in zip(local_offs, local_offs[1:])), "subtable not monotonic"
    assert copy_aux[0] == sub + 3 * (N_LOCAL + AUX_ENTRIES), "record area start"

    # -- map local record index -> (genre, slot) via the REAL nametable -------
    genres = read_genres(prog)
    rec_owner = {}
    for gi, (gname, ids) in enumerate(genres):
        for slot, sid in enumerate(ids):
            if sid & 0x300000:
                continue                        # CUSTOM/MEMORY: not in this resource
            e = u16be(prefix, nt + 2 * style_index(sid))
            if (e & 0xC000) == 0x8000:          # one alias indirection
                e = u16be(prefix, nt + 2 * (e & 0x7FF))
            if e < count:                       # plain -> local record e
                assert e not in rec_owner, f"record {e} claimed twice"
                rec_owner[e] = (gi, slot)

    assert len(rec_owner) == N_LOCAL - len(UNREFERENCED_LOCAL), \
        f"expected {N_LOCAL - len(UNREFERENCED_LOCAL)} owned local records, got {len(rec_owner)}"

    def rec_name(i):
        if i in rec_owner:
            gi, slot = rec_owner[i]
            nm = f"{GENRE_TAG[gi]} {slot + 1:02d} ?"
        else:
            nm = f"NO REF {i} ?"
        assert len(nm) <= 13
        return nm.ljust(13).encode("latin1")

    # -- assemble -------------------------------------------------------------
    size = local_offs[-1] + STUB_REC_LEN
    img = bytearray(b"\xFF" * size)             # erased-flash fill
    img[:COPY_PREFIX_LEN] = prefix
    img[copy_aux[0]:copy_aux[0] + STUB_AUX_LEN] = aux_block   # real aux records

    truncated = []
    for i, off in enumerate(local_offs):
        budget = (local_offs[i + 1] - off) if i + 1 < N_LOCAL else STUB_REC_LEN
        n = min(budget, STUB_REC_LEN)
        if n < STUB_REC_LEN:
            truncated.append((i, budget))
        img[off:off + n] = template[:n]
        img[off:off + 13] = rec_name(i)

    return img, rec_owner, truncated, genres, (nt, sub, count)


# ---- self-verification: simulate resolver 0x48433AC4 ------------------------
def resolve(img, table, geo, style_id):
    """Mirror the firmware resolver against the synthetic image.
    Secondary (0x4000-class) entries resolve via the REAL table ROM, exactly
    as the firmware does (this container only holds the entry values)."""
    nt, sub, count = geo
    e = u16be(img, nt + 2 * style_index(style_id))
    hop = 0
    while (e & 0xC000) == 0x8000 and hop == 0:  # one indirection max
        e = u16be(img, nt + 2 * (e & 0x7FF))
        hop += 1
    if e < count:
        off = u24be(img, sub + 3 * e)
        return img[off:off + 13].decode("latin1"), "local"
    if (e & 0xC000) == 0x4000:
        i2 = e & 0x7FF
        off = SEC_OFF + u24be(table, SEC_OFF + 3 * i2)
        return table[off:off + 13].decode("latin1"), "secondary(real)"
    return None, "unresolved"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--table", default="/home/fsanches/compartilhado/kn7000-emulator/roms/kn7000/kn7000_table.rom")
    ap.add_argument("--prog", default="/home/fsanches/compartilhado/kn7000_scratchpad_snapshot/kn7000_program_decompressed.bin")
    ap.add_argument("--out", default="technics_rhythms_synth.bin")
    ap.add_argument("--verify", action="store_true", help="simulate the firmware resolver over all factory IDs")
    args = ap.parse_args()

    table = open(args.table, "rb").read()
    prog = open(args.prog, "rb").read()

    img, rec_owner, truncated, genres, geo = build(table, prog)
    with open(args.out, "wb") as f:
        f.write(img)
    print(f"wrote {args.out}: {len(img)} bytes ({len(img)/1048576:.2f} MiB)")
    print(f"  local records: {len(rec_owner)} genre-owned + {len(UNREFERENCED_LOCAL)} unreferenced;"
          f" {len(truncated)} payloads truncated to their real slot size (names unaffected)")

    if not args.verify:
        return

    real = fallback = placeholder = 0
    print("\n== resolver simulation (0x48433AC4 semantics) ==")
    for gname, ids in genres:
        col = []
        for sid in ids:
            if sid & 0x300000:
                col.append((sid, "(CUSTOM/MEMORY: RAM path, out of scope)", ""))
                continue
            nm, src = resolve(img, table, geo, sid)
            if nm is None or nm == FALLBACK_NAME:
                fallback += 1
            elif src == "secondary(real)":
                real += 1
            else:
                placeholder += 1
            col.append((sid, nm, src))
        show = gname in ("8&16 BEAT", "BALLAD", "JAZZ & SWING",
                         "COUNTRY&WESTERN", "MARCH & WALTZ", "LATIN & WORLD")
        if show:
            print(f"\n-- {gname} --")
            for sid, nm, src in col:
                print(f"  0x{sid:06X}  {nm!r:20s} {src}")
    n_names = sum(1 for _, ids in genres for sid in ids if not (sid & 0x300000))
    print(f"\ntotals over {n_names} factory IDs: {real} REAL names (secondary catalog), "
          f"{placeholder} marked placeholders, {fallback} '8 Beat 1' fallbacks")
    dis = set()
    for gname, ids in genres:
        for sid in ids:
            if not (sid & 0x300000):
                dis.add(resolve(img, table, geo, sid)[0])
    print(f"distinct resolved names: {len(dis)} (fallback bug requires them all equal)")


if __name__ == "__main__":
    sys.exit(main())

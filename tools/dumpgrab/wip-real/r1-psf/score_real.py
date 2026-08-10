#!/usr/bin/env python3
"""Score a decoded page against the two independent references that exist for
this frame, and -- separately -- identify which page of which ROM it is.

Two references, per the package brief:
  (i)  the PHOTO TRANSCRIPTION of the same page read off a phone photo of the
       same instrument (build 893 / table build 80);
  (ii) our archived TABLE image (build 84), which agrees with (i) on 246 of 256
       bytes, all ten disagreements confined to the last row.

Both numbers are reported.  A decode that also matches the transcription on the
last row is strictly better evidence than one that matches our ROM everywhere,
because the last row is where the two builds genuinely differ.

`--identify` additionally scans both ROM images for the best-matching aligned
256-byte page.  That is a sanity check on the base address the decoder read off
the screen, not a substitute for it.
"""
from __future__ import annotations

import argparse
import json
import sys

import numpy as np

TABLE_ROM = "/home/fsanches/compartilhado/kn7000-emulator/roms/kn7000/kn7000_table.rom"
PROGRAM_ROM = "/home/fsanches/compartilhado/kn7000-emulator/roms/kn7000/kn7000_program.rom"
TRANSCRIPTION = ("/home/fsanches/compartilhado/kn7000_disassembly/dumps/"
                 "build893-photo-transcription/screens.json")


def load_transcription(base):
    for e in json.load(open(TRANSCRIPTION)):
        if e["base_address"].upper() == base.upper():
            return bytes(int(b, 16) for row in e["rows"] for b in row["bytes"]), e
    return None, None


def rom_page(path, cpu_base, addr):
    import os
    off = addr - cpu_base
    if off < 0 or off + 256 > os.path.getsize(path):
        return None
    with open(path, "rb") as f:
        f.seek(off)
        return f.read(256)


def compare(name, got, want):
    if want is None:
        print("  %-28s (not available)" % name)
        return None
    bad = [i for i in range(256) if got[i] != want[i]]
    print("  %-28s %3d/256 exact  = %8.4f %%   wrong: %s"
          % (name, 256 - len(bad), 100.0 * (256 - len(bad)) / 256.0,
             ", ".join("%02X:%02X!=%02X" % (i, got[i], want[i]) for i in bad[:14])
             + (" ..." if len(bad) > 14 else "") if bad else "none"))
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fit", default="fit_real.json")
    ap.add_argument("--bytes", default=None, help="256 bytes as hex, overrides --fit")
    ap.add_argument("--base", default=None)
    ap.add_argument("--identify", action="store_true")
    args = ap.parse_args()

    if args.bytes:
        got = bytes.fromhex(args.bytes)
        base = args.base
    else:
        f = json.load(open(args.fit))
        got = bytes.fromhex(f["decoded_bytes_hex"])
        base = args.base or f["base_address"]
    print("decoded base address read off the screen: 0x%s" % base)

    tr, meta = load_transcription(base)
    rom = rom_page(TABLE_ROM, 0x48000000, int(base, 16))
    if rom is None:
        rom = rom_page(PROGRAM_ROM, 0x48400000, int(base, 16))
    print("\nSCORED AGAINST")
    b1 = compare("photo transcription (b893)", got, tr)
    b2 = compare("our table/program ROM", got, rom)
    if tr is not None and rom is not None:
        d = [i for i in range(256) if tr[i] != rom[i]]
        print("  (the two references themselves disagree on %d bytes: %s)"
              % (len(d), " ".join("%02X" % i for i in d)))
        if b1 is not None:
            last = [i for i in b1 if i >= 0xF0]
            print("  decode vs transcription, LAST ROW only: %d/16 exact" % (16 - len(last)))

    if args.identify:
        print("\nIDENTIFY: best-matching aligned 256-byte page in each ROM image")
        for nm, path, cpub in (("table", TABLE_ROM, 0x48000000),
                               ("program", PROGRAM_ROM, 0x48400000)):
            data = np.frombuffer(open(path, "rb").read(), dtype=np.uint8)
            n = (len(data) // 256) * 256
            pages = data[:n].reshape(-1, 256)
            g = np.frombuffer(got, dtype=np.uint8)[None, :]
            same = (pages == g).sum(axis=1)
            k = int(np.argmax(same))
            print("  %-8s best page 0x%08X  %3d/256 bytes equal"
                  % (nm, cpub + 256 * k, same[k]))
            order = np.argsort(-same)[:5]
            print("           runners-up: %s"
                  % "  ".join("0x%08X:%d" % (cpub + 256 * int(i), same[i]) for i in order[1:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""avsdrv_unpack.py — helpers for NEC's AVSDRV.SYS (uPD6380 DOS driver).

Two jobs:

  expand <in.SY_> <out.SYS>
      Expand a Microsoft SZDD ("compress.exe") file.  Every `*.SY_` inside NEC's
      MS-DOS 6.2 update module UPDOS62.EXE is SZDD-packed.

  scan <file> [...]
      Report the evidence that a binary really is the uPD6380 driver: the
      occurrences of the I/O port constants A462h (control) and A464h (data),
      with the surrounding bytes, plus the DOS device header and the INT 0D9h
      vector installation (`B8 D9 25` = MOV AX,25D9h ; INT 21h).

Provenance of the input: NEC's own legacy download server,
  http://search.casnavi.nec.co.jp/download/pc/module/dos/dos6/updos62/UPDOS62.EXE
(host now NXDOMAIN; retrieved through the Wayback Machine, snapshot 20040123195142).
See notes/kn5000-dsp-avsdrv.md.
"""
import re
import sys


def szdd_expand(d: bytes) -> bytes:
    """Microsoft SZDD / "compress" format, mode 'A' (LZ77, 4 KiB window)."""
    if d[:8] != b"SZDD\x88\xf0\x27\x33":
        raise ValueError("not an SZDD file")
    outlen = int.from_bytes(d[10:14], "little")
    win = bytearray(b"\x20" * 4096)
    wp = 4096 - 16
    out = bytearray()
    i = 14
    while i < len(d) and len(out) < outlen:
        ctl = d[i]
        i += 1
        for bit in range(8):
            if i >= len(d) or len(out) >= outlen:
                break
            if ctl >> bit & 1:
                c = d[i]
                i += 1
                out.append(c)
                win[wp] = c
                wp = (wp + 1) & 0xFFF
            else:
                if i + 1 >= len(d):
                    break
                lo, hi = d[i], d[i + 1]
                i += 2
                pos = lo | ((hi & 0xF0) << 4)
                for k in range((hi & 0x0F) + 3):
                    c = win[(pos + k) & 0xFFF]
                    out.append(c)
                    win[wp] = c
                    wp = (wp + 1) & 0xFFF
    return bytes(out[:outlen])


PORTS = {
    0xA460: "PC-9801-73/98GS sound base",
    0xA462: "uPD6380 control (b7 cmd/data, b6 read, b5 reset / I-RAM modify)",
    0xA464: "uPD6380 data port",
    0xA466: "sound board",
    0xA468: "sound board",
}


def scan(path: str) -> None:
    d = open(path, "rb").read()
    print(f"== {path}  {len(d)} bytes")
    if d[:2] == b"MZ":
        hdr_para = int.from_bytes(d[8:10], "little")
        print(f"   MZ, header {hdr_para * 16:#x}, image starts at {hdr_para * 16:#x}")
        h = hdr_para * 16
        if d[h:h + 4] == b"\xff\xff\xff\xff":
            attr = int.from_bytes(d[h + 4:h + 6], "little")
            name = d[h + 10:h + 18].decode("ascii", "replace")
            print(f"   DOS device driver header: attr={attr:#06x} "
                  f"strategy={int.from_bytes(d[h+6:h+8],'little'):#06x} "
                  f"interrupt={int.from_bytes(d[h+8:h+10],'little'):#06x} "
                  f"name={name!r}")
    for pat, what in ((b"\xb8\xd9\x25", "MOV AX,25D9h  (INT 21h/AH=25h: install INT 0D9h)"),
                      (b"\xcd\xd9", "INT 0D9h")):
        hits = [m.start() for m in re.finditer(re.escape(pat), d)]
        if hits:
            print(f"   {what}: {len(hits)} at {[hex(x) for x in hits]}")
    for port, what in PORTS.items():
        b = port.to_bytes(2, "little")
        for m in re.finditer(re.escape(b), d):
            o = m.start()
            pre = d[o - 1:o]
            ctx = d[o - 1:o + 6].hex(" ")
            tag = "MOV DX,imm16" if pre == b"\xba" else ""
            print(f"   {port:04X}h @ {o:#07x}  {ctx}   {tag}   [{what}]")


def main() -> int:
    if len(sys.argv) < 3 or sys.argv[1] not in ("expand", "scan"):
        print(__doc__)
        return 2
    if sys.argv[1] == "expand":
        out = szdd_expand(open(sys.argv[2], "rb").read())
        open(sys.argv[3], "wb").write(out)
        print(f"{sys.argv[3]}: {len(out)} bytes")
    else:
        for p in sys.argv[2:]:
            scan(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())

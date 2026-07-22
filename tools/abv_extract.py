#!/usr/bin/env python3
"""abv_extract.py -- extract text from ASCII Book Viewer 2.0 (.ABV) electronic books.

Discovered while hunting NEC uPD6380/uPD6383 documentation for the KN5000 effects
DSP (see notes/kn5000-dsp-abv.md).

Container facts (verified on MM.ABV / HW.ABV / BI.ABV of the NEC "PC-9800 series
Technical Data Book" CD-ROMs):

  * The body text is *not* compressed.  It is Shift-JIS with every byte
    complemented (b ^ 0xFF).  That is the only obfuscation in the format.
  * Header (little-endian, byte-granular, NOT 2-aligned):
      +0x00  u16 0x0032          format/record id
      +0x02  u16 0x0001          version
      +0x04  u32 file_length     real payload size (ISO dir entry lies: 200,000,000)
      +0x08  u32 ...             page/record counts
      +0x14  u32 off_A           section (index-ish) start
      +0x18  u32 off_TEXT        start of the linear text pool  <-- what we want
      +0x1c  u32 off_B
      +0x20  u32 count
      +0x24  Shift-JIS title (PLAIN, not complemented), NUL padded
      +0x65  u32 off_TEXT (repeated)
      +0x69  u32 n_entries
      +0x6d  u32[n_entries] page offset table (page record start offsets)
  * The text pool runs from off_TEXT to file_length and is one long complemented
    Shift-JIS stream; '$' introduces a command/section anchor name.
  * Page records interleave layout opcodes with (kind,u16 len,bytes) text runs
    whose payload is likewise complemented Shift-JIS.
  * Figures and *all tables* are stored as ordinary, uncompressed Windows
    BITMAPFILEHEADER+BITMAPINFOHEADER .BMP blobs embedded verbatim in the file,
    immediately preceded by a NUL-terminated PLAIN Shift-JIS "name.bmp" and a
    PLAIN Shift-JIS caption.  They can be carved out byte-for-byte.

Usage:
  abv_extract.py iso <file.iso>                    list ISO9660 root directory
  abv_extract.py info <file.abv|iso> [lba]         dump header
  abv_extract.py text <file.abv|iso> [lba] -o out  dump the text pool as UTF-8
  abv_extract.py bmp  <file.abv|iso> [lba] -o dir  carve every embedded BMP
                                                   (writes dir/index.txt captions)
"""
import struct
import sys

SECTOR = 2048


def iso_root(path):
    """Yield (name, lba, length) of the ISO9660 root directory (no mount needed)."""
    with open(path, "rb") as f:
        f.seek(16 * SECTOR)
        pvd = f.read(SECTOR)
        assert pvd[1:6] == b"CD001", "not an ISO9660 image"
        root = pvd[156:190]
        lba = struct.unpack("<I", root[2:6])[0]
        ln = struct.unpack("<I", root[10:14])[0]
        f.seek(lba * SECTOR)
        d = f.read(ln)
    i = 0
    while i < len(d):
        L = d[i]
        if L == 0:
            i += 1
            continue
        r = d[i : i + L]
        nlen = r[32]
        yield (
            r[33 : 33 + nlen].decode("latin1"),
            struct.unpack("<I", r[2:6])[0],
            struct.unpack("<I", r[10:14])[0],
        )
        i += L


class Abv:
    def __init__(self, path, base=0):
        self.f = open(path, "rb")
        self.base = base
        h = self.rd(0, 0x400)
        self.length = struct.unpack("<I", h[4:8])[0]
        self.off_a = struct.unpack("<I", h[0x14:0x18])[0]
        self.off_text = struct.unpack("<I", h[0x18:0x1C])[0]
        self.off_b = struct.unpack("<I", h[0x1C:0x20])[0]
        self.title = h[0x24:0x60].split(b"\0")[0].decode("shift_jis", "replace")
        self.n_pages = struct.unpack("<I", h[0x69:0x6D])[0]
        self.pages = list(
            struct.unpack("<%dI" % min(self.n_pages, (0x400 - 0x6D) // 4), h[0x6D : 0x6D + 4 * min(self.n_pages, (0x400 - 0x6D) // 4)])
        )

    def rd(self, off, n):
        self.f.seek(self.base + off)
        return self.f.read(n)

    def text(self):
        n = self.length - self.off_text
        raw = self.rd(self.off_text, n)
        return bytes(b ^ 0xFF for b in raw).decode("shift_jis", "replace")

    def whole(self):
        return self.rd(0, self.length)

    def _bmp_offsets(self, d):
        """{offset: size} of every embedded BITMAPFILEHEADER blob."""
        out = {}
        i = 0
        while True:
            i = d.find(b"BM", i)
            if i < 0 or i > len(d) - 64:
                break
            sz = struct.unpack("<I", d[i + 2 : i + 6])[0]
            px = struct.unpack("<I", d[i + 10 : i + 14])[0]
            hsz = struct.unpack("<I", d[i + 14 : i + 18])[0]
            if hsz in (12, 40) and 0 < sz <= len(d) - i and 0 < px < sz:
                out[i] = sz
                i += sz
            else:
                i += 2
        return out

    def bitmaps(self):
        """Carve embedded BMPs.

        Each figure is described by a record holding a 30x30 icon ("tbl.bmp" /
        "fig.bmp", 598 bytes) plus the real image; the record contains a plain
        "name.bmp" string, a plain Shift-JIS caption, and a u32 file offset to
        the image data.  We resolve name -> image by looking for a u32 in the
        1 KiB before the name that equals a known BMP offset (largest wins,
        which discards the icon).

        Yields (offset, size, name, caption, blob).
        """
        import re

        d = self.whole()
        bset = self._bmp_offsets(d)
        seen = set()
        for m in re.finditer(rb"([A-Za-z0-9_]{2,12})\.bmp\x00+", d):
            name = m.group(1).decode("latin1") + ".bmp"
            if name in ("tbl.bmp", "fig.bmp") or name in seen:
                continue
            # the caption is the next plain string that is not the name again
            caption = ""
            j = m.end()
            for _ in range(4):
                e = d.find(b"\0", j)
                if e < 0 or not 0 < e - j < 200:
                    break
                s = d[j:e]
                if s != m.group(1) + b".bmp":
                    caption = s.decode("shift_jis", "replace")
                    break
                j = e
                while j < len(d) and d[j] == 0:
                    j += 1
            w = d[max(0, m.start() - 1024) : m.start() + 64]
            cands = [
                (bset[v], v)
                for k in range(len(w) - 4)
                for v in (struct.unpack("<I", w[k : k + 4])[0],)
                if v in bset
            ]
            if not cands:
                continue
            sz, off = max(cands)
            seen.add(name)
            yield off, sz, name, caption, d[off : off + sz]

    def info(self):
        return (
            "title      : %s\n"
            "length     : 0x%08x (%d)\n"
            "off_A      : 0x%08x\n"
            "off_TEXT   : 0x%08x  (%d bytes of text)\n"
            "off_B      : 0x%08x\n"
            "n_pages    : %d\n"
            "first pages: %s"
            % (
                self.title,
                self.length,
                self.length,
                self.off_a,
                self.off_text,
                self.length - self.off_text,
                self.off_b,
                self.n_pages,
                ", ".join("0x%x" % p for p in self.pages[:8]),
            )
        )


def open_target(argv):
    path = argv[0]
    base = 0
    if len(argv) > 1 and argv[1].isdigit():
        base = int(argv[1]) * SECTOR
    return Abv(path, base)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    cmd = sys.argv[1]
    if cmd == "iso":
        for name, lba, ln in iso_root(sys.argv[2]):
            print("%-16s lba=%-8d len=%d" % (name, lba, ln))
        return 0
    a = open_target(sys.argv[2:])
    if cmd == "info":
        print(a.info())
    elif cmd == "text":
        out = None
        if "-o" in sys.argv:
            out = sys.argv[sys.argv.index("-o") + 1]
        t = a.text()
        if out:
            open(out, "w", encoding="utf-8").write(t)
            print("wrote %s (%d chars)" % (out, len(t)))
        else:
            sys.stdout.write(t)
    elif cmd == "bmp":
        import os

        outdir = sys.argv[sys.argv.index("-o") + 1] if "-o" in sys.argv else "abv_bmp"
        os.makedirs(outdir, exist_ok=True)
        idx = open(os.path.join(outdir, "index.txt"), "w", encoding="utf-8")
        n = 0
        seen = {}
        for off, sz, name, caption, blob in a.bitmaps():
            base = name or "unnamed_%08x.bmp" % off
            seen[base] = seen.get(base, 0) + 1
            fn = base if seen[base] == 1 else "%s_%d.bmp" % (base[:-4], seen[base])
            open(os.path.join(outdir, fn), "wb").write(blob)
            idx.write("%s\t0x%08x\t%d\t%s\n" % (fn, off, sz, caption))
            n += 1
        idx.close()
        print("carved %d bitmaps into %s" % (n, outdir))
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Ground truth for measurement: the KN7000 flash images, addressed by CPU address.

Two windows are covered:
    0x48000000 .. 0x483FFFFF   TABLE flash   (kn7000_table.rom)
    0x48400000 .. 0x487FFFFF   PROGRAM flash (kn7000_program.rom)
Addresses past the end of a dump file read 0xFF, which is what the instrument
shows there too (see FINDINGS-kn7000-debug-screens.md section 4).

This module exists only so accuracy can be MEASURED; the extractor itself never
touches it.
"""
from __future__ import annotations

import os
from typing import Dict, Optional

DEFAULT_ROMDIR = "/home/fsanches/compartilhado/kn7000-emulator/roms/kn7000"

WINDOWS = [
    (0x48000000, 0x400000, "kn7000_table.rom"),
    (0x48400000, 0x400000, "kn7000_program.rom"),
]


class Oracle:
    def __init__(self, romdir: str = DEFAULT_ROMDIR):
        self.romdir = romdir
        self._blobs: Dict[str, bytes] = {}

    def _blob(self, name: str) -> bytes:
        if name not in self._blobs:
            with open(os.path.join(self.romdir, name), "rb") as fh:
                self._blobs[name] = fh.read()
        return self._blobs[name]

    def page(self, addr: int) -> Optional[bytes]:
        """The 256 bytes the viewer would show at `addr` (must be page aligned)."""
        for base, size, name in WINDOWS:
            if base <= addr < base + size:
                off = addr - base
                b = self._blob(name)
                out = bytearray(256)
                for i in range(256):
                    o = off + i
                    out[i] = b[o] if o < len(b) else 0xFF
                return bytes(out)
        return None

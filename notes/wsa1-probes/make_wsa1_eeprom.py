#!/usr/bin/env python3
"""Build a VALID calibration image for the SX-WSA1R's serial EEPROM.

Question it answers: is the driver's 93C46 wiring (P6.5 CS, P8.3 SK, P8.4 DI,
P8.5 DO on CPU 2) actually carrying data, end to end, into the firmware?

A blank EEPROM cannot answer that: EEPROM_LoadCalibration (prom_c 0xFC8B0B)
fails its own checksum and NoteTrim_BuildFromCalibration (0xF997FA) then zeroes
all 61 trims -- which is exactly what an EEPROM that is not wired at all would
also produce.  This image makes the two outcomes different.

Layout, every field read off 0xFC8B0B:
    word 0x00..0x1E   31 words = 62 calibration BYTES, copied to RAM 0x00E2A1
    word 0x1F         must equal the 16-bit sum of those 31 words
    word 0x20         must equal 0x5AA5
    word 0x21..0x3F   unused, left erased

The 62 bytes are filled with 0x4B + n, so that
    trim[n] = ToneGen_VelCurve_Trim51[ clamp(cal[n] - 0x4B, 0, 50) ]
            = ToneGen_VelCurve_Trim51[ min(n, 50) ]
which sweeps the whole curve, -12 .. +10, instead of landing on its five-entry
zero run.  A wired EEPROM therefore produces a trim table that is impossible to
confuse with the all-zero failure case.

Run:
    python3 make_wsa1_eeprom.py <path-to-nvram-dir>/wsa1r/eeprom
and read the result back with wsa1_eeprom_calibration.lua.

The file is a plain little-endian u16 array: eeprom_base_device stores 16-bit
cells with put_u16le (mame/src/devices/machine/eeprom.cpp:297-300).
"""
import struct
import sys

WORDS = 64

def build():
    cells = [0xFFFF] * WORDS
    for i in range(31):
        lo = (0x4B + 2 * i) & 0xFF
        hi = (0x4B + 2 * i + 1) & 0xFF
        cells[i] = (hi << 8) | lo
    cells[0x1F] = sum(cells[0:31]) & 0xFFFF
    cells[0x20] = 0x5AA5
    return b''.join(struct.pack('<H', c) for c in cells)

if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    data = build()
    assert len(data) == WORDS * 2
    with open(sys.argv[1], 'wb') as f:
        f.write(data)
    print("wrote %d bytes to %s" % (len(data), sys.argv[1]))
    print("checksum word 0x1F = 0x%04X, magic word 0x20 = 0x5AA5"
          % struct.unpack_from('<H', data, 0x1F * 2))

#!/usr/bin/env python3
"""decode_fdc_log.py -- turn a remote.lua run log's FDC/DMA tap lines into a readable command trace.

Question it answers: what did the firmware send the floppy controller, and what came back? The
taps (installed with remote.lua's `lua` command; see README.md) print one line per register
access:
  FDCW t=T [REG] VV   write (REG omitted on the KN5000: its data register 0x11000A)
  FDCR t=T [REG] VV   read of the data register (result bytes)
  FDCA t=T VV         KN5000 auxiliary command register 0x110008 (write)
  DMAW t=T REG VAL/MASK   MN10300 DMA channel 0 register write (KN6000/KN7000)
This prints them grouped into bursts (a new line after 50 ms of silence): bare hex = command and
parameter bytes, rXX = result bytes, aux:XX = auxiliary command, DSR:/CCR: = 82077 data-rate
registers, DOR:XX = 82077 DOR (printed only when its value changes) and DMA lines verbatim.
MARK lines (remote.lua `lua emu.print_error("MARK ...")`) are kept, so a trace can be cut at a
step.

usage: python3 -I decode_fdc_log.py RIG.log [--from MARKTEXT]
"""
import re
import sys

path = sys.argv[1]
start = sys.argv[sys.argv.index("--from") + 1] if "--from" in sys.argv else None
on = start is None
regtag = {"": "", "9802000A": "", "98020008": "DSR:", "9802000E": "CCR:", "98020004": "DOR:", "11000A": ""}
out, last, dor = [], 0.0, None
for line in open(path, errors="replace"):
    line = line.strip()
    if line.startswith("MARK"):
        on = on or (start is not None and start in line)
        if on:
            out.append(f"\n--- {line}")
            last = 0.0
        continue
    if not on:
        continue
    m = re.match(r"FDC([WRA]) t=([\d.]+) (?:([0-9A-F]+) )?([0-9A-F]+)(?:/([0-9A-F]+))?$", line)
    d = re.match(r"DMAW t=([\d.]+) ([0-9A-F]+) ([0-9A-F]+)/([0-9A-F]+)$", line)
    if m and m.group(5):                       # older taps: "REG VALUE/MASK", one byte lane set
        mask, value = int(m.group(5), 16), int(m.group(4), 16)
        lane = ((mask & -mask).bit_length() - 1) // 8
        reg = f"{int(m.group(3), 16) + lane:X}"
        m = (m.group(1), float(m.group(2)), reg, f"{(value >> 8 * lane) & 0xFF:02X}")
    elif m:
        m = (m.group(1), float(m.group(2)), m.group(3), m.group(4))
    if m:
        kind, t, reg, val = m
        if reg == "98020004":                  # 82077 DOR: rewritten constantly; show changes only
            if val == dor:
                continue
            dor = val
        tok = {"R": "r" + val, "A": "aux:" + val}.get(kind, regtag.get(reg or "", (reg or "") + ":") + val)
    elif d:
        t, tok = float(d.group(1)), f"\n    DMA {d.group(2)} <- {d.group(3)}"
    else:
        continue
    if t - last > 0.05:
        out.append(f"\n[{t:8.3f}]")
    out.append(tok)
    last = t
print(" ".join(out).replace(" \n", "\n"))

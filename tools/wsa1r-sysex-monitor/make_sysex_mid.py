#!/usr/bin/env python3
"""make_sysex_mid.py -- a Standard MIDI File carrying one SysEx, for feeding MAME's `midiin'.

    python3 make_sysex_mid.py OUT.mid [--at-seconds 5.0] [--bytes F0,7E,7D,01,F7]

WHY A FILE AND NOT A LIVE PORT
    `midiin_device::call_load' tries `load_image_by_path' FIRST and only falls back to the OSD
    MIDI layer if the file does not parse.  So a Standard MIDI File is a first-class input: it is
    deterministic, needs no daemon or kernel module, and replays identically every run -- which is
    what an automated regression wants.  The live ALSA port is the interactive route and is used
    for the REPLY direction (`-mdout "Midi Through Port-0"').

    ⚠ This is also why a PTY cannot feed `midiin': a raw byte stream is not a Standard MIDI File,
    and the parse happens before the port fallback.

THE DELAY MATTERS
    The firmware must have initialised its UART and SysEx parser before the message arrives, so
    the event is placed several seconds in, not at tick 0.  Tempo is left at the MIDI default
    (500000 us per quarter note = 120 bpm), so at 96 ticks per quarter one second is 192 ticks.
"""
import argparse
import struct

TICKS_PER_QUARTER = 96
US_PER_QUARTER = 500000          # the MIDI default, written explicitly below


def varlen(n):
    """MIDI variable-length quantity."""
    out = bytearray([n & 0x7F])
    n >>= 7
    while n:
        out.insert(0, 0x80 | (n & 0x7F))
        n >>= 7
    return bytes(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--at-seconds", type=float, default=5.0)
    ap.add_argument("--bytes", default="F0,7E,7D,01,F7")
    a = ap.parse_args()

    msg = bytes(int(x, 16) for x in a.bytes.split(","))
    if msg[0] != 0xF0 or msg[-1] != 0xF7:
        raise SystemExit("the message must start with F0 and end with F7")

    ticks = int(round(a.at_seconds * 1e6 / US_PER_QUARTER * TICKS_PER_QUARTER))

    trk = bytearray()
    #  an explicit tempo event, so the timing does not depend on a default
    trk += varlen(0) + bytes([0xFF, 0x51, 0x03]) + US_PER_QUARTER.to_bytes(3, "big")
    #  the SysEx: F0, then a varlen LENGTH of everything after it (terminator included)
    trk += varlen(ticks) + bytes([0xF0]) + varlen(len(msg) - 1) + msg[1:]
    #  a beat of slack, then end of track
    trk += varlen(TICKS_PER_QUARTER) + bytes([0xFF, 0x2F, 0x00])

    with open(a.out, "wb") as f:
        f.write(b"MThd" + struct.pack(">IHHH", 6, 0, 1, TICKS_PER_QUARTER))
        f.write(b"MTrk" + struct.pack(">I", len(trk)) + bytes(trk))

    print("wrote %s" % a.out)
    print("  message : %s" % " ".join("%02X" % b for b in msg))
    print("  at      : %.2f s  (%d ticks at %d tpqn, %d us/quarter)"
          % (a.at_seconds, ticks, TICKS_PER_QUARTER, US_PER_QUARTER))


if __name__ == "__main__":
    main()

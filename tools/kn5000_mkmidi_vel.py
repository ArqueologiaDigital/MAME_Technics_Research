#!/usr/bin/env python3
"""Generate a Standard MIDI File of HELD NOTES AT CHOSEN VELOCITIES.

Why this exists. Every held-note measurement in this project so far has driven the key bed
through the driver's ioports, which hard-code `KEYBED_VELOCITY = 100` (kn5000.cpp). Felipe
plays a real controller into `-midiin2`, i.e. the same `push_keybed_event()` path but with
whatever velocity his fingers produce. Velocity is therefore THE uncontrolled variable
between his reports and the rig's results, and it is not obviously innocent: it reaches the
TVF cutoff and register +0x080, both of which affect how loud a voice is and therefore
whether it crosses the silence interlock that makes the firmware deallocate the channel.

MAME's `midiin` device accepts a .mid image (`-listmedia` shows `.mid .syx` for midiin2),
so feeding it a file is a complete substitute for a hardware controller and is repeatable,
which a hardware controller is not.

The file holds ONE note at a time, each for `--hold` seconds with `--gap` between, cycling
through the velocity list. Notes go on MIDI channel 1 as plain note-on/note-off, no program
change: the patch is selected from the PANEL by kn5000_patch_probe.lua, exactly as Felipe
selects it, so this file must not disturb it.

usage: kn5000_mkmidi_vel.py out.mid --note 60 --vels 20,40,64,100,127 --delay 20 --hold 6 --gap 2
"""
import argparse
import struct


def vlq(n):
    b = [n & 0x7F]
    n >>= 7
    while n:
        b.insert(0, (n & 0x7F) | 0x80)
        n >>= 7
    return bytes(b)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--note", type=int, default=60)
    ap.add_argument("--vels", default="20,40,64,100,127")
    ap.add_argument("--delay", type=float, default=20.0, help="seconds before the first note")
    ap.add_argument("--hold", type=float, default=6.0)
    ap.add_argument("--gap", type=float, default=2.0)
    a = ap.parse_args()

    tpqn, tps = 480, 960          # 480 ticks/quarter at 120 BPM => 960 ticks/second
    vels = [int(v) for v in a.vels.split(",")]

    ev = bytearray()
    ev += vlq(0) + bytes([0xFF, 0x51, 0x03, 0x07, 0xA1, 0x20])   # 500000 us/quarter
    first = True
    marks = []
    t = a.delay
    for v in vels:
        ev += vlq(int((a.delay if first else a.gap) * tps)) + bytes([0x90, a.note & 0x7F, v & 0x7F])
        ev += vlq(int(a.hold * tps)) + bytes([0x80, a.note & 0x7F, 0])
        marks.append((v, t, t + a.hold))
        t += a.hold + a.gap
        first = False
    ev += vlq(0) + bytes([0xFF, 0x2F, 0x00])

    trk = b"MTrk" + struct.pack(">I", len(ev)) + bytes(ev)
    hdr = b"MThd" + struct.pack(">IHHH", 6, 0, 1, tpqn)
    with open(a.out, "wb") as f:
        f.write(hdr + trk)

    # a marks file in the same format the analysers read, so the WAV can be cut per velocity
    with open(a.out + ".marks", "w") as f:
        f.write("# patch midi t_on t_off\n")
        for v, t0, t1 in marks:
            f.write("vel%d %d %.6f %.6f\n" % (v, -1, t0, t1))
    print("wrote %s: note %d, velocities %s, %.1f s holds" % (a.out, a.note, vels, a.hold))
    print("  NOTE: the .marks times are MIDI-FILE times; the emulated note-on is what the")
    print("  KN5000_NOTELOG records, and that is what the analysis should key on.")


if __name__ == "__main__":
    main()

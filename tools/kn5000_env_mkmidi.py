#!/usr/bin/env python3
# Generate a minimal Standard MIDI File: optional Program Change, then a held
# note-on/off, with a long initial delay so the note lands after boot.
import struct, sys

def vlq(n):
    b = [n & 0x7f]; n >>= 7
    while n: b.insert(0, (n & 0x7f) | 0x80); n >>= 7
    return bytes(b)

def main():
    out = sys.argv[1]
    program = int(sys.argv[2])       # GM program 0-127
    note    = int(sys.argv[3])       # MIDI note
    # division 480 tpqn, tempo 120 BPM (500000 us/q) => 480 ticks = 0.5 s => 960 t/s
    tpqn = 480
    tps  = 960
    delay_s   = float(sys.argv[4])   # seconds before note-on
    hold_s    = float(sys.argv[5])   # note hold seconds
    ev = bytearray()
    # tempo meta (500000 us/q)
    ev += vlq(0) + bytes([0xFF,0x51,0x03,0x07,0xA1,0x20])
    # program change (ch0) at t=0
    ev += vlq(0) + bytes([0xC0, program & 0x7f])
    # note on after delay
    ev += vlq(int(delay_s*tps)) + bytes([0x90, note & 0x7f, 100])
    # note off after hold
    ev += vlq(int(hold_s*tps)) + bytes([0x80, note & 0x7f, 0])
    # end of track
    ev += vlq(0) + bytes([0xFF,0x2F,0x00])
    trk = b'MTrk' + struct.pack('>I', len(ev)) + bytes(ev)
    hdr = b'MThd' + struct.pack('>IHHH', 6, 0, 1, tpqn)
    with open(out,'wb') as f:
        f.write(hdr+trk)
    print("wrote", out, "prog", program, "note", note, "delay", delay_s, "hold", hold_s)

main()

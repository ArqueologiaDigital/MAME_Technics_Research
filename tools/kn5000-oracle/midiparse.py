#!/usr/bin/env python3
"""Minimal Standard MIDI File reader (no external deps).

Returns notes as (start_tick, end_tick, pitch, velocity, track_index) plus
the file's ticks-per-quarter and any tempo events found.
"""
import struct
import sys


def _vlq(buf, i):
    n = 0
    while True:
        b = buf[i]
        i += 1
        n = (n << 7) | (b & 0x7F)
        if not (b & 0x80):
            return n, i


def read_smf(path):
    data = open(path, 'rb').read()
    assert data[:4] == b'MThd', 'not an SMF'
    hlen = struct.unpack_from('>I', data, 4)[0]
    fmt, ntrk, div = struct.unpack_from('>HHH', data, 8)
    pos = 8 + hlen
    tracks = []
    tempos = []          # (tick, us_per_beat)
    names = []
    markers = []
    ti = 0
    while pos < len(data):
        if data[pos:pos + 4] != b'MTrk':
            break
        blen = struct.unpack_from('>I', data, pos + 4)[0]
        body = data[pos + 8: pos + 8 + blen]
        pos += 8 + blen
        tick = 0
        running = None
        i = 0
        on = {}          # (chan,pitch) -> (tick, vel)
        notes = []
        tname = None
        while i < len(body):
            d, i = _vlq(body, i)
            tick += d
            if i >= len(body):
                break
            b = body[i]
            if b & 0x80:
                status = b
                i += 1
                if status < 0xF0:
                    running = status
            else:
                status = running
                if status is None:
                    i += 1
                    continue
            if status == 0xFF:
                mtype = body[i]
                i += 1
                ln, i = _vlq(body, i)
                payload = body[i:i + ln]
                i += ln
                if mtype == 0x51 and ln == 3:
                    tempos.append((tick, (payload[0] << 16) | (payload[1] << 8) | payload[2]))
                elif mtype == 0x03:
                    tname = payload.decode('ascii', 'replace')
                elif mtype == 0x06:
                    markers.append((ti, tick, payload.decode('ascii', 'replace')))
                elif mtype == 0x2F:
                    break
            elif status in (0xF0, 0xF7):
                ln, i = _vlq(body, i)
                i += ln
            else:
                hi = status & 0xF0
                chan = status & 0x0F
                if hi in (0xC0, 0xD0):
                    i += 1
                else:
                    p1 = body[i]
                    p2 = body[i + 1]
                    i += 2
                    if hi == 0x90 and p2 > 0:
                        on[(chan, p1)] = (tick, p2)
                    elif hi == 0x80 or (hi == 0x90 and p2 == 0):
                        k = (chan, p1)
                        if k in on:
                            st, v = on.pop(k)
                            notes.append((st, tick, p1, v, ti, chan))
        for (chan, p1), (st, v) in on.items():
            notes.append((st, st + 1, p1, v, ti, chan))
        tracks.append({'index': ti, 'name': tname, 'notes': sorted(notes)})
        ti += 1
    return {'format': fmt, 'ntrk': ntrk, 'division': div,
            'tracks': tracks, 'tempos': tempos, 'markers': markers}


if __name__ == '__main__':
    m = read_smf(sys.argv[1])
    print('format', m['format'], 'ntrk-header', m['ntrk'], 'read', len(m['tracks']),
          'division', m['division'])
    print('tempos', m['tempos'][:5])
    allnotes = []
    for t in m['tracks']:
        n = t['notes']
        allnotes += n
        if n:
            print(f"  trk {t['index']:2d} name={t['name']!r:34s} notes={len(n):5d} "
                  f"pitch {min(x[2] for x in n):3d}-{max(x[2] for x in n):3d} "
                  f"chan {sorted(set(x[5] for x in n))} "
                  f"lastbeat {max(x[1] for x in n)/m['division']:.1f}")
        else:
            print(f"  trk {t['index']:2d} name={t['name']!r:34s} notes=0")
    print('TOTAL notes', len(allnotes))
    print('pitch range', min(x[2] for x in allnotes), max(x[2] for x in allnotes))
    print('velocity range', min(x[3] for x in allnotes), max(x[3] for x in allnotes))
    print('length beats', max(x[1] for x in allnotes) / m['division'])
    print('markers', len(m['markers']))
    for mk in m['markers'][:20]:
        print('   ', mk)

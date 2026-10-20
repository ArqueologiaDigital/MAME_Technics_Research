#!/usr/bin/env python3
"""wavedir.py -- read the KN7000 wave ROMs the way the tone generator does (G13).

Library for the other scripts in this folder; `python3 wavedir.py` prints a census.
Nothing here is ROM data: every table is computed from the ROM files at run time.

The model (evidence: README.md in this folder):

  * Each tone generator owns one ROM pair. 0x98050000 (the firmware's MAIN TG) reads
    IC203 (Y) + IC204 (X); 0x98040000 (SUB TG) reads IC207 (Y) + IC208 (X). The pair is
    one stream of 16-bit words, Y word i then X word i: stream word 2i = Y[i], 2i+1 = X[i].
  * The stream is 16 pages of 0x100000 words. Each page starts with its own directory:
        word 4j+0 A  record pointer (words from the page start); A of entry 0 = 4*N
        word 4j+1 P  0x1000 | E<<4 | F<<3 | K   (E pitch exponent, F 8-bit flag,
                                                 K loop granule: L = 2**(K+4) samples)
        word 4j+2 B  sample start, in units of 16 words from the page start
        word 4j+3 Q  first parameter word (a copy of the record's second word)
    The record at A is B again, then parameter words [flags:2][code:6][value:8].
  * Value >= 0x80 is a segment of (256 - value) * L samples. Flag 0x40 after a segment:
    the loop starts at its end; flag 0x80: the loop ends at its end. Without an explicit
    end, the loop is the one granule L after the last segment. Values < 0x80 (descending
    multiples of 8) are not segments; the record ends at the word with both flags set.
  * F = 1: two 8-bit samples per word, low byte first, and each segment's code (a, b)
    scales it by 2**(-b/2) (fitted, see code8fit.py; a is unused here); samples after the
    last segment (a one-granule loop) keep the last segment's gain.
  * Sample select (the 20-bit value the firmware writes to plane 0x1C): bits 19:12 =
    page (0x00-0x0F internal; 0x20 and up are the expansion board), bits 11:0 = entry.
  * Pitch: output rate (source samples per 44.1 kHz output sample)
        rate = 2 ** ((p18 - 0x1E200) / 0x3000 + E - 9) * C7 / 44100
    i.e. a waveform with period 2**(E-9) samples sounds at the MIDI note that p18 encodes
    (0x1E200 = note 96, 0x400 per semitone).
"""
import os
import numpy as np

ROMDIR = os.environ.get('KN7000_ROMS', os.path.expanduser('~/compartilhado/kn7000-emulator/roms/kn7000'))
PAIRS = {  # driver tg index -> (Y file, X file); 0 = 0x98040000 (SUB TG), 1 = 0x98050000 (MAIN TG)
    0: ('c3cbqd000004.ic207', 'c3cbqd000003.ic208'),
    1: ('c3cbqd000002.ic203', 'c3cbqd000001.ic204'),
}
PAIR_NAME = {0: 'sub (IC207/IC208)', 1: 'main (IC203/IC204)'}
PAGE = 0x100000          # words per page
C7 = 440.0 * 2 ** (27 / 12)

_streams = {}


def stream(tg):
    """the pair as one array of uint16 words, Y[i] at 2i and X[i] at 2i+1"""
    if tg not in _streams:
        y = np.fromfile(os.path.join(ROMDIR, PAIRS[tg][0]), dtype='<u2')
        x = np.fromfile(os.path.join(ROMDIR, PAIRS[tg][1]), dtype='<u2')
        s = np.empty(y.size * 2, dtype='<u2')
        s[0::2] = y
        s[1::2] = x
        _streams[tg] = s
    return _streams[tg]


def granule(P):
    return 1 << ((P & 7) + 4)


def page_directory(s, page):
    base = page * PAGE
    n = int(s[base]) // 4
    ents = []
    for j in range(n):
        A, P, B, Q = (int(v) for v in s[base + 4 * j: base + 4 * j + 4])
        ents.append(dict(page=page, entry=j, A=A, P=P, B=B, Q=Q))
    # a sample's region runs to the next distinct start in the page
    starts = sorted(set(e['B'] for e in ents))
    nxt = {b: (starts[i + 1] if i + 1 < len(starts) else None) for i, b in enumerate(starts)}
    for e in ents:
        e['end'] = nxt[e['B']]
        e['E'] = (e['P'] >> 4) & 0xFF
        e['is8'] = bool(e['P'] & 8)
        e['L'] = granule(e['P'])
    return ents


def record(s, e, limit=1024):
    """parameter words of e's record (the B copy dropped), up to the word with both flags"""
    base = e['page'] * PAGE + e['A']
    out = []
    for k in range(1, limit):
        v = int(s[base + k])
        out.append(v)
        if (v >> 14) == 3:
            break
    return out


def parse_record(params, L):
    """-> dict(ls, le, segs=[(start, end, a, b)]) in samples from the sample start"""
    pos = 0
    ls = None
    le = None
    segs = []
    for v in params:
        flags = v >> 14
        code = (v >> 8) & 0x3F
        val = v & 0xFF
        if val >= 0x80:
            n = (256 - val) * L
            segs.append((pos, pos + n, code >> 3, code & 7))
            pos += n
            if flags & 1 and ls is None:
                ls = pos
            if flags & 2:
                le = pos
                break
        if flags == 3:
            break
    if ls is None:
        ls = pos
    if le is None:
        le = ls + L
    return dict(ls=ls, le=le, segs=segs)


def samples(s, e, n=None):
    """decoded samples (float, 16-bit scale) from the start to the region end (or n)"""
    base = e['page'] * PAGE + e['B'] * 16
    end = e['page'] * PAGE + e['end'] * 16 if e['end'] is not None else (e['page'] + 1) * PAGE
    w = s[base:end]
    if not e['is8']:
        x = w.view('<i2').astype(np.float64)
    else:
        x = w.view(np.int8).astype(np.float64) * 256.0
        r = parse_record(record(s, e), e['L'])
        g = 1.0
        for a0, a1, ca, cb in r['segs']:
            g = 2.0 ** (-cb / 2.0)
            x[a0:a1] *= g
        if r['segs']:
            x[r['segs'][-1][1]:] *= g      # past the segments (the loop granule): the last gain
    return x if n is None else x[:n]


def entries(tg):
    s = stream(tg)
    out = {}
    for p in range(16):
        for e in page_directory(s, p):
            out[(p, e['entry'])] = e
    return out


def select(tg, aux20):
    """the directory entry a voice plays: aux20 = (plane 0x1C index << 16) | data"""
    page = (aux20 >> 12) & 0xFF
    if page >= 16:
        return None
    return entries_cache(tg).get((page, aux20 & 0xFFF))


_ents = {}


def entries_cache(tg):
    if tg not in _ents:
        _ents[tg] = entries(tg)
    return _ents[tg]


def rate(p18, E):
    return 2.0 ** ((p18 - 0x1E200) / 0x3000 + E - 9) * C7 / 44100.0


if __name__ == '__main__':
    from collections import Counter
    for tg in (1, 0):
        s = stream(tg)
        sizes = [len(page_directory(s, p)) for p in range(16)]
        print('%s: entries per page %s, total %d' % (PAIR_NAME[tg], sizes, sum(sizes)))
        fmt = Counter()
        for (p, j), e in entries_cache(tg).items():
            fmt['8-bit' if e['is8'] else '16-bit'] += 1
        print('   formats', dict(fmt))

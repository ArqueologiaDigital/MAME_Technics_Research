#!/usr/bin/env python3
"""Generate src/mame/matsushita/kn5000_pitch_trim.hxx from the firmware-derived
per-selector log-pitch constant table.

SOURCE OF TRUTH is notes/data/kn5000-pitch-trim-table.tsv, which is itself emitted by
    python3 tools/kn5000_pitch_audit.py --emit-table
straight out of the firmware's 487 multisample SET descriptors (see that tool's header
for the derivation, and notes/FINDINGS-kn5000-chunk-root-pitch.md for the measurement).

    C(zone) = (SET.basepitch - ((SET.root << 8) + 0x80)) + trim(zone)
    +0x400  = (key << 8) + 0x80 + C                       (with no transposes)
    selector (+0x040) = (class << 12) | entry             -- identical to regs[1]

This script does NOT re-derive anything: it transcribes the tsv's C_modal column verbatim,
so the device and the offline analysis tools (tools/kn5000-rootpitch/decode.py, parts.py)
use bit-identical constants and their predictions remain comparable.

Usage:  python3 tools/gen_kn5000_pitch_trim.py [--check]
        --check exits 1 if the committed .hxx differs from what the tsv implies.

Stdlib only.  Run from anywhere; paths are resolved against this file.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
TSV = os.path.join(REPO, 'notes/data/kn5000-pitch-trim-table.tsv')
OUT = os.path.join(REPO, 'src/mame/matsushita/kn5000_pitch_trim.hxx')

# int16_t is the storage type; assert the measured range fits so a future regeneration
# cannot silently truncate.
C_MIN, C_MAX = -32768, 32767


def read_tsv():
    rows = [l.rstrip('\n').split('\t') for l in open(TSV)]
    hdr, rows = rows[0], rows[1:]
    ix = {k: i for i, k in enumerate(hdr)}
    out = []
    for r in rows:
        if not r or not r[0] or r[0].startswith('#'):
            continue
        sel = int(r[ix['sel']], 16)
        c = int(r[ix['C_modal']])
        nd = int(r[ix['n_distinct']])
        kw = int(r[ix['key_weight']])
        if not (C_MIN <= c <= C_MAX):
            sys.exit("C out of int16_t range for selector %04X: %d" % (sel, c))
        if sel > 0xFFFF:
            sys.exit("selector out of range: %X" % sel)
        out.append((sel, c, nd, kw))
    out.sort()
    for a, b in zip(out, out[1:]):
        if a[0] == b[0]:
            sys.exit("duplicate selector %04X in %s" % (a[0], TSV))
    return out


def emit(rows):
    n = len(rows)
    n_single = sum(1 for r in rows if r[2] == 1)
    n_amb = n - n_single
    kw = sum(r[3] for r in rows)
    kw_amb = sum(r[3] for r in rows if r[2] > 1)
    L = []
    A = L.append
    A('// license:BSD-3-Clause')
    A('// copyright-holders:Felipe Correa da Silva Sanches')
    A('// ============================================================================')
    A('// GENERATED FILE -- DO NOT EDIT BY HAND.')
    A('//   regenerate: python3 tools/gen_kn5000_pitch_trim.py')
    A('//   source:     notes/data/kn5000-pitch-trim-table.tsv')
    A('//               (itself: python3 tools/kn5000_pitch_audit.py --emit-table)')
    A('// ============================================================================')
    A('//')
    A('// KN5000 IC303 -- the PER-SELECTOR ABSOLUTE-PITCH CONSTANT C.')
    A('//')
    A('// The sub-CPU ships the voice an absolute log pitch in +0x400 (regs[8]) at 0x100')
    A('// units per semitone, offset by a constant that belongs to the SELECTED RECORDING:')
    A('//')
    A('//     +0x400 = (note << 8) + 0x80 + C(+0x040) + 2*fine + detune')
    A('//')
    A('// so a voice with no correlated keybed/MIDI input (demo, rhythm, sequencer) can still')
    A('// be given its true absolute note:')
    A('//')
    A('//     note = (regs[8] - 0x80 - C(regs[1])) / 256')
    A('//')
    A('// C is NOT read from the wave ROM and NOT inferred from audio: it is arithmetic on the')
    A('// firmware\'s own 487 multisample SET descriptors --')
    A('//     C = (SET.basepitch - ((SET.root << 8) + 0x80)) + zone_trim')
    A('// with zone_trim the stride-6 zone record\'s +0x04..05 word (sub-CPU v142 asm')
    A('// LABEL_022AC5 L14341). MEASURED, over 5384 captured demo note-ons: decoding with C')
    A('// recovers an INTEGER MIDI note 70.4% of the time against a C-permuted null of')
    A('// 15.1 +- 6.9%, and 0.9% for the 0x3524 anchor it replaces. See')
    A('// notes/FINDINGS-kn5000-chunk-root-pitch.md.')
    A('//')
    A('// ⚠ THE TABLE IS NOT A CHIP INTERFACE. The real IC303 never sees C -- the sub-CPU has')
    A('// already folded it into +0x400. This is a DECODE of a value the chip does receive,')
    A('// which is why the HLE needs it and the hardware does not. Same standing as')
    A('// decode_wave_select()\'s directory walk: firmware-derived, not invented.')
    A('//')
    A('// COVERAGE (from the tsv, key-weighted by the SET zones\' key spans):')
    A('//   %d selectors, key weight %d' % (n, kw))
    A('//   single-valued C : %4d selectors (%.1f%%), key weight %d (%.1f%%)'
      % (n_single, 100.0 * n_single / n, kw - kw_amb, 100.0 * (kw - kw_amb) / kw))
    A('//   AMBIGUOUS C     : %4d selectors (%.1f%%), key weight %d (%.1f%%)  -> modal value,'
      % (n_amb, 100.0 * n_amb / n, kw_amb, 100.0 * kw_amb / kw))
    A('//                      counted and reported separately at device_stop.')
    A('//   a selector ABSENT from this table is NOT decodable and falls back to the anchor.')
    A('')
    A('#ifndef MAME_MATSUSHITA_KN5000_PITCH_TRIM_HXX')
    A('#define MAME_MATSUSHITA_KN5000_PITCH_TRIM_HXX')
    A('')
    A('#pragma once')
    A('')
    A('#include <cstdint>')
    A('')
    A('namespace kn5000_pitch_trim {')
    A('')
    A('struct entry_t')
    A('{')
    A('\tuint16_t sel;        // +0x040 word = (class << 12) | entry')
    A('\tint16_t  c;          // C, in 1/256 semitone units')
    A('\tuint8_t  ambiguous;  // 0 = the firmware tables give this selector exactly one C;')
    A('\t                     // 1 = more than one, and `c` is the key-weighted MODAL value')
    A('};')
    A('')
    A('// Sorted by `sel` -- std::lower_bound depends on it.')
    A('static const entry_t TABLE[] =')
    A('{')
    for sel, c, nd, _kw in rows:
        A('\t{ 0x%04X, %6d, %d },' % (sel, c, 1 if nd > 1 else 0))
    A('};')
    A('')
    A('static constexpr unsigned COUNT = %d;' % n)
    A('static constexpr unsigned COUNT_SINGLE_VALUED = %d;' % n_single)
    A('static constexpr unsigned COUNT_AMBIGUOUS = %d;' % n_amb)
    A('')
    A('} // namespace kn5000_pitch_trim')
    A('')
    A('#endif // MAME_MATSUSHITA_KN5000_PITCH_TRIM_HXX')
    return '\n'.join(L) + '\n'


def main():
    rows = read_tsv()
    text = emit(rows)
    if '--check' in sys.argv:
        try:
            cur = open(OUT).read()
        except OSError:
            sys.exit("%s does not exist; run without --check" % OUT)
        if cur != text:
            sys.exit("%s is STALE with respect to %s" % (OUT, TSV))
        print("up to date: %s (%d selectors)" % (OUT, len(rows)))
        return
    with open(OUT, 'w') as f:
        f.write(text)
    print("wrote %s (%d selectors, %d ambiguous)"
          % (OUT, len(rows), sum(1 for r in rows if r[2] > 1)))


if __name__ == '__main__':
    main()

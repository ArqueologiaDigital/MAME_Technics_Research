#!/usr/bin/env python3
"""Re-derives, from the ROMs alone, every number in the "TG pitch is zone-relative"
finding -- i.e. the evidence that the driver does NOT need fw::*_VOICE_RECORDS.

QUESTION ANSWERED: is the 18-bit value the firmware writes to the tone generator's
pitch register (class 0x2400 on KN7000) an ABSOLUTE musical pitch, or a rate index
RELATIVE to the selected wave zone's native playback rate?

ANSWER (printed below, from disassembly): relative.  pitch16 = ((note16 - zoneCenter16)
>> exp) + 0x4280 and pitch18 = (pitch16 + 0x1800) << 2, so pitch18 == 0x16A00 means
"play the selected zone at its native rate".  The absolute pitch therefore lives in the
WAVE ROM (undumped), not in the register traffic and not in the CPU's work RAM.

RUN:
    python3 tg_pitch_is_zone_relative.py \
        --kn7000 /path/to/kn7000 program ROM, de-interleaved, 4 MiB, loads at 0x48400000 \
        --kn6000 /path/to/kn6000_prog.bin
Needs MAME's unidasm on PATH or via --unidasm.
"""
import argparse, subprocess, sys, tempfile, os

# KN7000: the self-loaded library at CPU 0x4C000000 is a verbatim copy of program-ROM
# file offset 0x3B8FD1 (notes/library-rom-loading.md).  KN6000: file off = addr-0x48400000.
KN7K_LIB_FILE_BASE = 0x3B8FD1


def lib2file(a):
    return KN7K_LIB_FILE_BASE + (a - 0x4C000000)


def dis(unidasm, path, file_off, count, basepc):
    with tempfile.NamedTemporaryFile(suffix='.bin', delete=False) as f:
        d = open(path, 'rb').read()[file_off:file_off + count]
        f.write(d)
        tmp = f.name
    try:
        out = subprocess.run([unidasm, tmp, '-arch', 'mn10300', '-basepc', '%X' % basepc],
                             capture_output=True, text=True).stdout
    finally:
        os.unlink(tmp)
    return out


def want(text, needle, label):
    ok = needle.lower() in text.lower()
    print('  [%s] %-52s %s' % ('OK ' if ok else 'MISS', label, needle))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--kn7000', required=True)
    ap.add_argument('--kn6000')
    ap.add_argument('--unidasm', default='unidasm')
    a = ap.parse_args()
    bad = 0

    print('A. lib 0x4C031037..0x4C031064 -- note16 is STORED to rec+0x0C, then pitch16 is')
    print('   built RELATIVE to the wave zone (zone+0x0B = centre key, desc exp = key follow):')
    t = dis(a.unidasm, a.kn7000, lib2file(0x4C031037), 0x30, 0x4C031037)
    print(t)
    for n, l in (('movhu   d0, (0xc, a3)', 'note16 -> voice record +0x0C (what the driver snoops)'),
                 ('and     0x3800, d1', 'exp = (descriptor hw0 >> 11) & 7'),
                 ('movbu   (0xb, a2), d0', 'zone record +0x0B = CENTRE KEY'),
                 ('sub     d0, d3', 'note16 - centre16'),
                 ('asr     d2, d1', '>> exp  (key-follow scaling)'),
                 ('add     0x4280, d1', 'pitch16 neutral == zone at NATIVE RATE')):
        bad += not want(t, n, l)

    print('\nB. lib 0x4C02D5B1..0x4C02D605 -- the note-on pitch emitter: voice-record base,')
    print('   the pitch16 -> pitch18 packing, and the class-0x2400 TG write:')
    t = dis(a.unidasm, a.kn7000, lib2file(0x4C02D5B1), 0x58, 0x4C02D5B1)
    print(t)
    for n, l in (('mov     0xb4, d1', 'voice-record stride 0xB4'),
                 ('add     0x500af940, a3', 'voice-record base == fw::KN7000_VOICE_RECORDS'),
                 ('call    0x4c031127', 'runtime pitch accumulate -> pitch16'),
                 ('add     0x1800, d0', 'pitch18 = (pitch16 + 0x1800) << 2 ...'),
                 ('asl2    d1', '... the << 2'),
                 ('and     0x0003ffff, d1', '... 18 bits'),
                 ('mov     0x24000000, d1', 'TG register class 0x2400 (pitch)'),
                 ('call    0x4c036f9a', 'TG write primitive')):
        bad += not want(t, n, l)

    if a.kn6000:
        print('\nC. KN6000 0x484800A0 -- the SAME 0xB4-stride array, base baked in at link time:')
        t = dis(a.unidasm, a.kn6000, 0x80090, 0x30, 0x48480090)
        print(t)
        for n, l in (('mov     0xb4, d1', 'same stride'),
                     ('add     0x5027af28, d0', 'base == fw::KN6000_VOICE_RECORDS')):
            bad += not want(t, n, l)
        d6 = open(a.kn6000, 'rb').read()
        n28 = d6.count((0x5027AF28).to_bytes(4, 'little'))
        n1c = d6.count((0x5027AF1C).to_bytes(4, 'little'))
        print('  literal 0x5027AF28 in the KN6000 image: %d sites' % n28)
        print('  literal 0x5027AF1C (the KN6500 value)  : %d sites  <- a different BUILD,'
              ' 12 bytes away' % n1c)
        bad += (n28 == 0) or (n1c != 0)

    print('\nD. arithmetic that follows from A+B (no ROM needed):')
    neutral16 = 0x4280
    neutral18 = ((neutral16 + 0x1800) << 2) & 0x3FFFF
    print('   pitch18 at the zone\'s NATIVE RATE = ((0x4280 + 0x1800) << 2) = 0x%05X' % neutral18)
    print('   1 semitone = 0x100 in pitch16 = 0x400 in pitch18; 1 octave = 0x3000 = %d' % 0x3000)
    print('   playback rate = zone_native_rate * 2 ** ((pitch18 - 0x%05X) / 12288)' % neutral18)
    # the empirically calibrated keybed anchor (kn7000_mame de4fc88^: absolute decode)
    p18_c4 = 0x1C838
    print('   measured keybed Concert Grand anchor: pitch18 0x%05X == MIDI 60 (middle C)'
          % p18_c4)
    hz = 261.6255653 / 2.0 ** ((p18_c4 - neutral18) / 12288.0)
    print('   => a placeholder sample declared to sound %.3f Hz at pitch18 0x%05X'
          ' reproduces that anchor exactly' % (hz, neutral18))
    # what the Overture's G3 part shows about per-zone offsets
    p18_g3_riff = 0x19510          # measured, notes/tg-pitch-pipeline.md
    p18_keybed_55 = p18_c4 - 5 * 0x400
    print('   Overture G3 part writes 0x%05X for the same MIDI 55 the keybed maps to 0x%05X'
          ' => %.2f semitones of ZONE offset' % (p18_g3_riff, p18_keybed_55,
                                                 (p18_keybed_55 - p18_g3_riff) / 1024.0))

    print('\n%s' % ('FAIL: %d check(s) missed' % bad if bad else 'PASS: every check matched'))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())

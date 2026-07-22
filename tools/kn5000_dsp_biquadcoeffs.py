#!/usr/bin/env python3
"""
kn5000_dsp_biquadcoeffs.py -- decode of the KN5000 Sub CPU's `op 0x70` evaluation
helper, the routine that turns (frequency, Q, gain) into the coefficient words of a
uPD6383GF biquad band.

Companion to notes/kn5000-dsp-biquad-coeffs.md.  It does three things:

  1. `tables`  -- reads the frequency / Q / gain parameter tables straight out of the
                  sub-CPU ROM (proof that the helper's inputs are Hz, Q and dB).
  2. `design`  -- re-implements the helper's arithmetic exactly as the firmware does it
                  (bilinear transform, K = tan(pi*f0/fs), fs = 44100) and prints the
                  five words it emits, in emission order, in the firmware's own
                  fixed-point formats.
  3. `check`   -- the mandatory falsification pass: invert the emitted words back to
                  (f0, Q, gain), test pole stability, and locate the response peak.

Usage:
  python3 tools/kn5000_dsp_biquadcoeffs.py [subcpu.rom] [section]
     section in: tables | design | check | all   (default all)

Sub-CPU ROM base is 0xEF00 (file offset = cpu_addr - 0xEF00).
"""

import cmath
import math
import struct
import sys

SUB_BASE = 0xEF00
FS = 44100.0

# ---------------------------------------------------------------- ROM addresses
# All MEASURED in kn5000_subprogram_v142.rom; see the note for the disassembly.
ADDR_FREQ_TABLE = 0x012397   # 27 x float32, ISO third-octave centres
ADDR_Q_TABLE    = 0x012403   # 32 x float32
ADDR_GAIN_MUL   = 0x012F07   # double 0.5   : gain_dB = 0.5*v - 12.0
ADDR_GAIN_ADD   = 0x012F0F   # double -12.0
ADDR_PI_OVER_FS = 0x012F57   # double pi/44100 -- the anchor constant

# per-emit scale factors, mode 0 (peaking), in emission order
ADDR_SCALES_M0  = [0x012FAB, 0x012FAF, 0x012FB3, 0x012FB7, 0x012FBB]
ADDR_HALVERS_M0 = [0x012F9F, 0x012FA3, 0x012FA7]   # b0,b1,b2 divided by these


class Rom:
    def __init__(self, path, base=SUB_BASE):
        self.d = open(path, 'rb').read()
        self.base = base

    def f32(self, a):
        return struct.unpack_from('<f', self.d, a - self.base)[0]

    def f64(self, a):
        return struct.unpack_from('<d', self.d, a - self.base)[0]


# ---------------------------------------------------------------- the helper itself
#
# MEASURED transcription of LABEL_03A933 (reached from the op 0x70 stub at 0x03CD96,
# jump-table entry 0x0208 off base 0x03CB8E).  Mode 0 = peaking, mode 1 = bandpass.
#
#     K   = tan(pi * f0 / 44100)                 [double, then rounded to float]
#     A   = K / Q
#     B   = K * K
#     a0  = 1 + A + B
#     a1  = -2 * (1 - B)          =  2*(B - 1)
#     a2  = 1 + (B - A)
#     V   = 10 ^ (|gain_dB| / 20)                [double pow, twice]
#     n0  = 1 + V*A + B
#     n1  = a1                                   (verbatim copy: b1 == a1)
#     n2  = 1 - V*A + B
#   boost (gain >= 0):   b0=n0/a0 b1=n1/a0 b2=n2/a0  A1=-a1/a0  A2=-a2/a0
#   cut   (gain <  0):   b0=a0/n0 b1=a1/n0 b2=a2/n0  A1=-n1/n0  A2=-n2/n0
#     N   = (1 - A1 - A2) / (b0 + b1 + b2)       = 1 / H(z=1)
#     b0,b1,b2 <- N*b0/2, N*b1/2, N*b2/2
#   emitted, in this order, to consecutive DSP words starting at T1[0x70][band]:
#     b1 * 2^22,  b0 * 2^22,  b2 * 2^22,  A1 * 2^22,  A2 * 2^23

def design_mode0(f0, q, gain_db, fs=FS):
    """Bit-for-bit-faithful (in double) re-implementation of the mode-0 arithmetic."""
    K = math.tan(math.pi * f0 / fs)
    A = K / q
    B = K * K
    a0 = 1.0 + A + B
    a1 = -2.0 * (1.0 - B)
    a2 = 1.0 + (B - A)
    V = 10.0 ** (abs(gain_db) / 20.0)
    n0 = 1.0 + V * A + B
    n1 = a1
    n2 = 1.0 - V * A + B
    if gain_db >= 0.0:                 # boost: numerator gets the V
        b0, b1, b2 = n0 / a0, n1 / a0, n2 / a0
        A1, A2 = -a1 / a0, -a2 / a0
    else:                              # cut: the whole section is reciprocated
        b0, b1, b2 = a0 / n0, a1 / n0, a2 / n0
        A1, A2 = -n1 / n0, -n2 / n0
    N = (1.0 - A1 - A2) / (b0 + b1 + b2)
    b0, b1, b2 = N * b0 / 2.0, N * b1 / 2.0, N * b2 / 2.0
    return dict(K=K, N=N, b0=b0, b1=b1, b2=b2, A1=A1, A2=A2)


def design_mode1(f0, q, fs=FS):
    """Mode 1 -- no gain parameter, b1 forced to 0, b2 = -b0.  A bandpass."""
    K = math.tan(math.pi * f0 / fs)
    A, B = K / q, K * K
    a0 = 1.0 + A + B
    a1 = -2.0 * (1.0 - B)
    a2 = 1.0 + (B - A)
    b0 = A / a0
    return dict(K=K, b0=b0, b1=0.0, b2=-b0, A1=-a1 / a0, A2=-a2 / a0)


def to_words(c):
    """Emission order and fixed-point formats, MEASURED from the emit sequence."""
    return [
        ('b1', q_round(c['b1'], 22)),
        ('b0', q_round(c['b0'], 22)),
        ('b2', q_round(c['b2'], 22)),
        ('-a1', q_round(c['A1'], 22)),
        ('-a2', q_round(c['A2'], 23)),
    ]


def q_round(x, frac):
    v = int(round(x * (1 << frac)))
    return v & 0xFFFFFF, v


# ---------------------------------------------------------------- inversion
def invert(b0, b1, b2, A1, A2, fs=FS):
    """Recover (f0, Q, gain_dB) from the *unscaled* five coefficients.

    Uses only the denominator (A1, A2) for f0 and Q, so the recovery is independent
    of the numerator path and of the N/2 numerator scaling -- i.e. it is a real test.
        a1 = -A1, a2 = -A2 (both already normalised by a0=1)
        a1 = 2(B-1)/a0 , a2 = (1-A+B)/a0 , a0 = 1+A+B  with a0 normalised to 1
    Solve: from a1 and a2 (post-normalisation, a0'=1):
        1 + a1' + a2' = (1+A+B + 2B-2 + 1-A+B)/a0 = 4B/a0
        1 - a1' + a2' = (1+A+B - 2B+2 + 1-A+B)/a0 = 4/a0
        a2' - ... -> A/a0 = ((1 - a2')/2) ... see below
    """
    a1p, a2p = -A1, -A2
    s_plus = 1.0 + a1p + a2p          # = 4B/a0
    s_minus = 1.0 - a1p + a2p         # = 4/a0
    if s_minus <= 0 or s_plus <= 0:
        return None
    B = s_plus / s_minus              # = K^2
    K = math.sqrt(B)
    inv_a0 = s_minus / 4.0
    # 1 - a2' = (1+A+B - 1+A-B)/a0 = 2A/a0
    A = (1.0 - a2p) / (2.0 * inv_a0)
    q = K / A if A else float('inf')
    f0 = math.atan(K) * fs / math.pi
    # gain: |H| at f0 relative to DC, in dB
    dc = abs(resp(b0, b1, b2, A1, A2, 0.0, fs))
    g = 20.0 * math.log10(abs(resp(b0, b1, b2, A1, A2, f0, fs)) / dc)
    return f0, q, g


def resp(b0, b1, b2, A1, A2, f, fs=FS):
    z = cmath.exp(-2j * math.pi * f / fs)
    return (b0 + b1 * z + b2 * z * z) / (1.0 - A1 * z - A2 * z * z)


def stable(A1, A2):
    """Poles inside the unit circle for y = ... + A1*y1 + A2*y2, i.e. a1=-A1,a2=-A2."""
    a1, a2 = -A1, -A2
    return abs(a2) < 1.0 and abs(a1) < 1.0 + a2


# ---------------------------------------------------------------- sections
def sec_tables(rom):
    print("== parameter tables read out of the sub-CPU ROM (MEASURED)")
    freqs = [rom.f32(ADDR_FREQ_TABLE + 4 * i) for i in range(27)]
    qs = [rom.f32(ADDR_Q_TABLE + 4 * i) for i in range(32)]
    print("  frequency table @%06X (27 x f32):" % ADDR_FREQ_TABLE)
    print("   ", " ".join("%g" % v for v in freqs))
    print("  Q table @%06X (32 x f32):" % ADDR_Q_TABLE)
    print("   ", " ".join("%g" % v for v in qs))
    print("  gain  = %g * user - %g dB   (@%06X / @%06X)"
          % (rom.f64(ADDR_GAIN_MUL), -rom.f64(ADDR_GAIN_ADD),
             ADDR_GAIN_MUL, ADDR_GAIN_ADD))
    print("  pi/fs = %.17g   (@%06X)   -> fs = %.6f Hz"
          % (rom.f64(ADDR_PI_OVER_FS), ADDR_PI_OVER_FS,
             math.pi / rom.f64(ADDR_PI_OVER_FS)))
    print("  emit scales:", ["2^%d" % round(math.log2(rom.f32(a)))
                             for a in ADDR_SCALES_M0])
    print("  b-halvers  :", [rom.f32(a) for a in ADDR_HALVERS_M0])
    return freqs, qs


def sec_design(rom, freqs, qs):
    print("\n== worked examples (mode 0, peaking)")
    for f0, q, g in [(1000.0, 1.0, 12.0), (1000.0, 1.0, -12.0),
                     (100.0, 0.5, 6.0), (8000.0, 10.0, -6.0),
                     (40.0, 20.0, 0.5), (16000.0, 0.1, 12.0)]:
        c = design_mode0(f0, q, g)
        ws = to_words(c)
        print("  f0=%-7g Q=%-5g g=%+6.1f dB  N=%.6f" % (f0, q, g, c['N']))
        print("      " + "  ".join("%s=%06X" % (n, w[0]) for n, w in ws))


def sec_check(rom, freqs, qs):
    print("\n== FALSIFICATION PASS: invert, then test stability and peak location")
    bad_stab = 0
    worst_f = worst_q = worst_g = 0.0
    n = 0
    gains = [0.5 * v - 12.0 for v in range(0, 49)]
    for f0 in freqs:
        for q in qs:
            for g in gains:
                c = design_mode0(f0, q, g)
                n += 1
                if not stable(c['A1'], c['A2']):
                    bad_stab += 1
                    continue
                r = invert(c['b0'], c['b1'], c['b2'], c['A1'], c['A2'])
                if r is None:
                    bad_stab += 1
                    continue
                rf, rq, rg = r
                worst_f = max(worst_f, abs(rf - f0) / f0)
                if g >= 0:
                    worst_q = max(worst_q, abs(rq - q) / q)
                worst_g = max(worst_g, abs(rg - g))
    print("  cases                        : %d  (27 f0 x 32 Q x 49 gains)" % n)
    print("  unstable / non-invertible    : %d" % bad_stab)
    print("  worst relative f0 error      : %.3e" % worst_f)
    print("  worst relative Q  error, BOOST: %.3e" % worst_q)
    print("  worst absolute gain error dB : %.3e" % worst_g)
    # the cut branch reciprocates the section, so the POLE Q becomes Q/V.
    # PREDICTION (stated before running): recovered_Q == Q / 10^(|g|/20) exactly.
    worst_cut = 0.0
    for f0 in freqs:
        for q in qs:
            for g in gains:
                if g >= 0:
                    continue
                c = design_mode0(f0, q, g)
                rf, rq, rg = invert(c['b0'], c['b1'], c['b2'], c['A1'], c['A2'])
                pred = q / (10.0 ** (abs(g) / 20.0))
                worst_cut = max(worst_cut, abs(rq - pred) / pred)
    print("  CUT branch: worst |Q_rec - Q/10^(|g|/20)| rel : %.3e" % worst_cut)

    print("\n  -- peak-location check on a sample of presets --")
    for f0, q, g in [(1000.0, 1.0, 12.0), (1000.0, 1.0, -12.0),
                     (250.0, 4.0, 6.0), (6300.0, 0.7, -9.0)]:
        c = design_mode0(f0, q, g)
        # scan the response, find the extremum
        best = None
        f = 10.0
        while f < 20000.0:
            m = abs(resp(c['b0'], c['b1'], c['b2'], c['A1'], c['A2'], f))
            if best is None or (m > best[1] if g >= 0 else m < best[1]):
                best = (f, m)
            f *= 1.0005
        dc = abs(resp(c['b0'], c['b1'], c['b2'], c['A1'], c['A2'], 0.0))
        print("    f0=%-7g Q=%-4g g=%+5.1f -> extremum at %8.1f Hz (%.3f dB), "
              "DC gain %.6f, stable=%s"
              % (f0, q, g, best[0], 20 * math.log10(best[1]), dc,
                 stable(c['A1'], c['A2'])))

    print("\n  -- mode 1 (bandpass) sanity --")
    for f0, q in [(1000.0, 1.0), (100.0, 5.0), (8000.0, 0.5)]:
        c = design_mode1(f0, q)
        peak = None
        f = 10.0
        while f < 20000.0:
            m = abs(resp(c['b0'], c['b1'], c['b2'], c['A1'], c['A2'], f))
            if peak is None or m > peak[1]:
                peak = (f, m)
            f *= 1.0005
        print("    f0=%-7g Q=%-4g -> peak %8.1f Hz gain %.4f, DC %.2e, stable=%s"
              % (f0, q, peak[0], peak[1],
                 abs(resp(c['b0'], c['b1'], c['b2'], c['A1'], c['A2'], 0.0)),
                 stable(c['A1'], c['A2'])))


def main():
    rom_path = (sys.argv[1] if len(sys.argv) > 1 else
                '/home/fsanches/compartilhado/kn5000-roms-disasm/original_ROMs/'
                'kn5000_subprogram_v142.rom')
    which = sys.argv[2] if len(sys.argv) > 2 else 'all'
    rom = Rom(rom_path)
    freqs, qs = sec_tables(rom)
    if which in ('all', 'design'):
        sec_design(rom, freqs, qs)
    if which in ('all', 'check'):
        sec_check(rom, freqs, qs)


if __name__ == '__main__':
    main()

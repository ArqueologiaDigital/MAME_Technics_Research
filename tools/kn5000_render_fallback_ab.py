#!/usr/bin/env python3
"""What did the detect_period bound change actually do to a drum? Render both ways.

BACKGROUND. `detect_period()` finds no fundamental in an aperiodic recording. Until
2026-08-14 it then returned `N<<16` for anything up to 2048 samples, and `update_pitch()`
treated N as the period:

    step = freq * N / 48000          (samples of source advanced per output sample)

For a 1496-sample chunk at C4 that is step = 8.16, so the whole recording is squeezed into
1496/8.16 = 183 output samples -- 3.8 ms. A brush slap becomes a click. The file's own comment
already blamed "extreme noise" on exactly two wave-select words, `+040 = 0x505B` and `0x5046`,
and those are **Brush Slap** (SET 375) and **Rock Rim** (SET 376).

The fix returns 0 above 256 samples, which makes `update_pitch` set `pitch_step = 1.0` -- play
as recorded.

This renders both, so the difference can be heard and measured rather than argued:

    python3 tools/kn5000_render_fallback_ab.py --outdir /tmp/ab

Writes, per chunk, `<name>_old.wav` (resampled, the bug) and `<name>_new.wav` (as recorded),
and prints duration and spectral centroid for each. The WAVs are regenerable, so they are not
committed -- this script is the artefact.

★ MEASURED 2026-08-14, and it corrects the expected acceptance signal:

    brush_slap  1496 samples: 31.17 ms -> 3.83 ms   (compressed 8.2x)  centroid 10982 -> 12423 Hz
    rock_rim    1568 samples: 32.67 ms -> 3.83 ms   (compressed 8.5x)  centroid 12295 -> 12618 Hz

The audible signature is DURATION, not pitch. An 8x resample ought to lift the spectrum 8x, but
these hits are broadband and already centred near 11-12 kHz, so the shifted content lands past
Nyquist and folds back -- the centroid saturates and barely moves (1.0-1.1x). Any acceptance test
that looks for a high-band energy change on these chunks will therefore see almost nothing while
the defect is plainly audible as a 31 ms brush slap turning into a 3.8 ms click. Grade on
duration and on aliasing, not on centroid.

⚠ WHAT THIS IS NOT: it is an offline model of the two code paths, not a capture of the
emulator. It shows the size of the effect; it does not prove the shipped binary does this. An
in-emulator capture triggering a patch that selects one of these chunks is still owed.
"""
import argparse
import math
import os
import struct
import sys
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kn5000_period_oracle as O  # noqa: E402

RATE = 48000
C4 = 261.6256
TARGETS = [(0x505B, "brush_slap"), (0x5046, "rock_rim")]


def chunk_pcm(rom, page, entry):
    d = O.page_dir(rom, page)
    start, n = d[entry]
    return [struct.unpack_from("<h", rom, start + 2 * i)[0] for i in range(n)]


def resample(src, step):
    """Linear-interpolating playback at `step` source samples per output sample."""
    out, pos = [], 0.0
    while pos < len(src) - 1:
        i = int(pos)
        f = pos - i
        out.append(int(src[i] * (1.0 - f) + src[i + 1] * f))
        pos += step
    return out


def centroid(x):
    n = 1
    while n < len(x):
        n <<= 1
    a = list(x) + [0] * (n - len(x))
    # simple DFT magnitude via numpy if available, else skip
    try:
        import numpy as np
        m = abs(np.fft.rfft(np.asarray(a, dtype=float)))
        f = np.fft.rfftfreq(n, 1.0 / RATE)
        return float((m * f).sum() / max(m.sum(), 1e-9))
    except ImportError:
        return float("nan")


def write_wav(path, samples):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(b"".join(struct.pack("<h", max(-32768, min(32767, s))) for s in samples))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--outdir", default="kn5000_ab_out")
    ap.add_argument("--note", type=float, default=C4, help="played frequency in Hz")
    args = ap.parse_args()
    os.makedirs(args.outdir, exist_ok=True)

    rom = O.load_rom()
    for word, name in TARGETS:
        page, entry = (word >> 12) & 3, word & 0xFFF
        src = chunk_pcm(rom, page, entry)
        n = len(src)
        old_step = args.note * n / RATE
        old = resample(src, old_step)
        new = list(src)

        write_wav(os.path.join(args.outdir, f"{name}_old.wav"), old)
        write_wav(os.path.join(args.outdir, f"{name}_new.wav"), new)

        print(f"{name}  (+040=0x{word:04X}, page {page} entry 0x{entry:03X}, {n} samples)")
        print(f"  OLD  step {old_step:6.3f}  ->{len(old):6d} out samples "
              f"= {1000.0 * len(old) / RATE:7.2f} ms   centroid {centroid(old):8.0f} Hz")
        print(f"  NEW  step  1.000  ->{len(new):6d} out samples "
              f"= {1000.0 * len(new) / RATE:7.2f} ms   centroid {centroid(new):8.0f} Hz")
        print(f"  the bug compressed it {old_step:.1f}x and lifted its centroid "
              f"{centroid(old) / max(centroid(new), 1e-9):.1f}x\n")


if __name__ == "__main__":
    main()

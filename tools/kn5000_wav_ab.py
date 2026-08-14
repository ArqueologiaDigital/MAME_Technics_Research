#!/usr/bin/env python3
"""Compare two emulator audio captures: did a code change reach the sound, and where?

Built for the 2026-08-14 detect_period bound change, whose whole claim is that 35 reachable
chunks stop being resampled ~8x. The gate cannot see that — its liveness check sits at the
home screen with no notes playing, and its audio oracle runs on the KN7000 — so the change
needs a KN5000 capture with the demo actually playing.

    python3 tools/kn5000_wav_ab.py before.wav after.wav

⚠ TWO TRAPS THAT MADE A FIRST ATTEMPT AT THIS VACUOUS (2026-08-14):
  1. **The stimulus must actually fire.** The KN5000 demo needs NAVIGATION -- DEMO -> LEFT 4 ->
     LEFT 2 -- not one button press. Pressing DEMO alone leaves transport/AccPlayMode flat at
     0x00 and the machine silent. Confirm transport 0x0420 reads 0x04.
  2. **Channel 0 of these captures is ALWAYS SILENT.** The KN5000 writes 3 channels and the
     audio is on channels 1 and 2 (measured: ch0 rms 0.00, ch1 472, ch2 525 with the demo
     running). Analysing channel 0 shows silence no matter what the machine is doing.
Both were skipped once, producing two silent files whose "bit-identical" comparison was
mistaken for evidence of no regression. This tool now reports per-channel rms so neither can
recur unnoticed.

FIRST QUESTION, and it is the one that can end the exercise: are the two captures IDENTICAL?
If they are, the stimulus never selected an affected chunk, and this A/B proves nothing either
way. That is a legitimate negative result and the tool says so rather than hunting for a
difference that is not there.

If they differ it reports, per second: rms of each, rms of the difference, and the peak sample
delta — so the change can be localised in time and lined up against what the demo is playing.
It also reports total duration, because for THIS change the expected signature is duration
(a 31 ms brush slap had been compressed to 3.8 ms), not a spectral shift: the affected hits are
broadband near 11-12 kHz, so 8x-shifted content folds back past Nyquist and the centroid barely
moves. See tools/kn5000_render_fallback_ab.py.
"""
import struct
import sys
import wave


def load(path):
    with wave.open(path, "rb") as w:
        n, ch, sw, sr = w.getnframes(), w.getnchannels(), w.getsampwidth(), w.getframerate()
        raw = w.readframes(n)
    if sw != 2:
        sys.exit(f"{path}: expected 16-bit, got {sw * 8}-bit")
    s = struct.unpack("<%dh" % (len(raw) // 2), raw)
    return s, ch, sr, n


def rms(xs):
    if not xs:
        return 0.0
    return (sum(float(v) * v for v in xs) / len(xs)) ** 0.5


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    a, cha, sra, na = load(sys.argv[1])
    b, chb, srb, nb = load(sys.argv[2])
    print(f"A {sys.argv[1]}: {na} frames, {cha}ch, {sra} Hz, {na / sra:.2f}s")
    print(f"B {sys.argv[2]}: {nb} frames, {chb}ch, {srb} Hz, {nb / srb:.2f}s")
    if (cha, sra) != (chb, srb):
        sys.exit("format mismatch -- captures are not comparable")

    # Per-channel levels FIRST: a silent capture makes every later number meaningless.
    print()
    for c in range(cha):
        ca = a[c::cha]
        cb = b[c::chb]
        print(f"  ch{c}: rmsA {rms(ca):9.2f}  rmsB {rms(cb):9.2f}"
              + ("   <-- SILENT IN BOTH, carries no evidence" if rms(ca) == 0 and rms(cb) == 0 else ""))
    if all(rms(a[c::cha]) == 0 for c in range(cha)):
        print("\n=> BOTH CAPTURES ARE SILENT. Nothing was played, so this comparison cannot "
              "support\n   any conclusion in either direction. Fix the stimulus and re-run.")
        return

    if a == b:
        print("\n=> IDENTICAL. The stimulus never selected a chunk the change affects, so this "
              "A/B\n   proves nothing about the change. Pick a stimulus that reaches one, or "
              "accept\n   that the change is unreachable from here.")
        return

    m = min(len(a), len(b))
    diff = [a[i] - b[i] for i in range(m)]
    nz = sum(1 for d in diff if d)
    print(f"\n=> DIFFER: {nz} of {m} samples ({100.0 * nz / m:.2f}%), "
          f"peak |delta| {max(abs(d) for d in diff)}, rms(diff) {rms(diff):.1f}")
    if na != nb:
        print(f"   length differs by {abs(na - nb)} frames "
              f"({abs(na - nb) / sra * 1000:.1f} ms)")

    step = sra * cha
    print(f"\n{'sec':>4} {'rmsA':>9} {'rmsB':>9} {'rmsDiff':>9} {'peakDelta':>10}")
    for t in range(0, m // step):
        w = slice(t * step, (t + 1) * step)
        da = diff[w]
        if not any(da):
            continue
        print(f"{t:>4} {rms(a[w]):>9.1f} {rms(b[w]):>9.1f} {rms(da):>9.1f} "
              f"{max(abs(v) for v in da):>10d}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Per-second RMS of a WAV, for the WSA1R note-off (voice-retirement) A/B.

QUESTION THIS ANSWERS: does a released MIDI note RETIRE, or does it accumulate
into a rising drone?  Before the note-off release model, the WSA1R placeholder
never freed a voice (the tone generator's busy bit never fell, so the firmware's
retire path never ran); feeding note_long.mid made the left-channel RMS climb
monotonically to ~21000 by ~55 s.  With the model, each released note decays and
the firmware frees the voice, so the RMS stops climbing -- it tracks the notes
instead of summing them.

USAGE:
    python3 tools/rigs/wsa1_wav_rms.py <file.wav> [window_seconds=1.0]

It prints per-window RMS (left channel) and a verdict: the peak, the final
window, and the largest monotonic run.  A drone shows final ~= peak and a long
monotonic run; retiring voices show final well below peak and no long run.

Stimulus (committed beside this): tools/rigs/wsa1_midi_in_test.py writes
note_long.mid -- a note every second from t=15 s.  Run each binary with
`-midiin note_long.mid -wavwrite out.wav -seconds_to_run 55 -nomax`.
"""
import struct, sys, wave


def per_window_rms(path, win_s):
    with wave.open(path, "rb") as w:
        ch, width, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        if width != 2:
            raise SystemExit(f"expected 16-bit PCM, got {width*8}-bit")
        raw = w.readframes(n)
    step = ch                                   # take channel 0 (left)
    samples = struct.unpack("<%dh" % (len(raw) // 2), raw)
    left = samples[0::step]
    win = max(1, int(rate * win_s))
    out = []
    for i in range(0, len(left), win):
        seg = left[i:i + win]
        if not seg:
            break
        rms = (sum(s * s for s in seg) / len(seg)) ** 0.5
        out.append(rms)
    return out, rate


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    path = sys.argv[1]
    win_s = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    rms, rate = per_window_rms(path, win_s)
    print(f"{path}: {len(rms)} windows of {win_s:g}s @ {rate} Hz")
    for i, r in enumerate(rms):
        bar = "#" * int(r / 400)
        print(f"  t={i*win_s:5.1f}s  rms={r:8.1f}  {bar}")
    peak = max(rms) if rms else 0.0
    final = rms[-1] if rms else 0.0
    # longest monotonic non-decreasing run among AUDIBLE windows (drone signature).
    # Silence (boot) is excluded so the run counts real accumulation, not the quiet.
    floor = max(50.0, 0.05 * peak)
    best = run = 0
    prev = None
    for r in rms:
        if r <= floor:
            run = 0; prev = None; continue
        run = run + 1 if (prev is None or r >= prev - 1.0) else 1
        prev = r
        best = max(best, run)
    print(f"\n  peak={peak:.1f}  final={final:.1f}  final/peak={ (final/peak if peak else 0):.2f}"
          f"  longest_nondecreasing_run={best} windows")
    verdict = ("DRONE (voices accumulate)" if peak > 3000 and final > 0.6 * peak and best >= 8
               else "voices retire (no sustained monotonic climb)")
    print(f"  VERDICT: {verdict}")


if __name__ == "__main__":
    sys.exit(main())

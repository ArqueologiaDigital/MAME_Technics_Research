#!/usr/bin/env python3
"""Read a kn5000_capture_hold.sh run and report, per HELD NOTE, the rendered amplitude
ENVELOPE over the hold.

This is the measurement Felipe's 2026-08-06 report needs and the one that level metrics
cannot give: rms/peak/clipping over a whole capture are all perfectly happy while every
held note dies 20 ms in.  The number that can FAIL here is `sus_db`, the level of the
last tenth of the hold relative to the loudest tenth -- a sustaining patch keeps it near
0 dB, a patch that decays away drives it to -60 dB or below.

  usage: kn5000_hold_analyze.py <rundir> [<rundir> ...]
"""
import sys, os, wave, array, math, csv

WIN = 0.050          # analysis window, seconds
FLOOR = -120.0


def db(x, ref):
    if x <= 0 or ref <= 0:
        return FLOOR
    return 20.0 * math.log10(x / ref)


def env(a, ch, sr, t0, t1):
    """RMS in WIN-second windows over [t0, t1)."""
    n = int(WIN * sr)
    out = []
    t = t0
    while t + WIN <= t1:
        i = int(t * sr) * ch
        seg = a[i:i + n * ch]
        if not seg:
            break
        out.append((t, math.sqrt(sum(v * v for v in seg) / len(seg))))
        t += WIN
    return out


def run(d):
    marks = os.path.join(d, "marks.txt")
    wav = os.path.join(d, "out.wav")
    if not (os.path.exists(marks) and os.path.exists(wav)):
        print(f"{d}: missing marks.txt or out.wav")
        return
    w = wave.open(wav, "rb")
    sr, ch, n = w.getframerate(), w.getnchannels(), w.getnframes()
    a = array.array("h")
    a.frombytes(w.readframes(n))
    w.close()

    # the EG words the firmware programmed, per hold, from the notelog
    notes = []
    csvp = os.path.join(d, "notes.csv")
    if os.path.exists(csvp):
        notes = list(csv.DictReader(open(csvp)))

    print(f"== {d}   sr={sr} ch={ch} dur={n/sr:.1f}s   window={WIN*1000:.0f} ms")
    print(f"{'sound':9s} {'hold':>6s} {'peak':>7s} {'attack':>7s} {'mid':>7s} "
          f"{'end':>7s} {'sus_db':>7s} {'rel_db':>7s}  segments (level<<8|rate)")
    for line in open(marks):
        if line.startswith("#") or not line.strip():
            continue
        # Two marks formats, both written by rigs in this directory:
        #   kn5000_hold_note.lua     "sound t_on t_off"          (3 fields)
        #   kn5000_patch_probe.lua   "patch midi t_on t_off"     (4 fields; midi -1 = hold)
        f = line.split()
        if len(f) == 4:
            sound, midi, t0, t1 = f
            if int(midi) >= 0:
                continue          # a swept note, not a hold -- not this tool's job
        else:
            sound, t0, t1 = f
        t0, t1 = float(t0), float(t1)
        e = env(a, ch, sr, t0, t1)
        if not e:
            continue
        peak = max(v for _, v in e)
        k = max(1, len(e) // 10)
        atk = max(v for _, v in e[:k])
        mid = sum(v for _, v in e[len(e)//2 - k//2: len(e)//2 + k//2 + 1]) / max(1, k)
        end = sum(v for _, v in e[-k:]) / k
        # the release: 300 ms starting 100 ms after key-off, vs the sustain
        r = env(a, ch, sr, t1 + 0.10, t1 + 0.40)
        rel = max((v for _, v in r), default=0.0)
        segs = " ".join(
            f"ch{x['ch']}:{x['eg0_end']}/{x['eg1_end']}/{x['eg2_end']}"
            for x in notes if t0 - 0.2 <= float(x['t_on']) <= t0 + 0.5)
        print(f"{sound:9s} {t1-t0:6.1f} {peak:7.0f} {atk:7.0f} {mid:7.0f} {end:7.0f} "
              f"{db(end, peak):7.1f} {db(rel, end if end else peak):7.1f}  {segs}")


for d in sys.argv[1:]:
    run(d)

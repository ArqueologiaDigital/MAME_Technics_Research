#!/usr/bin/env python3
"""Read a kn5000_capture_hold.sh run and report, per HELD NOTE, the rendered amplitude
ENVELOPE over the hold.

This is the measurement Felipe's 2026-08-06 report needs and the one that level metrics
cannot give: rms/peak/clipping over a whole capture are all perfectly happy while every
held note dies 20 ms in.  The number that can FAIL here is `sus_db`, the level of the
last tenth of the hold relative to the loudest tenth -- a sustaining patch keeps it near
0 dB, a patch that decays away drives it to -60 dB or below.

  usage: kn5000_hold_analyze.py [--shape] <rundir> [<rundir> ...]

--shape adds the FULL ENVELOPE SHAPE of each hold: the level at fixed times after the
gate, in dB relative to the ATTACK PEAK, plus the time the envelope first crosses -3 /
-6 / -12 dB and the per-voice teardown source.  This exists because `sus_db` alone
answers the wrong question.  Felipe's report is "shorter sustain than EXPECTED",
compared against the real instrument -- and a patch that falls 20 dB over three seconds
and then holds scores a comfortable `sus_db` while sounding, to a player, like it died.
Only the shape can tell those two apart.  ko_src: 1 = ended by the real key release
(correct), 2 = the firmware's own 0x7E00 FREE, i.e. the voice was TORN DOWN mid-hold.
"""
import sys, os, wave, array, math, csv

WIN = 0.050          # analysis window, seconds
FLOOR = -120.0
SHAPE_T = (0.1, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0)


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

        if not SHAPE:
            continue
        # ---- ENVELOPE SHAPE, relative to the ATTACK PEAK -----------------------------
        # `atk` (the loudest window of the first tenth) is the reference, not the global
        # peak: it is the level the player hears the note START at, which is what
        # "shorter sustain than expected" is measured against.
        def at(ts):
            # the window whose start is nearest ts seconds after the gate
            if not e:
                return None
            return min(e, key=lambda p: abs((p[0] - t0) - ts))[1]
        cols = []
        for ts in SHAPE_T:
            if ts > (t1 - t0):
                cols.append("    -  ")
                continue
            v = at(ts)
            cols.append(f"{db(v, atk):7.1f}")
        # first crossing of each threshold, measured on a level that has to STAY below
        # (a single dipping window is a beat note, not a decay)
        cross = []
        for thr in (-3.0, -6.0, -12.0):
            hit = "  -  "
            for i, (tt, v) in enumerate(e):
                if db(v, atk) <= thr and all(db(x, atk) <= thr + 1.0 for _, x in e[i:i + 6]):
                    hit = f"{tt - t0:5.2f}"
                    break
            cross.append(hit)
        ko = " ".join(
            f"ch{x['ch']}:{float(x['t_ko_rel']):.2f}/src{x['ko_src']}"
            for x in notes if t0 - 0.2 <= float(x['t_on']) <= t0 + 0.5)
        print(f"{'  shape':9s} " + " ".join(f"{t:>7}" for t in
                                            [f"{x}s" for x in SHAPE_T]))
        print(f"{'   dB':9s} " + " ".join(cols) +
              f"   | -3dB@{cross[0]} -6dB@{cross[1]} -12dB@{cross[2]}")
        print(f"{'   ko':9s} {ko}")


SHAPE = "--shape" in sys.argv
for d in sys.argv[1:]:
    if d.startswith("--"):
        continue
    run(d)

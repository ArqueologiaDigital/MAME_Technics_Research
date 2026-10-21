#!/usr/bin/env python3
# mklisten.py WORK OUT -- the listening files from the runs' raw recordings (README.md here).
#
# QUESTION IT ANSWERS: are the files Felipe gets audible and comparable? It trims each recording to the music (from
# 0.5 s before the first note), keeps two channels as ordinary stereo 16-bit 48 kHz WAV, applies one gain per
# comparison group (the group's loudest peak to -1 dBFS), writes an MP3 of each (ffmpeg, libmp3lame), and checks
# every output by analysis: duration, peak, RMS, the first note, the share of 1 s windows with sound, and for the
# MIDI takes the level of each section of listen.mid and of the releases. Prints the table and writes OUT/stats.txt.
#
# Inputs, under WORK (made by run_midi.sh / run_aw.sh):
#   midi-on/run.wav, midi-off/run.wav, midi-byp/run.wav    listen.mid, REVERB on / off / DSP bypassed (3 channels)
#   aw-dsp-live/run.wav, aw-dsp-live/live.wav              the intro in DSP mode: computed (3 ch) and host capture (2 ch)
#   aw-tg/run.wav                                          the intro in tone-generator mode (3 ch)
# MAME's -wavwrite file has 3 channels: 0 and 1 are the instrument's left and right outputs, 2 is the floppy drive's
# sound (silent once the loader is read). Channels 0 and 1 are kept, and the script checks channel 2 is silent in the
# trimmed span. The live capture is pw-record's 2 channels as they are.
import os
import subprocess
import sys
import wave

import numpy as np

WORK, OUT = sys.argv[1], sys.argv[2]
RATE = 48000
PRE = 0.5            # seconds kept before the first note
TAIL = 0.5           # seconds kept after the last sound (live capture only)
THR_DB = -90.0       # a 10 ms window above this is sound (the sources are digital zero before the music;
                     # the intro fades in from about -70 dBFS)


def read(path):
    with wave.open(path, "rb") as w:
        assert w.getsampwidth() == 2, path
        assert w.getframerate() == RATE, (path, w.getframerate())
        n, ch = w.getnframes(), w.getnchannels()
        a = np.frombuffer(w.readframes(n), dtype="<i2").reshape(-1, ch).astype(np.float64) / 32768.0
    return a


def db(x):
    return 20 * np.log10(max(x, 1e-12))


def frames_db(x, win=0.01):
    m = x if x.ndim == 1 else np.sqrt((x ** 2).mean(axis=1))
    k = int(win * RATE)
    n = len(m) // k
    return 10 * np.log10(np.maximum((m[: n * k] ** 2).reshape(n, k).mean(axis=1), 1e-24))


def first_sound(x, after_s):
    f = frames_db(x)
    i0 = int(after_s / 0.01)
    hit = np.nonzero(f[i0:] > THR_DB)[0]
    assert len(hit), "no sound after %.1f s" % after_s
    return (i0 + hit[0]) * 0.01


def last_sound(x):
    f = frames_db(x)
    hit = np.nonzero(f > THR_DB)[0]
    return (hit[-1] + 1) * 0.01


def events(path):
    t = {}
    for line in open(path):
        p = line.split()
        if len(p) > 2 and p[1] == "INTRO":
            t["intro"] = float(p[0])
    return t


# (name, group, source, channels, start-search (s in the source), end: seconds after the first note or "last")
MID_LEN = 68.0 - 30.0                      # listen.mid: first note at emulated 30.0, file end at 68.0
def opt(f, *a):
    try:
        return f(*a)
    except (OSError, KeyError, ValueError):
        return None


aw_dsp = opt(lambda: events(os.path.join(WORK, "aw-dsp-live/events.txt"))["intro"])
aw_tg = opt(lambda: events(os.path.join(WORK, "aw-tg/events.txt"))["intro"])
wall = opt(lambda: float(open(os.path.join(WORK, "aw-dsp-live/intro_wall.txt")).read()))
AW_LEN = 60.0
PLAN = [
    ("midi-reverb-on", "midi", "midi-on/run.wav", (0, 1), 29.5, MID_LEN),
    ("midi-reverb-off", "midi", "midi-off/run.wav", (0, 1), 29.5, MID_LEN),
    ("midi-dsp-bypassed", "midi", "midi-byp/run.wav", (0, 1), 29.5, MID_LEN),
    ("aw-intro-dsp-computed", "aw-dsp", "aw-dsp-live/run.wav", (0, 1), aw_dsp, AW_LEN),
    ("aw-intro-dsp-live", "aw-dsp", "aw-dsp-live/live.wav", (0, 1), None if wall is None else max(0.0, wall - 3.0), "last"),
    ("aw-intro-tg-computed", "aw-tg", "aw-tg/run.wav", (0, 1), aw_tg, AW_LEN),
]
os.makedirs(OUT, exist_ok=True)
clips = {}
for name, group, src, chans, after, length in PLAN:
    path = os.path.join(WORK, src)
    if not os.path.exists(path) or after is None:
        print("missing %s: %s skipped" % (src, name))
        continue
    a = read(path)
    t1 = first_sound(a[:, list(chans)], after)
    s0 = max(0, int((t1 - PRE) * RATE))
    s1 = int((last_sound(a[:, list(chans)]) + TAIL) * RATE) if length == "last" else int((t1 + length) * RATE)
    s1 = min(s1, len(a))
    seg = a[s0:s1]
    other = [c for c in range(a.shape[1]) if c not in chans]
    other_db = db(np.abs(seg[:, other]).max()) if other else None
    clips[name] = dict(group=group, src=src, chans=chans, t1=t1, s0=s0 / RATE, x=seg[:, list(chans)], other_db=other_db)

gains = {}
for name, c in clips.items():
    pk = np.abs(c["x"]).max()
    gains[c["group"]] = max(gains.get(c["group"], 0.0), pk)
gains = {g: -1.0 - db(pk) for g, pk in gains.items()}

rows = []
for name, c in clips.items():
    g = gains[c["group"]]
    y = np.clip(np.round(c["x"] * (10 ** (g / 20)) * 32768.0), -32768, 32767).astype("<i2")
    wav = os.path.join(OUT, name + ".wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(RATE); w.writeframes(y.tobytes())
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", wav, "-codec:a", "libmp3lame", "-q:a", "2",
                    os.path.join(OUT, name + ".mp3")], check=True)
    # the check, on the file as written
    z = read(wav)
    dur = len(z) / RATE
    peak, rms = db(np.abs(z).max()), db(np.sqrt((z ** 2).mean()))
    first = first_sound(z, 0.0)
    f1 = frames_db(z, 1.0)
    sounding = (f1 > -50.0).mean() * 100
    r = dict(name=name, group=c["group"], src=c["src"], chans=c["chans"], cut="%.2f-%.2f" % (c["s0"], c["s0"] + dur),
             dur=dur, gain=g, peak=peak, rms=rms, first=first, sounding=sounding, other=c["other_db"])
    if c["group"] == "midi":
        def seg_db(a_, b_):
            q = z[int((first + a_) * RATE): int((first + b_) * RATE)]
            return db(np.sqrt((q ** 2).mean())) if len(q) else float("nan")
        # sections of listen.mid, seconds after the first note (gen_listen_mid.py)
        r["sections"] = [("square-lead chord held 0.5-3", seg_db(0.5, 3)), ("0.2-0.7 s after its release", seg_db(3.2, 3.7)),
                         ("1-2 s after its release", seg_db(4, 5)), ("3-5 s after its release", seg_db(6, 8)),
                         ("piano 8-21.3", seg_db(8, 21.3)), ("strings+drums 22-30", seg_db(22, 30)),
                         ("pad held 31.5-35", seg_db(31.5, 35)), ("pad 0.5-1.5 s after release", seg_db(35.5, 36.5)),
                         ("end 36.5-38", seg_db(36.5, 38))]
    rows.append(r)

with open(os.path.join(OUT, "stats.txt"), "w") as f:
    def P(s=""):
        print(s); f.write(s + "\n")
    hdr = ["file", "group", "source", "cut (s in source)", "duration", "gain", "peak", "RMS", "first note", "1 s windows > -50 dBFS", "ch 2 peak"]
    data = [[r["name"] + ".wav", r["group"], r["src"] + " ch " + ",".join(map(str, r["chans"])), r["cut"],
             "%.2f s" % r["dur"], "%+.2f dB" % r["gain"], "%.2f dBFS" % r["peak"], "%.2f dBFS" % r["rms"],
             "%.2f s" % r["first"], "%.0f%%" % r["sounding"],
             ("%.1f dBFS" % r["other"]) if r["other"] is not None else "-"] for r in rows]
    w = [max(len(x) for x in col) for col in zip(hdr, *data)]
    P("| " + " | ".join(h.ljust(n) for h, n in zip(hdr, w)) + " |")
    P("|" + "|".join("-" * (n + 2) for n in w) + "|")
    for d in data:
        P("| " + " | ".join(x.ljust(n) for x, n in zip(d, w)) + " |")
    P()
    mids = [r for r in rows if "sections" in r]
    if mids:
        hdr = ["section of listen.mid (s after the first note)"] + [r["name"] for r in mids]
        data = [[s] + ["%.1f dBFS" % r["sections"][i][1] for r in mids] for i, (s, _) in enumerate(mids[0]["sections"])]
        w = [max(len(x) for x in col) for col in zip(hdr, *data)]
        P("| " + " | ".join(h.ljust(n) for h, n in zip(hdr, w)) + " |")
        P("|" + "|".join("-" * (n + 2) for n in w) + "|")
        for d in data:
            P("| " + " | ".join(x.ljust(n) for x, n in zip(d, w)) + " |")

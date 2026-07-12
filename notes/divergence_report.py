#!/usr/bin/env python3
"""Divergence-focused verdict across sweep runs (current four-effect binary).

Reads each RUNDIR/metrics.json (produced by analyze_fx.py) and classifies every
effect segment by the DIVERGENCE failure mode -- the historical reverb bug where
a SHARC effect program self-excites to the +/-full-scale rail.

Signals (per segment):
  frail = frames where max|s24| over DSP DM 0xC342-0xC359 >= 0x7FFF00 (rail)
  fpeak = running max |s24| over those slots (8388608 = 100% FS; rail thr 0x7FFF00)
  clip  = int16 DAC samples with |s| >= 32000 anywhere in the segment

Verdict rules (worst-first):
  FAIL     frail>0                    -> a DSP slot railed (divergence)
  FAIL     clip>0                     -> audible DAC clipping
  SUSPECT  fpeak >= 50% FS (4.19M)    -> near-rail, no hard rail yet
  WATCH    fpeak >= 25% FS (2.10M)    -> elevated vs the 4-12% healthy band
  PASS     otherwise

Calibration (R1 reverb, healthy excited): fpeak 4-12% FS, frail 0, clip 0.
"""
import json, sys

FS = 8388608
RAIL = 0x7FFF00
def pct(v): return 100.0 * v / FS

def verdict(m):
    fr = m.get("frail_note", 0) + m.get("frail_tail", 0) + m.get("frail_sel", 0)
    fp = m.get("fpeak", 0)
    cl = m.get("clip", 0)
    if fr > 0:   return "FAIL", f"railed {fr} frames"
    if cl > 0:   return "FAIL", f"{cl} DAC clips"
    if fp >= FS // 2:        return "SUSPECT", f"fpeak {pct(fp):.0f}% FS"
    if fp >= FS // 4:        return "WATCH",   f"fpeak {pct(fp):.0f}% FS"
    return "PASS", ""

def main():
    rank = {"FAIL": 0, "SUSPECT": 1, "WATCH": 2, "PASS": 3}
    rows = []
    for rd in sys.argv[1:]:
        try:
            ms = json.load(open(rd + "/metrics.json"))
        except FileNotFoundError:
            print(f"!! no metrics.json in {rd} (run analyze_fx.py first)", file=sys.stderr); continue
        run = rd.rstrip("/").split("/")[-1]
        for m in ms:
            v, why = verdict(m)
            rows.append((rank[v], run, m["seg"], v, why,
                         m.get("fpeak", 0), m.get("clip", 0),
                         m.get("frail_note", 0) + m.get("frail_tail", 0) + m.get("frail_sel", 0),
                         m.get("held_peak", 0), m.get("up_sel", 0)))
    rows.sort(key=lambda r: (r[0], -r[5]))
    counts = {}
    for r in rows: counts[r[3]] = counts.get(r[3], 0) + 1
    print(f"=== {len(rows)} segments across {len(sys.argv)-1} runs ===")
    print(f"verdicts: " + "  ".join(f"{k}={counts.get(k,0)}" for k in ("FAIL","SUSPECT","WATCH","PASS")))
    print(f"{'verdict':8} {'run':4} {'effect':40} {'fpeak%FS':>8} {'clip':>5} {'frail':>5} {'DACpk':>6} {'upl':>4}  why")
    for _, run, seg, v, why, fp, cl, fr, dpk, upl in rows:
        print(f"{v:8} {run:4} {seg[:40]:40} {pct(fp):8.1f} {cl:5d} {fr:5d} {dpk:6.0f} {upl:4d}  {why}")
    # machine-readable
    out = {"segments": len(rows), "counts": counts,
           "fails": [dict(run=r[1], seg=r[2], why=r[4], fpeak=r[5], clip=r[6], frail=r[7]) for r in rows if r[3] == "FAIL"],
           "suspects": [dict(run=r[1], seg=r[2], why=r[4], fpeak=r[5]) for r in rows if r[3] == "SUSPECT"]}
    json.dump(out, open("/tmp/claude-1000/-home-fsanches-compartilhado-KN7000/c6cf97f4-b4f1-4ba1-adc0-85474706b167/scratchpad/fxtest/divergence_verdicts.json", "w"), indent=1)

if __name__ == "__main__":
    main()

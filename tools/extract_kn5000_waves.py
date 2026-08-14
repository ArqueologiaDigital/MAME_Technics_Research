#!/usr/bin/env python3
"""
extract_kn5000_waves.py -- KN5000 waveform ROM extractor (donor-sample tool).

PURPOSE
  Extract every PCM waveform from the dumped Technics SX-KN5000 waveform mask
  ROMs (IC304/IC305/IC306/IC307, 4 MB each) into WAV files plus a JSON
  manifest, as DONOR MATERIAL for a clearly-marked SYNTHETIC/fabricated
  placeholder wave ROM for the SX-KN7000 (whose four wave ROMs are undumped).

  Nothing produced by this tool is, or may be represented as, a real KN7000
  dump. It is legitimate preservation-adjacent fabrication from the same
  manufacturer's previous flagship, and every output is labeled as such.

ROM FORMAT (per kn5000-docs/waveform-rom-format.md, verified against dumps)
  Each 4 MB chip is a self-describing bank:
    0x0000        198-entry index: {uint16 param_ptr, uint16 wave_offset} LE
                  (first param_ptr == 0x318 == 198*4, confirming entry count)
    0x0318..      variable-length parameter records:
                  uint16 wave_start (== index wave_offset), then N param
                  words [flags:8][value:8] (key zones, tuning, 0x40/0x80
                  loop/end markers)
    <min offset>  signed 16-bit LE PCM; wave_offset * 16 = byte address
    tail          0xFF padding
  Observed: IC304/305/306 share a byte-identical index+param header (same
  wave layout) but hold different PCM (parallel banks/layers); IC307 has its
  own layout. Entry 0 of each chip is a 256-sample test wave
  (sine/saw/triangle/sine).

USAGE
  python3 extract_kn5000_waves.py [--roms A.ic304 B.ic305 ...]
      [--outdir DIR] [--rate 44100] [--no-wavs]

OUTPUT
  DIR/<chip>/w###_off0x######.wav   (mono s16, --rate Hz header)
  DIR/manifest.json                 per-chip entries + unique-wave analysis
"""

import argparse
import json
import math
import os
import struct
import sys
import wave as wavmod
import zlib
from array import array

# CRC32s of ROMs with verified provenance (per kn5000-docs/waveform-rom-format.md)
KNOWN_DUMPS = {
    0x20FF4629: "IC307 QS6GX3C32008 -- genuine dump",
}
# IC304/305/306 are NO_DUMP; the files sometimes present alongside IC307 are
# the KN5000 project's own SYNTHETIC sine/saw/triangle banks (per
# kn5000-docs/tone-generator.md "synthetic approximations available").
# They are NOT donor material.

INDEX_ENTRIES = 198
INDEX_END = INDEX_ENTRIES * 4          # 0x318
WAVE_OFFSET_GRANULE = 16               # wave_offset * 16 = byte address

DEFAULT_ROM_DIR = "/home/fsanches/compartilhado/kn5000_original_roms/kn5000"
DEFAULT_ROMS = [
    os.path.join(DEFAULT_ROM_DIR, "kn5000_waveform_rom.ic%d" % n)
    for n in (304, 305, 306, 307)
]

PARAM_FLAG_NAMES = {
    0x00: "keyzone",
    0x01: "perkey_tune",
    0x08: "perkey_tune_alt",
    0x0A: "transition",
    0x1C: "header",
    0x40: "mid_marker",     # possible loop point / split
    0x80: "end_marker",
    0xC0: "terminal_zone",  # end + mid combined
}


def parse_index(data):
    """Return list of (param_ptr, wave_offset) for the 198-entry index."""
    entries = []
    for i in range(INDEX_ENTRIES):
        param_ptr, wave_off = struct.unpack_from("<HH", data, i * 4)
        entries.append((param_ptr, wave_off))
    if entries[0][0] != INDEX_END:
        raise ValueError(
            "entry0 param_ptr 0x%04x != 0x%04x -- not a KN5000 waveform ROM?"
            % (entries[0][0], INDEX_END))
    return entries


def parse_param_records(data, entries):
    """Split the param region into records using sorted param_ptr deltas.

    Returns {param_ptr: {"wave_start": w, "params": [(flags, value), ...]}}.
    """
    ptrs = sorted({p for p, _ in entries})
    pcm_start = min(w for _, w in entries) * WAVE_OFFSET_GRANULE
    ends = {}
    for i, p in enumerate(ptrs):
        ends[p] = ptrs[i + 1] if i + 1 < len(ptrs) else pcm_start
    records = {}
    for p in ptrs:
        wave_start = struct.unpack_from("<H", data, p)[0]
        nparams = (ends[p] - p - 2) // 2
        params = []
        for k in range(nparams):
            w = struct.unpack_from("<H", data, p + 2 + 2 * k)[0]
            params.append(((w >> 8) & 0xFF, w & 0xFF))
        records[p] = {"wave_start": wave_start, "params": params}
    return records


def wave_regions(data, entries):
    """Return [(wave_offset_words, byte_start, byte_len), ...] for the unique
    waves, lengths derived from consecutive unique offsets; the last wave is
    trimmed of trailing 0xFF padding."""
    offs = sorted({w for _, w in entries})
    regions = []
    end_of_rom = len(data)
    # trim trailing 0xFF padding for the final wave
    trimmed = end_of_rom
    while trimmed > 0 and data[trimmed - 1] == 0xFF:
        trimmed -= 1
    trimmed += trimmed & 1  # keep 16-bit alignment
    for i, w in enumerate(offs):
        start = w * WAVE_OFFSET_GRANULE
        end = offs[i + 1] * WAVE_OFFSET_GRANULE if i + 1 < len(offs) else trimmed
        regions.append((w, start, max(0, end - start)))
    return regions


def pcm_samples(data, byte_start, byte_len):
    a = array("h")
    a.frombytes(data[byte_start:byte_start + (byte_len & ~1)])
    if sys.byteorder == "big":
        a.byteswap()
    return a


def rms(seg):
    if not seg:
        return 0.0
    return math.sqrt(sum(float(s) * s for s in seg) / len(seg))


def analyze(samples, rate):
    """Pure-python acoustic analysis: RMS, envelope shape, zero-crossing
    rate, dominant pitch (autocorrelation over a sustained window)."""
    n = len(samples)
    out = {
        "samples": n,
        "duration_s": round(n / rate, 4),
    }
    if n == 0:
        return out
    peak = max(abs(min(samples)), abs(max(samples)))
    out["peak"] = peak
    out["rms"] = round(rms(samples if n <= 65536 else samples[:65536]), 1)

    # 8-segment RMS envelope -> attack/decay character
    seg_rms = []
    step = max(1, n // 8)
    for i in range(8):
        seg = samples[i * step:(i + 1) * step]
        if len(seg) > 4096:           # subsample long segments
            seg = seg[::len(seg) // 4096]
        seg_rms.append(rms(seg))
    out["envelope_rms"] = [round(x, 1) for x in seg_rms]
    env_peak = max(seg_rms) or 1.0
    out["end_level_ratio"] = round(seg_rms[-1] / env_peak, 3)  # ~1 sustained, ~0 one-shot
    out["attack_ratio"] = round(seg_rms[0] / env_peak, 3)

    # zero-crossing rate (proxy for brightness / noisiness)
    win = samples[n // 4: n // 4 + min(4096, n - n // 4)] or samples
    zc = 0
    prev = win[0]
    for s in win[1:]:
        if (s >= 0) != (prev >= 0):
            zc += 1
        prev = s
    out["zcr"] = round(zc / max(1, len(win) - 1), 4)

    # dominant pitch via normalized autocorrelation on a mid-file window.
    # Correct method: r(lag) starts ~1 near lag 0 for any smooth signal, so
    # first descend past the zero-lag lobe (first dip below 0.3), THEN take
    # the highest peak; finally walk down to the fundamental (smallest lag
    # whose score is comparable and integer-divides the peak lag).
    wlen = min(2048, n)
    start = max(0, (n - wlen) // 2) if n > 4096 else 0
    w = [float(s) for s in samples[start:start + wlen]]
    mean = sum(w) / len(w)
    w = [s - mean for s in w]
    e0 = sum(s * s for s in w)
    best_lag, best_r = 0, 0.0
    if e0 > 1e3 and wlen >= 64:
        max_lag = min(wlen // 2, 1000)
        rs = [0.0, 0.0]
        for lag in range(2, max_lag + 1):
            r = sum(a * b for a, b in zip(w, w[lag:]))
            norm = math.sqrt(e0 * (sum(s * s for s in w[lag:]) or 1.0))
            rs.append(r / norm)
        # find end of the zero-lag lobe
        lobe_end = next((i for i in range(2, len(rs)) if rs[i] < 0.3),
                        len(rs))
        for lag in range(lobe_end, len(rs)):
            if rs[lag] > best_r:
                best_r, best_lag = rs[lag], lag
        # fundamental refinement: smallest divisor lag with a similar score
        if best_lag:
            for div in range(int(best_lag / max(2, lobe_end)), 1, -1):
                cand = int(round(best_lag / div))
                if cand >= 2 and cand < len(rs) and rs[cand] > 0.85 * best_r:
                    best_lag, best_r = cand, rs[cand]
                    break
    if best_lag and best_r > 0.3:
        out["period_samples"] = best_lag
        out["pitch_hz_at_rate"] = round(rate / best_lag, 2)
        out["pitch_confidence"] = round(best_r, 3)
    else:
        out["period_samples"] = None
        out["pitch_hz_at_rate"] = None
        out["pitch_confidence"] = round(best_r, 3)
    return out


def classify(a, has_end_marker, has_mid_marker):
    """Coarse acoustic class for donor mapping."""
    if a["samples"] == 0 or a.get("peak", 0) < 16:
        return "silence"
    pitched = a["pitch_confidence"] > 0.55 and a["pitch_hz_at_rate"]
    sustained = a["end_level_ratio"] > 0.5
    percussive = a["end_level_ratio"] < 0.15 and a["attack_ratio"] > 0.35
    noisy = not pitched and a["zcr"] > 0.08
    if a["samples"] <= 2048 and pitched and sustained:
        return "single/multi-cycle loop (sustained timbre)"
    if noisy and not sustained:
        return "drum/percussion (one-shot noise)"
    if pitched and percussive:
        return "struck/plucked (attack+decay)"
    if pitched and sustained:
        return "sustained instrument (looped)"
    if pitched:
        return "pitched (decaying)"
    if sustained:
        return "noise loop (breath/texture)"
    return "unpitched one-shot"


def process_rom(path, outdir, rate, write_wavs):
    name = os.path.basename(path)
    chip = name.split(".")[-1] if "." in name else name
    data = open(path, "rb").read()
    entries = parse_index(data)
    records = parse_param_records(data, entries)
    regions = wave_regions(data, entries)

    chip_dir = os.path.join(outdir, chip)
    if write_wavs:
        os.makedirs(chip_dir, exist_ok=True)

    # per-index-entry decode
    entry_list = []
    for i, (pp, wo) in enumerate(entries):
        rec = records[pp]
        flags_present = sorted({f for f, _ in rec["params"]})
        entry_list.append({
            "entry": i,
            "param_ptr": pp,
            "wave_offset": wo,
            "wave_byte_addr": wo * WAVE_OFFSET_GRANULE,
            "record_matches_index": rec["wave_start"] == wo,
            "params": ["%02X:%02X" % (f, v) for f, v in rec["params"]],
            "keyzones": [v for f, v in rec["params"] if f in (0x00, 0xC0)],
            "flags_present": ["0x%02X" % f for f in flags_present],
        })

    wave_list = []
    wave_users = {}
    for e in entry_list:
        wave_users.setdefault(e["wave_offset"], []).append(e["entry"])

    for wi, (wo, bstart, blen) in enumerate(regions):
        samples = pcm_samples(data, bstart, blen)
        a = analyze(samples, rate)
        users = wave_users.get(wo, [])
        # aggregate loop-ish flags over all records that use this wave
        has_mid = has_end = False
        zones = []
        for ei in users:
            fl = entry_list[ei]["flags_present"]
            has_mid |= "0x40" in fl or "0xC0" in fl
            has_end |= "0x80" in fl or "0xC0" in fl
            zones.append(entry_list[ei]["keyzones"])
        wav_name = "w%03d_off0x%06X.wav" % (wi, bstart)
        info = {
            "wave_index": wi,
            "chip": chip,
            "wave_offset_words": wo,
            "byte_offset": bstart,
            "byte_length": blen,
            "loopflags": {"mid_0x40": has_mid, "end_0x80": has_end},
            "zones": zones,
            "used_by_entries": users,
            "wav": os.path.join(chip, wav_name),
            "class": classify(a, has_end, has_mid),
        }
        info.update(a)
        wave_list.append(info)
        if write_wavs and blen >= 2:
            with wavmod.open(os.path.join(chip_dir, wav_name), "wb") as f:
                f.setnchannels(1)
                f.setsampwidth(2)
                f.setframerate(rate)
                if sys.byteorder == "big":
                    swapped = array("h", samples)
                    swapped.byteswap()
                    f.writeframes(swapped.tobytes())
                else:
                    f.writeframes(samples.tobytes())
    crc = zlib.crc32(data) & 0xFFFFFFFF
    return {
        "rom": path,
        "chip": chip,
        "crc32": "%08x" % crc,
        "provenance": KNOWN_DUMPS.get(
            crc, "UNVERIFIED -- not a known genuine dump (IC304-306 files "
                 "are typically the project's synthetic sine/saw/tri banks)"),
        "index_entries": len(entries),
        "unique_waves": len(wave_list),
        "pcm_start": min(w for _, w in entries) * WAVE_OFFSET_GRANULE,
        "entries": entry_list,
        "waves": wave_list,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--roms", nargs="+", default=DEFAULT_ROMS)
    ap.add_argument("--outdir", default="kn5000_waves_out")
    ap.add_argument("--rate", type=int, default=44100,
                    help="WAV header sample rate (native TG rate unknown; "
                         "44100 default)")
    ap.add_argument("--allow-unverified", action="store_true",
                    help="process ROMs whose CRC32 is not in KNOWN_DUMPS. Off by default: "
                         "the default --roms list names IC304-306, which are NOT dumps but "
                         "the project's synthetic banks, and extracting them would put "
                         "fabricated PCM into the donor pool under a real chip name.")
    ap.add_argument("--no-wavs", action="store_true",
                    help="manifest only, skip WAV writing")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    manifest = {
        "_provenance": (
            "DONOR/FABRICATED material: PCM extracted from dumped Technics "
            "SX-KN5000 waveform mask ROMs for use in a clearly-marked "
            "SYNTHETIC placeholder KN7000 wave ROM. NOT a KN7000 dump."),
        "rate": args.rate,
        "roms": [],
    }
    for rom in args.roms:
        if not os.path.exists(rom):
            print("skipping %s (absent)" % rom, flush=True)
            continue
        with open(rom, "rb") as fh:
            crc = zlib.crc32(fh.read()) & 0xFFFFFFFF
        if crc not in KNOWN_DUMPS and not args.allow_unverified:
            print("SKIPPING %s -- crc32 %08x is not a known genuine dump. "
                  "Pass --allow-unverified to force." % (rom, crc), flush=True)
            continue
        print("processing %s ..." % rom, flush=True)
        manifest["roms"].append(process_rom(rom, args.outdir, args.rate,
                                            not args.no_wavs))
    if not manifest["roms"]:
        raise SystemExit("no verified donor ROM processed -- refusing to write an empty manifest")
    mpath = os.path.join(args.outdir, "manifest.json")
    with open(mpath, "w") as f:
        json.dump(manifest, f, indent=1)
    total_pcm = sum(w["byte_length"] for r in manifest["roms"] for w in r["waves"])
    print("wrote %s (%d roms, %d unique waves, %.1f MB PCM)" % (
        mpath, len(manifest["roms"]),
        sum(r["unique_waves"] for r in manifest["roms"]),
        total_pcm / 1048576.0))


if __name__ == "__main__":
    main()

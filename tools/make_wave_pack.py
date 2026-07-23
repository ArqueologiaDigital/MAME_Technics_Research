#!/usr/bin/env python3
"""Build the SYNTHETIC KN7000 wave pack (kn7000_waves_synthetic.rom).

The KN7000's four PCM wave ROMs are UNDUMPED. This tool fabricates a clearly-
labeled placeholder pack from donor waves extracted out of the *genuine* KN5000
IC307 waveform ROM dump (tools/extract_kn5000_waves.py), keyed by the KN7000's
runtime sample-select decode (aux word bank/zone -- see
notes/wave-select-decode-and-donor-plan.md). It is NOT a KN7000 dump and never
claims to be: a provenance block is embedded and the driver loads it BAD_DUMP.

Pack layout (little-endian):
  +0x000  magic  "KN7WVSY2"
  +0x008  u32    entry count
  +0x00C  u32    (reserved, 0)
  +0x010  256B   ASCII provenance
  +0x110  entries, 32 bytes each:
          u8 bank, u8 zone_lo, u8 zone_hi, u8 flags(bit0=looped)
          u32 pcm_off (bytes from file start), u32 pcm_len (samples)
          u32 loop_start (samples), u32 loop_len (samples)
          u32 root_mhz (root pitch, milli-Hz, at 44100 Hz playback)
          8B  ASCII label
  PCM pool: s16le mono 44100 Hz. Loop seams are crossfaded in place so the
  driver can wrap with a plain position jump.
File padded to exactly 16 MiB (the driver ROM region size).
"""
import json, struct, sys, wave, zlib, hashlib, argparse, math
from pathlib import Path

PACK_SIZE = 0x1000000
MAGIC = b"KN7WVSY2"

# --- FABRICATED DEFAULT SINE (faithful MECHANISM, not faithful data) ----------
# Felipe Sanches' faithful-mechanism principle: the KN7000/KN6000/KN6500 wave
# ROMs are undumped, so voices whose runtime sample-select maps to no donor zone
# used to fall back to a computed sin() oscillator in the render loop. Real
# hardware has NO sine oscillator -- every voice reads PCM from wave ROM. So we
# fabricate the fallback timbre as an honest PCM sample and play it through the
# SAME sample-playback datapath (start/len/loop/interp) as the donor zones. The
# audible result is unchanged (a clean sine at the same pitch/level); only the
# MECHANISM becomes faithful. This entry uses the reserved wildcard bank 0xFF so
# it never zone-matches a real voice; the driver adopts it as the default that
# any otherwise-unmapped voice maps to (so the per-voice wave-select is NEVER -1).
SINE_LEN = 441                     # one cycle; 44100/441 = 100.000 Hz root, exact
SINE_ROOT_HZ = 44100.0 / SINE_LEN  # = 100.000 Hz

def build_sine_entry(pcm_base, pool):
    """One single-cycle, whole-loop sine at full scale. Returns the 32-byte entry
    record and appends its s16le PCM to `pool` (mutated in place)."""
    smp = [max(-32768, min(32767, int(round(32767.0 * math.sin(2.0 * math.pi * i / SINE_LEN)))))
           for i in range(SINE_LEN)]
    off = pcm_base + len(pool)
    pool += struct.pack("<%dh" % SINE_LEN, *smp)
    ent = struct.pack("<BBBBIIIII8s",
        0xFF, 0x00, 0x00, 1,                 # bank 0xFF = DEFAULT wildcard (never zone-matches)
        off, SINE_LEN, 0, SINE_LEN,          # whole single cycle loops seamlessly
        int(round(SINE_ROOT_HZ * 1000.0)), b"SINE\0\0\0\0")
    return ent

def load_wav(path):
    w = wave.open(str(path), "rb")
    assert w.getnchannels() == 1 and w.getsampwidth() == 2
    data = w.readframes(w.getnframes())
    return list(struct.unpack("<%dh" % (len(data) // 2), data))

def normalize(smp):
    """Balance donor levels: common peak, applied AFTER carving (a segment cut out
    of a large multisample blob must be normalized by ITS OWN peak)."""
    peak = max(1, max(abs(x) for x in smp))
    g = 28000.0 / peak
    return [max(-32768, min(32767, int(round(x * g)))) for x in smp]

def crossfade_seam(smp, loop_start, loop_len, period):
    """Blend the loop head with the material just past the loop end (click-free wrap)."""
    xf = min(int(period), loop_len // 4)
    for i in range(max(0, xf)):
        a = loop_start + i                       # head
        b = loop_start + loop_len + i            # just past the loop end
        if b >= len(smp):
            break
        t = i / xf
        smp[a] = int(smp[a] * t + smp[b] * (1.0 - t))

def pick_loop(smp, period):
    """Choose a loop region near the tail: >= ~2000 samples, whole periods."""
    period = max(8, int(round(period)))
    nper = max(4, (2000 + period - 1) // period)
    loop_len = nper * period
    pad = period // 2
    loop_start = max(0, len(smp) - loop_len - pad)
    loop_len = min(loop_len, len(smp) - loop_start - 1)
    return loop_start, loop_len

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--waves", required=True, help="kn5000_waves extraction dir (with manifest.json + ic307/)")
    ap.add_argument("--map", default=str(Path(__file__).parent / "wave_pack_map.json"))
    ap.add_argument("--out", required=True, help="output kn7000_waves_synthetic.rom path")
    args = ap.parse_args()

    waves_dir = Path(args.waves)
    manifest = json.load(open(waves_dir / "manifest.json"))
    ic307 = [r for r in manifest["roms"] if "ic307" in r["rom"]][0]
    assert "genuine" in ic307["provenance"], "refusing: ic307 manifest not marked genuine"
    wrec = {w["wave_index"]: w for w in ic307["waves"]}

    spec = json.load(open(args.map))
    entries, pool = [], bytearray()
    # +1 entry for the fabricated default sine (built first, index 0).
    pcm_base = 0x110 + 32 * (len(spec["entries"]) + 1)
    entries.append(build_sine_entry(pcm_base, pool))
    print(f"  DEFAULT     SINE fallback (fabricated) {SINE_LEN} smp root {SINE_ROOT_HZ:.1f} Hz loop 0+{SINE_LEN}")
    for e in spec["entries"]:
        w = wrec[e["wave"]]
        smp = load_wav(waves_dir / "ic307" / Path(w["wav"]).name)
        # optional carve: [start, end] sample range (for concatenated multisample blobs)
        if e.get("segment"):
            a, b = int(e["segment"][0]), int(e["segment"][1])
            smp = smp[max(0, a):min(len(smp), b)]
        smp = normalize(smp)
        period = w.get("period_samples") or 64
        # root pitch: explicit override in the map wins (audition/name-grounded),
        # else the manifest estimate, else the period
        if "root_hz" in e:
            root_hz = float(e["root_hz"])
        else:
            root_hz = w.get("pitch_hz_at_rate") or (44100.0 / period)
            if w.get("pitch_confidence", 1.0) < 0.3:
                root_hz = 44100.0 / period
        period = 44100.0 / root_hz
        # explicit loop [start, len] (relative to the carved segment) wins
        if "loop" in e:
            loop_start, loop_len = int(e["loop"][0]), int(e["loop"][1])
            loop_start = max(0, min(loop_start, len(smp) - 2))
            loop_len = max(16, min(loop_len, len(smp) - loop_start - 1))
        else:
            loop_start, loop_len = pick_loop(smp, period)
        crossfade_seam(smp, loop_start, loop_len, period)
        off = pcm_base + len(pool)
        pool += struct.pack("<%dh" % len(smp), *smp)
        entries.append(struct.pack("<BBBBIIIII8s",
            e["bank"], int(e["zone_lo"], 0), int(e["zone_hi"], 0), 1,
            off, len(smp), loop_start, loop_len,
            int(round(root_hz * 1000.0)), e["label"].encode()[:8].ljust(8, b"\0")))
        print(f"  bank{e['bank']} zones {e['zone_lo']}-{e['zone_hi']}: w{e['wave']:<3} "
              f"({e['label']}) {len(smp)} smp root {root_hz:.1f} Hz loop {loop_start}+{loop_len}")

    prov = ("SYNTHETIC KN7000 WAVE PLACEHOLDER -- NOT A DUMP. Donor PCM from the genuine "
            "KN5000 IC307 waveform ROM (CRC32 20ff4629); mapping per tools/wave_pack_map.json. "
            "Entry 0 (bank 0xFF) is a FABRICATED sine placeholder for unmapped voices -- "
            "faithful sample-playback mechanism, fabricated data. Built by tools/make_wave_pack.py.").encode()[:255]
    pack = bytearray()
    pack += MAGIC
    pack += struct.pack("<II", len(entries), 0)
    pack += prov.ljust(256, b"\0")
    for ent in entries:
        pack += ent
    assert len(pack) == pcm_base
    pack += pool
    assert len(pack) <= PACK_SIZE, f"pack too large: {len(pack)}"
    pack += b"\0" * (PACK_SIZE - len(pack))

    Path(args.out).write_bytes(pack)
    crc = zlib.crc32(pack) & 0xFFFFFFFF
    sha = hashlib.sha1(pack).hexdigest()
    print(f"\nwrote {args.out} ({len(pack)} bytes, {len(entries)} entries, pool {len(pool)//2} samples)")
    print(f"ROM_LOAD hashes:  CRC({crc:08x}) SHA1({sha})")

if __name__ == "__main__":
    main()

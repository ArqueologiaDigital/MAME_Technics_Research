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
import json, struct, sys, wave, zlib, hashlib, argparse
from pathlib import Path

PACK_SIZE = 0x1000000
MAGIC = b"KN7WVSY2"

def load_wav(path):
    w = wave.open(str(path), "rb")
    assert w.getnchannels() == 1 and w.getsampwidth() == 2
    data = w.readframes(w.getnframes())
    smp = list(struct.unpack("<%dh" % (len(data) // 2), data))
    # normalize to a common peak so donor levels are balanced across families
    peak = max(1, max(abs(x) for x in smp))
    g = 28000.0 / peak
    return [max(-32768, min(32767, int(round(x * g)))) for x in smp]

def pick_loop(smp, period):
    """Choose a loop region near the tail: >= ~2000 samples, whole periods."""
    period = max(8, int(round(period)))
    nper = max(4, (2000 + period - 1) // period)
    loop_len = nper * period
    pad = period // 2
    loop_start = max(0, len(smp) - loop_len - pad)
    loop_len = min(loop_len, len(smp) - loop_start - 1)
    # crossfade the seam: blend the loop tail into the loop head region
    xf = min(period, loop_len // 4)
    for i in range(xf):
        a = loop_start + i                       # head
        b = loop_start + loop_len + i            # just past the loop end
        if b >= len(smp):
            break
        t = i / xf
        smp[a] = int(smp[a] * t + smp[b] * (1.0 - t))
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
    pcm_base = 0x110 + 32 * len(spec["entries"])
    for e in spec["entries"]:
        w = wrec[e["wave"]]
        smp = load_wav(waves_dir / "ic307" / Path(w["wav"]).name)
        period = w.get("period_samples") or 64
        root_hz = w.get("pitch_hz_at_rate") or (44100.0 / period)
        if w.get("pitch_confidence", 1.0) < 0.3:
            root_hz = 44100.0 / period
        loop_start, loop_len = pick_loop(smp, period)
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
            "Built by tools/make_wave_pack.py.").encode()[:255]
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

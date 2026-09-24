#!/usr/bin/env python3
"""How does the KN5000 wave ROM store playback rate -- explicitly, or implicitly?

WHY THIS MATTERS FOR THE KN7000
  The KN7000's four wave ROMs are NO_DUMP, so the driver cannot turn the chip's
  18-bit pitch word (p18, +0x400 per semitone) into a frequency: it lacks each
  sample's root rate. Today it dodges that by reading the firmware's own computed
  musical pitch out of CPU RAM, which the hardware could never do.
  If the KN5000 -- same manufacturer, same "index-not-address" sampler design --
  stores no per-sample base rate either, then ONE estimated anchor suffices for the
  KN7000 and the RAM read can be replaced by arithmetic.

WHAT IS MEASURED  (IC307, the one hardware-rooted dump, crc32 20ff4629)
  * the 198-entry index table at 0x0000: {param_ptr, wave_offset}
  * every parameter record it points at, classified by the documented flag byte
  * specifically the per-key TUNING words (flags 0x01 / 0x08), whose low byte is a
    signed pitch offset -- the only pitch-ish metadata in the ROM

  The question each answers:
    - is there a per-sample BASE RATE field?      -> if absent, the rate is implicit
    - how large are the tuning offsets?           -> if small, one anchor + offsets
    - how many samples carry any tuning at all?   -> if few, one anchor suffices

RUN  python3 kn5000_wave_tuning.py <kn5000_waveform_rom.ic307>
"""
import sys, collections, zlib

def u16(d, o):
    return d[o] | (d[o + 1] << 8)

def main(path):
    d = open(path, 'rb').read()
    crc = zlib.crc32(d) & 0xffffffff
    print(f"file {path}\n  size {len(d)}  crc32 {crc:08x}"
          f"{'  (matches the documented IC307 dump)' if crc == 0x20ff4629 else '  ⚠ NOT the documented dump'}")

    N = 198
    idx = [(u16(d, i * 4), u16(d, i * 4 + 2)) for i in range(N)]
    print(f"\nindex table: {N} entries, first param_ptr = 0x{idx[0][0]:04X} "
          f"(= {N}*4 = 0x{N*4:04X}, i.e. immediately past the table)")

    # Records are VARIABLE LENGTH and self-terminating: the documented end markers
    # are flag 0x80 (end-of-record) and 0xC0 (terminal zone boundary = 0x80|0x40),
    # i.e. flag bit 7. An earlier version of this script ran each record to the NEXT
    # record's pointer instead, which swept PCM bytes in as "parameters" and invented
    # undocumented flags (0x23, 0x11, 0x13 ...) and impossible tuning offsets. The
    # clean-termination rate below is what catches that: if records do not end on a
    # bit-7 flag, this parse is wrong and nothing derived from it should be believed.
    uniq = sorted({p for p, _ in idx})
    print(f"distinct parameter records: {len(uniq)} (198 entries share them)")

    CAP = 512                      # words; longest documented record is 424 params
    flagcount = collections.Counter()
    tuning, keyzones = [], []
    sizes = collections.Counter()
    clean = 0
    for rp in uniq:
        o, n = rp + 2, 0           # first word is wave_start
        while o + 1 < len(d) and n < CAP:
            word = u16(d, o)
            flag, val = word >> 8, word & 0xFF
            flagcount[flag] += 1
            if flag in (0x01, 0x08):
                # per the format doc, ONLY 0xF0..0xFF is a signed pitch offset;
                # 0x00..0x7F in this position is a MIDI key number.
                if val >= 0xF0:
                    tuning.append((rp, flag, val - 256))
                else:
                    keyzones.append((rp, flag, val))
            o += 2; n += 1
            if flag & 0x80:
                clean += 1
                break
        sizes[n] += 1
    print(f"records terminating on a bit-7 flag: {clean} of {len(uniq)} "
          f"({100.0*clean/len(uniq):.0f}%)")
    if clean < 0.8 * len(uniq):
        print("  ⚠ PARSE NOT TRUSTWORTHY -- most records do not self-terminate.")

    print("\nparameter-word FLAG byte census (the documented meanings):")
    meaning = {0x00: "key zone boundary", 0x01: "per-key pitch/tuning",
               0x08: "per-key pitch/tuning (alt)", 0x0A: "transition marker",
               0x1C: "initial/header", 0x40: "mid-record marker",
               0x80: "end-of-record", 0xC0: "terminal zone boundary"}
    for f, n in sorted(flagcount.items(), key=lambda kv: -kv[1])[:12]:
        print(f"  0x{f:02X}  {n:6d}   {meaning.get(f, '(undocumented)')}")

    print(f"\nrecord sizes: {len(sizes)} distinct; most common "
          f"{sorted(sizes.items(), key=lambda kv: -kv[1])[:6]}")

    print(f"\nPER-KEY TUNING (flags 0x01/0x08, low byte 0xF0..0xFF = signed offset):")
    print(f"  {len(tuning)} tuning words across {len({t[0] for t in tuning})} records")
    if tuning:
        offs = [t[2] for t in tuning]
        print(f"  offset range {min(offs)} .. {max(offs)}")
        print(f"  distribution: {sorted(collections.Counter(offs).items())}")
    print(f"  (same flags with a low byte 0x00..0x7F = key numbers: {len(keyzones)})")

    print("\nIS THERE A PER-SAMPLE BASE-RATE FIELD?")
    print("  The record format is {wave_start, params...} where every param word's")
    print("  high byte is one of the flags above -- key zones, tuning deltas, markers.")
    print("  No field carries a sample rate or a root key in absolute units, which is")
    print("  what the format doc states as well: the PCM is recorded at a FIXED base")
    print("  rate and the chip pitch-shifts from there.")
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))

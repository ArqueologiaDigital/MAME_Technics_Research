# Wave-ROM playback research (2026-07-11, workflow wf_44d926b3-dd3) — decode + tone tables + donors

Three-agent research grounding the "better placeholder wave ROM" (Felipe's request).

## 1. THE WAVE SELECT (runtime, CONFIRMED by chromatic sweep)
No wave start/loop/length addresses EVER cross the CPU->TG bus (exhaustive boot capture, 17.8k writes
all accounted for). Sample selection is the AUX WORD (reg 0x1C02+ch*0x10, already captured as m_aux):
  bits 7:0  = key-zone / sample index (piecewise-constant across the keybed; steps exactly where the
              pitch base resets -- 12/12 chromatic checks)
  bits13:12 = sample-bank extension (disambiguates e.g. piano G3 0x200D vs organ C4 0xB00D)
  bit 15    = gate-follow flag (envelope work)
Pitch (0x2400/01) = 17-bit ZONE-RELATIVE log pitch, exactly 0x400/semitone within a zone; per-zone
base carries the root offset (incl. piano stretch tune). The TG dereferences an IN-ROM directory
(KN5000-style) -- format unknown, NOT needed for MAME (we key playback on (bank,zone) directly).
The 0x80xx quad = per-channel output/mixer record (REFUTED as wave address; boot writes defaults to
all 64 ch; hi bytes invariant across sounds). Channel decode: addr = group|ch(6 bits, 64 ch)|reg --
the old "16 blocks" reading is dead; RUN3 allocated ch 0x00..0x19 sequentially.
Observed (bank,zone) anchors -- DISJOINT across all families even ignoring the TG index:
  bank2 09-17 piano-L1 (C2..C7) | bank0 1D-2B piano-L2, 23 | bank0 04 world | bank0 38 synth |
  bank0 72-77 strings | bank0 7E pad | bank1 0C-22 brass(+sax 16) | bank1 31-52 guitar |
  bank1 61 sax | bank3 00 sax | bank3 0D-0F organ | bank3 16/18 bass | bank3 39 mallet | bank3 66 pad
Raw data: /tmp/wr_run1..4.txt + analyzers in the session scratchpad.

## 2. TONE TABLES (JK chunk, table ROM 0x4806EA98)
1139 named sound records ([16B name][hdr 0x54][1-5 layers x 0x7A]); per-layer WAVE SELECTOR u16 at
layer+0x04/05 {group,sub} (Concert Grand = "Grand Piano L"/"Grand Piano R"); 856-entry NAMED physical
wave table at JK+0x1B8EF (name + u24 + u24 W={bank 0-0x14,group,idx}); 1055 distinct layer wave refs.
Register data is GENERATED from compact layer bytes (pan=(b<<8) etc.); the EG septet + 0x80xx quad
exist NOWHERE verbatim in ROM. Runtime (bank2bit,zone8) <-> table W mapping goes through the unknown
in-ROM directory; for MAME we use runtime anchors (above) and can extend by capturing more sounds.

## 3. DONORS (KN5000 IC307 -- the only GENUINE dump)
tools/extract_kn5000_waves.py extracts 186 unique waves (3.99MB PCM, 198 index entries, entry 0 =
bit-perfect 256-sample sine) with zones/loopflags/pitch manifest. ★ PROVENANCE FLAG: the ic304/305/306
files in kn5000_original_roms/kn5000/ are NOT dumps -- they are the KN5000 project's own synthetic
sine/saw/triangle banks (kn5000-docs/tone-generator.md line 372 confirms NO_DUMP); only IC307
(CRC32 20ff4629) is genuine. Recommend renaming that directory's synthetic files (Felipe's call).
Donor classification (acoustic): piano w69/w64/w182-184; organ w11-33 drawbar families; strings
w75-77/w121/w130-132; brass w40-53; sax/woodwind w82-97; flute w62-63; guitar/pluck w99-101/114-119/
133-135; bass w165; mallet w74/58-61; pads w47/76/77/122; drums w153-181.

## 4. THE PLAN (v1, implemented)
tools/make_wave_pack.py + tools/wave_pack_map.json: (bank,zone-range)->donor entries from the anchors
-> kn7000_waves_synthetic.rom (16MB, magic KN7WVSY2, directory + 44.1k s16 PCM with baked crossfaded
loops, provenance block). Driver: optional ROM region "wavepack"; kn7000_tonegen looks up (bank,zone)
from m_aux at note-on and plays the donor sample (linear interp, loop, step=freq/root) instead of
sin(); sine fallback for unmapped zones / missing pack. Envelope/life-cycle machinery unchanged on top.

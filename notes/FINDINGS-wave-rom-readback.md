# Can the machine be made to read out its own wave ROMs?

Question (Felipe, 2026-08-27): *could a custom DSP program be crafted to return raw
sample ROM data to the maincpu or subcpu, so the wave ROMs can be dumped and saved
elsewhere (floppy, MIDI SysEx, anything)?* Asked for **WSA1R** and **KN5000**.
Follow-up: *can the envelope be configured to be neutral, output identical to input?*

Short answer: **not via the DSP, on either machine — ESTABLISHED from the schematics.**
The DSPs are physically not on the wave ROM bus. The only candidate is the tone
generator, and there is one specific lead there worth testing.

## Evidence

Read directly off the service-manual sheets. Both manuals are pure scans with no text
layer — render with `pdftoppm -r 300 -png` (or open the page in a PDF-capable reader);
do not trust the OCR text for wiring.

* **WSA1R**, `KN7000/service_manual/SX-WSA1R Service Manual.pdf`
  PDF page 18 = BLOCK Diagram, sheets II-5/II-6.
* **KN5000**, `technics-docs/service_manual/technics_sx-kn5000.pdf`
  PDF page 34 = `TONE GENERATOR SECTION (A)`, sheets II-15/II-16;
  PDF page 35 = `TONE GENERATOR SECTION (B)`, sheets II-17/II-18;
  PDF page 33 = `CPU SECTION (B)`, sheets II-13/II-14.

| | WSA1R | KN5000 |
|---|---|---|
| wave ROM | IC43, IC44, IC45, IC47, IC48, IC49 — 6 x **16 Mbit** = **12 MB** | IC304 `QSIGU3C32375`, IC305 `QSIGU3C32374`, IC306 `QSIGT3C32A01`, IC307 `QSIGX3C32008` — 4 x **32 Mbit** = **16 MB** |
| owns the ROM bus | **IC4 `TC183C230002` Tone Generator LSI** | **IC303 `TC183C230002` Tone Generator LSI** |
| ROM addressing | `A0~A19` from IC4; data `D0~D15` back to IC4 | TWO 21-bit buses: `ADY0~ADY20`->`AY0~AY20` (IC304, IC306) and `ADX0~ADX20`->`AX0~AX20` (IC305, IC307); per-ROM enables `NOEX0..NOEX3`; shared `RD0~RD15` return |
| DSPs | IC5, IC8, IC30 | IC311 `D6383GF-3BA`, IC310 `MN19413` |
| DSP audio I/O | serial: `SDO1~SDO3`, `SDO6,SDOA,SDOB,SDIB` | serial: `SDIA`, `SDIB`, `SDOA`, `SDOB`, `BCK`, `LRCK` |
| DSP memory | private DRAM IC51, IC61 (`A0~A7`) | private DRAM IC309 4 Mbit (`DSP1A0..A8`), IC308 1 Mbit (`DSP2A0..A8`) |
| DSP host port | — | `DSP1 D0-D7` + `DSPWR`/`DSPRD`/`DSPCS`/`DSPCD`/`DSPRDY` from IC27 TMP94C241F (sheet II-13); DSP2 is serial `DSP2CS`/`DSP2SCK`/`DSP2DA` |

**Every DSP address line terminates in that DSP's own delay RAM.** No DSP has a wire to
any waveform ROM. A custom microprogram therefore cannot read the samples: it receives
audio the TG has *already* fetched, pitch-interpolated and enveloped, so even a perfect
capture of its input is a RECONSTRUCTION, not a dump. Grade: **ESTABLISHED**.

## Where the real lead is

1. **The two machines share the tone generator.** `TC183C230002` is IC4 on the WSA1R and
   IC303 on the KN5000. Panasonic's service-parts catalogue independently cross-references
   that part number to `SXKN3000`, `SXKN5000`, `SXWSA1`, `SXWSA1R` — so one readback
   mechanism, if it exists, would cover four instruments.

2. WARNING: **the KN7000 result does NOT transfer.** The KN7000's proven wave-read port
   (main `0x9804` / sub `0x9805`) belongs to a *different* tone generator — the KN7000 uses
   two `C1BB00000709` (IC201/IC205), the KN6000/KN6500 one NEC `D82398GD001` (IC213). Do
   not reason from either to the KN5000's TC183C230002.

3. **IC303 has what look like external-access pins.** Along its bottom edge, adjacent to
   the CPU address lines `SA2-SA8`, sheets II-15/II-16 show **`EXADL1`..`EXADL7`,
   `EXADA0`..`EXADA4`, and `EXRW`** — plausibly "external address" plus an external
   read/write strobe. Grade: **INFERRED FROM PIN NAMES ONLY.** Not traced; no firmware
   touching them has been found. This is the thing to test.

4. WARNING: **re-test, do not inherit, the standing claim** that the KN5000 has no
   equivalent of the KN7000 wave-read port. It is not currently known whether that was
   *positively tested* or merely *not found* — very different things. The `EXAD`/`EXRW`
   pins are a reason to look again.

The CPU-side interface to the TG is `SD0-SD15` with only **`SA2-SA9`** — eight address
lines, i.e. a register window, not the ROM address space. Any readback must therefore be a
register protocol (load an address, strobe, read a data register), not a memory window.

## The strongest negative we have

The WSA1R's service-mode **"Wave ROM check" is NOT a checksum** — it is a listening test.
Entered by holding number-pad `3` at power-on; covers MAIN IC43-45, 47-49:

> "When set to the self-diagnostic mode, the Wave ROM outputs a sine wave... When a button
> is pressed, the corresponding sine wave sound is produced. **If no sound is produced, or
> if the sound is distorted, the Wave ROM corresponding to that button is defective.**"

Technics checksums the program ROMs and RAM, but for the wave ROMs fell back on a
*subjective human audio test*. That is what you do when the CPU cannot read those bytes.
Grade: **ESTABLISHED** (`wsa1r_service_manual_ocr.txt:864-879`).

## Can the envelope be made neutral? (follow-up question)

Yes, almost certainly — and it is the **easiest** obstacle in the chain, not the decisive
one. Bit-exactness requires *every* stage to be exactly unity, not approximately:

| stage | neutral setting | risk |
|---|---|---|
| envelope | max sustain, no attack/decay | a log/dB EG has an exact 0 dB; a linear multiplier whose max is `0x7F/0x80` is **0.99219**, not 1 |
| pitch / phase increment | exactly 1.0 — the sample's own root pitch, no detune, no LFO | at fractional phase 0 a linear interpolator returns the sample untouched; any other increment resamples |
| velocity / part level / master volume | all unity | each is another multiply that can land one LSB short |
| pan | hard-pan so one channel is unity | centre is usually -3 dB |
| voice mixing | exactly one voice sounding | mix buses often scale for headroom |
| DSP effects | bypassed | on the WSA1R the DSP is *always* in the path |

That last row is the one place a custom DSP program IS the right tool — not as a ROM
reader, but as a **bit-transparent pass-through**, far easier to write and to verify.

### The point that decides it

**Even a perfectly neutral chain yields decoded audio, not ROM bytes.** If the waveform
ROMs hold anything other than linear PCM — ADPCM, companded, differential,
block-floating-point, all common in mid-90s tone generators fitting large sample sets into
32 Mbit — the TG decodes on the way out and no neutrality inverts that. The result would
be a faithful **sample set**, which has real preservation value, but it is NOT a ROM image
and must never be labelled as one (see the cross-model ROM integrity rule).

So the gating question is: **what format is in those ROMs?** `RD0~RD15` being 16 bits wide
is at least consistent with linear PCM, but that is not evidence of it.

## Exfiltration is not the bottleneck

MIDI SysEx at 31250 baud: 10 bits/byte -> 3125 B/s raw; SysEx payload must be 7-bit,
costing 1/8, leaving **~2734 data bytes/s**.

* KN5000, 16 MB: 16777216 / 2734 ~= 6137 s ~= **1.7 hours**, unattended.
* WSA1R, 12 MB: ~1.3 hours.
* Floppy instead: 1.44 MB/disk -> 12 disks (KN5000), 9 (WSA1R).

KN5000 MIDI implementation chart (sheet I-26) confirms `System Exclusive: O`.
**The read path is the entire problem; getting the bytes out is easy.**

Capture can also be *digital*, avoiding any ADC: the **SY-ES1 Output Expansion Board**
gives the WSA1/WSA1R a coaxial S/PDIF out at 44.1 kHz / 20 bits carrying the main pair
(see `technics-docs/wsa1.md`). The KN5000 equivalent is `DO3`, but our notes place that on
the HD-AE5000 extension rather than the main mix, so it needs that board.

## The test that should come first

Play back a region of **IC307** — the one genuinely hardware-rooted dump we hold — through
the neutralised chain and compare the captured samples against the known ROM bytes.

* match bit-for-bit -> the chain is proven transparent AND the storage proven linear, in
  one measurement;
* mismatch -> the difference characterises what the TG does.

It is a test that can actually fail, against ground truth already in hand. Run it before
any attempt on IC304-306.

## The route that needs no firmware trick

IC307 was dumped by somebody — that is precisely how we know IC304-306 in the tree are
duplicates of it rather than genuine dumps. Whatever method produced IC307 applies to the
other three, and to the WSA1R's six, and depends on no undiscovered port.

## What a next pass should do

1. Trace `EXADL*` / `EXADA*` / `EXRW` on sheets II-15/II-16 to their destinations.
2. Look up the EG's numeric range in our own KN5000 tone-generator model — the emulator
   already implements EG/pitch/velocity, so whether its maximum is *exactly* unity is
   answerable from our source and decides row 1 of the table above.
3. Search both firmwares for TG-register writes matching an address-load-then-read
   pattern, and for any wave-ROM checksum.
4. Only then consider whether a TG readback is worth modelling in MAME.

---
*Written 2026-08-27. Sources are the two service manuals cited above, read as page images.
Kept on branch `notes/wave-rom-readback`; nothing here is implemented in the driver.*

# r4-capture-side — making the capture chain, not the software, do the work

Everything here is measured on the two artefacts we actually have:
`KN7000/photos/1st-frame-grabbed.png` (composite, real instrument) and
`KN7000/photos/dump-via-debug/photo_5170298038159870981_y.jpg` (phone photo of the same
page 0x48000000, the source of the committed transcription), with a clean emulator frame
(`/tmp/dg_cap1/frames/0002.png`, 640×240 framebuffer) as the ceiling reference.

## For Felipe

**`FELIPE-CAPTURE-INSTRUCTIONS.md`** — the whole answer in operator form: grabber settings,
the PAL/NTSC test, why there is no better connector, and a numbered ~15-minute calibration
session that produces 4 × 256 known bytes plus an optically-clean paired photo of the same
screen at the same moment.

**`capture_probe.sh`** — run once, sends back everything the grabber can do.
**`capture_raw.sh`** — captures with no preview, no scaler, no filter, no chroma loss.

## The scoring harness

**`score_capture.py`** — the deliverable that makes every future capture-side change an
A/B instead of an opinion. It never decodes bytes; it measures how much of the screen's own
structure survived, in units of *native LCD pixels*, so captures at different resolutions
compare directly.

    python3 score_capture.py FRAME.png
    python3 score_capture.py --dir frames/            # adds temporal noise + drift
    python3 score_capture.py --video clip.mkv --frames 60

Measured today, same screen, three paths:

| | sampling (px per native px) | V edge rise | H edge rise | MTF 3 px | MTF 2 px | noise floor |
|---|---|---|---|---|---|---|
| emulator framebuffer (ceiling) | 0.99 × 1.01 | 0.62 | — | **3.255** | above Nyquist | 0.000 |
| real composite capture | 1.61 × 2.06 | 0.93 | 1.68 | **0.245** | **0.008** | 0.015 |

The composite path keeps **7.5 %** of the 3-native-pixel contrast and **0.008** at the
2-native-pixel period — *below its own 0.015 noise floor*, i.e. the intra-glyph stroke
information is absent, not merely attenuated. That single number is why the capture end
matters more than the decoder end.

## The measurement scripts behind the numbers

| script | what it establishes |
|---|---|
| `measure_psf.py` | edge rises, chroma-vs-luma bandwidth, flat-field noise, interlace parity, the horizontal spectrum in MHz |
| `mtf_compare.py` | relative MTF of composite vs phone photo, on the *same* printed text (the address ladder), so the content divides out |
| `chroma_channel.py` | whether the aqua/yellow/lime/fuchsia highlight channel survives — it does not appear at all in the hex area of this frame |
| `measure_grid.py` | noise autocorrelation and an 8×8 JPEG-blocking test, i.e. what the unknown preview scaler did |
| `which_page.py`, `which_page2.py` | two attempts to identify the displayed page from the frame alone, both **inconclusive** — kept because the negative result is the point: 512 character votes and a self-calibrated per-glyph ink model both fail on this frame |

## Firmware findings that answer "does the mode change anything else?"

* `PAL_VDOUT` / `NTSC_VDOUT` are entries in the GUI descriptor table at `0x487539D0`
  (screen `VideoOutScr`, handler `0x48517EA8`).
* The CUSTOMIZE handler at `0x48516841` stores `value & 1` as a u16 at **`0x500D35B2`**.
* Library routine **`0x4C024218`** copies exactly **2 bytes** from `0x500D35B2` to the
  LCD-controller register **`0x96804A9E`**; `0x4C024514` reads it back and verifies.
* Every other reference to `0x500D35B2` in the image is UI or the defaults table
  (`0x4858D6FC`, 26 words; the video-out word is index 23, factory default `0x0001`).
* Service-mode `TestVideoOutFunc` (`0x484A1895`) does the same one-bit write.

So the setting is **one bit in one register**. Nothing else in the firmware differs
between PAL and NTSC.

## Hardware findings from the schematic (`photos/kn7000-video-out-circuit.png`)

IC104 **`C0HBA0000117` (COLOR LCD CONTROLLER)** is the video encoder. Composite leaves the
**GREEN** DAC (pin 115), through Q101 (2SD601AQTX) as an emitter follower, R114 150 Ω,
L101 ferrite and D101/D102 clamps, to the VIDEO OUT jack — **no low-pass filter in the
instrument**, so the band-limiting is inside IC104 and inside the capture device.
**RED (112), BLUE (117), HRTC (119) and VRTC (120) are not connected**: the chip has an
RGB-plus-separate-sync capability that this instrument does not use and the firmware never
enables. The user manual's connector list confirms VIDEO OUT is the only video connector.

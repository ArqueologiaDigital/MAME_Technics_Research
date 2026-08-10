# KN7000 dump-screen capture — what to do at the instrument

Everything here is a *test with a number attached*. After each capture, run

    python3 score_capture.py --video CLIP.mkv --frames 60 --label "what you changed"

and keep the printout next to the clip. That turns "does PAL help?" into a table.

---

## 0. The one change that matters most, before anything else

The frame we have (`photos/1st-frame-grabbed.png`) is a **gnome-screenshot of a preview
window** — the PNG says so in its own metadata (`Software: gnome-screenshot`), and 1055×533
is not a video size. So between the grabber and the file there was a video player's scaler
and the desktop compositor, and we cannot tell what they did.

**Never capture by screenshotting a preview again.** Use `capture_raw.sh`, which writes
what the device delivers straight to a lossless file with no filter in the chain. This
costs nothing and removes an uncontrolled variable from every measurement below.

---

## 1. Tell us what the grabber actually is (2 minutes, do this first)

1. Connect the grabber, switch the KN7000 on, leave it on any screen.
2. Run `./capture_probe.sh` and send back the `grabber-probe-*.txt` it writes.

That file names the decoder chip, lists every resolution and pixel format the device
offers, and lists its picture controls. The settings in §2 are the *defaults we
recommend*; the probe output is what lets us tell you if your device can do better.

---

## 2. Grabber settings — use these unless the probe says otherwise

| setting | use | why |
|---|---|---|
| resolution | **720×480** (NTSC) / **720×576** (PAL) | The KN7000 paints 640 pixels across the active line. At 720 samples you get **1.10 samples per KN7000 pixel** — barely above Nyquist. At 640×480 you get **1.00**, i.e. exactly Nyquist, and 1-pixel glyph strokes alias. 720 is not a preference, it is the minimum. |
| pixel format | **YUYV / UYVY (4:2:2)** | Full-rate luma. The glyphs are luma. |
| **not** MJPEG | avoid | JPEG throws away exactly the high-frequency luma we need. The tool's own damage study measured JPEG blocking as the worst of the eight damage axes at equal severity. |
| container | **FFV1 in .mkv** for calibration clips; H.264 `-crf 16` for long production sweeps | lossless while we are still measuring; ~1–5 GB per 4 MB chip once we are just dumping. |
| pixel layout | `yuv422p` | never let ffmpeg convert to `yuv420p` on the way in. |
| sharpness | **0** | edge enhancement adds ringing that changes the glyph shapes non-linearly. |
| noise reduction / "3D denoise" | **off** | temporal denoise smears a page across a page flip. |
| deinterlace | **off** — no `yadif`, no `bwdif`, no player "deinterlacer" | the source is a static picture; any deinterlacer either halves the vertical detail or invents it. |
| any scaling filter | **none** | we rescale later, in a tool that knows the screen's geometry. |
| brightness / contrast | leave at default, then check | if `score_capture.py` reports clipping-looking numbers, or the luma histogram piles up at 0 or 255, back the contrast off. Clipped whites destroy the edge measurement. |

If the device offers a **field mode** (`720×240`, or `v4l2-ctl --set-fmt-video=...,field=alternate`),
capture one clip that way as well and label it. It is a diagnostic, not an expected win —
see §3.

---

## 3. PAL vs NTSC — worth ten minutes, but not for the reason you would expect

**What the firmware does.** The whole "Video Out Mode" setting is **one bit**. Traced in
the ROM: the CUSTOMIZE handler at `0x48516841` stores `value & 1` as a 16-bit word at
`0x500D35B2`, and library routine `0x4C024218` copies exactly **2 bytes** from there to the
LCD-controller register at **`0x96804A9E`**. Nothing else in the firmware changes: no
different framebuffer, no different font, no different pixel clock, no different scaling.
Whatever changes on the wire is the encoder chip's own response to that one bit.

**The 576-vs-480-lines argument does not apply here.** The KN7000's screen is **240 lines**.
NTSC already gives it two scanlines per LCD line, and measurement confirms the vertical axis
is not the problem: on the real frame the vertical 10–90 % edge rise is **0.93 native LCD
pixels** — individual LCD lines are fully resolved — while the horizontal rise is **1.7**
(mean of the panel's left and right edges; individual edges measure 1.1–2.3).
PAL's extra 96 lines cannot add information a 240-line source does not have.

**The real reason to try PAL is horizontal.** A composite decoder has to notch the colour
subcarrier out of luma. NTSC puts that subcarrier at 3.58 MHz; PAL puts it at 4.43 MHz. The
KN7000 clocks its 640 pixels out in ~52 µs, i.e. ~12.3 MHz, so the notch is what sets the
finest resolvable detail — and PAL moves it up by **24 %**. That is the whole prediction:
about a quarter more horizontal bandwidth, on the one axis that is broken.

**How to test it (the setting persists across power-off — manual p. 186):**

1. Press **CUSTOMIZE**.
2. Select **VIDEO OUT MODE SETTING**.
3. Note which option is currently lit (the factory default word in ROM is `1`, and the
   option list is *PAL* then *NTSC*, so `1` is almost certainly NTSC — consistent with what
   your capture looks like). Write down what it was.
4. Select the *other* one.
5. Set the grabber to the matching standard: `v4l2-ctl -d /dev/video0 --set-standard=PAL`
   (or `NTSC`), or `capture_raw.sh --std PAL`.
6. Capture the **same page** as before (see §5) and score it.

**Risks, all small:** the internal LCD is driven from a completely separate bus
(`FPDAT0..23` on IC104) and cannot be affected, so you can always navigate back on the
instrument's own screen even if the TV output goes black. Some cheap grabbers are NTSC-only
and will simply fail to lock — that is the answer, not a fault. PAL runs at 25 fps instead
of 30, so a held sweep gives ~9 frames per page instead of ~11.

---

## 4. Is there a better video path off the instrument? No — but there is a better *picture*

**Checked, and the answer is no.** The rear panel has exactly one video connector (the
manual's own connector list: PHONES, FOOT SW 1/2, FOOT CONTROLLER, EXP PEDAL, MAIN OUT,
SUB OUT, AUX IN, LINE IN, USB, **VIDEO OUT**, MIDI, MIC). The schematic
(`photos/kn7000-video-out-circuit.png`) shows why: composite comes from the **GREEN** DAC
(pin 115) of **IC104 `C0HBA0000117`, the colour LCD controller**, through a single
emitter-follower (Q101 2SD601AQTX) and a ferrite bead to the jack. The chip's **RED (112)**,
**BLUE (117)**, **HRTC (119)** and **VRTC (120)** pins — an RGB-with-separate-sync capability
— are **wired to nothing**. There is no S-Video and no RGB output, and the firmware never
programs the chip into any other output mode.

Two better paths exist only inside the case, and neither is a tonight job: tapping those
unused DAC/sync pins (which would also need the chip reconfigured, which the firmware never
does), or tapping the panel's own 24-bit digital `FPDAT` bus with an FPGA.

**The path that *is* available tonight is a camera pointed at the LCD**, and it is not
close. Measured on the same page 0x48000000, comparing your existing phone photo
`photos/dump-via-debug/photo_5170298038159870981_y.jpg` against the composite frame, at the
spatial frequencies that separate glyph strokes:

| detail period | composite keeps | photo keeps | photo ÷ composite |
|---|---|---|---|
| 6 native px (character pitch) | 1.000 (reference) | 1.000 (reference) | 1.0× |
| 4 native px | 0.070 | 0.322 | **4.6×** |
| 3 native px | 0.247 | 5.269 | **21×** |
| 2.5 native px | 0.019 | 0.275 | **15×** |
| 2 native px (adjacent strokes) | **0.008** | 5.198 | **>100×** |

The composite frame's own noise floor is **0.015**, so its 2-native-pixel figure of 0.008
is *below the noise*: that information is not attenuated, it is absent. A clean emulator
frame scores 3.26 at the 3-px period; the composite keeps **7 %** of that.

So please also shoot the camera captures in §5. If they score as well as the sample photo
did, the fastest route to PROGRAM 893 may be a phone on a tripod shooting 4K video of the
LCD while the orange button is held — same hands-free sweep, roughly 6 camera pixels per
LCD pixel instead of composite's 1.1 samples with the detail already filtered out.

---

## 5. ★ The calibration capture we need next

Four table pages were measured to be **byte-identical between your build 80 and our build
84**, so each one gives us **256 known bytes** to score a decoder against with no guessing:

    0x48019000    0x48039000    0x48049000    0x48159000

They are only a few button presses apart, which is why these four.

### Getting there

1. Enter the hidden viewer: hold **UP and DOWN together** on **PART MUTE / balance columns
   1, 4, 5 and 8** simultaneously. The **MEMORY DUMP** screen appears.
2. The address is dialled on the **eight balance rocker columns**, one hex digit each,
   **column 1 = most significant**. Press **UP** on a column to increment that digit,
   **DOWN** to decrement.
3. Dial `4 8 0 1 9 0 0 0` — i.e. column 1 → `4`, column 2 → `8`, column 3 → `0`,
   column 4 → `1`, column 5 → `9`, columns 6, 7, 8 → `0`.
   Confirm on the footer: **`DUMP ADR0 = 48019000`**.

### The captures (about 15 minutes total)

Start `capture_raw.sh --out ~/kn7000-cal --secs 15 --stills 4` before each one, and give
each clip the name in bold.

4. **`cal-48019000-ntsc`** — sit on `0x48019000` and *do not touch anything* for 15 s.
   Do not hold the page button: we want ~450 frames of one settled page, which is what
   lets us measure the temporal noise, whether frame-averaging can also buy resolution,
   and whether the tool's page-agreement logic behaves on real video.
5. **`cal-48039000-ntsc`** — press **MUTE UP 4** twice (`48019000` → `48029000` →
   `48039000`). Check the footer reads `48039000`. Capture 15 s.
6. **`cal-48049000-ntsc`** — press **MUTE UP 4** once more. Capture 15 s.
7. **`cal-48159000-ntsc`** — press **MUTE UP 3** once (`48049000` → `48149000`), then
   **MUTE UP 4** once (`48149000` → `48159000`). Check the footer. Capture 15 s.
8. **`cal-hold-rate`** — from wherever you are, start recording, hold **MUTE UP 6** for a
   full 10 s, release, stop. This measures the real page-advance rate and the real number
   of frames per page on hardware; the 5.2 pages/s figure we plan with is an emulator
   number and has never been checked against the instrument.

### ★ The paired photo — the single most valuable item in the list

9. Go back to `0x48019000`. **Without touching the instrument again**, and while the
   grabber is still recording, take a phone photo of the LCD:
   * whole screen in frame, including the coloured legend strip at the bottom of the panel
     and the four/eight rocker graphics — we need the full 640×240, not a crop;
   * as square-on as you can manage, phone roughly level with the middle of the screen;
   * tap to focus on the panel and **lock focus and exposure** (long-press on most phones);
   * highest resolution the camera offers, no zoom, no flash, no "HDR"/"AI scene" mode;
   * room lights arranged so there is no reflection across the panel.
   Name it `cal-48019000-photo.jpg`. Repeat for one more of the four pages.

   This gives us, for the *same* screen at the *same* moment: a composite clip and an
   optical ground truth. It settles page identity, it calibrates the composite decoder
   against a readable rendering of the identical pixels, and it tells us whether the camera
   route is worth pursuing for the real 4 MB sweeps.

10. **`cal-48019000-pal`** — now do §3: switch **CUSTOMIZE → VIDEO OUT MODE SETTING** to
    the other standard, set the grabber to match, return to `0x48019000` (the address slots
    survive leaving the screen, until power-off) and capture 15 s.

11. Finally, one settings A/B on whichever standard scored better: capture the same page
    again with **sharpness at its maximum** instead of 0, named `cal-48019000-sharp`. If
    sharpening turns out to help the decoder rather than hurt it, that is worth knowing and
    costs one clip.

### What to send back

The `.mkv` clips, the two photos, the `grabber-probe-*.txt`, and the `score_capture.py`
printout for each clip.

---

## 6. One thing we noticed and cannot resolve from here

In `photos/1st-frame-grabbed.png` the hex area has **zero colour anywhere** — the peak
saturation over all sixteen text rows is 4.9, against 136 on the legend strip — yet the
committed photo transcription of page `0x48000000` has two bytes equal to `F0`, which the
viewer paints on an **aqua** background, and the phone photo of that page plainly shows them.

So either that frame is not page `0x48000000`, or one of the four highlight values had been
stepped away from its default with the rocker columns 10–13. When you do §5, please leave
the four highlight values alone, and mention it if you have ever changed them. The paired
photo in step 9 settles this permanently.

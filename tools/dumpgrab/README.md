# dumpgrab — read KN7000 ROM back out of its MEMORY DUMP screen

The KN7000's service firmware has a hidden hex viewer (`DbMemoryDumpProc` @ `0x484878AC`,
opened with the 1/4/5/8 UP+DOWN chord). It prints 256 bytes of any CPU address as 16 rows
of 16 hex bytes, **each row labelled with its own full 32-bit address**, and the panel's
orange page rocker (PART MUTE UP 6) steps `+0x100` and auto-repeats when held. Point the
rear composite VIDEO OUT at a capture card, hold the button, and the instrument reads its
own flash out loud. This tool turns that video back into bytes.

The intended use is Felipe's undumped **PROGRAM 893** ROM, for which no oracle exists —
which is why nothing here needs one: the atlas can be built from the screen itself, and
every result is gated on redundancy the screen carries (the 16-row address ladder, the
colour legend), not on knowing the answer.

## What it does

    dumpgrab.py image  FRAME.png [FRAME.png ...]   one still, or a handful
    dumpgrab.py frames DIR/                        a directory of stills
    dumpgrab.py video  FILE.avi | /dev/videoN      a recording, or a live grabber
    dumpgrab.py agree  --dir RUN1 --dir RUN2       keep only what two sweeps agree on
    dumpgrab.py validate --dir OUT --oracle ROM    score the result against a known ROM

All three capture modes write the same thing into `--out`:

| file | meaning |
|---|---|
| `<prefix>_<START>_<LEN>.bin` | the bytes; one file per contiguous recovered run |
| `<prefix>_<START>_<LEN>.mask` | 1 byte per byte: `0` = never recovered, `N` = N frame votes |
| `<prefix>_manifest.json` | runs, holes, conflicts, the fill byte |
| `<prefix>_coverage.txt` | human-readable coverage and the holes to re-sweep |
| `<prefix>_report.json` | frame / tear / vote statistics, plus the oracle score if given |

**A hole is never quietly filled.** An unrecovered byte is `0` in the mask and the fill
byte in the `.bin`. A gap can be re-swept in thirty seconds; an invented byte can never be
found again.

## Dependencies

`python3`, `numpy`, `Pillow`. The `ffmpeg` binary for video/V4L2 mode only.
**No OpenCV** — it is not installed on this machine and nothing here needs it; frames come
out of ffmpeg as a rawvideo pipe, which is also how a capture card is read.

## Exact commands

Capture a sweep in the emulator (the harness that produced every number below):

    tools/dumpgrab/capture/capture.sh --out /tmp/dg_cap1 \
        --start 0x48400000 --pages 40 --mode hold --snap all --movie avi \
        --predelay 300 --timeout 1500

(`--predelay` is not cosmetic: the viewer's idle repaint period is ~2.95 s, so recording
immediately after the address is dialled catches the start page half painted.)

Extract from the frames it wrote, scoring against the real ROM:

    python3 tools/dumpgrab/dumpgrab.py frames /tmp/dg_cap1/frames \
        --out /tmp/dg_out_frames \
        --oracle /home/fsanches/compartilhado/kn7000-emulator/roms/kn7000/kn7000_program.rom \
        --expect 0x48400000:0x2900

Extract from the video file instead (same options, same outputs):

    python3 tools/dumpgrab/dumpgrab.py video /tmp/dg_cap1/movie.avi \
        --out /tmp/dg_out_video \
        --oracle /home/fsanches/compartilhado/kn7000-emulator/roms/kn7000/kn7000_program.rom

One still, printed as hex with per-row confidence:

    python3 tools/dumpgrab/dumpgrab.py image /tmp/dg_cap1/frames/0100.png --out /tmp/dg_one

Score an output directory afterwards (byte accuracy, per page, glyph confusion matrix,
and a whole-page byte-shift diagnosis that separates a mis-framed grid from a misread
glyph):

    python3 tools/dumpgrab/dumpgrab.py validate --dir /tmp/dg_out_frames \
        --oracle /home/fsanches/compartilhado/kn7000-emulator/roms/kn7000/kn7000_program.rom

Two sweeps of the same range, keeping only what they agree on (this is the verification
when there is no oracle — i.e. on PROGRAM 893):

    python3 tools/dumpgrab/dumpgrab.py agree --dir /tmp/dg_out_pass1 --dir /tmp/dg_out_pass2 \
        --out /tmp/dg_merged

Live from a grabber, when one exists (untested — there is no capture hardware here yet):

    python3 tools/dumpgrab/dumpgrab.py video /dev/video0 --out /tmp/dg_live -- --size 720x480

Anything `dumpgrab.py` does not recognise is passed through to the pipeline CLI
(`python3 -m kn7000videograb --help`): `--vote-mode`, `--tear-policy`, `--min-posterior`,
`--base-continuity`, `--dedup`, `--max-votes-per-page`, …

## MEASURED ACCURACY

Everything below was measured on this machine on 2026-08-09 by the commands above, against
`kn7000-emulator/roms/kn7000/kn7000_program.rom` byte for byte. **These are emulator
numbers.** MAME hands the extractor a pixel-exact framebuffer, so they measure the
extractor and the voter, *not* an analog capture chain — see “What is still unknown”.

### End to end, a 40-page hold sweep

| run | range | source | frames | pages | bytes known | wrong | **byte accuracy** | perfect pages |
|---|---|---|---|---|---|---|---|---|
| capture 3, `video` | 0x48400000 | `movie.avi` | 828 | 41 | 10,496 (100 % of the sweep) | 14 | **99.866616 %** | 40 / 41 |
| capture 1, `video` | 0x48400000 | `movie.avi` | 555 | 41 | 10,495 | 16 | **99.847546 %** | 40 / 41 |
| capture 1, `frames` | 0x48400000 | 1,108 PNGs | 1,108 | 41 | 10,495 | 16 | **99.847546 %** | 40 / 41 |
| capture 2, `video` | 0x48410000 | `movie.avi` | 822 | 41 | 10,491 | 63 | **99.399485 %** | 38 / 41 |
| one still, `image` | 0x48736300 | 1 PNG | 1 | 1 | 256 | 0 | **100.000000 %** | 1 / 1 |

Each sweep is 40 pages held on the orange button. Captures 1 and 3 are two independent passes
over the *same* address range, which is what makes the `agree` test below meaningful. The video
and frames modes of capture 1 produced **byte-identical** results through two completely
different input paths (ffmpeg rawvideo pipe vs Pillow), which is the cross-check that says the
readers agree.

**Where the wrong bytes are.** Never spread out: 40 of 41 pages come out 256/256, and all the
errors sit on one or three pages per sweep. Two distinct causes, and the second is the
interesting one:

1. *A page that was never shown settled.* The auto-repeat interval dips to 8 frames while the
   16-row repaint needs ~7 frames plus latency, so occasionally a page is stepped past before it
   is finished. The same happens to the start page if recording begins before the post-dial
   repaint completes — `capture.sh --predelay` (default 5 s) fixes *that*, though on these runs it
   bought a correctly painted start page and no accuracy: capture 3 waited the full 5 s and still
   returned 14 wrong bytes there, which is cause 2 below, not cause 1.
2. ★ *A page the extractor simply reads wrong, every time.* On capture 2's page `0x48412600`,
   three pixel-identical, fully settled frames (16/16 rows on the ladder, zero low-confidence
   cells) each decode **24 bytes wrong** — `0`→`3`, `F`→`A`, `C`→`D` in the right-hand columns,
   `0`→`C`, `8`→`B` in the bottom rows. This is a sub-pixel grid residual in the bottom-right of
   the hex area biting on exactly the glyph pairs that differ by one column of pixels. It is
   **deterministic**, so cross-frame voting cannot touch it, and it recurs across independent
   sweeps: `agree` over captures 1 and 3 dropped only **2** conflicting bytes and left 14 of the
   16 errors in place, because both passes made the same mistake on the same page.

    python3 dumpgrab.py agree --dir /tmp/dg_v_cap1 --dir /tmp/dg_v_cap3 --out /tmp/dg_merged
    -> agreed bytes 10,493   conflicts dropped 2   accuracy 99.8666 %

So: **two passes catch the timing-dependent errors and nothing else.** The remaining class needs
an independent encoding of the same byte — the ASCII column the viewer already prints to the
right of the hex — or a grid-refinement stage scored on classification confidence over the DATA
cells rather than on structure. Neither is implemented. This is the single most valuable next
piece of work on this tool, and it is why the honest number above is 99.87 % and not 100 %.

### Throughput and cost

* extraction ≈ **0.5 frames/s** per core with three other jobs on the box (~2 s/frame
  uncontended); a 40-page sweep of 555 frames takes ~17 min to extract
* the sweep itself: **5.17-5.21 pages/s**, i.e. ~53 min of held button per 4 MB chip
* ⚠ **RECORD UNCOMPRESSED IF YOU POSSIBLY CAN.** Measured: cross-frame voting on H.264-medium
  plateaus at **97.7 %** byte-exact no matter how many frames vote, while the same pipeline on
  uncompressed video reaches **99.8 %** — lossy compression destroys glyph detail in a way
  voting cannot recover. Uncompressed AVI is 460,800 B/frame (~84 GB for a full 4 MB sweep), so
  if that is impossible, prefer a *lossless* codec (FFV1, MNG, or one PNG per page ≈ 208 MB)
  over H.264/MJPEG. `doc/STRATEGY.md` has the measured bitrates.

### Simulated composite damage (a PREDICTION, not a measurement of the real chain)

Six clean pages, each degraded three times with an independent 0.5 px capture jitter and pushed
through the whole shipped pipeline (`predict/degrade_shipped.py`):

| axis | severity | physical unit | bytes emitted | accuracy |
|---|---|---|---|---|
| (control) | 0 | jitter only | 1,279 | 99.7654 % |
| blur_horizontal | 0.2 | luma sigma 0.50 px | 1,024 | 99.1211 % |
| blur_horizontal | 0.3 | luma sigma 0.75 px | 511 | 99.8043 % |
| blur_horizontal | 0.5 | luma sigma 1.25 px | 0 | — (refused everything) |
| interlace | 0.1 | field shear 0.30 px | 1,022 | 99.3151 % |
| interlace | ≥0.2 | field shear ≥0.60 px | 0 | — (refused everything) |
| noise_gaussian | 0.5 | sigma 20 of 255 | 1,023 | 99.9022 % |
| jpeg_blocking | 0.3 | JPEG q=69 | 1,023 | 98.7292 % |
| jpeg_blocking | 0.5 | JPEG q=52 | 768 | 98.6979 % |
| composite_chain | ≥0.1 | joint | 0 | — (refused everything) |

Read the *coverage* column as much as the accuracy column: as damage rises the tool refuses more
frames and emits fewer bytes rather than emitting wrong ones. Horizontal luma bandwidth and
sub-pixel field shear are what kill a 5×7 font with 1-px strokes; additive noise is nearly free.
Even the control is not 100 %: half a pixel of sampling jitter, with no other damage, costs about
3 bytes in 1,280.

**These curves are a simulation whose fidelity is unverified**, and two of its axes are documented
as misbehaving (`composite_ntsc` is non-monotone; `resample` applies its resampling twice). Their
only honest use is after the first real capture: dump a page the ROM covers, score it, and see
where it lands.

## How it is put together

    dumpgrab.py          the single entry point: image / frames / video / agree / validate
    agree.py             two-pass agreement -- the verification when there is no oracle
    kn7000dump/          single-frame extractor — geometry fit, glyph OCR, confidence
    kn7000videograb/     frame sources, tear detection, cross-frame voting, assembly
                         (also carries `reference_extractor.py`, an independent stand-in
                          reachable with `--extractor reference` -- useful as a second
                          opinion, not the shipped path)
    adapter.py           the glue: kn7000dump -> the pipeline's frame contract
    validate.py          scoring against a known ROM (+ dumpfmt.py, pages_to_sparse.py)
    photofit.py          EXPERIMENTAL pitch search for hand-held photos (does not work yet)
    capture/             the MAME harness + the Lua measurement rigs
    predict/             composite-video degradation simulator: what to expect on real video
    doc/STRATEGY.md      what to dump, in what order, how long each chip takes, and why
    doc/GEOMETRY.txt     the screen's character layout and the two MAME capture traps

### The extractor (`kn7000dump`)

Nothing is hardcoded to a capture resolution. The ink map is a local-background ratio (so
an LCD backlight gradient does not become ink), the row comb is fitted on the *horizontal
gradient* (so the panel's own solid border, which has ink but no horizontal structure,
cannot be mistaken for a text row), the column fit is a matched filter against the known
75-character row layout, and each character cell is re-centred on its own ink before it is
cut. OCR is template matching against an 18-class atlas.

Two redundancies are exploited, both free:

* **the address ladder** — the 16 row addresses must ascend by exactly `0x10`, so the base
  address is a 16-way vote and a disagreeing row localises a failure to that row;
* **the colour legend** — the viewer highlights cells whose value equals one of four
  legend bytes, and the legend is *read off the screen*, not assumed, because those bytes
  can be stepped from the panel at runtime.

### The voter (`kn7000videograb`)

Frames stream in, torn frames are detected and split per row, and every page is voted
across the frames that saw it with a Bayesian log-likelihood weighted by the extractor's
per-cell confidence. A sweep-continuity guard rejects a page address the sweep cannot
currently be at, which is what stops a systematically misread address digit from filing a
whole page at an address that was never visited.

### The gate that makes the numbers meaningful

`adapter.py` refuses any frame whose own printed addresses do not hang together — at least
12 of the 16 rows must agree on one page base (counting a two-base split one page apart,
which is what a mid-repaint frame looks like) — and zeroes its confidences so a caller that
ignores the refusal still cannot be poisoned. This matters because a misplaced grid produces
*confident nonsense*: on a badly framed corpus 26 % of the bytes above confidence 0.9 were
wrong. **Gate on the grid, weight by confidence, abstain per cell.**

Three calibration decisions here are measured, not guessed, and each cost a full re-run:

* **Do not gate on `kn7000dump.PageResult.ok`.** It additionally demands that all 256 cells
  be readable, which is a fine test for "is this frame settled" and a terrible voter gate:
  it threw away 192 of 555 frames and lost page `0x48400000` entirely, where letting the one
  unreadable cell abstain recovers the other 255 bytes.
* **A frame that is not fully settled votes at half weight** (`UNSETTLED_DISCOUNT`). Measured
  effect on the 555-frame sweep: 214 wrong bytes at full weight, 201 at 0.5, 200 at 0.15 —
  i.e. small, because the errors live on pages that *only* unsettled frames ever saw and
  there is nothing to out-vote them. Kept at 0.5 as the cheap half of the defence; the other
  half is `agree`.
* **A claimed tear must be exactly one page wide.** Accepting any multiple of 0x100 let a few
  misread address digits file 196 bytes at `0x48402B00`, three pages past where the sweep ever
  went: 185 of that run's 201 wrong bytes were that one fabricated page. The button steps one
  page and the repaint is shorter than a page period, so nothing else is physically possible.

## What is still unknown

* **Analog tearing is UNASSESSED.** MAME emits pixel-exact frames, so nothing here has
  ever seen a real analog capture: no field interlace, no chroma smear, no scaler ringing,
  no dropped frame. The *firmware's* own non-atomic repaint is measured (below) and
  handled; the capture chain's behaviour is not. The synthetic degradation curve in
  `predict/` is a prediction, and its fidelity is unverified.
* **Phone photos do not work.** Both photos tried from `KN7000/photos/dump-via-debug` are
  refused outright and emit zero bytes — which is the right answer, not a bug. The geometry
  stage misestimates the character pitch by a few percent, and a few percent is three
  characters of drift by the right end of a 75-character row; the address column cannot see
  it, because it sits at the left where the drift has not accumulated. `photofit.py` measures
  how far a global pitch search gets: on one photo from mean confidence 0.078 and no usable
  bytes to 0.509 and 130 of 256 bytes correct, on the other nothing at all. The rest needs a
  four-corner homography, not a better 1-D search.
* **The ASCII column is not read.** The viewer prints each byte a second time as ASCII, a
  fully independent encoding at a different screen position. It is the one defence against
  the systematic glyph errors that cross-frame voting, posterior gating *and two independent
  sweeps* all fail to catch (measured above). Not implemented; it is the next piece of work.
* **There is no checksum anywhere in the loop.** The service ROM test reports PASS/FAIL,
  not a value. Verification of a dump with no oracle must come from two opposite-direction
  sweeps agreeing byte for byte.

## Provenance

Assembled from five parallel work packages (capture harness, extractor, video pipeline,
validation/degradation study, endgame strategy) into one tool, then re-measured end to end
by the integrator with the commands printed above. The side-quest write-up is
`KN7000/side-quests/findings/kn7000_dump_roms_via_debug_screen_in_video_grabber_findings.md`.

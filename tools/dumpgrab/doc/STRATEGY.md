# c5-endgame — can the debug screen actually archive a ROM?

Package: `c5-endgame`. Deliverable: strategy, not code (the two Lua measurement
rigs under `tools/` are the evidence for the numbers below, not the product).

Everything numeric here is either **measured** in the emulator (provenance stated
per number) or **read out of the firmware bytes**. Nothing is inferred from how
the screen "probably" behaves.

---

## 0. The four answers in one paragraph

A full 4 MB sweep takes **52 minutes** of holding one button (measured 5.2
pages/s), and every page is displayed for **11 video frames, 6 of which are
pixel-identical** — so a 30 fps capture is guaranteed at least two clean frames
per page and tearing costs nothing. The address is a **plain 32-bit counter with
carry and no region logic at all**: it never wraps, never stops, never notices a
chip boundary, so a sweep covers a range contiguously and needs no re-dialling —
but nothing stops it at the top either. Six chips are reachable this way,
including **two that have never been dumped by anyone** (picture flash, rhythm
flash) and **two small holes in dumps we already own that cost 28 s and 70 s**.
The wave ROMs are **not** reachable — they sit behind a TG page/offset/data port,
not in the CPU address space — and neither is any sub-processor's internal
firmware; those still need a clip-on reader or a custom service routine.

---

## (a) Coverage arithmetic

### Measured page-advance rate

Rig: `tools/measure_sweep_rate.lua` — opens the viewer with the 1/4/5/8 chord,
parks `ADR0` (`0x500012EC`) at `0x48400000`, presses and **holds** `MUTE UP 6`
(`CPC_SEG8` bit 0x40 — the `0x100` digit, one screenful per repeat), and logs the
address once per emulated video frame.

| run | hold | address travelled | pages | rate |
|---|---|---|---|---|
| 30 s hold | 30.02 s | `0x48400000` → `0x48409D00` | 157 | **5.24 pages/s** (191 ms/page) |
| 14 s hold | 14.02 s | `0x48400000` → `0x48404900` | 73 | **5.21 pages/s** (192 ms/page) |
| 5 s hold  |  5.02 s | `0x48400000` → `0x48401F00` | 31 | 6.18 pages/s (best case, no stalls) |

Use **5.2 pages/s** for planning. Provenance: MAME, `MN10300(config, m_maincpu,
16_MHz_XTAL * 2)` = 32 MHz, our `kn7000` driver. **Re-measure on hardware before
committing to a session plan** — see the 60-second protocol in §(d).

Where the 191 ms goes (rig `tools/measure_repaint.lua`, read taps on the first
and last word of the displayed page):

* one full repaint = **112 ms** of CPU work (row 0 first read → row 15 last read),
  16 rows × (1 `sprintf` + `DrawString` for the address + 16 × (`sprintf` +
  `MT_GetColor` + `DrawString`) + 16 ASCII glyphs);
* the auto-repeat timer is **3 app-ticks** — `EV_AUTOINC` handler `0x48417390`
  re-arms `SetApTimer(3, …)` at `0x484173CD` before re-sending the button event
  (first repeat after `0x10` ticks, armed by `SetAutoInc 0x4841773B`);
* the idle repaint timer is `0x78` ticks and the measured idle period is
  **2952 ms** (8 consecutive repaints, 2840.0–2840.9 ms apart plus the 112 ms
  repaint) ⇒ **1 app-tick ≈ 23.7 ms** in emulation.

So the sweep is **repaint-bound, not timer-bound**. That matters: the timer part
is firmware-fixed and will be identical on hardware, the 112 ms part is CPU
throughput and is exactly the piece MAME may get wrong.

### Frame cadence — does every page land as a clean frame?

Rig: 14 s of the sweep recorded with `-aviwrite`, cropped to the LCD, per-scanline
diff of 120 consecutive frames (`run/frames/`). The pattern is exactly periodic:

```
5 frames in transition   (redraw front sweeping top→bottom)
6 frames pixel-identical (settled)
--------------------------------
11 frames = 183 ms per page @ 60 Hz
```

* **54 % of frames are fully settled**, in one contiguous run of ~100 ms per page.
* A 29.97 fps capture samples every 33.4 ms ⇒ **≥ 2 settled frames per page,
  guaranteed** (⌊92 ms / 33.4 ms⌋ = 2 using the pessimistic 5.5-frame settled
  window). PAL 25 fps: ⌊92/40⌋ = 2. Field-rate capture (59.94/50) is better still.
* Transition frames are **not merely torn — they contain superimposed glyphs**
  (a mid-repaint frame shows old and new hex digits overlapping in the rows being
  redrawn; see `run/tear035.png`). The extractor must **reject** them, not try to
  read them. The cheap, robust rejection test: accept a frame only if it agrees
  with the next captured frame (under analog noise: agrees *after classification*).
* Because the renderer prints `"%04X%04X  "` **per row** (`0x48487B37`, address =
  `ADR + row*16`), every row is self-addressing. A page is therefore never
  "missed" in a way that costs alignment — worst case it is simply not yet
  collected, and the next pass fills it.

### Video volume, at composite resolution

Measured by encoding the recorded sweep scaled to 720×480 / 29.97 fps, video only,
with synthetic grain standing in for analog noise (`noise=alls=N:allf=t+u`), then
scaling to one 4 MB sweep (3129 s):

| container | bitrate | size per 4 MB sweep |
|---|---|---|
| raw YUY2 720×480 @29.97 (arithmetic, exact) | 165.7 Mbit/s | **64.8 GB** |
| MJPEG q3, clean → σ14 noise (what cheap UVC grabbers emit) | 17.3 → 33.6 Mbit/s | **6.8 → 13.1 GB** |
| H.264 crf18, clean | 0.78 Mbit/s | **0.30 GB** |
| H.264 crf18, σ6 noise | 1.62 Mbit/s | **0.63 GB** |
| H.264 crf18, σ14 noise | 12.4 Mbit/s | **4.9 GB** |
| FFV1 lossless, σ14 noise | 413 Mbit/s | 162 GB — **do not** |

**Recommendation:** capture whatever the grabber natively emits (usually MJPEG or
YUY2) and transcode to H.264 `-crf 16` immediately after, or record straight to
H.264 `-crf 16` if the machine keeps up. Budget **1–5 GB per 4 MB chip**. Do
*not* try lossless: analog noise makes it 30× bigger for zero decode benefit,
because the decoder is a 16-class template matcher, not an archival copy of the
video.

### One sitting or many?

| target | pages | sweep time |
|---|---|---|
| program-flash hole (`0x487F6F00`+) | 145 | **28 s** |
| table-flash hole (`0x483E9400`+) | 364 | **70 s** |
| one full 4 MB chip | 16,384 | **52 min** |
| one full 8 MB chip | 32,768 | **105 min** |

Two full chips (PROGRAM 893 + TABLE 80) = **1 h 45 min** of held button; adding
the picture and rhythm flashes takes it to **3.5–4.5 h**. That is many sittings —
and it does not have to be one, because **the method is restartable and
order-free**: each row carries its own address, so coverage is a *set of row
addresses*, any sitting contributes whatever it contributes, and gaps are
re-swept later. Plan it as: two 1-minute runs for the holes first (they are the
highest value per minute in the whole project), then one chip per sitting.

Practical: 52 minutes is too long for a finger. Wedge/tape the `MUTE UP 6` cap
down, and put the capture on a machine with the disk space checked *first*.

---

## (b) Address discipline — answered from the code, not from behaviour

Source: `kn7000_disassembly/disasm/debugger_memdump.asm`, handler
`DbMemDumpEvIndexSw` at `0x48487E60`, and the renderer `DbMemDumpMtParaDraw` at
`0x48487A58`.

**The step is a plain 32-bit add on the whole address.**

```
48487e66: mov a2,d0 ; asl2 d0 ; mov 1,d3 ; asl d0,d3     ; d3 = 1 << (4*i)
  DOWN:  48487e86: sub d3,d1   ; mov d1,(d0,a0)          ; ADR[slot] -= step
  UP:    48487e9e: add d3,d0   ; mov d0,(d1,a0)          ; ADR[slot] += step
```

There is **no per-digit modulo, no page register, no bank field**. Carry
propagates out of the `0x100` digit into every higher digit, which is exactly why
holding `UP 6` walks `…FF00 → …0000` of the next 4 KB, then the next 64 KB, then
the next megabyte, without the operator touching anything.

**The only bound in the whole handler:**

```
48487ea6: cmp 0xc0000000, d0
48487eac: bcs 0x48487ebb          ; addr <u 0xC0000000 -> leave alone
48487eb3: and 0x0fffffff, d0      ; else fold into 0x0xxxxxxx
```

So:

* **It does not wrap at a region boundary.** It does not know what a region is.
* **It does not stop at the top of a chip.** `0x487FFF00 + 0x100 = 0x48800000`
  and the sweep carries straight on into whatever the bus decodes next. What you
  see there is the bus's business, not the viewer's — mirrors, open bus, or the
  next device.
* **It rolls over only at `0xC0000000`**, and then to `0x0FFFFFFF`-masked. From
  `0x48400000` that is 1.87 GB / 7.85 M pages / **17.5 days** of holding away:
  operationally unreachable. Sweeping *down* past `0x00000000` folds to
  `0x0FFFFF00`.
* The renderer applies the same guard per row (`48487B1E: cmp 0xbffffff0, a2`),
  so a displayed row address is always the true address of the 16 bytes on it.

**Consequence for the operator: a sweep can be trusted to cover a range
contiguously.** You dial the start address once (8 rocker columns, one hex digit
each, column 1 = most significant) and hold. You never re-dial mid-range. You
*do* have to stop it yourself — watch the footer `DUMP ADR0 = %04X%04X` and
release at the end address.

Three more facts that matter operationally, all from the same listing:

* **Four independent address slots** (`ADR0..3` at `0x500012EC/F0/F4/F8`, selected
  by column 15). Park a different sweep in each — e.g. ADR0 = program flash,
  ADR1 = table flash — and switch between them without re-dialling.
* **The slots persist.** `EV_SHOW` only writes the defaults while the cold flag at
  `0x50001304` is non-zero and clears it on first open, so leaving the screen and
  coming back resumes where you were (until power-off).
* **The viewer is strictly read-only.** Every store in the whole window proc goes
  to the stack frame or to its own five state cells; the inspected address is only
  ever `movbu (dN,a2),dM`. Sweeping cannot corrupt anything — but *reading* can,
  if the address is an I/O window (see §(d)).
* Measured, not inferred: the screen did **not** self-dismiss during ≥25 s idle or
  ≥30 s with a button held. A 52-minute hold has **not** been tested; do a 5-minute
  hold on hardware before committing to a full sweep.

---

## (c) Which ranges matter

Sizes/offsets computed from the two oracle files: `kn7000_program.rom` =
`0x3F6F01` bytes (covers `0x48400000`–`0x487F6F00`), `kn7000_table.rom` =
`0x3E94D4` bytes (covers `0x48000000`–`0x483E94D3`).

| # | target | CPU range | size | pages | sweep | reachable? | priority |
|---|---|---|---|---|---|---|---|
| 1 | **program-flash top hole** — the on-board FLASH UPDATER, absent from every update disk | `0x487F6F00`–`0x487FFFFF` | 37,119 B | 145 | **28 s** | ✅ plain loads | **1 — best value/minute in the project** |
| 2 | **table-flash top hole** | `0x483E9400`–`0x483FFFFF` | 92,972 B | 364 | **70 s** | ✅ | **1** |
| 3 | **PROGRAM 893** (his build; ours is 941) | `0x48400000`–`0x487FFFFF` | 4 MB | 16,384 | 52 min | ✅ | **1 — unarchived firmware** |
| 4 | **TABLE 80** (his build; ours is 84) | `0x48000000`–`0x483FFFFF` | 4 MB | 16,384 | 52 min | ✅ | **1** |
| 5 | **picture flash** — never dumped by anyone | `0x57800000`–? | ? (4–8 MB) | ? | 52–105 min | ✅ (firmware dereferences the u32 at `0x57800000` for the PICTURE version, `AcAromVerBoxProc 0x48488A0B`) | **2** |
| 6 | **rhythm flash** — never dumped by anyone | base + 0–0x3FFFFF, base ∈ {`0x40000000`, `0x40600000`, `0x40800000`, `0x54E00000`} | 4 MB | 16,384 | 52 min | ✅ once located | **2** |
| 7 | factory-data flash / custom-data flash (IC18) — *existence disputed*, see below | `0x57000000`, `0x56000000` | ? | 1 page to settle | seconds | ✅ probe | 3 |
| 8 | custom flash IC21 (his registrations) | read view `0x56000000` per docs; ⛔ command view `0x96800000` | 2 MB | 8,192 | 26 min | ✅ read view only | 3 |
| 9 | **wave ROMs** IC203/204/207/208 | *not in the CPU map* | 32–64 MB | — | — | ❌ **no** | see §(d) |
| 10 | library/kernel `0x4C000000` | RAM, self-loaded from program flash at boot | 253 KB | — | — | ✅ but pointless | — |
| 11 | sub-CPU / panel MCU / USB co-processor firmware | not in the CPU map | — | — | — | ❌ | see §(d) |

### Locating the rhythm flash — a concrete 5-dial procedure

The firmware's own locator is at `0x4843D6DC`: it `strncmp`s the string
`"Technics Rhythms"` (at `0x4872980C`) against **base + 0x10000** for each
candidate, in this order:

```
0x48010000   0x40610000   0x40010000   0x54E10000   0x40810000   (fallback 0x54E00000)
```

The RHYTHM version stamp is at **base + 0x3FFFEC** (`0x14` below the top of a
4 MB span), which is what fixes the device size at 4 MB.

So: dial each of those five addresses and look at the ASCII column. The one that
reads `Technics Rhythms` is the base. (Our `kn7000_table.rom` does *not* carry the
signature at `0x10000`, so the first candidate is not the answer on a stock unit;
the signature does appear at table offset `0x3E828C`, which is a different, name-table
use of the same string — do not confuse them.)

### The disputed windows are settled by this very screen

`notes/rom-backup-and-update-format.md` §5.1 lists custom-data flash at
`0x56000000` and factory-data flash at `0x57000000`; the driver comment in
`kn7000.cpp` says `0x56000000`/`0x57000000` are two of the four EXP.CS *expansion
slot* windows and models them as open bus. **One page-dial each, on real hardware,
decides it** — real data or `00`/`FF` fill. That reframes the whole exercise: this
viewer is not only a dumper, it is a **memory-map probe**, and each unresolved
window costs one dial and one screenshot.

### Surveying trick

Column 6 steps `0x100` (one page). Column 5 steps `0x1000` — sixteen pages per
repeat, ~83 pages/s. Useless for dumping (it skips 15 of every 16 pages) but ideal
for **finding the extent of a device**: hold column 5 until the content turns to
fill bytes, and you have the chip's top in under a minute instead of 52.

---

## (d) The honest limit

**What this method cannot do.**

1. **It can only see what a plain load can see.** The wave ROMs are the clearest
   case: they hang off the tone generators' 80-pin wave bus and the CPU reaches
   them only through a page/offset/data window — write `0x8000|page` to
   `0x98040006`, write `0x8000|offset` to `0x98040008`, read `0x9804000A` (sub TG:
   `0x98050006/8/A`). The hex viewer does exactly one thing, `movbu (dN,a2),dM`
   from a static address; it cannot drive a protocol. Worse, parking it on
   `0x9804xxxx` would *repeatedly read TG registers* — a live hazard, not a dump.
   Same verdict for anything behind a bank register: **the viewer shows whichever
   bank is currently selected and gives you no way to change it.**
2. **It cannot see any other processor's memory.** The panel/key sub-CPU, the
   USB co-processor (IC407/IC408, entirely undumped), and any internal mask ROM
   are not in the MN10300 address space. No chord reaches them.
3. **Throughput is 1.4 kB/s.** 256 bytes per 183 ms. Even if the wave ROMs *were*
   reachable, 64 MB would be 14 hours of held button and ~400 GB of MJPEG.
4. **There is no error detection in the loop.** Nothing on screen is a checksum
   of anything. A single mis-classified glyph in 4 MB produces a wrong byte that
   nothing flags. The mitigations, in order of strength:
   * **Two passes in opposite directions.** `DOWN 6` sweeps backwards through the
     same range with a different frame phase and different tearing alignment.
     Require byte-for-byte agreement; disagreements localise to specific rows,
     which are then re-swept (cheap — you re-sweep pages, not the chip).
   * **Per-byte majority vote** across the ~3 settled frames each page gets, after
     frame-averaging within the settled run (the image is static for ~100 ms, so
     averaging 2–3 frames is a free 2–3 dB against analog noise).
   * **Cross-check 893 against 941.** They are builds of the same firmware; large
     data regions will be identical. Isolated single-byte differences inside
     otherwise-identical runs are the signature of a decode error, not of a build
     difference. This is the strongest residual-error detector available and it
     costs nothing.
   * **Structural validation.** The image must disassemble cleanly as MN10300,
     the boot header at `0x48400000` must have the documented shape, the version
     cell must read 893, the MILK symbol/name tables must be well formed.
   * The factory service menu does contain a program-ROM test
     (`MainRomTestFunc 0x4849FDF8`, reached by the power-on note combo), but the
     workers it calls compare accumulators against each other and report
     PASS/FAIL — **I did not find a displayed checksum number**, and the two
     candidate constant tables at `0x4860C9A0/A8` read as zeros in our image.
     Treat "the service ROM test can verify a video dump" as **unproven**; it is
     worth one photo from the service menu to settle.
   * The `SMCKPRn.INF` oracle (32-bit total sum + 16 × 256 KB block sums) verifies
     only images we already have a matching update disk for — i.e. 941, not 893.
5. **The analog path is the accuracy floor, and it is untested.** Glyphs are 6 px
   wide on a 640-px line; at NTSC 720-sample capture that is ~6 samples per glyph,
   and a cheap grabber's ~3.5–4.5 MHz luma bandwidth resolves roughly 5 of them.
   Template matching over 16 classes should cope — that is what packages c2–c4
   measure against the oracle — but chroma will smear (the colour legend is a
   *redundancy*, never the primary read), and TV-style overscan cropping in the
   capture app would silently eat the leftmost address digits. Verify the full
   640-px width is captured before the first long run.
6. **Read side effects.** Because the address is a free-running counter, the
   danger is *dialling*, not sweeping (from `0x48400000` you would need 274 hours
   of holding to reach `0x96800000`). Never dial into: `0x96800000` (custom-flash
   command window — the viewer re-reads its parked address forever),
   `0x98000000–0x9807FFFF` (TG/FDC), `0x9C000000` (DSP port), `0x9CC00008` (SD),
   `0x20000000`/`0x34000000` (CPU internal I/O incl. the MIDI transmitter).
7. **Unverified on hardware: everything about the rate.** MAME's MN10300 core
   timing is approximate and the repaint is 112 ms of *CPU work*. If the real
   instrument repaints in 50 ms the sweep is ~2× faster and the settled window
   shrinks to ~50 ms — still ≥1 clean frame at 30 fps, but the margin is gone and
   a 60-field/s capture becomes mandatory.

**The 60-second hardware protocol** (do this first, before anything else):
open the viewer, dial `ADR0 = 0x48400000`, start a stopwatch, hold `MUTE UP 6`
for exactly 60 s, release, read the footer address. `(addr − 0x48400000) / 0x100 /
60` = pages/s on real hardware. Multiply the tables in §(a) by `5.2 / that`.
While there, confirm on a TV that the MEMORY DUMP screen actually appears on
VIDEO OUT (the manual says "the image of the display" is output, and the SOFT
VERSION chord is already confirmed working on his unit, so this is a two-minute
check) and try both NTSC and PAL from CUSTOMIZE → VIDEO OUT MODE SETTING —
NTSC's 240 active lines map 1:1 to the 240-line LCD, PAL's 288 do not, so NTSC is
the likely winner but it costs nothing to compare crispness.

**Where a clip-on reader is still required:** the four wave mask ROMs
(IC203 `C3CBQD000002`, IC204 `C3CBQD000001`, IC207 `C3CBQD000004`,
IC208 `C3CBQD000003`), the USB co-processor's flash, the panel/key sub-CPU, and
any bank-switched device whose selector the running firmware controls. For those,
the realistic non-invasive alternative is not this screen but a **custom service
routine** — the firmware's own wave-ROM test already walks every bank of both TGs
through the readback window (`MainWaveRomTestFunc 0x484A2E3A`), so the same
addressing with "store" instead of "add to checksum" dumps the wave set to SD.
That is a different project with a different risk profile (it requires getting
code to run on the instrument), and it is the honest answer to "why not just use
the debug screen for everything".

---

## What the extractor must do (requirements falling out of the above, for c2/c3/c4)

1. **Key every row by its own printed 32-bit address.** Never by frame order,
   never by page index. This makes the whole pipeline restartable, order-free and
   immune to dropped frames.
2. **Reject transition frames.** They contain *superimposed* glyphs, not merely
   stale rows. Accept a frame only when it agrees with its successor (post-
   classification agreement under noise). Expect to keep ~54 % of frames.
3. **Average the settled run before classifying** — 2–3 frames of the same static
   image, free SNR.
4. **Majority-vote per byte cell** across all accepted frames carrying the same
   row address, and emit a **per-byte confidence**, so the coverage report is
   "N bytes decoded, M bytes unanimous, K bytes contested" rather than a single
   accuracy number.
5. **Emit a coverage/gap report keyed by address**, so the operator knows exactly
   which pages to re-sweep.
6. Use the colour legend (Aqua=F0, Yellow=F7, Lime=FF, Fuchsia=XX) only as a
   **cross-check** on the luma decode, never as the primary read — composite
   chroma bandwidth is ~1/8 of luma.

---

## Files

* `tools/measure_sweep_rate.lua` — chord → park → hold `MUTE UP 6` → per-frame
  address log. Env `HOLD_SECONDS` (default 30).
* `tools/measure_repaint.lua`, `tools/measure_repaint_idle.lua` — read taps on the
  first/last word of the displayed page; yields repaint duration and idle period.
* `run/stderr.log`, `run/stderr2.log`, `run/stderr3.log` — the raw measurement logs.
* `run/frames/`, `run/tear035.png`, `run/lcd40_big.png` — the frame-cadence and
  tearing evidence.
* `run/n{0,6,14}.mp4` — the H.264 bitrate measurements (σ = 0, 6, 14 grain).
  The MJPEG variants and the 6.3 GB `-aviwrite` source were measured and then
  deleted; their sizes are in the table above and the commands are in this file's
  history (`ffmpeg -ss 31 -t 14 -i sweep.avi -an -vf scale=720:480,fps=29.97[,noise=alls=N:allf=t+u] …`).

All MAME runs were `timeout`-wrapped, `DISPLAY=:0`, visible video, with private
`-cfg_directory`/`-nvram_directory` per run.

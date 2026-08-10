# kn7000live — read the KN7000's MEMORY DUMP screen from a live camera

Point a camera at the instrument's screen, open the hidden MEMORY DUMP viewer, and
sweep the pages. The tool reads the hex off the screen in real time, draws what it has
understood on top of the picture, and commits a byte only once several independent frames
agree on it. Committed bytes turn green and are never read again. A page is finished when
the whole block is green; a sweep is finished when the coverage bar stops moving.

**This is not a chip dump and must never be presented as one.** It is a transcription of
what the instrument prints on its own screen. It exists because Felipe's KN7000 runs
PROGRAM build 893 / TABLE build 80, a firmware pair that exists nowhere else — the
archived images are 941 / 84 — and the machine's own hex viewer is the only way to read it
without desoldering the flash.

---

## Why a live tool rather than a better batch decoder

The batch extractor (`../kn7000dump/`) reaches 99.87 % byte accuracy on emulator frames and
**refuses every real capture**. That refusal is correct, and the reason is worth stating
because it shapes everything here.

The blind grid fit assumes the panel fills the frame. It does, on a 640×240 framebuffer.
On a photograph of an instrument it does not, and the fit has plenty of other
regularly-spaced dark structure to lock onto — measured, it lands off the text on both the
composite grabber frames and the phone photos, and every byte downstream is noise. Worse,
the hex area's ink/ink/space column pattern repeats every three characters, so the
objective is nearly degenerate under a three-character shift.

A live tool does not have to solve that, because it has an operator who can see the screen
and drag four corners onto the text. What the software then owes the operator is
**feedback**: honest numbers, updated continuously, that say whether moving the camera is
helping. Everything in the HUD exists to be optimised by hand.

There is also a hardware reason to prefer a camera over the video-out socket. The composite
path keeps **0.8 % contrast at the two-native-pixel period, below its own 1.5 % noise
floor** — the strokes that distinguish one glyph from another are absent from the signal,
not merely dim, and no decoder can recover them. A camera aimed at the LCD skips that chain
entirely. The font is 5×7 pixels, so what matters is simply how many camera pixels land on
each character.

---

## Quick start

    python3 -m kn7000live devices                       # what can we capture from?
    python3 -m kn7000live live --source v4l2:/dev/video0 --store ~/kn7000-dump \
                               --seed-address 48019000

1. On the instrument, hold **UP+DOWN of mixer columns 1, 4, 5 and 8** together to reach the
   MEMORY DUMP screen, and dial an address.
2. Frame the screen so the hex table fills as much of the picture as possible. **Aim for the
   57-character block to span at least ~500 px** of the frame (9 px per character was
   measured to still work; 12 is comfortable). **Brace the camera if you can** — resting it
   on something is worth more than any setting, because heavy hand movement is one of the
   conditions under which the tool stops committing anything at all.
3. Press **SPACE** to freeze, drag the four corner handles onto the character block — from
   the top-left of the first address digit to the bottom-right of the last hex digit — and
   press SPACE again.
4. Watch the HUD. When TEMPLATES reads 16/16 and ADDRESS LADDER reads 16/16, bytes start
   going green.
5. Press **PART MUTE UP 6** on the instrument to advance a page and keep going. Nothing is
   lost when the page changes.

⚠ **Tap the page button, do not hold it.** A page needs roughly **two to three seconds** to
fill: the decoder runs at about 20 fps, a byte needs four independent frames, and the first
few frames after a page change go on re-settling the fit. Holding the rocker auto-repeats at
about **5.4 pages per second**, which is some fifty times too fast — the sweep would look
busy and commit almost nothing. Watch the page block go green before advancing.

`--seed-address` is worth giving: it tells the tool which page is on screen, which labels
all eight address digits instead of two and trains the templates about eight times faster.
It is only needed once, at the start.

---

## What is on screen

| colour | meaning |
|---|---|
| **green** | committed to the store — will not be read again |
| **amber** | evidence accumulating, not yet enough to commit |
| **red** | nothing legible yet |
| **magenta** | a committed byte was later disputed — needs a human |
| **blue** | the address column, whose correct content is known in advance |

| HUD line | what to do about it |
|---|---|
| TEMPLATES *n*/16 | learning; if it sticks below 16, the picture is not legible enough |
| separation | how distinguishable the 16 templates are. Below ~0.05, some digit pairs are physically indistinguishable at this resolution — move closer or focus |
| match margin | how decisively cells are matching. This is the number to optimise by hand |
| ADDRESS LADDER *n*/16 | the self-check. Below 14, nothing is committed |
| motion | frame-to-frame movement, in cells. Over the gate, voting pauses (blurred frames are excluded, not averaged in) |
| conflicts | committed bytes later contradicted — investigate before trusting the store |

Keys: `h` for the full list. `SPACE` freeze, `1`–`4` pick a corner, arrows nudge, `a`
auto-seed, `r` re-acquire, `x` forget this page, `s` save now.

---

## Why you can trust what turns green

Several independent things have to agree before a byte is committed.

**The screen checks itself.** Row *r* of a page shows the address `base + 0x10*r`, so the
sixteen row addresses must ascend by exactly 0x10. A registration that has slipped by one
character, a frame smeared by hand shake, a half-drawn repaint — all of them break that
arithmetic. It cannot be satisfied by accident and it needs no reference copy of the ROM,
which matters because for build 893 no reference copy exists.

**And the far end is checked separately.** The address column is the leftmost eighth of the
block, so the ladder proves only where each row *starts*. A character pitch that is slightly
wrong is invisible at column 0 and half a glyph out by column 56 — so a frame may only vote
if the match strength across a spread of far-right columns also clears a threshold.

**Several frames must agree.** A value is committed only when its total evidence clears a
threshold, comes from at least four *distinct* frames, and holds at least 85 % of the vote.
Frames are counted rather than observations, because thirty readings of one badly-focused
frame are one piece of evidence.

**The screen states some bytes twice.** The viewer's footer legend reads
"Aqua = F0  Yellow = F7  Lime = FF  Fuchsia = XX", and it draws every byte equal to one of
those values on a coloured background. That is an independent statement of the byte's value
in a channel the glyph classifier cannot influence — and it lands exactly where the glyph
channel is weakest. **A page of erased flash is one long run of `FF`**, which is both a run
of identical characters (where local misalignment is invisible) and a rare glyph class
(`F`, whose template gets the least training). Measured, without this check the tool read a
blank page as 88 bytes of `EE`, confidently and consistently. The colour is used only to
**veto**: a disagreement leaves the cell unread rather than substituting the colour's
opinion. `--legend` overrides the values if you have stepped them from the panel;
`--no-colour` turns it off.

**And each byte is re-read at a displaced geometry.** Frame agreement alone is not enough,
and this is the single most important thing to understand about the tool: it defends against
*noise*, and a grid that is a fraction of a cell out of place is not noise. It yields the
same wrong answer in every frame, with a high match margin. So every byte is also read at a
deliberately jittered grid position and thrown away unless it reads the same — a glyph that
genuinely fills its cell survives that, one that is only being read correctly by luck does
not. Nothing is committed at all until the fit has been complete for several consecutive
frames, for the same reason: the reads taken while the registration is still converging are
consistently wrong rather than randomly wrong.

**Committed bytes are re-checked anyway.** Four rows per frame are re-read in full,
round-robin — four and not one, because overturning a committed byte needs four frames of
agreement, and a sixteen-frame round trip would revisit a row about three times in a normal
dwell, so the audit could never actually correct anything it found. A committed value that
accumulates real evidence for something else is recorded as a *conflict* and surfaced —
never silently overwritten. Silently preferring either answer is how a dump acquires bytes
nobody can account for.

And attribution is **per row, not per frame**: each row is filed under the address it
itself states. So a torn repaint — 29 % of frames during a sweep, measured — contributes
both of its halves to the right places instead of being discarded, and changing page loses
nothing.

**The consequence, stated plainly.** All of that adds up to a tool that commits nothing at
all unless the fit is essentially perfect. If the picture is marginal or the camera is
moving too much, the page stays red and the coverage bar does not move — the tool does not
degrade gracefully into approximate answers, because an approximate ROM dump is worse than
no ROM dump. When nothing is going green, the HUD's `status` line says which check is
failing; fix that, rather than lowering a threshold.

---

## The store

    store/meta.json      what this store is and the rules it was written under
    store/journal.jsonl  append-only: every commit and every conflict, in order
    store/snapshot.npz   the same rolled up, for fast loading
    store/bank.npz       the learned glyph templates
    store/calib.json     the last registration, so the next session starts aimed

The journal is the record; the snapshot is a cache. `rebuild` reconstructs one from the
other, so an interrupted write costs nothing.

    python3 -m kn7000live report --store ~/kn7000-dump
    python3 -m kn7000live export --store ~/kn7000-dump --window program --out build893.bin

`export` writes unknown bytes as `0xFF` **and a `.bin.mask` beside it** with a 1 for every
byte actually read. Always ship the mask: without it there is no way to tell a byte that
was read from a hole, and a 4 MB file that is mostly fill looks exactly like a dump.

---

## Measuring it

The decoder runs headless in `selftest`, against a synthetic instrument built from the real
5×7 font (`simulate.py`) — rendered, warped through a homography, blurred, noised and
shaken like a handheld camera, then decoded back to bytes that are known.

    python3 -m kn7000live selftest --source "sim:48019000,px=12,blur=1.1,shake=1.5" \
                                   --address 48019000 --frames 60

Measured over 60 frames a page, at 12 camera pixels per character, starting from a corner
placement 1.5 px out — about what an operator achieves by eye with the grid drawn on the
picture:

| condition | committed | **wrong** | of the 75 non-`0x77` cells |
|---|---|---|---|
| camera still | 228/256 | **0** | 60 |
| hand movement | 176/256 | **0** | 16 |
| hand movement, further away (9 px/char) | 176/256 | **0** | 8 |
| hand movement, 3× the sensor noise | 168/256 | **0** | 8 |
| heavier movement, or 2× the blur, or a 12° tilt | 0 | **0** | 0 |

The last row is the design working rather than failing: those conditions do not produce
wrong bytes, they produce *nothing at all*, and the HUD says which check is refusing. What
is missed is picked up by the next pass over the same page — the store accumulates, so
coverage is recoverable and correctness is not.

There is also one real page whose 256 bytes are known — table page `0x48019000`, in
`../real-NTSC-48019000.png`. ⚠ It is **71 % the single byte `0x77`**, so accuracy on it
must always be quoted twice: overall, and over the 75 cells that are not `0x77`. A decoder
that always guessed `0x77` would score 71 % and be useless. On that frame — a composite
grab, not a camera — the tool commits **0 bytes and gets 0 wrong**: it declines, which is
the correct answer for a signal that does not carry the information.

### The one failure mode that is understood and not fully solved

Testing kept turning up a single wrong byte in one particular place, and it turned out to be
structural rather than a bug. The byte was the **first of a four-byte run of `00`**,
immediately after a `70`.

Inside a run of identical characters, displacing the grid by a whole cell changes nothing —
every cell still contains the same glyph. So the jitter check, which compares a displaced
read against the base read, cannot see a misalignment there; neither can the match margin,
because each cell still matches its template perfectly. Only the *global* grid protects
those cells, and a residual sub-cell error at one end of a row can still tip the byte at a
run's boundary.

**Practical consequence: long runs of identical bytes are where an error would hide.** They
are also, fortunately, the easiest thing to check by eye against a photograph, and the place
where a second sweep is most likely to disagree.

### Verify by sweeping twice

Nothing above makes a wrong byte impossible; it makes one unlikely and, when it happens,
findable. Every commit is journalled with the evidence behind it (`w` = weight, `nf` =
distinct frames), so the weakest bytes in a store can be listed without re-running anything.

For anything that matters, **sweep the same pages twice into two separate stores and diff
the exports.** Two independent sessions have independent registrations, independent
template banks and independent frames; a byte that both agree on has far stronger backing
than the lock rule alone provides, and any byte they disagree on is exactly the byte worth
photographing by hand.

Findings that came out of that harness, kept because they are not obvious and every one of
them cost committed bytes or, worse, produced wrong ones:

* **Voting does not protect against a misplaced grid.** This is the central lesson. Agreeing
  across frames defends against *noise*; a grid that is a fraction of a cell out of place is
  not noise, it produces the *same* wrong answer in every frame with a high match margin,
  and it sails through any amount of voting. The wrongly-committed bytes had a mean
  confidence of 0.91 against 0.99 for the correct ones — far too close to separate with a
  threshold (raising it from 0.02 to 0.08 removed one wrong byte at the cost of eleven right
  ones). Two things catch it instead: a **warm-up**, so nothing is committed while the
  registration is still converging (that alone was 4 wrong bytes in a store of 247), and a
  **jitter check** — every byte is read again at a deliberately displaced geometry and
  discarded unless it reads the same. A glyph that genuinely fills its cell survives that;
  one that is only being read correctly by luck does not. Together: **zero wrong bytes**.
* **No horizontal over-cut.** The font is 5 px wide on a 6 px pitch, so widening the sample
  aperture sideways pulls in the neighbouring glyph and the template becomes a template of
  a digit *pair*. Going from a 20 % to a 0 % horizontal over-cut took committed bytes from
  217/256 to 240/256 and raised the worst-case template separation from 0.118 to 0.134. A
  little *vertical* over-cut does help, the row gap being wider.
* **Train on committed bytes — but never on ones the current frame disputes.** A page's
  addresses contain the same five or six digits over and over, so `B`, `E` and `F` arrive
  once per frame against 657 samples of `0`; their templates stay noisy and rows get
  rejected for low margin on digits that were in fact read correctly. Committed bytes fix
  that — and, done naively, introduce something far worse. **Training on the store's own
  output is a feedback loop with no brake**: a byte committed wrongly becomes a labelled
  example of the wrong glyph, the template drifts towards it, and the next page makes the
  same mistake more confidently. That is not hypothetical — it is what turned a single
  `F`/`E` confusion into an entire page of erased flash reading as `EE`. A committed byte
  may now teach only if something independent still agrees with it: the highlight colour
  where the viewer provides one, or this frame's own reading of the cell otherwise. Samples
  are also capped per class per frame, because a page that is 71 % one byte is not a
  balanced teacher either.
* **The geometry update must be monotone.** Re-solving the homography from per-glyph
  displacements is the right idea, but eight parameters fitted to a few hundred sub-pixel
  measurements are over-determined in the two projective directions. Unguarded, it walked a
  *perfectly placed* grid 11 px off the text in seven frames while every internal number
  still looked healthy. It is now a proposal that is accepted only on a strict improvement.
* **Predict the motion, do not merely correct it.** A search that only ever corrects what it
  can already see is permanently one frame behind, and its step size when it believes itself
  healthy is deliberately small — so it can lag a slow drift indefinitely while every
  candidate it tries is still an improvement. Carrying a velocity estimate took committed
  bytes under hand movement from **0 to 168**.
* **The referee cannot be the ladder alone.** The address column is the left eighth of the
  block, so it cannot see the far end sliding off — which, with a handheld camera, is
  exactly how a fit dies.
* **Do not let a crop margin decide anything.** The ink map's reference brightness was
  originally taken over the whole cropped region, which meant it depended on how much dark
  surround the crop happened to include: widening that margin from 6 % to 10 % took the tool
  from 242 committed bytes to **none at all**. It is now measured from the centre, where the
  panel certainly is.

Speed, on this machine: **48 ms/frame at 1280×720** (≈21 fps) and 74 ms at 1920×1080. Most
of it is the geometry search, which is given a cheap half-resolution scorer and only spends
its full budget when rows are actually being lost.

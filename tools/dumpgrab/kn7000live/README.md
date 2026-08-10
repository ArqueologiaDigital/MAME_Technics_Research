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
2. Frame the screen so the hex table fills as much of the picture as possible.
3. Press **SPACE** to freeze, drag the four corner handles onto the character block — from
   the top-left of the first address digit to the bottom-right of the last hex digit — and
   press SPACE again.
4. Watch the HUD. When TEMPLATES reads 16/16 and ADDRESS LADDER reads 16/16, bytes start
   going green.
5. Press **PART MUTE UP 6** on the instrument to advance a page and keep going. Nothing is
   lost when the page changes.

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

Three independent things have to agree before a byte is committed.

**The screen checks itself.** Row *r* of a page shows the address `base + 0x10*r`, so the
sixteen row addresses must ascend by exactly 0x10. A registration that has slipped by one
character, a frame smeared by hand shake, a half-drawn repaint — all of them break that
arithmetic. It cannot be satisfied by accident and it needs no reference copy of the ROM,
which matters because for build 893 no reference copy exists.

**Several frames must agree.** A value is committed only when its total evidence clears a
threshold, comes from at least four *distinct* frames, and holds at least 85 % of the vote.
Frames are counted rather than observations, because thirty readings of one badly-focused
frame are one piece of evidence.

**Committed bytes are re-checked anyway.** One row per frame is re-read in full,
round-robin. A committed value that accumulates real evidence for something else is
recorded as a *conflict* and surfaced — never silently overwritten. Silently preferring
either answer is how a dump acquires bytes nobody can account for.

And attribution is **per row, not per frame**: each row is filed under the address it
itself states. So a torn repaint — 29 % of frames during a sweep, measured — contributes
both of its halves to the right places instead of being discarded, and changing page loses
nothing.

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

There is also one real page whose 256 bytes are known — table page `0x48019000`, in
`../real-NTSC-48019000.png`. ⚠ It is **71 % the single byte `0x77`**, so accuracy on it
must always be quoted twice: overall, and over the 75 cells that are not `0x77`. A decoder
that always guessed `0x77` would score 71 % and be useless.

Findings that came out of that harness, kept because they are not obvious:

* **No horizontal over-cut.** The font is 5 px wide on a 6 px pitch, so widening the sample
  aperture sideways pulls in the neighbouring glyph and the template becomes a template of
  a digit *pair*. Going from a 20 % to a 0 % horizontal over-cut took committed bytes from
  217/256 to 240/256 and raised the worst-case template separation from 0.118 to 0.134. A
  little *vertical* over-cut does help, the row gap being wider.
* **Train on committed bytes, not just addresses.** A page's addresses contain the same
  five or six digits over and over, so `B`, `E` and `F` arrive once per frame against 657
  samples of `0`; their templates stay noisy and rows get rejected for low margin on digits
  that were in fact read correctly.
* **The geometry update must be monotone.** Re-solving the homography from per-glyph
  displacements is the right idea, but eight parameters fitted to a few hundred sub-pixel
  measurements are over-determined in the two projective directions. Unguarded, it walked a
  *perfectly placed* grid 11 px off the text in seven frames while every internal number
  still looked healthy. It is now a proposal that is accepted only on a strict improvement.
* **The referee cannot be the ladder alone.** The address column is the left eighth of the
  block, so it cannot see the far end sliding off — which, with a handheld camera, is
  exactly how a fit dies.

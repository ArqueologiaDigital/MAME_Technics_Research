# KN7000 layout positioning vs the user's mockup (2026-07-07)

The user provided a clean 2000x1500 mockup (cached at ~/.claude/image-cache/<sess>/5.png) and asked to
fine-tune element positions. Tooling built this session:
- `tools/render_lay.py` -> renders kn7000.lay to a 2000x1500 schematic in the mockup's coordinate
  system (Compact view: screen_block@(0,0), left_block@(0,997), right_block@(1000,997)).
- overlay: draw the .lay element boxes (red) over the mockup (scratchpad/overlay.png) to see offsets.

## Measured findings
- **Button CENTERS are largely aligned.** RHYTHM GROUP (16 buttons, isolated -> clean measurement):
  centroid offset median dx=-0.3, dy=-1.7 px. The top panel (LCD, flanking buttons, mute row) also
  overlays cleanly.
- **The mockup draws buttons ~5px larger** than the layout: mockup RHYTHM button diameter = ~37px vs
  the layout's round_btn 32px bounds. Uniform (all 16 within 36-37). Centers still match, so the
  layout buttons look slightly small inside the mockup circles.
- Some clusters *may* have a small local offset (the PART/GLOBAL EFFECT crop suggested my buttons sit
  up-left of the mockup circles by more than the size delta), but automated measurement there is
  UNRELIABLE: the centroid/widest-row methods get contaminated by the adjacent LED dot + label text
  (e.g. widest-row caught "8 & 16 BEAT" label as a 40px run). Needs the real artwork render to confirm.

## Blocker for pixel-precise per-cluster tuning
The MAME artwork snapshot (`-video soft` + `video:snapshot()`) HANGS in this headless env (confirmed
again this session, killed at timeout) -- so I can only compare the schematic (32px boxes), not the
real rendered buttons. Automated mockup-circle detection is defeated by nearby labels/LEDs.

## Safe next steps (not done -- avoid unverified global changes)
1. If the buttons should match the mockup size, bump round_btn draws 32->~37px keeping centers
   (P("round_btn",cx-16,cy,32,32) -> cx-18,cy-2,36,36) and re-verify no overlaps via render_lay.py.
2. Resolve the PART/GLOBAL EFFECT cluster offset once a real artwork render is available.

## RESOLUTION (2026-07-07, user provided a real emulator screenshot)
The user supplied an actual emulator render (cached .../image-cache/<sess>/6.png, 1920x1080 with the
2000x1500 Compact view letterboxed to x=240..1680). Aligning it to the mockup (crop+resize to 2000x1500,
blend) gave a RELIABLE comparison:
- **Content is positioned exactly on spec.** The RHYTHM active-style green LED in the render sits at the
  .lay LED coordinate within dy=-0.6px. So the crop is accurate and the render faithfully reflects the .lay.
- **Applied + validated the button-size fix**: round_btn 32 -> 37px (P() helper, centre preserved). The
  render buttons now match the mockup circle diameter (36.6px measured).
- Label positions differ from the mockup by only ~10px and INCONSISTENTLY in sign (OTHER PART render -13,
  CONTRAST +25) -- automated text-row detection is unreliable (font differs MAME vs mockup, catches LED/
  highlight rows). Treated as font-rendering + minor, NOT worth unverified global shifts. Iterate per-label
  with the user's screenshots if they flag specific ones.
Tooling for next time: scratchpad/blend.png = render+mockup 45% blend; render green-LED centroid vs .lay
LED pos is the clean alignment probe (content, not labels).

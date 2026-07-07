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

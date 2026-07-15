# A Design Language for Musical-Instrument Control Panels
### (extracted from the KN7000 layout work, generalised)

*Status: DESCRIPTIVE / PROVISIONAL.* This document reverse-engineers a coherent visual system out of the long
series of fine-tuning decisions made on the emulated Technics SX-KN7000 control panel. Most of those decisions
turned out to express intentions that are **not** specific to the KN7000 — they are how a *musical instrument*
control surface wants to look and behave in general, and several of them ultimately trace back to how such
panels are physically *manufactured*. So the document is split:

- **Part I — Generic.** Principles and rules that should apply to *any* keyboard/synth/arranger/workstation
  control panel (real or emulated). Hand this half to someone skinning a different instrument and it should
  still guide them.
- **Part II — KN7000 instantiation.** The concrete tokens, values and per-control assignments that realise
  Part I on this specific panel. Everything numeric or button-named lives here.

Nothing here was designed top-down; it is an *extraction* of the implicit rules behind ~30 individual
requests. Treat every rule as a hypothesis about intent — sharpen or discard freely. Where a rule is inferred
rather than stated, it is flagged.

---
---

# PART I — Generic design language (any instrument panel)

## 1. First principles

A performance instrument's front panel is a *dense, function-organised control surface* meant to be read and
operated at a glance, often mid-performance — and it is a *manufactured object*. Good panel design (physical
or emulated) follows a few intents:

1. **Function determines appearance.** A control's *role* — sound selection vs. expression vs. function
   toggle vs. transport vs. navigation — decides its material, colour and shape. Position on the board does
   not; a "voice button" looks like a voice button whether it's top-left or bottom-right.
2. **The panel is a kit of reusable parts.** Physical panels are built from a *small library of
   injection-moulded parts*, reused across many functions and differentiated cheaply by colour and printed
   legend. This manufacturing reality is the root of much of the visual grammar and gets its own section
   (§2). A faithful or convincing panel design honours it: **a reduced set of shapes, reused.**
3. **Material/finish hierarchy carries importance.** Instruments signal what's primary with *material and
   finish*: shiny/metallic for the hero selectors, brushed metal for the performance surface, matte for
   secondary functions, dark recesses for depth. A finish ladder (shinier/brighter → more primary) is a
   strong, pre-attentive organiser — and, per §2, finish is a *cheap* variation over a shared moulded shape.
4. **Consistency within a class is mandatory.** Members of the same control class share size, shape, stroke,
   and the *relative* placement of their satellites (label, indicator LED). Two buttons that do the same kind
   of thing must be visually interchangeable — because, physically, they are often the *same part* (§2).
5. **Precision over approximation.** Sizes, gaps and alignments should be *exact* and, where possible,
   expressed as a rule or formula rather than eyeballed (an enclosing ring's width = the span of what it
   encloses; sibling buttons identical; bracket lines centred on their text).
6. **Make grouping visible.** Functional groups are declared — with enclosing outlines, bracket/rule lines
   that span the group, bounding boxes, and shared alignment — never left for the user to infer.
7. **Remove non-meaningful marks.** Every stroke should mean something. Decorative doubling, leftover rings,
   and heavy contours are noise; strip them so the meaningful marks stand out.
8. **Affordance must read honestly.** Anything that looks pressable is pressable; anything decorative (a
   divider, a bracket, a bezel) is visibly *not* a control and is non-interactive.
9. **Fidelity to the instrument's real materials & conventions.** For an emulation, match the physical unit.
   For an original design, match the *conventions of the instrument class* (red = record, a big central
   data/value wheel, transport at the bottom, sound banks gridded). When a styling question is ambiguous,
   "what real instruments of this type do" is a legitimate tie-breaker.

## 2. The panel is a kit of moulded parts (the manufacturing basis)

This is the physical fact that underwrites most of the rules below, so it comes first.

Instrument panels are made largely of **injection-moulded plastic parts**. Cutting a mould (the tool) is
expensive and slow; running plastic through an existing mould is cheap. So manufacturers **amortise tooling by
reusing the same moulded part** across many functions, many positions, and often across a whole product line
and successive generations. What varies from one instance of a part to the next is *cheap* to vary:

- **Colour** — a different resin / masterbatch. Cheap. This is the primary differentiator.
- **Legend** — the printed/engraved caption (silkscreen, pad-print, laser). Cheap and per-unit.
- **Finish** — plating, coating, texture (a chrome-look button vs. a matte one) over the *same* moulded body.
- **Orientation** — the same part rotated or *mirrored*. (Left/right rocker halves are frequently one moulded
  part used both ways.)

What is *expensive* to vary is the **shape/size** — that needs a new mould. Therefore:

- **The shape vocabulary is small and reused.** A real panel has maybe a handful of distinct button/knob
  bodies; everything else is those bodies in different colours with different legends. A design that invents a
  bespoke shape for a one-off control is, in physical terms, commissioning a bespoke mould — a "smell".
- **Same part ⇒ pixel-identical.** Two controls that would share a moulded part must be *identical* in shape
  and size in the design. You cannot stretch one member of a class; there is no separate tool for it. (This is
  the physical reason behind §1.4 "consistency within a class" and rules like "all small split-pills the same
  size".)
- **Differentiate by colour and legend before inventing a shape.** New meaning should first be expressed with
  the cheap levers (colour, legend, finish, orientation) and only reluctantly with a new shape.
- **Finish is a legitimate second axis.** The *same* moulded body can appear as a bright plated "hero" part
  and as a matte "secondary" part — a precise, manufacturable way to say "same family, lesser member" without
  a new shape. (See §4/§5, the finish × shape decomposition.)

**Anatomy of a control, then, is:** *one moulded shape (from the small library)* × *colour* × *finish* ×
*legend* × *orientation*. Design and code should mirror this: **a small element library, reused** — which is
exactly what a layout generator with a handful of shared "part" definitions gives you (Part II §12).

## 3. The material / tonal hierarchy

Instrument panels tend to use **one desaturated grey scale for the bulk of controls, plus a few saturated
accents reserved for special actions.** Arrange the greys as a ladder and assign rungs to roles (all of these
are *colours/finishes applied to the shared moulded shapes of §2*):

- **Top rung — mirror/metallic (a *gradient*, not a flat tone).** The hero selectors. A gradient is what
  reads as *polished/plated metal*; keep it as the top rung even if its average lightness overlaps a flatter
  tone — finish, not hue, is doing the work.
- **Upper-middle — flat "silver".** The performance/expression surface (faders, wheels, pads, pill buttons,
  registration recall). One shared finish unifies "the things you touch while playing".
- **Middle — plain grey.** The numerous secondary function buttons. The neutral baseline.
- **Lower — dark recess.** The ring/well a raised button sits in; gives depth and frames the hero buttons.
- **Bottom — panel & structural darks.** Background, rails, engraved lines.

Rules that make the ladder work:
- **Specify tones *relatively*.** "A bit darker than the wheel, not as dark as the function buttons" is the
  natural way to place a new tone — between two existing references, not as an absolute value. Adopt this as
  the method; it keeps the ladder internally consistent as it grows.
- **Prefer the calmer of two candidate tones for the resting state.** Panels read better when the default is
  subdued and interaction/emphasis is what brightens.
- **Every interactive fill is a *pair*: a normal tone and a darker *pressed* tone.** Pressed is always a
  darkened normal (fill, recess, and any highlight all darken together). Purely decorative elements use the
  *same* fill for both states — a quiet signal that they carry no interaction.

## 4. Accent colours = special functions only

Saturated colour is a scarce resource (and, per §2, just a different resin on the same part), spent only on
actions that are conventionally colour-coded on instruments:

- **Record → red.** **Transport go/commit → green or teal.** **App-launch / load / special mode → a warm
  accent (orange/amber).**
- Everything "ordinary" stays on the grey/silver ladder.
- Push accents **darker and more muted** than a first naïve pick — instrument panels avoid bright, toy-like
  colour; the accent should read as a purposeful marker, not decoration.
- **Flip text colour for contrast on a saturated fill** (e.g. black label on a mid-saturation button).

## 5. Control taxonomy (the generic role→look map)

Most performance instruments expose the same handful of control *roles*. Map each to a rung of the hierarchy —
remembering these are finishes/colours over the shared shape kit (§2):

| Role | Typical members | Suggested treatment |
|------|-----------------|---------------------|
| **Primary sound/voice/style selectors** | banks of voice / style / tone buttons | **Top rung** — metallic/mirror, richest treatment; often gridded and the most numerous "important" buttons. |
| **Performance / expression / recall** | faders, pitch/mod & data wheels, pads, registration/memory buttons, favourites | **Silver family** — one shared finish so the eye reads them as "the surface I perform on". |
| **Function / mode toggles** | effects on/off, part select, layer/split, sequencer functions | **Plain grey**, single simplest shape. Numerous and secondary. |
| **Transport & record** | start/stop, play/pause, record, rewind/ff | **Accent pills** (green-teal / red per convention). |
| **Continuous controls** | faders, wheels, knobs | draggable, with visible travel and a clear indicator; part of the silver family. |
| **Navigation / utility** | page, exit, contrast, display hold, help, demo | plain grey; visually quietest. |

Two independent levers realise this map, and they compose (both are cheap over a shared mould, §2):
- **Finish** — mirror vs. flat vs. matte (plating/coating/resin).
- **Shape** — from the small library: e.g. recessed-with-inner-ring vs. plain single outline.

Because they're independent, you get useful in-betweens: a button with the *hero shape* but a *matte finish*
reads as "same family as the hero buttons, but a secondary member" — a precise, manufacturable way to say
"related but lesser" without inventing a new shape.

## 6. Geometry & construction rules (generic)

*Everything here presumes the reduced-parts kit of §2: define a small set of shapes and reuse them.*

- **Round buttons:** one outline by default. A *second concentric ring* is a meaningful, reserved signal
  (e.g. "this is a recessed/hero-family part") — don't spend it on ordinary buttons.
- **Size tiers, centre-preserving.** Pick a *small* set of button sizes (a real panel has few moulds) and
  stick to them. When you resize a button, keep its **centre** fixed so its label and indicator stay aligned.
- **Pills:** uniform thin stroke; **fully round ends** (corner radius = half the height). **Generate art at
  final size, never scale a small master up** — scaling distorts strokes and stretches round ends into ovals
  (and, physically, would imply a different mould).
- **Split (rocker) buttons:** two *clickable* halves + a **non-clickable divider** between them. The two
  halves are typically the *same moulded part mirrored* (§2, orientation), so draw them as mirror images. The
  divider is decorative (a seam), carries no input, and is drawn as a bordered strip — honest affordance
  (principle 8).
- **Enclosure rings hug their contents exactly:** a ring grouping N buttons has width = *button diameter* +
  *centre-to-centre span of the end buttons*, so each rounded end sits over an end button. One ring per group.
- **Stroke discipline:** outlines thin, uniform, and dark; contours crisp, never heavy. Heaviness usually
  betrays a scaled-up master (see pills).

## 7. Layout, alignment & grouping (generic)

- **Align within a group; make exceptions deliberate and *anchored*.** If one member breaks the row, it
  should snap to a *different* reference (e.g. line up with the adjacent larger row instead), never float free.
- **Reference-element pattern.** Within a class, make one member the template and copy its *relative*
  satellite geometry (label offset, LED offset, half-label positions) to every other member. New members are
  laid out by copying the class reference, not by eyeballing. (This is the layout analogue of §2's part-reuse:
  reuse a *placement recipe*, not just a shape.)
- **Collision avoidance — the control wins the pixels.** A label or indicator must never overlap the control
  it annotates; push labels/LEDs to clear space.
- **Section headers = centred label flanked by bracket lines.** The bracket lines should **span the full
  extent of the group's controls** (they *declare membership*) and be **vertically centred on the label
  text**. Exclusions are stated precisely — stop the bracket short of a control that isn't a member.
- **Constant pitch.** Rows use a uniform centre-to-centre spacing; size tweaks are small and relative
  ("a bit narrower"), not wholesale.

## 8. Typography (generic)
- **Two label weights:** brighter for member/function labels, dimmer for section/secondary captions. (These
  are the *legends* of §2 — cheap, per-position, printed on a shared body.)
- Text centred in its box.
- **Prefer a real glyph to a hand-drawn one** when the font provides it (symbols, note glyphs).
- Flip to a contrasting colour on saturated fills.

## 9. Interaction & affordance (generic)
- Continuous controls are draggable with visible travel and a clear position indicator.
- Pressed = a darker fill.
- **Decorative ≠ interactive.** Bezels, dividers and brackets must be click-through.

---
---

# PART II — KN7000 instantiation

The concrete realisation of Part I on this panel (`tools/gen_lay.py` → `src/mame/layout/kn7000.lay`). Values
here are specific to the SX-KN7000 and this emulator; the *reasons* for them are in Part I.

## 10. Colour tokens

| Token | Hex | Rung / role (§3–4) |
|-------|-----|--------------------|
| `SILVER` / `SILVER_D` | `#909097` / `#7a7a82` | flat-silver performance family; normal / pressed |
| metallic dome | vertical gradient `#9c9ca2→#b6b6bc→#74747e→#646470→#8c8c94` (pressed: `#828288→#9c9ca2→#5c5c66→#4c4c58→#727278`) | top-rung mirror |
| recess | `#2c2c32` (pressed `#1e1e23`) | dark recess ring |
| `LBTN`/`LBTN_D` | `#626268`/`#2c2c2e` | fader knob |
| `BTN` / `BTN_D` | `#54545c` / `#262628` | plain grey function buttons; also the matte body inside the exception buttons |
| `MSP`/`MSP_D` | = `SILVER` | performance pads (aliased to silver) |
| `PANEL` / `PANEL2` | `#38383a` / `#232325` | background / structural darks |
| `STROKE` | `#000` | all outlines |
| accents | orange `#b0561a`/`#6f360c`; teal `#4a5c5e`/`#33454a`; red `#98202e`/`#641a28` | app-launch / transport / record |
| text | `TXT` rgb(.90,.90,.90) bright; `TXTH` rgb(.72,.72,.74) dim (slight cool tint) | member / section legends |
| LEDs | red `#3a0000`/`#ff2020`; green `#003a00`/`#20ff20` | off / on |

Calibration note kept from the requests: SILVER is deliberately placed *between* two references — darker than
the old wheel body `#a3a3a9`, lighter than `BTN #54545c` (≈ ⅓ of the way toward BTN). The metallic dome tone
was shifted a notch darker so the resting look is the former *pressed* look (Part I §3, "prefer the calmer
tone").

## 11. Per-control taxonomy mapping

| Tier (§5) | KN7000 members |
|-----------|----------------|
| Metallic mirror (primary selectors) | the 16 RHYTHM GROUP + 16 SOUND GROUP buttons |
| Silver family (performance/recall) | TEMPO/PROGRAM wheel; all pill buttons (FADE, FILL IN, INTRO & ENDING, TAP TEMPO, SYNCHRO & BREAK, TRANSPOSE, R1/R2 OCTAVE, SD VOLUME, CONTRAST/MUTE, PAGE); MSP pads; the 8 PANEL MEMORY buttons; CUSTOM PANEL / FAVORITES / CUSTOMIZE + their enclosing ring |
| Plain grey function | PART EFFECT, GLOBAL EFFECT, PART SELECT, CONDUCTOR, VARIATION, APC controls, SEQUENCER, pad-control (AUTO SETTING/BANK/STOP), OTHER PART/HELP/DISPLAY HOLD/EXIT, the 16 MUTE part-buttons |
| Matte exception (hero shape, grey body) | **DEMO, SOUND EXPLORER, EW EXPANSION** — recessed ring `#2c2c32` + grey `BTN` body: the **same moulded shape as the metallic hero buttons, different finish** (Part I §2/§5). "Related to the metallic buttons but secondary." |
| Accent pills | orange = MUSIC STYLIST, SD LOAD; teal = START/STOP + PANEL MEMORY SET hub; red = EASY REC |

## 12. The element library = the parts kit; concrete geometry

The generator's shared element definitions (`two(name, w, h, s0, s1)` reused across many placements) **are**
the injection-moulded parts kit of Part I §2: `round_btn` / `round_btn_big` (+ `_silver` colour variants),
`metal_btn`, `round_btn2` (double-ring), `round_red`, the pill bodies (`pill_wide`, `pill_orange`,
`pill_greycyan`), the split-pill half (`_hhalf`, mirrored for left/right), `_gapseam`, `half_t`/`half_b`,
`page_up`/`page_dn`, `mute_up`/`mute_down`, `msp_*`, `tempo_knob`, `pill_ring_pair`, `hline`/`ghline`. New
controls should reuse these; a bespoke shape means a "new mould" and should be resisted.

- Round-button sizes: **standard 37** (authored 32, auto-grown +5, centre-preserved); **large 42**
  (round_btn_big; and the enlarged VARIATION/CONDUCTOR). Only two round-button sizes — a small "mould" set.
- Metallic dome: outer recess r=14 + gradient dome r=11 + a specular ellipse near top-left; stroke 1.5 outer /
  0.5 dome edge. The matte exceptions reuse this exact geometry with a `BTN` dome.
- Pills: stroke 1.5, `rx = h/2`, emitted at final size. Small split-pills **105×28**, large **105×50**.
- Split-pill divider: two clickable mirrored halves `hw=(w−4)//2`; a non-clickable seam of width `gw=w−2·hw`,
  stroke 1.0 black outline + silver fill, **no inputtag**.
- Enclosure ring example: DIGITAL DRAWBAR + ORGAN TABS ring width = 37 + 56 = **93**.
- Reference element for the small-split class = **FADE** (main label −33, half-labels −29, LEDs −15 from the
  pill top, centred on each half). R1/R2 OCTAVE is the anchored exception: lower than the other small pills,
  vertically centred with the large FILL/INTRO pills.
- Header brackets applied to PART EFFECT, GLOBAL EFFECT (right line extended to cover the 4th button, both
  lines centred on the text), RHYTHM GROUP, SOUND GROUP (brackets stop before SOUND EXPLORER / EW EXPANSION —
  excluding the two matte-exception buttons from the core set).
- LCD gets a thin **silver frame** around its black bezel.

## 13. KN7000-specific quirks & the tuning layer

- **The nudge layer.** Base positions come from the generator; Felipe's Inkscape fine-tuning is applied as
  per-element (dx,dy) *nudges* on top (see the `kn7000-layout-nudge-workflow` note). This design language
  describes the intended end-state; the nudges are how it's dialled in by hand. A maturing of the system
  would push more intent into the generator so fewer nudges are needed.
- Button→function and button→indicator-LED bindings are governed by **firmware-derived maps**, not by
  appearance — they are out of scope for this visual language.
- Reference photos of the physical unit are in `photos/`; the material choices track them.

## 14. Tensions & open questions

*Generic (would recur on any panel):*
- **Label-centred vs. group-centred headers.** If the section label isn't at the geometric centre of its
  group, the flanking bracket lines come out asymmetric. Re-centre the label, or let the brackets bend around
  it? Unresolved.
- **"Pill" vs. "rounded rectangle."** Where is the boundary (how round is a pill)? A judgement call today — it
  decided that the KN7000 MUTE buttons stay grey rather than joining the silver pills. In parts-kit terms:
  are they the *same mould* as the pills or a *different* one?
- **When does a group earn a header bracket?** Some groups have them, some don't; no rule yet.
- **Pressed-state feedback for continuous controls** (wheels/faders) isn't standardised.
- **How small should the parts kit be?** §2 says "small", but the exact target count of distinct shapes is a
  design decision not yet made.

*KN7000-specific:*
- Exact header-bracket gaps around text are hand-set per header.
- A formal token name for the metallic gradient doesn't exist yet.

## 15. Quick decision reference

*"I'm adding / restyling a control — how should it look?"* (generic path, then KN7000 lookup)

1. **Can an existing part (shape) carry it?** Prefer reusing a shape from the kit, changing only colour /
   finish / legend / orientation. Inventing a new shape is a last resort (§2).
2. **Primary sound/voice/style selector?** → top-rung metallic. *(KN7000: unless it's a secondary member like
   SOUND EXPLORER / EW EXPANSION → same hero shape, matte grey finish.)*
3. **Performance / expression / recall control?** → silver family.
4. **Transport / record / launch?** → accent (green-teal / red / orange, per convention).
5. **Plain function toggle?** → single grey circle, standard size (larger only if it merits emphasis), no
   inner ring.
6. **Two-state partner (±, in/out, 1/2)?** → split (rocker) pill: clickable mirrored halves + non-clickable
   black-outlined divider; match the class's existing size.
7. **Belongs to a labelled group?** → give the group a centred header with bracket lines spanning all members
   (exclude non-members explicitly).
8. **Choosing a tone?** → specify it *relative* to existing tokens ("a bit darker than X, lighter than Y"),
   add a darker pressed variant, keep the stroke thin & black, and place the label/LED using the class's
   reference offsets so nothing collides.

---

*Compiled from the 2026-07 KN7000 layout passes. Part I aims to be portable to any instrument control panel;
Part II is the concrete KN7000 realisation. All rules are hypotheses about intent — correct or discard freely.*

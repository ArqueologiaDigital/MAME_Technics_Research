> Recon report produced 2026-07-09 by the sound-subsystem planning sweep (5 parallel research agents).
> Companion to notes/sound-subsystem-plan.md. Verify page/line citations before building on them.

# KN7000 User's Manual — Sound-related GUI screen inventory

Source: `/home/fsanches/compartilhado/KN7000/kn7000_users_manual.pdf` (211 pages, text layer OK, screens read visually).
**Page numbering: PDF page index == printed page number (offset 0).** Verified visually on pdf pages 57, 60, 153, 163 (printed "57", "60", "153", "163" in footer) and via footer text on pdf pages 100/150/200. All page numbers below are therefore both the printed and the pdf page.

---

## 1. TABLE OF CONTENTS (condensed; from printed pages 7–9)

| Chapter | Page |
|---|---|
| Cautions / Controls and functions | 6 / 10 |
| **BASIC FUNCTIONS**: Getting started 12; Demonstration 14; Add effects 15; DIRECT PLAY 16; SD-AUDIO PLAY 17; MUSIC STYLIST 18; ONE TOUCH PLAY 20; PANEL MEMORY 22; CUSTOM PANEL 23; SEQUENCER 24; Save on SD 26; COMPOSER LOAD 28 | 12–28 |
| **PRACTICAL APPLICATIONS**: About the display 29; Favorites 32 | 29–33 |
| **Part I Sounds and effects**: Overview 34; Selecting sounds 35; Digital Drawbar 36; Organ Tabs 37; Accordion Register 38; Assigning parts to the keyboard 39; Effects (PART) 42; Effects (GLOBAL) 44; Controller 46; Transpose 47; Techni-chord 48 | 34–48 |
| **Part II Playing the rhythm**: Overview 49; Selecting rhythms 50; Playing the rhythm 52; Auto Play Chord 53; Fade In/Fade Out 58; Sound Arranger 60; One Touch Play 61; Music Stylist 61; Music Style Arranger 64; Panel Memory 65 | 49–67 |
| **Part III Performance Pads** | 68–73 |
| **Part IV Sequencer** (Outline 74; Easy Record 79; Realtime Record 80; Play 83; Step Record 88; Note Edit 98; Drum Edit 99; …) | 74–107 |
| **Part V Composer** (Outline 108; Chord Modify Change 113; Part Setting 114; Step Record 116; …) | 108–121 |
| **Part VI Disk Drive** | 122–137 |
| **Part VII SD Card** | 138–152 |
| **Part VIII Sound**: Outline 153; Part Setting 154; Mixer 157; Master Tuning 159; Key Scaling 159; Sound Load Option 160; Monitor Setting 160; Separate Setting 161; APC Reverb Setting 161 | 153–161 |
| **Part IX Reverb & Effect**: Outline 162; Equalizer 163; Allocation 163 | 162–163 |
| **Part X Sound Edit**: Outline 164; Easy Edit 165; Tone Edit 166; Pitch Edit 169; Filter Edit 170; Amplitude Edit 172; LFO Edit 174; Effect Edit 175; Controller Edit 176; Store the new sound 176 | 164–177 |
| **Part XI Control**: Outline 178; Overall Touch Sensitivity 179; Foot Controllers 179 | 178–180 |
| **Part XII Customize**: Outline 181; Home Page Setting 182; Display Time Out 183; Wallpaper 184; Data Protection 184; Custom Panel Mode 185; MIDI Setting Load Option 185; Video Out Mode 186 | 181–186 |
| **Part XIII MIDI** (labelled "Part XII" twice in the TOC — printing error): What is MIDI 187; Outline 189; Part Setting 190; … Computer Connection 196 | 187–196 |
| Initialize 197; Backup memory 198; Options 198; Terminals 199; Troubleshooting 201; Error messages 203; Index 205; Specifications 207 | 197–208 |

---

## 2. CHORD FINDER (pages 54, 57; also reachable from Sequencer chord step-record, page 93)

**Documented procedure (page 57, quoted):**

> "The CHORD FINDER can help, for example, when you do not know which keys to press to specify a given chord. When you input the chord name, the CHORD FINDER shows you which keys to press and even lets you hear the notes that make up.
> 1. Press the AUTO PLAY CHORD's MODE button to turn it on. • The display changes to the following. [APC SELECT screen]
> 2. Select CHORD FINDER. • The display changes to the following. [CHORD FINDER screen]
> 3. Use the APC MODE button to select the automatic accompaniment mode you will use to specify chords (FINGERED, PIANIST). • In the list column are shown the chords which can be specified in each mode.
> 4. Use the ROOT buttons to select the root note of the chord. Use the TYPE buttons to select the type of chord. • A typical way to finger the specified chord (TYPICAL) is illustrated on a keyboard diagram. • Each time the INVERSION button is pressed, different INVERSION fingerings are illustrated in order. (If there is no INVERSION fingering for the specified chord, this button is not shown on the display.) • **When the button with a picture of an ear is pressed, the notes of the chord sound. (The octave of the illustrated keys and that of the played tones may differ.)**
> 5. To exit the CHORD FINDER procedure, press the EXIT button."

**The APC SELECT screen** (screenshots on pages 52, 55, 56, 57): title bar `APC SELECT` + tempo (♩=160). Left column of LCD buttons: `BASIC` / `FINGERED` / `PIANIST`. Right column: `MEMORY : OFF`, `ON BASS : ON`, `LEFT HOLD : OFF`. Bottom-left: `COUNT INTRO : VOICE` (VOICE = spoken count, CLICK = clicking sound, p52). Bottom-right LCD button: **`CHORD FINDER`** (with a small ear-icon glyph). Note: this screen auto-returns to the previous display "after a few seconds" (p55), so the CHORD FINDER button must be pressed promptly.

**The CHORD FINDER screen** (page 57, read at 300 dpi):
- Header: ear icon + `CHORD FINDER`, tempo `♩=120` top right.
- Top-left box: `ROOT: [C]` (highlighted), `TYPE: Maj`.
- Top-right: `APC MODE: [FINGERED]` (toggles FINGERED/PIANIST), `INVERSION: TYPICAL`.
- Middle-left box — chord-type list (FINGERED mode shows 22 types, 3 rows): `Maj  min  7  min7  m7b5  6  m6  Maj7 / sus4  aug  mb5  7sus4  aug7  dim  b5  7b5 / mM7  M7b5  M7#5  mM7b5  add9  madd9`.
- Middle-right: keyboard diagram with dots on the keys to press (C-E-G for C Maj TYPICAL).
- Bottom button row (mapped to the physical balance buttons under the LCD): `ROOT` (∧/∨ rocker) — `TYPE` (◄ arrow, ∧/∨ rocker, ► arrow) — `INVERSION` (∧/∨ rocker) — **ear-icon button** (rightmost).

**What the ear button does:** it sounds the notes of the displayed chord. The manual explicitly warns the sounded octave may differ from the illustrated keys. **Which part/voice is used is NOT stated anywhere in the manual — not found** (searched pages 54, 57, 93, index 204–207). RE will have to determine the part empirically (plausibly the LEFT/CHORD part, since p55 says the initialized behavior of specified chords is "the specified root note (R. BASS part) and chord notes (CHORD part) are produced" when rhythm is off — but that statement is about keybed chord entry, not the ear button).

This is our best deterministic note-event trigger: no rhythm running, no keybed scan needed, one LCD button press produces note-on events.

Secondary path: page 93 (Sequencer STEP RECORD: CHORD) — "The CHORD FINDER feature, which shows you how to finger a specified chord, is available. (Refer to page 57.)"

---

## 3. SOUND SCREENS INVENTORY

### Part I — panel-button screens

**SOUND (sound select)** — p35. Path: PART SELECT (RIGHT1/RIGHT2/LEFT) + one of the SOUND GROUP panel buttons (PIANO, GUITAR, STRINGS & VOCAL, BRASS, MALLET & ORCH PERC, WORLD, ORGAN & ACCORDION, SAX & WOODWIND, PAD, SYNTH, BASS, DRUM KITS, MEMORY, EW EXPANSION). Screen `SOUND – RIGHT 1  PIANO  PAGE 1/3`: 10 sound names on side buttons (e.g. Concert Grand, Pop Grand, … Strynthed Clav) + instrument picture. "When you select a sound, the optimum effects for the sound are automatically applied" (cancellable via SOUND LOAD OPTION, p160). 1236 sounds total (spec, p207).

**SOUND EXPLORER** — p35–36. Path: PART SELECT + SOUND EXPLORER panel button. Screen `SOUND – RIGHT 1  SOUND EXPLORER  PAGE 1/2`: center category list (PIANO, ELECTRIC PIANO, HARPSI & CLAVI, MALLET, AC.GUITAR & HARP, ELECTRIC GUITAR, WORLD PERC, PERCUSSION …) selected with ∧/∨; sounds on left/right buttons, each annotated with its **MIDI [BANK MSB, LSB]-PROGRAM CHANGE number** (e.g. `[32.11-1 Concert Grand`); ALPHABET/CATEGORY toggle. GM2 sounds are selected here.

**DIGITAL DRAWBAR** — p36. Path: PART SELECT + DIGITAL DRAWBAR panel button (SOUND GROUP). Screen `SOUND – RIGHT1  DIGITAL DRAWBAR`: `<Jazz Drawbars>/<Rock Drawbars>` type button; 9 drawbars (16'…1') drawn as sliders, volumes changed live with the balance buttons; `FAST/SLOW TREMOLO` button (tremolo implemented by the SOUND DSP: Jazz=ROTARY SPEAKER, Rock=ROCK ROTARY — does not work if SOUND DSP button off); `PERCUSSIVE TONE` 2 2/3' and 4' on/off buttons; params `DRAWBAR ATTACK TIME / RELEASE TIME / PERCUSSIVE TONE DECAY / LEVEL` (bottom-right value list, ATTACK/RELEASE/DECAY/LEVEL buttons). Settings common to R1/R2/LEFT. Not selectable for ACCOMP/BASS of COMPOSER or PADS.

**ORGAN TABS** — p37–38. Path: PART SELECT + ORGAN TABS button. Screen `SOUND – RIGHT 1  TAB ORGAN`: TYPE ∧/∨ selects **USA Tabs / European Tabs / Theatre Pipes**; tab on/off buttons under display (FLUTE 16' 8' 4' 2 2/3' 2' 1' + 8' Vox); `PERCUSSIVE TONE` 2 2/3'/4'; `TREMOLO SLOW/FAST`; `VIBRATO ON/OFF`. Theatre Pipes variant: TIBIA tabs (16' 8' 4' 2 2/3' 2' 1 3/5' + Str) and `TIBIA TREMULANT / VOX TREMULANT / MAIN TREMULANT` OFF/ON buttons (MAIN = TRUMPET, ENGLISH HORN, STRING CELESTE tabs).

**ACCORDION REGISTER** — p38. Path: PART SELECT + ACCORDION REGISTER button. Screen `SOUND – RIGHT 1  ACCORDION REGISTER`: TYPE ∧/∨ = GERMAN / FRENCH / ITALIAN; register buttons across the bottom of display + `BASS1`/`BASS2` right; buttons light red; only one register at a time.

**CONDUCTOR / part assignment** — p39 (table of the 6 CONDUCTOR LED combinations; no LCD screen). **SPLIT POINT** — p40: press&hold SPLIT POINT → `SPLIT SELECT` screen ("Press a key to select the split point", shows e.g. `E 3`). **R1/R2 OCTAVE** — p41: `R1/R2 OCTAVE` screen, `OCTAVE : +2` (−2…+2). **SOLO** — p41 (button only; per-part monophonic).

**Effects (PART)** — p42: `SUSTAIN` button (on/off per part; length set in PART SETTING p154; initialized state assignable to Foot Switch), `DIGITAL EFFECT` button (on/off preset per sound). No screens; LED buttons only.

**SOUND DSP** — p43. Buttons: `SOUND DSP` + `VARIATION` (PART EFFECT block). Press & hold SOUND DSP → screen `SOUND DSP  RIGHT1  PAGE 1/1`: center list = effect groups (**Tremolo, Auto Pan, Vibrato, Ring Modulator, Mixup, Parametric EQ, LFO Filter, Enhancer**; EFFECT MEMORY holds edited effects), side buttons = types in group (e.g. Enhancer1–Enhancer6); `PART ∧/∨`; `DEPTH: 65` (0–127); `EDIT` button → **EFFECT EDIT** screen: `NAME: Enhancer3`, NAMING, EFFECT MEMORY LIST 1–4 (EMPTY), WRITE, PARAMETER/VALUE table (for Enhancer: MANUAL, MANUAL (V), LOW MIX, HIGH MIX, L DELAY, R DELAY, VOLUME, REVERB SEND; "(V)" params active when VARIATION on). Five SOUND DSPs exist: three for RIGHT1/RIGHT2/LEFT, two for APC (re-assignable to SEQUENCER via ALLOCATION p163). When DIGITAL DRAWBAR is on, VARIATION selects ROTARY SPEAKER/ROCK ROTARY. This display can also be reached from the REVERB & EFFECT MENU (p162).

**Effects (GLOBAL)** — p44–45. GLOBAL EFFECT panel buttons: CHORUS, MULTI, REVERB, MIC.
- **REVERB** (p44): press&hold → screen `REVERB  PAGE 1/3`: types on side buttons **Room1, Room2, Plate1, Plate2 | Concert1, Concert2, Dark1, Dark2** (page 1 of 3); center group list `Reverb` / `EFFECT MEMORY`; `TOTAL DEPTH` ∧/∨; `DETAIL EDIT` (same edit/store flow as SOUND DSP). Also reachable from REVERB & EFFECT MENU.
- **CHORUS** (p44): press&hold → `CHORUS  PAGE 1/1`: **Chorus1, Chorus2 | Chorus3, Chorus4**; groups `Band Chorus`/`EFFECT MEMORY`; `DETAIL EDIT`.
- **MULTI** (p45): press&hold → `MULTI EFFECT  PAGE 3/8`: types **Shallow1–Shallow8** on sides; center group list (page shown): **Overdrive, Fuzz, Amp Simulator, Limiter, Compressor, Slow Attacker, Dual Delay, Cross Delay** (8 pages of groups; full list not printed in the manual — not found); `DETAIL EDIT`. If a VOCAL-group type is selected, REVERB acts as MIC REVERB.
- **MIC** (p45–46): MIC button + MIC VOLUME slider (left end of panel). Press&hold MIC → `MIC REVERB & EFFECT  PAGE 1/2`: `MIC REVERB SETTING` PARAMETER/VALUE table (TYPE: Room, REVERB TIME: 99, VOLUME: 100), `MULTI EFFECT : OFF` button, `MIC REVERB : ON` button, `MULTI EFFECT SET` button; PAGE 2/2 = HARMONY EFFECT 1, 2 with `HARMONY PART` ∧/∨ and `MUTE`.

**Controller** — p46: PITCH BEND / MODULATION wheels (no screen; bend range per part on PART SETTING p154). **TRANSPOSE** — p47: panel +/− (±12 semitones), value shown on the home display.

**TECHNI-CHORD** — p48 (also on SOUND MENU, p153). Press&hold TECHNI-CHORD → screen `TECHNI-CHORD`: harmony-style grid, 2 columns: **CLOSE, OPEN 1, OPEN 2, DUET 1, DUET 2, COUNTRY, THEATRE | HYMN, BLOCK, BIG BAND BRASS, BIG BAND REEDS, OCTAVE, HARDROCK, FANFARE**; notation example picture ("Example: C-major chord"); `ORCHESTRATOR : CONDUCTOR` button (∧/∨ selects the part that produces harmony notes). OCTAVE/HARD ROCK/FANFARE work with unsplit keyboard.

### Part II — rhythm-side sound screens

**RHYTHM select** — p50: RHYTHM GROUP panel button → list screen (`RHYTHM  8&16 BEAT  ♩=121`: 8 Beat 1, 8 Beat 2, 8 Beat Slow, Swing Rock 1/2 | 16 Beat 1/2, 16 Beat Slow, 16 Beat Pop, Hip 16 Beat) + VARIATION 1–4 buttons. 220 rhythms × 4 variations (p207).

**APC SELECT** — p52/55/56/57 (see section 2). **CHORD FINDER** — p57 (section 2).

**FADE IN/OUT SETTING** — p59. Path: press&hold FADE IN or FADE OUT (also from CONTROL MENU, p178). Params: FADE IN Time (1–16 measures); FADE OUT Time (1–16 measures), Auto reset ON/OFF, Rhythm Auto stop ON/OFF, SEQ Auto stop ON/OFF. Selected with ▲/▼ + ∧/∨ buttons.

**SOUND ARRANGER** — p60. Path: SOUND ARRANGER `SET` button (panel, SOUND & ARRANGER block). Screen `SOUND ARRANGER  PATTERN : 8 Beat 1`: table `PART | SOUND | DIGITAL EFF` with rows **DRUMS1 (Pop Kit Tc, ---), DRUMS2 (Standard Kit1, ---), BASS (Funky E.Bass, OFF), ACCOMP1 (Funk Mute Guitar, OFF), ACCOMP2 (Mute Guitar, OFF), ACCOMP3 (Bright Piano, OFF), ACCOMP4 (Analog Syn.Brass, OFF), ACCOMP5 (SymphonicStrings, OFF)**. ▲/▼ selects part; sound chosen via SOUND GROUP buttons; DIGITAL EFFECT on/off per part (not DRUMS); OFF/ON button enables the substituted sounds during APC playback; per-rhythm setting.

**ONE TOUCH PLAY** — p61 (press&hold OTP button; auto sets sounds/effects/tempo, turns on APC + SYNCHRO & BREAK). **MUSIC STYLIST** — p61–63 (button → menu: MUSICAL CATEGORY / ORGAN STYLIST / MUSICAL ERA / ALPHABETICAL LIST / CUSTOM STYLIST; each a list screen; sets full registration incl. effects). **MUSIC STYLE ARRANGER** — p64 (press&hold → `MUSIC STYLE ARRANGER MODE` screen: RHYTHM / SOUND & RHYTHM / PANEL MEMORY).

### Part VIII — SOUND menu (PROGRAM MENUS → SOUND)

**PROGRAM MENUS screen** — p153/162/164/178: `SOUND, REVERB & EFFECT, CONTROL, MIDI | SOUND EDIT, SEQUENCER, COMPOSER, PERFORMANCE PADS`.

**SOUND MENU** — p153: `PART SETTING, MIXER, TECHNI-CHORD, SEPARATE OUT SETTING, APC REVERB SETTING | MASTER TUNING, KEY SCALING, SOUND LOAD OPTION, MONITOR SETTING`. Parts organization (p153): Normal parts = RIGHT1, RIGHT2, LEFT, PART 1–16; APC parts = ACCOMP1–5, BASS, DRUMS 1, 2, CHORD, R.BASS; PADS; BASS PEDAL.

**PART SETTING** — p154–156. 5 pages, PART SELECT ∧/∨ on the left:
- PAGE 1: SOUND (name, `Piano`), VOLUME 0–127, PAN L64–CTR–R63, SUSTAIN ON/OFF + SUSTAIN LENGTH (5), KEY SHIFT −24…+24, TUNING −128…+127, BEND RANGE 0–12 semitones.
- PAGE 2 (header shows `SOUND DSP TYPE : 018-009-000`): REVERB DEPTH 0–127 (40), DIGITAL EFFECT ON/OFF, SOUND DSP ON/OFF + SOUND DSP DEPTH 0–127 (60), CHORUS ON/OFF + CHORUS DEPTH (80), MULTI ON/OFF + MULTI DEPTH (80), **per-part EQUALIZER: LOW FC 100 Hz / LOW GAIN 0.0 dB / HI FC 10k Hz / HI GAIN 0.0 dB** (EQ LOW / EQ HIGH buttons).
- PAGE 3: GLIDE PEDAL, SUSTAIN PEDAL, PART EXP PEDAL, AFTER TOUCH, SOUND CONTROLLER, ORIGINAL TUNING (all ON/OFF).
- PAGE 4: FILTER RESONANCE (64), BRIGHTNESS (64), ATTACK TIME, DECAY TIME, RELEASE TIME, VIBRATO RATE, VIBRATO DEPTH, VIBRATO DELAY (all 0–127, center 64 = ±0).
- PAGE 5: MONO/POLY MODE, PORTAMENTO ON/OFF + PORTAMENTO TIME, MODULATION SENSITIVITY MSB (0)/LSB (64).

**MIXER** — p157–158. SOUND MENU → MIXER. 5 pages, all parts as fader columns (RIGHT1/RIGHT2/LEFT + PT1–16 via `OTHER PARTS/TR` panel button):
- PAGE 1: SOUND (per column), PAN, VOLUME (mute = press both balance buttons).
- PAGE 2: REVERB (level per part 0–127), DIGITAL EFF ON/OFF, SOUND DSP ON/OFF, SOUND DSP DEPTH.
- PAGE 3: CHORUS ON/OFF, CHORUS DEPTH, MULTI ON/OFF, MULTI DEPTH.
- PAGE 4: EQUALIZER HI FC + HI GAIN (dB), EQUALIZER LOW FC + LOW GAIN (per part).
- PAGE 5: KEY SHIFT (−24…+24), MIDI CHANNEL (CH1–CH16), LOCAL CONTROL ON/OFF, and `EDIT MIXER` button → **EDIT MIXER** (2 pages): p1 VIBRATO RATE / VIBRATO DEPTH / VIBRATO DELAY / FILTER RESONANCE, p2 BRIGHTNESS / ATTACK TIME / DECAY TIME / RELEASE TIME (all per-part 0–127).

**MASTER TUNING** — p159: single value `MASTER TUNING : 440.0 Hz`, ∧/∨.

**KEY SCALING** — p159–160: PART SELECT ∧/∨, ORIGINAL TUNING ON/OFF, per-key octave tuning (12 sliders, ±half-tone), ALL PARTS INITIAL; `OCTAVE TUNING TEMPLATE` sub-screen: PART / TYPE (**FLAT, WERCKMEISTER, KIRNBERGER, ARABIC 1–5, SLENDRO, PELOG**) / SHIFT (key, `[KEY=C]`) / SET.

**SOUND LOAD OPTION** — p160 (also on REVERB & EFFECT menu): SOUND DSP LOAD / SOLO LOAD / PORTAMENTO LOAD / CHORUS LOAD, each ON/OFF (whether these accompany a sound selection).

**MONITOR SETTING** — p160: ON/OFF buttons + signal-flow diagram (MIC IN, SOUND GENERATOR, LINE IN → MAIN VOLUME → MONITOR switch → LINE OUT, SPEAKER & HEADPHONE; AUX IN). Turns internal speakers off.

**SEPARATE SETTING** — p161: MODE = OFF / STEREO / MONO×2; PART ASSIGN per SUB OUT; "With MAIN OUT" ON/OFF; EXPRESSION ON/OFF. Routes parts to the two SUB OUT jacks.

**APC REVERB SETTING** — p161: table PART (ACCOMP1–5, BASS, DRUM1, DRUM2) | DEPTH = `PRESET IN RHYTHM` or 0–127.

### Part IX — REVERB & EFFECT menu (PROGRAM MENUS → REVERB & EFFECT), p162–163

Menu items: `MIC REVERB & EFFECT, SOUND LOAD OPTION, ALLOCATION, MIXER | SOUND DSP, MULTI, CHORUS, REVERB, EQUALIZER` (the middle five open the same screens as the panel press&hold paths above).

**EQUALIZER** — p163: **5-band EQ applied to the final L/R output**. Preset buttons left: **Flat, Make Up, Radio, Treble Boost, No Hi Hat**; per-band `GAIN` sliders, `FC` (frequency) row and `Q` (resonance acuity; not on EQ1 and EQ5); `EQ : OFF/ON` button; `ORIGINAL` button restores previous values.

**ALLOCATION** — p163: `ALLOCATION MODE : APC` (or SEQ); when SEQ, `SOUND DSP4 :` / `SOUND DSP5 :` rows select which SEQUENCER part uses DSP 4/5 (▲▼ + ∧∨). Initialized: DSP4/5 serve the automatic accompaniment.

### Part X — SOUND EDIT (PROGRAM MENUS → SOUND EDIT), p164–177

**SOUND EDIT MENU** — p164: `WRITE, TONE, AMPLITUDE, PITCH, FILTER | ORIGINAL(/EDITED), EASY EDIT, LFO, EFFECT, CONTROLLER`. A sound = up to 4 tones (p166). `SOLO` button auditions the selected tone only. ORIGINAL/EDITED toggles A/B compare. Drum-kit sounds get a different display (NOTE SELECT while pressing a key, p165).

- **EASY EDIT** (p165): one page: BRILLIANCE, VIBRATO DEPTH, VIBRATO SPEED, VIBRATO DELAY, OCTAVE SHIFT, ATTACK TIME, RELEASE TIME, DIGITAL EFFECT : OFF (DIG.EFFECT type select) + WRITE.
- **TONE EDIT** (p166–168), 4 pages: 1/4 `TONE SELECT` (per tone 1st–4th: ON/OFF, GROUP, TONE NAME, TONE DYNAM, LEVEL, KEY, DETUNE, PANNING MODE/PAN (NORMAL/STEREO L/R), DELAY (ms), TRIGGER = KEY ON / KEY OFF / LEGATO / NON LEG / PEDAL / CHORD; `TONE COPY` dialog FROM/OPTION/TO/OK); 2/4 `KEY LAYER` (L-FADE/LOW/HIGH/H-FADE key ranges w/ crossfades); 3/4 `VELOCITY LAYER` (same, per velocity); 4/4 `TONE DYNAMICS` (velocity-switched waveforms: GROUP, TONE WAVEFORM, LEVEL ADJUST, FILTER ADJUST, VELOCITY range, e.g. pp Piano L 0–107 / B Celesta 108–127).
- **PITCH EDIT** (p169–170), 3 pages: 1/3 `KEY SHIFT & DETUNE` (KEY SHIFT semitones, DETUNE, TONE SCALE = NORM, 1/2, 1/4, 1/8, 1/16, 1/32, 1/64, FIX; KEYBOARD OCTAVE: OCT SHIFT / RIGHT SPLIT / LEFT SPLIT); 2/3 `PITCH ENVELOPE` (START PITCH, ATK, PEAK, DCY1, SUS1, DCY2, SUS2, RLS, STOP PITCH, TOTAL DEPTH, envelope graph); 3/3 `P-ENV TOUCH & KEY FOLLOW` (TOUCH TIME/LEVEL; ENVELOPE KEY FOLLOW ATK/DCY/RLS + CENTER note).
- **FILTER EDIT** (p170–172), 4 pages: 1/4 `FILTER & EQUALIZER` (MODE = **LPF(6)+EQ, HPF(6)+EQ, LPF24, HPF24, BPF, THRU**; CUTOFF (e.g. 21.1K), RESO (dB); EQUALIZER-FILTER: RANGE HIGH/LOW, FREQ/CUTOFF, GAIN/RESO); 2/4 `TOUCH & KEY FOLLOW` (FILTER TOUCH: CUTOFF/CURVE/RESO; FILTER KEY FOLLOW: SLOPE/RANGE + graph); 3/4 `FILTER ENVELOPE` (START POINT, ATK, PEAK, DCY1, SUS1, DCY2, SUS2, RLS, STOP POINT, CUTOFF ADJUST); 4/4 `F-ENV TOUCH & KEY FOLLOW`.
- **AMPLITUDE EDIT** (p172–173), 3 pages: 1/3 `LEVEL` (LEVEL, TOUCH, CURVE, LEVEL KEY FOLLOW SLOPE/RANGE); 2/3 `ENVELOPE` (ATK, PEAK/PEK?, DCY1, SUS1, DCY2, SUS2, RLS + SUSTAIN PEDAL type LONG/HOLD, envelope graph); 3/3 `ENVELOPE TOUCH & KEY FOLLOW` (ATK/DCY touch, ATK/DCY/RLS key follow + RANGE).
- **LFO EDIT** (p174): **12 LFO groups**; 4 pages = destination: 1/4 `PITCH MODULATION` (vibrato), 2/4 AMP (tremolo), 3/4 FILTER (wah-wah), 4/4 PAN (auto pan). Per tone: SELECT (LFO 1–12), SPEED, KEYSYNC ON/OFF, PHASE(DEG), CONNECTION ON/OFF (arrow); TONE SETTINGS: PHASE ±, WAVE = SIN/TRI/SQR/SAW, DELAY, DEPTH, TOUCH; `OVERVIEW` button.
- **EFFECT EDIT** (p175), 2 pages: 1/2: SOUND DSP block (ON/OFF, GROUP `Enhancer`, TYPE `Enhancer3`, VARI OFF, DEPTH 85), CHORUS (ON/OFF, DEPTH 60), REVERB (ADJUST 37), MONO/POLY, PORTAMENTO (ON/OFF, TIME); 2/2 `DIGITAL EFFECT`: TYPE (e.g. `CHORUS 2`), ON/OFF (auto-on when sound selected), STEREO/MONO, params DEPTH 10, SPEED 20, DETUNE 10, DELAY 1, BALANCE 100, INTENSITY 0, REVERB ADJUST 0 (params revert to defaults when type changes).
- **CONTROLLER EDIT** (p176): `CONTROLLER ASSIGN` table: MOD WHEEL / AFTER TOUCH, two FUNCTION slots each (e.g. `LFO 1 DEPTH`), DEPTH (64), TONE ENABLE per tone 1st–4th ON/OFF/INV, `GLIDE : DISABLE/ENABLE`.
- **Store** (p176–177): SOUND EDIT MENU `WRITE` → `MEMORY WRITE` screen (NAME → MEMORY BANK 1–40, OK) + `SOUND NAMING` keyboard screen. Recall via SOUND GROUP `MEMORY` button. 40 memories + 1 user drum kit (p208).

### Related (Composer/Control)

- **Composer PART SETTING** — p114 (per-APC-part sound/volume/effects when building rhythms; same idea as Sound Arranger).
- **CONTROL MENU** (PROGRAM MENUS → CONTROL, p178): INITIAL, OVERALL TOUCH SENSITIVITY (p179: keyboard touch + VELOCITY SENSE), FOOT CONTROLLERS (p179–180: FOOT SWITCH 1=SUSTAIN, 2=GLIDE etc. assignment list incl. APC HOLD, DIGITAL EFFECT), PANEL MEMORY MODE, MUSIC STYLE ARRANGER MODE, FADE IN/OUT SETTING (spec p208 confirms the six items).

---

## 4. GUI TOP-LEVEL MAP (all top-level screens/menus; ♪ = sound-related)

| Screen | Page | Opened by | Purpose |
|---|---|---|---|
| Normal display / HOME PAGE | 29 | (default) | Rhythm, tempo, chord name, R1/R2/LEFT sounds, per-part volume faders (DRM/ACP/APC/PADS/LEFT/R2/R1); balance buttons adjust/mute ♪ |
| OTHER PARTS/TR view | 30 | OTHER PARTS/TR button | PT1–16 volume faders ♪ |
| PROGRAM MENUS | 30/153 | PROGRAM MENUS button | Hub: SOUND ♪, REVERB & EFFECT ♪, CONTROL, MIDI, SOUND EDIT ♪, SEQUENCER, COMPOSER, PERFORMANCE PADS |
| HELP | 32 | HELP button | Per-button on-screen help, language select |
| FAVORITES / FAVORITES SETTING | 32–33 | FAVORITES button | 4 user banks of shortcut displays; items incl. CURRENT SOUND/RHYTHM/STYLE, SOUND MENU, EFFECT MENU, SND EDIT MENU, SEQUENCER MENU, COMPOSER MENU; PANIC button (sound kill) ♪; MUTE KEYS |
| DEMO | 14 | DEMO button | Demonstration song playback ♪ |
| SOUND select | 35 | SOUND GROUP buttons | Choose sound per part ♪ |
| SOUND EXPLORER | 35 | SOUND EXPLORER button | Category/alphabet sound browser w/ MIDI bank+PC numbers ♪ |
| DIGITAL DRAWBAR | 36 | DIGITAL DRAWBAR button | Drawbar organ screen ♪ |
| TAB ORGAN (Organ Tabs) | 37 | ORGAN TABS button | Tab organ screen ♪ |
| ACCORDION REGISTER | 38 | ACCORDION REGISTER button | Accordion register screen ♪ |
| SPLIT SELECT | 40 | hold SPLIT POINT | Custom split point |
| R1/R2 OCTAVE | 41 | R1/R2 OCTAVE ± | Octave shift ♪ |
| SOUND DSP | 43 | hold SOUND DSP | DSP effect type/depth + EFFECT EDIT ♪ |
| REVERB / CHORUS / MULTI EFFECT | 44–45 | hold REVERB/CHORUS/MULTI | Global effect type + DETAIL EDIT ♪ |
| MIC REVERB & EFFECT | 45 | hold MIC | Mic reverb/harmony ♪ |
| TECHNI-CHORD | 48 | hold TECHNI-CHORD (or SOUND MENU) | Harmony style + ORCHESTRATOR ♪ |
| RHYTHM select | 50 | RHYTHM GROUP buttons | Rhythm list ♪ |
| APC SELECT | 55 | APC MODE button | BASIC/FINGERED/PIANIST, MEMORY, ON BASS, LEFT HOLD, COUNT INTRO, → CHORD FINDER ♪ |
| CHORD FINDER | 57 | APC SELECT → CHORD FINDER | Chord fingering display + audible chord (ear button) ♪ |
| FADE IN/OUT SETTING | 59 | hold FADE IN/OUT (or CONTROL MENU) | Fade times/auto-stop ♪ |
| SOUND ARRANGER | 60 | SOUND ARRANGER SET | Substitute APC part sounds ♪ |
| MUSIC STYLIST (5 sub-screens) | 61–63 | MUSIC STYLIST button | Registration by category/organ/era/alphabet/custom ♪ |
| MUSIC STYLE ARRANGER MODE | 64 | hold MUSIC STYLE ARRANGER | RHYTHM / SOUND & RHYTHM / PANEL MEMORY |
| PANEL MEMORY / BANK VIEW | 65–67 | PANEL MEMORY buttons | Store/recall registrations ♪ (indirect) |
| PERFORMANCE PADS screens | 68–73 | PAD buttons / PROGRAM MENUS | Phrase pads, copy, compile, record ♪ (note events) |
| SEQUENCER MENU (Easy/Realtime/Step Record, Play, Punch, Track Assign, Quantize, Note Edit, Drum Edit, …) | 74–107 | SEQUENCER PLAY/EASY REC buttons, PROGRAM MENUS | 16-track recorder ♪ (playback = note events) |
| COMPOSER MENU (incl. Part Setting p114) | 108–121 | PROGRAM MENUS | Rhythm pattern creation ♪ |
| DISK menu (Load/Save/DIRECT PLAY/Medley/Tools) | 122–137 | DISK IN USE/LOAD buttons | Floppy I/O; DIRECT PLAY = SMF playback ♪ |
| SD menu (Load/Save/SD-AUDIO/SD-SOUND/Playlist/Medley) | 138–152 | SD CARD LOAD button | SD I/O + audio playback ♪ |
| SOUND MENU (9 items) | 153 | PROGRAM MENUS → SOUND | See section 3 ♪ |
| REVERB & EFFECT MENU (9 items) | 162 | PROGRAM MENUS → REVERB & EFFECT | See section 3 ♪ |
| SOUND EDIT MENU (9 items) | 164 | PROGRAM MENUS → SOUND EDIT | See section 3 ♪ |
| CONTROL MENU (6 items) | 178 | PROGRAM MENUS → CONTROL | Touch sensitivity, foot controllers, MSA mode, fade, initial |
| CUSTOMIZE menu (9 items) | 181 | CUSTOMIZE button | Home page, favorites, display timeout, wallpaper, data protection, custom panel, MIDI load option, language, disk prefs, video out |
| MIDI menus (10 items) | 189–196 | PROGRAM MENUS → MIDI | Channels, messages, presets, computer connection |
| INITIALIZE | 197 | CONTROL MENU → INITIAL / power-on combo | Factory reset |

---

## 5. NOTES FOR EMULATOR PROBING (action → expected immediate 0x98xxxxxx traffic)

Priority order for MAME scripting while logging TG ports (0x98040000/2, 0x98050000/2) and the rest of the 0x980xxxxx block:

1. **CHORD FINDER ear button (p57) — the planned deterministic trigger.** Script: press APC `MODE` panel button → on APC SELECT press the LCD button at bottom-right (`CHORD FINDER`) *within the auto-return window* → on CHORD FINDER press the rightmost bottom LCD button (ear icon). Expect a burst of 3 note-on/note-off event writes (C-E-G, default C Maj) with **no rhythm engine and no keybed scan involved**. Vary ROOT/TYPE rockers for different note sets; INVERSION for different voicings. Part/voice used is undocumented — identify it from the register writes.
2. **COUNT INTRO voice (p52).** APC SELECT has `COUNT INTRO : VOICE` — turn COUNT INTRO (FILL IN 2) on, press START/STOP: a *spoken one-measure count* plays first. Single sample-playback trigger, simpler than a full rhythm; VOICE vs CLICK selects different sample paths.
3. **START/STOP with a rhythm (p51–52).** Continuous stream of drum note events at tempo; TAP TEMPO / TEMPO dial should modulate event timing, not register setup.
4. **DEMO (p14).** One button press → full song playback; exercises MainSeqRun-style playback engine end-to-end.
5. **Sound selection (p35).** Selecting a sound (SOUND GROUP button + LCD button) triggers "optimum effects automatically applied" — expect immediate TG program/parameter writes and SOUND DSP setup writes *without any key press*. Toggle SOUND LOAD OPTION (p160) filters to isolate which writes are effect setup vs. patch setup.
6. **PART SETTING (p154–156).** With a note held (or even without), each ∧/∨ press on VOLUME/PAN/REVERB DEPTH/BRIGHTNESS etc. should produce exactly one parameter write to the part's TG channel — ideal for mapping the register-indirect address space of IC201/IC205. Page 2's per-part EQ (LOW/HI FC + GAIN) tells us whether per-part EQ lives in the TG or the SHARC.
7. **MIXER (p157–158).** Same parameters but addressed per part in columns — good for confirming the part→TG-channel mapping (RIGHT1/RIGHT2/LEFT + PT1–16, incl. MIDI CHANNEL and LOCAL CONTROL on page 5/5).
8. **MASTER TUNING (p159).** One global value (440.0 Hz ±) — should be a single distinctive global TG write; easy to spot.
9. **REVERB / CHORUS / MULTI type select (p44–45) and EQUALIZER preset select (p163).** Selecting Room1→Dark2 etc. should reprogram the effects processor (expected: the ADSP-21065L path, plausibly via 0x98060000/0x98070000 or the 0x98020004/8/A/E group); EQ preset buttons (Flat/Make Up/Radio/Treble Boost/No Hi Hat) + `EQ ON/OFF` give clean coefficient-block diffs. `TOTAL DEPTH` is a single-parameter knob.
10. **SOUND DSP screen (p43).** PART ∧/∨ + type select + DEPTH; VARIATION button toggles "(V)" parameters — each press = one param write. EFFECT EDIT PARAMETER/VALUE list is a ready-made parameter name↔register map for one DSP algorithm at a time.
11. **DIGITAL DRAWBAR (p36).** Balance buttons move individual drawbar volumes *while sound is on* — continuous, fine-grained per-harmonic level writes; TREMOLO FAST/SLOW toggles the ROTARY SPEAKER DSP rate; PERCUSSIVE TONE 2 2/3'/4' toggles an extra attack tone.
12. **SOUND ARRANGER (p60) + START/STOP.** Changes which patch each APC part uses; comparing pattern playback before/after isolates per-part program-change writes from note writes.
13. **SUSTAIN / DIGITAL EFFECT / SOUND DSP / VARIATION panel buttons (p42–43).** Single on/off writes per press, per selected CONDUCTOR part.
14. **TECHNI-CHORD (p48).** Needs two keybed events (left chord + right melody) — produces extra harmony note events on the ORCHESTRATOR part; lower priority since it needs the keybed.
15. **FAVORITES → PANIC (p33).** "interrupts the sound" — should emit an all-notes-off / reset burst: useful to find the TG's global-silence register.
16. **MONITOR SETTING OFF/ON (p160), SEPARATE SETTING (p161).** Output-routing writes (likely DAC/analog switch side, possibly 0x98000000/0x98010000 candidates).
17. **KEY SCALING template SET (p159).** Writes a 12-entry per-key tuning table per part — a distinctive block write, good signature for finding tuning-table registers.
18. **SOUND EDIT SOLO + parameter edits (p164–176).** Per-tone (1 of 4) parameter writes; TONE SELECT ON/OFF per tone shows how the 4 tones of one patch map onto TG voices; LFO/FILTER/AMPLITUDE envelope edits map the synthesis-parameter register space in detail.

Caveats for scripting: the APC SELECT display auto-returns after a few seconds (p55), and many setting displays do too (use `DISPLAY HOLD`, p31, to pin a display). Menu items are chosen with the unlabeled LCD-side buttons (left/right of display) and the balance buttons below the display (p30–31); `EXIT` backs out one level.
# KN7000 bits still needing a fresh emulator HELP-info confirmation

Bits whose name in `wf/panel-button-names.md` is LOW/MED and could be pinned (or is worth
double-checking) with a live emulator HELP-info run. Split by whether the HELP-info oracle is
*expected to resolve* the bit.

Method (per verify_0/verify_2): press HELP (`SEG08 0x08`), then press the candidate bit, read the
`HELP : <NAME>` line off the LCD. Harness gotchas the verifiers hit and fixed:
- Do NOT use `pkill -9 -f 'kn7000 kn7000'` — it matches the launching shell's own argv and SIGKILLs
  it before boot under `errexit`. Use `pkill -9 -x kn7000` (process-name match) + `|| true` guards.
- Concurrent sibling agents contend for the single DISPLAY:0 slot; several verifier runs were killed
  mid-boot. Run these when no other emulator agent is active, and allow a generous boot timeout
  (cold cache can miss a 150 s dump window).

---

## A. Expected to RESOLVE via HELP-info (do these first)

| SEG.bit | event / arg | current name | what to confirm |
|---------|-------------|--------------|-----------------|
| SEG03.0x04 | ev20A9 / arg0027 | AUTO PLAY CHORD OFF/ON (LOW candidate) | Confirm the exact HELP name. Static pool literal @0x48395038 entry 57 says "AUTO PLAY CHORD OFF/ON"; verify_1 could not launch the emulator. This is the highest-value single confirmation (a HIGH-confidence physical button currently only LOW). |
| SEG12.0x10 | ev2040 / arg0767 | ev2040 mode button (unresolved) | ev2040 "open named mode" index 7. Candidate set: SEQUENCER / COMPOSER / SOUND / MUSIC STYLIST / CUSTOM PANEL / MIDI. HELP-info should name the opened screen. |
| SEG12.0x20 | ev2040 / arg0363 | ev2040 mode button (unresolved) | Same family, mode index 3; same candidate set. |
| SEG15.0x01 | ev2040 / arg0666 | ev2040 mode button (unresolved) | Same family, mode index 6; same candidate set. Do NOT adopt the stale "SOUND ARRANGER SET" guess. |
| SEG13.0x10 | ev2062 / arg0010 | GLOBAL EFFECT cluster (unresolved) | Sits in the GLOBAL EFFECT row with REVERB (0x40) / MIC (0x80). One of CHORUS / DIGITAL EFFECT / MULTI EFFECT — HELP should disambiguate this bit vs SEG13 0x20. |
| SEG13.0x20 | ev2061 / arg0032 | GLOBAL EFFECT cluster (unresolved) | Same cluster; resolve alongside 0x10 so the CHORUS/MULTI ordering is pinned. |
| SEG15.0x02 | ev20AE / arg0033 | unresolved (ev20AE/0033) | Isolated fn-id 0x33 toggle. The "SOUND ARRANGER OFF/ON?" hint was removed (that name is SEG02 0x80). A fresh HELP read is the only way to name it. |

## B. HELP-info known/expected to NOT resolve (needs a different method)

These return only a group name or the HOME/CONDUCTOR view; HELP cannot separate them. Listed so a
future pass doesn't waste the emulator slot on HELP — use MIDI-out capture, LED/behavior sweep, or a
targeted state snapshot instead.

| SEG.bit(s) | event / arg | issue | suggested method |
|------------|-------------|-------|------------------|
| SEG15.0x10 / 0x20 / 0x40 / 0x80 | ev2011 / 2012 / 2013 / 2016 | PART EFFECT cluster; the full SEG15 HELP sweep named only 0x04, and these show the HOME/CONDUCTOR view (panel-completion-plan tick f). Names (SUSTAIN/DIGITAL EFFECT/CHORUS/MULTI EFFECT) exist in the ROM pool but there is no event→name table. | Capture the MIDI/SysEx or DSP-state change each press produces, or LED sweep, and match to the effect. |
| SEG09.0x10 / 0x20, SEG10.0x08 | ev2085 / arg 0016 / 0116 / 0316 | VARIATION & MSA — all four members share the identical HELP screen; the VAR position number is a non-linear arg-hi inference (VAR1=arg-hi 0x02, VAR2=0x00). | Press each and read the on-screen VARIATION indicator (1–4) from a snapshot, not HELP. |
| SEG10.0x20 / 0x40 | ev2009 / arg 0102 / 0002 | PART SELECT group members 2/3 — HELP returns the group name for any member. | Snapshot the selected-part cursor after each press. |
| SEG11.0x20 / 0x40 | ev2008 / arg 0101 / 0001 | CONDUCTOR group members 2/3 — same limitation. | Snapshot the CONDUCTOR selection after each press. |
| SEG0F.0x04 – 0x40 | ev2001 / arg 1000–1400 | LCD-RIGHT soft-keys (ON-mirror of SEG03). No HELP name (part-control bits, like the mute matrix, return no HELP). Physical identity is context-dependent. | Snapshot the LCD RIGHT soft-key labels on a screen where they are active. |

---

## Priority summary

- **7 bits** are genuinely worth a fresh HELP-info run (section A) — the two SEG13 GLOBAL EFFECT
  bits and the three ev2040 mode buttons would collapse most of the remaining LOW count; SEG03 0x04
  is the single most valuable (a HIGH physical button stuck at LOW only for want of a launchable
  emulator).
- **~12 bits** (section B) are HELP-unresolvable and should be pursued with snapshot / MIDI / LED
  methods, not HELP.

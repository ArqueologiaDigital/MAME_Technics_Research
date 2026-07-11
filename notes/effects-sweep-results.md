# Effects sweep results (workflow wf_46aaaf77-352, 2026-07-11)

Batch health-test of the DSP effect types after the reverb fixes. Recipes for selecting every effect
type are in notes/effect-selection-recipes.json (224 entries: 8 Reverb, 8 Chorus, 94 Multi across 16
groups, 114 SoundDSP across 17 groups).

## Navigation mechanics (verified)
- Effect-type screens open on press-and-HOLD ~2.5s: REVERB :SEG0F 0x04, CHORUS :SEG11 0x04,
  MULTI :SEG10 0x04, SOUND DSP :SEG0F 0x08.
- Side soft-keys select the current group's types: L1-L4 = :SEG00 0x02/0x08/0x20/0x01,
  R1-R4 = :SEG11 0x10, :SEG11 0x20, :SEG13 0x01, :SEG12 0x01 (column split by group size).
- GROUP-LIST cursor = :SEG09 0x04 up / 0x08 down (wraps; instant type-set switch). The "PAGE n/m"
  header follows the selected GROUP. So group-level pages are walked by the group cursor.
- The dedicated PAGE rocker (now SEG0B 0x10/0x20, fixed this session) steps within-screen pages too
  (verified on MULTI EFFECT). TYPE-pages WITHIN a group (e.g. Flanger "1/5") still have an unfound
  page-flip control -- SEG16-1A/20 are no-ops there (they are valuator wires). OPEN ITEM.
- Do NOT press :SEG00 0x04 (DETAIL EDIT, leaves the type screen; exit = :SEG0B 0x80).

## Verdicts
- ★ ALL 8 REVERB TYPES PASS: each has a DISTINCT plausible tail (Room short -> Dark2 long), zero DAC
  clips, zero DSP rail writes (0 of ~3.79M TX writes/segment), zero inter-segment leak, all decay to
  zero by +3s. Selection Room1..Dark2 monotonically changes the tail as the names suggest -- proves
  type selection reprograms the DSP correctly. (Concert1 == boot-default character.)
- CHORUS = NO AUDIBLE EFFECT (SUSPECT): all chorus selections leave keybed audio numerically
  identical (tail inherited from the still-active reverb). Interpretation pending: likely the chorus
  SEND for RIGHT1 is 0 by default (test-rig limitation, not necessarily a bug) OR the chorus unit's
  return is not summed. NEXT: verify whether a nonzero chorus send for the played part produces the
  effect; if send>0 and still silent, investigate the chorus unit's return wiring.
- MULTI / SOUND DSP: recipes enumerated (16 + 17 groups walked); batch health-tests were only
  partially completed (the sweep's test phase was killed mid-run, OOM). RE-RUN the batch tester over
  notes/effect-selection-recipes.json to get per-type verdicts (harness in the workflow scratchpad;
  key gotcha: MAME needs -seconds_to_run or it sits on the BAD_DUMP wavepack warning screen).

## Open items
1. Chorus-no-effect: send-vs-return investigation (above).
2. Within-group TYPE page-flip control (Flanger 1/5 etc.) unfound.
3. Complete the MULTI/SOUND-DSP batch health tests.

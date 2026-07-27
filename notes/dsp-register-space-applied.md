# uPD6383GF register space — what was found, and what was applied (NOTHING)

Companion to `kn5000-roms-disasm/dsp/analysis/register-space.md` (2026-07-27),
the pass on the **other 44 dark words** of the KN5000 effects-DSP frame —
everything in `dark-words.md`'s partition except the 42 external delay-DRAM
slots a sibling pass owns.

Reproduce every number with

```
python3 dsp/tools/register_space.py            # in kn5000-roms-disasm
```

## APPLIED TO THE EMULATOR: nothing

* `git status -- src/` in this tree is empty. No device, no disassembler, no
  driver was touched, so the audio is bit-identical to the published build **by
  construction**.
* Neither disassembler mirror was edited, so their word-for-word agreement over
  the 3057-word corpus is unaffected.
* `dsp/verify.py` reports **BYTE-MATCH OK**.
* **Zero of the 44 dark slots are recovered.** The one FORCED result (the
  `is_c40()` immediate is 8 bits, not 13) is a re-derivation of
  `output-stage-decode.md`'s payload rule and does not make any word executable.
  Everything ambiguous keeps trapping.

## APPLIED TO THE TOOLS: one bug fix, one note corrected

**`tools/kn5000_dsp_params.py`** — `writer_0387E6()` and `writer_038539()`
encoded byte 1 of the DSP data packet as `(value >> 1) & 0x7F`. **It is
`(value >> 17) & 0x7F`.** All three Sub CPU writers emit

```
   sra 0x01,XWA        ; >> 1
   sra 0x00,XWA        ; >> 16   <-- a shift COUNT OF 0 MEANS 16 on the TLCS-900
   and XWA,0x7F
```

at `0x03859D` (LABEL_038539), `0x03884A` (LABEL_0387E6) and `0x038985`
(LABEL_038922). The old reading silently dropped the second shift and therefore
the top seven bits of every coefficient. Round-trip over the 1751 data packets
canned in the ROM's per-algorithm PARAM streams: `v>>17` reproduces
**1751 of 1751**, `v>>1` only **938**. The corrected function now reproduces the
two MEASURED live cold-boot packets byte-for-byte:

```
   writer_038539(0x06, 0x400000)[1] == 0a 20 00 00 15
   writer_038539(0x86, 0x178D0B)[1] == 0a 0b c6 85 95
```

`dsp_disasm.host_packet()` and `upd6383d.cpp` always had the split right, so no
disassembly, listing or decoded value anywhere in the project was wrong — only
the *re-synthesis* helper and the note that quotes it.

**`notes/kn5000-dsp-parameters.md`** — three annotations added in place:

1. §2, the writer byte layout (above). The consequential part: the datum is
   **one contiguous 24-bit field at `W[30:7]`**, so that section's "17-bit
   immediate plus a duplicated 7-bit field" reading is withdrawn. Two bits above
   it stay OPEN — byte 0 is `0x0A` in 1707 packets and `0x0B` in 44, and all 44
   target *even* cells of the `0x50…` state block.
2. §5's SPECULATIVE prediction that **cell `0x90` is the effect wet/output
   level** is **FALSIFIED**: `0x90` is **REV SEND**, 37 of 37.
3. The effect's own output level is **cells `0x06` (unit 0) / `0x86` (unit 1)**,
   and the user-facing parameter is called **VOLUME** — 49 of 49 algorithms.

## The one result the audio path cares about

The two words immediately preceding the DO1/DO2 presentations are dark
(`w72 = 000.1.06.087`, `w77 = 859.0.86.822`). What they address is now settled:

```
   USER PARAMETER "VOLUME", 0..99
     -> parameter record  [op 0x63][operand][selector byte]     canned per algorithm
     -> evaluator LABEL_038EB9:  *(CURVE[sel] + 4*value)        sel 0/1/2 ->
                                                                0x012483 / 0x012613 / 0x0127A3
     -> T1 address 0x06 (37 unit-0 algos) / 0x86 (12 reverbs)
     -> writer LABEL_038539: 000.1.AA.000 + a tag-0x15 datum
     -> D-RAM cell 0x06 / 0x86:  24-bit UNSIGNED Q0.23 LINEAR GAIN
```

`CURVE[*][0] == 0`, so user value 0 is exact mute; `CURVE_C` is a perfect
0.258 dB/step ladder. The two MEASURED cold-boot values land on `CURVE_A[84]`
and `CURVE_C[70]` — the exact curves algo 1 (CHORUS) and algo 16 (ROOM REVERB 1)
can in their own streams — and the unit-1 value is in no other table, so a wrong
selector would have failed the check.

**This confirms `r2-output.md` / `k5-output-stage.md`'s "per-unit OUTPUT LEVEL"
reading through a chain that shares no premise with it**, and adds the name, the
format, the law and the lifetime. It does **not** settle what `w72` and `w77`
compute, so both keep trapping.

## Two corrections other notes in this tree should carry

* **`notes/kn5000-dsp-parameters.md` §5's `0x90` prediction** — done, in place.
* **`kn5000-roms-disasm/dsp/instruction-set.md`'s auto-increment sentence** — the
  9-select tiling (`0x1D, 0x21, …, 0x3D`, stride 4, four values each) proves
  *stride-1 addressing* but **not the direction**: a descending burst tiles
  identically, so the tiling alone leaves `{+1, −1}`. The direction comes from a
  second datum — algo 39 issues `select 0x50 ×29` then `select 0x6D ×11`, and
  `0x6D = 0x50 + 29`. Flagged in the analysis note; the ISA note is in the other
  repo and was left to its owner.

## For whoever works on the delay line next

`register_space.py cells` prints **every algorithm's delay-descriptor image**,
statically, for the first time:

* the descriptor space is **partitioned by unit** — unit-1 owns `0x00..0x1F`
  (12 of 12 reverbs, identical extent), unit-0 owns `0x26..0x39` (79 of 79).
  That is R3 candidate (iii)'s two bases, **measured** rather than enumerated;
* MULTI TAP DELAY `0x26/0x28/0x29/0x2A = 6000/12000/18000/24000` are confirmed
  as `DELAY 1..4` by the T1 parameter map *and* by the UI name list — 136/272/
  408/544 ms at 44.1 kHz — and cell `0x2C = 0`, the value R3 §6.3 used to
  identify `880.1.60.000` as the line write;
* ROOM REVERB `descriptor[0x00] − descriptor[0x03] = 33568 − 32768 = 800`
  reproduces R3's pre-delay exactly;
* **50 of the 82 corpus ACTION-`0x0B` words are delay-DRAM words**, so ACTION
  `0x0B` and the DRAM family are one problem, not two.

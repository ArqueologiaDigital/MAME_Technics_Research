# The EG level law, from the fader tables

2026-08-06. Follows the organ-envelope investigation (`8a5ed73`, blog part 129).
Both tables dumped from `kn5000_subprogram_v142.rom` and analysed. **Structure solved; the
absolute dB-per-code slope is NOT determined, and I am not going to guess it.**

## The tables

    PeakLevel_Fader  sub-CPU 0x011899  (file offset 0x2999)
    Level_Fader      sub-CPU 0x0118FE  (file offset 0x29FE)

101 entries each (index 0..100), monotonic NON-INCREASING, `[0] = 0xFF`,
`Peak[100] = 0x09`, `Level[100] = 0x04`. **Index is an ATTENUATION percent** — higher index
gives a LOWER level code.

## Three exact structural facts (MEASURED)

1. **`code = 234 - 2*index`, EXACTLY, over index 21..94.** A least-squares fit returns
   234.000 and -2.000, and reproduces `Level_Fader[60] = 114 = 0x72` exactly — the very code
   that makes the organ collapse. Two code units per percent.
2. **`Level_Fader = PeakLevel_Fader + 20`, EXACTLY, over index 18..94.** The two tables are the
   same curve offset by a constant 20 code units. So PEAK and SUSTAIN really are on one scale
   (this closes the standing uncertainty), and 20 codes is a FIXED acoustic ratio between them.
3. Both curves are COMPRESSED outside that body — index 0..17 and 95..100 — so the linear form
   is the working range, not the whole table.

## What this does NOT settle

The tables map **index <-> code**. They do not map **code -> gain**. So they give the SHAPE of
the law and its linear region, but not the dB per code unit. Three candidate readings, and the
data rules against all three:

| law | gain(114) organ sustain | gain(206) piano | verdict |
|---|---|---|---|
| current `2^((L-255)/16)` | 0.0022 (-53 dB) | 0.12 (-18 dB) | ✗ organ inaudible — the bug |
| linear `L/255` | 0.447 (-7.0 dB) | 0.808 | ✗ MEASURED: piano peak pinned at 32768, 0.56% clipped |
| fader-as-linear-amplitude, `gain = (code-34)/200` | 0.40 (-8.0 dB) | 0.86 | ✗ LOUDER than L/255 at the piano's level, so it clips worse |

★ **The trap this exposes.** Every law that lifts the organ's code 114 to a musical level also
lifts the piano's code ~206, and the piano is ALREADY at the clipping edge. Fixing the EG law
alone cannot be right — a compensating factor has to exist elsewhere in the chain. The obvious
candidate is the `sample * env_level / 0xFF` multiply, whose own comment says it is
"Known to be the WRONG reading and deliberately retained". **The next pass should treat the EG
law and the env_level multiply as ONE joint calibration, not two independent fixes.**

## The measurement that would settle it

The 20-code Peak/Level offset is a fixed ratio in whatever domain the codes live. If a slope
`m` dB/code is correct, that offset is `20m` dB:

    m = 0.188 -> 3.8 dB     m = 0.376 (current) -> 7.5 dB
    m = 0.300 -> 6.0 dB     m = 0.500 -> 10.0 dB

So: **find what the firmware's own UI or documentation says the peak-vs-sustain relationship is,
or find the consumer of these tables and read what it does with the result.** One known ratio
pins `m`, and `m` plus the exact linear form above gives the whole law with no fitting.

Second, cheaper route: the SUST class parks at code 242 and the CLICK class at 114, and both
were measured in the same capture. Their true gain RATIO is one number that any correct law must
reproduce — but it must be measured from a window that does not straddle the 1.9 ms attack (the
earlier 0.812 figure for the SUST class does, which is why it disagreed with its own prediction).

## Do not repeat

The organ's decay tail rising is NOT evidence for a law — it follows arithmetically from raising
gain(114) by any amount at all. The piano's HEADROOM is the criterion that can actually fail, and
it is the one that killed the linear law.

# +0x080[14:12] probes -- how descriptor bits reach the tone generator

Written 2026-08-19, tracing where the tone generator's undecoded register fields come from, after
the project owner rejected the conclusion that "nothing transfers the ROM data".

**The result these produced:** register `+0x080` bits[14:12] are built by `Voice_Build_OutputLevel`
(ROM `0x0232C7`, `kn5000_subprogram_v142.asm:15687-15726`) from the SELECTED ZONE RECORD:

    bit 7 of zone_record[+0x02] SET   ->  field = (zone_record[+0x02] >> 4) & 7   # descriptor bits
    bit 7 CLEAR                       ->  field = T[folded_note mod 12]           # table at 0x00FBE4
                                          T[n] = floor(2 * (n mod 12) / 3)

That is the same record whose word[0] is the `+0x040` selector and whose word at `stride-2` is the
pitch constant C. So per-recording ROM data DOES reach the chip, in processed form.

Verified on a 2182-burst capture: **196/196 = 100.0%** for selectors with a unique zone record. The
polished version of that check is `../kn5000-rootpitch/reg080_oracle.py` -- **start there**; these
are the working probes behind it.

| group | scripts | question |
|---|---|---|
| ROM walk | `_walk.py` | Walk `table_data` to selector -> zone record. Sourced by the `pan_*` probes via `exec()`. |
| the field itself | `pan_rom_vs_bus.py`, `pan_endtoend.py`, `pan_gate.py` | Does the ROM predict the captured field, per burst? |
| which branch | `pan_channel.py`, `pan_sets.py`, `pan_offset.py` | Which selectors take the override branch, and how does the field behave on the other one? |
| as an oracle | `pan_disambig.py` | Can the field choose between the candidate C values of an ambiguous selector? |
| C structure | `analyse.py`, `deep.py`, `rootprobe.py` | What constrains C, given the field? |

## Running them

`_walk.py` and the `pan_*` probes run as-is: `python3 pan_endtoend.py`.

⚠ **Reference-only** -- `bound.py`, `decoder.py`, `final.py`, `flagm.py`, `octave.py`,
`persets.py`, `sets.py`, `window.py` load a `G.pkl` pickle that was built in session scratch and is
NOT preserved. They are kept as a record of the method and the arithmetic, not as runnable tools;
regenerating `G.pkl` means re-walking the ROM with `_walk.py` and re-parsing a burst capture.

## Caveat that cost 3% of an answer

A selector can appear in more than one SET, with different zone records. Score only selectors with a
unique record: unrestricted, the same capture reads 204/211 = 96.7%, and the 7 "errors" are the
mapping, not the theory.

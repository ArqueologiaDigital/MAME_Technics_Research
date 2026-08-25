# GAP A audit probes — what each script answers, and how to run it

These are the probes an adversarial review of the proposed `0x0010C000` register
decode ran before any of it was allowed near `src/mame/matsushita/wsa1.cpp`.
They exist so the numbers quoted in that review can be re-checked, not so the
review can be re-read. Both read `../../../wsa1-roms-disasm/` **read-only** and
write nothing.

| script | the question it answers |
|---|---|
| `gapA_rom_checks.py` | Do the five tables the decode rests on really have the shape claimed — the output-level table's closed form and its `0x0FF4` top, the 3-bit note-field staircase, the CC volume curve's 32-counts-per-halving and its `C[127] == 0`, the two 101-byte halves of register `0x0800`, the 51-byte detune curve? Reads **bytes**, never the listing. |
| `gapA_listing_checks.py` | Which staging word feeds which register block, in execution order; how many words the burst actually reads; whether the gate is pulsed 1-then-0; how many computed stores the byte-pair block group has; whether the callees around the `0x0500`/`0x08C0` packing preserve `HL`/`DE`; whether both copies of register `0x0040`'s fix-up carry the `< 0x6000` guard; and what bounds `sub_FA5ED3`'s three arguments. Parses the listing by each line's own `; ADDR  insn` comment, so it reads instructions at addresses, not header prose. |

Run both (each prints `FAILURES: 0` when everything holds):

    python3 notes/wsa1-gapA-audit-probes/gapA_rom_checks.py
    python3 notes/wsa1-gapA-audit-probes/gapA_listing_checks.py

Optional argument: a path to `wsa1_prom_c.ic28` / `wsa1_prom_c.s` respectively.

**Signals worth remembering when a number here ages.** `gapA_rom_checks.py`
section 1 is the only thing pinning register `0x0080`'s dB-per-count and its
`0x0FF4` reference; section 3 fixes which direction is loud. `gapA_listing_checks.py`
section 1 is the whole word→register map — if one row moves, every register label
in the driver moves with it — and section 5 is a real disagreement between two
copies of one routine, not a formatting detail.

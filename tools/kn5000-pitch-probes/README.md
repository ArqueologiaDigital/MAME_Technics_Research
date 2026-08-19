# KN5000 pitch-constant probes

Why these exist: the tone generator HLE needs a per-selector constant C to recover the true note
from the absolute pitch the firmware writes to register +0x400. It currently ships as a generated
1444-entry table in the MAME PR, which upstream reviewers are expected to object to. These scripts
answer whether that table is necessary, whether it is correct, and where the data really lives.

| script | question it answers | run it |
|---|---|---|
| `kn5000_pitch_C_derivability.py` | Is C derivable from anything the emulator already knows -- the selector's class/entry bits, the SET's root, its key range, its flags -- or is it irreducible per-recording data? Also: is the shipped table correct? | `python3 kn5000_pitch_C_derivability.py` |
| `load.py` | helper: loads the extracted SET descriptor tsv | imported by the above |
| `../kn5000_pitch_constant_analysis.py` | How big is the table really -- distinct values, how many are zero, how much key-span weight rides on the non-zero ones? | `python3 tools/kn5000_pitch_constant_analysis.py` |

## What they established (2026-08-19)

**C is irreducible.** It is the recorded sample's own fundamental expressed in the chip's log-pitch
units. 193 distinct non-zero values, gcd 1, smallest neighbour gap 0.39 cent, only ~9.8% whole
semitones. No formula reproduces it, and it is not present in the one dumped wave ROM's parameter
records. A table -- or a read of the firmware's own descriptors -- is unavoidable.

**But the data is not "firmware-derived data in a source tree".** The SET descriptors sit verbatim
in the `table_data` mask ROM (IC1 odd / IC3 even) that the driver already loads, and which boot
merely copies into sub-CPU RAM. So the table can be BUILT AT RUNTIME from a ROM MAME already
ships and hashes, and the generated file deleted.

**⚠ The shipped table has a bug, and so does any naive walk.** When a SET descriptor's byte +0x00
has bit 1 set, the firmware substitutes the literal 0x4280 for both the root pivot and the
basepitch, so the `(basepitch - pivot)` term is identically zero and neither field is read
(`kn5000_subprogram_v142.asm:16216-16260`). `tools/kn5000_pitch_audit.py` subtracts it
unconditionally, fabricating a +49/+57/+65 semitone offset for **112 of 1444 selectors (7.8%)**.

Corroboration that needs no disassembly: the 13 SETs with bit 1 set are EXACTLY the 13 whose `root`
byte is not 0x42, and all 13 carry the same basepitch 0x417F -- i.e. precisely the fields the
firmware never reads for them hold junk. Verify with:

    python3 -c "import csv,collections; \
      r=list(csv.DictReader(open('notes/data/kn5000-multisample-sets.tsv'),delimiter='\t')); \
      print({x['set_idx'] for x in r if int(x['flags'],16)&2} == {x['set_idx'] for x in r if x['root']!='42'})"

**Do not use 'byte-identical to the shipped .hxx' as an acceptance gate for a new implementation.**
That gate passes the bug.

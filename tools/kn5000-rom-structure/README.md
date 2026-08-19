# KN5000 ROM structure probes

Exploratory probes written while tracing where the tone generator's register values come from
(2026-08-19). They are kept because the upcoming runtime SET-descriptor walk -- building the pitch
constants at `machine_start()` from `table_data` instead of shipping a generated table -- needs this
structural knowledge, and re-deriving it costs hours.

Two ROMs are probed. `table_data` (IC1 odd / IC3 even) holds the multisample SET descriptors that
the boot code copies into sub-CPU RAM. `ic307` is the one hardware-rooted waveform dump.

| script | question it answers |
|---|---|
| `zonerec.py`, `zonerec2.py` | What is the layout of a SET's zone records -- stride, field offsets, how `(lo, hi, class, entry, trim)` is packed? |
| `ambig.py` | Which selectors have more than one C in the firmware tables, and what distinguishes the candidates? (the 77 ambiguous rows) |
| `waverec.py` | What does an IC307 wave-directory record contain? |
| `flagcensus.py`, `flagmod.py` | What flag bits appear in those records, and how do they group? |
| `loopprobe.py` | Do the records describe loop points, and where? |
| `page3.py` | Structure of one specific IC307 page, used as a worked example |

All are read-only and take no arguments: `python3 <script>`.

⚠ These are PROBES, not tools: terse, no argument parsing, paths hardcoded to
`~/compartilhado/kn5000_original_roms/kn5000/`. The polished descendants live in
`tools/kn5000-pitch-probes/` (is the pitch table reducible, and where does it come from) and
`tools/kn5000-rootpitch/` (can the root pitch be recovered from the register stream or the audio).
Start there; come here only when you need the raw ROM layout underneath.

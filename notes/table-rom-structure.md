# KN7000 table ROM structure — see notes/table-rom-format.md

The table ROM's resource-archive format was already decoded in **`notes/table-rom-format.md`**
(directory of u32 chunk offsets; `TCMP` code/style container; `TPAD` / "Technics Pads"; 119 embedded
standard JFIF JPEGs; TCMP per-record + rhythm-pattern event grammar). That file is authoritative —
this one is a stub to avoid duplication.

An independent re-derivation (2026-07-08, walking the de-interleaved 4 MB image) reproduced the same
85-entry directory and confirmed all 117–119 JPEG streams decode with an ordinary JFIF decoder
(reinforcing that the boot-splash "garbage" is a firmware/emulation decoder bug, not a bad format).

**One small correction to note:** directory entry **[83] @0x483E828C** reads `"Technics Rhythms"`
in the ROM (`54 65 63 68 6e 69 63 73 20 52 68 79 74 68 6d 73`), i.e. a rhythm resource — not
"Technics Pads" as an earlier draft listed it. Named `TechnicsRhythmsTable` in kn7000_manual.sym.

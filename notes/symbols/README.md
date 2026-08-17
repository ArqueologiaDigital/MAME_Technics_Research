# Recovered firmware symbols — they live in `kn7000_disassembly`

Not here. The authoritative copies are **committed** in the sibling repository:

```
~/compartilhado/kn7000_disassembly/kn7000.sym          the symbol table
~/compartilhado/kn7000_disassembly/kn7000_manual.sym   hand-added names
~/compartilhado/kn7000_disassembly/tools/gen_symbols.py  the generator
```

The names come from the firmware's own **MILK-toolkit reflection tables** — they are the
manufacturer's, not invented here.

## Why this file exists at all

On 2026-08-17, ahead of a shutdown, a copy of these tables was found in `/tmp` and rescued into
this repository on the reasoning that their stated generator (`tools/gen_symbols.py`) was not in
`kn7000_mame` and a filesystem search had not located it.

**That was wrong, and the rescued copies have been removed.** A completed search found the
generator in `kn7000_disassembly`, and the `/tmp` copy was **byte-identical** (md5
`7af9e547921b1c8856c7b925ec5def82`) to the committed `kn7000.sym` there. Nothing was ever at
risk, and duplicating a committed file into a second repository invites the two to diverge.

The mistake was scoping the search to `kn7000_mame` and then trusting a `find` that had timed
out. **When checking whether something is already preserved, search every sibling repository —
this project has several, and disassembly artefacts live in `kn7000_disassembly`, not here.**

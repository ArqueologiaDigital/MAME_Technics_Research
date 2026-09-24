# Key-bed port probes

## keybed_names.lua

**Question it answers:** the key bed was rewritten from two bespoke macros
(`KN_KEYM`/`KN_KEYPC`) to plain `PORT_BIT` lines using MAME's `PORT_GM_*` note
constants, dropping `PORT_NAME`. Do the 61 fields still carry a usable name in
the UI, and does each land on the mask the key index intends?

Dropping `PORT_NAME` was the one real risk in that change: no other MAME driver
combines `PORT_NAME` with `PORT_GM_` (measured: 0 of 1010 GM-note fields), so
the name has to come from the note constant — but that is a claim worth reading
off the running machine rather than assuming.

`-listxml` cannot answer it: it emits `<port>` elements with no `<field>`
children for these ports. That is not specific to the key bed — the unchanged
`REARSW` port is equally empty — so an empty result there is a property of
listxml, not a regression.

Run:

```
cd ~/compartilhado/mame-pr-kn7000drv
./kn kn7000 -rompath ~/compartilhado/technics_romsets -skip_gameinfo \
    -window -nomaximize -str 6 -sound none \
    -autoboot_script ~/compartilhado/kn7000_mame/notes/keybed-ports/keybed_names.lua
```

**Pass:** `KEYBED: fields=61 unnamed=0`, and the sampled names track the masks.

**Measured 2026-09-25** (tip `2e1b616adcb`):

```
KEYBED: :KEYS0 mask=0x0001 name="C2"     key index 0x00
KEYBED: :KEYS0 mask=0x0002 name="C2#"    key index 0x01
KEYBED: :KEYS1 mask=0x0200 name="C4#"    key index 0x19
KEYBED: :KEYS1 mask=0x8000 name="G4"     key index 0x1F
KEYBED: :KEYS2 mask=0x0001 name="G4#"    key index 0x20
KEYBED: :KEYS2 mask=0x0008 name="B4"     key index 0x23
KEYBED: :KEYS3 mask=0x0010 name="E6"     key index 0x34
KEYBED: fields=61 unnamed=0
```

MAME spells sharps after the octave (`C2#`, not `C#2`); the old hand-written
`PORT_NAME`s said `Key C#2`. Same note, MAME's own spelling, applied uniformly.

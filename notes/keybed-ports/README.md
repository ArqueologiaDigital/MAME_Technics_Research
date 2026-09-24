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
KEYBED: :KEYS0 mask=0x0001 name="C2"      key index 0x00
KEYBED: :KEYS0 mask=0x0004 name="D2"      key index 0x02
KEYBED: :KEYS1 mask=0x0004 name="F3#"     key index 0x12
KEYBED: :KEYS2 mask=0x8000 name="B5"      key index 0x2F
KEYBED: :KEYS3 mask=0x1000 name="C7"      key index 0x3C
KEYBED: fields=61 unnamed=0
KEYBED: control C4 pressed=0x0100 released=0x0000 -> READ CAN MOVE
KEYBED: :KEYS0..3 read 0x0000 at reset
KEYBED: ports-asserted-at-reset=0 control=VALID
```

MAME spells sharps after the octave (`F3#`, not `F#3`); the old hand-written
`PORT_NAME`s said `Key F#3`. Same note, MAME's own spelling, applied uniformly.

## The reset check needed a control, and failed without one

The second question — `IPT_KEYBOARD` became `IPT_OTHER`, so does any field read as
asserted at reset and inject a phantom note? — first came back "all four ports read
0x0000", which is what a correct result looks like *and* what a port that can never
read anything looks like.

The control settles it: press `C4`, read, release, read. The first attempt printed
`pressed=0x0000 released=0x0000 -> READ IS STUCK`, because `set_value` lands on the
next input update and the read ran in the same instant. With an `emu.wait(0.2)`
between them it reads `0x0100` pressed and `0x0000` released — `0x0100` being the
mask the key index 0x18 is assigned, so the control checks the mapping too.

Only with `control=VALID` does `ports-asserted-at-reset=0` mean anything. It does
here, which is why this change needs no audio A/B: with no key asserted, the port
type cannot reach the tone generator.

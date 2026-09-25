# TLCS-900 instruction timings, transcribed

`tlcs900-states.jsonl` — 227 instruction forms with their execution time in
states, from `TLCS900hv-is.pdf` pages 165-174 ("Instruction Lists of 900").
This is the data MAME's TLCS-900 core has never had: its cycle counts come from
NeoPop, whose author says they are invented.

One JSON object per line:

| key | meaning |
|---|---|
| `group`, `mnemonic`, `operands` | the instruction form |
| `size` | which sizes exist, e.g. `BWL`, `BW-`, `---` |
| `codes` | opcode pattern, verbatim, e.g. `C8+zz+r :88+R` |
| `length` | encoded length, verbatim, e.g. `2`, `2+M`, `1+#` |
| `state_raw` | the State cell verbatim |
| `state_b`, `state_w`, `state_l` | parsed states for byte / word / long word, or null |

**1 state = 2/fc** (one φ period). See `../REFACTOR.md` for the three places the
datasheet says so.

## How it was produced, and how far to trust it

Pages rendered at 200 dpi and split into overlapping halves so no row fell in
the split. Every half-page was transcribed by one agent and then re-read by a
second, independent one instructed to assume errors and correct the file in
place. That pass found and fixed **19 errors across 3 pages**; no rows were
missing and no page was unusable.

`merge_timings.py` merges the per-half files, removes the boundary duplicates
(21 of them) and checks what can be checked mechanically:

```
python3 merge_timings.py <rows-dir> tlcs900-states.jsonl
```

It fails on implausible state values or on more than a handful of rows whose
`size` disagrees with which state slots are filled — that disagreement is the
signature of a transcription slip. Current state: 227 rows, range 2..32, mode 4,
0 implausible, 1 explained mismatch.

## Known book oddities, carried through deliberately

- **Shift/rotate long-word forms take `8+2n`** states, n being the shift count.
  Kept verbatim in `state_raw` with the parsed field null. Variable-time
  instructions are real and a faithful core has to model them.
- **`DJNZ` splits on the branch taken, not on size**: `11 (r≠0)`, `7 (r=0)`.
- **Sizeless instructions** (`RCF`, `SCF`, `CCF`, `ZCF`, `NOP`, `HALT`, …) print
  a single state with no B/W/L split; parsed fields are null, `state_raw` holds it.
- **Two misprints in the book**: `B0+men` for `B0+mem` in two LDCF rows, and
  `SUB R.(mem)` with a period where every neighbouring row has a comma.
- **One contradictory cell**: `SCC cc,r` prints `6.-6.-` against size `BW-`.
  Only `state_b = 6` was taken; the word form needs a second source.

## What is not here yet

The mapping from these mnemonic-indexed forms onto MAME's opcode-indexed tables
in `900tbl.hxx`, and the addressing-mode adders on page 174 which the `+M`
lengths refer to. That is the next phase.

## `gen_p172a.py`

The rotate/shift group on page 172 is perfectly regular — six mnemonics × three
operand forms, with opcodes marching in step — so that half-page was transcribed
by writing the generator rather than eighteen near-identical lines by hand. It
emits `rows/p172a.jsonl`, which merges into the dataset like any other page, and
it went through the same independent verify pass (which corrected errors on this
page among others).

```
python3 gen_p172a.py <out.jsonl>
```

Kept because it is the provenance of 18 of the 227 rows: the regularity it
encodes is itself a claim about the book, and a reader should be able to check it
against the scan.

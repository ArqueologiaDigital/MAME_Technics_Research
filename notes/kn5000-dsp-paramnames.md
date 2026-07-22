# KN5000 effect parameters — the name→slot binding, LOCATED

Task: find the table/code that says *which* of the 85 parameter names (`0x0324D5`) belongs to
*which* effect's parameter slots. Companion note to `kn5000-dsp-parameters.md` (esp. §4/§10, which
recorded the binding as NOT FOUND). Tool: `tools/kn5000_dsp_paramnames.py`. Claims tagged
**MEASURED / INFERRED / SPECULATIVE**.

## Headline

**The binding is FOUND, and its shape explains why §4's search failed.** It is **not** a fixed-stride
ROM table. It is a **per-effect list of name indices held in the firmware's UI object-property
database**, materialised into a flat RAM array (`0x29AC`) when an effect is selected, and consumed by
the effect-edit draw loop. Both the draw path and the loader path are located, with addresses, on the
main CPU (TMP94C241F / TLCS-900), ROM base `0xE00000`.

The disassembly used is `kn5000-roms-disasm/archive/asl/maincpu/kn5000_v10_program.asm`
(ROM offset `X` ↔ CPU address `0xE00000 + X`; `PROGRAM_FLASH__BASE_ADDR EQU 0E00000h`).

## A. The reader — how the edit page turns a slot into a name (MEASURED)

`DspItem0CngFunc` (asm ~204015, entry `0xF355xx`) draws the DIGITAL EFFECT parameter page. The
name-drawing loop `LABEL_F3561F` (asm ~204102) and the unit loop `LABEL_F3566C` (asm ~204130) are:

```
LABEL_F3561F:                       ; draw parameter NAME for each visible slot
    PUSHW  0011h                    ; stride 17  (== PNAME table stride)
    LD A,(021098h)                  ; window/page base index for this screen
    ADD WA,(XSP+014h)               ; + slot/row offset
    LDA XBC,29ACh                   ; RAM name-index array
    ADD XWA,XBC
    LD A,(XWA)                      ; A = RAM[0x29AC + idx]  <-- THE NAME INDEX (1-based)
    MULS_WA 0011h                   ; * 17
    LDA XBC,0E324C4h                ; 0xE324C4 = 0xE324D5 - 17  (= name entry -1)
    ADD XWA,XBC                     ; ptr = 0xE324C4 + 17*storedidx
    ... CALL LABEL_FF0CF3           ; draw_string(ptr, ...)
LABEL_F3566C:                       ; draw parameter UNIT, SAME stored index
    LDA XBC,0E32418h                ; 0xE32418 = 0xE3241A - 2  (unit entry -1), stride 2
```

So, **MEASURED**:

```
  name[slot] = string @ 0xE324D5 + 17*(RAM[0x29AC+slot] - 1)      (PNAME_BASE, stride 17)
  unit[slot] = string @ 0xE3241A +  2*(RAM[0x29AC+slot] - 1)      (PUNIT_BASE, stride 2)
  value[slot]= word   @ RAM[0x2978 + 2*slot]
```

The stored byte in `0x29AC` is a **1-based** index into the 85-name table (`0xE324C4 = base − 1
stride`; the same −1 for units). That off-by-one is a small correction to the raw name-table anchor
in `kn5000-dsp-parameters.md` §4 — the *table* addresses there are right; the *stored index* is 1-based.

The related items `01e00045h`/`01e8004ch`/`01e00047h` (asm 204066–204071) and the jump table at
`0xE34DA4` (asm 204078) are the per-widget draw handlers; `0xF355F3` is the base handler that runs the
name/unit/value loops. `0xE32A7A` (asm 204089, the effect-name pointer table) is read on the same page
to draw the effect *title*.

## B. The loader — where `0x29AC` comes from (MEASURED)

`LABEL_F457CF` (asm ~230296) clears `0x2976..0x29AC+0x19` then fills it for the current effect. It
dispatches on the effect-page TYPE byte `RAM[0x8D38]`:

| `RAM[0x8D38]` | handler | slot source base | count | note |
|---|---|---|---|---|
| `0x0a` | F45831 | `0x4B10 + i` | `RAM[0x29AA]`, ≤25 | value `0x4B00`, count `0x4B04` |
| `0x0b` | F458CA | `0x4910 + i` | `RAM[0x29AA]`, ≤25 | value `0x4900`, count `0x4904` |
| `0x0c` | F4593A | `0x4C10 + i` | 8 fixed | value only |
| `0x0e` | F4599A | `0x4E10 + i` | 4 fixed | |
| `0xd6` | F4599A/… | `0x4E10 + i` | 4 | |

Per slot `QIZH` it does:

```
    value      = LABEL_FDC7F9(objid)   -> RAM[0x2978 + 2*QIZH]        ; current value (word)
    name index = LABEL_FDC6E7(objid)   -> RAM[0x29AC + QIZH]          ; NAME INDEX (byte, 1-based)
```

`LABEL_FDC7F9` / `LABEL_FDC6E7` (asm 408564 / 408442) are a **generic UI object-property database**:
resolver `LABEL_FDC5AB`, decoders `LABEL_FDC504` / `FDC41D`, pointer/handler tables at `0xEE6044`,
`0xEE61D4`, `0xEE637A` (the property reader ranges `0x4900/0x4C00/0x4D00/0x4E00` are split in
`LABEL_FDC650`..`FDC6CD`). The **name index for a slot is a *property* of that slot's parameter object
in the DB** — read the same way as the value, the min, the max, etc.

## C. Why the §4 fixed-stride scan found nothing (the instrument was blind)

§4 searched the whole main-CPU ROM for a fixed-stride byte table whose reverb rows (algo 16..27)
repeat identically twelve times, at strides 4..16, and found none. **Correct — because no such table
exists.** The binding is (a) **variable-length** (a count-prefixed list per effect, `RAM[0x29AA]`
long) and (b) **object-indirected** (the indices live as object properties reached through a resolver
and pointer tables, not as consecutive bytes). Those are precisely the two shapes a fixed-stride scan
cannot see — the exact caveat the brief warned about. So §10's "NOT FOUND" should be amended to
**"FOUND: not a table; a per-effect object-property list"**.

## D. Constraint-propagation attack (the second, independent line) — HONEST result

Run `tools/kn5000_dsp_paramnames.py`; it applies the units/ranges table (`0x03241A`) as the hard
filter to the per-algorithm DSP streams. Findings:

* **One clean PIN, unit-forced and universal:** `op 0x21 → DSP 0x90`, the `0..0.8` lerp level,
  present in 37/59 effects. This **forces a SLOT** (every effect has this level control at `0x90`) but
  **not a name** — §5 already showed its name is undecided between `DEPTH`(6) and a per-block
  `…DRY/WET`. So it is a slot pin, not a name pin.
* **ms-helper (`op 0x68`)** forces a slot's unit to *ms* → one of `{DELAY L/R, PRE DELAY, GATE/MASK
  TIME, HARS TIME L/R, DELAY 1..4}`; **deg-helper (`op 0x69`)** → `{PHASE, PAN 1..4}`. These narrow but
  do not uniquely force, because most effects expose more than one ms name.
* **The COUNT cross-check cannot be closed statically.** The displayed slot count is `RAM[0x29AA]`,
  itself a DB value; and the T2 **record** count is **not** the UI parameter count — many records are
  internal constants with no on-screen name (e.g. the reverb's `op75/op67/op76` coefficient loads).
  Without the real per-effect count the propagation is under-constrained.
* **No contradiction was produced — reported as a MISS, not a success:** too few names could be forced
  for a contradiction to even arise. The propagation does not, on its own, deliver the per-effect
  named lists; it agrees with attack A only on the `0x90` slot pin.

**Predict-then-check that DID hold** (structural, from `kn5000-dsp-parameters.md` §5, restated here as
cross-checks, not new claims): the twelve reverbs share one stream and their `0xAC/0xB2` constant
orders DARK > BRIGHT — consistent with `HIGH DAMP GAIN`(35) being a reverb slot. The compressor
(algo 36) stream is the natural home of `THRESHOLD`(39)/`RATIO`(40); the PARAMETRIC EQ (algo 39) with
5×`op0x70` bands is the home of `BAND EMPHASIS FC/Q/G`(50/51/52). These remain **INFERRED** family
arguments — the object DB is what would upgrade them to proven.

## E. Deliverable status and the follow-up that closes it

* **Located:** the binding, its shape, and both code paths (reader §A, loader §B), with addresses.
* **Not yet extracted:** the actual 59 per-effect name-index lists, because they live in the UI object
  DB rather than a readable table.
* **Follow-up to fully answer Felipe (well-posed now):** decode the object-property database —
  `LABEL_FDC5AB` + the pointer tables `0xEE6044 / 0xEE61D4 / 0xEE637A` — enough to resolve
  `FDC6E7(0x4B10+i)` statically for each effect. That yields `RAM[0x29AA]` (the true slot count, which
  also closes the propagation's count-check) and the ordered name-index list per effect. Alternatively,
  a single emulator run dumping `RAM[0x29AC..0x29AC+RAM[0x29AA]]` for each effect would read the lists
  off directly (blocked here: no emulator run allowed).

## Addresses cited (quick reference)

| what | address |
|---|---|
| parameter NAME table (stride 17) | ROM `0x0324D5` / CPU `0xE324D5` |
| parameter UNIT table (stride 2) | ROM `0x03241A` / CPU `0xE3241A` |
| draw base used by code (name −1) | CPU `0xE324C4` |
| draw base used by code (unit −1) | CPU `0xE32418` |
| effect NAME table (stride 18, desc) | ROM `0x033568` / CPU `0xE33568` |
| effect-name pointer table | CPU `0xE32A7A` |
| RAM name-index array / count / values | `0x29AC` / `0x29AA` / `0x2978` |
| effect-page type byte | `0x8D38` |
| draw fn / name loop / unit loop | `DspItem0CngFunc` / `F3561F` / `F3566C` |
| per-effect loader | `LABEL_F457CF` (asm 230296) |
| property reader (name index / value) | `LABEL_FDC6E7` / `LABEL_FDC7F9` |
| property resolver + tables | `FDC5AB`, `0xEE6044`, `0xEE61D4`, `0xEE637A` |

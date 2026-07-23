# NEC uPD6383GF — capturing the host uC-IF stream to find the data-pointer ORIGIN

KN5000 IC311 effects DSP (NEC uPD6383GF-3BA). Date: 2026-07-23.
Tools: `tools/kn5000_dsp_origincap.lua` (drives the panel to select a DSP-EFFECT type),
`tools/kn5000_dsp_origincap.py` (decodes the capture, hunts the pointer poke, maps effect
blocks). Follows `kn5000-dsp-origin.md`, whose §4 proposed exactly this experiment.

Claims are tagged **MEASURED**, **INFERRED**, **PROVEN BY CONSTRUCTION**, **FALSIFIED**.
**No audio path was added; the core is still instantiated DISABLED; the KN5000 driver was not
touched; the disassembler was NOT edited (the origin poke was not proven — it was falsified).**

---

## Headline

1. **★★ THE PREDICTION IS FALSIFIED BY DIRECT CAPTURE.** `kn5000-dsp-origin.md` §4 predicted
   that selecting PARAMETRIC EQ in MAME would emit a pointer-init poke setting the data pointer
   to `0x19` — "most likely a word `801.0.19.821` or a `0x825`/`0x820`/`0x822`-route load carrying
   `0x19`". **There is NO pointer load of `0x19` anywhere in the captured EQ host stream** (344
   transfers, 15 734 bytes). Nor any per-effect `0x19` poke of any form. **MEASURED / FALSIFIED.**
2. **★★ POSITIVE CONTROL PASSES: the captured EQ body is byte-identical to static algo39.** The
   `cmd 0x01, I-RAM[84..188]` upload (transfer 328, 105 words = 525 bytes) equals
   `tools/kn5000_dsp_extract.py`'s `algo39.bin` **byte-for-byte** — so the stream analysed is
   unambiguously the PARAMETRIC EQ's. Screen snapshot-verified ("DSP EFFECT / TYPE: PARAMETRIC EQ",
   five BAND EMPHASIS FC/Q/G rows) and RAM-verified (`RAM[0x8D38]=0x0B`, `RAM[0x29AA]=17`,
   `RAM[0x29AC..]=[51,52,53]×5,1,3`). **MEASURED.**
3. **★★ WHAT THE STREAM ACTUALLY CONTAINS — the origin is NOT per-effect.** One sweep uploaded
   16 effects (I stepped the TYPE selector down to CHORUS then up to PARAMETRIC EQ). **Every**
   effect frames its coefficient upload IDENTICALLY:
   * opens `801.0.26.825` (a constant `0x26` cursor load — same for all 16);
   * sets the coefficient base with `801.0.00.821` (**`0x00`, the same for all 16 effects**);
   * streams the per-effect coefficient sections, each opened by a pointer load that is **always
     anchored at `0x00`** and advances by the section size (EQ: `00,06,0C,12,18` = 5 bands × 6);
   * closes `801.0.90.821` (a constant `0x90` terminal — same for all 16).

   The only EQ-specific extra is `801.0.1E.821`: `0x1E = 30 = 5 bands × 6`, the coefficient
   **extent/end**, not an origin. **There is no per-effect origin poke, and specifically no
   `0x19`.** The effect→base table (`--map` mode) is below. **MEASURED.**
4. **★ THE `0x19` (and the gated-reverb `0x07`) WAS A SINGLE-POINTER MODELLING ARTIFACT.** The
   real machine addresses through **several pointer registers** (`0x821`, `0x825`, `0x827`,
   `0x820`, `0x822`) plus the **C-RAM/D-RAM split** (INDEX backlog item 1). Coefficients go to a
   host-poked base **`0x00`** (per-effect uploads); the effect-INDEPENDENT resident header loads
   the **state** pointers `0x70` (via `0x821`), `0x6C` (via `0x827`), `0x25` (via `0x825`) — and
   `0x6C`/`0x70` are exactly two members of `-origin.md`'s static state block `{64,68,6C,70,74}`.
   So the "header is effect-independent yet effects need different origins" paradox **DISSOLVES**:
   effects do NOT use different origins in the actual stream. The stride-4 walk that fit
   `{64,68,6C,70,74}` uniquely to origin `0x19` was an artifact of collapsing this multi-register,
   two-space addressing onto one wrapping pointer. **INFERRED (strong, from the capture).**
5. **The gated-reverb `0x07` prediction is falsified the same way.** Its block (effect#5, a
   reverb-family algo) is `26.825 / 00.821 / 02.821 / 00.821 / 90.821` — base `0x00`, no `0x07`.
6. **COVERAGE UNCHANGED AT 18.3 % (545/2974).** No body word was decoded; the disassembler was
   not upgraded (the task gated that on PROVING the origin, which the capture instead falsified).

---

## The effect→coefficient-base table (MEASURED, one sweep, 16 effects)

`python3 tools/kn5000_dsp_origincap.py <capture>.txt --map <progsdir>` (progsdir from
`kn5000_dsp_extract.py`). Each row: the leading pointer-load of every host-poke transfer in
that effect's block. Read `hi12.class4.addr8.lo12`.

```
effect# 0 algo  1 : 26.825  00.821  09.821  00.821  90.821
effect# 1 algo  2 : 26.825  00.821  0D.821  02.821  00.821  0C.821  90.821
effect# 2 algo  3 : 26.825  00.821  09.821  08.821  90.821
effect# 3 algo  4 : 26.825  00.821  08.821  05.821  00.821  90.821
effect# 4 algo  5 : 26.825  00.821  05.821  00.821  02.821  06.821  90.821
effect# 5 algo  6 : 26.825  00.821  02.821  00.821  90.821
effect# 6 algo  8 : 26.825  00.821  17.821  07.821  0E.821  16.821  15.821  90.821
effect# 7 algo  9 : 26.825  00.821  26.825  28.825  00.821  09.821  03.821  06.821  0C.821  0F.821  90.821
effect# 8 algo 10 : 26.825  00.821  26.825  28.825  29.825  2A.825  03.821 .. 0B.821  90.821
effect# 9 algo 32 : 26.825  00.821  00.821  02.821  90.821
effect#10 algo 33 : 26.825  00.821  00.821  08.821  90.821
effect#11 algo 34 : 26.825  00.821  00.821  02.821  90.821
effect#12 algo 35 : 26.825  00.821  00.821  02.821  03.821  09.821  90.821
effect#13 algo 36 : 26.825  00.821  04.821  04.821  02.821  03.821  90.821
effect#14 algo (ambiguous, 42 images) : 26.825  00.821  04.821  05.821  06.821  90.821
effect#15 algo 39 (PARAMETRIC EQ) : 26.825  00.821  1E.821  00.821  06.821  0C.821  12.821  18.821  90.821
```

Invariants across all 16: **`26.825` opens, `00.821` sets the coefficient base to `0x00`,
`90.821` closes.** Only the count/spacing of the interior loads is per-effect (it is the number
and size of the effect's coefficient sections). This is the decisive evidence that the origin is
NOT a per-effect value.

## How the coefficients are uploaded (MEASURED)

The per-effect blocks write short micro-sequences into the **host-poke I-RAM region `[352..382]`**
(`cmd 0x01`, address prefix `01 60` = 352): a pointer-load word (`801.0.NN.821`) followed inline
by the Q0.23 coefficients (`cmd 0x02` records and 3-byte groups). Executing that scratch sequence
copies the coefficients into C-RAM at base `0x00`. The header (I-RAM `0..59`, byte-identical for
every effect) and the body (here I-RAM `84..188` = algo39) are uploaded separately; the body is
never patched per-parameter — only the coefficient C-RAM is. Two `I-RAM[64]` patch words
(`00 40 0C 40 A8/54 04 45`) and a full zero-clear of `[352..382]` bracket the EQ block.

## Reproduce

```
cd <run dir>; export DISPLAY=:0
../kn7000_mame_build/kn7000 kn5000 -rompath ../kn7000_mame_build/roms -skip_gameinfo -window \
  -nvram_directory ./nvram -pluginspath ../kn7000_mame_build/plugins \
  -snapshot_directory ./snap \
  -autoboot_script ../kn7000_mame/tools/kn5000_dsp_origincap.lua
# TYPEIDX=15 (default) lands on PARAMETRIC EQ; the capture kn5000_dsp1_upload.{bin,txt}
# is written to the run dir at exit.
python3 tools/kn5000_dsp_origincap.py kn5000_dsp1_upload.txt --ptr 0x19      # the FALSIFIED hunt
python3 tools/kn5000_dsp_origincap.py kn5000_dsp1_upload.txt --map <progsdir> # the effect table
```

Archived capture + screenshot: `notes/data/kn5000_dsp1_upload_parametriceq.txt`,
`notes/data/kn5000_dsp_parametriceq_screen.png`.

## Where the origin search goes next (redirected by this capture)

The origin is not a per-effect poke to chase. The open question is now precisely the
**C-RAM/D-RAM distinction** (INDEX backlog item 1): the body reads its **state** through the
header's effect-independent D-RAM pointers `0x6C`/`0x70` and its **coefficients** through the
host-poked C-RAM base `0x00`, and the addressing rule of `-addressing.md` (`class4 & 7 == 2`
pointer post-increment) must be re-read as **which pointer register / which space** each class
selects, not as one 8-bit origin. The disassembler should print absolute addresses only once
that register/space selection is decoded — NOT under a fabricated per-effect origin.

## Misses / limits

* **The prediction missed cleanly.** No `0x19`, no per-effect origin poke. Reported as prominently
  as a hit would have been (RULES OF EVIDENCE).
* This capture proves what the stream does *not* contain (a per-effect origin) and *does* contain
  (fixed base `0x00`, header state pointers). It does not by itself decode the C-RAM/D-RAM selector
  — that is the redirected next target, and it is a static/execution question, not a capture one.
* The disassembler was deliberately left un-upgraded: absolute addressing under the falsified
  `0x19` origin would have printed wrong addresses.

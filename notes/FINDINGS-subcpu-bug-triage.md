# KN5000 sub-CPU: triage of the 130 unintegrated `[UNCERTAIN]` findings

2026-08-06. Input: `kn5000-roms-disasm/symbols/proposals/subcpu-region-01..16.txt`.
Every promoted BUG re-verified from `original_ROMs/kn5000_subprogram_v142.rom` with unidasm,
plus whole-image reference scans. Nothing in the disasm repo was modified.
Numbering U001..U130 in file order (region 01 -> U001-U003, 02 -> U004-U010, 03 -> U011-U020,
04 -> U021-U030, 05 -> U031-U040, 06 -> U041-U051, 07 -> U052-U061, 08 -> U062-U074,
09 -> U075-U082, 10 -> U083-U089, 11 -> U090-U095, 12 -> U096-U101, 13 -> U102-U108,
14 -> U109-U115, 15 -> U116-U123, 16 -> U124-U130).

| class | blocks | distinct |
|---|---|---|
| **BUG** | 10 | **9** (U001 = U026) |
| NAMING | 71 | |
| UNRESOLVED-QUESTION | 43 | |
| NOT-A-PROBLEM | 6 | |

7 of the 9 are FIRMWARE defects (MAME reproduces them by running the ROM — behaviour to expect
and document, not emulation bugs); 2 are defects in OUR metadata that would corrupt the
disassembly if integrated as-is.
**None of the 130 is an observation of the duplicate-INT0 wedge fixed in 3fd44f3.**

## BUG-1 (U061) — `FindBestSlot` returns 0xFF, used unchecked as a word-table subscript, lands in the pitch accumulator. RANK 1, most likely to be biting us today.

`Voice_Selector_FindBestSlot` 0x02AC54 scatters 9 nibbles into a frame buffer; if ALL NINE ARE
ZERO both candidates stay 0xFF:
```
2ac80: ld E,0xff      ; "first nibble >= 4"
2ac82: ld L,0xff      ; "first nibble != 0"
2acc9: cp E,0xff / jr Z,0x02ace6
2ace6: ld (XWA),L                 <-- INDEX = 0xFF
2acf5: ld A,(XBC+WA)              <-- VALUE = buf[0xFF], off-frame stack read
```
Sole caller `Voice_Selector_ComputeMixWeights` 0x02AD03 uses it as a subscript into 9-entry
word tables (0x00F79A, 0x00F7AC), extents measured and butting exactly:
0x00F786(+0x14) 0x00F79A(+0x12) 0x00F7AC(+0x12) 0x00F7BE(+0x14) 0x00F7D2.
In range `0x00F79A[0..8]` = -12,0,+7,+12,+19,+24,+28,+31,+36 semitones at 0x100/semitone.
With INDEX=0xFF: `0x00F79A+0x1FE` = **0x5502 = +85.0 semitones**, stored to `part+0x112`.

`Voice_Slot_ComputePitch` 0x02B3DD consumes it **unconditionally** — no layer-enable test, no
clamp: `2b411: add IZ,(XBC+0x0112)`. Every note on that part transposes **+85 semitones**.

REACHABILITY: 6 callers; `Voice_InitFromSlot` 0x02ADC1 is reached from 0x0349AF, the per-part
"apply the whole tone" sequence = **every program change**. Trigger is simply
"part+0x102/+0x104/+0x106 all zero". Whether the shipped ToneDB (main-CPU side, not in this
image) produces that state is the ONE thing not settled here.
Note even INDEX=0 is not neutral (-12 semitones) — evidence the author assumed all-zero cannot occur.

## BUG-2 (U037) — `Voice_ToneTableRamp_Down` reads past a 26-entry curve, and its pitch half reads the WRONG curve. RANK 2, audio-tick hot path.
```
RAMP_UP   0x027798  pitch : idx 1..0x4F into 0x010D64 (80-entry)   OK
                    filter: /6 -> max 25 into 0x010DB4 (26-entry)  OK
RAMP_DOWN 0x02783D  pitch : >>1 -> max 39 into 0x010DB4            OOB, and WRONG TABLE
                    filter: /5 -> max 29 into 0x010DB4             OOB
```
Byte-verified at 0x027859 (`c9 ef 01` srl 1,A), 0x02786B, 0x02788B (`c9 0a 05` div A,5), 0x02789D.
The overflow is a cliff, not noise:
```
0x010DB4[0..25] = 00 0A 14 ... EB F6 FF      (clean linear ramp)
0x010DB4[26..39]= 20 20 20 20 21 21 ... 23   (the NEXT table)
```
So descending from the top the broadcast parameter starts at **0x20 instead of 0xFF**, sits
there ~20 (filter) / ~27 (pitch) steps, then snaps to 0xFF. Up-sweep and down-sweep are not each
other's reverse. One caller: `calr` at 0x027CA1 inside `Voice_UpdateAllNoteStates` 0x027AC4 =
audio-tick phase B, every tick while a ramp-down is active.

## BUG-3 (U097) — `DSP_GetEffectRouting` 0x035585 reads 0x041377 twice; 0x04137A's value never used. RANK 3 (highest likelihood — unconditional; lowest severity).
```
35587: cp (0x041377),0 ; jr Z ...
3558f: ld A,(0x041377) ; sll 8 ; or HL,WA    ; HIGH byte  <- control A
3559b: cp (0x04137a),0 ; ret Z               ; gate       <- control B
355a3: ld A,(0x041377)                       ; LOW byte   <- control A AGAIN
```
0x04137A is tested but never loaded. Writers: `(0x041377 + part*0x11F)` at 0x028992 and
`(0x04137A + part*0x11F)` at 0x0289A3 — two independent per-part send controls. The second send
is enabled by its own control but takes its LEVEL from the first. Call sites 0x035615, 0x035696.

## BUG-4 (U028) — both slot resolvers STORE into the record before bounds-checking. RANK 4.
`Voice_Chan_ResolveSlot` 0x024CAB: store at 0x024CC9, range test `cp (XSP+0x0e),0x0080` at
0x024CCC — after. `Voice_SubVoice_ResolveSlot` 0x024FFF: store 0x02501F, test 0x025022.
0xFF is the ORDINARY sentinel (producer 0x02177E; exits `or HL,0x00FF` at 0x0217A6/0x021991,
`ld L,0xFF` at 0x0218A8/0x021964), and reject conditions include ordinary ones, not just
starvation. Wild store lands at **0x045D39 / 0x045D42** (region 04's own arithmetic was wrong),
0xD6B past the array end (bound 0x04424E + 0x80*0x1B = 0x044FCE).
DAMAGE PROBABLY NIL: a whole-image absolute-operand scan finds NO variable referenced in
0x045570..0x047A03. Promoted because the write is unambiguously OOB on a normal path.

## BUG-5 (U103) — `EFF_Disconnect`/`EFF_Link` index with mode stride 12 into stride-20 tables. RANK 5 (severity high, reachability unproven).
0x037FAE computes `12*mode + 4*slot`; the tables at 0x01F3F0 / 0x01F404 are 5 pointers each,
**20 bytes apart**. 0x01F418 = `0x0080004D` is NOT a pointer. `DSP_Config_ClampLimits` 0x036DA3
PERMITS mode 1. With mode 1, `EFF_Link(slot 2..4)` hands a non-pointer to 0x03C181.
Open exactly as region 13 said: is `block[+0x06]` ever 1 on these paths?

## BUG-6 (U122) — three unbounded loops; plus a STALE claim about our own driver.
(a) `ToneGen_Note_Loop` 0x03D02E exits only when 0x110002 bit 0 clears — no cap.
(b) `DSP_Translator_CheckEnd` 0x03CBB6 and (c) `DSP_BytecodeInterpreter_CheckEnd` 0x03C9CE —
sentinel-only, bite only on a malformed stream.
⚠ Region 15's "MAME maps 0x110000-3 as noprw() so this cannot fire" is **STALE**: kn5000.cpp:584
maps them to `kbd_data_r`/`kbd_status_r`. The loop DRAINS and terminates, but it is LIVE.
`push_keybed_event()` bounds `m_pending_notes` (64) and **not** `m_keybed_queue` — anyone
touching the keybed path must keep "status falls while the loop drains" explicit.

## BUG-7 (U076) — `INTERCPU_REPLY_EDITBUFFER_BLOCK` 0x02ED44 copies 470 bytes out of an 80-byte-stride array. RANK 7.
Same base arithmetic as `AUDIO_CMD_TONEEDIT_REPLY_SEND` 0x030508, which uses length 0x3A (58) —
fits the 0x50 stride. 470 does not. The image at (0x04531C) is 0x72AA bytes and 0x030515 reads
its index at offset 0x72A7, so the array is 0x4AA7..0x72A7 = **128 records x 0x50**. A 470-byte
read from record 127 ends **387 bytes past the end of the image**, shipped to the main CPU as
tone-edit data. Needs the main-CPU receiver at 0x001E4AA7 to call bug vs deliberate.

## BUG-8 (U001 = U026) — OUR METADATA. Eleven data labels in 0x00F693..0x00F787 are bound 8 bytes past the address the code indexes.
Code: `024318: lda XIX,0x00F6B3`, `02445E: ...0x00F6BF`, `02456E: ...0x00F6CB`.
Reference lines 73-77: `LABEL_00F693 0x00F69B`, `LABEL_00F6A7 0x00F6AF`, `LABEL_00F6B3 0x00F6BB`,
`LABEL_00F6BF 0x00F6C7`, `LABEL_00F6CB 0x00F6D3` — the placeholder NAME carries the true address,
the ADDRESS COLUMN is +8 on every one. Found independently by two regions.
**Re-anchor before integrating anything in the 0x00F000 data segment.**

## BUG-9 (U058) — OUR METADATA. Region 04's header states the wrong part-record base.
It says "0x041300 + channel*0x11F". The 3-byte LE constant **0x041300 occurs ZERO times** in the
image; **0x041368 occurs 162 times**. Direct: `0x02AB83: lda XDE,0x041368`,
`0x02AD11: lda XBC,0x04146A` (= 0x041368 + 0x102). Region 07 is right. Also corroborates BUG-1.

## Falsifiable tests for the top four

**T1 (BUG-1) — single-value oracle, cannot false-positive.** The in-range table maxes at 0x2400,
so **0x5502 is unreachable through any legal index**. Watchpoint on `0x04147A + n*0x11F`
(n=0..15) firing on `data == 0x5502`; or breakpoint at **0x02ACE6** with `L == 0xFF`, which is
exactly the bug's entry. Then dump and listen — every note on part n should be +85 semitones.
⚠ Lua taps must be held in a GLOBAL or the GC kills them.

**T2 (BUG-2) — cliff detector.** Breakpoint 0x027875 (pitch broadcast) and 0x0278A9 (filter),
log C. Legal descent goes FF F6 EB E1 D7 CD... The defect signature is C in 0x20..0x23 for the
first 20-27 samples then a jump to 0xFF. Audible A/B: sweep a part fully up then fully down — a
correct implementation is time-symmetric; this one is not.

**T3 (BUG-3) — two independent tests.** In MAME: break 0x0355AC, poke 0x041377=0x30 and
0x04137A=0x0C, read HL. Buggy = 0x3030; correct-by-intent = 0x300C.
★ On real hardware (ASK FELIPE): set the two per-part effect-send controls to clearly different
values and listen whether the SECOND send tracks the first. If it does, the firmware really
contains the typo and MAME must keep reproducing it.

**T4 (BUG-4) — existence check.** Write-watchpoint on 0x045D30..0x045D50. If it never fires
across a full demo plus deliberate voice starvation (30+ notes, 4-layer tone), it drops to a
footnote.

## Refuted / dismissed

* **U123 REFUTED by measurement** — the claim that `DSP_Bytecode_NotifyStateChange` could stall
  on an empty priority-1 queue. The empty-queue arm at 0x020390 bumps a saturating counter and
  jumps to 0x01FF72 = `pop XIZ/XIY/XIX/XDE/XBC/XWA/XHL; pop SR; ret` — a clean return. Nothing stalls.
* U008 `(XIX+256)` = converter artefact (raw `bc 00 55` is displacement 0). U072 the `*_NopCont*`
  labels are the TG settle delay. U075 self-corrected. U080 dead padding.
* **U115 — three exact code duplicates in region 14** (same C static emitted per translation
  unit). Not a defect but a REAL TRAP: changing one copy breaks the 100.00% byte-match unless all
  three change.

## Highest-leverage NON-bug item

U004/U011/U021/U052/U090: the reference file lags the authoritative ELF by ~900 `LABEL_xxxxxx`
placeholders across five regions. **A mechanical address-ordered sync retires them all** — do
that first (after fixing BUG-8's +8 skew), then argue about names.

Also flagged as a systematic hazard: the **soft-float library is misnamed throughout**
(mul<->add<->div swapped, SP<->DP swapped, libm entries wearing audio prefixes) across ~200 call
sites — U085/U112/U117/U124-U127, conclusive and mutually corroborating across two regions.
**Until it is fixed, every formula derived from those call sites is wrong unless the reader
applies the swap.**

## Open questions worth pulling forward

* **U104** — the class table at 0x012226 assigns class 0 (= NO DSP program) to effects 88-91,
  the very streams our DSP notes call "malformed". Either the notes or this table is describing
  something else. **This contradicts a claim we repeat.**
* **U099** — the word at 0x448C carries two meanings; 8 writers/readers at 0x035899-0x035B12.
  Nearest block to the inter-CPU link — worth a live trace now that 3fd44f3 un-wedged it.
* **U044** — `Voice_SetMonoMode` 0x028D2E sets mono when A==0, and `Voice_ResetAllControllers`
  calls it with 0, so reset would ENABLE mono. One breakpoint settles name-vs-polarity.
* **U029/U030/U095** — three globals read in the audio path whose writers were never found.
* **U010/U016/U047/U088/U093/U109** — six routines with no discoverable caller. Decoding
  `CMD_DISPATCH_TABLE` (0x00F46C), `CALL_TABLE_12159`, the tick table at 0x00F460 and the
  interpreter offset tables at 0x014739/0x014745 would close all six at once.

## Not resolved here

BUG-1 reachability (needs the main-CPU ToneDB); BUG-4 consequence (pointer-based access cannot
be excluded by an absolute-operand scan); BUG-5 reachability; BUG-7 intent (needs the main-CPU
receiver at 0x001E4AA7); U099/U104/U130 all need a run-time trace, not more disassembly.

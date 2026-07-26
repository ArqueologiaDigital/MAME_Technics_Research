# KN5000 sub-CPU naming — subsystem A (AMPLITUDE / ENVELOPE) and B (VOICE LIFECYCLE / ALLOCATION)

Author: autonomous naming pass, 2026-07-26. Requested by Felipe Sanches.

Turns what the 2026-07-23…26 tone-generator investigations **proved** into permanent semantic names
and routine headers in the disassembly, so the knowledge lives in the source rather than only in the
notes.

**APPLIED AND VERIFIED.** All the names below are committed to
`kn5000-roms-disasm` (`1ebc634`), together with a routine/data header block in the repo's existing
style above every one of them. Both build paths were re-run afterwards and reproduce
`original_ROMs/kn5000_subprogram_v142.rom` **byte-identically**:

| path | command | result |
|---|---|---|
| asl | `make rebuilt_ROMs/kn5000_subprogram_v142.rebuilt.rom` | 3 passes, **0 errors, 0 warnings**, `cmp` clean |
| llvm | `make rebuilt_ROMs/kn5000_subprogram_v142.llvm.rom` | `llvm-mc` + `ld.lld` clean, `cmp` clean |

Files touched: `archive/asl/subcpu/kn5000_subprogram_v142.asm` (renames + 38 header blocks),
`symbols/subcpu_symbols_reference.txt` (36 renames, format `SYMBOL 0xADDRESS` preserved),
`v142/subcpu/subcpu_data_tables.s` (the three data-table names, which the LLVM tree also carried).

Evidence labels: **MEASURED** (read from the ROM bytes / the disassembly, or from a live register
capture cited in the notes) · **INFERRED** (deduction from measured facts) · **SPECULATIVE**
(unproven — not named).

Sources: `notes/audit/kn5000-audit-amplitude.md`, `notes/audit/kn5000-audit-voicelife.md`,
`notes/audit/kn5000-eg-calibration.md`, `notes/audit/kn5000-lifecycle-design.md`,
`notes/kn5000-envelope-engine.md`, and a fresh predict-then-check read of the disassembly for every
address below.

---

## 0. CORRECTIONS — the notes that turned out to be wrong

These were found by reading the code before naming it, and they are worth more than the names.

### C-1 (MAJOR). `0x00F507` and `0x00F519` are POLYPHONY QUOTAS, not envelope tables

`notes/kn5000-envelope-engine.md` §1 names and documents them as

* `Voice_AttackDecay_Widths` (0x00F507) — "per-group **stage WIDTHS (durations)**"
* `Voice_EnvelopeRate_Lookup` (0x00F519) — "per-group **envelope RATES**"

and §1 further claims `LABEL_021ECB` copies them into "18 seven-stage state blocks" whose
"`[2..29]` = 7 × 32-bit accumulators" are envelope accumulators. **All of that is wrong.** The proof
chain, all MEASURED:

1. `Voice_Reset_Engine` (0x021ECB) copies `table[g]` into **byte 0** of the block at `0x112D + g*0x1E`
   and sets **byte 1 to 0**, then zeroes seven dwords at `+0x02, +0x06 … +0x1A`.
2. `Voice_List_MoveToPool` (0x021C83) computes its list-head address as
   **`pool + 0x02 + 4*key`** for key 0..6 — i.e. those seven dwords are the **seven priority-list
   heads** of a doubly-linked voice list, not accumulators. The link pair lives in the node at
   `node+0x00/+0x04`.
3. `Voice_Retire_ToFreePool` (0x021E31) does
   `if pool(node+0x1d).byte1 != 0: byte1--` **before** the move and
   `if pool(node+0x1d).byte1 < pool.byte0: byte1++` **after** it — and the move rewrote `node+0x1d`.
   The two halves therefore act on *different* pools: it is a single "transfer one voice from pool A
   to pool B" accounting step. That pins **byte 0 = quota** and **byte 1 = current occupancy**.
4. The numbers close the case. `0x00F507` = `20 10 04 0C 00×12 40 40`:
   32+16+4+12 = **64**, the machine's full polyphony, split four ways.
   `0x00F519` = `0C 06 06 04 04 04 04 04 02×7 06 40 40`:
   12+6+6+4+4+4+4+4+14+6 = **64** again, split sixteen ways.
   Two different partitions of exactly the same 64-voice budget.
5. Pools 16 and 17 have quota `0x40` = 64 in **both** tables because they are the special pools:
   17 (`0x132B` = `0x112D + 17*0x1E`) is the **free pool** and 16 (`0x130D`) is the **global pool**
   that `Voice_Find_Candidate` searches when an order byte has bit 7 set.

Renamed to `Voice_Pool_Quota_ModeA` / `Voice_Pool_Quota_ModeB`. The mode is selected by
`LABEL_028ADC`, which also sets/clears bit 0 of the audio config word at `0x041343`. *(Which
user-facing mode that is — most plausibly single-timbre vs. 16-part multi — is INFERRED and
deliberately not encoded in the name.)*

Consequence for the HLE: **there is no per-group envelope width/rate table in the sub ROM.** The
real parameter→rate table is `0x011963` (`Voice_EnvRate_Lookup`, per
`notes/audit/kn5000-eg-calibration.md` §1) and the real segment descriptors are built per voice by
`Voice_Build_EnvSegments_FixedAtk` / `_PatchAtk`.

### C-2. `LABEL_021ECB` is the whole voice-engine reset, not an envelope-table init

`notes/kn5000-envelope-engine.md` describes it as "init: seed 0x112D env state blocks from the
tables". MEASURED, it does seven things (see the header on `Voice_Reset_Engine`), of which the table
copy is only step 2. Step 1 is a **panic-silence of all 64 channels** (`+0x840 = 0xA200`,
`+0x800 = 0xA280`, then `+0x0C0 = 0x0000`, `+0x000 = 0x7E00`), conditional on any bank of
`0x292E` still showing sounding voices. `notes/audit/kn5000-audit-voicelife.md` §3 GAP 6 cites that
panic pair as coming from "`LABEL_021F08`" — accurate as a description of the loop, but `021F08` is
that loop's **body label inside `021ECB`**, not a separate routine.

### C-3. `slot+0x2f` is a one-shot RELEASE DELAY; the coarse branch of the stepper is dead code

Already caught by `notes/audit/kn5000-eg-calibration.md` §3.4 and re-verified here, because the task
brief still frames `LABEL_026E5B` as "per-voice AMPLITUDE envelope stepper":

* seeded as a **byte** at asm L27198-27200 (`CALL LABEL_03421E; LD A,L; EXTZ WA; LD (XIZ+02fh),WA`),
  so the value is `0x0000..0x00FF`;
* the only bit ever set afterwards is bit 7 (`ORW (XBC+02fh), 0080h`, asm L29374);
* **no instruction in the payload ever sets bit 15**, so the `BIT 0fh` branch of the stepper — the
  one that would rewrite the level register — never executes in v142;
* the live branch decrements by 1 per tick and fires `Voice_Reload_Levels` **once**, then clears
  bit 7 and disarms.

The name applied is therefore `Voice_Step_AmpDelay`, and the header states the coarse branch is dead
code in this build rather than pretending it is a ramp. This is the mechanism behind
`kn5000-audit-amplitude.md` MISS 2 ("the software EG writes far less than the note claims").

Edge case worth recording: arming is guarded by `CPW (XBC+02fh), 0000h` — a counter seeded to 0 is
never armed, which matters because `0x0080` would decrement to `0x007F` and disarm without ever
firing.

### C-4. The EG-segment builder's entry point is `0x025A35`, not `0x025A9E`

The task brief and `kn5000-eg-calibration.md` §1.1 both anchor the four-segment descriptor builder at
`LABEL_025A9E`. MEASURED: `025A9E` is reached only by `JR Z, LABEL_025A9E` from asm L19376 — it is the
**join point inside `LABEL_025A35`**, after the optional key-follow adjustment of the PEAK level.
`025A35` is the real entry (three callers), and it is the one that does
`ORW (XWA+001h), 8000h` — the flag `Voice_Reload_Levels` later tests. `025A9E` was left as a
`LABEL_` on purpose.

### C-5. `LABEL_02222A` and `LABEL_02CDDA` are inner labels, not routines

`02222A` is the per-channel loop body of `Voice_Manager_PollBank` (0x02219F); `02CDDA` is the
`slot+0x01 bit8 == 0` branch of `Voice_Reload_Levels` (0x02CD71). Both were left as `LABEL_` and are
documented in the enclosing routine's header. Naming them would have implied callable entry points
that do not exist.

### C-6. `LABEL_026769` and friends write the SHARED SCRATCH BLOCK, not the voice slot

Minor but load-bearing for anyone reading the code: `Voice_Calc_LevelPair_EGA/B/C` take the **voice
slot** pointer (`0x04308E + ch*0x47`) in `XWA` but store their results to **absolute** addresses
`0x0451F8/0x0451FA`, `0x0451FC/0x0451FE`, `0x045200/0x045202` — i.e. offsets `+0x2C…+0x36` of the
single shared register-staging block at `0x0451CC`, which `ToneGen_WriteLevelBurst` then ships.
There are two different structs with overlapping offset numbering; the notes' phrase "struct +0x2C"
means the **scratch**, while "slot+0x2d / slot+0x2f" mean the **voice slot**.

### C-7. `notes/kn5000-envelope-engine.md` §4 attributes the envelope-counter seed to `LABEL_0253FE`

MEASURED: `slot+0x2f` is seeded from `LABEL_03421E` and `slot+0x31` from `LABEL_033CE5`, both at
asm L27194-27206, inside the note-on path. `LABEL_0253FE` is a different computation (the
`+0x0C0` level/keyscale word — subsystem F). Flagged, not renamed: `0253FE` belongs to the TIMBRE
dimension and is out of this pass's scope.

---

## 1. NAME LIST — address → name → purpose

### 1.1 Subsystem A — amplitude / envelope (routines)

| address | name | purpose |
|---|---|---|
| 0x026E5B | `Voice_Step_AmpDelay` | Per-tick step of a voice's amplitude-domain delay counter `slot+0x2f`; fires `Voice_Reload_Levels` once, then disarms |
| 0x026EC3 | `Voice_Step_ExprRamp` | Per-tick step of the second (expression) domain: writes `+0x180`, accumulates `slot+0x33` toward the floor `0xFF00`, emits the kill pair on countdown |
| 0x025589 | `Voice_Build_GateCommand` | Build the group-0/bank-0 command word `slot+0x2d` from the partial block (`mag = 0xFF − 4·(p & 0x3F)`, bit 8 = magnitude-present) |
| 0x0255F3 | `Voice_Build_GateCommand_NoPartial` | Same for a voice with no partial block — bare `0xFE00` / `0xF000`, magnitude 0 |
| 0x02552A | `Voice_Apply_GateRouting` | OR the per-part bus/routing bits 9-12 into a command word, from the flag byte at `0x04138D + part*0x11F` |
| 0x025A35 | `Voice_Build_EnvSegments_FixedAtk` | Build ATK/PEAK, DECAY1/SUST1, DECAY2/SUST2 and RELEASE into `slot+0x3c/+0x3e/+0x40/+0x46`; attack rate hard-coded `0x7F` |
| 0x025636 | `Voice_Build_EnvSegments_PatchAtk` | Same, but the attack rate comes from `Voice_EnvRate_Lookup[rec+0x28]` — the slow-attack path |
| 0x0232C7 | `Voice_Build_OutputLevel` | Build the `+0x080` word into scratch `+0x04` via the float→log table `0x010764`; sets bit 15 (the ARM strobe) |
| 0x026769 | `Voice_Calc_LevelPair_EGA` | Compute scratch `+0x2C/+0x2E` → chip `+0x800/+0x840` (level fader + cap + velocity scaling) |
| 0x026975 | `Voice_Calc_LevelPair_EGB` | Same shape → scratch `+0x30/+0x32` → chip `+0x900/+0x940` |
| 0x026AAA | `Voice_Calc_LevelPair_EGC` | Same shape → scratch `+0x34/+0x36` → chip `+0x9C0/+0xA00` |
| 0x026BDC | `Voice_Calc_LevelPair_Silence` | Stage a silencing set: zero the EGB/EGC pairs, hold EGA at `slot+0x46` |
| 0x02684A | `Voice_Stage_EnvSegments` | Copy `slot+0x3e/+0x40` into scratch `+0x1A/+0x1C` for `ToneGen_WriteEnvSegments` |
| 0x02CD71 | `Voice_Reload_Levels` | Recompute and re-ship a voice's level registers (segment reload) — 10 call sites, **not** a note-off |
| 0x02D436 | `ToneGen_WriteLevelBurst` | The six-write level burst `+840, +940, +A00, +800, +900, +9C0` |
| 0x02D50E | `ToneGen_WriteLevelPair` | Ship `+0x840` then `+0x800` from scratch `+0x2e/+0x2c` |
| 0x02D5D0 | `ToneGen_WriteEnvSegments` | Ship scratch `+0x1a/+0x1c` to `+0x840` (DECAY1/SUST1) and `+0x880` (DECAY2/SUST2) |
| 0x02D620 | `ToneGen_WriteSegRegs_SameLevel` | Write scratch `+0x2e` to **both** `+0x840` and `+0x880` (collapse the decay segments onto the current level) |
| 0x02D670 | `ToneGen_WriteExprReg` | Write `+0x180 + ch` — the only writer of the register the voice manager reads back |

Left alone on purpose: `ToneGen_WriteSingleReg` (0x02D41B) and `ToneGen_WriteVoiceParams` — already
good names.

### 1.2 Subsystem A — data (ROM tables)

| address | name | layout / meaning |
|---|---|---|
| 0x00F507 | `Voice_Pool_Quota_ModeA` | 18 B, `pool[g].quota` for allocation mode A: `20 10 04 0C 00×12 40 40` (32+16+4+12 = 64) — **was** `Voice_AttackDecay_Widths` |
| 0x00F519 | `Voice_Pool_Quota_ModeB` | 18 B, mode B: `0C 06 06 04 04 04 04 04 02×7 06 40 40` (= 64) — **was** `Voice_EnvelopeRate_Lookup` |
| 0x00F52B | `Voice_Part_PoolPtr_ModeA` | 27 × dword, `descriptor[p].pool` for mode A; every value is `0x112D + g*0x1E` — was `LABEL_00F52b` (asl) / `Voice_ChannelPtrTable` (llvm) |

Proposed but **not applied** (no label exists at these addresses in the source; they are referenced
as absolute constants, so naming them needs a data-block split that would be a byte-level edit):

| address | proposed name | layout / meaning |
|---|---|---|
| 0x00F597 | `Voice_Part_PoolPtr_ModeB` | 27 × dword, the mode-B counterpart of 0x00F52B |
| 0x00F633 | `Voice_Class_AllocDesc` | 6-byte records: `+0` = dword pointer to a priority-order byte list (0xFF-terminated), `+4` = pool list key, `+5` = the per-voice priority stored in `node+0x26` |
| 0x011899 | `Voice_PeakLevel_Fader_Lookup` | 101 B, patch param 0..100 → PEAK level byte (`LVL_A`) |
| 0x0118FE | `Voice_Level_Fader_Lookup` | 101 B, patch param 0..100 → level byte (`LVL_B`; 255…4, ≈ −2/step) |
| 0x011963 | `Voice_EnvRate_Lookup` | 101 B, patch param 0..100 → rate byte 0..127 |
| 0x0119C8 | `Voice_Bipolar_Expand_Lookup` | 51 B, signed ±50 → ±128 (`LABEL_022B68`) |
| 0x011ADF | `Voice_LevelCap_Lookup` | max-loudness cap indices, 4 parameter units (= 3.010 dB) per position |
| 0x010764 | `Voice_LevelCode_To_Log_Table` | 256 words, bit-exactly `round(128·log2(2^(i>>4)·(1+(i&15)/16)))` — the 4-bit-exponent/4-bit-mantissa float law, 16 counts per octave |
| 0x00FBE4 | `Voice_OutputBus_Lookup` | words ORed into the `+0x080` high bits by `Voice_Build_OutputLevel` (INFERRED) |

### 1.3 Subsystem B — voice lifecycle / allocation (routines)

| address | name | purpose |
|---|---|---|
| 0x021ECB | `Voice_Reset_Engine` | Full voice-engine reset: panic-silence 64 channels, reseed 18 pools + 27 part descriptors + 64 nodes, retire every node, clear both bank bitmaps |
| 0x02219F | `Voice_Manager_PollBank` | Per-tick manager: poll one bank's active bitmap, tear down "was sounding, now silent" voices, read each voice's level from `+0x180+ch` |
| 0x02B4A1 | `ToneGen_SilenceChannel` | Free one chip channel: `+0x0C0 = 0x0000`, `+0x000 = 0x7E00` |
| 0x022587 | `Voice_Clear_HoldBit` | Drop a channel's software keep-alive bit in `0x2936`, then tail-call `Voice_Reprioritise` |
| 0x021EA1 | `Voice_Reprioritise` | Re-file a node after its polled level changed; demote if below 0x80, else advance the stage flags and re-key |
| 0x021E83 | `Voice_Demote_Decayed` | Move a decayed node to priority class 6 (preferred steal victim) |
| 0x021E31 | `Voice_Retire_ToFreePool` | Return a node to the free pool `0x132B` / free part list `0x1481`, with the pool-count transfer |
| 0x021C83 | `Voice_List_MoveToPool` | Move a node between voice-pool priority lists (head = `pool + 2 + 4*key`) |
| 0x021D59 | `Voice_List_MoveToPartList` | Move a node between per-part lists (head = `descriptor + 4 + 4*index`), second link pair |
| 0x021E02 | `Voice_List_UnlinkLru` | Unlink from the third (age) chain `node+0x10/+0x14` |
| 0x021E15 | `Voice_List_RelinkLru` | Move to the tail of the third chain |
| 0x027A46 | `Audio_Tick_ServiceVoices_A` | Tick pass A: amplitude-domain counters only |
| 0x027AC4 | `Audio_Tick_ServiceVoices_B` | Tick pass B: pitch bend + amplitude domain + expression domain |
| 0x022340 | `Voice_Allocate_Nodes` | Allocate and bind up to four voice nodes for one note-on command; pure firmware list surgery, touches no chip register |
| 0x02229A | `Voice_Find_Candidate` | Pick the node to (re)use, walking a priority-order byte list over this part's pool and the global pool |
| 0x02CD55 | `Voice_Query_AllChannels` | Build the list of live channels the two tick passes iterate |

Left alone on purpose: `Audio_Process_Init` (0x034CDA) and `Audio_Main_Loop` (0x01FAE3) — already
good; `LABEL_02150D` (channel-resource release, zone tables 0x2126/0x24E6 — subsystem C's material);
`Voice_ParamInit` (0x02CF0D) — the existing name is **misleading** (it is a deferred voice-update
dispatcher keyed on `slot+0x01 & 0x003C`: `0x20`→reload levels, `0x10`→`LABEL_02CED5`,
`0x08`→`LABEL_02CE4C`, `0x04`→arm the release delay) but renaming an already-named symbol is out of
scope here; **proposal: `Voice_Dispatch_PendingUpdate`**.

---

## 2. EQU-STYLE SYMBOL PROPOSALS (RAM, struct offsets, register offsets)

Not applied to the source — an unused `EQU` block is noise until the operands actually use it, and
converting hex operands to symbols is a mechanical follow-up. All addresses below are sub-CPU RAM
and were confirmed in this pass.

```asm
; ---- voice allocator ------------------------------------------------------
VOICE_POOL_BASE      equ 0112Dh   ; 18 pools, stride VOICE_POOL_STRIDE
VOICE_POOL_STRIDE    equ 01Eh
VOICE_POOL_QUOTA     equ 000h     ; byte : max voices this pool may hold
VOICE_POOL_COUNT     equ 001h     ; byte : voices currently in this pool
VOICE_POOL_LIST0     equ 002h     ; 7 dwords, stride 4 : priority-list heads 0..6
VOICE_POOL_GLOBAL    equ 0130Dh   ; = VOICE_POOL_BASE + 16*01Eh, quota 64
VOICE_POOL_FREE      equ 0132Bh   ; = VOICE_POOL_BASE + 17*01Eh, quota 64

VOICE_PARTPOOL_BASE  equ 01349h   ; 27 descriptors, stride 0Ch
VOICE_PARTPOOL_STRIDE equ 00Ch
VOICE_PARTPOOL_POOL  equ 000h     ; dword : pointer to the pool this part draws from
VOICE_PARTPOOL_LIST0 equ 004h     ; 2 dwords, stride 4 : per-part list heads 0..1
VOICE_PARTPOOL_FREE  equ 01481h   ; = VOICE_PARTPOOL_BASE + 26*00Ch

VOICE_NODE_BASE      equ 0148Dh   ; 64 nodes, stride 027h; node index == channel
VOICE_NODE_STRIDE    equ 027h
VOICE_NODE_POOLPREV  equ 000h     ; dword : pool-list link
VOICE_NODE_POOLNEXT  equ 004h     ; dword
VOICE_NODE_PARTPREV  equ 008h     ; dword : part-list link
VOICE_NODE_PARTNEXT  equ 00Ch     ; dword
VOICE_NODE_AGEPREV   equ 010h     ; dword : third (age) chain
VOICE_NODE_AGENEXT   equ 014h     ; dword
VOICE_NODE_PARTDESC  equ 018h     ; dword : current part descriptor
VOICE_NODE_PARTKEY   equ 01Ch     ; byte  : current part-list index
VOICE_NODE_POOL      equ 01Dh     ; dword : current pool
VOICE_NODE_POOLKEY   equ 021h     ; byte  : current pool priority class
VOICE_NODE_FLAGS     equ 022h     ; byte  : b0 free, b1 decayed, b2/b3 stage, b7 command-held
VOICE_NODE_KEY       equ 023h     ; byte  : MIDI-ish key that owns this voice
VOICE_NODE_CHAN      equ 024h     ; byte  : channel number (== node index)
VOICE_NODE_LEVEL     equ 025h     ; byte  : level polled back from the chip, (v & 3FFFh) >> 5
VOICE_NODE_PRIO      equ 026h     ; byte  : priority class to re-file into

VOICE_POLL_BANK      equ 01128h   ; byte  : round-robin bank 0..3 for the poll loop
VOICE_ALLOC_OVERRIDE equ 01345h   ; dword : forced node for the next allocation, 0 = none

TONEGEN_ACTIVE_PREV  equ 0292Eh   ; 4 words : previous merged active bitmap, per bank
TONEGEN_HOLD_MASK    equ 02936h   ; 4 words : software keep-alive mask ORed into the chip bitmap
VOICE_QUERY_BUF      equ 02A5Eh   ; query descriptor {mode, key.w, mask.w} + result byte list at +5

; ---- per-voice slot -------------------------------------------------------
VOICE_SLOT_BASE      equ 04308Eh  ; 64 slots, stride 047h
VOICE_SLOT_STRIDE    equ 047h
VSLOT_CHAN           equ 000h     ; byte  : chip channel number
VSLOT_FLAGS          equ 001h     ; word  : b8 single-reg reload, b10 pitch dirty, b15 EG built
VSLOT_PART           equ 004h     ; byte  : part index
VSLOT_PARTIALPTR     equ 017h     ; dword : partial parameter block
VSLOT_PARTPTR        equ 023h     ; dword : part struct (0x04136A + part*011Fh)
VSLOT_GATECMD        equ 02Dh     ; word  : group-0/bank-0 command word
VSLOT_AMPDELAY       equ 02Fh     ; word  : b15 coarse-armed (never set), b7 fine-armed, b6:0 ticks
VSLOT_EXPRSTATE      equ 031h     ; word  : b15 armed, b14:12 phase, b6:0 kill countdown
VSLOT_EXPRACC        equ 033h     ; word  : signed expression accumulator, floor 0FF00h
VSLOT_EXPRRATE       equ 035h     ; byte  : rate merged into the state word each tick
VSLOT_EXPRSTEP4      equ 036h     ; word  : per-tick increment, phase 4000h
VSLOT_EXPRSTEP1      equ 038h     ; word  : per-tick increment, phase 1000h
VSLOT_EXPRCEIL       equ 03Ah     ; word  : ceiling
VSLOT_SEG_ATK        equ 03Ch     ; word  : (PEAK << 8) | rate
VSLOT_SEG_DEC1       equ 03Eh     ; word  : (SUST1 << 8) | rate, rate floored at 4
VSLOT_SEG_DEC2       equ 040h     ; word  : (SUST2 << 8) | rate, rate 0 = HOLD
VSLOT_REL_LEVEL      equ 046h     ; byte  : RELEASE target level

; ---- shared register staging block ---------------------------------------
TONEGEN_REG_SCRATCH  equ 0451CCh
TGS_OUTLEVEL         equ 004h     ; word -> chip +080h   (bit15 = ARM strobe)
TGS_SEG_ATK          equ 018h     ; word -> chip +800h   (ATK/PEAK segment)
TGS_SEG_DEC1         equ 01Ah     ; word -> chip +840h
TGS_SEG_DEC2         equ 01Ch     ; word -> chip +880h
TGS_LEVEL_A          equ 02Ch     ; word -> chip +800h
TGS_LEVEL_A2         equ 02Eh     ; word -> chip +840h
TGS_LEVEL_B          equ 030h     ; word -> chip +900h
TGS_LEVEL_B2         equ 032h     ; word -> chip +940h
TGS_LEVEL_C          equ 034h     ; word -> chip +9C0h
TGS_LEVEL_C2         equ 036h     ; word -> chip +A00h

; ---- part / global state --------------------------------------------------
PART_STRUCT_BASE     equ 04136Ah  ; stride 011Fh
PART_MODE_WORD       equ 00Ah     ; b0 sustain pedal, b15 delayed-release / unison-synth gate
PART_BUS_ROUTING     equ 04138Dh  ; byte at +part*011Fh, consumed by Voice_Apply_GateRouting
PART_EXPR_MODE       equ 04138Eh  ; byte at +part*011Fh, selects the +180h packing
TONEGEN_RELEASE_MODE equ 04134Ch  ; byte : 0/5/6 -> command base 0FE00h, else 0F000h
AUDIO_TICK_PHASE     equ 041342h  ; byte : Audio_Process_Init A/B toggle
AUDIO_CONFIG_FLAGS   equ 041343h  ; word : b0 = allocation mode (Voice_Reset_Engine argument)
TOUCH_SENS_MODE      equ 04A48h   ; byte : TOUCH SENSITIVITY 0..9, default 6
```

---

## 3. PREDICT-THEN-CHECK log for this pass

| prediction | result |
|---|---|
| `LABEL_026E5B` matches the transcription in `kn5000-envelope-engine.md` §2 | **HIT** on the instruction sequence, **MISS** on the framing — see C-3 |
| `LABEL_021ECB` copies the two 18-byte tables into `0x112D` blocks | **HIT** on the copy, **MISS** on everything around it — see C-1, C-2 |
| The seven dwords in a `0x112D` block are envelope accumulators | **MISS** — they are `Voice_List_MoveToPool`'s seven list heads (`pool + 2 + 4*key`) |
| `LABEL_02219F` matches `kn5000-audit-voicelife.md` §1.5 line for line | **HIT**, including `node+0x25 = (read(0x0180+ch) & 0x3FFF) >> 5` and the `0x2936 | chip` merge |
| `LABEL_02D436` writes exactly six registers in the order `840, 940, A00, 800, 900, 9C0` | **HIT**, and it is the only writer emitting `+940` directly after `+840` |
| `LABEL_025589` builds `mag = 0xFF − 4·(p & 0x3F)` with bit 8 as a presence flag | **HIT** |
| `LABEL_026769/975/AAA` write the voice slot | **MISS** — they write the shared scratch at `0x0451F8…0x045202` (C-6) |
| `LABEL_025A9E` is the EG-segment builder's entry point | **MISS** — the entry is `LABEL_025A35` (C-4) |
| The two quota tables sum to 64 (predicted *after* spotting the pool-count arithmetic, *before* adding them up) | **HIT** — 64 for both, which is what closed C-1 |

---

## 4. What this changes for the HLE

Nothing in `kn5000_tonegen.cpp` needs to change because of a rename, but two of the corrections have
consequences worth recording:

* **C-1** removes a phantom data source. Any plan that proposed to drive HLE envelope segment
  widths/rates from `0x00F507`/`0x00F519` (e.g. `kn5000-envelope-engine.md` §6 step 2) is drawing
  from a polyphony table. The segment words come from `Voice_Build_EnvSegments_*` and the
  parameter→rate table `0x011963`.
* **C-3** removes the "software ramp" model. The sub-CPU does not ramp the amplitude per tick; it
  arms a one-shot delay and then reloads a level once. Combined with
  `kn5000-audit-amplitude.md` GAP 4/GAP 5, that means the ramp lives **in the chip**, and the HLE's
  job is to model the chip's own ramp plus the `+0x180` readback — not to re-implement a firmware
  ramp that does not exist.

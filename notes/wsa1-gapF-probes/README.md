# Gap-F adversarial probes

One script, `gapF_refutation_probes.py`, written to REFUTE a proposed change to
`wsa1_state::tg_status_r()` (the `0x0010C000 + 4` read-back).  It reads the raw
bytes of `wsa1-roms-disasm/original_ROMs/*` at BASE `0xF80000` and never reads
`prom_c/wsa1_prom_c.s`, so a listing error cannot propagate into it.

    python3 notes/wsa1-gapF-probes/gapF_refutation_probes.py

Each probe's docstring says what question it answers and what a pass looks like.
Results as of 2026-08-25, against `wsa1_prom_c.ic28`:

| probe | result |
|---|---|
| P1 | 102 loads of the immediate `0x0010C000` across the four images; exactly **one** (`0xFA68FC`, `Dev10C_PollBankAndRetire`) steps the pointer by 4, so it is the only reader of the DATA port. |
| P2 | `0x7E00` has exactly **3** store sites (`0xFA66C7`, `0xFB0AB5`, `0xFB8211`); `0x8100` has **7**, not 3 — the four extra ones (`0xFB7D13`, `0xFB7E09`, `0xFB7EFF`, `0xFB80D6`) select register blocks `0x0540` / `0x0580` / `0x05C0`, not block 0. |
| P2b | no `ld r16,0x8100/0x7E00` anywhere in prom_c, so P2 is a complete census for those two words. |
| P3 | **`0xFB810E` is `ld HL,0x0840`, not `ldb d,0x40`.** The 64-iteration loop counter is at **`0xFB8116`** (`24 40`), with `dec 1,D` at `0xFB8140`. `wsa1.cpp`'s own comment (near line 429) carries the same wrong address. |
| P4 | 15 `set 0x02,<byte reg>` sites in prom_c; exactly one (`0xFA6632`) is inside the voice module `0xFA6528-0xFA6EF9`. |
| P5 | `rec[+0x15]` is written **`0xFF`** by the allocator at `0xFA6CC3` and zeroed by `ChanRec_Release` at `0xFA6598`; `sub_FA65BD`'s guard at `0xFA65CD` is `flags & 0x03`, so the RELEASED bit blocks it. |
| P6 | the allocator **does** OR the channel's bit into `0x0087BF` itself, at `0xFA6D39`-`0xFA6D41` — a fourth mask site that `FINDINGS-prom_c-voice-readback.md` sec.2 does not list. |
| P7 | both producers of `voicerec[+0x29]` (the computed word `Dev10C_WriteReg_c` sends to block 0) build it as an OR whose high byte is a shifted parameter, so a computed block-0 word can in principle equal `0x7E00` or `0x8100`. |

Nothing here was measured in the emulator; every line is a byte read.

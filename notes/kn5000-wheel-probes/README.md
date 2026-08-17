# TEMPO/PROGRAM wheel probes

The static evidence behind **blog Part 135** ("It was on the wire all along") and the retraction in
`notes/FINDINGS-kn2400-table-rom.md`'s sibling work: the KN5000's data wheel is a control-panel
serial input `[0xD7, signed detent count]`, not something that must be poked into DRAM.

All of these read the six dumped KN5000 program ROMs from
`/home/fsanches/compartilhado/kn7000-emulator/roms/kn5000/` (mapped at CPU `0xE00000`) and take no
arguments. Run with `python3 notes/kn5000-wheel-probes/<script>`.

| script | the question it answers |
|---|---|
| `tblid.py` | **Where does the header→record translation table live in each revision, and is its content the same?** This is the load-bearing one. |
| `curve.py` | **What is the acceleration curve?** Dumps the 32 signed longs and prints the wire value each index corresponds to. |
| `xrev.py` | **Do the parser signatures exist in every revision?** Locates the header→record translator, the value-translation dispatch, the parser class dispatch, the wheel descriptor and the accel curve by byte signature rather than by address. |
| `refs.py` | **Which sites reference a given 16-bit DRAM address as a direct operand?** (TLCS-900 `C1/D1/E1/F1` + lo/hi.) Used to show the scan-list address is referenced in some revisions and not others. |
| `listaddr.py` | **Where is the scan list in each revision?** Finds the enqueue prologue and the `lda XHL,imm16; ret` helper. |
| `verify.py`, `verify2.py` | Cross-revision re-checks of the above, written independently as a second opinion. |

## The result that matters

`tblid.py`, run 2026-08-18:

```
v5:  table 0xED9F28 sha1=48d964b155730fe0a0d48837a362d975d728b588
v6:  table 0xED9F40 sha1=48d964b155730fe0a0d48837a362d975d728b588
v7:  table 0xEDA03C sha1=48d964b155730fe0a0d48837a362d975d728b588
v8:  table 0xEDA03C sha1=48d964b155730fe0a0d48837a362d975d728b588
v9:  table 0xEDA03C sha1=48d964b155730fe0a0d48837a362d975d728b588
v10: table 0xEDA03C sha1=48d964b155730fe0a0d48837a362d975d728b588
```

**Three different addresses, byte-identical content.** That is the whole argument for implementing
the wheel at the wire rather than by poking DRAM: the *encoding* is a constant of the machine, the
*addresses* are not. The current HLE hardcodes `0x8E94`, which is v8/v9/v10 only — on `-bios v5`,
`-bios v6` and `-bios v7` it writes into unrelated work RAM.

Related: `tools/rigs/kn5000_wheel_bios_sweep.py` (the same point from the scan-list side, with a
pass/fail verdict), `tools/rigs/kn5000_wheel_rate_test.lua` (the detent-loss measurement),
`tools/rigs/kn5000_wheel_idle.lua` (the negative control: record `0x19` never appears at idle),
`tools/dis_kn5000.sh` and `tools/tlcs900_callers.py`.

⚠ These are analysis probes, not tests: they print, they do not assert. Read the output.

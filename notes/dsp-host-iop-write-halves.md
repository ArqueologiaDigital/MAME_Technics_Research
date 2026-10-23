# The effects DSP's host port: an IOP register written at each 16-bit half

**Status: observed in MAME on 2026-10-23; how the chip behaves is not yet checked against the ADSP-21065L
manual. The driver is unchanged.**

## What the driver does

`kn7000_state::dsp_data_w` (`src/mame/matsushita/kn7000.cpp`) keeps the SHARC's IOP register file in step with
the host's register writes. The firmware writes a register as two 16-bit halves, low then high. The driver calls
`host_iop_w(reg, value)` after **each** half:
- after the low half, with the low half alone;
- after the high half, with both.

So between the two halves the DSP sees the register holding the low half alone.

## How it showed

KN7FM (kn5000_homebrew `demos/kn7000_fm`) takes its key commands through MSGR6. The DSP acts at its next frame on
the bits it finds, then writes MSGR6 = 0. The host waits for 0 before writing again. Its first protocol had the
key-on bits in the low half. Under the recompiler a key-on was taken twice:
- the DSP read MSGR6 between the two halves, took the key-on and cleared the register;
- the high half's write then put `low | high << 16` back, with the key-on bit still set;
- the next frame took the key-on again.

The evidence: the per-frame voice dumps of `tests/mame/fm_capture.lua` showed voice 0's phases reset again one frame
after its key-on, while its gain went on (KN7FM `07bf3c2`'s message has the frames). Under the interpreter the
same session happened not to interleave so.

KN7FM now keeps its commands in the high half, with the low half 0, which is safe whichever way the port works.
Another World's mixer (technics-anotherworld `kn7000/tools/dsp_mixer.py`) has its command bits in MSGR6's low half
too. A start taken twice restarts a sample, which is hard to hear.

## What the chip does (to check)

The 21065L packs a 16-bit host's words into 32-bit words. If an IOP register write lands only once the second
half is in, the driver should call `host_iop_w` once, after the high half. The source to check is the 21065L
User's Manual, Host Interface chapter, "Packing" and the host writes to IOP registers.

If it does work that way, the fix is in `dsp_data_w`: keep the low half and write the register at the second.
Two things depend on the current behaviour and would need care:
- the DMAC0 path (`case 0x1c`), which acts on the low half;
- the readback paths.

A test: KN7FM with its commands moved back to the low half (bits 0-7 key-on) should then take each key-on once,
under both cores.

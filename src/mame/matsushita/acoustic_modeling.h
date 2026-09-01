// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    Technics SX-WSA1 / SX-WSA1R -- the second per-channel register file
    at 0x00104000 on CPU 2.  PLACEHOLDER: no audio is synthesised.

    THE PART NAME IS THE PROJECT OWNER'S CALL; THE DECODE IS STILL AN INFERENCE.
    ------------------------------------------------------------------------
    This device is named L7A1429 by Felipe's decision of 2026-09-01.  He owns
    the hardware and the service manual, and that outranks the grading below,
    which is written from the firmware alone.  What the two sources each settle
    is worth keeping separate, because they are different claims:

      * The PART EXISTS AND IS NAMED.  The service manual's parts list gives
        IC3 = L7A1429, "MODELING LSI".  That is documentation, not inference.
      * That 0x00104000 DECODES TO IC3 is what the firmware cannot show.  No
        string in any of the four ROM images names a part number, and the
        disassembly deliberately keeps the address-stating prefix `Dev104_` for
        that reason.  Renaming this device does not change that, and the
        disassembly's prefix is not to be "brought into line" with it.

    So: the name asserts the part, on the owner's authority.  The evidence that
    this window IS that part remains a RANKED INFERENCE, graded in
    wsa1-roms-disasm/notes/FINDINGS-sound-subsystem-boundary.md §3 and
    reproduced below.  If a schematic ever shows 0x00104000 decoding elsewhere,
    it is this file that is wrong, not §3.

    What §3 actually establishes, and what it does not:

      ★ ESTABLISHED  0x00104000 is the only per-channel synthesis device CPU 2
                     drives that has NO counterpart in the KN5000 sub-CPU -- a
                     PCM sample-playback engine with closely related firmware
                     and no physical modelling, used there as the control group.
                     Its register file is also a different SHAPE from the tone
                     generator's: 19 contiguous blocks against 22 sparse ones.
      ⚠ INFERENCE   therefore it is the acoustic modelling section.  Supporting
                     it: it is per-CHANNEL on the tone generator's own 64-channel
                     numbering; it is reset channel by channel *inside*
                     Dev10C_ResetAllChannels, so the two files are two halves of
                     one voice; and all four note-on staging paths write BOTH
                     devices for EVERY voice.
      ⚠ ALTERNATIVE that fits every number: the two devices are the DRIVER and
                     the RESONATOR halves of one modelling engine, rather than
                     "the PCM part and the modelling part".  Nothing measured
                     separates those readings -- and both put the modelling in
                     this register file.
      ⚠ REFUTED BY  a part number, or a KN5000 sub-CPU device below the
                     detection threshold that turns out to be a 64-channel
                     parameter file.

    The parts list's only otherwise-unaccounted-for synthesis LSI is IC3,
    L7A1429 "MODELING LSI".  ⚠ Reaching that part by elimination is NOT the same
    as measuring it: the argument is "nothing else in the parts list is left",
    which is only as strong as the parts list is complete.  The device carries
    the name on the owner's authority (above); this paragraph records what the
    firmware evidence for it is worth, which is less.

    ------------------------------------------------------------------------
    ★ IT IS A REGISTER FILE, NOT A PROGRAM LOADER
    ------------------------------------------------------------------------
    Settled by CONTROLLED COMPARISON rather than by inspecting the traffic and
    forming an opinion about it.  This firmware contains a KNOWN code-upload
    path -- DSP effect microcode leaving CPU 2 through port P7, a byte at a
    time, with strobes and a 0x1F40 timeout -- so every discriminant is scored
    for both, and the answer is whichever column 0x104000 resembles:

      discriminant                   P7 (known code upload)   0x104000
      ---------------------------------------------------------------------
      opaque byte stream             yes, ld (0x0013),(XIZ+d) no
      handshake / strobe protocol    yes: P5, PB, 0x1F40 poll no
      micro-DMA ever aimed at it     channel-driven           NO CHANNEL
      destination addresses          one port, repeatedly     fixed register set
      register numbering             n/a                      block*0x40 + channel
      values sourced from            a byte buffer            a packed part record

    Reproduce, 6 selftest checks:
      python3 wsa1/notes/sound/dev104_payload_class.py [--selftest]
    in ~/compartilhado/kn5000-roms-disasm.

    ⚠ THE CLAIM IS BOUNDED: no executable payload crosses this port.  That is
    NOT proof that the die holds no microcode of its own.  A modelling engine
    with fixed on-die code exposing only coefficients would look exactly like
    this, and this device cannot tell the difference.

    ------------------------------------------------------------------------
    THE INTERFACE
    ------------------------------------------------------------------------
    +0 address latch (register select), +2 data.  0xFB7802 `ld XBC,0x00104000`,
    then the fifteen-plane burst at 0xFB7807-0xFB791B, whose first six planes
    and block-word offsets are identical to the KN5000 tone generator's note-on
    burst.  All nine 32-bit-immediate load sites are inside 0xFB7715-0xFB7B62 or
    inside Dev10C_ResetAllChannels.

    REGISTER NUMBERING is `block * 0x40 + channel`, 64 channels.  ⚠ TWO
    DIFFERENT COUNTS OF "the blocks" are quoted below and they measure
    DIFFERENT THINGS -- do not quote one as the other:

      * EIGHT distinct block numbers appear in the SETTER NAMES the disassembly
        has converted so far -- 0x00C0, 0x0100, 0x0140, 0x0180, 0x01C0, 0x0200,
        0x0240, 0x0280 -- spaced exactly 0x40 apart.  That is a property of the
        named accessors, measured by dev104_payload_class.py.
      * NINETEEN CONTIGUOUS BLOCKS, 0x000..0x480, are what the REGISTER FILE
        itself spans, from the unrolled writer.
        (FINDINGS-sound-subsystem-boundary.md §3.)

    Dev104_WriteAllChanRegs (prom_c 0xFB77EF) writes nineteen registers of one
    channel in one run:

        register (chan + k*0x40) = staging word 2*k     for k = 1 .. 0x12
        register (chan + 0)      = staging word 0       written LAST

    and `field == 2 * (base / 0x40)` holds for all nineteen (0 failures,
    notes/prom_c_tg_regmap.py --dev104).

    ⚠ BLOCK 0 LAST IS THE SHAPE OF A COMMIT REGISTER, AND IT IS A PROPERTY OF
    THE ROUTINE, NOT OF THE REGISTER.  Two of the small accessors in the same
    bank -- Dev104_SetChanRegs_01C0_0200_0240 (0xFB796E, first write 0xFB7983)
    and Dev104_SetChanRegs_0140_to_0240 (0xFB79D0, first write 0xFB79E5) --
    write block 0 FIRST, before the registers they are named for.  Execution
    order for all three was measured with
    `notes/prom_c_tg_chanmap.py <addr> <len> --dev 0x00104000 --pairs`.  Two
    routine headers used to claim the opposite and were corrected.
    (FINDINGS-prom_c-tone-generator.md §4.)

    ⚠ NOTHING IN prom_c READS THIS DEVICE.  Every literal-address site is a
    store, so a read means either a code path the analysis has not reached or a
    decode error -- which is why data_r() logs unconditionally rather than
    under a VERBOSE mask.

    The power-on image, from Dev10C_ResetAllChannels (0xFB80E1): register 0x0800
    := the word at ROM 0xFE1313, then the per-channel loop that calls this
    device's writer and the tone generator's once each per channel.  0x0800 is
    ABOVE the 19-block per-channel span and is recorded as read, not explained.

    ★ AND THAT IS EXACTLY WHAT THE BUS SHOWS.  A tap on CPU 2's program space at
    0x104000-0x104003 over 45 emulated seconds of boot
    (tools/rigs/wsa1_dev104_bus_trace.lua) sees 2,642 writes, ZERO reads, and a
    file of 1,217 distinct registers spanning 0x0000..0x0800 -- which is
    19 blocks x 64 channels = 1,216, plus 0x0800 alone.
    ⚠ THIS CORRECTS A MISREADING THAT WAS IN THE FIRST DRAFT OF THIS HEADER:
    FINDINGS-sound-subsystem-boundary.md §4.2 step 3's `for i = 0..0x3F:
    0x0840+i := 0xFF00, 0x0800+i := 0xFF80` sweep does NOT land here -- no
    register in 0x0801..0x087F is ever written in the window, so that step is
    the TONE GENERATOR's.  Only the single 0x0800 write of step 2 is this
    device's.

    ------------------------------------------------------------------------
    PROVENANCE: every paragraph above moved here VERBATIM in substance from the
    inline block comments in wsa1.cpp, where this device lived as synth2_addr_w
    / synth2_data_w / synth2_data_r until it was promoted.  The firmware
    citations are theirs.

***************************************************************************/

#ifndef MAME_MATSUSHITA_ACOUSTIC_MODELING_H
#define MAME_MATSUSHITA_ACOUSTIC_MODELING_H

#pragma once


class l7a1429_device : public device_t
{
public:
	l7a1429_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock = 0);

	// 0x104000 +0: the address latch (register select).
	void addr_w(uint16_t data);

	// 0x104002 +2: the data register.  Write-only in every code path reached so
	// far; the read exists to catch the one that is not.
	void data_w(uint16_t data);
	uint16_t data_r();

	// Read-back for the debugger and for a future synthesis model.  Out-of-range
	// selects return 0 rather than aliasing, which is this driver's choice: what
	// the real part does with a select above its file is not established.
	uint16_t reg(unsigned n) const { return (n < REG_COUNT) ? m_regs[n] : 0; }

protected:
	virtual void device_start() override ATTR_COLD;

private:
	// The file is sized to cover every select the firmware is known to form.
	// 0x1000 is the tone generator's ceiling, carried over unchanged from the
	// inline code so the bounds check behaves identically; this device's own
	// per-channel span is only 0x000..0x4BF (19 blocks x 0x40 + 0x3F), plus the
	// single register 0x0800 that Dev10C_ResetAllChannels writes on top of it.
	static constexpr unsigned REG_COUNT = 0x1000;
	static constexpr unsigned VOICES    = 64;      // `ld D,0x40`, prom_c 0xFB8116

	uint16_t m_latch = 0;
	uint16_t m_regs[REG_COUNT]{};
};

DECLARE_DEVICE_TYPE(L7A1429, l7a1429_device)

#endif // MAME_MATSUSHITA_ACOUSTIC_MODELING_H

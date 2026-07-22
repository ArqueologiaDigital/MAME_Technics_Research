// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    Technics KN5000 DSP Devices

    IC311 (uPD6383GF-3BA) - "DSP1" - parallel host interface on Sub CPU port PZ
    IC310 (MN19413)       - "DSP2" - GPIO serial interface (bit-bang)

    Both chips are digital signal processors used for audio effects
    (reverb, chorus, delay, etc.). They are controlled by a shared
    bytecode interpreter running on the Sub CPU.

    ---------------------------------------------------------------------
    PART IDENTIFICATION (2026-07-22)
    ---------------------------------------------------------------------
    IC311 was previously recorded as "DS3613GF-3BA", described as a custom
    ASIC of unknown origin with no public documentation. That part number is
    a TRANSCRIPTION ERROR. The chip is an NEC uPD6383GF-3BA.

    The same part appears as IC302 in the Pioneer CDJ-500/CDJ-500G service
    manual (RRV1087), pages 1-15..1-17, which documents its block diagram and
    all 100 pins. Felipe's own pin survey of the KN5000 chip
    (kn5000_project/chips_dsp_usados_no_kn5000.txt) matches that pinout
    one-for-one over the pins he transcribed:
        1 /CS, 2 /DC, 3 /SCK, 4 SI, 5 SO, 6 EIFLAG, 7 EOFLAG, 8 RDY, 9 /RST,
        10 /RST2, 11 /BR-RQ, 12 /BR-AK, 13 /Fs-RST, 14 /Fs-MASK, 15 VDD,
        16 GND, 17 BCLKI, 18 LRCKI, 19 XFsI, 20-22 DI1-DI3
    ...and both are 100-pin parts.

    uPD6383GF ARCHITECTURE (from the CDJ-500 manual):
      * I-RAM  384 x 36  - INSTRUCTION RAM, uploaded by the host CPU
      * C-RAM  256 x 24  - coefficient RAM
      * D-RAM  256 x 24  - data RAM
      * 24x24 multiplier -> 44-bit ALU, ACCA/ACCB accumulators, 2 shifters
      * PC + 2-level stack, loop counters LC1-LC3, pointers DP/BP1/BP2/PR1/PR2
      * external DRAM controller (RAS/CAS/WE, A0-A16, 16-bit I/O) for delay
      * 3 serial audio in (DI1-DI3), 3 serial audio out (DO1-DO3)
      * host flags: GF1-GF3 (set by instructions), RQ1-RQ3 (set by host,
        testable in an instruction's COND field)
      * host interface selectable parallel (P/S high) or serial (P/S low)

    The KN5000 uses the PARALLEL interface: the Sub CPU writes command and
    data bytes through port PZ with READ/WRITE strobes (DSP_Send_Command at
    subcpu 0x036331, DSP_Send_Data at 0x0367EE), chip select on P7.5 and
    reset on PH.1.

    ---------------------------------------------------------------------
    WHY THIS DEVICE CAPTURES THE BYTE STREAM
    ---------------------------------------------------------------------
    Because I-RAM is RAM, the DSP program MUST be uploaded at runtime, so the
    program image is reachable without decoding a single opcode.

    The Sub CPU's two-level bytecode interpreter emits payloads in "groups of
    5" (opcodes 0x0N/0x1N/0x5N) and "groups of 3" (opcode 0x2N). Those widths
    match this chip exactly:
        5 bytes = 40 bits, the smallest byte-aligned container for a
                  36-bit I-RAM instruction word
        3 bytes = 24 bits, exactly a C-RAM/D-RAM word
    CONFIRMED 2026-07-22, two independent ways:
      * in the ROM: the bytecode handlers divide payload lengths by literal
        constants -- "div WA,0x0005" at 0x03C32E/0x03C568/0x03C7BB (ops 0/1/5)
        and "div WA,0x0003" at 0x03C661 (op 2);
      * at runtime, capturing the real port: every op3 upload carries a 16-bit
        I-RAM word address followed by a body that is an EXACT multiple of 5,
        and the addresses tile I-RAM without overlap --
            addr   0, 300 bytes =  60 words   (common header, 0..59)
            addr  60, 115 bytes =  23 words   (algorithm-change stub, 60..82)
            addr  84, 350 bytes =  70 words   (effect unit 0)
            addr 200, 665 bytes = 133 words   (effect unit 1)
            addr 352, 155 bytes =  31 words   (ends at 382, just under the 384 limit)
        Ten uploads, ten integer word counts, nothing out of range. A wrong word
        size would give fractional counts and addresses past the end of I-RAM.

    So this device records every command/data byte and writes the transfers
    out for offline inspection. What to look for: N groups of 5 with
    N <= 384 (I-RAM capacity -- a program may use only part of it), and
    crucially a DIFFERENT N per effect algorithm. Fixed-size register traffic
    would not vary that way, so the variation is the real evidence.

    DECODING STRATEGY (Felipe, 2026-07-22): cross-check numeric constants
    against the KN7000 effect algorithms, which are already fully disassembled
    and documented (see kn7000_disassembly/dsp/ -- reverb, chorus family,
    insert effects, tremolo/rotary, phaser/enhancer/gate, dynamics/EQ/exciter,
    modulation/pitch). No guarantee the two are the same, but correlations are
    plausible: both are Technics effect units of the same era, and the KN7000
    algorithms are known in full.
    Aim this at the GROUPS OF 3 first, not the instructions: 24-bit C-RAM/D-RAM
    words are coefficients and delay lengths, and those are the values most
    likely to survive a change of instruction set -- a delay tap of a given
    number of milliseconds is the same physical quantity on either machine, so
    a length should reappear (scaled by the sample rate) even if nothing about
    the opcode encoding matches. Filter coefficients likewise.

***************************************************************************/

#ifndef MAME_MATSUSHITA_KN5000_DSP_H
#define MAME_MATSUSHITA_KN5000_DSP_H

#pragma once

#include <vector>

//**************************************************************************
//  DSP1 - IC311 (uPD6383GF-3BA) - parallel host interface
//**************************************************************************

class kn5000_dsp1_device : public device_t
{
public:
	kn5000_dsp1_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock);

	// ---------------------------------------------------------------
	// THE REAL uC-IF: Sub CPU port PZ carries the byte, port 7 the control
	// lines (P7.3 /WRITE, P7.4 /READ, P7.5 /CS-DSP1, P7.6 C/D where 0 =
	// command and 1 = data; PH.0 ready, PH.1 reset).  EVERY microprogram and
	// coefficient byte goes through here.
	// ---------------------------------------------------------------
	void host_w(bool cd, uint8_t data);   // cd=false -> command, true -> data

	// ---------------------------------------------------------------
	// A SEPARATE, UNRELATED register block at 0x130000 (4 channels x 8
	// registers, 0x20 spacing), written by DSP_Init_Channels (subcpu
	// 0x01FC95) / DSP_Write_Channel (0x01FCDE).  This is NOT the uC-IF and
	// carries no microcode -- an earlier revision of this file wrongly
	// modelled it as the command/data port, which is why an upload capture
	// hooked here saw nothing but zeros.
	// ---------------------------------------------------------------
	void reg_addr_w(uint16_t data);   // 0x130000: register address latch
	void reg_data_w(uint16_t data);   // 0x130002: register data write
	uint16_t reg_data_r();            // 0x130002: register data read

	// Historical names used by the memory map.
	void addr_w(uint16_t data) { reg_addr_w(data); }
	void data_w(uint16_t data) { reg_data_w(data); }
	uint16_t data_r() { return reg_data_r(); }

	// I-RAM capacity, in 36-bit instruction words (uPD6383GF).
	static constexpr int IRAM_WORDS = 384;

protected:
	virtual void device_start() override ATTR_COLD;
	virtual void device_reset() override ATTR_COLD;
	virtual void device_stop() override;

private:
	void flush_transfer();

	uint8_t  m_cmd;                 // most recent uC-IF command byte
	uint8_t  m_addr_latch;          // 0x130000 register block address latch
	uint8_t  m_regs[0x100];         // 0x130000 register file (read-back model)

	// --- upload capture (not emulation state; excluded from save states) ---
	struct transfer
	{
		uint8_t              cmd;
		std::vector<uint8_t> payload;
	};
	std::vector<transfer> m_transfers;    // completed transfers this session
	transfer              m_current;      // transfer being accumulated
	bool                  m_have_current;
};

DECLARE_DEVICE_TYPE(KN5000_DSP1, kn5000_dsp1_device)

#endif // MAME_MATSUSHITA_KN5000_DSP_H

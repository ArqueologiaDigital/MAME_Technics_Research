// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    Technics SX-WSA1 / SX-WSA1R -- IC3, the L7A1429 "MODELING LSI", the
    per-channel register file at 0x00104000 on CPU 2 (IC2, the SUB processor).
    Models the register interface and the decoded per-channel resonator state
    (decoded_channel / l7a1429_resonator_params); no audio is synthesised -- see
    THE INTERNAL SIGNAL PATH note below for why that is correct, not unfinished.

    ------------------------------------------------------------------------
    THE PART, THE DECODE AND THE PORT -- SETTLED BY THE SERVICE MANUAL
    ------------------------------------------------------------------------
    Sheets II-9..II-12 of the SX-WSA1R service manual (the P.C. diagrams; the
    book has no text layer, so every text search of it had returned nothing):

      * IC27, a D74HC139GS, decodes CPU 2's SCS0 with SA14/SA15 into four
        selects: 1Y0 = SMIF (0x100000, the inter-processor link), 1Y1 = WFICS
        (0x104000), 1Y2 = KSCS (0x108000, keybed), 1Y3 = SGCS (0x10C000, tone
        generator) -- the four devices in the order the disassembly had derived
        them from the firmware alone.
      * IC3 takes NSGCE <- WFICS, NWR <- SWR, NRST <- +5MI, MD0..MD15 <-> SD0..SD15
        and NAD <- SA1.  NAD off one address line IS this driver's port pair:
        +0 selects, +2 carries data.
      * IC3's product leaves on RQWFI and IOWFI(0..12) -- nets RQWFI,
        DWFI0..DWFI12 -- into pins 25-40 of IC4, TC183C230002 "TONE GENELATOR
        LSI" (the sheet's spelling), the device at 0x10C000.  IC3 hands the tone
        generator a 13-bit word on request; the two are two stages of ONE signal
        path, not two independent voices, and IC3's output is not audio.
      * IC4's crystal X4 is 33.8688 MHz = 768 x 44100, so the pair's audio rate
        is 44.1 kHz.  IC3's own memory is four private 16-bit DRAM ports M1, M2,
        S1, S2, which the CPU never addresses.

    ⚠ WHAT IS STILL INFERENCE IS THE INTERNAL SIGNAL PATH.  The part, the
    decode and the port are documented; a vocabulary and a coefficient set are
    not a block diagram.  Series or parallel, where the excitation enters, how
    MAIN and SUB are coupled, and whether MUTING's two coefficients are two
    cascaded poles or one stage are all open, and no ROM can close them: the
    device is never read (see below), so there is no readback to calibrate
    against, and the KN5000 sub-CPU -- the control group that gave the tone
    generator twenty-two of its register meanings -- has no counterpart device
    to borrow from.

    ------------------------------------------------------------------------
    ★ IT IS A REGISTER FILE, NOT A PROGRAM LOADER
    ------------------------------------------------------------------------
    Settled by controlled comparison against a KNOWN code-upload path in the
    same firmware -- DSP effect microcode leaving CPU 2 through port P7, a byte
    at a time, with strobes and a 0x1F40 timeout:

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
    +0 register select, +2 data.  Register number = block * 0x40 + channel, 64
    channels, 19 blocks 0x0000 and 0x0040..0x0480, plus the single global 0x0800
    that carries no channel field.  19 x 64 + 1 = 1217 registers.

    Dev104_WriteAllChanRegs (prom_c 0xFB77EF) loads one whole channel:
    `ld XBC,0x00104000` at 0xFB7802, then eighteen `add <rr>,imm16` block
    offsets 0xFB77FE..0xFB794B, register (chan + k*0x40) taking staging word 2*k
    of a 38-byte struct for all nineteen, block 0 written last.

    The whole bus surface is EIGHT driver routines plus one direct write inside
    Dev10C_ResetAllChannels: nine 0x00104000 literals in the image, all stores.
    (wsa1/notes/dev104_apply_regsyms.py --checks, section 3.)

    ⚠ NOTHING READS THIS DEVICE, so data_r() logs unconditionally rather than
    under a VERBOSE mask -- a read is new information.  A tap on CPU 2's program
    space over 45 emulated seconds of boot
    (tools/rigs/wsa1_dev104_bus_trace.lua) saw 2,642 writes, ZERO reads and
    1,217 distinct registers over 0x0000..0x0800, which is the count above.

    NO WRITE-RECOVERY DELAY.  Every 0x0010C000 data write in this firmware is
    followed by five nops of bus padding; that run occurs zero times in the
    eight 0x00104000 routines.

    THE ONLY ATOMIC UNIT IS THE (SELECT, DATA) PAIR.  Block 0 is written LAST in
    1 routine, FIRST in 2, ALONE in 1 and is ABSENT from 4 -- and those four are
    exactly the four with located callers, so every parameter change that
    actually happens lands with no block-0 write after it.  A single register
    write takes effect on its own.
    (FINDINGS-l7a1429-write-sequencing.md secs. 2 and 7.)

    POWER-ON, from Dev10C_ResetAllChannels (0xFB80E1): register 0x0800 := the
    word at ROM 0xFE1313 = 0x1100; then all 64 channels loaded from the 19-word
    ROM image at 0xFE133B; then block 0 rewritten per channel with bit 2
    cleared.  1 + 64*19 + 64 = 1281 register writes.

    ------------------------------------------------------------------------
    THE REGISTERS
    ------------------------------------------------------------------------
    Fourteen of the nineteen blocks are named by the tone editor's own MODELING
    screens; the block names below are the disassembly's DEV104_* symbols
    (prom_c/devices/dev10c_dev104_drivers.s) so a trace and a listing read
    alike.  The others are logged by block NUMBER and are not given a name.

      0x0000  --                    mode/enable word; bits 6..4 gate 0x0300  UNIDENTIFIED
      0x0040  MAIN TUNE             MAIN RESONATOR KEY SHIFT + DETUNE        PROVEN
      0x0080  SUB TUNE              SUB RESONATOR KEY SHIFT + DETUNE         PROVEN
      0x00C0  POSITION              resonator POSITION, a log-domain period  PROVEN
      0x0100  --                    POSITION's table-pair companion          value PROVEN
      0x0140  MAIN FITTING DECAY    MAIN FITTING, decay form                 PROVEN
      0x0180  SUB FITTING DECAY     SUB FITTING, decay form                  PROVEN
      0x01C0  MAIN FITTING RISE     MAIN FITTING, rise form                  PROVEN
      0x0200  SUB FITTING RISE      SUB FITTING, rise form                   PROVEN
      0x0240  DEPTH                 the register the DEPTH control scales    STRONG
      0x0280  SUB GAIN              0..100 percent with an explicit OFF      PROVEN
      0x02C0  --                    the literal 0xFF00 on every path         UNIDENTIFIED
      0x0300  INTERACTION GAIN      an 8-bit gain, 0..127, in both halves    STRONG
      0x0340  MAIN MUTING Q13       Q13 companion of 0x0400                  PROVEN
      0x0380  SUB MUTING Q13        Q13 companion of 0x0440                  PROVEN
      0x03C0  --                    NO EDITOR NAME EXISTS; p15 is a preset   refused
      0x0400  MAIN MUTING Q16       one-pole lowpass cutoff, bilinear        fit PROVEN
      0x0440  SUB MUTING Q16        one-pole lowpass cutoff, bilinear        fit PROVEN
      0x0480  --                    NO EDITOR NAME EXISTS, as 0x03C0         refused
      0x0800  --                    global, no channel; 0x1100 at power-on   UNIDENTIFIED

    0x0240 and 0x0300 are named on the tone editor's PAGE1/2: every value that
    page draws carries its display-RAM address, and the SED1330's own C/R = 40
    turns that into a screen row, putting all five of its values on a caption's
    row against a null mean of 0.19 of 5.  0x0300 has a second, independent
    argument -- it is a MODE-GATED gain, and DEPTH and FORMANT have no reason to
    be mode-gated.  0x03C0 and 0x0480 are REFUSED a name rather than left open:
    no editor ever writes p15, their only input, so the firmware has no caption
    to give them.  (FINDINGS-l7a1429-editor-pages.md secs. 3a, 4, 4a, 4c.)

    THE MAIN/SUB DIRECTION AND THE FITTING/MUTING SPLIT each now have a second,
    independent route, so neither is a single point of failure.  On PAGE1/3 the
    two value rows sit +4 display rows under the MAIN RESONATOR and SUB
    RESONATOR labels the same paint routine draws, with equal offsets -- an
    argument that never mentions SUB GAIN -- and that page's own column headers
    stand over the FITTING and MUTING fields directly, without the caption block
    the old argument rested on.
    (FINDINGS-l7a1429-editor-pages.md secs. 3c, 5.4.)

    Units, for the decoded view LOG_DECODE prints (wsa1/notes/
    FINDINGS-l7a1429-curve-tables.md sec. 1; HLE-GUIDE-l7a1429.md secs. 2.2, 5):

      fold(x)   = (x & 0x8000) ? 0x8000 - (x & 0x7FFF) : x + 0x8000, the
                  firmware's own sign-magnitude -> offset-binary step at 0xFC5361
      0x0400/0x0440/0x0480:  K = fold(v)/(65536 - fold(v)) is tan(pi*fc/fs), the
                  bilinear prewarp; the ROM curve fits round(65536*K/(1+K)) to
                  1 count, with the index a MIDI note minus 36 and an implied
                  fs of 44,091 Hz -- 44,100 to 0.33 cent, agreeing with IC4's
                  crystal by a wholly independent route
      0x0340/0x0380/0x03C0:  the SAME cutoff in Q13: (1 - fold(v)/8192)*K = 1/128
      0x0040/0x0080:  1/256 semitone, so v/256 is a MIDI note number
      0x00C0:  log-domain PERIOD, 3072 counts per octave, pitch entering
                  negated.  ⚠ THE ABSOLUTE SCALE IS UNIDENTIFIED -- only the
                  ratio 2^(v/3072) is known, so no time is printed
      0x0280, 0x0140/0x0180, 0x01C0/0x0200/0x0240:  Q15, v/32768

    ⚠ THE DECODE IS A VIEW OF THE NUMBERS, NOT A MODEL OF THE CHIP.  What is
    proven is that these words ARE bilinear one-pole coefficients and log-domain
    pitches; that the die runs a one-pole with them is STRONG, not measured.

***************************************************************************/

#ifndef MAME_MATSUSHITA_ACOUSTIC_MODELING_H
#define MAME_MATSUSHITA_ACOUSTIC_MODELING_H

#pragma once

// WSA1R_ENABLE_ACOUSTIC_HLE -- compile-time switch for the RESEARCH HLE audio path.
//
// DEFAULT 0: the device is a register file with a decoded, inspectable parameter view and
// synthesises NO audio -- exactly as documented above.  This is the shipped behaviour.
//
// 1: the device additionally becomes a device_sound_interface and RUNS the documented
// coupled digital-waveguide resonator model (ported from kn5000-roms-disasm wsa1/hle/
// l7a1429_hle.py, itself validated against wsa1/notes/HLE-GUIDE-l7a1429.md).  ⚠ This is a
// realization of the DOCUMENTED model, NOT the chip's real audio: the excitation is a
// synthetic stand-in for IC4's UNDUMPED wave ROMs and the POSITION absolute scale is unknown
// (both flagged at their use).  It is opt-in for research, wired to the speakers only under
// this switch (wsa1.cpp), so the default machine is unchanged.  Build:
//   make ... CPPFLAGS=-DWSA1R_ENABLE_ACOUSTIC_HLE=1
#ifndef WSA1R_ENABLE_ACOUSTIC_HLE
#define WSA1R_ENABLE_ACOUSTIC_HLE 0
#endif


// A decoded snapshot of one channel's resonator parameters, in engineering
// units, computed from the raw register file.  This is the device's model of
// the chip's PROGRAMMED STATE: every field is a register whose meaning is graded
// PROVEN or STRONG in the table above, read in the unit the ROM curves fit.
//
// ⚠ IT IS THE INPUT SIDE ONLY.  These are the coefficients the firmware hands
// the chip, not the chip's product: the internal signal path that would turn
// them into IC3's 13-bit stream is unmeasured, and IC4's six wave mask ROMs are
// undumped, so nothing here is rendered to audio.  It exists for the debugger
// and as the drop-in the eventual synthesis reads, the same role reg() has -- a
// faithful HLE of a coefficient-programmed part is its coefficient state, and
// this is that state named and scaled.
struct l7a1429_resonator_params
{
	uint16_t mode = 0;              // 0x0000 raw word; bits 6..4 gate interaction_gain
	double   main_tune_note = 0.0;  // 0x0040, MIDI note number (1/256-semitone steps)
	double   sub_tune_note = 0.0;   // 0x0080, MIDI note number
	double   position_octaves = 0.0;// 0x00C0, log-domain period; ⚠ ABSOLUTE SCALE UNKNOWN,
	                                //          only 2^position_octaves (a ratio) is meaningful
	double   main_fitting_rise = 0.0;   // 0x01C0, Q15 [0,1)
	double   main_fitting_decay = 0.0;  // 0x0140, Q15
	double   sub_fitting_rise = 0.0;    // 0x0200, Q15
	double   sub_fitting_decay = 0.0;   // 0x0180, Q15
	double   depth = 0.0;               // 0x0240, Q15 (STRONG)
	double   sub_gain = 0.0;            // 0x0280, Q15 linear gain (0.0 = the explicit OFF)
	unsigned interaction_gain = 0;      // 0x0300, 0..127 (STRONG), effective only when mode gates it
	double   main_muting_hz = 0.0;      // from 0x0400, the Q16 bilinear one-pole cutoff
	double   sub_muting_hz = 0.0;       // from 0x0440
};


class l7a1429_device : public device_t
#if WSA1R_ENABLE_ACOUSTIC_HLE
	, public device_sound_interface
#endif
{
public:
	l7a1429_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock = 0);

	// 0x104000 +0: the register select (IC3's NAD low).
	void addr_w(uint16_t data);

	// 0x104002 +2: the data register.  Write-only in every code path reached so
	// far; the read exists to catch the one that is not.
	void data_w(uint16_t data);
	uint16_t data_r();

	// Read-back for the debugger and for a future synthesis model.  Out-of-range
	// selects return 0 rather than aliasing, which is this driver's choice: what
	// the real part does with a select above its file is not established.
	uint16_t reg(unsigned n) const { return (n < REG_COUNT) ? m_regs[n] : 0; }

	// The decoded resonator state of one channel (0..VOICES-1), read from the
	// raw register file in engineering units.  The HLE's model of what the
	// firmware has programmed that voice to be; see l7a1429_resonator_params.
	// Out-of-range channels return a zeroed struct.
	l7a1429_resonator_params decoded_channel(unsigned ch) const;

	// The tone editor's name for a block, or nullptr where the block is
	// unidentified.  Fourteen of the nineteen are named; the rest deliberately
	// are not, because a guessed name in a trace is worse than a number.
	static const char *block_name(unsigned block);

protected:
	virtual void device_start() override ATTR_COLD;
#if WSA1R_ENABLE_ACOUSTIC_HLE
	virtual void sound_stream_update(sound_stream &stream) override;
#endif

private:
	// The file is sized to cover every select the firmware is known to form.
	// 0x1000 is the tone generator's ceiling, carried over unchanged from the
	// inline code so the bounds check behaves identically; this device's own
	// per-channel span is only 0x000..0x4BF (19 blocks x 0x40 + 0x3F), plus the
	// single global register 0x0800.
	static constexpr unsigned REG_COUNT = 0x1000;

	// Channel count, from THIS device's own writers: the two loops of
	// Dev10C_ResetAllChannels that call a 0x104000 writer with HL as the channel
	// are closed by `cp HL,0x0040` at prom_c 0xFB81B9 and 0xFB8281.  (The
	// `ldb D,0x40` loop at 0xFB8116 belongs to the tone generator -- 0xFB8102
	// reloads XIX with 0x0010C000 first.)
	static constexpr unsigned VOICES = 64;

	// IC4's crystal X4, 33.8688 MHz = 768 x 44100.  Used only by the decoded
	// view: it is the rate at which the coefficient tables fit.
	static constexpr double SAMPLE_RATE = 44100.0;

	void log_decoded(unsigned block, uint16_t data) const;

	uint16_t m_latch = 0;
	uint16_t m_regs[REG_COUNT]{};

#if WSA1R_ENABLE_ACOUSTIC_HLE
	// ---- the RESEARCH HLE resonator model (ported from l7a1429_hle.py) --------------
	// One digital-waveguide resonator: a delay of `n` samples with a one-pole loss filter
	// (the MUTING damping) in the loop and a feedback gain, plus a POSITION pickup tap.
	static constexpr int WG_MAX = 2048;             // >= fs / lowest note period
	struct waveguide
	{
		double buf[WG_MAX] = { 0 };
		int    n = 2;                               // delay length = the pitch period
		int    i = 0;                               // ring cursor
		double d = 0.0;                             // MUTING one-pole loss coeff (0..1)
		double y1 = 0.0;                            // one-pole state
		double fb = 0.999;                          // loop feedback
		int    tap = 0;                             // POSITION pickup tap (samples)
	};
	// One channel's voice: MAIN + SUB waveguides, mixed by SUB GAIN.  No key-off: it decays
	// autonomously (HLE-GUIDE 7.5).  `age` retires a voice once it has rung down to silence.
	struct hle_voice
	{
		waveguide main, sub;
		double    sub_gain = 0.0;
		bool      active = false;
		double    env_peak = 0.0;                   // running |output| estimate, for retirement
	};
	hle_voice     m_voice[VOICES];
	sound_stream *m_stream = nullptr;
	uint32_t      m_exc_seed = 1;                   // deterministic excitation PRNG state

	void  excite_voice(unsigned ch, const l7a1429_resonator_params &p);
	void  setup_waveguide(waveguide &w, double freq_hz, double muting_hz,
	                      double position, double feedback);
	double run_waveguide(waveguide &w);             // one output sample
#endif
};

DECLARE_DEVICE_TYPE(L7A1429, l7a1429_device)


//**************************************************************************
//  ⚠⚠ ABI GUARD -- read this before toggling WSA1R_ENABLE_ACOUSTIC_HLE
//**************************************************************************
//
//  `WSA1R_ENABLE_ACOUSTIC_HLE' changes `sizeof(l7a1429_device)' by about ONE MEGABYTE: with the
//  HLE on, the class gains `m_voice[VOICES]' and each voice carries `double buf[WG_MAX]'
//  (64 x 2048 x 8 bytes), and it also gains `device_sound_interface' as a base.  With it off the
//  object is ~8 KiB.
//
//  ⛔ WHAT THAT COST, MEASURED 2026-09-14.  `wsa1r' SEGFAULTED on every start, deterministically,
//  in `l7a1429_device::l7a1429_device' -- the faulting instruction a `rep stos', i.e. a memset
//  running off the end of the object.  Cause: the build tree is INCREMENTAL and MAME's build
//  system does not treat ARCHOPTS/CPPFLAGS as a dependency, so `acoustic_modeling.o' (built
//  2026-09-11) and `wsa1.o' (rebuilt 2026-09-14) disagreed about the macro -- one translation
//  unit allocated the small object, the other ran the big object's member initialisers.
//  A `touch' on this file plus a rebuild fixed it, but nothing PREVENTED it.
//
//  ⇒ This guard turns that silent crash into a message that names the cause.  Any translation
//  unit that configures the device calls `l7a1429_abi_check()' BEFORE the device is constructed;
//  it compares its own `sizeof' against the one the device's own translation unit computed, and
//  a mismatch is a `fatalerror' instead of a segfault.
//
//  ⚠ It DETECTS rather than prevents.  The layout could be made macro-independent by putting the
//  HLE state behind a `unique_ptr' and making the sound-interface base unconditional; that is a
//  bigger change to a driver, and it is recorded here as the proper fix rather than done in
//  passing.  The remedy when this fires is a clean rebuild of both files.

// implemented in acoustic_modeling.cpp -- i.e. with THAT file's view of the macro
size_t l7a1429_abi_size();

inline void l7a1429_abi_check()
{
	if (l7a1429_abi_size() != sizeof(l7a1429_device))
		fatalerror("l7a1429_device ABI mismatch: this translation unit says sizeof = %u, "
				"acoustic_modeling.cpp says %u.  WSA1R_ENABLE_ACOUSTIC_HLE disagrees between "
				"them -- almost certainly a STALE OBJECT FILE, because MAME's build system does "
				"not treat -D flags as a dependency.  Rebuild acoustic_modeling.cpp and wsa1.cpp "
				"together (touch both, then rebuild).  See the ABI GUARD note in "
				"acoustic_modeling.h.\n",
				unsigned(sizeof(l7a1429_device)), unsigned(l7a1429_abi_size()));
}

#endif // MAME_MATSUSHITA_ACOUSTIC_MODELING_H

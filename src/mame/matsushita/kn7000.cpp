// license:GPL2+
// copyright-holders:Felipe Sanches
/******************************************************************************

    Technics SX-KN7000 music keyboard driver

    ---------------------------------------------------------------------------
    WORK IN PROGRESS / DRAFT
    ---------------------------------------------------------------------------

    The SX-KN7000 (2002) is the successor of the SX-KN5000 (see kn5000.cpp).
    Unlike the KN5000 - which is driven by a pair of Toshiba TLCS-900
    (TMP94C241) CPUs - the KN7000 main board is built around a single Panasonic
    MN10300/AM33 CPU (little-endian, byte-aligned variable-length 1..7 byte
    instructions).

    As of this writing there is NO execution core for the MN10300/AM33 family in
    MAME: the only existing code is the disassembler at
    src/devices/cpu/mn10300/mn103dasm.cpp. This driver therefore instantiates a
    mn10300_device (declared in src/devices/cpu/mn10300/mn10300.h) whose
    execution core is itself a work in progress. Everything downstream of the
    CPU (peripherals, video, sound) is consequently guesswork and is marked with
    TODO where behavior is unknown.

    Models: besides the KN7000, this file hosts its MN10300/MILK siblings as drafts
    reusing this machine config - SX-KN6000, SX-KN6500, and the SX-KN2400/KN2600/PR54
    family (one shared firmware, runtime model selector). KN5000 is separate (kn5000.cpp).

    ROMs: each flash is modeled as its physical even/odd 16-bit chips, de-interleaved
    from the checksum-verified .SLD firmware-update images and loaded as good dumps
    (the .SLD/.INF block checksums verify the decompression); real chip dumps would
    supersede them. Per-model details live on the kn5000-docs site.

    Memory layout (from firmware static analysis, the mn10300_sim boot trace,
    and the service-test IC map; see the kn5000-docs "Technics KN7000" pages and
    this repo's notes/io-map.md + notes/library-rom-api.md). 112 individual I/O
    registers have been recovered; the banks and their apparent purpose:

        0x20000000  small register block (7 regs; reset writes 0x30/0x03 to
                                          0x20000070)
        0x32000000  system / timers (15 regs; 0x40/0x42 loaded 0x497/0xEA6 at
                                     reset; 0x800 is a 32-bit counter)
        0x34000000  LCD/display controller + key/panel scan (58 regs - the
                                     largest block; see Display subsystem doc)
        0x36008000  bit-mapped control / GPIO (8 regs, all bset/bclr/btst;
                                     0x36008004 toggled 125x = chip selects)
        0x48000000  Table / rhythm flash               (kn7000_table.rom, ~4 MB)
        0x48400000  Program flash                      (kn7000_program.rom, ~4 MB)
        0x4C000000  Library / kernel ROM (undumped, >= ~6 MB): the C runtime +
                                     MILK kernel; 7,965 calls to 298 entry points
                                     (printf @0x4C001A48, memcpy @0x4C003051, ...)
        0x50000000  Work RAM (>2.5 MB used; initial SP = 0x50021CF8)
        0x57800000  Picture flash (undumped; only lightly referenced)
        0x8C000000  device window / video path (boot copies ROM data here)
        0x90000000  framebuffer / LCD V-RAM window (IC104?)
        0x98040000  tone generator (synth LSI IC205, C1BB00000709) - 16-bit register set
        0x98050000  2nd TG register set (parallel 16-bit)
        0x9804/50004  VOICE-EVENT (keyboard) FIFO reads -- the KN5000-shared "keyboard
                     input" interface (KN5000 0x110000: 16-bit, low byte = key code with
                     bit7 = make/break, high byte = velocity; empty = 0xFFFF). This is how physical key presses
                     reach the firmware (parallel to MIDI-in); see notes/tone-generator.md.
                     wave/sample data in undumped ROMs IC203/204/207/208 (C3CBQD00000x)
        0x98020000  sound control (byte regs); 0x98060000/0x98070000 more sound

    Notable work-RAM globals recovered from the disassembly (constants below):
        0x50007578  LCD panel type (0=colour, 2=2-bit grayscale)
        0x5000757A  LCD mode
        0x5000757C  live UI object table (0x38-byte slots; +0x10 = current target)
        0x50122DB8  font descriptor table pointer (0x14-byte entries)
        0x50380004  currently-running task handle
        0x5038002C  main task handle
        0x500D3C5C / 0x500D3C60  per-task (AP / main) focused-object id

    Reset behavior: file offset 0 of the program flash (i.e. CPU address
    0x48400000) contains "jmp 0x4840FF7E", so the reset vector of the AM33 core
    is expected to land at the base of the program flash region. The boot then
    programs the GPIO/timer banks and enters the MILK kernel; mn10300_sim runs
    ~4.59 M instructions before it must call into the undumped 0x4C000000 ROM.

    Hardware blocks named in the service-test IC map (not yet emulated):
        - Program ROMs IC16 / IC17
        - Table / rhythm ROMs
        - Dual tone generators: master TG IC201, sub TG IC205 (both C1BB00000709)
        - Wave/sample ROMs IC203/IC204 (master) + IC207/IC208 (sub), undumped
        - Effects DSP IC306 (ADSP-21065L SHARC) + its SDRAM IC307/IC308
        - Floppy Disk Controller IC103
        - LCD V-RAM IC104
        - Panel sub-CPUs: CPL / CPC / CPR / CPSD
        - SD card
        - USB

******************************************************************************/

#include "emu.h"

#include "cpu/mn10300/mn10300.h"
#include "cpu/sharc/sharc.h"        // IC306 effects DSP (ADSP-21065L; F.1 uses the 21062 core)

#include "bus/midi/midi.h"          // pulls in BUSES["MIDI"] for the focused build
#include "machine/spi_sdcard.h"     // the SD card (SPI protocol via the 0x9805000C byte mailbox)
#include "bus/midi/midiinport.h"
#include "bus/midi/midioutport.h"

#include "screen.h"
#include "speaker.h"          // first-cut audio output

#include "kn7000.lh"

#include <atomic>


// ----------------------------------------------------------------------------
//  KN7000 SIO UART -- byte<->bit bridge between a byte-oriented SIO channel and
//  MAME's bit-serial midi_port. One instance per MIDI channel (31250 baud, 8N1).
//  Modelled on src/mame/misc/vocalizer.cpp's UART.
// ----------------------------------------------------------------------------
class kn7000_sio_uart_device : public device_t, public device_serial_interface
{
public:
	kn7000_sio_uart_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock = 0);

	auto tx_cb() { return m_tx_cb.bind(); }      // each TX bit -> midi_port write_txd
	auto rx_cb() { return m_rx_cb.bind(); }      // each fully-received byte -> driver

	void write(uint8_t data) { transmit_register_setup(data); }
	bool tx_empty() const { return is_transmit_register_empty(); }

protected:
	virtual void device_start() override {}
	virtual void device_reset() override ATTR_COLD;

	virtual void tra_callback() override { m_tx_cb(transmit_register_get_data_bit()); }
	virtual void rcv_complete() override { receive_register_extract(); m_rx_cb(get_received_char()); }

	devcb_write_line m_tx_cb;
	devcb_write8 m_rx_cb;
};

DEFINE_DEVICE_TYPE(KN7000_SIO_UART, kn7000_sio_uart_device, "kn7000_sio_uart", "KN7000 SIO MIDI UART")

DECLARE_DEVICE_TYPE(KN7000_TONEGEN, kn7000_tonegen_device)

// ---------------------------------------------------------------------------
// kn7000_tonegen_device -- FIRMWARE-DRIVEN audio output (Phase C, Stage 2).
//
// The real tone generators (IC201/IC205) play PCM from the four undumped wave ROMs.
// This device does not have those samples, but it IS driven by the real firmware
// voice engine: every tone-generator register write is routed to tg_write(), and we
// render a placeholder sine per voice using the firmware's own pitch (class 0x2401)
// and note-on/off gating (0x2401 write / 0x0001=0xC000 mute). So pitch, polyphony,
// timing and note events are authentic; only the timbre is a stand-in until the wave
// ROMs are dumped. The path (stream, speakers, DAC) is proven; the machine is
// MACHINE_IMPERFECT_SOUND. See notes/tg-voice-register-semantics.md.
// ---------------------------------------------------------------------------
class kn7000_tonegen_device : public device_t, public device_sound_interface
{
public:
	kn7000_tonegen_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock = 0)
		: device_t(mconfig, KN7000_TONEGEN, tag, owner, clock)
		, device_sound_interface(mconfig, *this)
	{ }

	// Kept for the key-bed input hook (kn7000_state::kbd_key). No longer synthesizes
	// directly: with the TG-enable gate open the FIRMWARE drives every voice through
	// tg_write() below, so keying a second sine here would double the notes.
	void note_on(uint8_t)  { }
	void note_off(uint8_t) { }

	// Stage 2 -- FIRMWARE-DRIVEN synthesis. Every tone-generator register write (both
	// TGs) is routed here from io_w. Once the TG-enable gate is open (see the
	// 0x98070000 strap in io_r) the firmware programs a full per-voice block on each
	// note and we render audio from these registers:
	//   * class 0x2400/0x2401 = the pitch register: an 18-bit SAMPLE-ZONE-RELATIVE
	//     log-pitch, pitch18 = ((class bit0)<<16) | data, at 0x400/semitone. It is
	//     NOT absolute musical pitch: the firmware bakes each tone's element-
	//     descriptor tuning (zone center key, key-scale exponent, coarse/fine) into
	//     the value (lib pitch pipeline: init 0x4C030FB9, runtime 0x4C031127,
	//     transform ((pitch16+0x1800)<<2)&0x3FFFF, write primitive 0x4C036F98), so
	//     each tone sits at a different offset and unpitched drums use a constant.
	//     The MUSICAL pitch therefore comes from the caller (io_w) which resolves it
	//     from the library's voice record (notePitch16, see tg_pitch_resolve()); the
	//     raw pitch18 is kept as the per-note reference so later rewrites on a held
	//     voice apply as RELATIVE bends (vibrato/portamento/pitch bend).
	//     A pitch write on an idle voice gates it ON (attack); on a held voice it is
	//     a bend, not a retrigger (new notes are always preceded by the mute).
	//   * class 0x0001 = 0xC000 = the voice mute the firmware writes on note-off /
	//     voice-steal -> gate the voice OFF (release).
	// Timbre is a placeholder sine: the real PCM wave ROMs (IC203/4/7/8) are undumped,
	// so authentic samples are not yet possible. addr = [group:6][channel:6][index:4].
	// note_x256: musical pitch in 1/256-semitone units resolved from the firmware's
	// voice record by the caller, or -1 if unavailable (fall back to the legacy
	// keybed-anchored absolute decode of pitch18).
	void tg_write(int tg, uint16_t addr, uint16_t data, int32_t note_x256 = -1)
	{
		if ((addr & 0xFF00) == 0xFC00) return;            // 0xFC0x idle / status refresh
		const int v = (tg << 6) | ((addr >> 4) & 0x3F);   // voice 0..127 (0..63 sub, 64..127 master)
		const uint16_t cls = addr & 0xFC0F;               // register class (channel masked out)
		if ((cls & 0xFC0E) == 0x2400)                     // pitch (bit0 = pitch18 bit16)
		{
			const uint32_t p18 = (uint32_t(cls & 1) << 16) | data;
			m_stream->update();
			if (!m_gate[v])
			{
				// note-on: musical pitch from the resolved voice-record notePitch16
				// when available; else the legacy absolute decode (anchored where
				// pitch18 0x1C838 = MIDI 96, the keybed top-C reference).
				const double note = (note_x256 >= 0) ? double(note_x256) / 256.0
				                                     : 96.0 + (double(p18) - double(0x1C838)) / 1024.0;
				m_note[v]   = note;
				m_p18ref[v] = p18;
				m_freq[v]   = 440.0 * pow(2.0, (note - 69.0) / 12.0);
				m_gate[v]   = 1;      // held
				m_atk[v]    = 1;      // start the attack
				m_phase[v]  = 0.0;    // clean attack transient
				// Resolve this voice's amplitude envelope from the firmware's EG registers.
				// CONFIRMED by live capture (piano vs organ/strings): SUS1 (r7) is the sustain
				// level -- 0x2C (~35%) for the decaying Concert Grand, 0x7F (max) for sustaining
				// organ/strings -- so a held note now decays or sustains per the sound. The decay
				// time is scaled from DCY2 (r8) and calibrated so the Concert Grand's ~1.8 s decay
				// is preserved; the exact chip rate curve + release (rA) are still provisional.
				constexpr double FS = 44100.0;
				const double sus  = std::clamp(double(m_envreg[v][3] >> 8) / 127.0, 0.0, 1.0);      // SUS1
				const double dcyT = std::clamp(1.8 * pow(2.0, (0x99 - double(m_envreg[v][4] >> 8)) / 10.0), 0.03, 8.0); // from DCY2
				m_sus[v]  = sus;
				m_dcyc[v] = exp(-1.0 / (dcyT * FS));
				m_rlsc[v] = exp(-1.0 / (0.12 * FS));   // ~120 ms release (provisional; rA curve TBD)
			}
			else
			{
				// held voice: RELATIVE pitch update (bend/vibrato/portamento) around
				// the note-on reference, 0x400 pitch18 units per semitone.
				const double note = m_note[v] + (double(p18) - double(m_p18ref[v])) / 1024.0;
				m_freq[v] = 440.0 * pow(2.0, (note - 69.0) / 12.0);
			}
			m_tgwrites++;
		}
		else if (cls == 0x0001)                           // 0xC000 = voice mute -> note-off
		{
			if (data == 0xC000) { m_stream->update(); m_gate[v] = 0; }
		}
		else if (cls == 0x2009)                           // per-voice level (best-effort)
		{
			// The firmware writes this once at note-on; in the default full-velocity
			// patch it is 0x5FFF, so normalising by 0x5FFF keeps that voice at unity
			// (no change to the current sound) while honouring softer/louder values
			// the firmware would emit for MIDI velocity or the mixer's part volumes.
			m_stream->update();
			m_level[v] = std::clamp(double(data) / double(0x5FFF), 0.0, 1.4);
		}
		else if (cls >= 0x0004 && cls <= 0x000A)          // amplitude-envelope params r4..rA
		{
			// The firmware writes the sound's per-voice amplitude EG (7 halfwords, ATK PEAK
			// DCY1 SUS1 DCY2 SUS2 RLS) just before the note-on pitch write. Cache them; the
			// note-on resolves them into a decay/sustain/release. (See notes/tg-envelope-*.)
			m_envreg[v][cls - 0x0004] = data;
		}
	}
	uint32_t tg_write_count() const { return m_tgwrites; }

protected:
	virtual void device_start() override
	{
		m_stream = stream_alloc(0, 2, 44100);
		std::fill(std::begin(m_phase), std::end(m_phase), 0.0);
		std::fill(std::begin(m_freq),  std::end(m_freq),  0.0);
		std::fill(std::begin(m_env),   std::end(m_env),   0.0);
		std::fill(std::begin(m_gate),  std::end(m_gate),  0);
		std::fill(std::begin(m_atk),   std::end(m_atk),   0);
		std::fill(std::begin(m_level), std::end(m_level), 1.0);
		std::fill(std::begin(m_sus),   std::end(m_sus),   0.0);
		std::fill(std::begin(m_dcyc),  std::end(m_dcyc),  0.0);
		std::fill(std::begin(m_rlsc),  std::end(m_rlsc),  0.0);
		save_item(NAME(m_phase));
		save_item(NAME(m_freq));
		save_item(NAME(m_note));
		save_item(NAME(m_p18ref));
		save_item(NAME(m_env));
		save_item(NAME(m_gate));
		save_item(NAME(m_atk));
		save_item(NAME(m_level));
		save_item(NAME(m_envreg));
		save_item(NAME(m_sus));
		save_item(NAME(m_dcyc));
		save_item(NAME(m_rlsc));
		save_item(NAME(m_tgwrites));
	}

	// Per-voice amplitude envelope DRIVEN BY THE FIRMWARE'S EG registers (resolved at note-on
	// into m_sus / m_dcyc / m_rlsc, see tg_write). Each voice: fast attack to peak, exponential
	// decay toward the sound's SUSTAIN level, hold there while the firmware keeps the voice gated,
	// then exponential release once it is muted. A decaying sound (piano, low sustain) fades toward
	// its low sustain; a sustaining sound (organ/strings, sustain = max) holds -- the audible
	// difference the old fixed "always decay to silence" envelope threw away.
	virtual void sound_stream_update(sound_stream &stream) override
	{
		constexpr double FS = 44100.0;
		constexpr double TWO_PI = 6.28318530717958647692;
		const double atk = 1.0 / (0.006 * FS);         // linear ~6 ms attack (click-free)
		for (int s = 0; s < stream.samples(); s++)
		{
			double acc = 0.0;
			for (int v = 0; v < 128; v++)
			{
				if (m_atk[v])                                  // attack: ramp to peak
				{
					m_env[v] += atk;
					if (m_env[v] >= 1.0) { m_env[v] = 1.0; m_atk[v] = 0; }
				}
				else if (m_gate[v])                            // held: decay toward the sustain level
				{
					m_env[v] = m_sus[v] + (m_env[v] - m_sus[v]) * m_dcyc[v];
				}
				else                                           // released: decay to silence
				{
					m_env[v] *= m_rlsc[v];
					if (m_env[v] < 0.0005) m_env[v] = 0.0;
				}
				if (m_env[v] <= 0.0) continue;
				acc += sin(m_phase[v]) * m_env[v] * m_level[v];
				m_phase[v] += TWO_PI * m_freq[v] / FS;
				if (m_phase[v] >= TWO_PI) m_phase[v] -= TWO_PI;
			}
			float smp = std::clamp(float(acc * 0.11), -1.0f, 1.0f);  // headroom for polyphony
			stream.put(0, s, smp);
			stream.put(1, s, smp);
		}
	}

private:
	sound_stream *m_stream = nullptr;
	double   m_phase[128] = { };     // per-voice oscillator phase
	double   m_freq[128]  = { };     // per-voice frequency (Hz)
	double   m_note[128]  = { };     // per-voice musical note at note-on (bend reference)
	uint32_t m_p18ref[128] = { };    // per-voice pitch18 at note-on (bend reference)
	double   m_env[128]   = { };     // per-voice envelope level
	uint8_t  m_gate[128]  = { };     // per-voice gate: 1 = firmware note held, 0 = muted/released
	uint8_t  m_atk[128]   = { };     // per-voice attack-in-progress flag
	double   m_level[128] = { };     // per-voice level (firmware class 0x2009; 1.0 = default full)
	// Per-voice AMPLITUDE ENVELOPE, driven by the firmware's own EG registers (group-0 regs
	// 0x04-0x0A = ATK,PEAK,DCY1,SUS1,DCY2,SUS2,RLS; see notes/tg-envelope-implementation-plan.md).
	// Captured live: sustaining sounds (organ/strings) write a HIGH SUS1 (r7=0x7F), decaying
	// sounds (piano) write a LOW SUS1 (r7=0x2C) -- so the note now sustains or decays per the sound.
	uint16_t m_envreg[128][7] = { };  // raw r4..rA per voice (index 0..6)
	double   m_sus[128]  = { };       // resolved sustain level 0..1 (from SUS1)
	double   m_dcyc[128] = { };       // per-sample decay coefficient (toward sustain)
	double   m_rlsc[128] = { };       // per-sample release coefficient (toward 0)
	uint32_t m_tgwrites = 0;         // count of firmware pitch writes seen (0 = engine dormant)
};

DEFINE_DEVICE_TYPE(KN7000_TONEGEN, kn7000_tonegen_device, "kn7000_tonegen", "KN7000 Tone Generator (firmware-driven, placeholder timbre)")

DECLARE_DEVICE_TYPE(KN7000_DSP_BRIDGE, kn7000_dsp_bridge_device)

// ---------------------------------------------------------------------------
// kn7000_dsp_bridge_device -- routes the tone-generator audio through the effects
// DSP (F.3). It sits between the TG and the speakers with 2 inputs and 2 outputs.
// The audio-thread stream and the CPU-timeline IRQ0 tick (kn7000_state::dsp_audio_tick)
// exchange samples through two rings: the stream pushes each TG frame into rx (the DSP's
// input) and pops the DSP's processed frame from tx (to the speakers); the tick consumes
// rx (writing the SPORT input buffer) and produces tx (reading the SPORT output buffer).
// Both run at ~44.1 kHz, so the rings stay balanced; when the DSP is not running (tx
// empty) the bridge simply passes the TG through, so it is transparent with the DSP off.
// Samples in the rings are 24-bit signed (the SPORT word format).
// ---------------------------------------------------------------------------
class kn7000_dsp_bridge_device : public device_t, public device_sound_interface
{
public:
	kn7000_dsp_bridge_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock = 0)
		: device_t(mconfig, KN7000_DSP_BRIDGE, tag, owner, clock)
		, device_sound_interface(mconfig, *this)
	{ }

	// Called from the DSP IRQ0 tick (CPU timeline): take one TG input frame, hand back one
	// processed output frame. 24-bit signed samples.
	void pop_input(int32_t &l, int32_t &r)
	{
		if (m_rx_rd != m_rx_wr) { l = m_rx[m_rx_rd][0]; r = m_rx[m_rx_rd][1]; m_rx_rd = (m_rx_rd + 1) % RING; }
		else { l = r = 0; }   // underflow: DSP consumed ahead of the stream (brief; harmless)
	}
	void push_output(int32_t l, int32_t r)
	{
		if (!m_dsp_active) { m_dsp_active = true; m_rx_rd = m_rx_wr; }   // first output: flush stale pre-DSP input
		m_tx[m_tx_wr][0] = l; m_tx[m_tx_wr][1] = r;
		m_tx_wr = (m_tx_wr + 1) % RING;
		if (m_tx_wr == m_tx_rd) m_tx_rd = (m_tx_rd + 1) % RING;   // overflow: drop oldest (bound latency)
	}

	// Master output gain (0..1), set from the front-panel MAIN VOLUME slider by the driver.
	void set_master_gain(float g) { m_master_gain = g; }

protected:
	virtual void device_start() override
	{
		m_stream = stream_alloc(2, 2, 44100);
		save_item(NAME(m_rx));   save_item(NAME(m_tx));
		save_item(NAME(m_rx_rd)); save_item(NAME(m_rx_wr));
		save_item(NAME(m_tx_rd)); save_item(NAME(m_tx_wr));
		save_item(NAME(m_dsp_active)); save_item(NAME(m_tx_primed)); save_item(NAME(m_tx_last));
	}

	virtual void device_reset() override
	{
		m_rx_rd = m_rx_wr = m_tx_rd = m_tx_wr = 0;
		m_dsp_active = false; m_tx_primed = false;
		m_tx_last[0] = m_tx_last[1] = 0;
	}

	virtual void sound_stream_update(sound_stream &stream) override
	{
		constexpr float SCALE = 8388607.0f;   // 2^23 - 1
		for (int s = 0; s < stream.samples(); s++)
		{
			// push this TG input frame into the DSP's input ring (float -> 24-bit signed),
			// dropping the oldest if full so the DSP always sees recent input (low latency).
			const int32_t il = int32_t(std::clamp(stream.get(0, s), -1.0f, 1.0f) * SCALE);
			const int32_t ir = int32_t(std::clamp(stream.get(1, s), -1.0f, 1.0f) * SCALE);
			m_rx[m_rx_wr][0] = il; m_rx[m_rx_wr][1] = ir;
			m_rx_wr = (m_rx_wr + 1) % RING;
			if (m_rx_wr == m_rx_rd) m_rx_rd = (m_rx_rd + 1) % RING;

			int32_t ol, orr;
			if (!m_dsp_active)
			{
				ol = il; orr = ir;   // effects DSP off -> transparent passthrough
			}
			else
			{
				// Consume the DSP's output only once a small latency buffer has built up, then
				// hold the last sample on underflow. NEVER fall back to the TG here: mixing the
				// (latent) DSP output with the immediate TG phase-cancels and clicks.
				const uint32_t fill = (m_tx_wr - m_tx_rd + RING) % RING;
				if (!m_tx_primed && fill >= PRIME) m_tx_primed = true;
				if (m_tx_primed && m_tx_rd != m_tx_wr)
				{
					ol = m_tx[m_tx_rd][0]; orr = m_tx[m_tx_rd][1]; m_tx_rd = (m_tx_rd + 1) % RING;
					m_tx_last[0] = ol; m_tx_last[1] = orr;
				}
				else { ol = m_tx_last[0]; orr = m_tx_last[1]; }
			}
			// Front-panel MAIN VOLUME slider: a master output attenuation on the final mix
			// (modelled as a post-DAC analog-style gain; the driver pushes the taper via
			// set_master_gain from the VOL_MAIN adjuster). 1.0 = unity.
			const float g = m_master_gain;
			stream.put(0, s, (float(ol) / SCALE) * g);
			stream.put(1, s, (float(orr) / SCALE) * g);
		}
	}

private:
	static constexpr int RING = 2048;
	static constexpr uint32_t PRIME = 128;   // ~2.9 ms latency buffer before consuming DSP output
	sound_stream *m_stream = nullptr;
	int32_t m_rx[RING][2] = { };   // TG -> DSP input
	int32_t m_tx[RING][2] = { };   // DSP output -> speakers
	uint32_t m_rx_rd = 0, m_rx_wr = 0, m_tx_rd = 0, m_tx_wr = 0;
	bool m_dsp_active = false;     // the DSP has started producing output
	bool m_tx_primed = false;      // the output latency buffer has filled
	int32_t m_tx_last[2] = { };    // last DSP output (held on underflow)
	std::atomic<float> m_master_gain{ 1.0f };   // MAIN VOLUME slider (audio thread reads, driver writes)
};

DEFINE_DEVICE_TYPE(KN7000_DSP_BRIDGE, kn7000_dsp_bridge_device, "kn7000_dsp_bridge", "KN7000 Effects-DSP audio bridge")

kn7000_sio_uart_device::kn7000_sio_uart_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock) :
	device_t(mconfig, KN7000_SIO_UART, tag, owner, clock),
	device_serial_interface(mconfig, *this),
	m_tx_cb(*this),
	m_rx_cb(*this)
{
}

void kn7000_sio_uart_device::device_reset()
{
	set_data_frame(1, 8, PARITY_NONE, STOP_BITS_1);   // MIDI: 8N1
	set_rate(31250);                                  // MIDI baud
}


namespace {

class kn7000_state : public driver_device
{
public:
	kn7000_state(const machine_config &mconfig, device_type type, const char *tag)
		: driver_device(mconfig, type, tag)
		, m_maincpu(*this, "maincpu")
		, m_screen(*this, "screen")
		, m_workram(*this, "workram")
		, m_vram(*this, "vram")
		, m_lcdbuf(*this, "lcdbuf")
		, m_progrom(*this, "maincpu")
		, m_midi_uart(*this, "midi_uart%u", 0U)
		, m_kbd_midi_uart(*this, "kbdmidi_uart")
		, m_tonegen(*this, "tonegen")
		, m_dspbridge(*this, "dspbridge")
		, m_dsp(*this, "dsp")
		, m_seg(*this, "SEG%02X", 0U)
		, m_dial(*this, "DIAL")
		, m_rearsw(*this, "REARSW")
		, m_sdsw(*this, "SDSW")
		, m_sdcard(*this, "sdcard")
		, m_sdcover(*this, "SDCOVER")
		, m_volmain(*this, "VOL_MAIN")
		, m_cpl_leds(*this, "cpl_led%u", 0U)
		, m_cpc_leds(*this, "cpc_led%u", 0U)
		, m_cpr_leds(*this, "cpr_led%u", 0U)
	{ }

	void kn7000(machine_config &config) ATTR_COLD;
	void kn6000(machine_config &config) ATTR_COLD;
	DECLARE_INPUT_CHANGED_MEMBER(kbd_key);     // PC-key note -> voice-event FIFO (public: PORT_CHANGED_MEMBER)
	DECLARE_INPUT_CHANGED_MEMBER(sd_cover_changed);   // SD slot cover toggle (public: PORT_CHANGED_MEMBER)

protected:
	virtual void machine_start() override ATTR_COLD;
	virtual void machine_reset() override ATTR_COLD;

private:
	required_device<mn10300_device> m_maincpu;
	required_device<screen_device> m_screen;
	required_shared_ptr<uint32_t> m_workram;
	required_shared_ptr<uint32_t> m_vram;        // LCD V-RAM window at 0x90000000
	required_shared_ptr<uint32_t> m_lcdbuf;      // firmware's composited RGB565 LCD image @0x9CE00000
	bool m_lib_mirror = false;                   // KN6000/KN6500: library @0x4C/0x8C mirrors the program ROM
	bool m_lcd_kn6 = false;                      // KN6000/KN6500: LCD framebuffer is RGB555 and mounted rotated 180deg (vs the KN7000's upright RGB565)
	required_region_ptr<uint32_t> m_progrom;     // program flash (holds the CLUT)
	required_device_array<kn7000_sio_uart_device, 2> m_midi_uart;
	required_device<kn7000_sio_uart_device> m_kbd_midi_uart;  // MIDI -> internal key bed (velocity)
	required_device<kn7000_tonegen_device> m_tonegen;   // first-cut audio (Phase C Stage 0)
	required_device<kn7000_dsp_bridge_device> m_dspbridge;  // F.3: routes TG audio through the effects DSP
	required_device<adsp21065l_device> m_dsp;           // IC306 effects DSP (ADSP-21065L SHARC; host-boot idle until F.2)

	template <int Ch> void midi_rx(uint8_t data) { sio_rx_push(Ch, data); }

	// Control panel button ports and LEDs (CPL = 8 cols, CPC = 5 cols; CPR + the
	// serial HLE device that reads these / drives the LEDs are still to come).
	required_ioport_array<0x21> m_seg;  // one per normalized segment 0x00-0x20
	required_ioport m_dial;
	required_ioport m_rearsw;           // rear-panel MIDI IN / BASS PEDAL selector SW701 (strap bit12 = data-bus D28)
	required_ioport m_sdsw;               // SD front-panel switches (byte 0x9CC00008, active-low)
	optional_device<spi_sdcard_device> m_sdcard;   // the SD card (SPI protocol via the 0x9805000C byte mailbox)
	required_ioport m_sdcover;             // SD slot cover switch (open/closed)
	required_ioport m_volmain;             // front-panel MAIN VOLUME slider (0-100 adjuster)
	output_finder<512> m_cpl_leds;
	output_finder<64> m_cpc_leds;
	output_finder<512> m_cpr_leds;

	void maincpu_mem(address_map &map) ATTR_COLD;

	// bring-up logging handlers for the (not-yet-decoded) I/O banks
	uint16_t io_r(offs_t offset, uint16_t mem_mask = ~0);
	void io_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);

	// --- On-chip interrupt controller (INTC) at 0x34000100 ------------------
	// GxICR(group) = 0x34000100 + group*4 (16-bit): bit0 DETECT, bit4 REQUEST,
	// bit8 ENABLE, bits12-14 LEVEL. 0x34000100/0x104 double as the IAGR the
	// (self-loaded) library dispatcher reads to find the pending group. A source
	// is pending when its REQUEST bit is set; the CPU maskable line is asserted
	// while any ENABLE&REQUEST source exists. See notes/interrupt-mechanism.md.
	enum { IRQGRP_TIMER = 0x06, IRQGRP_PANEL = 0x1A, IRQGRP_MIDI1 = 0x12, IRQGRP_MIDI2 = 0x14 };
	uint16_t intc_r(offs_t offset, uint16_t mem_mask = ~0);
	void intc_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);
	void intc_assert(int group);
	void intc_recompute();
	int  intc_pending_group() const;
	uint16_t m_gxicr[0x20] = { };
	IRQ_CALLBACK_MEMBER(irq_ack);              // latches IAGR (group+vector) at accept
	bool m_c11_unserviced = false;             // a panel transfer-complete not yet accepted
	int m_iagr_latch = 0;
	uint16_t m_intc_280 = 0;                   // 0x34000280 latched control fields
	uint16_t m_snd_500e = 0;                   // 0x9805000E readback latch (sound init spins on it)
	// Keyboard / voice-event FIFO (read at 0x98050004). The firmware polls it for
	// note events from the key bed (KN5000-shared "keyboard input"; 16-bit word,
	// low byte = KEY code, high byte = velocity; 0xFFFF = empty). MAKE/BREAK is
	// encoded in BIT 7 of the key byte, NOT in the velocity: the firmware decoder
	// does btst 0x80 on the key byte (0x484480e5 routes the event; 0x48448151 gates
	// the voice: bit7=0 -> compute pitch / gate ON, bit7=1 -> clear gate / key up).
	// So a release must set bit 7 (key | 0x80); a bit7=0 word with velocity 0 is
	// still a NOTE-ON (that was the "stuck notes" bug). A release velocity of 0xFF is
	// the clean key-up: it bypasses the sustain/hold re-latch at 0x484480fa (cmp 0xff
	// -> skip the 0x501496a2 held-key store that would otherwise re-gate the note).
	uint16_t m_kbd_fifo[16] = { };
	uint8_t  m_kbd_head = 0, m_kbd_tail = 0;
	void kbd_push(uint8_t note, uint8_t vel)
	{ m_kbd_fifo[m_kbd_head & 15] = uint16_t(note) | (uint16_t(vel) << 8); m_kbd_head++; }

	// --- MIDI -> internal KEY BED bridge (velocity-sensitive) ------------------
	// A MIDI controller wired here plays the machine's OWN key bed (the voice-
	// event FIFO the firmware polls at 0x98050004), NOT the rear MIDI IN jacks:
	// note-on/off become key-bed events with the MIDI velocity, so the firmware
	// treats them exactly like physical key presses (self-tests that watch the
	// key bed see them, and dynamics/velocity are honoured). The key bed's FIFO
	// value is the KEY INDEX (internal note = index + 36 = MIDI note); MIDI note
	// n maps to index n-36, i.e. the 61-key compass C2(36)..C7(96). Notes outside
	// are clamped into range. Connect a host controller with -kbdmidi <port>.
	uint8_t m_kbd_midi_status = 0;             // MIDI running-status byte
	uint8_t m_kbd_midi_d1 = 0;                  // first data byte (note)
	bool    m_kbd_midi_have_d1 = false;
	void kbd_midi_rx(uint8_t b)
	{
		if (b & 0x80)                          // status byte
		{
			if (b >= 0xF8) return;             // real-time messages: ignore
			m_kbd_midi_status = (b < 0xF0) ? b : 0;   // system-common clears running status
			m_kbd_midi_have_d1 = false;
			return;
		}
		const uint8_t cmd = m_kbd_midi_status & 0xF0;
		if (cmd != 0x90 && cmd != 0x80) return;       // only note-on / note-off
		if (!m_kbd_midi_have_d1) { m_kbd_midi_d1 = b; m_kbd_midi_have_d1 = true; return; }
		const uint8_t note = m_kbd_midi_d1, vel = b;
		m_kbd_midi_have_d1 = false;            // ready for the next note in running status
		if (note < 36 || note > 96) return;    // outside the 61-key bed
		const uint8_t idx = note - 36;
		const bool on = (cmd == 0x90) && (vel != 0);
		// make/break = bit 7 of the key byte (see the FIFO note above). A release
		// (MIDI note-off, or note-on velocity 0) sets bit 7; velocity 0xFF = clean
		// key-up. A note-on passes the MIDI velocity straight through.
		kbd_push(on ? idx : uint8_t(idx | 0x80), on ? vel : 0xff);
	}
	// Tone generators (main 0x98040000 / sub 0x98050000): register-indirect,
	// write-only from the firmware. Address latched at base+0, data written at
	// base+2 -> reg[address]. Voice registers are group<<8|bank<<6|channel
	// (< 0x1000); the 0xFC0x system-refresh group is accepted but not stored.
	// See notes/tone-generator.md. (State capture; synthesis is future work.)
	uint16_t m_tg_addr[2] = { 0, 0 };          // latched register address, [0]=main [1]=sub
	uint16_t m_tg_reg[2][0x10000] = { };       // captured voice-register file (FULL 16-bit address
	                                           // space -- the old [0x1000] + <0x1000 gate silently
	                                           // dropped the per-voice pitch/key-on writes at 0x2000+)

	// --- Effects DSP (IC306 ADSP-21065L) host port -------------------------
	// The CPU host-boots the SHARC through an index register at 0x98000000 and a
	// data register at 0x9C000000 (the 0x9C bank the driver otherwise treats as
	// LCD RAM). At boot the firmware probes DSP register 0 expecting 0x20; if it
	// reads anything else it sets a "DSP dead" flag (work-RAM 0x500066CC) and
	// SUPPRESSES the whole effect engine (see notes/dsp-host-interface.md +
	// notes/dsp-effect-catalog.md). Because the driver backs 0x9C000000 with
	// stale RAM, the probe currently fails and effects never run.
	//
	// This host interface answers the DSP probe + self-test handshake and captures the
	// download stream, driving the real ADSP-21065L (IC306). The KN7000 ALWAYS has this
	// DSP, so it is unconditionally present -- with the self-test completion handshake now
	// modeled (group 0x17, see intc_w), the firmware keeps 0x500066CC="present" and the
	// runtime effect-upload gate stays open, so selecting a reverb/chorus reaches the DSP.
	uint16_t dsp_data_r(offs_t offset, uint16_t mem_mask);
	void     dsp_data_w(offs_t offset, uint16_t data, uint16_t mem_mask);
	bool     dsp_present() { return true; }        // IC306 ADSP-21065L is always fitted
	bool     tg_sound_enabled() { return true; }   // IC201/IC205 tone generators are always fitted

	// Resolve the MUSICAL pitch for a TG pitch write from the library's per-slot
	// voice record. The record array is 0x500AF940 + slot*0xB4 (128 slots; slots
	// 0x00-0x3F drive 0x98050000 = our tg index 1, 0x40-0x7F drive 0x98040000 =
	// tg index 0, per the lib write primitive 0x4C036F98), and is fully populated
	// BEFORE the first pitch write of a note reaches the TG (race-free by
	// construction). Fields (RE + runtime-verified, notes/tg-pitch-pipeline.md):
	//   +0x08 byte: bit7 = record active, bits 0-6 = internal note
	//   +0x0C u16:  notePitch16 = (note<<8) + 0x80 + part transpose + master tune
	//               + scale stretch = the MUSICAL pitch in 1/256-semitone units --
	//               exactly what our placeholder-sine synthesis should sound.
	// The exp-7 (key-scale-off) case -- unpitched drums -- leaves notePitch16 at
	// the formula constant 0x4280; return -1 there (and for inactive records) so
	// the tonegen keeps its raw-pitch18 decode for those voices.
	int32_t tg_pitch_resolve(int tg, uint16_t tgaddr)
	{
		if ((tgaddr & 0xFC0E) != 0x2400)
			return -1;                                       // not a pitch write
		const int slot = ((tgaddr >> 4) & 0x3F) | (tg == 0 ? 0x40 : 0x00);
		auto &sp = m_maincpu->space(AS_PROGRAM);
		const offs_t rec = 0x500AF940 + slot * 0xB4;
		if (!(sp.read_byte(rec + 0x08) & 0x80))
			return -1;                                       // record not active
		const uint16_t np16 = sp.read_word(rec + 0x0C);
		if (np16 == 0x4280 || np16 == 0 || np16 > 0x7FFF)
			return -1;                                       // unpitched (exp-7 constant) / implausible
		return int32_t(np16) - 0x80;                         // 1/256-semitone units
	}
	uint16_t m_dsp_index = 0;                  // latched host register index (0x98000000)
	uint32_t m_dsp_dl_words = 0;               // count of download words written to the SHARC
	// F.2 host-boot upload state (see dsp_data_w): the firmware sets a target address (reg
	// 0x40), commits a PM/DM block (reg 0x1C = 0xA1/0x41), then streams words to the DMA
	// buffer (index 0x04, 3x16 per 48-bit PM word / 2x16 per 32-bit DM word).
	uint32_t m_dsp_dl_addr = 0;                // reg 0x40: download target address (2x16, low then high)
	uint32_t m_dsp_cur = 0;                    // current auto-incrementing write address in the active block
	uint8_t  m_dsp_mode = 0;                   // active block: 1 = PM (0xA1), 2 = DM (0x41)
	uint16_t m_dsp_wbuf[3] = { };              // streamed-word accumulator
	uint8_t  m_dsp_wcnt = 0;
	bool     m_dsp_block_open = false;         // a PM/DM block is open (0xA1/0x41 seen, awaiting its 0xA0)
	bool     m_dsp_running = false;            // released from host-boot to run (set at first end/sync)
	// Provisional effects-DSP audio frame rate: drives the IRQ0 tick that steps the SHARC
	// kernel's main loop one frame per edge. Stands in for the SPORT/codec frame sync until
	// F.3 models the real serial audio path; value is a plausible placeholder, not measured.
	static constexpr int DSP_FRAME_HZ = 44100;
	emu_timer *m_dsp_irq_timer = nullptr;      // periodic: pulse the SHARC's IRQ0 (audio frame tick)
	TIMER_CALLBACK_MEMBER(dsp_audio_tick);
	emu_timer *m_sys_timer = nullptr;
	TIMER_CALLBACK_MEMBER(sys_tick);
	emu_timer *m_fav_timer = nullptr;      // one-shot: pre-load Favorites SRAM after the boot BSS-clear
	TIMER_CALLBACK_MEMBER(fav_preload);

	// --- On-chip 16-bit TEMPO timer (mode 0x34001082 / base 0x34001092 / count 0x340010A2)
	// The clock behind ALL sequenced playback. The firmware registers ISR
	// 0x48447084 -- a 96-PPQN tick counter (increments a mod-0x60 beat phase at
	// 0x50149664 and drives five sub-tick consumers) -- on INTC group 7 (GxICR
	// 0x3400011C, level 4, registration at 0x4844780C), and programs this timer's
	// reload to the current tempo (start sequence at 0x484477D3: write mode ->
	// write base -> bset/bclr 0x40 [load] -> bset 0x80 [count enable]; tempo
	// changes rewrite the base at 0x48447888 while running). With the timer
	// unmodeled the tick never fired: rhythm accompaniment never started, demo
	// songs played only their first (synchronously fired) event then stalled,
	// and the ApTimer software-timer layer never ran. IOCLK = 16 MHz (from the
	// firmware's own MIDI-baud math: IOCLK/8/(TM3BR+1) = 31250 => 16 MHz).
	uint8_t  m_tmr7_mode = 0;              // bit7 = count enable, bit6 = load pulse, low bits = source/prescale
	uint16_t m_tmr7_base = 0;              // 16-bit reload (underflow period)
	emu_timer *m_tempo_timer = nullptr;
	TIMER_CALLBACK_MEMBER(tempo_tick);

	// --- SD card-detect (GxICR group 0x1B pin, register 0x3400016C) ------------
	// The card/lid switch is an external-interrupt pin whose ICR the firmware
	// POLLS (strobe: write 1 to clear DETECT, read back, btst bit4/REQUEST):
	// bit4 SET = no card / lid open, CLEAR = card present (reader 0x4854bce0,
	// debounce 0x4854bd39). The SD state machine is DEMAND-DRIVEN off the detect
	// TRANSITION: the debounced 1->0 edge fires the SdCover widget path -> insert
	// message 0x107020bb arg=1 -> SD state 1 (handler 0x48551920). A line that is
	// statically "present" from power-on never edges, so no event ever fires --
	// model the card as ABSENT at power-on and INSERT it a few seconds after
	// boot. (RE: workflow wf_d6998fbd-c86, notes/sd-card-emulation-plan.md.)
	// The absent state is held via DETECT bit1 (the firmware's strobe w1c-clears
	// bit0 only, so bit1 survives and keeps REQUEST/bit4 set through strobes).
	emu_timer *m_sd_insert_timer = nullptr;
	TIMER_CALLBACK_MEMBER(sd_insert);

	// The SD slot has a hinged COVER; the firmware reads the cover switch as the
	// card-detect line (cover closed + card in = accessible; cover open => the
	// firmware refuses access with "ERROR 93: SD lid is open"). Model it as a
	// user switch (SDCOVER, default CLOSED) plus the attached image: card-detect
	// "present" = cover CLOSED and an image is mounted. Toggling the cover live
	// produces the debounced edge -- closing (with a card) fires the insert /
	// mount, opening triggers the removal + the ERROR 93 gate.
	void sd_update_carddetect()
	{
		if (m_lib_mirror) return;
		const bool cover_open = (m_sdcover->read() & 1) != 0;
		const bool card = m_sdcard && m_sdcard->get_card_present();
		if (!cover_open && card)
			m_gxicr[0x1B] &= ~0x001F;                  // bit4=0: present (closed + card)
		else
			m_gxicr[0x1B] |= 0x0012;                   // bit4=1: no card / lid open
	}

	// --- SD mailbox (register 0x9805000C + ICR group 0x1C handshake) ----------
	// The firmware speaks the STANDARD SD-card SPI protocol through this byte
	// mailbox (captured live: 10x 0xFF wake-up clocks, then CMD0 = 40 00 00 00
	// 00 95, then R1 response reads). Send-byte primitive 0x4854bf4d: W1C-clear
	// DETECT bit0 of ICR 0x34000170, write the byte to 0x9805000C, poll bit4
	// (REQUEST) for the transfer-complete ack. Each mailbox write clocks the
	// byte through MAME's spi_sdcard device (8 bits, MISO collected into
	// m_sdmbx_out) and asserts group 0x1C. Reads return the MISO byte -- i.e.
	// the register behaves as the usual full-duplex SPI data latch.
	uint16_t m_sdmbx_out = 0xFF;               // last MISO byte (mailbox read value)
	uint16_t m_gpio8004 = 0xFFFF;              // GPIO latch 0x36008004 (bit1 = SD SPI CS, active-low)
	uint8_t  m_sdmbx_miso = 0;                 // MISO bit collector (spi_miso callback)
	void cpsd_mbx_write(uint16_t data);
	void sd_miso_w(int state) { m_sdmbx_miso = uint8_t(m_sdmbx_miso << 1) | (state & 1); }
	void tmr7_mode_w(uint8_t data);
	void tmr7_base_w(uint16_t data);
	void tmr7_rearm(bool restart_phase);

	// --- SIO ASIC: three USART channels at 0x34000800 / 0x810 / 0x820 -------
	// ch0 = control panel, ch1 = MIDI port 1, ch2 = the SD sub-CPU "CPSD"
	// (MN102H60) -- NOT MIDI-2 as first assumed: the SD firmware polls ch2 status
	// (0x3400082c bit7) ~370k times while an SD screen waits and never touches it
	// on non-SD screens (RE 2026-07-08, notes/sd-card-emulation-plan.md). Per
	// channel, at +0x10 stride:
	//   +0 config(16) · +4 control(8) · +8 TX-data(8) · +9 RX-data(8) · +C status(16)
	enum { SIO_PANEL = 0, SIO_MIDI1 = 1, SIO_MIDI2 = 2, SIO_SD = 2 };
	uint16_t sio_r(offs_t offset, uint16_t mem_mask = ~0);
	void sio_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);
	void sio_tx_byte(int ch, uint8_t data);
	void sio_rx_push(int ch, uint8_t data);
	bool sio_rx_ready(int ch) const { return m_sio_rx_head[ch] != m_sio_rx_tail[ch]; }
	uint8_t sio_rx_pop(int ch);

	uint16_t m_sio_config[3] = { 0, 0, 0 };
	uint8_t  m_sio_control[3] = { 0, 0, 0 };
	uint8_t  m_sio_rx_fifo[3][64] = { };   // small ring buffer per channel
	uint8_t  m_sio_rx_head[3] = { 0, 0, 0 };
	uint8_t  m_sio_rx_tail[3] = { 0, 0, 0 };

	// --- Control-panel HLE (the sub-CPU side of the panel serial link) ------
	// LED command bytes arrive as 2-byte [ADDR][DATA] frames on the panel TX;
	// each DATA bit is one LED of the register selected by ADDR. Buttons are
	// scanned from the ioports and reported back as 2-byte [ADDR][DATA] frames
	// on the panel RX (only delivered to the firmware once the MN10300 core
	// takes SIO interrupts -- see notes/panel-serial-protocol.md).
	TIMER_CALLBACK_MEMBER(panel_scan);
	void panel_led_frame(uint8_t addr, uint8_t data);
	uint8_t m_panel_resp[64] = { };        // pending panel->main bytes (replies + button events)
	void panel_queue(const uint8_t *bytes, int n);  // append + kick the ATN delivery
	int     m_panel_resp_len = 0, m_panel_resp_pos = 0;
	TIMER_CALLBACK_MEMBER(panel_event);    // deferred ATN edges / RX-byte delivery
	emu_timer *m_panel_evt = nullptr;      // one-shot; param: 1=ATN edge, 2=deliver RX byte
	emu_timer *m_panel_txdone = nullptr;   // one-shot: sync-transfer complete -> group 0x11

	// --- CPSD (SD sub-CPU MN102H60) HLE on SIO channel 2 --------------------
	// The SD card is reached over SIO ch2. Delivery model (RE 2026-07-08): the
	// The CPSD link (ch2) speaks MIDI FRAMING (RE 2026-07-10): the RX classifier
	// 0x484b28ee + real-time dispatcher 0x484b2454 route >=0xF8 bytes as MIDI
	// real-time (0xF8 Clock -> tempo module 0x48447366, 0xFA/0xFB/0xFC Start/
	// Continue/Stop -> transport, 0xFE ActiveSense -> alive bit6 @0x50150f55 with
	// a ~0x87-tick watchdog), and 0xF0..0xF7 SysEx into the library MIDI engine
	// (0x4C024A1F). This fits the hardware: the CPSD streams SD-Song MIDI data
	// and wraps control/status in SysEx; the SD panel's transport buttons arrive
	// as real-time Start/Stop. cpsd_queue() pushes CPSD->main bytes into the ch2
	// RX FIFO (status bits in sio_r reflect it); cpsd_rx_byte() consumes
	// main->CPSD bytes. Frame payload semantics still under RE.
	void cpsd_queue(const uint8_t *bytes, int n);   // (unused since the ch2=MIDI-2 finding; kept for a future SD transport)
	bool    m_cpsd_probed = false;         // (retired with the ch2 probe)
	emu_timer *m_panel_timer = nullptr;
	int     m_panel_pos = 0;               // position within the 7-byte TX frame
	uint8_t m_panel_p1 = 0, m_panel_p2 = 0; // frame payload bytes (positions 2 and 4)
	uint8_t m_btn_prev[0x21] = { }; // last scanned state, one per normSeg 0x00-0x20

	uint32_t screen_update(screen_device &screen, bitmap_rgb32 &bitmap, const rectangle &cliprect);
};


void kn7000_state::maincpu_mem(address_map &map)
{
	// The MN10300/AM33 has a flat 32-bit little-endian address space.

	// --- Table / rhythm flash -------------------------------------------
	// kn7000_table.rom, decompressed size 0x3E94D4 bytes (~4 MiB).
	map(0x48000000, 0x483fffff).rom().region("table", 0);

	// --- Program flash --------------------------------------------------
	// kn7000_program.rom, decompressed size 0x3F6F01 bytes (~4 MiB).
	// Held in program ROMs IC16 / IC17. CPU begins execution here
	// (0x48400000 -> "jmp 0x4840FF7E").
	map(0x48400000, 0x487fffff).rom().region("maincpu", 0);

	// --- Work RAM -------------------------------------------------------
	// The firmware sets the initial SP to 0x50021CF8 and, when single-stepped
	// through boot with the mn10300_sim interpreter, touches RAM past 0x50298000
	// (>2.5 MB), so the real work RAM (IC12/IC13) is larger than the ~1.5 MB BSS.
	// TODO: confirm the exact size; mapping 4 MB here as a working estimate.
	map(0x50000000, 0x503fffff).ram().share("workram");

	// --- Device windows found by executing the boot (mn10300_sim) -------
	// The boot code writes to 0x90000000 and 0x8C000000 (copying from the top of
	// the program ROM). Neither is in the static I/O map (notes/io-map.md); they
	// are almost certainly the LCD V-RAM / video / wave-DMA windows. Mapped as RAM
	// placeholders so bring-up can proceed past them.
	// TODO: identify the real devices (LCD V-RAM = IC104?).
	// KEY: the "library ROM" at 0x4C000000 is NOT a physical/undumped ROM. The
	// boot LOADS it at runtime from the program flash: InitializeBlock27
	// (0x484D7BBD) copies ~253 KB from program-ROM 0x487B8FD1.. into logical
	// 0x4C000000, but its copy loop adds 0x40000000 so the bytes actually land at
	// 0x8C000000 -- and the code later executes at the 0x4C000000 alias. Mapping
	// BOTH ranges to the same RAM lets the firmware populate its own library ROM,
	// so the boot runs real library code with no dump and no HLE. (Proven by
	// tracing the boot in mn10300_sim; see notes/library-rom-loading.md.)
	map(0x4c000000, 0x4cffffff).ram().share("libram");
	map(0x8c000000, 0x8cffffff).ram().share("libram");
	map(0x90000000, 0x97ffffff).ram().share("vram");   // LCD controller window (regs + trampolines)
	// NOTE: 0x96800000-0x969FFFFF within this range is actually the WRITABLE custom-data
	// FLASH (AMD 29LV160-class; unlock cmds to 0x9680AAAA/0x96805554), programmed by the
	// "Initial Data" disk (idd7000). Modeled here as blank RAM -> empty -> style names /
	// Favorites / Custom default. TODO: split out as a real flash device + load the
	// installed content. See notes/initial-data-disk-and-custom-flash.md.

	// Further windows the boot reaches only AFTER the library ROM loads and runs
	// (found by execution). 0x44000000 is a heavily read/written ~1 MB block
	// (RAM/buffer); 0x9C000000 holds an unidentified peripheral at 0x9CC00000.
	// Mapped as RAM placeholders so bring-up proceeds. TODO: identify these.
	// 0x44000000 and its +0x40000000 alias 0x84000000 are the same RAM (the same
	// one-bit window pair as the library ROM 0x4c/0x8c). Boot init copies record
	// arrays to 0x84030FF8..; without the alias those writes were dropped.
	map(0x44000000, 0x44ffffff).ram().share("ram44");
	map(0x84000000, 0x84ffffff).ram().share("ram44");
	map(0x9c000000, 0x9cffffff).ram().share("lcdbuf");   // firmware's composited LCD image (RGB565) lives at 0x9CE00000
	// SD front-panel switch register (byte 0x9CC00008, ACTIVE-LOW: bits0-5 = the
	// six CPSD-side transport switches, 1 = released). The firmware's SD-panel
	// scan reads it on TG-present boots (scan-enable write 0x9cc00004=0xC0 is
	// TG-gated); left as plain RAM it reads 0x00 = ALL SWITCHES PRESSED, which
	// fires six phantom SD-button events and makes the boot take over the UI
	// with the SD screen -- the long-standing "TG-present boot lands on the SD
	// menu" mystery (RE + live-verified, wf_d6998fbd-c86: with idle switches the
	// TG-present boot reaches the PMEM home screen). Reads return idle bits0-5;
	// bytes 1-3 of the dword (incl. the 0x9cc00009 control byte the card-detect
	// strobe RMWs) stay RAM-backed. Writes fall through to the RAM share.
	if (!m_lib_mirror)
		map(0x9cc00008, 0x9cc0000b).lr32(NAME([this](offs_t) -> uint32_t
		{
			return (m_lcdbuf[0x00C00008 >> 2] & 0xFFFFFF00) | (~m_sdsw->read() & 0x3F);
		}));
	// Override the low 4 bytes: 0x9C000000 is the effects-DSP host DATA port
	// (paired with the index at 0x98000000), NOT LCD RAM. The framebuffer at
	// 0x9CE00000 and the rest of the bank stay RAM (this narrower entry wins).
	map(0x9c000000, 0x9c000003).rw(FUNC(kn7000_state::dsp_data_r), FUNC(kn7000_state::dsp_data_w));

	// --- Stubs for regions whose behavior is still unknown --------------
	// TODO: Library / boot ROM (undumped) at 0x4C000000. The firmware calls
	//       into it (e.g. a printf-like renderer at 0x4C001A48), so this is
	//       real code, not just data.
	//map(0x4c000000, 0x4c0fffff).rom().region("library", 0);

	// Data-flash READ views (byte-verified RE, notes/initial-data-disk-and-custom-flash.md):
	//   0x56000000 = the CUSTOM writable flash's read view (programmed by the "Initial Data"
	//                disk idd7000; command/program aperture is a SEPARATE window at 0x96800000,
	//                AMD unlocks 0x9680AAAA -- same 2MB 29LV160 chip). A u32-offset directory
	//                archive lives at flash-offset 0x200. THIS is where the custom-flash image
	//                must be ROM_LOADed once the AST install codec is reversed.
	//   0x57000000 = FACTORY read-only rhythm/style flash (extends the table ROM).
	// Both UNDUMPED; read-as-0 placeholders so boot-time pointer parsing is stable. Empty ->
	// style names / Custom fall back to defaults (the "8 Beat 1" bug).
	map(0x56000000, 0x577fffff).ram().share("dataflash");

	// TODO: Picture flash (splash / bitmap graphics), separate device.
	//map(0x57800000, 0x57ffffff).rom().region("picture", 0);

	// --- I/O register banks -------------------------------------------------
	// 112 I/O registers were recovered by static analysis of the firmware (see
	// notes/io-map.md for the per-register table). Mapped here to logging
	// handlers so every access is visible during bring-up; real device decode
	// (LCD, tone generators, panel, FDC, ...) comes later.
	//   0x20000000  small register block (reset writes 0x30/0x03 to 0x20000070)
	//   0x32000000  system / timers (0x40/0x42 = 0x497/0xEA6 at reset; 0x800 counter)
	//   0x34000000  large peripheral block, 58 regs (likely LCD/display + key/panel)
	//   0x36008000  bit-mapped control / GPIO (0x36008004 toggled 125x)
	//   0x98040000 & 0x98050000  parallel 16-bit sets = the DUAL tone generators
	//                            (main TG IC203/204 + sub TG IC207/208); plus
	//                            0x98020000/0x98060000/0x98070000 sound control
	map(0x20000000, 0x2000ffff).rw(FUNC(kn7000_state::io_r), FUNC(kn7000_state::io_w));
	map(0x32000000, 0x3200ffff).rw(FUNC(kn7000_state::io_r), FUNC(kn7000_state::io_w));
	map(0x34000000, 0x3400ffff).rw(FUNC(kn7000_state::io_r), FUNC(kn7000_state::io_w));
	// On-chip interrupt controller (GxICR array + IAGR) -- more-specific override.
	map(0x34000100, 0x340002ff).rw(FUNC(kn7000_state::intc_r), FUNC(kn7000_state::intc_w)); // GxICR block + the 0x34000200 scheduler-level group reg
	// KN6000/KN6500: the firmware polls the on-chip 16-bit timer counters (TMnBC at
	// 0x340010a0+) as busy-wait delays. Return an advancing (down-counting) value so
	// those loops progress. The KN7000 keeps the generic 0x34000000 handler.
	if (m_lib_mirror)
		map(0x340010a0, 0x340010af).lr16(NAME([this](offs_t o) { return uint16_t(-(m_maincpu->total_cycles() >> 4)); }));
	// KN7000: the on-chip 16-bit TEMPO timer (see the member declarations for the
	// full RE). mode byte @0x34001082, 16-bit reload @0x34001092, counter
	// @0x340010A2; underflow asserts INTC group 7 = the firmware's 96-PPQN
	// sequencer tick. The sibling registers (0x1080/0x1090/0x10A0, another timer
	// touched only by early boot) keep the previous behaviour: log + read 0.
	if (!m_lib_mirror)
	{
		map(0x34001080, 0x34001083).lrw16(
			NAME([this](offs_t o) -> uint16_t { return o ? m_tmr7_mode : 0; }),
			NAME([this](offs_t o, uint16_t data, uint16_t mem_mask) { if (o && ACCESSING_BITS_0_7) tmr7_mode_w(data & 0xff); }));
		map(0x34001090, 0x34001093).lrw16(
			NAME([this](offs_t o) -> uint16_t { return o ? m_tmr7_base : 0; }),
			NAME([this](offs_t o, uint16_t data, uint16_t mem_mask) { if (o) tmr7_base_w(data); }));
		map(0x340010a0, 0x340010a3).lr16(
			NAME([this](offs_t o) -> uint16_t
			{
				if (!o || !(m_tmr7_mode & 0x80)) return 0;
				// live down-count derived from the emu_timer phase
				const attotime period = m_tempo_timer->period();
				if (period.is_never() || period.is_zero()) return 0;
				return uint16_t(uint64_t(m_tmr7_base + 1) * m_tempo_timer->remaining().as_attoseconds() / period.as_attoseconds());
			}));
	}
	// The SIO ASIC (panel + two MIDI channels) is a decoded sub-block of the
	// 0x34000000 bank; this more-specific mapping overrides the logger above.
	map(0x34000800, 0x3400082f).rw(FUNC(kn7000_state::sio_r), FUNC(kn7000_state::sio_w));
	map(0x36008000, 0x360080ff).rw(FUNC(kn7000_state::io_r), FUNC(kn7000_state::io_w));
	// GPIO input port 0x36008084: bit 0 = panel-link ready/presence line, held
	// HIGH by the panel sub-CPUs. The TX state machine's state-1 handler tests it
	// (btst 0x01 at 0x484AC80C) and ABORTS the whole transaction back to state 0
	// if clear -- with a 0 stub no handshake command could ever be transmitted.
	map(0x36008084, 0x36008085).lr16(NAME([]() -> uint16_t { return 0x0001; }));
	// GPIO output latch 0x36008004: bit1 = the SD card's SPI CHIP SELECT
	// (active-low: bclr = assert/select, bset = release/deselect). The firmware
	// brackets every SD SPI transaction with it (assert 0x4854bc8f / release
	// 0x4854bc85), and the >= 74 init clocks are issued with CS RELEASED. Drive
	// MAME's spi_sdcard select from it (the device resets its SPI state on the
	// CS rising edge, so correct framing is required for card-init to complete).
	// Other bits are plain GPIO -- keep a shadow so bset/bclr RMW is preserved.
	if (!m_lib_mirror)
		map(0x36008004, 0x36008005).lrw16(
			NAME([this](offs_t) -> uint16_t { return m_gpio8004; }),
			NAME([this](offs_t, uint16_t data, uint16_t mem_mask)
			{
				COMBINE_DATA(&m_gpio8004);
				if (m_sdcard)
					m_sdcard->spi_ss_w((m_gpio8004 & 0x0002) ? 0 : 1);   // active-low CS
			}));
	map(0x98000000, 0x9807ffff).rw(FUNC(kn7000_state::io_r), FUNC(kn7000_state::io_w));

	// TODO: replace the logging handlers with real device models: LCD V-RAM
	//       (IC104), FDC (IC103), tone generators (IC201/IC205), effects DSP
	//       IC306 (ADSP-21065L) + SDRAM IC307/IC308, panel sub-CPUs
	//       (CPL/CPC/CPR/CPSD), SD card and USB blocks.
}


// Bring-up placeholder: log every I/O access and return 0. The CPU accesses
// these banks at 8/16/32-bit widths; a 16-bit handler with mem_mask lets MAME
// route all of them. One handler serves all five banks, so `offset` is relative
// to the mapped range -- shift left 1 for the byte offset within the bank. The
// decoded per-register list is in notes/io-map.md.
uint16_t kn7000_state::io_r(offs_t offset, uint16_t mem_mask)
{
	// 0x98070000 (offset 0x38000 within the 0x98000000 window): a status/strap word.
	// Boot init reads it and, if bit 15 is CLEAR, branches into a lengthy factory
	// power-on diagnostic (a battery of RAM/HW tests whose results are bit-banged
	// out on a panel GPIO with multi-second software delays -- not the normal boot
	// path). On real hardware bit 15 is set, so the diagnostic is skipped. Model
	// that here (guard at program-flash 0x484A4FDA: btst 0x8000,d0 / beq 0x484A4FE3).
	if (offset == 0x38000)
		// Rear-panel config strap (16-bit, on the upper half of the data bus). bit15 =
		// skip the factory power-on diagnostic (see above). bit12 (= data-bus D28, gated
		// by the EXP-port output-enable) = the rear-panel MIDI IN / BASS PEDAL selector
		// SW701: BassPedalSw (0x484A2CB1) -> 0x484b2615 reads bit12 and stores !bit12 into
		// the MIDI-in mode flag 0x5006bfd2 bit1. bit12 SET = MIDI IN, clear = Bass Pedals.
		//
		// bits 1..2 = the tone-generator-present strap read by the TG probe at
		// 0x484d7713: bit1 CLEAR makes the probe return "3 = no TG", which leaves the
		// sound library's TG-enable gate (RAM 0x500ce380) at 0x7F and SUPPRESSES every
		// per-voice register write forever (the instrument stays silent). The real
		// KN7000 has both tone generators (IC201/IC205); reporting them present
		// (bit1|bit2) opens the gate and the firmware drives the TGs on every note.
		// Gated behind a machine-config switch (default OFF) because opening it also
		// lets boot advance into the still-paused SD subsystem, which then rests on the
		// SD Card menu instead of the home screen -- so sound is opt-in for now.
		return 0x8000 | (tg_sound_enabled() ? 0x0006 : 0) | (m_rearsw->read() & 0x1000);
	// 0x98050004 (offset 0x28002): the VOICE-EVENT / keyboard FIFO -- the interface
	// the KN5000 firmware calls "keyboard input" (KN5000 0x110000: read voice events,
	// low byte = KEY code with bit 7 = make/break flag, high byte = velocity). The
	// firmware polls it for note on/off from the physical key bed (parallel to
	// MIDI-in); bit7=0 -> note-on, bit7=1 -> note-off (see kbd_push). Boot init reads it in a
	// loop until it yields 0xFFFF (empty / end marker; also the floating-bus value).
	// Returning 0 made the loop treat 0 as a valid note-0 event forever. Return 0xFFFF
	// = empty so the loop terminates (loop at 0x484480A2: movhu (0x98050004); cmp
	// 0xffff; beq exit). Push note/velocity words via kbd_push() to play the key bed.
	if (offset == 0x28002)
	{
		if (!machine().side_effects_disabled() && m_kbd_head != m_kbd_tail)
			return m_kbd_fifo[m_kbd_tail++ & 15];
		return 0xFFFF;
	}
	// 0x9805000E (offset 0x28007): sound-interface register; the init loop at
	// 0x4854BC59 writes a value (d1|0x80) and spins until it READS BACK what it
	// wrote (setlb/lne with a 2-tick timeout) -- a readback latch unblocks it.
	if (offset == 0x28006)                            // 0x9805000C: SD mailbox data latch
		return m_sdmbx_out;
	if (offset == 0x28007)
		return m_snd_500e;
	if (!machine().side_effects_disabled())
		logerror("%s: io_r  +%06X mask %04X\n", machine().describe_context(),
			offset << 1, mem_mask);
	return 0;
}

void kn7000_state::io_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	if (offset == 0x28007)                        // 0x9805000E readback latch
	{
		COMBINE_DATA(&m_snd_500e);
		return;
	}
	// Tone-generator register-indirect write interface (write-only; see the
	// member declaration and notes/tone-generator.md). Modeling it here captures
	// the register file and keeps the constant TG traffic out of the io_w log.
	switch (offset)
	{
	case 0x28006:                                                 // 0x9805000C: SD mailbox data latch
		cpsd_mbx_write(data);
		return;
	case 0x00000: m_dsp_index = data; return;                     // 0x98000000: effects-DSP host register index
	case 0x20000: m_tg_addr[0] = data; return;                    // main TG: address latch (0x98040000)
	case 0x20001:                                                 // main TG: data (0x98040002) -> reg[addr]
		m_tg_reg[0][m_tg_addr[0]] = data;                         // capture the FULL address (was gated <0x1000)
		m_tonegen->tg_write(0, m_tg_addr[0], data,                // Stage 2: feed the real TG voice engine
			tg_pitch_resolve(0, m_tg_addr[0]));
		return;
	case 0x28000: m_tg_addr[1] = data; return;                    // sub TG: address latch (0x98050000)
	case 0x28001:                                                 // sub TG: data (0x98050002) -> reg[addr]
		m_tg_reg[1][m_tg_addr[1]] = data;
		m_tonegen->tg_write(1, m_tg_addr[1], data,
			tg_pitch_resolve(1, m_tg_addr[1]));
		return;
	case 0x20002: case 0x20008:                                   // main TG control (0x98040004 / 0x98040010)
		return;
	}
	logerror("%s: io_w  +%06X = %04X mask %04X\n", machine().describe_context(),
		offset << 1, data, mem_mask);
}

// Effects-DSP host DATA port at 0x9C000000 (paired with the index at 0x98000000).
uint16_t kn7000_state::dsp_data_r(offs_t offset, uint16_t mem_mask)
{
	if (!dsp_present())
		return 0;
	// Answer the host register read selected by the latched index. The boot probe
	// (fw 0x48405028) reads register 0 and requires 0x20 to consider the DSP alive.
	switch (m_dsp_index)
	{
	case 0x00: return 0x0020;    // probe: "DSP present / ready"
	case 0x0B: return 0x1065;    // ID/version readback (plausible 21065L id; exact value TBD)
	case 0x37: return 0x0000;    // status: busy (bit7) clear
	default:   return 0x0000;
	}
}

void kn7000_state::dsp_data_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	if (!dsp_present())
		return;
	// F.2 host-boot: decode the upload protocol and write the streamed program/data into
	// the SHARC's internal memory. Register writes to 0x9C000000 carry their reg number as
	// the index (32-bit value = 2x16, low then high); the actual program/data streams via
	// index 0x04 (the external-port DMA buffer), 3x16 per 48-bit PM word / 2x16 per 32-bit
	// DM word, auto-incrementing from the reg-0x40 target. See notes/sharc-lle-assessment.md.
	switch (m_dsp_index)
	{
	case 0x40:  // download target address (low then high)
		m_dsp_dl_addr = (m_dsp_dl_addr >> 16) | (uint32_t(data) << 16);
		return;
	case 0x1c:  // block command strobe (low half = command)
		// Upload framing: 0xA1/0x41 opens a PM/DM block (target = reg-0x40 addr), words stream
		// via index 0x04, then 0xA0 closes the block. The whole download is bracketed by two
		// "bare" 0xA0s (no block open): the first (before any block) is a reset handshake; the
		// last (after the final block) is the "go". Release the SHARC on that final bare 0xA0.
		if (data == 0xa1)      { m_dsp_mode = 1; m_dsp_cur = m_dsp_dl_addr; m_dsp_wcnt = 0; m_dsp_block_open = true; }  // PM commit
		else if (data == 0x41) { m_dsp_mode = 2; m_dsp_cur = m_dsp_dl_addr; m_dsp_wcnt = 0; m_dsp_block_open = true; }  // DM commit
		else if (data == 0xa0)                                                                 // end / sync
		{
			if (m_dsp_block_open)
			{
				m_dsp_block_open = false;                         // closes the current block
				// A RUNTIME upload (SHARC already running, e.g. selecting a reverb) that lands in
				// PROGRAM memory (mode 1) changes live code behind the DRC's back -- its self-modify
				// detection only fires for PM writes issued by the SHARC itself, so notify_pm_written()
				// would flush the recompiled cache and let the newly-uploaded effect run. That IS the
				// correct behaviour and it DOES make the effect execute -- but the currently-modelled
				// effect pipeline then emits SILENCE (the running microprogram reads its input and its
				// SDRAM delay lines yet writes 0 to the output slot 0xC350; likely an unset wet/dry mix
				// coefficient or an output routed to a TX slot the bridge doesn't read). Until that is
				// resolved, leaving the cache stale keeps the (audible) boot passthrough rather than
				// regressing to silence. Re-enable once the effect output is non-zero.
				// See notes/dsp-effect-execution-chain.md.
				if (m_dsp_running && m_dsp_mode == 1)
					m_dsp->notify_pm_written();
			}
			else if (!m_dsp_running && m_dsp_dl_words > 0)        // bare 0xA0 after the last block = "go"
			{
				m_dsp_running = true;
				logerror("DSP: kernel loaded (%u words); releasing SHARC (entry 0x8005)\n", m_dsp_dl_words);
				m_dsp->set_input_line(INPUT_LINE_HALT, CLEAR_LINE);   // reset_pc()=0x8004 -> first-executed 0x8005 (JUMP init)
				// Start the audio frame tick: the kernel's reset handler enables IRQ0 and then
				// IDLEs (PM 0x8076) waiting for the first IRQ0, which drives its main loop one
				// audio frame per edge. On real hardware IRQ0 comes from the SPORT/codec frame
				// sync; here a periodic pulse stands in until F.3 models the serial audio path.
				// Provisional rate -- see notes/sound-subsystem-plan.md (F.3).
				m_dsp_irq_timer->adjust(attotime::from_hz(DSP_FRAME_HZ), 0, attotime::from_hz(DSP_FRAME_HZ));
			}
		}
		return;
	case 0x04:  // streamed program/data words -> SHARC internal memory
		if (m_dsp_mode == 1)        // 48-bit PM word (3x16, MSW first)
		{
			m_dsp_wbuf[m_dsp_wcnt++] = data;
			if (m_dsp_wcnt == 3)
			{
				// The firmware streams the 3 halfwords LSW-first, so the 48-bit PM word is
				// wbuf[2]:wbuf[1]:wbuf[0] (verified: puts the opcode field in the high bits).
				const uint64_t w = (uint64_t(m_dsp_wbuf[2]) << 32) | (uint64_t(m_dsp_wbuf[1]) << 16) | m_dsp_wbuf[0];
				m_dsp->space(AS_PROGRAM).write_qword(m_dsp_cur++, w);
				m_dsp_wcnt = 0; m_dsp_dl_words++;
			}
		}
		else if (m_dsp_mode == 2)   // 32-bit DM word (2x16, low first)
		{
			m_dsp_wbuf[m_dsp_wcnt++] = data;
			if (m_dsp_wcnt == 2)
			{
				const uint32_t w = (uint32_t(m_dsp_wbuf[1]) << 16) | m_dsp_wbuf[0];
				m_dsp->space(AS_DATA).write_dword(m_dsp_cur++, w);
				m_dsp_wcnt = 0; m_dsp_dl_words++;
			}
		}
		return;
	}
}


// ============================================================================
//  On-chip interrupt controller (INTC)
// ============================================================================
// The library-ROM interrupt handler (self-loaded, entry 0x4C03DDA0) reads the
// pending group from the IAGR at 0x34000100, indexes its handler table, and
// calls the registered ISR callback. offset is the 16-bit word index within
// 0x34000100; group = offset/2, register = 0x34000100 + group*4.

int kn7000_state::intc_pending_group() const
{
	// Among enabled+requested groups, the winner is the highest-priority one =
	// the LOWEST ICR LEVEL value (bits 14:12). Firmware programs: SIO panel/MIDI
	// groups 0x12-0x15 LEVEL=1, 0x0F/0x19 LEVEL=3, group 7 LEVEL=4, and the
	// system tick (group 6) LEVEL=6 -- the lowest priority in the system.
	int best = 0, best_level = 8;
	for (int g = 2; g < 0x20; g++)
		if ((m_gxicr[g] & 0x0110) == 0x0110)   // ENABLE(0x100) & REQUEST(0x10)
		{
			const int level = (m_gxicr[g] >> 12) & 7;
			if (level < best_level) { best_level = level; best = g; }
		}
	return best;
}

// Freeze the arbitration result (group AND vector, atomically) at the instant
// the CPU accepts the interrupt -- the real INTC latches IAGR at acknowledge.
IRQ_CALLBACK_MEMBER(kn7000_state::irq_ack)
{
	const int g = intc_pending_group();
	if (g)
	{
		m_iagr_latch = g;
		if (g == 0x11)
			m_c11_unserviced = false;
		const int level = (m_gxicr[g] >> 12) & 7;
		// KN7000: hardcoded firmware handlers. KN6000/KN6500: ALL maskable IRQs vector to the
		// firmware trampoline slot 0 (0x90000000 -> the general handler, which reads the latched
		// group at 0x34000200 and dispatches). Slot 1 (0x90000006 -> 0x4847b19d) is the KN6000's
		// EXCEPTION/fault handler (disables IRQs + halts), NOT an IRQ dispatch -- routing IRQs
		// there halts the boot (was the 0x4847b238 hang). See notes/kn6000-kn6500-boot.md.
		m_maincpu->set_irq_vector(m_lib_mirror ? 0x90000000
		                                       : (level == 6 ? 0x4C03DE26 : 0x4C03DDA0));
		m_maincpu->set_irq_level(level);
	}
	return 0;
}

uint16_t kn7000_state::intc_r(offs_t offset, uint16_t mem_mask)
{
	const int reg = offset << 1;                  // byte offset within 0x34000100
	if (reg == 0x00)                              // IAGR: the group latched at interrupt accept
		return m_iagr_latch << 3;
	if (reg == 0x04)
		return 0;
	if (reg == 0x100)                             // 0x34000200: level-6 group register (latched at accept)
		return m_iagr_latch << 2;
	if (reg == 0x180)                             // 0x34000280: per-source 2-bit control fields (latched)
		return m_intc_280;                        // firmware only ever RMWs it (|0xC0 panel, |0x0C00 sound,
		                                          // &0xFF3F|0x80 post-ping) -- state must accumulate
	const int group = reg >> 2;                   // GxICR(group) at +group*4
	if (group < 0x20)
		return m_gxicr[group];
	return 0;
}

void kn7000_state::intc_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	const int reg = offset << 1;
	// The panel transfer-complete (group 0x11) is level-like until serviced: the
	// firmware's ISR-exit ack (full-word 0x0101 at 0x484AC736) w1c-clears DETECT,
	// and on real hardware the NEXT byte's completion always arrives after that
	// ack (the serial shift is slower than the ISR exit). If our deferred
	// completion landed before the ack (and was thus wiped un-serviced),
	// re-deliver it after the ack.
	if (reg == 0x44 && m_c11_unserviced && (data & mem_mask & 0x000f))
		m_panel_txdone->adjust(attotime::from_usec(40), 3);
	if (reg == 0x180)                             // 0x34000280 = EXTMD (ext-int trigger modes)
	{
		const uint16_t prev = m_intc_280;
		COMBINE_DATA(&m_intc_280);
		// Panel ATN pulse, edge 2: the group-0x1A ISR's pass 1 re-arms the pin
		// for the opposite edge (bits 7:6: 11b -> 10b) and expects the second
		// edge of the panel's attention pulse to arrive after it returns.
		// Deferred via timer: pass 1 runs with IE clear and acks its DETECT on
		// exit, so a synchronous assert here would be wiped.
		if (((prev & 0x00c0) == 0x00c0) && ((m_intc_280 & 0x00c0) == 0x0080))
			m_panel_evt->adjust(attotime::from_usec(60), 1);
		return;
	}
	if (reg < 0x08)
		return;                                   // IAGR is read-only
	const int group = reg >> 2;
	if (group >= 0x20)
		return;
	// Effects-DSP self-test handshake (group 0x17 == GxICR 0x3400015c). During init the
	// firmware SOFTWARE-TRIGGERS this interrupt (writes bit0) then spin-polls bit4 (REQUEST)
	// to confirm the ADSP-21065L answered its power-on self-test (fw 0x48404d25). On the
	// 0x3ffff-count timeout it marks the DSP ABSENT (stores 0x500066CC=0xFF), which slams
	// shut the runtime effect-upload gate (fw 0x48404ef5 checks 0x500066CC==0) -- so after
	// that, selecting a reverb/chorus in the sound menus never reaches the DSP and "the
	// sound doesn't change". The real DSP asserts group 0x17 on self-test completion; the
	// booted SHARC in the emulator is present, so model the ack: latch REQUEST here so the
	// poll succeeds and 0x500066CC stays "present". The firmware's write is 0x0001, so the
	// ENABLE byte stays 0 -> no spurious dispatch. Group 0x17 has no other user (no ISR is
	// registered against it; its only refs are this handshake + the INTC bulk-clear).
	if (group == 0x17 && (data & mem_mask & 0x000f) && dsp_present())
	{
		m_gxicr[0x17] = uint16_t((data & mem_mask & 0xff00) | 0x0011);   // DETECT+REQUEST; ENABLE as written
		intc_recompute();
		return;
	}
	// GxICR write semantics (matches the on-chip INTC, and required for correct
	// delivery): the high byte (ENABLE + LEVEL) is stored as written; the DETECT
	// flags (bits 0-3) are WRITE-1-TO-CLEAR; REQUEST (0x10) is hardware status
	// derived from the surviving DETECT bits. A plain latched write here would
	// let the firmware's enable write (e.g. 0x0100) silently destroy a pending
	// request that arrived between 'clear' and 'enable' -- observed in the panel
	// handshake, where the reply's REQUEST was wiped by the subsequent enable.
	{
		const uint16_t cur = m_gxicr[group];
		const uint16_t nv  = (cur & ~mem_mask) | (data & mem_mask);
		// w1c applies ONLY to detect bits the access actually wrote (mem_mask):
		// the firmware's control-byte writes (movbu to +1, mask 0xFF00) must not
		// touch pending DETECT flags.
		uint16_t detect = (cur & 0x000f) & ~(data & mem_mask & 0x000f);
		m_gxicr[group] = (nv & 0xff00) | detect | (detect ? 0x0010 : 0x0000);
	}
	intc_recompute();
}

void kn7000_state::intc_assert(int group)
{

	m_gxicr[group] |= 0x0011;
	// (REQUEST + DETECT bit0 were just set above; the scheduler-level dispatcher at 0x4C03DE72 scans the DETECT bits 0-3 to pick the sub-source within the group)
	intc_recompute();
}

void kn7000_state::intc_recompute()
{
	// The AM33 dispatches each interrupt LEVEL through its own vector, and the
	// firmware installs two distinct handlers:
	//  - 0x4C03DDA0: quick dispatch (no stack switch) -- used by the high-
	//    priority device levels (reads IAGR at 0x34000100).
	//  - 0x4C03DE26: the SCHEDULER entry -- outermost entry saves the interrupted
	//    task's SP into its TCB (*0x5038002C), switches to the scheduler stack
	//    (*0x50380CBC), dispatches (reads the group register at 0x34000200), and
	//    on exit reloads SP from the (possibly re-chosen) current TCB. Only the
	//    system tick (group 6, LEVEL=6, the lowest priority) uses this one.
	// Routing the tick to the quick handler instead desynchronizes the TCB
	// saved-SPs from reality (the scheduler moves *0x5038002C but nothing
	// switches stacks), which corrupts the next yield -- so the vector must be
	// selected per pending level.
	const int g = intc_pending_group();
	if (g)
	{
		const int level = (m_gxicr[g] >> 12) & 7;
		// KN7000: hardcoded firmware handlers. KN6000/KN6500: ALL maskable IRQs vector to the
		// firmware trampoline slot 0 (0x90000000 -> the general handler, which reads the latched
		// group at 0x34000200 and dispatches). Slot 1 (0x90000006 -> 0x4847b19d) is the KN6000's
		// EXCEPTION/fault handler (disables IRQs + halts), NOT an IRQ dispatch -- routing IRQs
		// there halts the boot (was the 0x4847b238 hang). See notes/kn6000-kn6500-boot.md.
		m_maincpu->set_irq_vector(m_lib_mirror ? 0x90000000
		                                       : (level == 6 ? 0x4C03DE26 : 0x4C03DDA0));
		m_maincpu->set_irq_level(level);
	}
	m_maincpu->set_input_line(0, g ? ASSERT_LINE : CLEAR_LINE);
}

TIMER_CALLBACK_MEMBER(kn7000_state::dsp_audio_tick)
{
	// Audio frame tick: pulse the effects DSP's IRQ0 (the kernel's frame interrupt). We only
	// ASSERT: the SHARC core clears the pending bit when it *takes* the interrupt, so one edge
	// is delivered per tick without a matching CLEAR. IRQ0 is edge-configured by the kernel
	// (MODE2 0x18011) and its ISR (PM 0x8020) sets R13=1 to hand a frame to the main loop.
	if (!m_dsp_running)
		return;

	// F.3 audio path: the effect kernel processes one stereo frame per IRQ0. Without the
	// (unmodelled) SPORT DMA advancing the autobuffer index, the kernel writes its output frame
	// to a FIXED position each interrupt and reads its input 0x20 below that -- runtime-observed
	// at TX0+0xE (0xC350 = L,R) and RX0+0xE (0xC370 = L,R), the passthrough's I4 offset into the
	// buffers. We stand in for the codec DMA directly: hand the DSP one TG input frame (from the
	// bridge's rx ring) and take back the previous frame's processed output (to the bridge's tx
	// ring -> speakers).
	// Follow the effect kernel's LIVE audio pointer instead of a fixed SPORT buffer. The kernel
	// keeps its per-frame audio frame in the DM index register I4: it writes the stereo output at
	// [I4],[I4+1] and reads the stereo input at [I4+0x20],[I4+0x21] (verified by disassembling the
	// running microprograms -- the passthrough parks I4 at 0xC350, but a real effect such as Dark2
	// reverb parks it at the SPORT0 TX-B buffer 0xC358, which the old fixed TX0+0xE=0xC350 read
	// missed -> silence). Reading I4 makes the bridge track whichever SPORT autobuffer the loaded
	// effect actually uses, without a full SPORT-DMA model.
	const uint32_t i4 = m_dsp->dm_index_reg(4);
	if (i4 >= 0xC000 && i4 < 0x10000)
	{
		address_space &dm = m_dsp->space(AS_DATA);
		const uint32_t obuf = i4;          // kernel's output frame (L,R)
		const uint32_t ibuf = i4 + 0x20;   // kernel's input frame  (L,R)
		auto sx24 = [](uint32_t v) -> int32_t { return int32_t(v << 8) >> 8; };
		const int32_t oL = sx24(dm.read_dword(obuf));
		const int32_t oR = sx24(dm.read_dword(obuf + 1));
		m_dspbridge->push_output(oL, oR);
		int32_t il = 0, ir = 0;
		m_dspbridge->pop_input(il, ir);
		dm.write_dword(ibuf,     uint32_t(il) & 0xffffff);
		dm.write_dword(ibuf + 1, uint32_t(ir) & 0xffffff);
	}
	m_dsp->set_input_line(0, ASSERT_LINE);
}

TIMER_CALLBACK_MEMBER(kn7000_state::sys_tick)
{
	intc_assert(IRQGRP_TIMER);
	// KN6000/KN6500: also fire the on-chip ms-timer (group 7, level 4). Its ISR
	// increments the software ms-counter 0x50276e48 the boot busy-waits on.
	if (m_lib_mirror)
		intc_assert(0x07);
}

// --- The KN7000 tempo timer (see the member declarations for the full RE) -----
// Semantics modeled from the firmware's own driver code:
//   start   (0x484477D3): write mode -> write base -> bset 0x40 (load counter
//            from base) -> bclr 0x40 -> bset 0x80 (count enable)
//   restart (0x484478C8): bclr 0x80 -> bset/bclr 0x40 -> bset 0x80
//   tempo   (0x48447888): movhu newbase, (0x34001092) while running -- takes
//            effect on the next underflow (hardware auto-reload semantics).
// Prescale: low mode bits select the source clock. Observed mode value logged at
// runtime; PRESCALE is fixed from the 96-PPQN math (see tmr7_rearm).

void kn7000_state::tmr7_mode_w(uint8_t data)
{
	const uint8_t rising = data & ~m_tmr7_mode;
	m_tmr7_mode = data;
	logerror("tmr7: mode=%02X base=%04X\n", data, m_tmr7_base);
	if (!(data & 0x80))
		m_tempo_timer->adjust(attotime::never);        // count disabled
	else if (rising & (0x80 | 0x40))
		tmr7_rearm(true);                              // enabled, or load pulse while enabled
}

void kn7000_state::tmr7_base_w(uint16_t data)
{
	m_tmr7_base = data;
	logerror("tmr7: base=%04X (mode=%02X)\n", data, m_tmr7_mode);
	// While running, the new reload takes effect at the next underflow: keep the
	// current countdown, change only the periodic reload.
	if ((m_tmr7_mode & 0x80) && !m_tempo_timer->remaining().is_never())
		tmr7_rearm(false);
}

void kn7000_state::tmr7_rearm(bool restart_phase)
{
	// IOCLK = 16 MHz (from the firmware's MIDI-baud derivation). PRESCALE: the
	// tick ISR counts 96 PPQN, so at the boot default of q=120 the rate must be
	// 192 Hz; the observed reload confirms the divider (logged above).
	static constexpr unsigned PRESCALE = 8;
	const attotime period = attotime::from_ticks(uint64_t(m_tmr7_base + 1) * PRESCALE, 16'000'000);
	if (restart_phase)
		m_tempo_timer->adjust(period, 0, period);
	else
		m_tempo_timer->adjust(m_tempo_timer->remaining(), 0, period);
}

TIMER_CALLBACK_MEMBER(kn7000_state::tempo_tick)
{
	intc_assert(0x07);      // GxICR 0x3400011C -> the 96-PPQN sequencer tick ISR 0x48447084
}

void kn7000_state::cpsd_mbx_write(uint16_t data)
{
	// Full-duplex SPI byte transfer: shift the 8 bits through the card (MSB
	// first), collecting MISO into m_sdmbx_out; then raise the ack (group 0x1C
	// DETECT/REQUEST -- polled, not interrupt-driven).
	if (m_sdcard)
	{
		m_sdmbx_miso = 0;
		for (uint8_t bit = 0x80; bit; bit >>= 1)
		{
			m_sdcard->spi_clock_w(CLEAR_LINE);
			m_sdcard->spi_mosi_w((data & bit) ? 1 : 0);
			m_sdcard->spi_clock_w(ASSERT_LINE);
		}
		m_sdmbx_out = m_sdmbx_miso;
	}
	intc_assert(0x1C);
}

TIMER_CALLBACK_MEMBER(kn7000_state::sd_insert)
{
	// The card appears: clear the group-0x1B DETECT/REQUEST bits -> the polled
	// reader sees bit4 drop, the debounce runs, and the firmware posts the
	// card-insert message (see the member declaration for the chain).
	sd_update_carddetect();
}

INPUT_CHANGED_MEMBER(kn7000_state::sd_cover_changed)
{
	// The user opened or closed the SD slot cover: update the card-detect line.
	// Closing with a card in produces the insert edge (mount); opening drops
	// access so the firmware shows "ERROR 93: SD lid is open" on the SD screens.
	sd_update_carddetect();
}

// One-shot (t=3s, after the boot BSS-clear): install the factory "Initial Data"
// Favorites into battery-backed SRAM so the Favorites screen lists the 4 presets
// without the (still-unreversed) custom-flash AST install. The firmware VALIDATES this
// block against a 16-byte magic ("KN7000 SDDIR INF" @0x50083D72; check at 0x4855EC0B)
// rather than clearing it, so once present the firmware keeps it. The Favorites LIST
// only needs the 16-char names; the 9 u16 recall-items per record need flash-backed
// reference resolution, so they stay 0 (a CUSTOM favorite can't be recalled until the
// flash is modeled). Data = idd7000 03FAVINI.FAV; layout verified by RE (name-setter
// 0x48561CDB, item-setter 0x48561D8E, format 0x4855EC34). STOPGAP for the unmodeled
// battery SRAM; see notes/initial-data-disk-and-custom-flash.md.
TIMER_CALLBACK_MEMBER(kn7000_state::fav_preload)
{
	auto poke8 = [&](offs_t cpu, uint8_t b)
	{
		const offs_t o = cpu - 0x50000000;                 // byte offset into workram
		uint32_t &w = m_workram[o >> 2];
		const unsigned sh = 8 * (o & 3);
		w = (w & ~(0xffu << sh)) | (uint32_t(b) << sh);
	};
	static const char magic[16] =
		{ 'K','N','7','0','0','0',' ','S','D','D','I','R',' ','I','N','F' };
	for (int i = 0; i < 16; i++)
		poke8(0x50083D72 + i, uint8_t(magic[i]));           // block magic @+0x00
	static const char *const fav[4] = {                     // directory @0x5008FDCA, 34-byte records
		"    Example     ", " Cool Sounds !  ", " Cool Rhythms ! ", "  Entertainer   " };
	for (int r = 0; r < 4; r++)
		for (int i = 0; i < 16; i++)
			poke8(0x5008FDCA + r * 34 + i, uint8_t(fav[r][i]));  // name[16]; items[9] left 0
}

// A PC-key note press/release: push a voice-event into the keyboard FIFO the
// firmware polls at 0x98050004. param carries the KEY index; velocity is fixed
// (PC keys are not velocity-sensitive). Make/break = BIT 7 of the key byte (see the
// FIFO note in the header): a release sets bit 7 (key | 0x80) with velocity 0xFF for
// a clean key-up -- NOT velocity 0, which the firmware reads as a NOTE-ON (the old
// "stuck notes" bug). Confirmed end-to-end: the firmware reads each event once.
INPUT_CHANGED_MEMBER(kn7000_state::kbd_key)
{
	kbd_push(newval ? uint8_t(param) : uint8_t(param | 0x80), newval ? 0x64 : 0xff);
	// First-cut audio: also key the bring-up sine synth directly, so a PC key is
	// audible now (independent of the firmware's dormant voice engine). This is a
	// monitor tap of the key bed, NOT the real TG path (Stage 2 will drive the
	// synth from the firmware's tone-generator voice writes instead).
	if (newval) m_tonegen->note_on(uint8_t(param));
	else        m_tonegen->note_off(uint8_t(param));
}


// ============================================================================
//  SIO ASIC -- three USART channels (panel + two MIDI ports)
// ============================================================================
//
// The handlers are 16-bit (as the whole 0x34000000 bank is); `offset` is the
// 16-bit-word index within 0x34000800. Each channel spans 0x10 bytes = 8 words,
// so channel = offset / 8 and the byte within the channel is (offset << 1) & 0xf.
// Byte registers (control @+4, TX @+8, RX @+9) are reached with movbu, i.e. a
// masked 16-bit access: TX is the low byte of word 4, RX the high byte.

uint16_t kn7000_state::sio_r(offs_t offset, uint16_t mem_mask)
{
	const int ch = offset / 8;
	const int reg = (offset << 1) & 0x0f;
	switch (reg)
	{
	case 0x0:                    // config
		return m_sio_config[ch];
	case 0x4:                    // control (byte @+4)
		return m_sio_control[ch];
	case 0x8:                    // +8 TX (write-only) / +9 RX (read, high byte)
		if (ACCESSING_BITS_8_15)
			return uint16_t(sio_rx_pop(ch)) << 8;
		return 0;
	case 0xc:                    // status: bit4 = RxRDY
		// ch2 is the MIDI-2 UART (adversarially verified RE 2026-07-10; earlier
		// "CPSD/SD link" attribution was wrong -- see notes/sd-card-emulation-plan.md).
		// Its RX classifier 0x484b28ee treats bit7 as RX-empty and its TX path
		// polls bit6 as TxRDY, but modeling those bits changes boot-time MIDI-2
		// behaviour and wedged the boot (black LCD) -- keep the historical
		// RxRDY-only status until MIDI-2 OUT modeling is actually wanted.
		return sio_rx_ready(ch) ? 0x0010 : 0x0000;
	}
	return 0;
}

void kn7000_state::sio_w(offs_t offset, uint16_t data, uint16_t mem_mask)
{
	const int ch = offset / 8;
	const int reg = (offset << 1) & 0x0f;
	switch (reg)
	{
	case 0x0:                    // config
		COMBINE_DATA(&m_sio_config[ch]);
		// Bit 15 = transfer START on the synchronous panel link: the firmware
		// sets it to clock one byte and then polls the register until the
		// hardware self-clears it on completion. The HLE completes transfers
		// instantly. In the RX direction (mode field low3 = 7) the panel
		// sub-CPU supplies the next response byte of its pending reply.
		if (ch == SIO_PANEL && (m_sio_config[ch] & 0x8000))
		{
			m_sio_config[ch] &= 0x7fff;
			// Bit15 = start/busy for the boot's POLLED bit-bang path only; it just
			// self-clears here. The per-byte transfer trigger is the DATA write
			// itself: state-2 (0x484AC8D2) and later payload states write data with
			// NO bit15 write at all -- an armed/pending model makes each such
			// transfer complete only on the NEXT retry's arm, advancing the state
			// machine one step per retry (the observed parking). Completion is
			// modeled per data write in sio_tx_byte.
		}
		// RX enable (bit14, set by the group-0x1A ISR's pass 2 together with mode
		// low3=7 and state:=8): the panel now sends its queued reply, one byte per
		// group-0x10 interrupt (the state-8 handler reads 0x34000809 into the ring
		// at 0x5006BDB4 and bumps the head that the handshake success test checks).
		if (ch == SIO_PANEL && (m_sio_config[ch] & 0x4000) && m_panel_resp_pos < m_panel_resp_len)
			m_panel_evt->adjust(attotime::from_usec(60), 2);
		break;
	case 0x4:                    // control (byte @+4)
		if (ACCESSING_BITS_0_7)
			m_sio_control[ch] = data & 0xff;
		break;
	case 0x8:                    // TX data (byte @+8 = low byte)
		if (ACCESSING_BITS_0_7)
			sio_tx_byte(ch, data & 0xff);
		break;
	default:
		break;
	}
}

void kn7000_state::sio_rx_push(int ch, uint8_t data)
{
	const uint8_t next = (m_sio_rx_head[ch] + 1) % std::size(m_sio_rx_fifo[ch]);
	if (next == m_sio_rx_tail[ch])
		return;                  // FIFO full -- drop (overrun)
	m_sio_rx_fifo[ch][m_sio_rx_head[ch]] = data;
	m_sio_rx_head[ch] = next;
	// Deliver the byte: assert the channel's RX interrupt group (ICRs: panel RX
	// 0x34000168 -> group 0x1A, MIDI-1 RX 0x34000148 -> 0x12, MIDI-2 RX
	// 0x34000150 -> 0x14; see notes/panel-serial-protocol.md #6). The firmware's
	// RX ISR reads +0x09 and acks its GxICR; polling paths see RxRDY regardless.
	static constexpr int rx_group[3] = { 0x1a, 0x12, 0x14 };
	if (ch != SIO_PANEL)                          // panel: the sync-transfer-complete
		intc_assert(rx_group[ch]);                // assert in sio_w covers group 0x1A

}

uint8_t kn7000_state::sio_rx_pop(int ch)
{
	if (m_sio_rx_head[ch] == m_sio_rx_tail[ch])
		return 0;
	const uint8_t v = m_sio_rx_fifo[ch][m_sio_rx_tail[ch]];
	if (!machine().side_effects_disabled())
		m_sio_rx_tail[ch] = (m_sio_rx_tail[ch] + 1) % std::size(m_sio_rx_fifo[ch]);
	return v;
}

void kn7000_state::sio_tx_byte(int ch, uint8_t data)
{
	switch (ch)
	{
	case SIO_PANEL:
		// Every data write clocks one sync transfer. Completion -> group 0x11 --
		// ALWAYS deferred (an ISR-context write + synchronous assert is wiped by
		// the exit ack). Safe with IAGR latched at accept.
		m_panel_txdone->adjust(attotime::from_usec(40), 3);
		// The main CPU transmits 7-byte FRAMES with interleaved line syncs:
		//   pos 0 sync, 1 sync, 2 PAYLOAD1, 3 sync, 4 PAYLOAD2, 5 sync, 6 sync
		// (TX sites: sender 0x484AC5E9; states 1..6 at 0x484AC7FA / 0x484AC8D3 /
		// 0x484AC977 / 0x484AC9FF / 0x484ACA96 / 0x484ACAEA). Parse by position.
		switch (m_panel_pos)
		{
		case 2: m_panel_p1 = data; break;
		case 4: m_panel_p2 = data; break;
		}
		if (++m_panel_pos >= 7)
		{
			m_panel_pos = 0;
			// Frame complete. Handshake commands (payload1 = 0x1F/0x1D/0x1E init,
			// 0x20/0xE0 ping CPL/CPR, 0x29/0xDD -- the boot's observed sequence)
			// are answered with a TYPE-3 sync packet and an ATN pulse on the
			// panel's external-interrupt pin (group 0x1A, EXTMD bits 7:6). All
			// other frames carry LED-register updates [addr][data].
			switch (m_panel_p1)
			{
			case 0x1f: case 0x1d: case 0x1e: case 0x20: case 0xe0: case 0x29: case 0xdd:
			{
				// TYPE-3 sync reply; delivery via the ATN pulse (edge 2 rides the
				// EXTMD 11b->10b re-arm; bytes deliver one per group-0x10
				// interrupt once the ISR's pass 2 sets RX enable).
				static constexpr uint8_t sync_reply[2] = { 0x18, 0x00 };
				panel_queue(sync_reply, 2);
				break;
			}
			case 0x00:
				break;                     // idle/padding frame
			default:
				panel_led_frame(m_panel_p1, m_panel_p2);
				break;
			}
		}
		break;
	case SIO_MIDI1:
	case SIO_MIDI2:
		// Serialize the byte out through the channel's UART to its MIDI OUT port.
		// (ch2 = MIDI-2, verified 2026-07-10; the interim CPSD hook + keep-alive
		// injected phantom MIDI bytes and wedged the boot -- removed.)
		m_midi_uart[ch - SIO_MIDI1]->write(data);
		break;
	}
}

// One decoded LED-command frame: ADDR selects an 8-LED register on one of the
// panel boards, DATA is that register's 8 LED bits. The board is chosen by the
// bank field in ADDR bits 6-7; the register index is ADDR bits 0-5. This mirrors
// the firmware's LED shadow layout (notes/panel-serial-protocol.md).
// TODO: the exact ADDR->(board,physical LED) table still needs cross-checking
// against the schematic silk-screen; the structural decode below is provisional.
void kn7000_state::panel_led_frame(uint8_t addr, uint8_t data)
{
	// addr = panel(bits 7:6; 0x00=right/CPR, 0xC0/0xE0=left/CPL) | reg(bits 5:0).
	// Each data bit is one LED of register `reg`. Index reg*8+bit within the bank.
	// (Provisional: reg<->physical-LED map is derived in notes/panel-leds.md but
	// not yet bound in the layout; both banks are wired for when it is.)
	const int reg = addr & 0x3f;
	const bool left = (addr & 0xc0) != 0;
	for (int bit = 0; bit < 8; bit++)
	{
		const int led = reg * 8 + bit;
		const int on = BIT(data, bit);
		if (led < 512) { if (left) m_cpl_leds[led] = on; else m_cpr_leds[led] = on; }
	}
	logerror("%s: panel LED frame addr=%02X data=%02X\n",
		machine().describe_context(), addr, data);
}

// Queue panel->main bytes (a handshake reply or a button-event packet) and start
// the delivery dance if idle: the panel pulses its ATN line (group 0x1A); the
// firmware's ISR switches the link to RX and clocks the bytes in one group-0x10
// interrupt at a time (state-8 handler -> the 92-byte ring -> the frame decoder).
void kn7000_state::panel_queue(const uint8_t *bytes, int n)
{
	if (m_panel_resp_pos == m_panel_resp_len)
		m_panel_resp_pos = m_panel_resp_len = 0;          // queue fully drained: reset
	if (m_panel_resp_len + n > int(sizeof(m_panel_resp)))
		return;                                           // overflow: drop (panel would too)
	const bool was_idle = (m_panel_resp_pos == m_panel_resp_len);
	for (int i = 0; i < n; i++)
		m_panel_resp[m_panel_resp_len++] = bytes[i];
	if (was_idle)
		m_panel_evt->adjust(attotime::from_usec(60), 1);  // ATN edge 1
}

// Deferred panel events (one-shot; scheduled from ISR-context register writes so
// the interrupt lands after the firmware's current handler returns):
//  param 1: ATN edge on the panel's external-interrupt pin -> group 0x1A.
//  param 2: the panel places its next reply byte on SIO0 -> group 0x10; the
//           state-8 handler reads it from +9 and stores it into the RX ring.
TIMER_CALLBACK_MEMBER(kn7000_state::panel_event)
{
	if (param == 1)
		intc_assert(0x1a);
	else if (param == 3)
	{
		m_c11_unserviced = true;
		intc_assert(0x11);                 // sync-transfer complete
	}
	else if (param == 2 && m_panel_resp_pos < m_panel_resp_len)
	{
		sio_rx_push(SIO_PANEL, m_panel_resp[m_panel_resp_pos++]);
		intc_assert(0x10);
		if (m_panel_resp_pos < m_panel_resp_len)
			m_panel_evt->adjust(attotime::from_usec(120), 2);   // next byte
	}
}

// CPSD (SD sub-CPU) frame delivery on SIO ch2. Simpler than the panel path: the
// firmware has already seen bit7 of the status set (cpsd_queue makes it read set)
// and enabled the ch2 RX interrupt; each timer tick clocks one byte into the ch2
// RX FIFO and fires group 0x14, which the firmware's ISR reads from +9.
[[maybe_unused]] void kn7000_state::cpsd_queue(const uint8_t *bytes, int n)
{
	// Deliver the whole frame into the ch2 RX FIFO at once; the status bits (bit7 +
	// bit4, both from sio_rx_ready) then reflect it and the firmware clocks the
	// bytes out via its bit4-gated reads of +9 (0x34000829). sio_rx_push also
	// asserts the ch2 RX interrupt (group 0x14) per byte, matching the DETECT the
	// firmware sets at 0x484b206f.
	for (int i = 0; i < n; i++)
		sio_rx_push(SIO_SD, bytes[i]);
}

// Periodic button scan: read each declared segment ioport, and for any that
// changed since last scan, queue a 2-byte [ADDR][DATA] switch-report frame onto
// the panel RX. DATA bit = 1 means pressed (active-high on the wire); the frame
// is the same format the real sub-CPUs emit (notes/panel-serial-protocol.md,
// e.g. START/STOP press = C0 10). Delivery to the firmware WORKS via the ATN/SIO
// handshake in panel_queue -- VERIFIED: a held DEMO (SEG06 0x40) press enters demo
// mode. NB a press must be HELD across scans (>~1 frame); a single-frame Lua tap can
// be cleared by the input frame-update before this 250 Hz scan samples it.
TIMER_CALLBACK_MEMBER(kn7000_state::panel_scan)
{
	// Front-panel MAIN VOLUME slider -> master output gain on the final mix. A squared
	// taper approximates a natural volume law (the exact analog-slider taper is unknown);
	// 100 = unity, 0 = silent. Polled here (250 Hz) -- cheap and always current.
	{
		const float v = float(m_volmain->read()) / 100.0f;
		m_dspbridge->set_master_gain(v * v);
	}

	// Inputs are declared one ioport per NORMALIZED SEGMENT (SEG00..SEG15), the
	// identity the firmware's button dispatcher (0x484ADB59) uses. For a changed
	// segment we emit its 2-byte [ADDR][DATA] switch frame, computing the wire
	// ADDR by REVERSE-normalizing (the inverse of table 0x486135A0):
	//   normSeg 0x00-0x0B -> ADDR 0xC0-0xCB (grp3), 0x0C-0x15 -> 0x00-0x09 (grp0),
	//   0x16-0x19 -> 0xD0-0xD3, 0x1A -> 0x10, 0x20 -> 0x17. normSeg 0x1B-0x1F have NO
	//   wire path (not panel-serial buttons). DATA = segment bitmask (bit=1 pressed);
	//   the main CPU XORs vs its shadow for press/release edges.
	// Delivery rides the ATN dance via panel_queue (a bare fifo push never IRQs).
	static const uint8_t seg_to_addr[0x21] = {
		0xc0,0xc1,0xc2,0xc3,0xc4,0xc5,0xc6,0xc7,0xc8,0xc9,0xca,0xcb, // normSeg 0x00-0x0B
		0x00,0x01,0x02,0x03,0x04,0x05,0x06,0x07,0x08,0x09,           // normSeg 0x0C-0x15
		0xd0,0xd1,0xd2,0xd3,0x10,0xff,0xff,0xff,0xff,0xff,0x17,       // normSeg 0x16-0x20
	};
	for (int seg = 0; seg < 0x21; seg++)
	{
		const uint8_t addr = seg_to_addr[seg];
		if (addr == 0xff)   // normSeg 0x1B-0x1F: no wire path
			continue;
		const uint8_t cur = m_seg[seg]->read();
		if (cur == m_btn_prev[seg])
			continue;
		m_btn_prev[seg] = cur;
		const uint8_t pkt[2] = { addr, cur };
		panel_queue(pkt, 2);
	}
}


// --- Control-panel buttons and LEDs -----------------------------------------
// Like the KN5000, the KN7000 front panel is driven by dedicated panel sub-CPUs
// -- one per panel PCB -- that scan the button matrices and drive the LEDs, and
// talk to the main MN10300 over a synchronous serial link. Confirmed from the
// service manual schematics (SX-KN7000, SCHEMATIC DIAGRAM-15..18):
//
//   * CPL P.C.B. (page 128, "CPL CIRCUIT"): sub-CPU IC1101 = C0BDB646823
//     (8-bit microcomputer, xtal X1101). Scans an 8x8 switch matrix
//     (strobes SW0..SW7 x columns SEG0..SEG7) and drives an LED matrix through
//     IC1102 (HD74LS138 3-to-8 decoder) + transistor rows + buffers IC1103.
//     Serial link pins: SIN, SOUT, CLK, RST, CNTR1 -> to the CPR board / main.
//   * CPC (centre), CPR (right) and CPSD boards: same design (pages 130-133).
//
// On the main-CPU side the link is ONE channel of a multi-channel USART/SIO ASIC
// mapped at 0x34000800 (config 0x800, control 0x804, TX-data 0x808, RX-data 0x809,
// status 0x80C; interrupt via ICR 0x34000168). It is INTERRUPT-DRIVEN, half-duplex:
// the RX ISR (0x484ACC13) reads one byte from 0x34000809 into a 92-byte ring buffer
// (0x5006BDB4), a frame decoder (0x484AD111) parses a header byte whose bits[5:3]
// are a 3-bit message type, and a switch-byte dispatcher (0x484AD680) indexes a
// 32-entry jump table (0x48613108) = the four panel groups CPL/CPC/CPR/CPSD. LED
// bytes go OUT on the SAME channel (TX path 0x484ABF50 -> 0x34000808). GPIO lines
// 0x36008004/24/64 strobe/select the sub-CPUs. NOTE: the sibling SIO channels at
// 0x34000810 and 0x34000820 are the two MIDI ports, NOT panel. See notes/io-map.md
// and the kn5000-docs Control Panel Protocol page.
//
// The button names below are transcribed from the CPL schematic; the exact
// SW-row within each SEG column should be double-checked against the print. Only
// CPL is filled in so far (pages 130-133 will populate CPC/CPR/CPSD). A proper
// serial-protocol HLE device (as in kn5000_cpanel.cpp) is still to be written.

static INPUT_PORTS_START(kn7000)
	// The tone generators (IC201/IC205) and the effects DSP (IC306, ADSP-21065L) are
	// always fitted on the KN7000, so the firmware voices notes and processes effects
	// unconditionally -- there are no machine-configuration switches for them.

	// Panel buttons organized by NORMALIZED SEGMENT (normSeg), the identity the
	// firmware's button dispatcher (0x484ADB59) actually uses. panel_scan emits
	// each segment's reverse-normalized wire address (bank11 subs 0-0xB -> segs
	// 0x00-0x0B; bank00 subs 0-9 -> segs 0x0C-0x15). Names for segs 0x00-0x07 are
	// the transcribed CPL panel labels (verified: START/STOP etc.); names for
	// 0x08-0x15 are derived from each button's firmware event code + arg (see
	// notes/panel-button-map.md) -- honest and traceable, refined as arg->genre
	// and arg->sound-group tables are decoded.
	PORT_START("SEG00")   // normSeg 0x00 (bank A = KN7000)
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("ACCOMP 1 OFF")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("RIGHT 1 OFF")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("ACCOMP 2 OFF")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("RIGHT 2 OFF")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("START/STOP")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("LEFT OFF")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("(ev2022 arg0105)")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SYNCHRO & BREAK")

	PORT_START("SEG01")   // normSeg 0x01 (bank A = KN7000)
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("RHYTHM MEMORY")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("RHYTHM ORGANIST")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("RHYTHM CUSTOM")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("RHYTHM ENTERTAINER")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("RHYTHM LATIN & WORLD")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("RHYTHM MOVIE & SHOW")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("RHYTHM MARCH & WALTZ")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("RHYTHM BALLROOM")

	PORT_START("SEG02")   // normSeg 0x02 (bank A = KN7000)
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("RHYTHM COUNTRY & WESTERN")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("RHYTHM JAZZ & SWING")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("RHYTHM SOUL & R&B")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("RHYTHM BALLAD")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("RHYTHM MODERN DANCE")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("RHYTHM ROCK & POP")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("RHYTHM 60s & 70s")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("RHYTHM 8 & 16 BEAT")

	PORT_START("SEG03")   // normSeg 0x03 (bank A = KN7000)
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("INTRO & ENDING")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("TAP TEMPO")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("FILL IN 2")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("FADE IN/OUT")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("FILL IN 1")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("FADE IN/OUT")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("VARIATION & MSA 4")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SPLIT POINT")

	PORT_START("SEG04")   // normSeg 0x04 (bank A = KN7000)
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("VARIATION & MSA 3")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("ONE TOUCH PLAY")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("VARIATION & MSA 2")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUSIC STYLE ARRANGER")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("VARIATION & MSA 1")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PERFORMANCE PAD 3")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PERFORMANCE PAD 6")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PERFORMANCE PAD 2")

	PORT_START("SEG05")   // normSeg 0x05 (bank A = KN7000)
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("DRUM 1 OFF")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("HELP")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PADS ON")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PADS OFF")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART 1 ON")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART 1 OFF")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART 2 ON")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART 2 OFF")

	PORT_START("SEG06")   // normSeg 0x06 (bank A = KN7000)
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PERFORMANCE PAD 5")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PERFORMANCE PADS STOP")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PERFORMANCE PAD 4")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PERFORMANCE PADS BANK")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PERFORMANCE PAD 1")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PERFORMANCE PADS AUTO SETTING")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("DEMO")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("CUSTOM PANEL (guess)")

	PORT_START("SEG07")   // normSeg 0x07 (bank A = KN7000)
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MUSIC STYLIST")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("APC / CHORD FINDER")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND ARRANGER")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("AUTO PLAY CHORD OFF/ON")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND ARRANGER OFF/ON")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_UNUSED)

	PORT_START("SEG08")   // normSeg 0x08 (bank A = KN7000)
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART 3 ON")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART 3 OFF")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART 4 ON")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART 4 OFF")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART 5 ON")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART 5 OFF")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART 6 ON")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART 6 OFF")

	PORT_START("SEG09")   // normSeg 0x09 (bank A = KN7000)
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART 7 ON")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART 7 OFF")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART 8 ON")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART 8 OFF")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART 9 ON")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART 9 OFF")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART 10 ON")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART 10 OFF")

	PORT_START("SEG0A")   // normSeg 0x0A (bank A = KN7000)
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART 11 ON")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART 11 OFF")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART 12 ON")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART 12 OFF")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART 13 ON")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART 13 OFF")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART 14 ON")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART 14 OFF")

	PORT_START("SEG0B")   // normSeg 0x0B (bank A = KN7000)
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART 15 ON")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART 15 OFF")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART 16 ON")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART 16 OFF")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("BASS ON")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("BASS OFF")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("DISPLAY HOLD")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("ACCOMP 5 ON")

	PORT_START("SEG0C")   // normSeg 0x0C (bank A = KN7000)
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOLO")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PANEL MEMORY 1")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PROGRAM MENUS")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SEQUENCER EASY RECORD")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND STRINGS & VOCAL")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND SYNTH")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("CUSTOMIZE")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_UNUSED)

	PORT_START("SEG0D")   // normSeg 0x0D (bank A = KN7000)
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("TECHNI-CHORD")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART SELECT")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("DISK")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SEQUENCER PLAY")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND WORLD")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND PAD")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("DISK MENU")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SD MENU")

	PORT_START("SEG0E")   // normSeg 0x0E (bank A = KN7000)
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART SELECT")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PART SELECT")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MIC REVERB & EFFECT")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND DSP VARIATION")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND MALLET & ORCH PERC")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND ACCORD REGISTER")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("FAVORITES")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_UNUSED)

	PORT_START("SEG0F")   // normSeg 0x0F (bank A = KN7000)
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("TRANSPOSE -/+")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("CONDUCTOR")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("REVERB")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND DSP")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND GUITAR")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND ORGAN TABS")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PANEL MEMORY 5")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("NEXT BANK")

	PORT_START("SEG10")   // normSeg 0x10 (bank A = KN7000)
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("TRANSPOSE -/+")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("CONDUCTOR")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("MULTI EFFECT")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("DIGITAL EFFECT")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND PIANO")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND DIGITAL DRAWBAR")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PANEL MEMORY 4")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PANEL MEMORY BANK SELECT")

	PORT_START("SEG11")   // normSeg 0x11 (bank A = KN7000)
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("ACCOMP 2 ON")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("CONDUCTOR")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("CHORUS")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SUSTAIN")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("RIGHT 1 ON")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("RIGHT 2 ON")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PANEL MEMORY 3")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PANEL MEMORY 6")

	PORT_START("SEG12")   // normSeg 0x12 (bank A = KN7000)
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("ACCOMP 1 ON")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("R1/R2 OCTAVE -/+")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND EW EXPANSION")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND SOUND EXPLORER")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PANEL MEMORY 2")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PANEL MEMORY 7")

	PORT_START("SEG13")   // normSeg 0x13 (bank A = KN7000)
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("LEFT ON")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("R1/R2 OCTAVE -/+")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND MEMORY")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND ORGAN & ACCORDION")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PANEL MEMORY SET (guess)")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PANEL MEMORY 8")

	PORT_START("SEG14")   // normSeg 0x14 (bank A = KN7000)
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND DRUM KITS")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND SAX & WOODWIND")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_UNUSED)

	PORT_START("SEG15")   // normSeg 0x15 (bank A = KN7000)
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND BASS")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SOUND BRASS")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_UNUSED)

	// SEG16-SEG20: DIAL/DATA/special panel-serial buttons (wire ADDR 0xD0-0xD3, 0x10, 0x17 from
	// PanelWireNormTable 0x486135A0). normSeg 0x1B-0x1F (0x1000 soft-keys, 0x20B5-BD, 0x2005/2030
	// dup events) have NO wire path and are not panel-serial; defined empty for the array. Names
	// are placeholders (event codes) pending snapshot ID; see notes/panel-descriptor-map.md.
	PORT_START("SEG16")   // normSeg 0x16 -- wire ADDR 0xD0
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PAGE UP (guess2)")
	PORT_BIT(0xfe, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_START("SEG17")   // normSeg 0x17 -- wire ADDR 0xD1
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("PAGE DOWN (guess2)")
	PORT_BIT(0xfe, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_START("SEG18")   // normSeg 0x18 -- wire ADDR 0xD2
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Fn 1009 (CPC)")
	PORT_BIT(0xfe, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_START("SEG19")   // normSeg 0x19 -- wire ADDR 0xD3
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("CONTRAST + (guess2)")
	PORT_BIT(0xfe, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_START("SEG1A")   // normSeg 0x1A -- wire ADDR 0x10
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("CONTRAST - (guess2)")
	PORT_BIT(0xfe, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_START("SEG1B")   // normSeg 0x1B -- no wire path
	PORT_BIT(0xff, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_START("SEG1C")   // normSeg 0x1C -- no wire path
	PORT_BIT(0xff, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_START("SEG1D")   // normSeg 0x1D -- no wire path
	PORT_BIT(0xff, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_START("SEG1E")   // normSeg 0x1E -- no wire path
	PORT_BIT(0xff, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_START("SEG1F")   // normSeg 0x1F -- no wire path
	PORT_BIT(0xff, IP_ACTIVE_HIGH, IPT_UNUSED)
	PORT_START("SEG20")   // normSeg 0x20 -- wire ADDR 0x17
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Fn 1020")
	PORT_BIT(0xfe, IP_ACTIVE_HIGH, IPT_UNUSED)

	PORT_START("DIAL")
	PORT_BIT(0xff, 0x00, IPT_DIAL) PORT_SENSITIVITY(30) PORT_KEYDELTA(1) PORT_NAME("DATA DIAL")

	// Front-panel volume sliders -- draggable placeholders (the ESQ1-style slider script in
	// kn7000.lay binds these). NOT yet wired to any audio/volume path; control targets are TBD
	// (needs schematic + disassembly RE). PORT_ADJUSTER gives a 0-100 value the layout knob animates.
	PORT_START("VOL_MAIN")   PORT_ADJUSTER(80, "Main Volume")
	PORT_START("VOL_APCSEQ") PORT_ADJUSTER(80, "APC / SEQ Volume")
	PORT_START("VOL_MIC")    PORT_ADJUSTER(50, "Mic Volume")
	PORT_START("VOL_LINEIN") PORT_ADJUSTER(50, "Line-In Volume")

	// Rear-panel MIDI IN / BASS PEDAL selector switch (SW701 on the JACK board). The
	// firmware reads it as bit12 (data-bus D28) of the config strap 0x98070000 via the
	// EXP-port output-enable. Set to BASS PEDAL and the firmware routes MIDI-in to the
	// bass-pedal part and disables normal MIDI input (the "ATTENTION! -1 / Midi is not
	// working ... set the switch ... to Midi" warning). Default MIDI IN so MIDI works.
	PORT_START("REARSW")
	PORT_CONFNAME(0x1000, 0x1000, "Rear panel: MIDI IN / BASS PEDAL selector (SW701)")
	PORT_CONFSETTING(0x1000, "MIDI IN")
	PORT_CONFSETTING(0x0000, "Bass Pedals")

	// SD front-panel switches (CPSD-side matrix, byte 0x9CC00008 ACTIVE-LOW,
	// bits 0-5 -> panel events 0x20B5..0x20BA per descriptor SEG1D @0x48613fc4;
	// physical order per the panel silk: VOLUME - / + , SKIP/SEARCH back/fwd,
	// STOP, PLAY/PAUSE). Clickable in the layout artwork (kn7000.lay sd_block).
	PORT_START("SDSW")
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SD SKIP/SEARCH <<")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SD SKIP/SEARCH >>")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SD STOP")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SD PLAY/PAUSE")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SD VOLUME -")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SD VOLUME +")

	// SD slot COVER switch. The KN7000's SD slot has a hinged cover; the firmware
	// reads it as the card-detect line and refuses SD access with "ERROR 93: SD
	// lid is open" while it is open. A latching toggle (default CLOSED): open it
	// to eject / see ERROR 93, close it (with an image attached via -harddisk) to
	// insert + mount. Toggling fires the debounced card-detect edge.
	PORT_START("SDCOVER")
	PORT_CONFNAME(0x01, 0x00, "SD slot cover") PORT_CHANGED_MEMBER(DEVICE_SELF, FUNC(kn7000_state::sd_cover_changed), 0)
	PORT_CONFSETTING(   0x00, "Closed")
	PORT_CONFSETTING(   0x01, "Open")

	// Music key bed: the FULL 61 keys (C2..C7). The FIFO value is the KEY INDEX
	// (0 = bottom C2; firmware maps internal note = index + 36 = MIDI). Every key
	// carries PORT_GM_NOTE musical-note markup, so a USB-MIDI controller mapped
	// via MAME's midi input provider plays the whole bed; the middle two octaves
	// (C4..C6) additionally keep the PC tracker-style key bindings.
#define KN_KEYM(mask, idx, gm, name) \
	PORT_BIT(mask, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME(name) PORT_GM_NOTE(gm) \
	PORT_CHANGED_MEMBER(DEVICE_SELF, FUNC(kn7000_state::kbd_key), idx)
#define KN_KEYPC(mask, idx, gm, code, name) \
	PORT_BIT(mask, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME(name) PORT_CODE(code) PORT_GM_NOTE(gm) \
	PORT_CHANGED_MEMBER(DEVICE_SELF, FUNC(kn7000_state::kbd_key), idx)
	PORT_START("KEYS0")
	KN_KEYM(0x0001, 0x00, 36, "Key C2")
	KN_KEYM(0x0002, 0x01, 37, "Key C#2")
	KN_KEYM(0x0004, 0x02, 38, "Key D2")
	KN_KEYM(0x0008, 0x03, 39, "Key D#2")
	KN_KEYM(0x0010, 0x04, 40, "Key E2")
	KN_KEYM(0x0020, 0x05, 41, "Key F2")
	KN_KEYM(0x0040, 0x06, 42, "Key F#2")
	KN_KEYM(0x0080, 0x07, 43, "Key G2")
	KN_KEYM(0x0100, 0x08, 44, "Key G#2")
	KN_KEYM(0x0200, 0x09, 45, "Key A2")
	KN_KEYM(0x0400, 0x0A, 46, "Key A#2")
	KN_KEYM(0x0800, 0x0B, 47, "Key B2")
	KN_KEYM(0x1000, 0x0C, 48, "Key C3")
	KN_KEYM(0x2000, 0x0D, 49, "Key C#3")
	KN_KEYM(0x4000, 0x0E, 50, "Key D3")
	KN_KEYM(0x8000, 0x0F, 51, "Key D#3")
	PORT_START("KEYS1")
	KN_KEYM(0x0001, 0x10, 52, "Key E3")
	KN_KEYM(0x0002, 0x11, 53, "Key F3")
	KN_KEYM(0x0004, 0x12, 54, "Key F#3")
	KN_KEYM(0x0008, 0x13, 55, "Key G3")
	KN_KEYM(0x0010, 0x14, 56, "Key G#3")
	KN_KEYM(0x0020, 0x15, 57, "Key A3")
	KN_KEYM(0x0040, 0x16, 58, "Key A#3")
	KN_KEYM(0x0080, 0x17, 59, "Key B3")
	KN_KEYPC(0x0100, 0x18, 60, KEYCODE_Z, "Key C4")
	KN_KEYPC(0x0200, 0x19, 61, KEYCODE_S, "Key C#4")
	KN_KEYPC(0x0400, 0x1A, 62, KEYCODE_X, "Key D4")
	KN_KEYPC(0x0800, 0x1B, 63, KEYCODE_D, "Key D#4")
	KN_KEYPC(0x1000, 0x1C, 64, KEYCODE_C, "Key E4")
	KN_KEYPC(0x2000, 0x1D, 65, KEYCODE_V, "Key F4")
	KN_KEYPC(0x4000, 0x1E, 66, KEYCODE_G, "Key F#4")
	KN_KEYPC(0x8000, 0x1F, 67, KEYCODE_B, "Key G4")
	PORT_START("KEYS2")
	KN_KEYPC(0x0001, 0x20, 68, KEYCODE_H, "Key G#4")
	KN_KEYPC(0x0002, 0x21, 69, KEYCODE_N, "Key A4")
	KN_KEYPC(0x0004, 0x22, 70, KEYCODE_J, "Key A#4")
	KN_KEYPC(0x0008, 0x23, 71, KEYCODE_M, "Key B4")
	KN_KEYPC(0x0010, 0x24, 72, KEYCODE_Q, "Key C5")
	KN_KEYPC(0x0020, 0x25, 73, KEYCODE_2, "Key C#5")
	KN_KEYPC(0x0040, 0x26, 74, KEYCODE_W, "Key D5")
	KN_KEYPC(0x0080, 0x27, 75, KEYCODE_3, "Key D#5")
	KN_KEYPC(0x0100, 0x28, 76, KEYCODE_E, "Key E5")
	KN_KEYPC(0x0200, 0x29, 77, KEYCODE_R, "Key F5")
	KN_KEYPC(0x0400, 0x2A, 78, KEYCODE_5, "Key F#5")
	KN_KEYPC(0x0800, 0x2B, 79, KEYCODE_T, "Key G5")
	KN_KEYPC(0x1000, 0x2C, 80, KEYCODE_6, "Key G#5")
	KN_KEYPC(0x2000, 0x2D, 81, KEYCODE_Y, "Key A5")
	KN_KEYPC(0x4000, 0x2E, 82, KEYCODE_7, "Key A#5")
	KN_KEYPC(0x8000, 0x2F, 83, KEYCODE_U, "Key B5")
	PORT_START("KEYS3")
	KN_KEYPC(0x0001, 0x30, 84, KEYCODE_I, "Key C6")
	KN_KEYM(0x0002, 0x31, 85, "Key C#6")
	KN_KEYM(0x0004, 0x32, 86, "Key D6")
	KN_KEYM(0x0008, 0x33, 87, "Key D#6")
	KN_KEYM(0x0010, 0x34, 88, "Key E6")
	KN_KEYM(0x0020, 0x35, 89, "Key F6")
	KN_KEYM(0x0040, 0x36, 90, "Key F#6")
	KN_KEYM(0x0080, 0x37, 91, "Key G6")
	KN_KEYM(0x0100, 0x38, 92, "Key G#6")
	KN_KEYM(0x0200, 0x39, 93, "Key A6")
	KN_KEYM(0x0400, 0x3A, 94, "Key A#6")
	KN_KEYM(0x0800, 0x3B, 95, "Key B6")
	KN_KEYM(0x1000, 0x3C, 96, "Key C7")
#undef KN_KEYM
#undef KN_KEYPC
INPUT_PORTS_END


uint32_t kn7000_state::screen_update(screen_device &screen, bitmap_rgb32 &bitmap, const rectangle &cliprect)
{
	// Present the firmware's OWN composited image -- the exact bytes the real LCD
	// controller scans. The firmware's software compositor blends the UI plane and the
	// 12-bit direct-colour picture planes (see notes/display-dual-plane-direct-color.md)
	// into a 640x240 RGB565 buffer at 0x9CE00000 (linear, top-to-bottom). Reading it
	// directly gives a pixel-perfect display (gamma-correct UI colours, pictures
	// composited by the machine itself) and supersedes reconstructing it from the work-
	// RAM planes + CLUT. Runtime-verified against a dump: the home screen is pixel-exact.
	// (The boot-splash JPEG still decodes to garbage -- a separate software-decoder bug
	// -- so the splash reads as noise here too, faithfully.)
	// TODO: honour the 2-bit grayscale panel (type 2 at 0x50007578).
	constexpr offs_t LCD = (0x9ce00000 - 0x9c000000) / 4;      // word offset of the framebuffer in the 0x9c RAM
	// KN7000: 640x240 RGB565, scanned top-to-bottom. KN6000/KN6500: the same composited buffer,
	// but the panel is RGB555 and physically mounted rotated 180 degrees -- so read it reversed
	// (bottom-right to top-left) and decode 5-5-5. (Decoding a 555 gray as 565 tinted it blue.)
	const bool kn6 = m_lcd_kn6;
	for (int y = cliprect.top(); y <= cliprect.bottom(); y++)
	{
		uint32_t *const dst = &bitmap.pix(y);
		for (int x = cliprect.left(); x <= cliprect.right(); x++)
		{
			const offs_t k = kn6 ? offs_t(239 - y) * 640 + (639 - x) : offs_t(y) * 640 + x;   // linear pixel index
			const uint32_t w = m_lcdbuf[LCD + (k >> 1)];
			const uint16_t v = (k & 1) ? uint16_t(w >> 16) : uint16_t(w);   // little-endian
			dst[x] = kn6
				? rgb_t(((v >> 10) & 0x1f) << 3, ((v >> 5) & 0x1f) << 3, (v & 0x1f) << 3)    // RGB555
				: rgb_t(((v >> 11) & 0x1f) << 3, ((v >> 5) & 0x3f) << 2, (v & 0x1f) << 3);   // RGB565
		}
	}
	return 0;
}


void kn7000_state::machine_start()
{
	// output_finders auto-resolve in this MAME version (see kn5000_cpanel) --
	// no explicit resolve() call is needed or available.

	save_item(NAME(m_dsp_index));
	save_item(NAME(m_dsp_dl_words));

	// Periodic control-panel button scan (the real sub-CPUs poll their matrices
	// continuously and report changes over the serial link).
	m_panel_timer = timer_alloc(FUNC(kn7000_state::panel_scan), this);
	m_panel_evt = timer_alloc(FUNC(kn7000_state::panel_event), this);
	m_panel_txdone = timer_alloc(FUNC(kn7000_state::panel_event), this);

	// The AM33 maskable interrupt vectors to the library-ROM low-level handler
	// (self-loaded; context-save entry at 0x4C03DDA0). The system-tick timer
	// raises the periodic interrupt that drives the MILK scheduler.
	m_maincpu->set_irq_vector(0x4C03DDA0);

	// KN6000/KN6500: unlike the KN7000 (which self-loads its library), the
	// "library" at 0x4C000000/0x8C000000 is a bus mirror of the program ROM.
	// Populate the aliased libram from the program ROM so the boot finds it.
	if (m_lib_mirror)
		memcpy(memshare("libram")->ptr(), memregion("maincpu")->base(), memregion("maincpu")->bytes());
	m_sys_timer = timer_alloc(FUNC(kn7000_state::sys_tick), this);
	m_fav_timer = timer_alloc(FUNC(kn7000_state::fav_preload), this);
	m_dsp_irq_timer = timer_alloc(FUNC(kn7000_state::dsp_audio_tick), this);
	m_tempo_timer = timer_alloc(FUNC(kn7000_state::tempo_tick), this);
	m_sd_insert_timer = timer_alloc(FUNC(kn7000_state::sd_insert), this);

	save_item(NAME(m_gxicr));
	save_item(NAME(m_sio_config));
	save_item(NAME(m_sio_control));
	save_item(NAME(m_sio_rx_fifo));
	save_item(NAME(m_sio_rx_head));
	save_item(NAME(m_sio_rx_tail));
	save_item(NAME(m_panel_pos));
	save_item(NAME(m_panel_p1));
	save_item(NAME(m_panel_p2));
	save_item(NAME(m_btn_prev));
	save_item(NAME(m_snd_500e));
	save_item(NAME(m_tg_addr));
	save_item(NAME(m_tmr7_mode));
	save_item(NAME(m_tmr7_base));
	save_item(NAME(m_tg_reg));
}

void kn7000_state::machine_reset()
{
	for (int ch = 0; ch < 3; ch++)
	{
		m_sio_config[ch] = 0;
		m_sio_control[ch] = 0;
		m_sio_rx_head[ch] = m_sio_rx_tail[ch] = 0;
	}
	m_panel_pos = 0;
	std::fill(std::begin(m_btn_prev), std::end(m_btn_prev), 0);
	std::fill(std::begin(m_gxicr), std::end(m_gxicr), 0);

	// Effects DSP (F.2): hold the SHARC halted. The firmware host-boots it -- dsp_data_w
	// streams its program into internal memory and releases it (INPUT_LINE_HALT clear + PC
	// = entry) when the resident kernel is fully loaded. Until then it must not run (its
	// memory is empty). It is released only once the firmware finishes the host-boot upload.
	m_dsp->set_input_line(INPUT_LINE_HALT, ASSERT_LINE);
	m_dsp_running = false;
	m_dsp_dl_words = 0; m_dsp_mode = 0; m_dsp_wcnt = 0; m_dsp_cur = 0; m_dsp_dl_addr = 0;
	m_dsp_block_open = false;
	m_dsp_irq_timer->adjust(attotime::never);   // audio frame tick starts only once the kernel is loaded

	// Start scanning the panel at ~250 Hz.
	m_panel_timer->adjust(attotime::from_hz(250), 0, attotime::from_hz(250));

	// System tick ~1 kHz (real rate TBD -- input clock unknown; tune later). The timer
	// interrupt dispatches (via IAGR=group<<3) to the real RTOS handler, whose context
	// save uses the AM33 F6 "udf"/DSP ops (getx etc.) -- now implemented in the core
	// (execute_f6), so this is ACTIVE and the boot is stable. (Earlier this was HELD
	// because those F6 ops were skipped and the saved context was corrupted; that is
	// resolved.) See notes/interrupt-mechanism.md ("F6 / udf extended ops").
	if (m_lib_mirror)
		// KN6000/KN6500: delay the tick past the single-threaded boot so the scheduler
		// does not preempt RTOS object creation (which derailed on an uncreated object).
		// Partial: the boot then waits on an unmodeled on-chip timer (0x34001080-92) that
		// drives a KN6000-specific ms counter. See notes/kn6000-kn6500-boot.md.
		m_sys_timer->adjust(attotime::from_seconds(2), 0, attotime::from_hz(1000));
	else
		m_sys_timer->adjust(attotime::from_hz(1000), 0, attotime::from_hz(1000));

	// Pre-load the factory "Initial Data" Favorites into battery-backed SRAM. This
	// must run AFTER the boot BSS-clear (which zeroes work RAM up to ~0x50180000) but
	// before the Favorites screen is opened, so it is deferred to a one-shot timer
	// (see fav_preload). Confirmed by RE: a machine_reset write is wiped by the clear;
	// a t=3s write survives and the firmware keeps it.
	m_fav_timer->adjust(attotime::from_seconds(3));

	m_tmr7_mode = 0;
	m_tmr7_base = 0;
	m_tempo_timer->adjust(attotime::never);
	if (!m_lib_mirror)
	{
		// SD card-detect: the polled group-0x1B ICR (0x3400016C) bit4 reads
		// 1 = no card / 0 = card present (raw read 0x4854bce0: btst bit4). The
		// SD state machine is edge-driven -- a static level never fires the
		// card-insert message -- so we always boot "no card" (bit4=1) and, if a
		// card image is attached AND the cover is closed, produce the 1->0 INSERT
		// EDGE a few seconds after boot: that both fires the firmware's insert
		// message (0x107020bb -> mount) and leaves bit4=0 so the card-check
		// debounce (0x4854bd39) reads present. Cover open, or no image -> stays
		// "no card / lid open" (ERROR 93 on SD access). The user can open/close
		// the cover live (SDCOVER) to remove/insert afterwards.
		m_gxicr[0x1B] |= 0x0012;
		const bool cover_open = (m_sdcover->read() & 1) != 0;
		if (!cover_open && m_sdcard && m_sdcard->get_card_present())
			m_sd_insert_timer->adjust(attotime::from_seconds(6));
		else
			m_sd_insert_timer->adjust(attotime::never);
		m_gpio8004 = 0xFFFF;                            // CS released (bit1=1) at reset
		if (m_sdcard)
			m_sdcard->spi_ss_w(0);                      // deselected until the firmware asserts CS (0x36008004 bit1)
	}
}

void kn7000_state::kn7000(machine_config &config)
{
	// Panasonic MN103002A (MN10300/AM33 core), IC4 on MAIN 1/5.
	// Clock tree (SX-KN7000 service manual, SCHEMATIC DIAGRAM-1): a 16.0 MHz
	// reference crystal X1 (part H0J160500026 -- the H0J<freq*10> code family:
	// X102 H0J177=17.73, X103 H0J240=24.0, X104 H0J143=14.32 MHz) drives clock
	// generator IC6 (C02BZ0000667: XIN/XOUT/FRSEL/S1/S2 -> SSCLK). SSCLK also
	// feeds a divide-by-2 flip-flop IC11 (TC7WH74) that clocks peripherals, so
	// the CPU itself is NOT the /2 branch (an 8 MHz AM33 is implausible for a
	// 2003 flagship that boots in ~12-15 s). The AM33 core runs the 16 MHz
	// reference through its internal PLL; x2 = 32 MHz matches the measured boot
	// work (~400M cycles / 32 MHz ~= 12.5 s, i.e. real-hardware boot time).
	// CONFIRMED via firmware MIDI-baud cross-check: the MIDI UARTs (SC1/SC2 at
	// 0x34000810/0x34000820) are set to 8N1 with the baud clock = Timer-3
	// underflow / 8 (SC1CTR CK field = 0x5), and TM3 counts at IOCLK with reload
	// TM3BR = 0x3F (63). MIDI baud is exactly 31250, so
	//   31250 = IOCLK / (8 * (0x3F + 1)) = IOCLK / 512  =>  IOCLK = 16.000 MHz.
	// The AM33 core runs at 2x IOCLK (schematic /2 peripheral branch via IC11;
	// MN10300 IOCLK = fc/2 convention) => fc = 32.000 MHz. Only 16 MHz IOCLK
	// reproduces TM3BR=0x3F (32 MHz would need 0x7F); 40/48 excluded likewise.
	MN10300(config, m_maincpu, 16_MHz_XTAL * 2);
	m_maincpu->set_irq_acknowledge_callback(FUNC(kn7000_state::irq_ack));
	m_maincpu->set_addrmap(AS_PROGRAM, &kn7000_state::maincpu_mem);

	/* video hardware */
	// LCD panel. Exact geometry is uncertain: the KN7000 front-panel LCD is
	// reported as either 320x240 or 640x240. Using 640x240 as a placeholder.
	// TODO: confirm resolution, pixel clock and the LCD controller feeding
	//       the V-RAM at IC104.
	SCREEN(config, m_screen, SCREEN_TYPE_LCD);
	m_screen->set_refresh_hz(60);
	m_screen->set_vblank_time(ATTOSECONDS_IN_USEC(0));
	// 640x240 8bpp LCD (proven from the blitter stride 0x280 and height 0xF0).
	m_screen->set_size(640, 240);
	m_screen->set_visarea(0, 640 - 1, 0, 240 - 1);
	m_screen->set_screen_update(FUNC(kn7000_state::screen_update));

	// Clickable front-panel artwork: buttons bound to the ioports, LEDs bound to
	// the cpl_led/cpc_led/cpr_led outputs. Generated by tools/gen_layout.py.
	config.set_default_layout(layout_kn7000);

	// --- MIDI ports (SIO channels 1 & 2 at 0x34000810 / 0x34000820) ---------
	// Each channel has a byte<->bit UART bridge feeding a standard MAME MIDI
	// IN/OUT port pair. TX (firmware -> SIO -> UART -> MIDI OUT) works now;
	// MIDI IN bytes are queued on the SIO RX FIFO but only reach the firmware
	// once the MN10300 core takes SIO receive interrupts.
	KN7000_SIO_UART(config, m_midi_uart[0], 0);
	m_midi_uart[0]->tx_cb().set("mdout1", FUNC(midi_port_device::write_txd));
	m_midi_uart[0]->rx_cb().set(FUNC(kn7000_state::midi_rx<SIO_MIDI1>));
	MIDI_PORT(config, "mdin1", midiin_slot, "midiin").rxd_handler().set(m_midi_uart[0], FUNC(kn7000_sio_uart_device::rx_w));
	MIDI_PORT(config, "mdout1", midiout_slot, "midiout");

	// MIDI -> internal key bed (velocity). A dedicated IN port so a controller
	// plays the key bed itself, distinct from the two rear MIDI IN jacks.
	KN7000_SIO_UART(config, m_kbd_midi_uart, 0);
	m_kbd_midi_uart->rx_cb().set(FUNC(kn7000_state::kbd_midi_rx));
	MIDI_PORT(config, "kbdmidi", midiin_slot, "midiin").rxd_handler().set(m_kbd_midi_uart, FUNC(kn7000_sio_uart_device::rx_w));

	KN7000_SIO_UART(config, m_midi_uart[1], 0);
	m_midi_uart[1]->tx_cb().set("mdout2", FUNC(midi_port_device::write_txd));
	m_midi_uart[1]->rx_cb().set(FUNC(kn7000_state::midi_rx<SIO_MIDI2>));
	MIDI_PORT(config, "mdin2", midiin_slot, "midiin").rxd_handler().set(m_midi_uart[1], FUNC(kn7000_sio_uart_device::rx_w));
	MIDI_PORT(config, "mdout2", midiout_slot, "midiout");

	// --- Sound (first cut): a bring-up sine synth keyed by the PC key bed, so
	//     notes are audible now. Real dual-TG PCM synthesis + effects DSP is future
	//     work (see notes/audio-output-implementation-plan.md). Shared by all the
	//     models that reuse this config; only kn7000 drops MACHINE_NO_SOUND for now.
	SPEAKER(config, "lspeaker").front_left();
	SPEAKER(config, "rspeaker").front_right();
	SPI_SDCARD(config, m_sdcard, 0);
	m_sdcard->set_prefer_sd();
	m_sdcard->spi_miso_callback().set(FUNC(kn7000_state::sd_miso_w));

	KN7000_TONEGEN(config, m_tonegen, 0);
	// F.3: route the tone-generator audio through the effects-DSP bridge, then to the speakers.
	// The bridge is transparent (passes the TG through) unless the effects DSP is running, so
	// this does not change the DSP-off behaviour.
	KN7000_DSP_BRIDGE(config, m_dspbridge, 0);
	m_tonegen->add_route(0, *m_dspbridge, 1.0, 0);
	m_tonegen->add_route(1, *m_dspbridge, 1.0, 1);
	m_dspbridge->add_route(0, "lspeaker", 1.0);
	m_dspbridge->add_route(1, "rspeaker", 1.0);

	// IC306 effects DSP -- Analog Devices ADSP-21065L SHARC (part S21065LKS240, ~60 MHz),
	// host-booted by the MN10300 over the 0x98000000 (index) / 0x9C000000 (data) port.
	// Phase F.1: instantiate MAME's 2106x SHARC core (the 21065L shares the ISA) in
	// HOST boot mode so it sits idle until the firmware uploads its program (F.2). The
	// 21065L's own memory/IOP personality (a subclass) and the SPORT audio path (F.3)
	// come next; for now this proves the core integrates and the KN7000 still boots.
	// See notes/sharc-lle-assessment.md.
	ADSP21065L(config, m_dsp, 60'000'000);
	m_dsp->enable_recompiler();   // DRC: the effects kernel is fixed-point-MAC heavy; interpreting
	                              // it drops the machine to ~36% real time, the DRC keeps it near 90%
	m_dsp->set_boot_mode(adsp21065l_device::BOOT_MODE_HOST);

	// TODO: real tone generators IC201/IC205; DSP SDRAM IC307/8, SPORT audio path;
	//       floppy disk controller (IC103), SD card and USB.
}

// KN6000/KN6500 reuse the KN7000 machine, but their library ROM at 0x4C000000 is
// a bus mirror of the program ROM (populated in machine_start), not self-loaded.
void kn7000_state::kn6000(machine_config &config)
{
	kn7000(config);
	m_lib_mirror = true;
	m_lcd_kn6 = true;
}


ROM_START(kn7000)
	ROM_REGION32_LE(0x400000, "maincpu", ROMREGION_ERASEFF)   // program IC16/IC17 -> 0x48400000
	ROM_LOAD32_WORD("kn7000_program_even.rom", 0x000000, 0x200000, CRC(529b87ce) SHA1(f198fd9a9ea31a454acfe7be0eb935beca6771b1))
	ROM_LOAD32_WORD("kn7000_program_odd.rom",  0x000002, 0x200000, CRC(a36e6222) SHA1(721d4469dc5f692f7a2c16c556b2e21115df19f6))
	ROM_REGION32_LE(0x400000, "table", ROMREGION_ERASEFF)
	ROM_LOAD32_WORD("kn7000_table_even.rom", 0x000000, 0x200000, CRC(005a6db2) SHA1(2f4112ea9b039b17b5ada6952b7646adae8d9dd6))
	ROM_LOAD32_WORD("kn7000_table_odd.rom",  0x000002, 0x200000, CRC(7e1a312e) SHA1(435b597b926ebac56d4710bcae25b635a59a9ce5))

	// TODO: Library / boot ROM at 0x4C000000 - currently undumped.
	//ROM_REGION(0x100000, "library", ROMREGION_ERASEFF)
	//ROM_LOAD("kn7000_library.rom", 0x000000, 0x100000, NO_DUMP)

	// TODO: Picture flash at 0x57800000 - not dumped yet.
	//ROM_REGION(0x800000, "picture", ROMREGION_ERASEFF)
	//ROM_LOAD("kn7000_picture.rom", 0x000000, 0x800000, NO_DUMP)

	// Tone-generator waveform / sample ROMs -- UNDUMPED. The synth LSI IC205
	// (C1BB00000709, "TONE GENERATOR" in the service manual) plays PCM samples
	// from four custom Panasonic mask ROMs on the sound board: IC203
	// (C3CBQD000002), IC204 (C3CBQD000001), IC207 (C3CBQD000004), IC208
	// (C3CBQD000003). These are physically separate chips, NOT part of the
	// firmware update disks this driver's ROMs come from, so audible sound is
	// impossible until they are dumped from the board (see the service manual
	// "8.9 WAVE ROM test" / "8.10 SOUND SYSTEM test"; sizes below are placeholders).
	//ROM_REGION(0x400000, "wave", ROMREGION_ERASEFF)
	//ROM_LOAD("kn7000_wave_ic203.rom", 0x000000, 0x400000, NO_DUMP)  // C3CBQD000002
	//ROM_LOAD("kn7000_wave_ic204.rom", 0x400000, 0x400000, NO_DUMP)  // C3CBQD000001
	//ROM_LOAD("kn7000_wave_ic207.rom", 0x800000, 0x400000, NO_DUMP)  // C3CBQD000004
	//ROM_LOAD("kn7000_wave_ic208.rom", 0xc00000, 0x400000, NO_DUMP)  // C3CBQD000003
ROM_END


// ===================================================================
// KN6000 / KN6500 -- MN10300 siblings of the KN7000 (DRAFT drivers).
// Same CPU family and same 0x48400000 program base as the KN7000
// (verified: KN6000 reset vector at 0x48400000 is "jmp 0x484002e3"),
// so for now they reuse kn7000_state and the kn7000 machine config;
// per-model memory map / peripheral wiring is still to be tuned.
// The images are the decompressed IK*.SLD (KN6000) / IKV*.SLD (KN6500)
// firmware-update payloads -- BAD_DUMP because they are derived from
// the update disks, not read from the chips (IC11/IC12 program flash,
// IC13/IC14 table mask ROM per the service manual).
// ===================================================================
ROM_START(kn6000)
	ROM_REGION32_LE(0x400000, "maincpu", ROMREGION_ERASEFF)   // program IC12/IC11 (IK1) -> 0x48400000
	ROM_LOAD32_WORD("kn6000_program_even.rom", 0x000000, 0x200000, CRC(56c2cfe3) SHA1(e15a4c73440f1dcdf06457f9956c96bf20d68b16))
	ROM_LOAD32_WORD("kn6000_program_odd.rom",  0x000002, 0x200000, CRC(9d94da6c) SHA1(d73b4c8ebf0c67b6a2eeb5571d0273fc6efbfe4c))
	ROM_REGION32_LE(0x400000, "table", ROMREGION_ERASEFF)     // table -> 0x48000000 (IK2, 0x1F7A31)
	ROM_LOAD32_WORD("kn6000_table_even.rom", 0x000000, 0x200000, CRC(fa5e4f93) SHA1(0426da99b1589c0362e6321466beab21b22b81b0))
	ROM_LOAD32_WORD("kn6000_table_odd.rom",  0x000002, 0x200000, CRC(fd8e3bcd) SHA1(e1b63d45299b67e5258d5d08a949ea8e05c1b8e6))
ROM_END

ROM_START(kn6500)
	ROM_REGION32_LE(0x400000, "maincpu", ROMREGION_ERASEFF)   // program IC12/IC11 (IKV1) -> 0x48400000
	ROM_LOAD32_WORD("kn6500_program_even.rom", 0x000000, 0x200000, CRC(f42a2fcf) SHA1(7cebf73bf623fd714ca455ed50b80da1d2186414))
	ROM_LOAD32_WORD("kn6500_program_odd.rom",  0x000002, 0x200000, CRC(ca2a733f) SHA1(2484d3b76b62b05ded39e4194cdc74fd3c01bcbe))
	ROM_REGION32_LE(0x400000, "table", ROMREGION_ERASEFF)     // table -> 0x48000000 (IKV2, 0x181691)
	ROM_LOAD32_WORD("kn6500_table_even.rom", 0x000000, 0x200000, CRC(8c7f33a2) SHA1(d44fb4415cd6b571e11e57d4a7642226b0bf4edf))
	ROM_LOAD32_WORD("kn6500_table_odd.rom",  0x000002, 0x200000, CRC(6953e094) SHA1(abf4c2252d40c71c761503d657593eb6e9c0eecc))
ROM_END


// ===================================================================
// KN2400 / KN2600 -- also MN10300/MILK siblings (DRAFT drivers). The
// SX-KN2000/KN2400/KN2600 family shares ONE firmware image: the update
// disk's KN24PRG.DAT is byte-identical to LKG1.SLD + LKG2.SLD, and the
// image carries "KN2000"/"KN2400"/"KN2600" model strings (it branches on
// model at runtime). Verified MN10300: reset vector at 0x48400000 is
// "jmp 0x48705bdf"; MILK toolkit present (MT_GetProcedureSp, ...). So
// kn2600 is a clone of kn2400 (same ROMs). Reuses kn7000_state / the
// kn7000 machine config for now; memory map / peripherals to be tuned.
// ===================================================================
ROM_START(kn2400)
	// KN2400/KN2600/PR54 share one firmware (runtime model selector): program =
	// LKG1@0x48400000 + LKG2@0x48600000 (== KN24PRG.DAT); no separate table flash.
	ROM_REGION32_LE(0x400000, "maincpu", ROMREGION_ERASEFF)   // program
	ROM_LOAD32_WORD("kn2400_program_even.rom", 0x000000, 0x200000, CRC(b94fc8a8) SHA1(86d5d9916afdb90f82de78064b1d76fce3a21d7b))
	ROM_LOAD32_WORD("kn2400_program_odd.rom",  0x000002, 0x200000, CRC(73781cbc) SHA1(d90a3560561efd94322dca1a6710f2d5d3837cd2))
	ROM_REGION32_LE(0x400000, "table", ROMREGION_ERASEFF)  // no separate table flash on this model
ROM_END

// KN2600 shares the KN2400 firmware image -> clone of kn2400 (ROMs resolve from the parent set).
ROM_START(kn2600)
	ROM_REGION32_LE(0x400000, "maincpu", ROMREGION_ERASEFF)
	ROM_LOAD32_WORD("kn2400_program_even.rom", 0x000000, 0x200000, CRC(b94fc8a8) SHA1(86d5d9916afdb90f82de78064b1d76fce3a21d7b))
	ROM_LOAD32_WORD("kn2400_program_odd.rom",  0x000002, 0x200000, CRC(73781cbc) SHA1(d90a3560561efd94322dca1a6710f2d5d3837cd2))
	ROM_REGION32_LE(0x400000, "table", ROMREGION_ERASEFF)
ROM_END

} // anonymous namespace


//   YEAR  NAME    PARENT  COMPAT  MACHINE  INPUT   CLASS         INIT        COMPANY     FULLNAME      FLAGS
SYST(2002, kn7000, 0,      0,      kn7000,  kn7000, kn7000_state, empty_init, "Technics", "SX-KN7000", MACHINE_NOT_WORKING | MACHINE_IMPERFECT_SOUND)

// KN6000 / KN6500 -- draft drivers reusing the KN7000 machine config (same MN10300 CPU, same 0x48400000 base).
SYST(2000, kn6000, 0,      0,      kn6000,  kn7000, kn7000_state, empty_init, "Technics", "SX-KN6000", MACHINE_NOT_WORKING | MACHINE_NO_SOUND)
SYST(2001, kn6500, 0,      0,      kn6000,  kn7000, kn7000_state, empty_init, "Technics", "SX-KN6500", MACHINE_NOT_WORKING | MACHINE_NO_SOUND)

// KN2400 / KN2600 -- MN10300/MILK siblings sharing one firmware image (kn2600 = clone of kn2400).
SYST(1998, kn2400, 0,      0,      kn7000,  kn7000, kn7000_state, empty_init, "Technics", "SX-KN2400", MACHINE_NOT_WORKING | MACHINE_NO_SOUND)
SYST(2000, kn2600, kn2400, 0,      kn7000,  kn7000, kn7000_state, empty_init, "Technics", "SX-KN2600", MACHINE_NOT_WORKING | MACHINE_NO_SOUND)

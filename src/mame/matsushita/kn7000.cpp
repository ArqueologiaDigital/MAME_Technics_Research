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
#include "machine/intelfsh.h"      // IC21 custom-data flash (16 Mbit bottom boot)
#include "imagedev/floppy.h"        // IC103 floppy drive
#include "machine/upd765.h"         // IC103 floppy disk controller (uPD765-family, C1DB00000607)
#include "bus/midi/midiinport.h"
#include "bus/midi/midioutport.h"
#include "kn7000_tonegen.h"       // tone-generator HLE (IC201 master + IC205 sub)
#include "kn6000_tonegen.h"       // ... and its KN6000/KN6500 sibling (IC213, one chip, 64 voices)
#include "kn7000_cpanel.h"        // control-panel HLE (buttons, LEDs, analog controls)
#include "kn6000_cpanel.h"        // ... and its KN6000/KN6500 sibling (same base class)

#include "screen.h"
#include "speaker.h"          // first-cut audio output

#include "kn7000.lh"
#include "kn6000.lh"

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
	// rawl/rawr = the un-send-scaled TG mix (for parallel effect sends such as chorus).
	void pop_input(int32_t &l, int32_t &r, int32_t &rawl, int32_t &rawr)
	{
		if (m_rx_rd != m_rx_wr)
		{
			l = m_rx[m_rx_rd][0]; r = m_rx[m_rx_rd][1];
			rawl = m_rxraw[m_rx_rd][0]; rawr = m_rxraw[m_rx_rd][1];
			m_rx_rd = (m_rx_rd + 1) % RING;
		}
		else { l = r = rawl = rawr = 0; }   // underflow: DSP consumed ahead of the stream (brief; harmless)
	}
	void push_output(int32_t l, int32_t r, int32_t cl = 0, int32_t cr = 0, int32_t dl = 0, int32_t dr = 0, int32_t ml = 0, int32_t mr = 0)
	{
		if (!m_dsp_active) { m_dsp_active = true; m_rx_rd = m_rx_wr; }   // first output: flush stale pre-DSP input
		m_tx[m_tx_wr][0] = l; m_tx[m_tx_wr][1] = r;
		m_tx[m_tx_wr][2] = cl; m_tx[m_tx_wr][3] = cr;   // chorus return (0 when chorus off -> no effect)
		m_tx[m_tx_wr][4] = dl; m_tx[m_tx_wr][5] = dr;   // sound-dsp return (0 when off -> no effect)
		m_tx[m_tx_wr][6] = ml; m_tx[m_tx_wr][7] = mr;   // multi return (0 when off -> no effect)
		m_tx_wr = (m_tx_wr + 1) % RING;
		if (m_tx_wr == m_tx_rd) m_tx_rd = (m_tx_rd + 1) % RING;   // overflow: drop oldest (bound latency)
	}

	// Master output gain (0..1), set from the front-panel MAIN VOLUME slider by the driver.
	void set_master_gain(float g) { m_master_gain = g; }


	// TG output-bus routing (the REVERB toggle's hardware action; see the tonegen's
	// group-0x20 capture): send = what the DSP receives; direct/return = the DAC-side
	// crossfade between the raw TG and the DSP output. Only meaningful when the audio
	// path is routed through the DSP; the Bypassed debug path stays plain dry.
	void set_bus_gains(float send, float direct, float ret, float depth)
	{ m_gain_send = send; m_gain_direct = direct; m_gain_return = ret; m_gain_depth = depth; }
	// Per-effect DSP returns (each effect has its OWN return level; the reverb toggle only moves
	// the reverb's -- see the tonegen capture). SOUND DSP and MULTI scale their wet by these
	// instead of the reverb return, so reverb on/off no longer mutes them.
	void set_effect_returns(float dsp_ret, float multi_ret)
	{ m_gain_dsp_ret = dsp_ret; m_gain_multi_ret = multi_ret; }

protected:
	virtual void device_start() override
	{
		m_stream = stream_alloc(2, 2, 44100);
		save_item(NAME(m_rx));   save_item(NAME(m_rxraw));   save_item(NAME(m_tx));
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
			// TG bus routing (reverb toggle): the DSP receives the SEND bus, not the raw mix.
			const float gsend = m_gain_send, gdir = m_gain_direct, gret = m_gain_return;
			const float gdepth = m_gain_depth;
			m_rx[m_rx_wr][0] = int32_t(double(il) * gsend);
			m_rx[m_rx_wr][1] = int32_t(double(ir) * gsend);
			m_rxraw[m_rx_wr][0] = il;   // un-send-scaled TG mix, for the chorus send bus
			m_rxraw[m_rx_wr][1] = ir;
			m_rx_wr = (m_rx_wr + 1) % RING;
			if (m_rx_wr == m_rx_rd) m_rx_rd = (m_rx_rd + 1) % RING;

			int32_t ol, orr;
			if (!m_dsp_active)
			{
				ol = il; orr = ir;   // DSP not talking yet (early boot) -> dry TG passthrough
			}
			else
			{
				// Consume the DSP's output only once a small latency buffer has built up, then
				// hold the last sample on underflow. NEVER fall back to the TG here: mixing the
				// (latent) DSP output with the immediate TG phase-cancels and clicks.
				const uint32_t fill = (m_tx_wr - m_tx_rd + RING) % RING;
				if (!m_tx_primed && fill >= PRIME) m_tx_primed = true;
				int32_t chl, chr, ddl, ddr, mml, mmr;
				if (m_tx_primed && m_tx_rd != m_tx_wr)
				{
					ol = m_tx[m_tx_rd][0]; orr = m_tx[m_tx_rd][1];
					chl = m_tx[m_tx_rd][2]; chr = m_tx[m_tx_rd][3];
					ddl = m_tx[m_tx_rd][4]; ddr = m_tx[m_tx_rd][5];
					mml = m_tx[m_tx_rd][6]; mmr = m_tx[m_tx_rd][7];
					m_tx_rd = (m_tx_rd + 1) % RING;
					m_tx_last[0] = ol; m_tx_last[1] = orr; m_tx_last[2] = chl; m_tx_last[3] = chr;
					m_tx_last[4] = ddl; m_tx_last[5] = ddr; m_tx_last[6] = mml; m_tx_last[7] = mmr;
				}
				else { ol = m_tx_last[0]; orr = m_tx_last[1]; chl = m_tx_last[2]; chr = m_tx_last[3];
				       ddl = m_tx_last[4]; ddr = m_tx_last[5]; mml = m_tx_last[6]; mmr = m_tx_last[7]; }
				// DAC-side crossfade (reverb toggle): DSP return vs TG direct. With reverb ON
				// the pair is {direct 0, return 7F}; OFF is {direct 7F, return 0} -- so OFF
				// also mutes the (currently diverging) reverb tank at the DAC, exactly as the
				// captured hardware routing dictates.
				// DSP return scaled by the TG return level and TOTAL DEPTH (0x8338 low7,
				// live-verified against the on-screen value; default 0x50/127 ~ 0.63).
				ol = int32_t(double(ol) * gret * gdepth + double(il) * gdir);
				orr = int32_t(double(orr) * gret * gdepth + double(ir) * gdir);
				// Chorus/SOUND-DSP/MULTI returns: each is an INDEPENDENT wet, added post-crossfade
				// at its own makeup so it does NOT couple to the reverb TOTAL DEPTH. Live capture
				// (notes/effect-return-routing.md) proved each effect owns a distinct RETURN register
				// and the reverb toggle moves ONLY the reverb's -- so these must NOT follow the reverb
				// return (gret). Previously they did, which wrongly muted them whenever reverb was off.
				// - CHORUS has no return register (toggling it moves only its send) -> send-driven wet
				//   with a fixed makeup (the chsend>0 gate already keeps it 0 when off; bit-exact).
				// - SOUND DSP scales by its own return (ch09.rA = gdsp_ret); MULTI by ch06.rA.
				const float gdsp_ret = m_gain_dsp_ret, gmul_ret = m_gain_multi_ret;
				constexpr double CHORUS_WET = 0.60;
				ol  += int32_t(double(chl) * CHORUS_WET);
				orr += int32_t(double(chr) * CHORUS_WET);
				constexpr double DSP_WET = 0.60;
				ol  += int32_t(double(ddl) * gdsp_ret * DSP_WET);
				orr += int32_t(double(ddr) * gdsp_ret * DSP_WET);
				constexpr double MULTI_WET = 0.60;
				ol  += int32_t(double(mml) * gmul_ret * MULTI_WET);
				orr += int32_t(double(mmr) * gmul_ret * MULTI_WET);
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
	int32_t m_rxraw[RING][2] = { };// raw (un-send-scaled) TG mix, parallel to m_rx (chorus feed)
	int32_t m_tx[RING][8] = { };   // DSP output ring: [0/1]=reverb(u0) [2/3]=chorus(u9) [4/5]=sound-dsp(u2) [6/7]=multi(u1)
	uint32_t m_rx_rd = 0, m_rx_wr = 0, m_tx_rd = 0, m_tx_wr = 0;
	bool m_dsp_active = false;     // the DSP has started producing output
	bool m_tx_primed = false;      // the output latency buffer has filled
	int32_t m_tx_last[8] = { };    // last DSP output (held on underflow): reverb + chorus + sound-dsp + multi
	std::atomic<float> m_master_gain{ 1.0f };   // MAIN VOLUME slider (audio thread reads, driver writes)
	std::atomic<float> m_gain_send{ 0.80f };    // TG -> DSP send level (reverb toggle)
	std::atomic<float> m_gain_direct{ 0.0f };   // DAC: TG direct (reverb-OFF side)
	std::atomic<float> m_gain_return{ 1.0f };   // DAC: DSP return (reverb-ON side)
	std::atomic<float> m_gain_depth{ float(0x50) / 127.0f };  // TOTAL DEPTH -> DSP-return scale
	std::atomic<float> m_gain_dsp_ret{ 0.0f };    // SOUND DSP own return (independent of reverb)
	std::atomic<float> m_gain_multi_ret{ 0.0f };  // MULTI own return (independent of reverb)
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
		, m_customflash(*this, "customflash")
		, m_lcdbuf(*this, "lcdbuf")
		, m_progrom(*this, "maincpu")
		, m_midi_uart(*this, "midi_uart%u", 0U)
		, m_kbd_midi_uart(*this, "kbdmidi_uart")
		, m_tonegen(*this, "tonegen")
		, m_dspbridge(*this, "dspbridge")
		, m_dsp(*this, "dsp")
		, m_dial(*this, "DIAL")
		, m_rearsw(*this, "REARSW")
		, m_sdsw(*this, "CPSD_SDSW")
		, m_sdcard(*this, "sdcard")
		, m_fdc(*this, "fdc")
		, m_floppy(*this, "fdc:0")
		, m_sdcover(*this, "SDCOVER")
		, m_volmain(*this, "VOL_MAIN")
		, m_volapcseq(*this, "VOL_APCSEQ")
		, m_tempoknob(*this, "TEMPO_KNOB")
		, m_cpanel(*this, "cpanel")
		, m_sd_leds(*this, "sd_led%u", 0U)
	{ }

	void kn7000(machine_config &config) ATTR_COLD;
	void kn6000(machine_config &config) ATTR_COLD;
	void kn6500(machine_config &config) ATTR_COLD;
	void kn2400(machine_config &config) ATTR_COLD;
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
	optional_device<fujitsu_29lv160b_device> m_customflash;  // IC21 @ 0x96800000
	uint32_t customflash_r(offs_t offset, uint32_t mem_mask = ~0);
	void customflash_w(offs_t offset, uint32_t data, uint32_t mem_mask = ~0);
	required_shared_ptr<uint32_t> m_lcdbuf;      // firmware's composited RGB565 LCD image @0x9CE00000
	bool m_lib_mirror = false;                   // KN6000/KN6500: library @0x4C/0x8C mirrors the program ROM
	bool m_ram90_workram = false;                // KN2400/KN2600: 0x90000000 = +0x40000000 alias of work RAM (library self-loads via it)
	bool m_lcd_kn6 = false;                      // KN6000/KN6500: LCD framebuffer is RGB555 and mounted rotated 180deg (vs the KN7000's upright RGB565)
	bool m_lcd_kn24 = false;                     // KN2400/KN2600: 320x240 4-level grayscale panel, 2bpp framebuffer at 0x9C800000
	required_region_ptr<uint32_t> m_progrom;     // program flash (holds the CLUT)
	required_device_array<kn7000_sio_uart_device, 2> m_midi_uart;
	required_device<kn7000_sio_uart_device> m_kbd_midi_uart;  // MIDI -> internal key bed (velocity)
	// Held by BASE type, like the control panel above: kn7000() installs the two-chip
	// KN7000 decode, kn6000() swaps in the KN6000/KN6500 one (same tag "tonegen", same
	// voice model, different register numbering).
	required_device<kn_tonegen_base_device> m_tonegen;   // first-cut audio (Phase C Stage 0)
	required_device<kn7000_dsp_bridge_device> m_dspbridge;  // F.3: routes TG audio through the effects DSP
	required_device<adsp21065l_device> m_dsp;           // IC306 effects DSP (ADSP-21065L SHARC; host-boot idle until F.2)

	template <int Ch> void midi_rx(uint8_t data) { m_maincpu->sio_rx_push(Ch, data); }

	// Control panel button ports and LEDs (CPL = 8 cols, CPC = 5 cols; CPR + the
	// serial HLE device that reads these / drives the LEDs are still to come).
	required_ioport m_dial;
	required_ioport m_rearsw;           // rear-panel MIDI IN / BASS PEDAL selector SW701 (strap bit12 = data-bus D28)
	required_ioport m_sdsw;               // SD front-panel switches (byte 0x9CC00008, active-low)
	optional_device<spi_sdcard_device> m_sdcard;   // the SD card (SPI protocol via the 0x9805000C byte mailbox)
	optional_device<n82077aa_device> m_fdc;        // IC103 floppy disk controller (C1DB00000607, N82077AA/PC-AT-compatible)
	optional_device<floppy_connector> m_floppy;    // the 3.5" floppy drive
	uint8_t fdc_r(offs_t off);                     // FDC (IC103) PC/AT registers at 0x98020000 (schematic-confirmed)
	void    fdc_w(offs_t off, uint8_t data);
	uint8_t fdc_dma_r(offs_t off);                 // FDC.DACK byte slot at 0x98010000 (software-DMA transfer)
	void    fdc_dma_w(offs_t off, uint8_t data);
	void    fdc_irq_w(int state);                  // FDC INTRQ -> INTC group 0x18
	void    fdc_drq_w(int state);                  // FDC DRQ  -> INTC group 0x18 (per-byte software-DMA)
	required_ioport m_sdcover;             // SD slot cover switch (open/closed)
	required_ioport m_volmain;             // front-panel MAIN VOLUME slider (0-100 adjuster)
	required_ioport m_volapcseq;           // front-panel APC/SEQ VOLUME slider (0-100 adjuster)
	required_ioport m_tempoknob;           // front-panel TEMPO/PROGRAM knob (0-100 adjuster; a RELATIVE encoder)
	// Held by BASE type: kn7000() installs the KN7000 panel, kn6000() swaps in the
	// KN6000/KN6500 one (same tag "cpanel", same protocol, different matrix + LEDs).
	required_device<kn_cpanel_base_device> m_cpanel;   // control-panel HLE (buttons, LEDs, analog controls)

	void maincpu_mem(address_map &map) ATTR_COLD;

	// bring-up logging handlers for the (not-yet-decoded) I/O banks
	uint16_t io_r(offs_t offset, uint16_t mem_mask = ~0);
	void io_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);

	// --- On-chip interrupt controller (INTC) at 0x34000100 ------------------
	// The register model (GxICR array, IAGR latch quirks, EXTMD, the group-0x17
	// DSP self-test self-ack, per-level vector delivery) lives in the MN10300
	// CPU core now (src/devices/cpu/mn10300/, internal map -- same migration
	// pattern as the SIO). The driver keeps only BOARD POLICY: which group each
	// peripheral asserts (this thin forwarder), the panel transfer-complete
	// re-delivery filter (group 0x11 "level-like until serviced"), and the
	// panel-ATN EXTMD edge-re-arm decode -- wired through the core's
	// intc_ack/intc_accept/intc_extmd callbacks in kn7000(machine_config).
	// See notes/interrupt-mechanism.md.
	enum { IRQGRP_TIMER = 0x06, IRQGRP_PANEL = 0x1A, IRQGRP_MIDI1 = 0x12, IRQGRP_MIDI2 = 0x14 };
	void intc_assert(int group) { m_maincpu->intc_assert(group); }
	bool m_c11_unserviced = false;             // a panel transfer-complete not yet accepted
	uint16_t m_extmd_prev = 0;                 // previous EXTMD value (edge decode across intc_extmd_cb)
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
	// 64-deep: a burst of key events between firmware polls must not overwrite unread
	// entries -- losing a RELEASE sticks a sustaining note forever (16 was overflowable
	// by a large chord/glissando released at once).
	uint16_t m_kbd_fifo[64] = { };
	uint8_t  m_kbd_head = 0, m_kbd_tail = 0;
	void kbd_push(uint8_t note, uint8_t vel)
	{
		m_kbd_fifo[m_kbd_head & 63] = uint16_t(note) | (uint16_t(vel) << 8); m_kbd_head++;
		// Keybed coupling for the tone generator's GATE-FOLLOW voices (brass/sax/organ
		// classes): tell it which key is being made/broken -- the real sub TG hosts this
		// FIFO itself, so it sees these events natively. See key_context()/key_break().
		if (note & 0x80) m_tonegen->key_break(note & 0x7F);
		else             m_tonegen->key_context(note);
	}

	// --- MIDI -> internal KEY BED bridge (velocity-sensitive) ------------------
	// A MIDI controller wired here plays the machine's OWN key bed (the voice-
	// event FIFO the firmware polls at 0x98050004), NOT the rear MIDI IN jacks:
	// note-on/off become key-bed events with the MIDI velocity, so the firmware
	// treats them exactly like physical key presses (self-tests that watch the
	// key bed see them, and dynamics/velocity are honoured). The key bed's FIFO
	// value is the KEY INDEX (internal note = index + 36 = MIDI note); MIDI note
	// n maps to index n-36, i.e. the 61-key compass C2(36)..C7(96). Notes outside
	// the compass are DROPPED (there is no honest pitch to clamp them to; note that a
	// controller octave-shifted mid-note can thus lose a release). Connect a host controller with -kbdmidi <port>.
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
	// modeled (group 0x17, see the core's intc_w), the firmware keeps 0x500066CC="present" and the
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
	// Resolve the firmware voice-record TYPE for a note-on (voice record +0x02 & 0x7C):
	// the library's key-off dispatchers (lib 0x4C004295 / 0x4C036D3F) switch on it --
	// types {04,08,10,20,40} receive the computed 6-write release ramp at key-up, any
	// other synthesis class gets NO key-up TG writes (plucked classes ring their own
	// envelope). Same record array and binding window as tg_pitch_resolve below.
	// ---- MODEL BINDING for the two resolves below --------------------------------
	// The KN6000/KN6500 firmware is a re-target of the same source tree, so it keeps
	// the SAME 0xB4-stride voice record with the SAME field semantics -- only the
	// array base and the slot mapping differ. Proven by the KN6000's own record
	// initialiser at 0x48493D80, which writes exactly the three fields these resolves
	// read, from a halfword pitch16 argument:
	//
	// WHICH ARRAY. The KN6000 has TWO 0xB4-stride arrays and only one of them is
	// indexed the way this code needs. The LIBRARY array at 0x502858F8 is indexed by
	// note-event element, NOT by voice slot -- live-measured: playing C4 then C5 filled
	// library records 00/01 both times while the notes went to TG slots 0/1 then 2/3.
	// The array to read is 0x5027AF28, a per-TG-SLOT COPY the firmware makes at note-on
	// (0x48492F20: `mulu slot,0xB4; add 0x5027AF28` as the destination, `mulu libidx,
	// 0xB4; add 0x502858F8` as the source, then a 0x2D-word block copy). Indexing THAT
	// by slot reproduces the KN7000's record-index == slot identity exactly, and is
	// live-verified: slot 0 -> note 60 pitch16 0x3C80, slot 2 -> note 72 pitch16 0x4880.
	//     movhu (0x20,sp),d0; asr 8,d0; extbu d0; or 0x80,d0; movbu d0,(8,a1)
	//        -> +0x08 = 0x80 | (pitch16 >> 8)   = active bit | internal note
	//     movhu (0x20,sp),d0; movhu d0,(0xa,a1) -> +0x0A = base pitch16
	//     movhu (0x20,sp),d0; movhu d0,(0xc,a1) -> +0x0C = notePitch16
	// That is field-for-field the KN7000's layout (its own writer is the library's
	// 0x4C030FB9), which is why the KN6000 needed no separate note->pitch RE: the
	// firmware publishes its computed musical pitch in a record we already decode.
	// See notes/kn6000-tonegen-spec.md.
	offs_t  m_tg_recbase   = 0x500AF940;   // library voice-record array (KN6000: 0x502858F8)
	bool    m_tg_one_chip  = false;        // KN6000/KN6500: one TG, slots 0..63, no chip select
	// The register class that carries pitch -- i.e. the note-on trigger the resolves
	// must answer for. KN7000: 0x2400|bit16. KN6000: 0x5000|bits16-17 (plane 0x14,
	// note-on blit site 0x48494A5E).
	uint16_t m_tg_pitch_cls = 0x2400, m_tg_pitch_mask = 0xFC0E;

	// slot = the library's voice-record index. On the KN7000 the two chips share one
	// 128-entry array with slot bit 6 selecting the window (lib primitive 0x4C036F98:
	// slot < 0x40 -> 0x98050000, else 0x98040000); the KN6000 has a single 64-entry
	// array behind a single window.
	int tg_slot(int tg, uint16_t tgaddr) const
	{
		const int s = (tgaddr >> 4) & 0x3F;
		return m_tg_one_chip ? s : (s | (tg == 0 ? 0x40 : 0x00));
	}

	int tg_type_resolve(int tg, uint16_t tgaddr)
	{
		if ((tgaddr & m_tg_pitch_mask) != m_tg_pitch_cls)
			return -1;
		// The record's synthesis/release class is decoded for the KN7000 only. The
		// KN6000 uses the same field offset but its value set (1/8 plus flag bits
		// 0x0100/0x0800, written at 0x48492FF0) has not been mapped onto the KN7000's
		// {04,08,10,20,40} release classes, so report "unknown" rather than guess --
		// the tone generator then treats every voice as firmware-managed, which is safe
		// because the KN6000 writes a universal key-up gate for all voice classes.
		if (m_tg_one_chip)
			return -1;
		auto &sp = m_maincpu->space(AS_PROGRAM);
		const offs_t rec = m_tg_recbase + tg_slot(tg, tgaddr) * 0xB4;
		if (!(sp.read_byte(rec + 0x08) & 0x80))
			return -1;                                       // record not bound
		return sp.read_word(rec + 0x02) & 0x7C;
	}

	int32_t tg_pitch_resolve(int tg, uint16_t tgaddr)
	{
		if ((tgaddr & m_tg_pitch_mask) != m_tg_pitch_cls)
			return -1;                                       // not a pitch write
		auto &sp = m_maincpu->space(AS_PROGRAM);
		const offs_t rec = m_tg_recbase + tg_slot(tg, tgaddr) * 0xB4;
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

	// --- On-chip 16-bit TEMPO timer (mode 0x34001082 / base 0x34001092 / count 0x340010A2)
	// The clock behind ALL sequenced playback (KN7000 96-PPQN sequencer tick;
	// KN6000/KN6500 ms-counter tick; both on INTC group 7). The TM4/TM5 model
	// lives in the MN10300 core now (same migration as the INTC above); its
	// underflow asserts group 7 internally -- nothing driver-side remains.

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

	// SD "in use" indicator (driver HLE approximation): the CPSD board's front-panel LEDs are NOT main-CPU
	// outputs (no LED write on the panel/SD I/O -- verified 2026-07-14), so we synthesise the "SD in use"
	// lamp from real card activity: each SPI byte transfer (cpsd_mbx_write) retriggers a one-shot, so the
	// LED is lit while the firmware is streaming to/from the card and drops ~250 ms after the last byte.
	output_finder<2> m_sd_leds;              // sd_led0 = SD in use; sd_led1 reserved for SD play/pause (TODO)
	emu_timer *m_sd_inuse_off = nullptr;     // one-shot: clear SD-in-use after the last SPI byte
	TIMER_CALLBACK_MEMBER(sd_inuse_off);

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
			m_maincpu->intc_icr_clear(0x1B, 0x001F);   // bit4=0: present (closed + card)
		else
			m_maincpu->intc_icr_set(0x1B, 0x0012);     // bit4=1: no card / lid open
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

	// --- SIO: three on-chip USART channels at 0x34000800 / 0x810 / 0x820 ----
	// ch0 = control panel, ch1 = MIDI port 1, ch2 = MIDI port 2 (adversarially
	// verified RE 2026-07-10; the earlier "SD sub-CPU CPSD" attribution was
	// wrong -- see notes/sd-card-emulation-plan.md). The register model
	// (config/control/TX/RX/status, sync-START instant completion, 64-byte RX
	// rings) now lives in the MN10300 CPU core (src/devices/cpu/mn10300/,
	// internal map on the core's AS_PROGRAM); the driver keeps only the
	// channel endpoints (panel HLE, MIDI UART bridges) and the INTC routing,
	// wired through the core's sio_* callbacks in kn7000(machine_config).
	enum { SIO_PANEL = 0, SIO_MIDI1 = 1, SIO_MIDI2 = 2, SIO_SD = 2 };

	// --- Control-panel HLE (the sub-CPU side of the panel serial link) ------
	// LED command bytes arrive as 2-byte [ADDR][DATA] frames on the panel TX;
	// each DATA bit is one LED of the register selected by ADDR. Buttons are
	// scanned from the ioports and reported back as 2-byte [ADDR][DATA] frames
	// on the panel RX (only delivered to the firmware once the MN10300 core
	// takes SIO interrupts -- see notes/panel-serial-protocol.md).
	// The panel-HLE frame parse / LED decode / button+analog scan now lives in
	// kn7000_cpanel_device; the driver keeps only the main-CPU SIO-transfer
	// completion (group 0x11) and the MAIN VOLUME -> DSP master-gain poll.
	TIMER_CALLBACK_MEMBER(panel_txdone_cb); // one-shot: SIO ch0 sync-transfer complete -> group 0x11
	emu_timer *m_panel_txdone = nullptr;
	TIMER_CALLBACK_MEMBER(volume_scan);     // periodic MAIN VOLUME slider -> DSP master gain
	emu_timer *m_vol_timer = nullptr;

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
	// KN2400/KN2600: 0x90000000..0x903fffff is the +0x40000000 write/execute ALIAS of the
	// 0x50000000 work RAM (the same one-bit window pair as 0x4C/0x8C and 0x44/0x84). The
	// KN2400's boot-time block loader (0x4870587E, descriptor list at 0x487965BB -- the
	// relocated twin of the KN7000's InitializeBlock27 loader) copies its ~147 KB library
	// from program ROM 0x487285BE to logical 0x50120000; the loader's `cmp 0x80000000 /
	// add 0x40000000` dest adjust makes the bytes land at 0x90120000, and the code is then
	// EXECUTED at 0x5012xxxx / builds dispatch tables into 0x5018xxxx. With 0x90000000
	// mapped as a separate "vram" share the copy went into the wrong RAM and the boot
	// called into zeroed work RAM (the long-standing KN2400 derail at 0x5018CCF4 -- see
	// notes/kn2400-boot.md). Gated to the kn2400 machine for now: the KN7000/KN6000 only
	// use this window for the IRQ trampolines+LCD regs and are already verified working
	// with the separate share (their trampoline disp math ALSO assumes this alias, so the
	// alias is probably faithful family-wide -- revisit when the LCD regs are modeled).
	if (m_ram90_workram)
		map(0x90000000, 0x903fffff).ram().share("workram");
	// 0x96800000-0x969FFFFF inside the window above is the WRITABLE custom-data FLASH
	// (IC21), not RAM. It is carved back out here -- a later map() entry overrides an
	// earlier one -- and handed to a real flash device so the firmware's erase and program
	// command sequences are decoded instead of being stored as stray bytes. Contents come
	// from the "customflash" region, which holds what the "Initial Data" disk installs.
	// See notes/initial-data-disk-and-custom-flash.md.
	// (installed at runtime in machine_start -- this map is SHARED between machines and is
	// also built during the validity check, where the device finder is not resolved, so a
	// map-time guard here silently skips the install and every access falls through to the
	// RAM window above. Same reason the rhythm name resource is installed at runtime.)

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

	// SYNTHETIC "Technics Rhythms" name resource: the "rhythms" region (kn7000 set
	// only) is installed at 0x54E00000 from machine_start(), NOT here -- this map is
	// shared with the KN6000/6500 sets which lack the region, and memregion() must
	// not run during the validity check (no machine yet -> crash). See machine_start
	// for the full rationale.

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
	// KN6000/KN6500: the firmware polls further on-chip 16-bit timer counters
	// (TMnBC at 0x340010a4+, beyond the TM4/TM5 pair the core models) as
	// busy-wait delays. Return an advancing (down-counting) value so those
	// loops progress; placeholder until TM6+ are modeled in the core. The
	// TM5BC half the boot's 0x4847b21c poll reads (0x340010a2) is the core's
	// real counter now. The KN7000 keeps the generic 0x34000000 handler.
	if (m_lib_mirror)
		map(0x340010a4, 0x340010af).lr16(NAME([this](offs_t o) { return uint16_t(-(m_maincpu->total_cycles() >> 4)); }));
	// The on-chip INTC (0x34000100-0x340002ff), SIO (panel + two MIDI channels,
	// 0x34000800-0x3400082f) and TM4/TM5 timer windows (0x34001080/0x34001090/
	// 0x340010a0) are modeled inside the MN10300 core: the core's internal
	// address map is appended AFTER this driver map (addrmap.cpp: "construct
	// the internal device map (last so it takes priority)"), so its windows
	// override the 0x34000000-wide logger above -- nothing to map here.
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
	// Floppy disk controller IC103 (C1DB00000607, N82077AA/PC-AT-compatible) at 0x98020000 -- carved out
	// of the io window above (must come AFTER it so this narrower entry wins). Confirmed by the service-
	// manual schematic (chip-select decoder IC1 = TC74VHC138F: Y2 of the 0x98000000 CS region = FDC.CS =
	// 0x98020000; Y4=0x98040000 TG fixes the base) AND by the firmware, which drives PC/AT registers here:
	// +4=DOR (boot reset seq @0x484000B5), +8=MSR/DSR, +A=data FIFO, +E=DIR/CCR (disk-change @0x48402623).
	// Data is on the D16-D23 byte lane (8-bit region) so the firmware byte-accesses these offsets directly.
	// The io window returned 0 here (the region was mislabelled "sound control"; sound is TG 0x98040000 /
	// snd 0x98060000). See notes/fdc-architecture.md addendum 15.
	map(0x98020000, 0x9802000f).rw(FUNC(kn7000_state::fdc_r), FUNC(kn7000_state::fdc_w));
	// FDC.DACK byte slot at 0x98010000 (decoder Y1). The software-DMA ISR (0x48402140), invoked per FDC.DRQ
	// (INTC group 0x18), reads/writes one FIFO byte here to feed/drain the FDC during read/write/format.
	map(0x98010000, 0x98010003).rw(FUNC(kn7000_state::fdc_dma_r), FUNC(kn7000_state::fdc_dma_w));

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
	// NOTE on bit15: it is btst-tested at 0x484A4FDA inside 0x484A4FBA (the parallel-FDC engine
	// body: movhu (0x98070000),d0 ; btst 0x8000,d0 ; ...). An earlier tick believed clearing bit15
	// would enable the floppy. That was FALSITY -- proven wrong by static + live RE (2026-07-12,
	// notes/fdc-architecture.md addendum 11): *0x484A4FBA is unreachable DEAD CODE* -- it has zero
	// callers of any kind (no call/jmp/bra target it, no absolute pointer, no task descriptor) and
	// the instruction right before it is `ret`, so it cannot be entered by fall-through either. The
	// FDC init 0x4854D835 is called ONLY from inside this dead engine (unidasm: its sole caller is
	// 0x484A4FE3). So bit15 gates nothing observable and its value is moot. The REAL floppy path is
	// the serial disk transport (0x4854BF60/BF9D via runtime driver-method pointers -> data port
	// 0x9805000C shared with SD, busy-polling handshake 0x34000170 bit4); that is what needs
	// modelling, NOT bit15 and NOT the 0x9CC00000 gate-array. Keep bit15 SET (shipped default; SD is
	// unaffected either way -- its worker task 0x4854AD90 is created unconditionally).
	if (offset == 0x38000)
	{
		// bit12 (= data-bus D28) = rear-panel MIDI IN / BASS PEDAL selector SW701 (0x484A2CB1 ->
		// 0x484b2615 reads bit12 -> MIDI-in mode flag 0x5006bfd2 bit1). bits1..2 = the TG-present
		// strap (0x484d7713): bit1 clear -> "no TG" leaves the TG-enable gate closed (silent),
		// so report the TGs present (bit1|bit2). bit15 = moot (gates dead code, see above).
		return 0x8000 | (tg_sound_enabled() ? 0x0006 : 0) | (m_rearsw->read() & 0x1000);
	}
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
			return m_kbd_fifo[m_kbd_tail++ & 63];
		return 0xFFFF;
	}
	// 0x9805000E (offset 0x28007): sound-interface register; the init loop at
	// 0x4854BC59 writes a value (d1|0x80) and spins until it READS BACK what it
	// wrote (setlb/lne with a 2-tick timeout) -- a readback latch unblocks it.
	if (offset == 0x28006)                            // 0x9805000C: SD mailbox data latch
		return m_sdmbx_out;
	if (offset == 0x28007)
		return m_snd_500e;
	// (The FDC is IC103 at 0x98020000 = decoder slot Y2; 0x98010000 = Y1 = FDC.DACK, the DMA-ack strobe,
	// not the register base -- that is why the old 0x98010000 probe never saw register traffic. The FDC
	// registers are carved out of this io window at 0x98020000-0f -> fdc_r/fdc_w.)
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
			tg_pitch_resolve(0, m_tg_addr[0]), tg_type_resolve(0, m_tg_addr[0]));
		return;
	case 0x28000: m_tg_addr[1] = data; return;                    // sub TG: address latch (0x98050000)
	case 0x28001:                                                 // sub TG: data (0x98050002) -> reg[addr]
		m_tg_reg[1][m_tg_addr[1]] = data;
		m_tonegen->tg_write(1, m_tg_addr[1], data,
			tg_pitch_resolve(1, m_tg_addr[1]), tg_type_resolve(1, m_tg_addr[1]));
		return;
	case 0x20002: case 0x20008:                                   // main TG control (0x98040004 / 0x98040010)
		return;
	}
	// (The FDC registers at 0x98020000-0f are carved out of this window -> fdc_r/fdc_w; see io_r note.)
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
				// detection only fires for PM writes issued by the SHARC itself, so tell the core:
				// notify_pm_written() flushes the recompiled cache and the newly-uploaded effect runs.
				// (This call IS live -- an earlier revision of this comment said it was disabled.)
				// Caveats (see notes/dsp-effect-execution-chain.md): a re-upload does NOT reset the
				// SHARC or clear its DM/SDRAM state, so a diverged effect tank keeps ringing across
				// program swaps; and host index writes other than 0x40/0x1C/0x04 are ignored.
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
//  On-chip interrupt controller (INTC) -- board-policy hooks only
// ============================================================================
// The INTC register model lives in the MN10300 core (mn10300.cpp intc_*). The
// board keeps three policy hooks, bound to the core's callbacks in
// kn7000(machine_config):
//  * intc_ack_cb: the panel transfer-complete (group 0x11) is level-like until
//    serviced -- the firmware's ISR-exit ack (full-word 0x0101 at 0x484AC736)
//    w1c-clears DETECT, and on real hardware the NEXT byte's completion always
//    arrives after that ack (the serial shift is slower than the ISR exit). If
//    our deferred completion landed before the ack (and was thus wiped
//    un-serviced), re-deliver it after the ack (intc_c11_ack below).
//  * intc_accept_cb: group 0x11 accepted -> the unserviced flag clears.
//  * intc_extmd_cb: panel ATN pulse, edge 2 -- the group-0x1A ISR's pass 1
//    re-arms the pin for the opposite edge (EXTMD bits 7:6: 11b -> 10b) and
//    expects the second edge of the panel's attention pulse to arrive after it
//    returns. Deferred via timer (cpanel atn_rearm): pass 1 runs with IE clear
//    and acks its DETECT on exit, so a synchronous assert would be wiped.

TIMER_CALLBACK_MEMBER(kn7000_state::dsp_audio_tick)
{
	// Audio frame tick: pulse the effects DSP's IRQ0 (the kernel's frame interrupt). We only
	// ASSERT: the SHARC core clears the pending bit when it *takes* the interrupt, so one edge
	// is delivered per tick without a matching CLEAR. IRQ0 is edge-configured by the kernel
	// (MODE2 0x18011) and its ISR (PM 0x8020) sets R13=1 to hand a frame to the main loop.
	if (!m_dsp_running)
		return;

	// F.3 audio path -- REAL TOPOLOGY (SPORT DMA-chain RE, workflow wf_b58b1fda-df3):
	// none of the DSP's TX slots feeds a DAC directly. All four SPORT TX pins loop back
	// into the TONE GENERATOR (DT0A/DT0B/DT1A/DT1B -> TG SDIE0-3); the TG mixes its
	// direct sound with the effect RETURNS (the 0x803A crossfade + 0x8338 depth we model
	// in the bridge) and drives the main DAC from its own serial out. The TX frame is a
	// per-unit I/O map: unit k's stereo return = its TX pair, its input = the same +0x20:
	//   u0 C342/43 (in C362/63)  u1 C344/45  u2 C346/47  u3 C348/49  u4 C34A/4B
	//   u5 C34C/4D  u6 C358/59   u7 C350/51  u8 C352/53  u9 C356/57
	// The TG's effect SEND enters at UNIT 0's input (C362/63) and the return the TG's
	// DAC-channel crossfade takes is UNIT 0's return (C342/43) -- the panel REVERB unit.
	// (The old I4-following heuristic parked on unit 6's slots: it fed the TG into the
	// chorus unit's input and listened to the chorus output -- one cause of the
	// reverb-ON noise, alongside the sign-extension bug fixed below.)
	constexpr uint32_t obuf = 0xC342;   // unit-0 effect RETURN (L,R) -> TG -> DAC
	constexpr uint32_t ibuf = 0xC362;   // unit-0 effect SEND input (L,R) <- TG
	{
		address_space &dm = m_dsp->space(AS_DATA);
		auto sx24 = [](uint32_t v) -> int32_t { return int32_t(v << 8) >> 8; };
		// Multi-unit routing per the LIVE-CAPTURED unit map (2026-07-20,
		// notes/dsp-unit-roles-live-capture.md -- DspEffectSelect + download-port taps):
		//   u0 = REVERB (in 0xC362/3, ret 0xC342/3)      -- wired, verified
		//   u9 = CHORUS (in 0xC376/7, ret 0xC356/7)      -- the hold-CHORUS screen's unit
		//   u1 = MULTI  (in 0xC364/5, ret 0xC344/5)      -- captured state (boot + PMEM recalls)
		//   u2..u6 = per-part Sound-DSP insert pool; RIGHT1 = u2 (in 0xC366/7, ret 0xC346/7)
		// (The previous wiring fed chorus to u4 and sound-dsp to u9 -- wrong-slot placeholders
		// from the old I4-walk inference; each was audible only because the OTHER effect's
		// algorithm happened to live there.) Feed each unit the TG send scaled by its per-part
		// send/depth level and sum its return into the DAC. GATED on send > 0 so with the
		// effect OFF this is byte-for-byte the unit-0-only path -> reverb output provably
		// unchanged (A/B bit-identical). APPROXIMATION (labelled): the whole TG mix feeds each
		// effect bus at the send level (per-part separation needs per-bus TG output); correct
		// for the common single-part case.
		// CHORUS send. A COLD panel-CHORUS toggle is announced by the firmware ONLY via the
		// CHORUS LED: the row refresh writes level 0 because the per-part depth application
		// is gated on the part-insert (SOUND DSP) flag -- full RE in the tonegen's group-0x20
		// note + notes/per-part-depth-bank.md. Model the missing depth application with the
		// part record's default CHORUS depth (0x3C) whenever the firmware's own LED says ON;
		// a firmware-written send level (insert on) always wins. With the LED off this is
		// exactly the old path (gain 0 -> branch gated).
		float chsend = m_tonegen->gain_chorus();
		if (chsend == 0.0f && m_cpanel->chorus_led())
			chsend = float(0x3C) / 127.0f;
		const float dspsend = m_tonegen->gain_dsp();   // SOUND DSP send (unit 2), same feed pattern
		const float mulsend = m_tonegen->gain_multi(); // MULTI send (unit 1), same feed pattern
		const int32_t oL = sx24(dm.read_dword(obuf));
		const int32_t oR = sx24(dm.read_dword(obuf + 1));
		int32_t cL = 0, cR = 0, dL = 0, dR = 0, mL = 0, mR = 0;
		if (chsend > 0.0f)
		{
			cL = sx24(dm.read_dword(0xC356));   // chorus (unit 9) return from last frame
			cR = sx24(dm.read_dword(0xC357));
		}
		if (dspsend > 0.0f)
		{
			dL = sx24(dm.read_dword(0xC346));   // SOUND DSP (unit 2) return from last frame
			dR = sx24(dm.read_dword(0xC347));
		}
		if (mulsend > 0.0f)
		{
			mL = sx24(dm.read_dword(0xC344));   // MULTI (unit 1) return from last frame
			mR = sx24(dm.read_dword(0xC345));
		}
		m_dspbridge->push_output(oL, oR, cL, cR, dL, dR, mL, mR);   // reverb + chorus + sound-dsp + multi
		int32_t il = 0, ir = 0, rawl = 0, rawr = 0;
		m_dspbridge->pop_input(il, ir, rawl, rawr);
		// The kernel programs the SPORTs with DTYPE=01 (SPCTL 0x013CB173/0x013C3173,
		// bits 2:1 = 01 = "right-justify; sign-extend MSBs", TRM ch.9): 24-bit samples
		// arrive SIGN-EXTENDED to 32 bits. Masking with 0xffffff (zero-fill = DTYPE 00)
		// turned every negative sample into a huge positive word (up to +2x full scale),
		// which railed every effect unit's output clip (the "reverb-ON clipped noise"
		// root cause -- first railed writer u6/rec06 @PC 0x8A4E was amplifying our own
		// poisoned input at 0xC378/79, not diverging).
		dm.write_dword(ibuf,     uint32_t(il));
		dm.write_dword(ibuf + 1, uint32_t(ir));
		if (chsend > 0.0f)
		{
			// feed the CHORUS unit (9) its send: raw TG mix scaled by the chorus send level.
			dm.write_dword(0xC376, uint32_t(int32_t(double(rawl) * chsend)));
			dm.write_dword(0xC377, uint32_t(int32_t(double(rawr) * chsend)));
		}
		if (dspsend > 0.0f)
		{
			// feed the SOUND DSP insert (unit 2 = RIGHT1): raw TG mix scaled by its send level.
			dm.write_dword(0xC366, uint32_t(int32_t(double(rawl) * dspsend)));
			dm.write_dword(0xC367, uint32_t(int32_t(double(rawr) * dspsend)));
		}
		if (mulsend > 0.0f)
		{
			// feed the MULTI unit (1): raw TG mix scaled by its send level.
			dm.write_dword(0xC364, uint32_t(int32_t(double(rawl) * mulsend)));
			dm.write_dword(0xC365, uint32_t(int32_t(double(rawr) * mulsend)));
		}
	}
	m_dsp->set_input_line(0, ASSERT_LINE);
}

TIMER_CALLBACK_MEMBER(kn7000_state::sys_tick)
{
	intc_assert(IRQGRP_TIMER);
	// (The KN6000/KN6500 ms-timer -- group 7, level 4 -- used to be HLE'd here
	// at 1 kHz; it now comes from the core's real TM5, which the KN6000 boot
	// programs itself: base 0xFA0 @0x34001092, mode 0x81 @0x34001082.)
}

// (The on-chip TEMPO timer -- TM5, the clock behind all sequenced playback --
// is modeled in the MN10300 core now: mn10300.cpp tm5_*.)

void kn7000_state::cpsd_mbx_write(uint16_t data)
{
	// SD "in use" lamp: every mailbox byte is a live SPI transfer, so the card is being accessed. Light
	// the LED and (re)arm the one-shot; a burst of bytes keeps it steady, and it drops ~250 ms after the last.
	m_sd_leds[0] = 1;
	m_sd_inuse_off->adjust(attotime::from_msec(250));

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

// SD "in use" one-shot expiry: no SPI byte for ~250 ms -> the card is idle, clear the lamp.
TIMER_CALLBACK_MEMBER(kn7000_state::sd_inuse_off)
{
	m_sd_leds[0] = 0;
}

INPUT_CHANGED_MEMBER(kn7000_state::sd_cover_changed)
{
	// The user opened or closed the SD slot cover: update the card-detect line.
	// Closing with a card in produces the insert edge (mount); opening drops
	// access so the firmware shows "ERROR 93: SD lid is open" on the SD screens.
	sd_update_carddetect();
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
//  SIO -- three on-chip USART channels (panel + two MIDI ports)
// ============================================================================
//
// The register model moved into the MN10300 CPU core (src/devices/cpu/mn10300/
// mn10300.cpp, byte-exact port of the HLE that lived here). The driver keeps
// the channel endpoints and the INTC: the core's sio_* callbacks (bound in
// kn7000(machine_config)) route TX bytes to the panel HLE / MIDI UART bridges
// and RX-ready / TX-done events to intc_assert. RX interrupt groups (ICRs:
// panel RX 0x34000168 -> group 0x10, MIDI-1 RX 0x34000148 -> 0x12, MIDI-2 RX
// 0x34000150 -> 0x14; see notes/panel-serial-protocol.md #6).


// The main-CPU SIO channel-0 sync-transfer completion (group 0x11). Deferred
// (an ISR-context write + synchronous assert is wiped by the exit ack). It is
// level-like until serviced: m_c11_unserviced clears when the group is accepted
// (the core's intc_accept_cb) and is re-delivered on the firmware's DETECT-ack
// write (the core's intc_ack_cb) if the ack raced ahead of it.
TIMER_CALLBACK_MEMBER(kn7000_state::panel_txdone_cb)
{
	m_c11_unserviced = true;
	intc_assert(0x11);
}

// CPSD (SD sub-CPU) frame delivery on SIO ch2. Simpler than the panel path: the
// firmware has already seen bit7 of the status set (cpsd_queue makes it read set)
// and enabled the ch2 RX interrupt; each timer tick clocks one byte into the ch2
// RX FIFO and fires group 0x14, which the firmware's ISR reads from +9.
[[maybe_unused]] void kn7000_state::cpsd_queue(const uint8_t *bytes, int n)
{
	// Deliver the whole frame into the ch2 RX FIFO at once; the status bits (bit7 +
	// bit4, both from the core's RxRDY) then reflect it and the firmware clocks the
	// bytes out via its bit4-gated reads of +9 (0x34000829). The core fires the ch2
	// rx-rdy callback (-> group 0x14) per byte, matching the DETECT the firmware
	// sets at 0x484b206f.
	for (int i = 0; i < n; i++)
		m_maincpu->sio_rx_push(SIO_SD, bytes[i]);
}

// Front-panel MAIN VOLUME slider -> master output gain on the final mix. A squared
// taper approximates a natural volume law (the exact analog-slider taper is unknown);
// 100 = unity, 0 = silent. Polled at 250 Hz. This is an audio-mixer control, not part
// of the CP serial protocol, so it stays in the driver; the CP-protocol analog controls
// (APC/SEQ pot, DATA dial, TEMPO knob) and all the panel buttons + LEDs are handled by
// kn7000_cpanel_device.
TIMER_CALLBACK_MEMBER(kn7000_state::volume_scan)
{
	const float v = float(m_volmain->read()) / 100.0f;
	m_dspbridge->set_master_gain(v * v);
	m_dspbridge->set_bus_gains(m_tonegen->gain_send(), m_tonegen->gain_direct(), m_tonegen->gain_return(), m_tonegen->gain_depth());
	m_dspbridge->set_effect_returns(m_tonegen->gain_dsp_ret(), m_tonegen->gain_multi_ret());

	// SD PLAY/PAUSE lamp (sd_led1): lit while SD-Audio or SD-Song playback is engaged. The play-state
	// getters GetSDAudPlay_PLAYPAUSEFunc (0x48575084) / GetSDSndPlay_PLAYPAUSEFunc (0x485756E7) read these
	// state bytes via 0x485793b8 / 0x4857b33f: 1 = playing, 2 = paused, 0 = stopped. Light on play or pause.
	address_space &prg = m_maincpu->space(AS_PROGRAM);
	const uint8_t sd_aud = prg.read_byte(0x500063e6);
	const uint8_t sd_snd = prg.read_byte(0x500063d9);
	m_sd_leds[1] = (sd_aud == 1 || sd_aud == 2 || sd_snd == 1 || sd_snd == 2) ? 1 : 0;
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

	// Front-panel BUTTON matrix (CP{board}_SEG{col}) is now declared by the control-panel
	// device itself (kn7000_cpanel_device::device_input_ports(), in kn7000_cpanel.cpp) -- the
	// panel sub-CPUs own those inputs. The layout references them as "cpanel:CP{board}_SEG{col}".

	PORT_START("DIAL")
	PORT_BIT(0xff, 0x00, IPT_DIAL) PORT_SENSITIVITY(30) PORT_KEYDELTA(1) PORT_NAME("DATA DIAL")

	// Front-panel volume sliders -- draggable placeholders (the ESQ1-style slider script in
	// kn7000.lay binds these). NOT yet wired to any audio/volume path; control targets are TBD
	// (needs schematic + disassembly RE). PORT_ADJUSTER gives a 0-100 value the layout knob animates.
	PORT_START("VOL_MAIN")   PORT_ADJUSTER(80, "Main Volume")
	PORT_START("VOL_APCSEQ") PORT_ADJUSTER(80, "APC / SEQ Volume")
	PORT_START("VOL_MIC")    PORT_ADJUSTER(50, "Mic Volume")
	PORT_START("VOL_LINEIN") PORT_ADJUSTER(50, "Line-In Volume")
	// TEMPO/PROGRAM knob: a RELATIVE encoder (wire 0x17). The adjuster value itself is meaningless to the
	// firmware -- the control-panel device (kn7000_cpanel) converts its CHANGES into [0x17, position] encoder steps. Dragging
	// the layout knob up raises the tempo, down lowers it. Centre start so there is room to drag both ways.
	PORT_START("TEMPO_KNOB") PORT_ADJUSTER(50, "Tempo / Program Knob")

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
	// bits 0-5 -> panel events 0x7020B5..0x7020BA per descriptor SEG1D @0x48613fc4).
	// bit->function from firmware RE (dispatch 0x48577ee2): bit0/1 = a plain property
	// step (VOLUME), bit2/3 = STOP/PLAY, bit4/5 drive the fwd/rew hold-timer 0x48578d3e
	// (= SKIP/SEARCH). This CORRECTS an earlier photo-based guess that had VOLUME and
	// SKIP/SEARCH swapped. Within-pair order (-/+ , <</>>, STOP/PLAY) is the best guess
	// and not yet panel-verified. Clickable in the layout artwork (kn7000.lay sd_block).
	PORT_START("CPSD_SDSW")   // SD play/vol board -- GPIO 0x9CC00008, not on the CP serial link
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SD VOLUME -")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SD VOLUME +")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SD STOP")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SD PLAY/PAUSE")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SD SKIP/SEARCH <<")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("SD SKIP/SEARCH >>")

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

	// KN2400/KN2600: a 320x240 FOUR-LEVEL GRAYSCALE panel. The firmware composites into a
	// 2bpp buffer at 0x9C800000 (stride 80 bytes, MSB-first pixel pairs, 0 = lightest).
	// Found empirically: after the 0x90-alias fix the boot paints exactly this region and
	// a 2bpp/320-wide decode shows the play screen (title bar, menus, sound-group tiles).
	if (m_lcd_kn24)
	{
		constexpr offs_t LCD24 = (0x9c800000 - 0x9c000000) / 4;
		for (int y = cliprect.top(); y <= cliprect.bottom(); y++)
		{
			uint32_t *const dst = &bitmap.pix(y);
			for (int x = cliprect.left(); x <= cliprect.right(); x++)
			{
				const offs_t k = offs_t(y) * 320 + x;                        // linear pixel index
				const uint32_t w = m_lcdbuf[LCD24 + (k >> 4)];               // 16 px per 32-bit word
				const uint8_t byte = uint8_t(w >> ((k & 0xc) << 1));         // little-endian byte within the word
				const uint8_t v = (byte >> (6 - 2 * (k & 3))) & 3;           // MSB-first 2-bit pixel
				const uint8_t g = 0xff - v * 0x55;
				dst[x] = rgb_t(g, g, g);
			}
		}
		return 0;
	}
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


// IC21, the custom-data flash at 0x96800000 -- a 16 Mbit bottom-boot part (MBM29LV160B class).
// The firmware drives it with the full AMD command set: unlock at +0xAAAA / +0x5554, autoselect
// 0x90, program 0xA0, sector erase 0x80+0x30, reset 0xF0. It refuses to program a device whose
// autoselect response is not in its own table at 0x485CF9E0, which is why the part identity here
// has to be right rather than merely plausible.
//
// The chip is 16 bits wide and the CPU bus is 32, and every firmware access is a halfword
// (movhu). Split each 32-bit slot into its two 16-bit device words rather than relying on umask,
// so the command sequences arrive at the device exactly as written.
uint32_t kn7000_state::customflash_r(offs_t offset, uint32_t mem_mask)
{
	uint32_t data = 0;
	if (ACCESSING_BITS_0_15)
		data |= m_customflash->read(offset * 2);
	if (ACCESSING_BITS_16_31)
		data |= uint32_t(m_customflash->read(offset * 2 + 1)) << 16;
	return data;
}

void kn7000_state::customflash_w(offs_t offset, uint32_t data, uint32_t mem_mask)
{
	if (ACCESSING_BITS_0_15)
		m_customflash->write(offset * 2, data & 0xffff);
	if (ACCESSING_BITS_16_31)
		m_customflash->write(offset * 2 + 1, (data >> 16) & 0xffff);
}

void kn7000_state::machine_start()
{
	// output_finders auto-resolve in this MAME version (see kn5000_cpanel) --
	// no explicit resolve() call is needed or available.

	// IC21 custom-data flash at 0x96800000, over the top of the broad RAM window. Installed
	// here rather than in the address map because the map is shared and is also constructed
	// during the validity check, when this optional device is not resolved.
	if (m_customflash)
	{
		m_maincpu->space(AS_PROGRAM).install_readwrite_handler(0x96800000, 0x969fffff,
				read32s_delegate(*this, FUNC(kn7000_state::customflash_r)),
				write32s_delegate(*this, FUNC(kn7000_state::customflash_w)));
		logerror("custom-data flash: IC21 mapped at 0x96800000\n");
	}

	save_item(NAME(m_dsp_index));
	save_item(NAME(m_dsp_dl_words));


	// Periodic control-panel button scan (the real sub-CPUs poll their matrices
	// continuously and report changes over the serial link).
	m_panel_txdone = timer_alloc(FUNC(kn7000_state::panel_txdone_cb), this);
	m_vol_timer = timer_alloc(FUNC(kn7000_state::volume_scan), this);

	// (The AM33 maskable-interrupt vectors are configured per level on the core
	// in kn7000/kn6000(machine_config) -- set_maskable_vector.)

	// SYNTHETIC "Technics Rhythms" name resource (kn7000 set only; the KN6000/6500
	// sets have no "rhythms" region, so nothing is installed for them -- runtime
	// install rather than a maincpu_mem entry because the map is shared and is also
	// constructed during the validity check, where regions don't exist).
	// 0x54E00000 is the firmware's LAST-RESORT software probe window for the rhythm
	// name resource (prober 0x4843D6DC, selector 0x4843385E). Per the Phase A
	// hardware survey (notes/table-rom-structure.md) it is NOT a real KN7000 chip
	// select -- the real resource lives on the undumped data flash -- so serving the
	// clearly-labeled synthetic container here is the honest emulator fix for the
	// "every style row says 8 Beat 1" fallback. The prober strncmps 0x54E10000
	// BEFORE 0x54E00000; that first probe lands mid-resource (image offset 0x10000
	// holds record payload, no magic -- verified), so the match lands at 0x54E00000
	// and all directory offsets resolve from the right base. Region tail beyond the
	// 0x3EB07F image is ERASEFF (reads as erased flash).
	if (memory_region *rr = memregion("rhythms"))
		m_maincpu->space(AS_PROGRAM).install_rom(0x54e00000, 0x54e00000 + rr->bytes() - 1, rr->base());

	// KN6000/KN6500: unlike the KN7000 (which self-loads its library), the
	// "library" at 0x4C000000/0x8C000000 is a bus mirror of the program ROM.
	// Populate the aliased libram from the program ROM so the boot finds it.
	if (m_lib_mirror)
		memcpy(memshare("libram")->ptr(), memregion("maincpu")->base(), memregion("maincpu")->bytes());
	m_sys_timer = timer_alloc(FUNC(kn7000_state::sys_tick), this);
	m_dsp_irq_timer = timer_alloc(FUNC(kn7000_state::dsp_audio_tick), this);
	m_sd_insert_timer = timer_alloc(FUNC(kn7000_state::sd_insert), this);
	m_sd_inuse_off = timer_alloc(FUNC(kn7000_state::sd_inuse_off), this);

	// (INTC + TM5 timer state is save_item'd by the MN10300 core now.)
	save_item(NAME(m_c11_unserviced));
	save_item(NAME(m_extmd_prev));
	// (SIO channel state is save_item'd by the MN10300 core now.)
	save_item(NAME(m_snd_500e));
	save_item(NAME(m_tg_addr));
	save_item(NAME(m_tg_reg));
}

void kn7000_state::machine_reset()
{
	// (SIO / INTC / TM5 state is cleared by the MN10300 core's device_reset,
	// which runs BEFORE this -- after-children ordering -- so the SD group-0x1B
	// re-init below lands on top of the cleared GxICR array.)

	// Effects DSP (F.2): hold the SHARC halted. The firmware host-boots it -- dsp_data_w
	// streams its program into internal memory and releases it (INPUT_LINE_HALT clear + PC
	// = entry) when the resident kernel is fully loaded. Until then it must not run (its
	// memory is empty). It is released only once the firmware finishes the host-boot upload.
	m_dsp->set_input_line(INPUT_LINE_HALT, ASSERT_LINE);
	m_dsp_running = false;
	m_dsp_dl_words = 0; m_dsp_mode = 0; m_dsp_wcnt = 0; m_dsp_cur = 0; m_dsp_dl_addr = 0;
	m_dsp_block_open = false;
	m_dsp_irq_timer->adjust(attotime::never);   // audio frame tick starts only once the kernel is loaded

	// Poll the MAIN VOLUME slider -> DSP master gain at ~250 Hz.
	m_vol_timer->adjust(attotime::from_hz(250), 0, attotime::from_hz(250));

	// System tick ~1 kHz (real rate TBD -- input clock unknown; tune later). The timer
	// interrupt dispatches (via IAGR=group<<3) to the real RTOS handler, whose context
	// save uses the AM33 F6 "udf"/DSP ops (getx etc.) -- now implemented in the core
	// (execute_f6), so this is ACTIVE and the boot is stable. (Earlier this was HELD
	// because those F6 ops were skipped and the saved context was corrupted; that is
	// resolved.) See notes/interrupt-mechanism.md ("F6 / udf extended ops").
	if (m_lib_mirror)
		// KN6000/KN6500: delay the tick past the single-threaded boot so the scheduler
		// does not preempt RTOS object creation (which derailed on an uncreated object).
		// The KN6000 ms counter is driven by the core's real TM5 now (the boot
		// programs it itself). See notes/kn6000-kn6500-boot.md.
		m_sys_timer->adjust(attotime::from_seconds(2), 0, attotime::from_hz(1000));
	else
		m_sys_timer->adjust(attotime::from_hz(1000), 0, attotime::from_hz(1000));


	// (TM5 mode/base/countdown are reset by the core's device_reset.)
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
		// the cover live (SDCOVER) to remove/insert afterwards. (Raw ICR poke via
		// the core's polled-line accessor -- deliberately no recompute, the line
		// is polled, never enabled.)
		m_maincpu->intc_icr_set(0x1B, 0x0012);
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

// ================= FDC (IC103, C1DB00000607, N82077AA-compatible) at 0x98020000 =================
// Confirmed by the SX-KN7000 service-manual schematic (chip-select decoder IC1 TC74VHC138F, page 101:
// Y2 of the 0x98000000 CS region = FDC.CS = 0x98020000) AND by the firmware, which drives the standard
// PC/AT FDC register file here. Register = (byteoffset>>1)&7 (FDC A0-A2 <- system A1-A3), on the D16-D23
// byte lane, so the firmware byte-accesses:
//   +4 = reg2 DOR  (read/write; boot does the DOR /RESET pulse @0x484000B5)
//   +8 = reg4 MSR (read) / DSR (write)
//   +A = reg5 data FIFO (command/result/data bytes)
//   +E = reg7 DIR (read: bit7 = DSKCHG / disk-change) / CCR (write: data rate)
// (regs 0/1/3/6 = SRA/SRB/TDR/reserved, not touched by this firmware.) Full RE: notes/fdc-architecture.md
// addenda 14-15. NOTE: the FDC INTRQ/DRQ are not yet wired to the MN10300 (the firmware polls MSR for the
// command/result phases); DMA for the sector data phase is still a stub -- see fdc_irq_w/fdc_drq_w.
uint8_t kn7000_state::fdc_r(offs_t off)
{
	if (!m_fdc) return 0xff;
	switch (off)
	{
	case 0x4: return m_fdc->dor_r();    // reg2 DOR
	case 0x8: return m_fdc->msr_r();    // reg4 Main Status Register
	case 0xa: return m_fdc->fifo_r();   // reg5 data FIFO
	case 0xe: return m_fdc->dir_r();    // reg7 DIR (bit7 = disk-change)
	default:  return 0xff;
	}
}

void kn7000_state::fdc_w(offs_t off, uint8_t data)
{
	if (!m_fdc) return;
	switch (off)
	{
	case 0x4: m_fdc->dor_w(data);  break;   // reg2 DOR (motor / drive-select / /RESET / DMA gate)
	case 0x8: m_fdc->dsr_w(data);  break;   // reg4 Data-rate Select Register
	case 0xa: m_fdc->fifo_w(data); break;   // reg5 data FIFO
	case 0xe: m_fdc->ccr_w(data);  break;   // reg7 Configuration Control Register (data rate)
	default: break;
	}
}

// FDC interrupt / DMA-request lines -> MN10300 on-chip INTC group 0x18 (GxICR at 0x34000160, which the
// FDC interrupt ISR 0x48402109 acknowledges). The FDC sector-data phase is SOFTWARE-DMA: the FDC asserts
// DRQ per byte -> this raises the group-0x18 interrupt -> the ISR (0x48402140) transfers one byte between
// the RAM buffer and the FDC.DACK slot at 0x98010000 (mapped to m_fdc->dma_r()/dma_w()). INTRQ (command
// complete) shares the group; the ISR dispatches by the current op. (Rising edge asserts; the ISR clears
// the GxICR REQUEST bit via its 0x34000160 write.) See notes/fdc-architecture.md addendum 18.
void kn7000_state::fdc_irq_w(int state)
{
	if (state)
		intc_assert(0x18);
}
void kn7000_state::fdc_drq_w(int state)
{
	if (state)
		intc_assert(0x18);
}
// FDC.DACK byte slot at 0x98010000 (decoder Y1). A read/write here transfers one FIFO byte to/from the
// FDC in the current DMA operation (asserts DACK); the software-DMA ISR uses it per FDC.DRQ.
uint8_t kn7000_state::fdc_dma_r(offs_t)
{
	return m_fdc ? m_fdc->dma_r() : 0xff;
}
void kn7000_state::fdc_dma_w(offs_t, uint8_t data)
{
	if (m_fdc)
		m_fdc->dma_w(data);
}

static void kn7000_floppies(device_slot_interface &device)
{
	// The KN7000 formats 1.44 MB "2HD" disks (firmware string "1.44M Byte format : 2HD" @0x25D160)
	// and also accepts 720 KB "2DD" media (firmware: '…"2HD". It can be used only "2DD" type in this
	// mode'). A 3.5" HD drive reads/writes both, so default to 35hd and offer 35dd as an option.
	device.option_add("35hd", FLOPPY_35_HD);   // 3.5" high-density (1.44 MB, the KN7000 default)
	device.option_add("35dd", FLOPPY_35_DD);   // 3.5" double-density (720 KB, 2DD media)
}

void kn7000_state::kn7000(machine_config &config)
{
	// IC21, the custom-data flash. The firmware validates the part via a JEDEC autoselect
	// against its own table, so this must be one of the accepted devices; MBM29LV160B is the
	// first entry. Being an nvram device, whatever the firmware saves here PERSISTS across
	// runs -- which is the point of modelling it rather than leaving the window as RAM.
	FUJITSU_29LV160B(config, m_customflash);

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
	m_maincpu->set_addrmap(AS_PROGRAM, &kn7000_state::maincpu_mem);

	// On-chip INTC (now modeled in the core): configure the per-level maskable
	// vectors -- the firmware installs two distinct handlers in its self-loaded
	// library: 0x4C03DDA0 = quick dispatch (no stack switch) for the device
	// levels, 0x4C03DE26 = the SCHEDULER entry, used only by the level-6 system
	// tick (see mn10300.cpp intc_recompute for why the split matters). The
	// KN6000/KN6500 override these in kn6000(machine_config) below.
	for (int level = 0; level < 8; level++)
		m_maincpu->set_maskable_vector(level, level == 6 ? 0x4C03DE26 : 0x4C03DDA0);
	// Board policy hooks out of the core INTC (see the "board-policy hooks"
	// comment block above the FDC section):
	// group 0x11 (panel transfer-complete) is level-like until serviced --
	// re-deliver a completion that was wiped un-serviced by the ISR-exit ack.
	m_maincpu->intc_ack_cb().set([this](uint8_t group) {
		if (group == 0x11 && m_c11_unserviced)
			m_panel_txdone->adjust(attotime::from_usec(40), 3);
	});
	// group 0x11 latched into the IAGR at accept -> it has been serviced.
	m_maincpu->intc_accept_cb().set([this](uint8_t group) {
		if (group == 0x11)
			m_c11_unserviced = false;
	});
	// EXTMD written: decode the panel-ATN edge re-arm transition (bits 7:6
	// 11b -> 10b) against our previous-value shadow.
	m_maincpu->intc_extmd_cb().set([this](uint16_t data) {
		const uint16_t prev = m_extmd_prev;
		m_extmd_prev = data;
		if (((prev & 0x00c0) == 0x00c0) && ((data & 0x00c0) == 0x0080))
			m_cpanel->atn_rearm();
	});

	// On-chip SIO routing (the register model lives in the core, as does the
	// INTC now; IRQ events still come OUT of the core through these callbacks
	// and are routed back into the core's INTC by group number -- the group
	// assignment is board wiring). ch0 = control panel (synchronous link):
	m_maincpu->sio_tx_done_cb<0>().set([this](int state) {
		// Sync-transfer completion -> group 0x11 -- ALWAYS deferred (an
		// ISR-context write + synchronous assert is wiped by the exit ack).
		// The core fires this before the TX-byte callback, preserving the
		// old schedule-then-tx_byte order. The level-like re-delivery
		// (m_c11_unserviced + the intc_ack_cb binding above) stays driver-side.
		m_panel_txdone->adjust(attotime::from_usec(40), 3);
	});
	// The main CPU transmits 7-byte frames with interleaved line syncs; the
	// panel HLE parses them, decodes LED writes, and queues replies.
	m_maincpu->sio_tx_cb<0>().set([this](uint8_t data) { m_cpanel->tx_byte(data); });
	// One group-0x10 interrupt per reply byte the panel delivers into the ch0
	// RX ring (the state-8 handler reads 0x34000809 per interrupt).
	m_maincpu->sio_rx_rdy_cb<0>().set([this](int state) { intc_assert(0x10); });
	// Config bit14 written set (group-0x1A ISR pass 2): the panel may now send
	// its queued reply.
	m_maincpu->sio_rx_enable_cb<0>().set([this](int state) { m_cpanel->rx_enable(); });
	// ch1/ch2 = MIDI 1 / MIDI 2: TX bytes serialize out through the UART
	// bridges below; each received byte raises the channel's RX group
	// (MIDI-1 0x12, MIDI-2 0x14 -- see notes/panel-serial-protocol.md #6).
	m_maincpu->sio_tx_cb<1>().set(m_midi_uart[0], FUNC(kn7000_sio_uart_device::write));
	m_maincpu->sio_rx_rdy_cb<1>().set([this](int state) { intc_assert(0x12); });
	m_maincpu->sio_tx_cb<2>().set(m_midi_uart[1], FUNC(kn7000_sio_uart_device::write));
	m_maincpu->sio_rx_rdy_cb<2>().set([this](int state) { intc_assert(0x14); });

	/* video hardware */
	// LCD panel. Exact geometry is uncertain: the KN7000 front-panel LCD is
	// reported as either 320x240 or 640x240. Using 640x240 as a placeholder.
	// TODO: confirm resolution, pixel clock and the LCD controller feeding
	//       the V-RAM at IC104.
	SCREEN(config, m_screen).set_lcd();
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
	// IN/OUT port pair. TX = firmware -> core SIO -> tx_cb -> UART -> MIDI OUT;
	// RX = MIDI IN -> UART -> midi_rx -> core sio_rx_push (rx-rdy raises the
	// channel's INTC group, bound above).
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

	// Control panel HLE (buttons, LEDs, analog controls) on SIO channel 0. The
	// device queues replies + button/analog events; the driver bridges its ATN
	// pulse and reply bytes to the main CPU's interrupt controller and SIO0 RX.
	KN7000_CPANEL(config, m_cpanel);
	m_cpanel->atn().set([this](int state) { if (state) intc_assert(0x1a); });
	m_cpanel->rxd().set([this](uint8_t data) { m_maincpu->sio_rx_push(SIO_PANEL, data); });
	// The panel scan-matrix button ports (CP{board}_SEG{col}) are declared by the control-panel
	// device itself now (kn7000_cpanel_device::device_input_ports()); no wiring needed here. The
	// shared front-panel analog controls stay in the driver's INPUT_PORTS and are handed over by tag:
	m_cpanel->set_dial_port(m_dial);
	m_cpanel->set_volapcseq_port(m_volapcseq);
	m_cpanel->set_tempoknob_port(m_tempoknob);

	// --- Sound (first cut): a bring-up sine synth keyed by the PC key bed, so
	//     notes are audible now. Real dual-TG PCM synthesis + effects DSP is future
	//     work (see notes/audio-output-implementation-plan.md). Shared by all the
	//     models that reuse this config; only kn7000 drops MACHINE_NO_SOUND for now.
	SPEAKER(config, "lspeaker").front_left();
	SPEAKER(config, "rspeaker").front_right();
	SPI_SDCARD(config, m_sdcard, 0);
	m_sdcard->set_prefer_sd();
	m_sdcard->spi_miso_callback().set(FUNC(kn7000_state::sd_miso_w));

	// IC103 floppy disk controller (custom C1DB00000607, N82077AA/PC-AT-compatible) + 3.5" drive.
	// Memory-mapped at 0x98020000 (schematic + firmware confirmed -- notes/fdc-architecture.md addendum
	// 15; see fdc_r/fdc_w). Full FORMAT nav: DISK=SEG0D 0x04 -> FORMAT=SEG11 0x10 -> confirm=PAGE UP ->
	// YES=SEG13 0x01. Clocked at 24 MHz (the FDC crystal on MAIN 2/5).
	N82077AA(config, m_fdc, 24'000'000);
	m_fdc->intrq_wr_callback().set(FUNC(kn7000_state::fdc_irq_w));   // FDC INTRQ (logging stub -- firmware polls MSR)
	m_fdc->drq_wr_callback().set(FUNC(kn7000_state::fdc_drq_w));     // FDC DRQ  (logging stub -- DMA not yet modelled)
	// PC floppy formats: KN7000 disks are FAT12 and "interchangeable with a PC" (standard IBM-PC MFM),
	// so use default_pc_floppy_formats -- it adds FLOPPY_PC_FORMAT (raw .img round-trip) on top of the
	// MFM containers, unlike the KN5000's default_mfm_floppy_formats which cannot load a raw PC image.
	FLOPPY_CONNECTOR(config, "fdc:0", kn7000_floppies, "35hd", floppy_image_device::default_pc_floppy_formats).enable_sound(true);

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
	ADSP21065L(config, m_dsp, 66'000'000);   // IC306 rated/run at 66 MHz (was 60 -- faithful correction)
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
	// KN6000/KN6500 interrupt vectors: ALL maskable IRQs go to the firmware-
	// built trampoline slot 0 (0x90000000 -> the general handler, which reads
	// the latched group at 0x34000200 and dispatches). Slot 1 (0x90000006 ->
	// 0x4847b19d) is the EXCEPTION/fault handler (disables IRQs + halts), NOT
	// an IRQ dispatch -- routing IRQs there halts the boot (was the 0x4847b238
	// hang). See notes/kn6000-kn6500-boot.md.
	for (int level = 0; level < 8; level++)
		m_maincpu->set_maskable_vector(level, 0x90000000);

	// The KN6000/KN6500 front panel speaks the SAME CP wire protocol as the KN7000 (which is
	// why these models already accepted button traffic, and why their TEMPO/PROGRAM wheel
	// worked, while running the KN7000 panel) -- but its MATRIX is almost entirely different:
	// 88% of its populated button cells carry a different function than the KN7000 cell at the
	// same seg/bit. Swap in the model's own panel so every button does what its silk says.
	// The KN6000/KN6500 tone generator: ONE `D82398GD001` (IC213) with 64 voice slots
	// behind the single 0x98050000 window, in place of the KN7000's two
	// `C1BB00000709`. Same voice model, different register numbering -- recovered from
	// the firmware's own note-on register blit at 0x484948CB; see kn6000_tonegen.h and
	// notes/kn6000-tonegen-spec.md. The audio routing is inherited from kn7000()
	// above, so only the decode changes.
	config.device_remove("tonegen");
	KN6000_TONEGEN(config, m_tonegen, 0);
	m_tonegen->add_route(0, *m_dspbridge, 1.0, 0);
	m_tonegen->add_route(1, *m_dspbridge, 1.0, 1);
	// ...and the driver-side bindings the resolves need: the KN6000's library voice
	// record array, its single-chip slot map, and its pitch register class.
	m_tg_recbase    = 0x5027AF28;      // vs the KN7000's 0x500AF940 (same 0xB4 stride);
	                                   // the per-SLOT copy, not the library array (see above)
	m_tg_one_chip   = true;            // 64 slots, one window, no chip select
	m_tg_pitch_cls  = 0x5000;          // plane 0x14 (KN7000: 0x2400)
	m_tg_pitch_mask = 0xFC00;          // class low nibble carries pitch bits 16-17

	config.device_remove("cpanel");
	KN6000_CPANEL(config, m_cpanel);
	m_cpanel->atn().set([this](int state) { if (state) intc_assert(0x1a); });
	m_cpanel->rxd().set([this](uint8_t data) { m_maincpu->sio_rx_push(SIO_PANEL, data); });
	m_cpanel->set_dial_port(m_dial);
	m_cpanel->set_volapcseq_port(m_volapcseq);
	m_cpanel->set_tempoknob_port(m_tempoknob);

	// ...and its OWN artwork.  Installing the matrix alone was not enough: the default layout was
	// still layout_kn7000, so every clickable element on screen sat at a KN7000 position, carried a
	// KN7000 legend and pointed at a KN7000 matrix cell -- clicking the artwork's "PIANO" sent the
	// KN7000's PIANO cell, which is a different function here.  layout_kn6000 draws this panel from
	// the SX-KN6000 service manual's own "Controls and functions" panel drawing (pp.5-6) and binds
	// every button to the cell its silkscreen actually means.  See tools/gen_kn6000_lay.py.
	config.set_default_layout(layout_kn6000);
}

// The KN6500 is the KN6000 machine with a different firmware BUILD. Same hardware
// (one D82398GD001 tone generator, same 64 voices, same register numbering), but the
// build's RAM layout shifted, so the driver-side voice-record binding has to follow it:
// the per-TG-slot voice record sits at 0x5027AF1C rather than the KN6000's 0x5027AF28.
// Both were located the same way, by the firmware's own note-on record copy (a 0x2D-word
// block copy preceded by the destination base -- KN6000 at 0x48492F3D, KN6500 at
// 0x48492E07), so this is a measured address, not an offset guess.
void kn7000_state::kn6500(machine_config &config)
{
	kn6000(config);
	m_tg_recbase = 0x5027AF1C;
}

// KN2400/KN2600 reuse the KN7000 machine, but their firmware self-loads its library
// into WORK RAM at 0x50120000 through the 0x90000000 (+0x40000000) alias window, so
// that window must alias work RAM instead of being a separate share (see maincpu_mem).
void kn7000_state::kn2400(machine_config &config)
{
	kn7000(config);
	m_ram90_workram = true;
	m_lcd_kn24 = true;
	// 320x240 4-level grayscale LCD (2bpp framebuffer at 0x9C800000).
	m_screen->set_size(320, 240);
	m_screen->set_visarea(0, 320 - 1, 0, 240 - 1);
	// Like the KN6000, the KN2400 firmware builds its own interrupt trampoline
	// table; route all maskable IRQs to trampoline slot 0 rather than the
	// KN7000's library handler addresses (which don't exist on this firmware).
	for (int level = 0; level < 8; level++)
		m_maincpu->set_maskable_vector(level, 0x90000000);
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
	// SYNTHETIC wave pack (optional): donor samples from the GENUINE KN5000 IC307 dump,
	// keyed by the runtime (bank,zone) sample select -- built by tools/make_wave_pack.py,
	// clearly labeled NOT-A-DUMP (embedded provenance block). When absent the tone
	// generator falls back to the sine placeholder. Rebuild + update hashes with the tool.
	ROM_REGION(0x1000000, "wavepack", ROMREGION_ERASE00)
	ROM_LOAD_OPTIONAL("kn7000_waves_synthetic.rom", 0x000000, 0x1000000, BAD_DUMP CRC(bc94e4ba) SHA1(66543485ac7ba53126a765168555b525b38d87b2))

	// SYNTHETIC "Technics Rhythms" style-name resource (optional) -- built by
	// tools/gen_technics_rhythms.py, NOT a dump (hence BAD_DUMP). The real ~4.1MB
	// rhythm-data flash (IC21 factory flash / IC18+IC20 custom flash per
	// notes/table-rom-structure.md) is UNDUMPED; without a resource the firmware's
	// name resolver falls back to its count=1 program-ROM stub and every style row
	// renders as "8 Beat 1". This container is deterministic from the two dumped
	// ROMs: the REAL intact directory prefix (a born-truncated copy survives in the
	// table flash at 0x483E828C), the REAL 8 aux records + record-0 payload from the
	// program-ROM stub, and REAL names for the 52 styles resolved via the intact
	// secondary catalog (table flash 0x48244F78). The remaining 168 factory display
	// names existed only on the undumped flash and are UNRECOVERABLE until it is
	// dumped: they are emitted as self-announcing placeholders ("BALLAD 04 ?" --
	// genre/slot from the byte-verified reverse map at 0x48734EE4). Mapped at the
	// firmware's last-resort probe window 0x54E00000 (see maincpu_mem).
	ROM_REGION32_LE(0x400000, "rhythms", ROMREGION_ERASEFF)
	ROM_LOAD_OPTIONAL("kn7000_rhythms_synthetic.rom", 0x000000, 0x3eb07f, BAD_DUMP CRC(1fff54c5) SHA1(c6c9615c40745096b436ec98e9c61d83295b7ebb))

	// IC21, the writable custom-data flash at 0x96800000 (2 MB, 16 Mbit bottom boot).
	// NOT a chip dump: this is the payload the "Initial Data" disk installs, which the
	// firmware inflates and writes VERBATIM to flash offset 0x20000 -- the top 30 of the
	// 64 KiB sectors. Nothing is written below that, so the boot sectors stay erased.
	// Installed into the window at machine_start; see machine_start() and
	// notes/initial-data-disk-and-custom-flash.md.
	// Region tag must match the device tag -- intelfsh loads its initial contents from the
	// region named after itself. It must be *_BE: for a 16-bit part nvram_default() stores
	// each region word big-endian while read_raw() reassembles little-endian, so declaring
	// this LE would byte-swap every halfword the firmware reads.
	ROM_REGION16_BE(0x200000, "customflash", ROMREGION_ERASEFF)
	// The Initial Data Disk is FOUR files, each installed to its own flash region -- not one
	// payload at one offset. Three of them (MD/FAV/HMP) carry the ASCII signature "JK " that
	// the boot validation at 0x487DCE9A compares against a ROM template (0x4858D730); with
	// that signature absent the firmware sets an error bit at 0x5001602C and falls back to
	// defaults everywhere, which is why the style list, Favorites and Custom came up empty.
	//
	// Each region is validated against its own blank TEMPLATE in program ROM, and those
	// templates identify the files: comparing the first 16 bytes gives 16/16 for UMDINI
	// (0x48617638), 16/16 for FAVINI (0x48605728) and 15/16 for HPGINI (0x485F9584 -- the
	// template is the empty variant, differing only in a count field). The chip address each
	// template is checked against is then read straight out of the code:
	//   0x004000  02UMDINI.MD  header 0x10 + 0xC0 + 3 x 0x90 = 0x280, its exact size, and the
	//                          referenced offsets 0x4010/0x40D0/0x4160/0x41F0/0x4280
	//   0x010000  03FAVINI.FAV compared at 0x4849EDC0
	//   0x011000  04HPGINI.HMP compared at 0x48496F60
	//
	// These three use ROM_GROUPWORD|ROM_REVERSE (i.e. a word swap) plus ROM_OPTIONAL -- they
	// are user data and the machine must still boot without them. Measured against the firmware's own read, a plain
	// ROM_LOAD into this _BE region delivers every 16-bit word reversed (the signature came
	// back as "KJ", byte 0x4000 reading 0x4B where 0x4A is required). CTMINI below is
	// unaffected and stays a plain ROM_LOAD.
	ROMX_LOAD("kn7000_umdini.rom",      0x004000, 0x000280, CRC(f36352d3) SHA1(f5693ab1f1d986dfd7af2776c862af45b0a69488), ROM_GROUPWORD | ROM_REVERSE | ROM_OPTIONAL)
	ROMX_LOAD("kn7000_favini.rom",      0x010000, 0x000198, CRC(959fdc3c) SHA1(93ae80f5ba737c229cb93edc1e3f3d630bba5599), ROM_GROUPWORD | ROM_REVERSE | ROM_OPTIONAL)
	ROMX_LOAD("kn7000_hpgini.rom",      0x011000, 0x004442, CRC(d56caae3) SHA1(931b35afe46942744b37abb64898c4524fe75a6f), ROM_GROUPWORD | ROM_REVERSE | ROM_OPTIONAL)
	ROM_LOAD_OPTIONAL("kn7000_custom_data.rom", 0x020000, 0x1e0000, CRC(2a133ea7) SHA1(67b2a0fe8154c4d15557399a86bf0d0b49813ced))

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
//
// !!! THE "table" REGION BELOW HOLDS THE **KN7000's** TABLE/FONT ROM
// !!! CONTENTS, LOADED AS A BAD_DUMP **PLACEHOLDER**.
// The KN6000/KN6500's OWN table/font mask ROMs -- IC13 (QSIGX3C16008)
// and IC14 (QSIGX3C16007) on the KN6000, C3FBMD000069/C3FBMD000068 on
// the KN6500 -- are UNDUMPED and still need a hardware read. That read
// is the only real fix; everything here is a usability stopgap.
// WHY: the font-table initialiser at 0x48420312 copies five font-
// descriptor pointers straight out of the table-ROM header at
// 0x48000200..0x48000210. With nothing valid there the text drawer
// (which runs 40x per boot, correctly gated) computes a garbage
// descriptor and blits nothing -- the KN6000/KN6500 render NO TEXT at
// all. Feeding the KN7000's table ROM makes the whole text subsystem
// come alive on the KN6000 -- its play screen now shows "PMEM: A-",
// "8 Beat 1", the tempo, the part names and every voice name (first
// predicted by the injection experiment written up in
// notes/kn6000-kn6500-boot.md, then confirmed live). The KN6500 does
// not benefit yet -- see the note in ROM_START(kn6500).
// CAVEAT -- READ THIS BEFORE CITING ANYTHING ON SCREEN: the glyphs and
// any other table-derived content displayed by kn6000/kn6500 are the
// KN7000's data, NOT the KN6000/KN6500's own. They must NOT be treated
// as KN6xxx-authentic (fonts, and anything else this ROM feeds, may
// legitimately differ between the models). This is exactly why the
// entries carry BAD_DUMP.
// ERRATUM: until 2026-07-20 this region instead carried four ROM_LOADs
// of kn6xxx_table_even/odd.rom, which were themselves a placeholder and
// not a dump -- verified byte-for-byte that their low 1 MB was exactly
// the program ROM's upper 1 MB (the region reproduced program bytes
// 0x200000..0x3fffff, i.e. IK2/IKV2 loaded a second time) and their
// upper 1 MB was all 0xFF. Those had no emulation effect whatsoever
// (blanking the region to 0xFF gave a byte-identical screen) while
// wrongly implying that IC13/IC14 had been dumped.
// ===================================================================
ROM_START(kn6000)
	ROM_REGION32_LE(0x400000, "maincpu", ROMREGION_ERASEFF)   // program IC12/IC11 (IK1) -> 0x48400000
	ROM_LOAD32_WORD("kn6000_program_even.rom", 0x000000, 0x200000, CRC(56c2cfe3) SHA1(e15a4c73440f1dcdf06457f9956c96bf20d68b16))
	ROM_LOAD32_WORD("kn6000_program_odd.rom",  0x000002, 0x200000, CRC(9d94da6c) SHA1(d73b4c8ebf0c67b6a2eeb5571d0273fc6efbfe4c))
	// Table/font mask ROM -> 0x48000000. The KN6000's own IC13 (QSIGX3C16008) and
	// IC14 (QSIGX3C16007) are UNDUMPED; these are the KN7000's table ROM files used
	// as a BAD_DUMP placeholder so that text renders. See the block comment above.
	ROM_REGION32_LE(0x400000, "table", ROMREGION_ERASEFF)
	ROM_LOAD32_WORD("kn7000_table_even.rom", 0x000000, 0x200000, BAD_DUMP CRC(005a6db2) SHA1(2f4112ea9b039b17b5ada6952b7646adae8d9dd6))
	ROM_LOAD32_WORD("kn7000_table_odd.rom",  0x000002, 0x200000, BAD_DUMP CRC(7e1a312e) SHA1(435b597b926ebac56d4710bcae25b635a59a9ce5))
	// ...except the first 0x200 bytes, which must stay blank. Measured: with the
	// KN7000's table-ROM identity header in place the KN6000 boot follows it and
	// derails to a permanently BLACK screen (verified through 40 s of emulated time);
	// blanking exactly 0x000000..0x0001FF and leaving the rest gives the full play
	// screen WITH text. The font-descriptor pointer block the KN6000's font init
	// reads starts at 0x200, just past this fill, and is preserved. This fill is part
	// of the placeholder, and is another reason these entries are BAD_DUMP -- a real
	// IC13/IC14 dump will need no such surgery.
	ROM_FILL(0x000000, 0x000200, 0xff)
ROM_END

ROM_START(kn6500)
	ROM_REGION32_LE(0x400000, "maincpu", ROMREGION_ERASEFF)   // program IC12/IC11 (IKV1) -> 0x48400000
	ROM_LOAD32_WORD("kn6500_program_even.rom", 0x000000, 0x200000, CRC(f42a2fcf) SHA1(7cebf73bf623fd714ca455ed50b80da1d2186414))
	ROM_LOAD32_WORD("kn6500_program_odd.rom",  0x000002, 0x200000, CRC(ca2a733f) SHA1(2484d3b76b62b05ded39e4194cdc74fd3c01bcbe))
	// Table/font mask ROM -> 0x48000000. The KN6500's own IC13/IC14
	// (C3FBMD000069 / C3FBMD000068) are UNDUMPED; same KN7000 BAD_DUMP placeholder
	// as the KN6000 above -- anything it renders is the KN7000's data, not the
	// KN6500's. See the block comment above.
	// STATUS (measured 2026-07-20): unlike the KN6000, the KN6500 does NOT yet gain
	// text from this placeholder -- its play screen looks exactly the same with the
	// region loaded, blanked, or with the 0x200 header left intact. So its font path
	// diverges from the KN6000's (different font init / descriptor pointer global)
	// and still has to be traced. The entry is kept because the chips and the
	// situation are the same, and it is the region that trace will need; it is NOT
	// claimed to fix the KN6500. No regression either: the screen is unchanged.
	ROM_REGION32_LE(0x400000, "table", ROMREGION_ERASEFF)
	ROM_LOAD32_WORD("kn7000_table_even.rom", 0x000000, 0x200000, BAD_DUMP CRC(005a6db2) SHA1(2f4112ea9b039b17b5ada6952b7646adae8d9dd6))
	ROM_LOAD32_WORD("kn7000_table_odd.rom",  0x000002, 0x200000, BAD_DUMP CRC(7e1a312e) SHA1(435b597b926ebac56d4710bcae25b635a59a9ce5))
	ROM_FILL(0x000000, 0x000200, 0xff)   // see the KN6000 note above: identity header must stay blank
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
	// No table ROM is loaded here -- and, unlike the KN6000/KN6500 above, no
	// placeholder ever was (checked 2026-07-20): the region has always been left
	// empty. The KN2400 boot reads NOTHING from 0x48000000-0x483fffff (read-tap
	// verified, notes/kn2400-boot.md), so whether this family even has a separate
	// table/mask ROM is still undetermined; no chip is claimed as dumped.
	ROM_REGION32_LE(0x400000, "table", ROMREGION_ERASEFF)
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
SYST(2000, kn6000, 0,      0,      kn6000,  kn7000, kn7000_state, empty_init, "Technics", "SX-KN6000", MACHINE_NOT_WORKING | MACHINE_IMPERFECT_SOUND)
// KN6500: MACHINE_NO_SOUND, deliberately, even though it carries the same (correct) tone
// generator as the KN6000. Its firmware emits ZERO tone-generator writes on a key-bed press
// (live-probed), so its voice engine never starts -- a boot/enable-gate difference from the
// KN6000, not a decode problem. The device and its voice-record binding are in place and
// ready for the moment that gate is found; until then claiming sound would be a lie.
SYST(2001, kn6500, 0,      0,      kn6500,  kn7000, kn7000_state, empty_init, "Technics", "SX-KN6500", MACHINE_NOT_WORKING | MACHINE_NO_SOUND)

// KN2400 / KN2600 -- MN10300/MILK siblings sharing one firmware image (kn2600 = clone of kn2400).
SYST(1998, kn2400, 0,      0,      kn2400,  kn7000, kn7000_state, empty_init, "Technics", "SX-KN2400", MACHINE_NOT_WORKING | MACHINE_NO_SOUND)
SYST(2000, kn2600, kn2400, 0,      kn2400,  kn7000, kn7000_state, empty_init, "Technics", "SX-KN2600", MACHINE_NOT_WORKING | MACHINE_NO_SOUND)

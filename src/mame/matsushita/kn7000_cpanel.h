// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    KN7000 control panel HLE

    High-level emulation of the KN7000 front-panel sub-CPUs (one per panel
    PCB) that scan the button matrices and analog controls and drive the panel
    LEDs, talking to the main MN10300 over a synchronous serial link (channel
    0 of the SIO ASIC).

    Unlike the KN5000's bit-level link, the KN7000 main CPU delivers whole
    bytes to this device (one per SIO transfer). The device parses the 7-byte
    TX frames, decodes LED-register writes, and pushes button/analog/handshake
    replies back to the main CPU via the panel ATN pulse and the SIO-channel-0
    receive interrupt.

    Protocol: notes/panel-serial-protocol.md

***************************************************************************/

#ifndef MAME_MATSUSHITA_KN7000_CPANEL_H
#define MAME_MATSUSHITA_KN7000_CPANEL_H

#pragma once

class kn7000_cpanel_device : public device_t
{
public:
	kn7000_cpanel_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock = 0);

	// The button scan-matrix ports (CP{board}_SEG{col}) are OWNED by this device --
	// declared in device_input_ports() and bound by tag in the constructor (see the
	// .cpp). The shared front-panel analog controls the panel also scans stay in the
	// driver's INPUT_PORTS (the layout faders / audio path reference them too) and are
	// handed to this device by tag via the setters below.
	template <typename T> void set_dial_port(T &&tag) { m_dial.set_tag(std::forward<T>(tag)); }
	template <typename T> void set_volapcseq_port(T &&tag) { m_volapcseq.set_tag(std::forward<T>(tag)); }
	template <typename T> void set_tempoknob_port(T &&tag) { m_tempoknob.set_tag(std::forward<T>(tag)); }

	// Callbacks to the main CPU (its interrupt controller / SIO channel 0):
	auto atn() { return m_atn_cb.bind(); }   // panel ATN pulse -> main asserts INTC group 0x1A
	auto rxd() { return m_rxd_cb.bind(); }    // one reply byte -> main pushes it onto SIO0 RX + asserts group 0x10

	// From the main CPU (SIO / INTC bridge):
	void tx_byte(uint8_t data);   // main CPU wrote one panel TX byte (SIO ch0 +8)
	void rx_enable();             // main CPU set SIO ch0 RX-enable (config bit14): clock out the next reply byte
	void atn_rearm();             // group-0x1A ISR re-armed EXTMD (11b->10b): deliver ATN edge 2

	// Firmware-authoritative global-effect ON state, read from the LED frames the firmware
	// itself sends (CPR bank reg 0x03: MULTI = D1054 bit4, CHORUS = D1082 bit5). The driver's
	// DSP bridge uses these as the effect-enable gate for the cold-toggle case where the
	// firmware announces the state ONLY via the LED (see kn7000.cpp's group-0x20 notes).
	bool chorus_led() const { return m_chorus_led; }
	bool multi_led() const { return m_multi_led; }

protected:
	// device_t overrides
	virtual void device_start() override ATTR_COLD;
	virtual void device_reset() override ATTR_COLD;
	virtual ioport_constructor device_input_ports() const override ATTR_COLD;   // the CP{board}_SEG{col} button matrix

	TIMER_CALLBACK_MEMBER(panel_event);   // deferred ATN edge / RX-byte delivery
	TIMER_CALLBACK_MEMBER(panel_scan);    // periodic button + analog scan

private:
	// Decode one [ADDR][DATA] LED-register frame onto the panel LED outputs.
	void panel_led_frame(uint8_t addr, uint8_t data);
	// Append panel->main reply bytes and kick the ATN delivery dance if idle.
	void panel_queue(const uint8_t *bytes, int n);

	// Serial frame parse (7-byte TX frames from the main CPU).
	int     m_panel_pos;                   // position within the 7-byte TX frame
	uint8_t m_panel_p1, m_panel_p2;        // frame payload bytes (positions 2 and 4)

	// Response queue (panel -> main).
	uint8_t m_panel_resp[64];              // pending panel->main bytes (replies + button events)
	int     m_panel_resp_len, m_panel_resp_pos;

	// Timers.
	emu_timer *m_panel_evt;                // one-shot; param: 1=ATN edge, 2=deliver RX byte
	emu_timer *m_panel_timer;              // periodic button/analog scan

	// Input scan state.
	uint8_t m_btn_prev[0x21];              // last scanned state, one per normSeg 0x00-0x20
	uint8_t m_vol_apcseq_prev;             // last DATA byte for the APC/SEQ pot
	bool    m_vol_apcseq_synced;           // false until the first scan records the pot (no startup frame)

	// Global-effect LED shadow (set in panel_led_frame; see chorus_led()/multi_led()).
	bool    m_chorus_led = false;          // D1082 CHORUS (cpr_led29)
	bool    m_multi_led  = false;          // D1054 MULTI (cpr_led28)
	uint8_t m_dial_prev;                   // last IPT_DIAL position delivered for the DATA dial (wire 0x10)
	bool    m_dial_synced;                 // false until the first scan records the dial (no startup frame)
	uint8_t m_tempoknob_prev;              // last adjuster value seen (for the signed per-scan delta, wire 0x17)
	bool    m_tempoknob_synced;            // false until the first scan records the knob (no startup frame)
	ioport_field *m_tempoknob_field;       // the TEMPO_KNOB adjuster field (read RAW, bypassing analog interp)

	// Callbacks to the main CPU.
	devcb_write_line m_atn_cb;
	devcb_write8     m_rxd_cb;

	// Button scan-matrix ports -- OWNED by this device (declared in device_input_ports(),
	// bound by tag in the constructor). One per physical board SEG column.
	optional_ioport_array<22> m_phys;      // CP{board}_SEG{col}
	// Shared analog panel controls (set by the main driver via the set_*_port() helpers above).
	optional_ioport m_dial;                // DATA dial (rotary encoder, wire 0x10)
	optional_ioport m_volapcseq;           // APC/SEQ VOLUME slider (wire 0xD2)
	optional_ioport m_tempoknob;           // TEMPO/PROGRAM knob (relative encoder, wire 0x17)

	// LED outputs (the three panel PCBs: left / center / right).
	output_finder<512> m_cpl_leds;
	output_finder<64>  m_cpc_leds;
	output_finder<512> m_cpr_leds;
};

DECLARE_DEVICE_TYPE(KN7000_CPANEL, kn7000_cpanel_device)

#endif // MAME_MATSUSHITA_KN7000_CPANEL_H

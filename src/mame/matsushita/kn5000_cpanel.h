// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    KN5000 control panel HLE

    Emulates the two Mitsubishi M37471M2196S MCUs on the control panel.
    Since no ROM dumps are available, this uses High Level Emulation based
    on reverse engineering of the main CPU firmware protocol.

    Protocol documentation: https://felipesanches.github.io/kn5000-docs/control-panel-protocol/

***************************************************************************/

#ifndef MAME_MATSUSHITA_KN5000_CPANEL_H
#define MAME_MATSUSHITA_KN5000_CPANEL_H

#pragma once

#include <queue>

class kn5000_cpanel_device : public device_t
{
public:
	kn5000_cpanel_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock = 0);

	// The button scan-matrix ports (CP{L,R}_SEG{col}) are OWNED by this device -- declared in
	// device_input_ports() and bound by tag in the constructor (see the .cpp), not wired by the
	// driver. The layout references them as "cpanel:CP{L,R}_SEG{col}".

	// Configuration
	void set_baudrate(uint16_t br);

	// Callbacks to main CPU
	auto txd() { return m_txd_cb.bind(); }
	auto sclk_out() { return m_sclk_out_cb.bind(); }
	auto inta() { return m_inta_cb.bind(); }

	// Serial interface from main CPU
	void rxd(int state);
	void sioclk(int state);
	void tx_start(int state);  // Called when CPU starts a new byte transmission

protected:
	// device_t overrides
	virtual void device_start() override ATTR_COLD;
	virtual void device_reset() override ATTR_COLD;
	virtual ioport_constructor device_input_ports() const override ATTR_COLD;   // the CP{L,R}_SEG{col} button matrix

	TIMER_CALLBACK_MEMBER(timer_callback);
	TIMER_CALLBACK_MEMBER(idle_detect_callback);
	TIMER_CALLBACK_MEMBER(self_clock_callback);
	TIMER_CALLBACK_MEMBER(button_scan_callback);

private:
	// Serial communication
	void send_byte(uint8_t data);
	void process_received_byte(uint8_t data);
	void process_command();

	// Response generation
	void send_sync_packet();
	void send_button_packet(int segment, bool is_left_panel);
	int32_t encoder_delta(optional_ioport &port, int32_t &prev, bool &synced, int32_t modulus);
	void send_encoder_packet(int8_t detents);
	void send_all_button_states(bool is_left_panel);

	// LED control
	void process_led_command(uint8_t row, uint8_t data);

	// Read button state from input ports
	uint8_t read_button_segment(int segment, bool is_left_panel);
	uint8_t read_status_register();

	// Timers
	emu_timer *m_timer;
	emu_timer *m_idle_detect_timer;
	emu_timer *m_self_clock_timer;
	emu_timer *m_button_scan_timer;
	uint16_t m_baud_rate;

	// Serial RX state
	uint8_t m_rx_clock_count;
	uint8_t m_rx_shift_register;
	uint8_t m_rxd;
	uint8_t m_sioclk_state;

	// Serial TX state
	uint8_t m_tx_clock_count;
	uint8_t m_tx_shift_register;
	std::queue<uint8_t> m_tx_queue; // FIXME: this breaks save state support
	bool m_tx_skip_first_falling;  // Skip first falling edge after pre-outputting bit 0

	// Command buffer (2-byte commands)
	uint8_t m_cmd_buffer[2];
	uint8_t m_cmd_index;

	// Protocol state
	bool m_initialized;
	bool m_self_clocking;
	bool m_inta_asserted;
	bool m_accept_next_byte;   // false = next received byte is phantom (PFFC-off), skip it
	bool m_tx_output_enabled;  // false = suppress TX output during phantom byte clock edges
	bool m_next_accept;        // Deferred accept_next_byte (applied at next byte boundary)
	bool m_next_tx_output_enabled;  // Deferred tx_output_enabled (applied at next byte boundary)
	bool m_rx_waiting_for_start;    // Ignore RX edges until next tx_start
	uint8_t m_self_clock_bytes_sent;  // Bytes sent in current INTA cycle
	uint8_t m_last_button_state[22];  // 11 segments * 2 panels (confirmed)
	uint8_t m_pending_button_state[22];  // Per-segment confirmation buffer

	// Callbacks
	devcb_write_line m_txd_cb;
	devcb_write_line m_sclk_out_cb;
	devcb_write_line m_inta_cb;

	// Button scan-matrix ports -- OWNED by this device (declared in device_input_ports(),
	// bound by tag in the constructor). Left / right panel PCB, segments 0-10.
	optional_ioport_array<11> m_cpl_ports;
	optional_ioport_array<11> m_cpr_ports;

	// Program data wheel (rotary encoder next to the LCD) -- also owned by this device.
	// TWO controls feed one wheel, because no single MAME field can serve both routes: an
	// analog field's only Lua write path is set_value(), which latches m_use_adjoverride
	// permanently and detaches the field from the input system, while user_value writes are
	// ignored on anything that is not an IPT_ADJUSTER (ioport.cpp:1048). So the keys get a
	// positional and the layout's pointer drag gets an adjuster, and the device sums them.
	optional_ioport m_encoder_port;        // IPT_POSITIONAL: keys and the mouse axis
	optional_ioport m_encoder_drag_port;   // IPT_ADJUSTER: the layout's circular drag only
	int32_t m_encoder_prev;        // last position seen, for the wrap-aware per-scan delta
	int32_t m_encoder_drag_prev;   // ditto for the drag control
	bool    m_encoder_synced;      // false until the first scan adopts the knob (no startup detent)
	bool    m_encoder_drag_synced;
	// Segment 0x0B's status byte. DELIBERATELY always 0: a wheel at rest is idle, and header
	// 0xCB maps to value-translation index 0x1F = invalid, so segment 0x0B provably cannot
	// produce an input record. The wheel reports through send_encoder_packet() instead.
	uint8_t m_encoder_latch;

	// Main-CPU handle used to deposit the wheel's scan-table entry into DRAM 0x8E94.
	// The real panel wheel is read by the firmware's main-loop poll Encoder_ValueScanAndSync
	// (not the CP serial protocol); this finder lets the HLE emit that entry directly.
	// Absolute ":maincpu" tag resolves from the machine root -- see the .cpp for the full
	// rationale and side-quests/findings/kn5000_data_wheel_findings.md.

	// LED outputs
	output_finder<50> m_cpl_leds;  // Left panel LEDs (CPL_0 through CPL_49)
	output_finder<69> m_cpr_leds;  // Right panel LEDs (CPR_0 through CPR_68)
};

DECLARE_DEVICE_TYPE(KN5000_CPANEL, kn5000_cpanel_device)

#endif // MAME_MATSUSHITA_KN5000_CPANEL_H

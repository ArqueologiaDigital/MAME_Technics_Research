// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    KN7000 control panel HLE

    Like the KN5000, the KN7000 front panel is driven by dedicated panel
    sub-CPUs -- one per panel PCB -- that scan the button matrices and drive
    the LEDs, and talk to the main MN10300 over a synchronous serial link.
    The main CPU delivers whole bytes on SIO channel 0; this device parses the
    7-byte TX frames, decodes the LED-register writes, and replies with
    handshake / button-event / analog-controller packets that ride back to the
    firmware via the panel ATN pulse and the SIO0 receive interrupt.

    Protocol: notes/panel-serial-protocol.md

***************************************************************************/

#include "emu.h"
#include "kn7000_cpanel.h"

#define LOG_COMMANDS (1U << 1)
#define LOG_SERIAL   (1U << 2)
#define LOG_BUTTONS  (1U << 3)
#define LOG_LEDS     (1U << 4)

#define VERBOSE 0
#include "logmacro.h"

DEFINE_DEVICE_TYPE(KN7000_CPANEL, kn7000_cpanel_device, "kn7000_cpanel", "KN7000 Control Panel HLE")

kn7000_cpanel_device::kn7000_cpanel_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock) :
	device_t(mconfig, KN7000_CPANEL, tag, owner, clock),
	m_panel_pos(0),
	m_panel_p1(0),
	m_panel_p2(0),
	m_panel_resp_len(0),
	m_panel_resp_pos(0),
	m_panel_evt(nullptr),
	m_panel_timer(nullptr),
	m_vol_apcseq_prev(0),
	m_vol_apcseq_synced(false),
	m_dial_prev(0),
	m_dial_synced(false),
	m_tempoknob_pos(0),
	m_tempoknob_prev(0),
	m_tempoknob_synced(false),
	m_atn_cb(*this),
	m_rxd_cb(*this),
	m_seg(*this, finder_base::DUMMY_TAG, 0U),
	m_dial(*this, finder_base::DUMMY_TAG),
	m_volapcseq(*this, finder_base::DUMMY_TAG),
	m_tempoknob(*this, finder_base::DUMMY_TAG),
	m_cpl_leds(*this, "cpl_led%u", 0U),
	m_cpc_leds(*this, "cpc_led%u", 0U),
	m_cpr_leds(*this, "cpr_led%u", 0U)
{
	std::fill(std::begin(m_panel_resp), std::end(m_panel_resp), 0);
	std::fill(std::begin(m_btn_prev), std::end(m_btn_prev), 0);
}

void kn7000_cpanel_device::device_start()
{
	m_panel_evt = timer_alloc(FUNC(kn7000_cpanel_device::panel_event), this);
	m_panel_timer = timer_alloc(FUNC(kn7000_cpanel_device::panel_scan), this);

	save_item(NAME(m_panel_pos));
	save_item(NAME(m_panel_p1));
	save_item(NAME(m_panel_p2));
	save_item(NAME(m_panel_resp));
	save_item(NAME(m_panel_resp_len));
	save_item(NAME(m_panel_resp_pos));
	save_item(NAME(m_btn_prev));
	save_item(NAME(m_vol_apcseq_prev));
	save_item(NAME(m_vol_apcseq_synced));
	save_item(NAME(m_dial_prev));
	save_item(NAME(m_dial_synced));
	save_item(NAME(m_tempoknob_pos));
	save_item(NAME(m_tempoknob_prev));
	save_item(NAME(m_tempoknob_synced));
}

void kn7000_cpanel_device::device_reset()
{
	m_panel_pos = 0;
	// Drop any in-flight reply and its deferred delivery. (The old inline driver
	// reset left these; emptying them on reset is safer -- no stale byte can leak
	// after a soft reset -- and identical at cold boot where both are zero.)
	m_panel_resp_len = m_panel_resp_pos = 0;
	m_panel_evt->reset();
	std::fill(std::begin(m_btn_prev), std::end(m_btn_prev), 0);
	m_vol_apcseq_synced = false;   // re-record the pot on the first post-reset scan (no frame)
	m_dial_synced = false;         // re-record the DATA dial on the first post-reset scan (no frame)

	// Periodic button/analog scan at 250 Hz (real panel sub-CPUs continuously
	// monitor their matrices and push change notifications via the ATN line).
	m_panel_timer->adjust(attotime::from_hz(250), 0, attotime::from_hz(250));
}

// One panel TX byte from the main CPU (SIO channel 0). The main CPU transmits
// 7-byte FRAMES with interleaved line syncs:
//   pos 0 sync, 1 sync, 2 PAYLOAD1, 3 sync, 4 PAYLOAD2, 5 sync, 6 sync
// (TX sites: sender 0x484AC5E9; states 1..6 at 0x484AC7FA / 0x484AC8D3 /
// 0x484AC977 / 0x484AC9FF / 0x484ACA96 / 0x484ACAEA). Parse by position.
void kn7000_cpanel_device::tx_byte(uint8_t data)
{
	switch (m_panel_pos)
	{
	case 2: m_panel_p1 = data; break;
	case 4: m_panel_p2 = data; break;
	}
	if (++m_panel_pos >= 7)
	{
		m_panel_pos = 0;
		// Frame complete. Handshake commands (payload1 = 0x1F/0x1D/0x1E init,
		// 0x20/0xE0 ping CPL/CPR, 0x29/0xDD -- the boot's observed sequence) are
		// answered with a TYPE-3 sync packet and an ATN pulse. All other frames
		// carry LED-register updates [addr][data].
		switch (m_panel_p1)
		{
		case 0x1f: case 0x1d: case 0x1e: case 0x20: case 0xe0: case 0x29: case 0xdd:
		{
			static constexpr uint8_t sync_reply[2] = { 0x18, 0x00 };
			panel_queue(sync_reply, 2);
			break;
		}
		default:
			// NB: addr byte 0x00 is NOT idle/padding -- it is the CPR register-0
			// LED update [0x00][bits], carrying the firmware's "mode indicator"
			// LEDs (SetModeLed path): cpr_led0 = the CUSTOMIZE-MENU LED (named
			// LED idx19), cpr_led1/cpr_led2 = idx13/idx11. A former `case 0x00:
			// break;' dropped these entirely, so those LEDs never lit. The
			// firmware frame builder (0x484B170C) skips only data==0xFF, so 0x00
			// addresses must be decoded -- [0x00][0x00] correctly clears cpr_led0
			// when the CUSTOMIZE menu closes. (RE: workflow customize-led-trace.)
			panel_led_frame(m_panel_p1, m_panel_p2);
			break;
		}
	}
}

// One decoded LED-command frame: ADDR selects an 8-LED register on one of the
// panel boards, DATA is that register's 8 LED bits. The board is chosen by the
// bank field in ADDR bits 6-7; the register index is ADDR bits 0-5. This mirrors
// the firmware's LED shadow layout (notes/panel-serial-protocol.md).
void kn7000_cpanel_device::panel_led_frame(uint8_t addr, uint8_t data)
{
	// addr = panel(bits 7:6; 0x00=right/CPR, 0xC0/0xE0=left/CPL) | reg(bits 5:0).
	// Each data bit is one LED of register `reg`. Index reg*8+bit within the bank.
	const int reg = addr & 0x3f;
	const bool left = (addr & 0xc0) != 0;
	for (int bit = 0; bit < 8; bit++)
	{
		const int led = reg * 8 + bit;
		const int on = BIT(data, bit);
		if (led < 512) { if (left) m_cpl_leds[led] = on; else m_cpr_leds[led] = on; }
	}
	LOGMASKED(LOG_LEDS, "panel LED frame addr=%02X data=%02X\n", addr, data);
}

// Queue panel->main bytes (a handshake reply or a button-event packet) and start
// the delivery dance if idle: the panel pulses its ATN line (group 0x1A); the
// firmware's ISR switches the link to RX and clocks the bytes in one group-0x10
// interrupt at a time (state-8 handler -> the 92-byte ring -> the frame decoder).
void kn7000_cpanel_device::panel_queue(const uint8_t *bytes, int n)
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
//  param 1: ATN edge on the panel's external-interrupt pin -> main asserts group 0x1A.
//  param 2: the panel places its next reply byte on SIO0 -> main pushes it onto the
//           RX FIFO and asserts group 0x10 (the state-8 handler reads it from +9).
TIMER_CALLBACK_MEMBER(kn7000_cpanel_device::panel_event)
{
	if (param == 1)
		m_atn_cb(1);
	else if (param == 2 && m_panel_resp_pos < m_panel_resp_len)
	{
		m_rxd_cb(m_panel_resp[m_panel_resp_pos++]);
		if (m_panel_resp_pos < m_panel_resp_len)
			m_panel_evt->adjust(attotime::from_usec(120), 2);   // next byte
	}
}

// Main CPU enabled SIO ch0 RX (config bit14, set by the group-0x1A ISR's pass 2):
// the panel now sends its queued reply, one byte per group-0x10 interrupt.
void kn7000_cpanel_device::rx_enable()
{
	if (m_panel_resp_pos < m_panel_resp_len)
		m_panel_evt->adjust(attotime::from_usec(60), 2);
}

// The group-0x1A ISR's pass 1 re-armed EXTMD for the opposite edge (11b -> 10b)
// and expects the panel's second ATN edge to arrive after it returns.
void kn7000_cpanel_device::atn_rearm()
{
	m_panel_evt->adjust(attotime::from_usec(60), 1);
}

// Periodic scan: read the analog controllers and each declared button segment,
// and for any that changed since last scan queue the 2-byte [ADDR][DATA] frame
// the real sub-CPUs emit. Delivery rides the ATN/SIO handshake in panel_queue.
TIMER_CALLBACK_MEMBER(kn7000_cpanel_device::panel_scan)
{
	// Front-panel APC/SEQ VOLUME slider -> the firmware's own accompaniment/sequencer volume,
	// delivered the way the real hardware does it: the panel sub-CPU digitises the pot and sends a
	// CP-protocol TYPE 2 "latched control" frame [ADDR, DATA]. ADDR 0xD2 (bank11/type2/sub2) = APC/SEQ
	// VOLUME -- VERIFIED empirically (its RAM write-set overlaps MUTE UP 9's, which edits the same
	// setting, far more than 0xD0/D1/D3 do) and consistent with the service-manual ADC map (VR1102 = AD2).
	// The 0xD2 handler (0x484AD772) does DATA -> NOT -> latch 0x5006BEA6 -> >>1 -> remap table 0x48613508
	// (a monotonic 0..127 ramp), so a LOUDER setting needs a LOWER DATA byte. Map the 0..100 adjuster
	// accordingly and emit only on change. (MAIN uses a post-DAC gain in the driver; MIC/LINE-IN pots --
	// ADDRs 0xD0/D1/D3 -- are not yet identified individually, so they stay unbound for now.)
	{
		const uint8_t data = uint8_t(255 - (m_volapcseq.read_safe(0) * 255 + 50) / 100);
		if (!m_vol_apcseq_synced)
		{
			// first scan: just record the initial pot position. Do NOT emit a frame during early boot --
			// the firmware isn't servicing the panel handshake yet, so an undelivered frame would sit in
			// the response queue and block all later ATN kicks (buttons included). The slider takes over
			// on the first real move (matching the hardware's soft-takeover behaviour).
			m_vol_apcseq_prev = data;
			m_vol_apcseq_synced = true;
		}
		else if (data != m_vol_apcseq_prev)
		{
			m_vol_apcseq_prev = data;
			const uint8_t pkt[2] = { 0xd2, data };
			panel_queue(pkt, 2);
		}
	}

	// Front-panel DATA dial (the big value wheel with the central SET button) -> CP-protocol TYPE 2
	// "latched control" frame [0x10, POSITION]. The wheel is a rotary ENCODER: the panel sub-CPU keeps
	// an 8-bit position counter and ships it on the CP link, and the main-CPU handler (0x484AD6B0, wire
	// ADDR 0x10 = bank00/type2/sub0) DIFFS successive positions to derive the turn direction/amount
	// (EV_DIALUP/DOWN), which the UI applies to whatever field is focused (scroll a list, edit a value).
	// MAME's IPT_DIAL is precisely this kind of relative accumulator (0..255, wraps), so we forward its
	// value verbatim: the firmware's signed 8-bit diff turns a 0xFF->0x00 wrap into +1 exactly as the
	// real 8-bit counter does. Emit only on change, recording the initial position silently on the first
	// scan (same panel-handshake-poison guard as the APC/SEQ pot -- an undelivered boot frame would wedge
	// ALL later ATN delivery).
	{
		const uint8_t pos = m_dial.read_safe(0);
		if (!m_dial_synced)
		{
			m_dial_prev = pos;
			m_dial_synced = true;
		}
		else if (pos != m_dial_prev)
		{
			m_dial_prev = pos;
			const uint8_t pkt[2] = { 0x10, pos };
			panel_queue(pkt, 2);
		}
	}

	// Front-panel TEMPO/PROGRAM knob -> CP-protocol RELATIVE encoder [0x17, POSITION]. Its main-CPU handler
	// 0x484AD6A0 latches the raw wire byte verbatim (snapshot 0x5006BE9F + control-record 0x5006BEA8; NO
	// remap, NO scale, plain uint8), and a downstream tempo routine DIFFS successive positions -- bigger
	// diff = faster/accelerated change. A mouse drag on the layout knob moves the TEMPO_KNOB adjuster; we
	// convert its motion into the encoder position, but STEP AT MOST +/-1 PER SCAN (slewing toward the
	// adjuster target) so the firmware stays in its linear region -- a large single diff trips the velocity
	// curve and slams the tempo to a rail. First scan records the position silently (same panel-handshake
	// guard as the sliders/dial: emitting before the firmware services the panel wedges all later delivery).
	{
		const uint8_t adj = m_tempoknob.read_safe(0);
		if (!m_tempoknob_synced)
		{
			m_tempoknob_prev = adj;
			m_tempoknob_synced = true;
		}
		else if (adj != m_tempoknob_prev)
		{
			const int step = (adj > m_tempoknob_prev) ? 1 : -1;
			m_tempoknob_prev = uint8_t(m_tempoknob_prev + step);   // slew one step toward the drag target
			m_tempoknob_pos  = uint8_t(m_tempoknob_pos + step);    // wrapping 8-bit encoder position
			const uint8_t pkt[2] = { 0x17, m_tempoknob_pos };
			panel_queue(pkt, 2);
		}
	}

	// Inputs are declared one ioport per NORMALIZED SEGMENT (SEG00..SEG20), the
	// identity the firmware's button dispatcher (0x484ADB59) uses. For a changed
	// segment we emit its 2-byte [ADDR][DATA] switch frame, computing the wire
	// ADDR by REVERSE-normalizing (the inverse of table 0x486135A0):
	//   normSeg 0x00-0x0B -> ADDR 0xC0-0xCB (grp3), 0x0C-0x15 -> 0x00-0x09 (grp0),
	//   0x16-0x19 -> 0xD0-0xD3, 0x20 -> 0x17. normSeg 0x1A (wire 0x10 = DATA dial) is a
	//   VALUATOR, emitted by the dial block above, NOT here; 0x1B-0x1F have NO wire path.
	//   DATA = segment bitmask (bit=1 pressed); the main CPU XORs vs its shadow for edges.
	// Delivery rides the ATN dance via panel_queue (a bare fifo push never IRQs).
	static const uint8_t seg_to_addr[0x21] = {
		0xc0,0xc1,0xc2,0xc3,0xc4,0xc5,0xc6,0xc7,0xc8,0xc9,0xca,0xcb, // normSeg 0x00-0x0B
		0x00,0x01,0x02,0x03,0x04,0x05,0x06,0x07,0x08,0x09,           // normSeg 0x0C-0x15
		0xd0,0xd1,0xd2,0xd3,0xff,0xff,0xff,0xff,0xff,0xff,0x17,       // normSeg 0x16-0x20 (0x1A=dial, own path)
	};
	for (int seg = 0; seg < 0x21; seg++)
	{
		const uint8_t addr = seg_to_addr[seg];
		if (addr == 0xff)   // normSeg 0x1B-0x1F: no wire path
			continue;
		const uint8_t cur = m_seg[seg].read_safe(0);
		if (cur == m_btn_prev[seg])
			continue;
		m_btn_prev[seg] = cur;
		const uint8_t pkt[2] = { addr, cur };
		panel_queue(pkt, 2);
	}
}

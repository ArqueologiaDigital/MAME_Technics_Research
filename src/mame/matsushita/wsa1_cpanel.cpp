// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    Technics SX-WSA1 / SX-WSA1R control panel HLE

    The rationale, the byte evidence that this is the panel at all, and the
    wire format are in wsa1_cpanel.h.  This file is the machine.

    Every constant below is quoted with the prom_a / prom_b address that
    establishes it, and every table is reproduced by
    notes/wsa1-probes/wsa1_panel_tables.py --selftest.

***************************************************************************/

#include "emu.h"
#include "wsa1_cpanel.h"

#define LOG_FRAME (1U << 1)
#define LOG_LED   (1U << 2)
#define LOG_BTN   (1U << 3)

#define VERBOSE 0
#include "logmacro.h"

DEFINE_DEVICE_TYPE(WSA1_CPANEL, wsa1_cpanel_device, "wsa1_cpanel", "SX-WSA1 Control Panel HLE")


//-------------------------------------------------
//  the scan matrix
//
//  Eleven ports because the CP1 microcomputer drives SEG0..SEG10 and reads
//  SW0..SW7 (the block diagram on manual page II-1).  The (0xC4)=2 variant
//  leaves SEG6 and SEG10 unmapped -- prom_a 0xF8A189 has no entry for wire
//  0xC6 or 0xCA -- and segment_is_wired() refuses to report them, so a key
//  bound there is inert on the rack instead of quietly injecting a packet
//  the firmware would file under a group id of 0x20 ("no such control").
//
//  ⚠ The BIT-to-legend mapping is NOT ESTABLISHED and is not invented here.
//  The three combinations below are the only bits the ROM itself names, and
//  each is a power-on chord the boot block tests before the main loop starts
//  (prom_a 0xF828D9, 0xF8294C, 0xF82A04).
//-------------------------------------------------

static INPUT_PORTS_START(wsa1_cpanel)
	PORT_START("CP_SEG0")
	// (0xC4)=2 only: bits 4,5,6 held at power-on = the ROM-version LED display (0xF8295F)
	PORT_BIT(0xff, IP_ACTIVE_HIGH, IPT_KEYBOARD)

	PORT_START("CP_SEG1")
	PORT_BIT(0xff, IP_ACTIVE_HIGH, IPT_KEYBOARD)

	PORT_START("CP_SEG2")
	// (0xC4)=1 only: bits 0,1,2 held at power-on = the ROM-version LED display (0xF82952)
	PORT_BIT(0xff, IP_ACTIVE_HIGH, IPT_KEYBOARD)

	PORT_START("CP_SEG3")
	// (0xC4)=2 only: bits 5,6,7 held at power-on = the third service chord (0xF82A18)
	PORT_BIT(0xff, IP_ACTIVE_HIGH, IPT_KEYBOARD)

	PORT_START("CP_SEG4")
	PORT_BIT(0xff, IP_ACTIVE_HIGH, IPT_KEYBOARD)

	PORT_START("CP_SEG5")
	PORT_BIT(0xff, IP_ACTIVE_HIGH, IPT_KEYBOARD)

	PORT_START("CP_SEG6")   // (0xC4)=1 only
	PORT_BIT(0xff, IP_ACTIVE_HIGH, IPT_KEYBOARD)

	PORT_START("CP_SEG7")
	PORT_BIT(0xff, IP_ACTIVE_HIGH, IPT_KEYBOARD)

	PORT_START("CP_SEG8")
	// held at power-on: bits 0,1,2 ((0xC4)=1) or 0,1 ((0xC4)=2) = FACTORY CLEAR.  The boot
	// block zeroes 0x000080 up, zeroes both checksum words, writes the 0x5AA5 magic at
	// 0x7FCA and jumps back to RESET (prom_a 0xF828D9-0xF8293D).
	PORT_BIT(0xff, IP_ACTIVE_HIGH, IPT_KEYBOARD)

	PORT_START("CP_SEG9")
	PORT_BIT(0xff, IP_ACTIVE_HIGH, IPT_KEYBOARD)

	PORT_START("CP_SEG10")  // (0xC4)=1 only
	// (0xC4)=1: bits 5,6,7 held at power-on = the third service chord (0xF82A0A)
	PORT_BIT(0xff, IP_ACTIVE_HIGH, IPT_KEYBOARD)

	// Wire 0xD3.  The handler at prom_a 0xF89A8B is the one analogue channel with no
	// (0xC4) test at all, i.e. present on both variants, and it maps the byte through the
	// plain 0..127 ramp at 0xF89AB4.  On the rack the manual's only continuous control
	// besides the dial is VOLUME.
	PORT_START("CP_VOLUME")
	PORT_ADJUSTER(80, "VOLUME")

	// Wire 0xD7.  Its dispatch slot (prom_a 0xF89825 entry 31) is a bare `scf` -- no curve,
	// no previous-value compare -- so every packet is accepted.  A control that must never
	// be de-duplicated is a RELATIVE encoder, and the KN5000's twin protocol uses the same
	// wire address 0xD7 for its endless wheel as [0xD7, signed detent count]
	// (kn5000_cpanel.cpp, send_encoder_packet).  ⚠ The signed-step reading is INFERRED from
	// those two facts; nothing in prom_a's group-0x0F consumer has been read.
	PORT_START("CP_DIAL")
	PORT_BIT(0xff, 0x00, IPT_DIAL) PORT_SENSITIVITY(25) PORT_KEYDELTA(1) PORT_NAME("DATA ENTRY DIAL")
INPUT_PORTS_END


ioport_constructor wsa1_cpanel_device::device_input_ports() const
{
	return INPUT_PORTS_NAME(wsa1_cpanel);
}


wsa1_cpanel_device::wsa1_cpanel_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock) :
	device_t(mconfig, WSA1_CPANEL, tag, owner, clock),
	m_variant(2),
	m_pos(0), m_len(2),
	m_resp_len(0), m_resp_pos(0),
	m_rx_enabled(false),
	m_scan_timer(nullptr), m_byte_timer(nullptr),
	m_vol_prev(0), m_vol_synced(false),
	m_dial_prev(0), m_dial_synced(false),
	m_atn_cb(*this), m_busy_cb(*this), m_sclk_cb(*this), m_rxd_cb(*this),
	m_seg(*this, "CP_SEG%u", 0U),
	m_volume(*this, "CP_VOLUME"),
	m_dial(*this, "CP_DIAL"),
	m_led_out(*this, "led%u", 0U)
{
	std::fill(std::begin(m_frame), std::end(m_frame), 0);
	std::fill(std::begin(m_resp), std::end(m_resp), 0);
	std::fill(std::begin(m_seg_prev), std::end(m_seg_prev), 0);
	std::fill(std::begin(m_led), std::end(m_led), 0);
}


void wsa1_cpanel_device::device_start()
{
	m_led_out.resolve();
	m_scan_timer = timer_alloc(FUNC(wsa1_cpanel_device::scan_tick), this);
	m_byte_timer = timer_alloc(FUNC(wsa1_cpanel_device::deliver_byte), this);

	save_item(NAME(m_variant));
	save_item(NAME(m_frame));
	save_item(NAME(m_pos));
	save_item(NAME(m_len));
	save_item(NAME(m_resp));
	save_item(NAME(m_resp_len));
	save_item(NAME(m_resp_pos));
	save_item(NAME(m_rx_enabled));
	save_item(NAME(m_seg_prev));
	save_item(NAME(m_vol_prev));
	save_item(NAME(m_vol_synced));
	save_item(NAME(m_dial_prev));
	save_item(NAME(m_dial_synced));
	save_item(NAME(m_led));
}


void wsa1_cpanel_device::device_reset()
{
	m_pos = 0;
	m_len = 2;
	m_resp_len = m_resp_pos = 0;
	m_rx_enabled = false;
	m_byte_timer->reset();
	std::fill(std::begin(m_seg_prev), std::end(m_seg_prev), 0);
	m_vol_synced = false;
	m_dial_synced = false;

	// The two lines SC1_WaitTxDrain and SC1_TxFlush_Body test before they will touch the
	// link (prom_b 0xF5AB7B / 0xF5AB80): "free" is P8 bit 5 HIGH and PB bit 4 LOW.  Get
	// this wrong and nothing is ever transmitted -- the four-way test bails to
	// SC1_TxFlush_Exit and no LED frame and no command leaves the CPU.
	m_sclk_cb(1);
	m_busy_cb(0);
	m_atn_cb(0);

	// 250 Hz, the same rate kn_cpanel_base_device uses.  Nothing in the WSA1 ROMs measures
	// the real MCU's scan period; this is a driver choice and is marked as one.
	m_scan_timer->adjust(attotime::from_hz(250), 0, attotime::from_hz(250));
}


//-------------------------------------------------
//  variant geometry
//-------------------------------------------------

bool wsa1_cpanel_device::segment_is_wired(int seg) const
{
	if (seg < 0 || seg >= NUM_SEG)
		return false;
	if (m_variant == 1)
		return true;                       // prom_a 0xF8A109: wire 0xC0..0xCA all mapped
	return (seg != 6) && (seg != 10);      // prom_a 0xF8A189: 0xC6 and 0xCA are 0x20 = none
}


//-------------------------------------------------
//  CPU 1 -> panel
//
//  The frame length rule is the firmware's own, from the two places it sets
//  the "bytes still expected" counter (0x2A81) after a first byte:
//  prom_b 0xF5ADD7 (transmit, SC1_State08_TxFromRing) and 0xF5AF41
//  (receive, SC1_State20_RxFirstByte).  Both are
//      (0x2A81) = 2 ; if ((b & 0x3F) >= 0x30) (0x2A81) = (b & 0x0F) + 3
//  which is exactly what SC1_TxOp3_Run emits (header + (n & 0x0F) + 2 more)
//  and what SC1_RxOp6_Run consumes (header + address + (n & 0x0F) + 1 data).
//
//  ★ That reconciles the "the two run encoders do NOT obviously agree" warning
//    in wsa1-roms-disasm/notes/FINDINGS-prom_b-sc1-link.md sec.6: they do
//    agree, at n+3 bytes per message, and the length counter is the third
//    independent witness to it.
//-------------------------------------------------

void wsa1_cpanel_device::tx_byte(u8 data)
{
	if (m_pos == 0)
		m_len = ((data & 0x3f) >= 0x30) ? ((data & 0x0f) + 3) : 2;

	if (m_pos < int(sizeof(m_frame)))
		m_frame[m_pos] = data;
	m_pos++;

	if (m_pos >= m_len)
	{
		frame_complete();
		m_pos = 0;
		m_len = 2;
	}
}


void wsa1_cpanel_device::frame_complete()
{
	const u8 hdr = m_frame[0];
	LOGMASKED(LOG_FRAME, "panel <- CPU: %d bytes, hdr %02X\n", m_len, hdr);

	if ((hdr & 0x30) == 0x30)
	{
		// Run frame: [HDR][FIRST_ADDR][DATA] x ((HDR & 0x0F) + 1), addresses stepping by 1.
		// SC1_TxOp3_Run (prom_b 0xF5B2D9) builds it; nothing in this firmware has been seen
		// to produce one, but the codec accepts it, so decode it.
		const int n = (hdr & 0x0f) + 1;
		u8 addr = (hdr & 0xc0) | (m_frame[1] & 0x1f);
		for (int i = 0; i < n && (2 + i) < m_len; i++, addr++)
			if ((addr & 0xf0) == 0xc0)
				led_frame(addr, m_frame[2 + i]);
		return;
	}

	const u8 addr = hdr, data = m_frame[1];

	if ((addr & 0xf0) == 0xc0)
	{
		led_frame(addr, data);
		return;
	}

	// Everything else is a command.  The seven the firmware ever sends first are, in ROM
	// order: 0xDF 0xD2 / 0xDF 0x1A / 0xDD 0x03 / 0xDE 0x80 (SC1_ConfigurePort, prom_b
	// 0xF5A8ED..0xF5A92C), 0xE0 0x00 (SC1_Cmd_E0_ReadStatus), 0xE3 0x00 / 0xE2 0x08 /
	// 0xE3 0x10 (SC1_Cmd_E3_E2_E3) and 0xEF 0x00 (SC1_Cmd_EF).
	//
	// ⚠ WHAT THEY ASK FOR IS NOT ESTABLISHED.  What IS established is what the firmware
	// does with the answer: SC1_Cmd_E0_ReadStatus (0xF5AAA9) zeroes both rx ring indices,
	// sends (0xE0,0x00), waits six ticks and sets bit 3 of (0x2A85) if the WRITE index
	// moved.  So the only thing it measures is "did the panel answer at all".  Answering
	// with a two-byte packet whose type field is 3, 4 or 5 satisfies that and is then
	// DISCARDED by SC1_RxOp3_Discard (0xF5B226) without entering the message queue --
	// exactly the KN5000's TYPE 3 sync packet (kn5000_cpanel.cpp, send_sync_packet).
	//
	// ⚠ The header byte itself is a CHOICE: 0xD8 = panel id 11 (which every live address on
	// this machine carries) + type 3.  The KN5000 sends 0x18, the same type with panel id
	// 00.  Only the TYPE field is decoded; the exact byte the real M37471 sends is unknown.
	static const u8 sync[2] = { 0xd8, 0x00 };
	switch (addr)
	{
	case 0xdd: case 0xde: case 0xdf:   // the open sequence, sent with interrupts masked
	case 0xe0: case 0xe2: case 0xe3: case 0xef:
		queue_frame(sync, 2);
		break;
	default:
		LOGMASKED(LOG_FRAME, "unhandled command %02X %02X\n", addr, data);
		break;
	}
}


//-------------------------------------------------
//  LED registers
//
//  Panel_RefreshLeds (prom_a 0xF8C456) walks EIGHT registers, comparing the
//  want-buffer at RAM 0x20D0..0x20D7 with the sent-shadow at 0x20F0..0x20F7
//  and calling Panel_SetLedRegister (0xF8C84A) for each one that differs.
//  That routine maps the register INDEX through one of two tables --
//  0xF8C8AC when (0xC4)==1, 0xF8C8B7 otherwise -- to the wire address, then
//  pushes [ADDR][DATA] into the outbound queue at 0x2BA0.
//-------------------------------------------------

void wsa1_cpanel_device::led_frame(u8 addr, u8 data)
{
	// prom_a 0xF8C8AC and 0xF8C8B7, read out of the ROM by wsa1_panel_tables.py.
	static const u8 wire_v1[8] = { 0xc0, 0xc1, 0xc2, 0xc4, 0xc5, 0xc9, 0xcc, 0xcd };
	static const u8 wire_v2[8] = { 0xc1, 0xc2, 0xc9, 0xca, 0xcb, 0xcc, 0xc3, 0x00 };
	const u8 *wire = (m_variant == 1) ? wire_v1 : wire_v2;

	for (int reg = 0; reg < 8; reg++)
	{
		if (wire[reg] != addr)
			continue;
		if (m_led[reg] == data)
			return;
		m_led[reg] = data;
		for (int bit = 0; bit < 8; bit++)
			m_led_out[reg * 8 + bit] = BIT(data, bit);
		LOGMASKED(LOG_LED, "LED reg %d (wire %02X) = %02X\n", reg, addr, data);
		return;
	}
	LOGMASKED(LOG_LED, "LED frame for unmapped wire address %02X = %02X\n", addr, data);
}


//-------------------------------------------------
//  panel -> CPU 1
//
//  One INT6 per MESSAGE, not per byte: INT6_SC1_PeerRequest (prom_b 0xF5AC0A)
//  turns RXE on, sets SC1CR bit 0 (the panel now clocks), selects INTES1=0x05
//  (receive only) and sets state 0x20.  SC1_State20_RxFirstByte then takes the
//  length from the first byte and SC1_State24_RxNextByte counts the rest down,
//  re-arming INT6 when it is done.  So: raise ATN, wait for the firmware to
//  enable RX, then push the message's bytes one at a time.
//-------------------------------------------------

void wsa1_cpanel_device::queue_frame(const u8 *bytes, int n)
{
	if (m_resp_pos == m_resp_len)
		m_resp_pos = m_resp_len = 0;
	if (m_resp_len + n > RESP_MAX)
		return;                              // the real MCU's queue would drop it too
	const bool was_idle = (m_resp_pos == m_resp_len);
	for (int i = 0; i < n; i++)
		m_resp[m_resp_len++] = bytes[i];
	if (was_idle)
	{
		m_busy_cb(1);                        // PB bit 4 high: the panel wants the link
		m_atn_cb(1);                         // INT6
	}
}


void wsa1_cpanel_device::rx_enable(int state)
{
	m_rx_enabled = bool(state);
	if (m_rx_enabled && m_resp_pos < m_resp_len)
		m_byte_timer->adjust(attotime::from_usec(60));
}


TIMER_CALLBACK_MEMBER(wsa1_cpanel_device::deliver_byte)
{
	if (m_resp_pos >= m_resp_len)
		return;

	m_rxd_cb(m_resp[m_resp_pos++]);

	if (m_resp_pos < m_resp_len)
	{
		m_byte_timer->adjust(attotime::from_usec(120));
	}
	else
	{
		m_resp_pos = m_resp_len = 0;
		m_busy_cb(0);
		m_atn_cb(0);
	}
}


//-------------------------------------------------
//  the periodic scan
//
//  Buttons are reported as [0xC0 | segment][bitmask].  The header's type field
//  falls out of the segment number for free -- segments 0..7 give type 0 and
//  8..15 type 1, which is exactly why SC1_RxOpTable entries [0] and [1] are
//  the same handler.  SC1_RxOp0_ThreeByte then XORs the mask against its own
//  shadow at RAM 0x2B20 + ((addr & 0x0F) + 0x10) and hands the foreground
//  {address, mask, CHANGED-bits} -- so sending the whole segment state, not
//  just the change, is correct and is what the shadow table is there for.
//
//  Analogue controls are [0xD0 | sub][value]; the firmware appends its own
//  0xFF third byte (prom_b 0xF5B163), so it must NOT be sent here.
//-------------------------------------------------

TIMER_CALLBACK_MEMBER(wsa1_cpanel_device::scan_tick)
{
	for (int seg = 0; seg < NUM_SEG; seg++)
	{
		if (!segment_is_wired(seg))
			continue;
		const u8 v = m_seg[seg].read_safe(0);
		if (v == m_seg_prev[seg])
			continue;
		m_seg_prev[seg] = v;
		const u8 pkt[2] = { u8(0xc0 | seg), v };
		LOGMASKED(LOG_BTN, "segment %d = %02X\n", seg, v);
		queue_frame(pkt, 2);
	}

	// Wire 0xD3.  prom_a 0xF89A8B halves the byte and looks it up in the 0..127 ramp at
	// 0xF89AB4, so the wire value is a full 8-bit pot reading.
	{
		const u8 v = u8((m_volume.read_safe(0) * 255 + 50) / 100);
		if (!m_vol_synced)
		{
			m_vol_prev = v;
			m_vol_synced = true;         // adopt silently: a frame nobody is servicing yet
		}                                //  would sit in the queue and block every later ATN
		else if (v != m_vol_prev)
		{
			m_vol_prev = v;
			const u8 pkt[2] = { 0xd3, v };
			queue_frame(pkt, 2);
		}
	}

	// Wire 0xD7, the DATA ENTRY DIAL.  Sent as a SIGNED STEP -- see the ioport comment for
	// why, and for the fact that this is inference and not decode.
	{
		const s32 pos = m_dial.read_safe(0);
		if (!m_dial_synced)
		{
			m_dial_prev = pos;
			m_dial_synced = true;
		}
		else if (pos != m_dial_prev)
		{
			s32 d = pos - m_dial_prev;
			if (d > 128) d -= 256;
			else if (d < -128) d += 256;
			m_dial_prev = pos;
			const s8 step = s8(std::clamp<s32>(d, -64, 63));
			const u8 pkt[2] = { 0xd7, u8(step) };
			queue_frame(pkt, 2);
		}
	}
}

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

// Physical scan matrix == firmware normalized-segment space (see kn7000.cpp INPUT_PORTS header).
// PORT_SEG[port] is the normSeg (= sub-CPU scan column) that input port n drives; the SW bit is
// forwarded unchanged. Each scan column maps to exactly one wire ADDR (no per-bit repacking), so
// this is a pure identity -- no per-button translation table is needed.
static const uint8_t PORT_SEG[22] = {
	0x00,0x01,0x02,0x03,0x04,0x06,0x07,   // CPL_SEG0,1,2,3,4,6,7
	0x05,0x08,0x09,0x0a,0x0b,             // CPC_SEG5,8,9,10,11
	0x0c,0x0d,0x0e,0x0f,0x10,0x11,0x12,0x13,0x14,0x15  // CPR_SEG0..9  (wire ADDR 0x00..0x09)
};


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
	m_phys(*this, finder_base::DUMMY_TAG, 0U),
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

void kn7000_cpanel_device::panel_led_frame(uint8_t addr, uint8_t data)
{
	// One decoded LED-command frame. ADDR = board (bits 7:6; 0x00 = CPR / right panel, 0xC0/0xE0 =
	// CPL / left panel) | LED register (bits 5:0). Each DATA bit is one LED; its output index is
	// reg*8 + bit within that board's bank (cpr_led#/cpl_led#), and the comment names the panel
	// function/mode that LED indicates (KN5000 style). This map is kept in sync with -- and generated
	// from -- the layout's LED bindings (tools/gen_lay.py LED_PURPOSE), which carry the empirically
	// verified assignments (e.g. FAVORITES = cpr_led2 via PANEL_LED, corrected 2026-07-14 from cpr_led97). Bits marked
	// (unmapped) are real firmware LEDs whose panel function is not yet identified; the default arm
	// keeps any register not enumerated here working too.
	const int reg = addr & 0x3f;
	if ((addr & 0xc0) == 0)
	{
		switch (reg)
		{
		case 0x00:
			m_cpr_leds[0]  = BIT(data, 0);   // D1009 CUSTOMIZE (green)
			m_cpr_leds[1]  = BIT(data, 1);   // D1023 CUSTOM PANEL (green)
			m_cpr_leds[2]  = BIT(data, 2);   // D1037 FAVORITES (green)   [Felipe 2026-07-14 live LED log: the real FAVORITES LED; supersedes the earlier cpr_led97 assignment]
			m_cpr_leds[3]  = BIT(data, 3);   // D1051 SOUND GROUP 5 (PANEL MEMORY 5) (amber)
			m_cpr_leds[4]  = BIT(data, 4);   // D1065 SOUND GROUP 4 (PANEL MEMORY 4) (amber)
			m_cpr_leds[5]  = BIT(data, 5);   // D1079 SOUND GROUP 3 (PANEL MEMORY 3) (amber)
			m_cpr_leds[6]  = BIT(data, 6);   // D1093 SOUND GROUP 2 (PANEL MEMORY 2) (amber)
			m_cpr_leds[7]  = BIT(data, 7);   // D1107 CONDUCTOR RIGHT 1 (red)   [empirically verified 2026-07-14: lights iff RIGHT 1 conductor-active; this is the real R1 indicator, not the inferred cpr_led63]
			break;
		case 0x01:
			m_cpr_leds[8]  = BIT(data, 0);   // (unmapped)
			m_cpr_leds[9]  = BIT(data, 1);   // D1024 SD CARD LOAD (green)
			m_cpr_leds[10] = BIT(data, 2);   // (unmapped)
			m_cpr_leds[11] = BIT(data, 3);   // D1052 DISK IN USE (red)   [Felipe 2026-07-14 live LED log]
			m_cpr_leds[12] = BIT(data, 4);   // D1066 BANK VIEW (PANEL MEMORY BANK SELECT) (green)
			m_cpr_leds[13] = BIT(data, 5);   // D1080 SOUND GROUP 6 (PANEL MEMORY 6) (amber)
			m_cpr_leds[14] = BIT(data, 6);   // D1094 SOUND GROUP 7 (PANEL MEMORY 7) (amber)
			m_cpr_leds[15] = BIT(data, 7);   // D1108 SOUND GROUP 8 (PANEL MEMORY 8) (red)
			break;
		case 0x02:
			m_cpr_leds[16] = BIT(data, 0);   // D1011 DISK EASY REC (green)
			m_cpr_leds[17] = BIT(data, 1);   // D1025 DISK PLAY (green)
			m_cpr_leds[18] = BIT(data, 2);   // D1039 VARIATION (red)
			m_cpr_leds[19] = BIT(data, 3);   // D1053 SOUND DSP (red)
			m_cpr_leds[20] = BIT(data, 4);   // D1067 DIGITAL EFFECT (red)
			m_cpr_leds[21] = BIT(data, 5);   // D1081 SUSTAIN (red)
			m_cpr_leds[22] = BIT(data, 6);   // D1095 SOUND EXPLORER (red)
			m_cpr_leds[23] = BIT(data, 7);   // D1116 ORGAN & ACCORDION (red)
			break;
		case 0x03:
			m_cpr_leds[24] = BIT(data, 0);   // D1012 PROGRAM MENUS (green)
			m_cpr_leds[25] = BIT(data, 1);   // D1026 DISK MENU LOAD (green)
			m_cpr_leds[26] = BIT(data, 2);   // D1040 EFFECT MIC (red)
			m_cpr_leds[27] = BIT(data, 3);   // D1068 REVERB (red)
			m_cpr_leds[28] = BIT(data, 4);   // D1054 MULTI (red)
			m_cpr_leds[29] = BIT(data, 5);   // D1082 CHORUS (red)
			m_cpr_leds[30] = BIT(data, 6);   // D1096 EW EXPANSION (red)
			m_cpr_leds[31] = BIT(data, 7);   // D1110 MEMORY (green)
			break;
		case 0x04:
			m_cpr_leds[32] = BIT(data, 0);   // D1027 SOLO (red)
			m_cpr_leds[33] = BIT(data, 1);   // D1013 TECHNI-CHORD (red)
			m_cpr_leds[34] = BIT(data, 2);   // D1069 PART SELECT RIGHT 1 (red)   [schematic labels D1069 LEFT; panel silk = RIGHT 1]
			m_cpr_leds[35] = BIT(data, 3);   // D1041 PART SELECT RIGHT 2 (red)
			m_cpr_leds[36] = BIT(data, 4);   // D1055 PART SELECT LEFT (red)   [schematic labels D1055 RIGHT 1; panel silk = LEFT]
			m_cpr_leds[37] = BIT(data, 5);   // D1083 TRANSPOSE R2 (+) (red)
			m_cpr_leds[38] = BIT(data, 6);   // D1097 TRANSPOSE R2 (-) (red)
			m_cpr_leds[39] = BIT(data, 7);   // D1111 TRANSPOSE R1 (+) (green)
			break;
		case 0x05:
			m_cpr_leds[40] = BIT(data, 0);   // D1042 STRINGS & VOCAL (red)
			m_cpr_leds[41] = BIT(data, 1);   // D1122 WORLD (red)
			m_cpr_leds[42] = BIT(data, 2);   // D1014 MALLET & ORCH PERC (red)
			m_cpr_leds[43] = BIT(data, 3);   // D1056 GUITAR (red)
			m_cpr_leds[44] = BIT(data, 4);   // D1070 PIANO (red)
			m_cpr_leds[45] = BIT(data, 5);   // D1098 SYNTH (red)
			m_cpr_leds[46] = BIT(data, 6);   // D1112 PAD (green)
			m_cpr_leds[47] = BIT(data, 7);   // D1117 ACCORDION REGISTER (red)
			break;
		case 0x07:
			m_cpr_leds[56] = BIT(data, 0);   // (unmapped)
			m_cpr_leds[57] = BIT(data, 1);   // (unmapped)
			m_cpr_leds[58] = BIT(data, 2);   // (unmapped)
			m_cpr_leds[59] = BIT(data, 3);   // (unmapped)
			m_cpr_leds[60] = BIT(data, 4);   // (unmapped)
			m_cpr_leds[61] = BIT(data, 5);   // (unmapped)
			m_cpr_leds[62] = BIT(data, 6);   // (unmapped)
			m_cpr_leds[63] = BIT(data, 7);   // (unmapped)   [was inferred CONDUCTOR RIGHT 1 but never lights; the real R1 indicator is cpr_led7 -- verified 2026-07-14]
			break;
		case 0x08:
			m_cpr_leds[64] = BIT(data, 0);   // D1114 CONDUCTOR RIGHT 2 (red)   [schematic labels D1114 RIGHT 1; panel silk = RIGHT 2]
			m_cpr_leds[65] = BIT(data, 1);   // D1120 CONDUCTOR LEFT (red)
			m_cpr_leds[66] = BIT(data, 2);   // (unmapped)
			m_cpr_leds[67] = BIT(data, 3);   // (unmapped)
			m_cpr_leds[68] = BIT(data, 4);   // (unmapped)
			m_cpr_leds[69] = BIT(data, 5);   // (unmapped)
			m_cpr_leds[70] = BIT(data, 6);   // (unmapped)
			m_cpr_leds[71] = BIT(data, 7);   // (unmapped)
			break;
		case 0x09:
			m_cpr_leds[72] = BIT(data, 0);   // D1115 SOUND GROUP 1 (PANEL MEMORY 1) (red)
			m_cpr_leds[73] = BIT(data, 1);   // (unmapped)
			m_cpr_leds[74] = BIT(data, 2);   // (unmapped)
			m_cpr_leds[75] = BIT(data, 3);   // (unmapped)
			m_cpr_leds[76] = BIT(data, 4);   // (unmapped)
			m_cpr_leds[77] = BIT(data, 5);   // (unmapped)
			m_cpr_leds[78] = BIT(data, 6);   // (unmapped)
			m_cpr_leds[79] = BIT(data, 7);   // (unmapped)
			break;
		case 0x0a:
			m_cpr_leds[80] = BIT(data, 0);   // D1109 SAX & WOODWIND (red)
			m_cpr_leds[81] = BIT(data, 1);   // D1028 BRASS (red)
			m_cpr_leds[82] = BIT(data, 2);   // (unmapped)
			m_cpr_leds[83] = BIT(data, 3);   // (unmapped)
			m_cpr_leds[84] = BIT(data, 4);   // (unmapped)
			m_cpr_leds[85] = BIT(data, 5);   // (unmapped)
			m_cpr_leds[86] = BIT(data, 6);   // (unmapped)
			m_cpr_leds[87] = BIT(data, 7);   // (unmapped)
			break;
		case 0x0b:
			m_cpr_leds[88] = BIT(data, 0);   // D1123 DRUM KITS (red)
			m_cpr_leds[89] = BIT(data, 1);   // D1084 BASS (red)
			m_cpr_leds[90] = BIT(data, 2);   // (unmapped)
			m_cpr_leds[91] = BIT(data, 3);   // (unmapped)
			m_cpr_leds[92] = BIT(data, 4);   // (unmapped)
			m_cpr_leds[93] = BIT(data, 5);   // (unmapped)
			m_cpr_leds[94] = BIT(data, 6);   // (unmapped)
			m_cpr_leds[95] = BIT(data, 7);   // (unmapped)
			break;
		case 0x0c:
			m_cpr_leds[96] = BIT(data, 0);   // D1118 TRANSPOSE R1 (-) (red)
			m_cpr_leds[97] = BIT(data, 1);   // TEMPO/PROGRAM   [Felipe 2026-07-14 F3+F4 LED test: the tempo/program knob LED, only unnamed CPR LED lit by PANEL MEMORY SET; NB this was the old wrong FAVORITES guess -- FAVORITES is cpr_led2]
			m_cpr_leds[98] = BIT(data, 2);   // (unmapped)
			m_cpr_leds[99] = BIT(data, 3);   // (unmapped)
			m_cpr_leds[100]= BIT(data, 4);   // (unmapped)
			m_cpr_leds[101]= BIT(data, 5);   // (unmapped)
			m_cpr_leds[102]= BIT(data, 6);   // (unmapped)
			m_cpr_leds[103]= BIT(data, 7);   // (unmapped)
			break;
		case 0x0d:
			m_cpr_leds[104]= BIT(data, 0);   // D1119 TAB ORGAN (red)
			m_cpr_leds[105]= BIT(data, 1);   // D1121 DIGITAL DRAWBAR (red)
			m_cpr_leds[106]= BIT(data, 2);   // (unmapped)
			m_cpr_leds[107]= BIT(data, 3);   // (unmapped)
			m_cpr_leds[108]= BIT(data, 4);   // (unmapped)
			m_cpr_leds[109]= BIT(data, 5);   // (unmapped)
			m_cpr_leds[110]= BIT(data, 6);   // (unmapped)
			m_cpr_leds[111]= BIT(data, 7);   // (unmapped)
			break;
		default:
			for (int bit = 0; bit < 8; bit++) { const int led = reg * 8 + bit; if (led < 512) m_cpr_leds[led] = BIT(data, bit); }
			break;
		}
	}
	else if ((addr & 0xe0) == 0xe0)
	{
		// CPC board (centre panel: OTHER PARTS/TG, the 16-part MUTE grid, ...). One sub-CPU drives both
		// CPL and CPC LEDs and selects the board with ADDR bit 5: 0xC0-0xDF = CPL, 0xE0-0xFF = CPC
		// (empirically CPC LED frames appear only as ADDR 0xE0-0xFF; register = ADDR bits 4:0). Bits not
		// yet tied to a panel function are still driven, so the layout can name cpc_led# once identified.
		const int creg = addr & 0x1f;
		for (int bit = 0; bit < 8; bit++)
		{
			const int led = creg * 8 + bit;
			if (led < 512)
				m_cpc_leds[led] = BIT(data, bit);
		}
	}
	else
	{
		switch (reg)
		{
		case 0x00:
			m_cpl_leds[0]  = BIT(data, 0);   // D1116 INTRO & ENDING 1 (red)
			m_cpl_leds[1]  = BIT(data, 1);   // D1147 BALLROOM (red)
			m_cpl_leds[2]  = BIT(data, 2);   // 8 & 16 BEAT
			m_cpl_leds[3]  = BIT(data, 3);   // D1164 VARIATION & MSA 1 (red)
			m_cpl_leds[4]  = BIT(data, 4);   // D1180 MUSIC STYLE ARRANGER (red)
			m_cpl_leds[5]  = BIT(data, 5);   // DISPLAY HOLD
			m_cpl_leds[6]  = BIT(data, 6);   // (unmapped)
			m_cpl_leds[7]  = BIT(data, 7);   // (unmapped)
			break;
		case 0x01:
			m_cpl_leds[8]  = BIT(data, 0);   // D1115 INTRO & ENDING 2 (red)
			m_cpl_leds[9]  = BIT(data, 1);   // D1142 MARCH (red)
			m_cpl_leds[10] = BIT(data, 2);   // 60s & 70s
			m_cpl_leds[11] = BIT(data, 3);   // D1163 VARIATION & MSA 2 (red)
			m_cpl_leds[12] = BIT(data, 4);   // D1179 PERFORMANCE PADS/AUTO (green)
			m_cpl_leds[13] = BIT(data, 5);   // SPLIT POINT G3   [keyboard split-point indicator; verified 2026-07-14]
			m_cpl_leds[14] = BIT(data, 6);   // (unmapped)
			m_cpl_leds[15] = BIT(data, 7);   // (unmapped)
			break;
		case 0x02:
			m_cpl_leds[16] = BIT(data, 0);   // D1114 SYNCHRO & BREAK (red)
			m_cpl_leds[17] = BIT(data, 1);   // D1141 MOVIE SHOW (red)
			m_cpl_leds[18] = BIT(data, 2);   // D1130 ROCK & POP (red)
			m_cpl_leds[19] = BIT(data, 3);   // D1162 VARIATION & MSA 3 (red)
			m_cpl_leds[20] = BIT(data, 4);   // D1178 APC/SEQ VOLUME (state LED, no button) (green)
			m_cpl_leds[21] = BIT(data, 5);   // SPLIT POINT C3   [keyboard split-point indicator; verified 2026-07-14]
			m_cpl_leds[22] = BIT(data, 6);   // (unmapped)
			m_cpl_leds[23] = BIT(data, 7);   // (unmapped)
			break;
		case 0x03:
			m_cpl_leds[24] = BIT(data, 0);   // BEAT 1
			m_cpl_leds[25] = BIT(data, 1);   // D1145 LATIN & WORLD (red)
			m_cpl_leds[26] = BIT(data, 2);   // D1148 MODERN DANCE (red)
			m_cpl_leds[27] = BIT(data, 3);   // D1161 VARIATION & MSA 4 (red)
			m_cpl_leds[28] = BIT(data, 4);   // D1177 MUSIC STYLIST (green)
			m_cpl_leds[29] = BIT(data, 5);   // OTHER PART & FR   [Felipe 2026-07-14 F3+F4 LED test: the OTHER PARTS/TG (CPC_SEG5.01) button's indicator, on the CPL board]
			m_cpl_leds[30] = BIT(data, 6);   // (unmapped)
			m_cpl_leds[31] = BIT(data, 7);   // (unmapped)
			break;
		case 0x04:
			m_cpl_leds[32] = BIT(data, 0);   // BEAT 2
			m_cpl_leds[33] = BIT(data, 1);   // D1143 ENTERTAINER (red)
			m_cpl_leds[34] = BIT(data, 2);   // D1128 BALLAD (red)
			m_cpl_leds[35] = BIT(data, 3);   // D1160 FADE IN (red)
			m_cpl_leds[36] = BIT(data, 4);   // D1176 AUTO MODE (green)
			m_cpl_leds[37] = BIT(data, 5);   // (unmapped)
			m_cpl_leds[38] = BIT(data, 6);   // (unmapped)
			m_cpl_leds[39] = BIT(data, 7);   // (unmapped)
			break;
		case 0x05:
			m_cpl_leds[40] = BIT(data, 0);   // BEAT 3
			m_cpl_leds[41] = BIT(data, 1);   // D1127 CUSTOM (green)
			m_cpl_leds[42] = BIT(data, 2);   // D1126 SOUL & FUNK (red)
			m_cpl_leds[43] = BIT(data, 3);   // D1159 FILL IN 1 (red)
			m_cpl_leds[44] = BIT(data, 4);   // D1175 SOUND SET (green)
			m_cpl_leds[45] = BIT(data, 5);   // (unmapped)
			m_cpl_leds[46] = BIT(data, 6);   // (unmapped)
			m_cpl_leds[47] = BIT(data, 7);   // (unmapped)
			break;
		case 0x06:
			m_cpl_leds[48] = BIT(data, 0);   // BEAT 4
			m_cpl_leds[49] = BIT(data, 1);   // ORGANIST
			m_cpl_leds[50] = BIT(data, 2);   // D1129 JAZZ COMBO (red)
			m_cpl_leds[51] = BIT(data, 3);   // D1158 FADE OUT (red)
			m_cpl_leds[52] = BIT(data, 4);   // D1174 PLAY CHORD OFF/ON (red)
			m_cpl_leds[53] = BIT(data, 5);   // (unmapped)
			m_cpl_leds[54] = BIT(data, 6);   // (unmapped)
			m_cpl_leds[55] = BIT(data, 7);   // (unmapped)
			break;
		case 0x07:
			m_cpl_leds[56] = BIT(data, 0);   // SPLIT POINT G2   [keyboard split-point indicator; manual p39 SPLIT POINT cycles G2->C3->G3->off; verified 2026-07-14]
			m_cpl_leds[57] = BIT(data, 1);   // D1125 MEMORY/LOAD (green)
			m_cpl_leds[58] = BIT(data, 2);   // D1144 COUNTRY (red)
			m_cpl_leds[59] = BIT(data, 3);   // D1157 FILL IN 2 (red)
			m_cpl_leds[60] = BIT(data, 4);   // D1173 ARRANGER OFF/ON (green)
			m_cpl_leds[61] = BIT(data, 5);   // (unmapped)
			m_cpl_leds[62] = BIT(data, 6);   // (unmapped)
			m_cpl_leds[63] = BIT(data, 7);   // (unmapped)
			break;
		default:
			for (int bit = 0; bit < 8; bit++) { const int led = reg * 8 + bit; if (led < 512) m_cpl_leds[led] = BIT(data, bit); }
			break;
		}
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
			// The layout knob is an INFINITE rotary encoder: a full-circle drag wraps the 0..100 adjuster
			// past its ends. Take the direction the SHORT way round (a jump of >50 = a wrap), so rotating
			// through the 100->0 (or 0->100) seam keeps stepping instead of slamming 100 steps the other way.
			int delta = int(adj) - int(m_tempoknob_prev);
			if (delta > 50) delta -= 101;
			else if (delta < -50) delta += 101;
			const int step = (delta > 0) ? 1 : -1;
			m_tempoknob_prev = uint8_t((int(m_tempoknob_prev) + step + 101) % 101);   // slew one step, wrap-aware
			m_tempoknob_pos  = uint8_t(m_tempoknob_pos + step);    // wrapping 8-bit encoder position -> firmware
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
	// Read the scan-matrix ports and assemble each wire segment's byte. Each port is one scan
	// column (normSeg PORT_SEG[p]); the SW-row bit forwards unchanged. OR the pressed bits into
	// their segment, then reverse-normalize each changed segment to its wire ADDR below.
	uint8_t seg_state[0x21] = { 0 };
	for (int p = 0; p < 22; p++)
	{
		const uint8_t v = m_phys[p].read_safe(0);
		if (!v)
			continue;
		for (int b = 0; b < 8; b++)
			if (BIT(v, b))
				seg_state[PORT_SEG[p]] |= (1u << b);   // identity: scan column -> normSeg, bit unchanged
	}
	for (int seg = 0; seg < 0x21; seg++)
	{
		const uint8_t addr = seg_to_addr[seg];
		if (addr == 0xff)   // no wire path
			continue;
		if (seg_state[seg] == m_btn_prev[seg])
			continue;
		m_btn_prev[seg] = seg_state[seg];
		const uint8_t pkt[2] = { addr, seg_state[seg] };
		panel_queue(pkt, 2);
	}
}

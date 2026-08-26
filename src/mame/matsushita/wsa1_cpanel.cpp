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
//  ★ THE RACK's BIT-to-LEGEND MAPPING IS NOW READ, from the SX-WSA1R service
//  manual, and every name below carries it as "(rack: LEGEND)".  The positional
//  part of the name is kept because it is what the SX-WSA1 KEYBOARD's panel
//  still is: a different board, two more scan columns, three more pots, and no
//  document for it anywhere.  So "Panel SEG3 SW5" remains the claim about the
//  WIRE, and the parenthesis is the claim about the RACK's panel only.
//
//  Where the legends come from, in descending order of strength:
//
//   1. the CP1/CP2 P.C. Diagram (PDF p.32 = manual II-29/30) PRINTS a legend
//      beside 29 of the 58 switches -- all of SEG0, SEG1, SEG2 and CP2's SEG7
//      and SEG8.  Traced by black-run extraction, not eyeballed:
//      notes/wsa1-probes/wsa1_sch_TRACE.md + wsa1_sch_{hscan,vscan,crop}.py.
//   2. prom_a's own variant-2 switch->LED table at 0xF95088 stores 0x0000 for a
//      position with no switch.  Its zero pattern reproduces the schematic
//      exactly -- 58 cells = 47 (CP1) + 11 (CP2), one hole at SEG2/SW7 = SW24 --
//      and it also settles the bit ORDER, which the four service keys could not:
//      they sit on rows SW2..SW5, a set symmetric under bit reversal, whereas
//      SEG8's two switches at bits 0,1 and SEG9's five at bits 0..4 are not.
//      15/15 checks in notes/wsa1-probes/wsa1_sch_vs_rom_matrix.py, which was
//      told nothing about the schematic.
//   3. the remaining 29 positions have no printed legend and are read off the
//      P.C. BOARD page (PDF p.31), whose orientation is fixed in BOTH axes by
//      silkscreen (the keypad reads 7,8 left to right and 7/4/1/0 top to bottom;
//      PAGE is silkscreened up on SW22 and down on SW21).  The ROM's two family
//      tags corroborate the GROUPING of these: 0x0608 covers exactly the numeric
//      family and 0x0604 exactly the LCD-navigation family, and the split falls
//      where the schematic's printed legends change.
//   4. the last reading inside (3) -- which of the two mirror-image five-key
//      columns beside the LCD is SEG3 and which is SEG9 -- was settled by the
//      FIRMWARE, not by geometry.  Screen 0x40, the DISK menu, draws FOUR
//      entries down the left of the LCD and TWO down the right; pressing rows
//      1..5 of each column moves the family-B screen to 47/4C/45/50/-- on SEG9
//      and 54/53/--/--/-- on SEG3, i.e. four live rows on SEG9 and two on SEG3,
//      exactly as the menu is drawn.  SEG9 is the LEFT column.
//      Reproduce: notes/wsa1-probes/wsa1_softkey_columns.sh.
//
//  What the ROM itself names is a FUNCTION for a handful of bits, and those are
//  marked below too: three power-on chords tested by the boot block before the
//  main loop starts (prom_a 0xF828D9, 0xF8294C, 0xF82A04), and the SX-WSA1R's
//  four SERVICE-SCREEN entries in SEG1 (0xF953CD).  ★ Those four independently
//  CONFIRM the schematic reading: SEG1 is the number pad, and manual I-11/I-12
//  names the same four service screens by the keys 2, 3, 4 and 5.
//
//  All of them are read out of the panel's own per-wire shadow at
//  RAM 0x2B20 + ((wire & 0x0F) | ((wire & 0x40) >> 2)).
//
//  ⚠ That shadow holds the LAST VALUE, not a change mask, and the difference
//  decides how the chords behave.  SC1_RxOp0_ThreeByte (prom_b 0xF5B0FD) does
//    and W,0x4F / ld XHL,0x2B20 / bit 6,W / sub W,0x30 / add L,W
//    ex (XHL),A        <- the shadow TAKES the new value, A takes the old one
//    xor A,(XHL)       <- and THAT is the change mask, which is what gets queued
//  so the byte at 0x2B20 + idx is the segment's current switch value.  Every
//  chord test below compares it for EQUALITY, which means an extra button held
//  in the same segment silently kills the chord -- the same discipline the
//  KN7000's debug chords use (notes/FINDINGS-kn7000-debug-screens.md sec.1).
//-------------------------------------------------

static INPUT_PORTS_START(wsa1_cpanel)
	PORT_START("CP_SEG0")
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG0 SW0 (rack: PLAY MODE SOUND)")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG0 SW1 (rack: PLAY MODE COMBI)")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG0 SW2 (rack: EDIT MODE SOUND)")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG0 SW3 (rack: EDIT MODE COMBI)")
	// v2 power-on chord: 0/4,0/5,0/6 held = ROM-version LED display (0xF8295F)
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG0 SW4 (rack: BANK USER 1)")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG0 SW5 (rack: BANK USER 2)")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG0 SW6 (rack: BANK ROM/EXT)")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG0 SW7 (rack: BANK RE-MAP)")

	// ★ SEG1 IS THE SX-WSA1R's SERVICE-SCREEN KEYPAD, and these are the first
	// four (position -> function) pairs any panel bit on this machine has had.
	// sub_F953CD (prom_a 0xF953CD), reached from RESET at 0xF827F8 -> 0xF40148 ->
	// 0xF952FC when the model strap says (0xC4) == 2, compares (0x2B31) -- which
	// is wire 0xC1, i.e. THIS segment -- for equality:
	//
	//     0x02 -> falls through, no screen        0xF953D8
	//     0x04 -> screen 0xD9  PANEL CPU CHECK    0xF953F4
	//     0x08 -> screen 0xDA  SINE WAVE CHECK    0xF953F9   (+ 0xF407AC / 0xF407B0)
	//     0x10 -> screen 0xDB  PANEL SW&LED CHECK 0xF9540B
	//     0x20 -> screen 0xDC  the screen cycler  0xF95410
	//
	// then stores the id in RAM (0x2070) and sets (0x2071) = 0x80.  The screen
	// titles are the display lists those ids dispatch to -- 0xF2C84D, 0xF2C88B,
	// 0xF2CA54 -- re-read from the ROM by
	// notes/wsa1-probes/wsa1_service_screen_refutation.py section 1, and EVERY
	// byte of the table above is asserted by
	// notes/wsa1-probes/wsa1_rack_service_chord.py (25 checks, 0 failures).
	//
	// ⚠ EQUALITY, so exactly one of them at a time.  ⚠ VARIANT 2 ONLY: on the
	// SX-WSA1 the same call goes to sub_F9530B instead, which reads the KEYBED
	// (see the block above the KEY0..KEY5 ports in wsa1.cpp).  The names below
	// say "rack" for that reason.
	// ⚠ AND THEY ARE NOT THE LAST WORD IN THE BOOT: the RESET block tests four
	// chords in address order -- FACTORY CLEAR 0xF827E5, then THIS one 0xF827F8,
	// then ROM VERSION 0xF8280E, then the third 0xF82813 -- and 0xF8294C's matched
	// arm never returns (`jr T` backwards at 0xF829A3).  A held ROM-version chord
	// therefore pre-empts a service screen this test already latched.
	PORT_START("CP_SEG1")
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG1 SW0 (rack: number 0)")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG1 SW1 (rack: number 1; power-on: recognised, no screen)")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG1 SW2 (rack: number 2; power-on: PANEL CPU CHECK)")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG1 SW3 (rack: number 3; power-on: SINE WAVE CHECK)")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG1 SW4 (rack: number 4; power-on: PANEL SW&LED CHECK)")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG1 SW5 (rack: number 5; power-on: screen cycler)")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG1 SW6 (rack: number 6)")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG1 SW7 (rack: number 7)")

	PORT_START("CP_SEG2")
	// v1 power-on chord: 2/0,2/1,2/2 held = ROM-version LED display (0xF82952)
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG2 SW0 (rack: number 8)")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG2 SW1 (rack: number 9)")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG2 SW2 (rack: +/-)")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG2 SW3 (rack: ENTER)")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG2 SW4 (rack: PAGE down)")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG2 SW5 (rack: PAGE up)")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG2 SW6 (rack: COMPARE)")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG2 SW7 (rack: not fitted)")

	PORT_START("CP_SEG3")
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG3 SW0 (rack: LCD soft key, RIGHT column, 1st from top)")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG3 SW1 (rack: LCD soft key, RIGHT column, 2nd)")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG3 SW2 (rack: LCD soft key, RIGHT column, 3rd)")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG3 SW3 (rack: LCD soft key, RIGHT column, 4th)")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG3 SW4 (rack: LCD soft key, RIGHT column, 5th)")
	// v2 power-on chord: 3/5,3/6,3/7 held = the third service entry (0xF82A18)
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG3 SW5 (rack: -1)")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG3 SW6 (rack: +1)")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG3 SW7 (rack: EXIT)")

	PORT_START("CP_SEG4")
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG4 SW0 (rack: under-LCD key, column 1, bottom)")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG4 SW1 (rack: under-LCD key, column 1, top)")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG4 SW2 (rack: under-LCD key, column 2, bottom)")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG4 SW3 (rack: under-LCD key, column 2, top)")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG4 SW4 (rack: under-LCD key, column 3, bottom)")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG4 SW5 (rack: under-LCD key, column 3, top)")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG4 SW6 (rack: under-LCD key, column 4, bottom)")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG4 SW7 (rack: under-LCD key, column 4, top)")

	PORT_START("CP_SEG5")
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG5 SW0 (rack: under-LCD key, column 5, bottom)")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG5 SW1 (rack: under-LCD key, column 5, top)")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG5 SW2 (rack: under-LCD key, column 6, bottom)")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG5 SW3 (rack: under-LCD key, column 6, top)")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG5 SW4 (rack: under-LCD key, column 7, bottom)")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG5 SW5 (rack: under-LCD key, column 7, top)")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG5 SW6 (rack: under-LCD key, column 8, bottom)")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG5 SW7 (rack: under-LCD key, column 8, top)")

	PORT_START("CP_SEG6")   // wire 0xC6 -- VARIANT 1 ONLY (absent from the 0xF8A189 map)
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG6 SW0")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG6 SW1")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG6 SW2")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG6 SW3")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG6 SW4")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG6 SW5")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG6 SW6")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG6 SW7")

	PORT_START("CP_SEG7")
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG7 SW0 (rack: MENU PART)")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG7 SW1 (rack: MENU SYSTEM)")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG7 SW2 (rack: MENU MIDI)")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG7 SW3 (rack: MENU DISK)")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG7 SW4 (rack: not fitted)")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG7 SW5 (rack: not fitted)")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG7 SW6 (rack: not fitted)")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG7 SW7 (rack: not fitted)")

	PORT_START("CP_SEG8")
	// power-on chord: FACTORY CLEAR.  v1 needs (0x2B38)==7 exactly, i.e. 8/0,8/1,8/2
	//                and nothing else in the segment; v2 needs 8/0,8/1 (0xF828D9)
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG8 SW0 (rack: REALTIME CREATOR 1~6)")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG8 SW1 (rack: REALTIME CREATOR RESET)")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG8 SW2 (rack: not fitted)")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG8 SW3 (rack: not fitted)")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG8 SW4 (rack: not fitted)")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG8 SW5 (rack: not fitted)")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG8 SW6 (rack: not fitted)")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG8 SW7 (rack: not fitted)")

	PORT_START("CP_SEG9")
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG9 SW0 (rack: LCD soft key, LEFT column, 1st from top)")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG9 SW1 (rack: LCD soft key, LEFT column, 2nd)")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG9 SW2 (rack: LCD soft key, LEFT column, 3rd)")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG9 SW3 (rack: LCD soft key, LEFT column, 4th)")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG9 SW4 (rack: LCD soft key, LEFT column, 5th)")
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG9 SW5 (rack: not fitted)")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG9 SW6 (rack: not fitted)")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG9 SW7 (rack: not fitted)")

	PORT_START("CP_SEG10")  // wire 0xCA -- VARIANT 1 ONLY (absent from the 0xF8A189 map)
	PORT_BIT(0x01, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG10 SW0")
	PORT_BIT(0x02, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG10 SW1")
	PORT_BIT(0x04, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG10 SW2")
	PORT_BIT(0x08, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG10 SW3")
	PORT_BIT(0x10, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG10 SW4")
	// v1 power-on chord: 10/5,10/6,10/7 held = the third service entry (0xF82A0A)
	PORT_BIT(0x20, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG10 SW5")
	PORT_BIT(0x40, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG10 SW6")
	PORT_BIT(0x80, IP_ACTIVE_HIGH, IPT_KEYBOARD) PORT_NAME("Panel SEG10 SW7")
	// Wire 0xD3.  The handler at prom_a 0xF89A8B is the one analogue channel with no
	// (0xC4) test at all -- i.e. present on both variants -- and it maps the byte through
	// the plain, strictly monotone 0..127 ramp at 0xF89AB4 (no plateau anywhere in it).
	// The rack's mechanical parts list has exactly one VOLUME KNOB.
	PORT_START("CP_VOLUME")
	PORT_ADJUSTER(80, "VOLUME")

	// Wire 0xD7.  Its dispatch slot (prom_a 0xF89825 entry 31 -> 0xF89AAD) is a bare
	// `scf` -- no curve, no previous-value compare -- so every packet is accepted.  A
	// control that must never be de-duplicated is a RELATIVE encoder, and the KN5000's
	// twin protocol uses the same wire address 0xD7 for its endless wheel as
	// [0xD7, signed detent count] (kn5000_cpanel.cpp:269-271).  The rack's parts list
	// has exactly one DIAL WHEEL.  ⚠ The SIGNED-STEP ENCODING IS INFERRED from those
	// two facts; nothing in prom_a's group-0x0F consumer has been read.
	PORT_START("CP_DIAL")
	PORT_BIT(0xff, 0x00, IPT_DIAL) PORT_SENSITIVITY(25) PORT_KEYDELTA(1) PORT_NAME("DATA ENTRY DIAL")

	// The SAME wheel, dragged in a circle by src/mame/layout/wsa1r.lay's widget
	// script, which writes it through user_value.  It cannot be the field above:
	// an analog field's only Lua write path, set_value(), latches
	// m_use_adjoverride permanently and detaches the field from the input system,
	// so one drag would kill the keys and the mouse axis for the rest of the
	// session.  An adjuster's user_value has no such side effect, so the two
	// controls coexist and scan_tick() sums their wrap-aware deltas.  Same split,
	// and for the same reason, as the KN5000's ENCODER / ENCODER_DRAG pair
	// (kn5000_cpanel.cpp).  It carries no key binding and needs none.
	PORT_START("CP_DIAL_DRAG")
	PORT_ADJUSTER(50, "DATA ENTRY DIAL (mouse drag)")
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
	m_scan_timer(nullptr), m_byte_timer(nullptr), m_req_timer(nullptr),
	m_requesting(false),
	m_vol_prev(0), m_vol_synced(false),
	m_dial_prev(0), m_dial_synced(false),
	m_dial_drag_prev(0), m_dial_drag_synced(false),
	m_atn_cb(*this), m_busy_cb(*this), m_sclk_cb(*this), m_rxd_cb(*this),
	m_seg(*this, "CP_SEG%u", 0U),
	m_volume(*this, "CP_VOLUME"),
	m_dial(*this, "CP_DIAL"),
	m_dial_drag(*this, "CP_DIAL_DRAG"),
	m_led_out(*this, "led%u", 0U)
{
	std::fill(std::begin(m_frame), std::end(m_frame), 0);
	std::fill(std::begin(m_resp), std::end(m_resp), 0);
	std::fill(std::begin(m_seg_prev), std::end(m_seg_prev), 0);
	std::fill(std::begin(m_led), std::end(m_led), 0);
}


void wsa1_cpanel_device::device_start()
{
	m_scan_timer = timer_alloc(FUNC(wsa1_cpanel_device::scan_tick), this);
	m_byte_timer = timer_alloc(FUNC(wsa1_cpanel_device::deliver_byte), this);
	m_req_timer  = timer_alloc(FUNC(wsa1_cpanel_device::request_tick), this);

	save_item(NAME(m_variant));
	save_item(NAME(m_frame));
	save_item(NAME(m_pos));
	save_item(NAME(m_len));
	save_item(NAME(m_resp));
	save_item(NAME(m_resp_len));
	save_item(NAME(m_resp_pos));
	save_item(NAME(m_rx_enabled));
	save_item(NAME(m_requesting));
	save_item(NAME(m_last_tx));
	save_item(NAME(m_seg_prev));
	save_item(NAME(m_vol_prev));
	save_item(NAME(m_vol_synced));
	save_item(NAME(m_dial_prev));
	save_item(NAME(m_dial_synced));
	save_item(NAME(m_dial_drag_prev));
	save_item(NAME(m_dial_drag_synced));
	save_item(NAME(m_led));
}


void wsa1_cpanel_device::device_reset()
{
	m_pos = 0;
	m_len = 2;
	m_resp_len = m_resp_pos = 0;
	m_rx_enabled = false;
	m_requesting = false;
	m_last_tx = attotime::zero;
	m_byte_timer->reset();
	m_req_timer->reset();
	std::fill(std::begin(m_seg_prev), std::end(m_seg_prev), 0);
	m_vol_synced = false;
	m_dial_synced = false;
	m_dial_drag_synced = false;

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
//  prom_b 0xF5ADD7 (transmit, SC1_State08_TxFromRing) and 0xF5AF33
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
	m_last_tx = machine().time();

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
			led_frame(addr, m_frame[2 + i]);
		return;
	}

	const u8 addr = hdr, data = m_frame[1];

	// The LED wire table is the authority, not the shape of the address: in variant 2
	// register 7 maps to wire address 0x00, and Panel_RefreshLeds walks all EIGHT
	// registers in BOTH variants (`ld B,0x08` at prom_a 0xF8C456), so that frame really
	// is emitted and it does not look like an LED address at all.
	if (led_frame(addr, data))
		return;

	if ((addr & 0xf0) == 0xc0)
	{
		LOGMASKED(LOG_LED, "LED frame for a wire address this variant does not map: %02X = %02X\n",
				addr, data);
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
	// ⚠ The header byte itself is a CHOICE: 0xD8 is type 3 (bits 5:3) with bits 7:6 = 11,
	// which is what every live address on THIS link carries.  The KN5000 sends 0x18, the
	// same type with bits 7:6 = 00.  Only the TYPE field is decoded by the receiver, so
	// both work; the exact byte a real M37471M2196S sends here is unknown.
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
//
//  ⚠ EIGHT in both variants.  Variant 2's table ends C1 C2 C9 CA CB CC C3 00,
//  and the 0x00 is a wire address the loop still emits -- it is NOT a seven-
//  register variant, and counting the non-zero entries (as an earlier version of
//  this file did) gets that wrong.
//-------------------------------------------------

bool wsa1_cpanel_device::led_frame(u8 addr, u8 data)
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
			return true;
		m_led[reg] = data;
		for (int bit = 0; bit < 8; bit++)
			m_led_out[reg * 8 + bit] = BIT(data, bit);
		LOGMASKED(LOG_LED, "LED reg %d (wire %02X) = %02X\n", reg, addr, data);
		return true;
	}
	return false;
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

//  EVERY MESSAGE THIS DEVICE SENDS IS EXACTLY TWO BYTES, and the queue is a FIFO
//  of two-byte messages rather than a byte stream, because the CPU's receive
//  state machine is per MESSAGE: INT6_SC1_PeerRequest accepts one request,
//  SC1_State20_RxFirstByte takes the length from the first byte -- 2 for every
//  address this device uses, since (addr & 0x3F) < 0x30 for 0xC0..0xD7 -- and
//  SC1_State24_RxNextByte re-arms INT6 when the count runs out.  Concatenating
//  two messages into one delivery would hand the second one to a state machine
//  that has stopped expecting bytes.
void wsa1_cpanel_device::queue_frame(const u8 *bytes, int n)
{
	if (m_resp_pos >= m_resp_len)
		m_resp_pos = m_resp_len = 0;
	if (m_resp_len + n > RESP_MAX)
		return;                              // the real MCU's queue would drop it too
	const bool was_idle = (m_resp_pos == m_resp_len);
	for (int i = 0; i < n; i++)
		m_resp[m_resp_len++] = bytes[i];
	if (was_idle && !m_requesting)
		start_request();
}


void wsa1_cpanel_device::start_request()
{
	m_requesting = true;
	m_req_timer->adjust(attotime::zero, 0);
}


//-------------------------------------------------
//  the attention line: A PULSE, AND A RETRY
//
//  ⚠ THIS IS A DRIVER POLICY, and it is here because holding the line high does
//  not work.  INT6's request flag is bit 3 of INTE67, and the SC1 module writes
//  that register with bit 3 CLEAR at eighteen sites -- 0x85 to arm INT6 at level
//  5 and 0x8F to park it at level 7, which tlcs900_check_irqs() never dispatches
//  (prom_b 0xF5A947, 0xF5ABD6 and sixteen more).  A request raised while the
//  module is transmitting therefore latches into a masked flag and is then
//  THROWN AWAY by the very write that re-arms INT6.  Measured: with the line
//  held, CPU 1 transmitted its opening frames and then never entered state 0x20
//  at all (notes/wsa1-probes/wsa1_sc1_handshake.lua).
//
//  So the panel asks again: a short pulse, repeated every 2 ms until the CPU
//  turns RXE on.  A real peer that can lose an edge this way has to do the same
//  thing; what is NOT established is the real part's pulse width or its retry
//  interval, and neither number below is claimed to be the hardware's.
//
//  The busy line is NOT raised while merely asking.  PB bit 4 blocks CPU 1 from
//  transmitting at all (prom_b 0xF5AB7B), so asserting it before the CPU has
//  accepted the request would be the panel silencing the very conversation it is
//  trying to join.  It goes high when the transfer actually starts, in
//  rx_enable(), and low again when the last byte has been handed over.
//-------------------------------------------------

TIMER_CALLBACK_MEMBER(wsa1_cpanel_device::request_tick)
{
	if (!m_requesting)
	{
		m_atn_cb(0);
		return;
	}

	if (param == 0)
	{
		// ★ NEVER ASK WHILE CPU 1 IS MID-FRAME.  This is not a nicety; it is what
		// kept every button press from doing anything.  INT6_SC1_PeerRequest
		// (prom_b 0xF5AC0A) opens `cp (0x2A81),0x00` -- the bytes-still-expected
		// counter, which the module uses for TRANSMIT as well as receive -- and if
		// it is NOT zero it takes the arm at 0xF5AC3C, which does
		//
		//     if ((0x2A92) == 0) (0x2A92) = 0x4C ;  decw 1,(0x2A92)
		//
		// i.e. it STEPS THE RX RING'S WRITE INDEX BACK ONE, on the assumption that
		// the peer will re-send the byte it just took.  This device never re-sends,
		// so every such edge desynchronises the ring by one byte permanently.
		//
		// MEASURED before this guard (notes/wsa1-probes/wsa1_sc1_ring_phase.lua):
		// three INT6 dispatches land during CPU 1's opening transmits at t = 0.326,
		// 0.334 and 0.342 s, walking the write index 0 -> 0x4C -> 0x49 while the read
		// index is still 0.  The reader then chews 27 empty slots and meets the
		// writer at 0x4A with ODD parity, after which SC1_RxOp0_ThreeByte pairs the
		// PREVIOUS message's data byte with THIS message's address byte for the rest
		// of the session -- so a press of wire 0xC7 wrote 0xC7 into shadow slot 0
		// instead of 0x08 into slot 0x17, and no screen and no lamp ever moved.
		//
		// The quiet window covers the part m_pos cannot: the firmware sets (0x2A81)
		// before it has written the first byte to SC1BUF and clears it after the last
		// (0xF5ADD7 / 0xF5AF82), so "no frame half-way in" is necessary but not
		// sufficient.  ⚠ 1 ms is a DRIVER CHOICE like the pulse width above it, not
		// a number from any datasheet.
		if (m_pos != 0 || (machine().time() - m_last_tx) < attotime::from_usec(1000))
		{
			m_req_timer->adjust(attotime::from_usec(2000), 0);
			return;
		}
		m_atn_cb(1);
		m_req_timer->adjust(attotime::from_usec(50), 1);
	}
	else
	{
		m_atn_cb(0);
		m_req_timer->adjust(attotime::from_usec(2000), 0);
	}
}


void wsa1_cpanel_device::rx_enable(int state)
{
	m_rx_enabled = bool(state);

	if (!m_rx_enabled || m_resp_pos >= m_resp_len)
		return;

	// The CPU has accepted: stop asking, take the link, and start clocking bytes in.
	m_requesting = false;
	m_req_timer->reset();
	m_atn_cb(0);
	m_busy_cb(1);
	m_byte_timer->adjust(attotime::from_usec(60), 0);
}


TIMER_CALLBACK_MEMBER(wsa1_cpanel_device::deliver_byte)
{
	if (m_resp_pos >= m_resp_len)
		return;

	m_rxd_cb(m_resp[m_resp_pos++]);

	// param counts bytes within THIS message: 0 was the address, 1 was the data.
	if (param == 0)
	{
		m_byte_timer->adjust(attotime::from_usec(120), 1);
		return;
	}

	// Message complete: give the link back.  Anything still queued has to ask again,
	// because the firmware re-arms INT6 at the end of a message and expects the next
	// one to arrive the same way this one did.
	m_busy_cb(0);
	m_atn_cb(0);

	if (m_resp_pos >= m_resp_len)
		m_resp_pos = m_resp_len = 0;
	else
		start_request();
}



//-------------------------------------------------
//  the periodic scan
//
//  Buttons are reported as [0xC0 | segment][bitmask].  The header's type field
//  falls out of the segment number for free -- segments 0..7 give type 0 and
//  8..15 type 1, which is exactly why SC1_RxOpTable entries [0] and [1] are
//  the same handler.  SC1_RxOp0_ThreeByte then XORs the mask against its own
//  shadow at RAM 0x2B20 + ((addr & 0x0F) | ((addr & 0x40) >> 2)) -- the +0x10 is
//  CONDITIONAL on address bit 6 (prom_b 0xF5B0FD does `and W,0x4F` and then
//  `sub W,0x30` only when bit 6 is set), which is true of every 0xC0..0xCF
//  address but is not the rule -- and hands the foreground
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
	//
	// TWO controls feed one wheel: the IPT_DIAL (keys and the mouse axis, 256 positions)
	// and the layout's drag adjuster (0..100, wrapped by the script).  Both are relative,
	// so their deltas simply add; neither one's absolute value means anything.
	{
		s32 d = dial_delta(m_dial, m_dial_prev, m_dial_synced, 256);
		d += dial_delta(m_dial_drag, m_dial_drag_prev, m_dial_drag_synced, 101);
		if (d != 0)
		{
			const s8 step = s8(std::clamp<s32>(d, -64, 63));
			const u8 pkt[2] = { 0xd7, u8(step) };
			queue_frame(pkt, 2);
		}
	}
}


//-------------------------------------------------
//  one relative control's movement since the last scan
//
//  Wrap-aware, because both fields wrap: the IPT_DIAL at 256 and the layout's
//  adjuster at 101 (the script does `user_value = (user_value + n) % 101`).  The
//  first read only ADOPTS the position -- a step reported before the firmware is
//  servicing the link would sit in the queue and block every later request.
//-------------------------------------------------

s32 wsa1_cpanel_device::dial_delta(optional_ioport &port, s32 &prev, bool &synced, s32 modulus)
{
	if (!port)
		return 0;

	const s32 pos = port->read();
	s32 d = pos - prev;
	if (d > modulus / 2) d -= modulus;
	else if (d < -modulus / 2) d += modulus;

	prev = pos;
	if (!synced)
	{
		synced = true;
		return 0;
	}
	return d;
}

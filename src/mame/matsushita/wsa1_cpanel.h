// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    Technics SX-WSA1 / SX-WSA1R control panel HLE

    One Mitsubishi M37471M2196S on the CONTROL PANEL 1 board -- the same part
    number as the two panel MCUs kn5000_cpanel.cpp emulates -- scanning this
    machine's button matrix and driving its LEDs, and talking to CPU 1 over
    the TMP95C061's SERIAL CHANNEL 1 in I/O-interface (synchronous) mode.

    WHY SC1 IS THE PANEL, and not the 0x7B0004/0x7A0000 subsystem
    ------------------------------------------------------------
    Measured, not argued.  Take the 3,150 bytes of CPU 1's SC1 module
    (prom_b 0xF5A800-0xF5B44D) and the whole 2 MiB of the KN5000's v10 main
    program ROM, and list every common substring of 16 bytes or more.  There
    are EIGHT, 154 bytes in all, and ALL EIGHT land inside the KN5000's
    control-panel driver, 0xFC3E65-0xFC4C33 -- 3,535 bytes, 0.169% of that ROM.
    (The window is bounded by the KN5000 symbol file itself: CPanel_InitDispatchTable
    at 0x00FC3E65, CPanel_DecEventPtr at 0x00FC4C29, ToneGen_IncrementWrap128
    at 0x00FC4C34.)

    ★ THE NULL, which is what makes this a result rather than a coincidence.
    Run the same maximal-common-substring scan over the WHOLE 512 KiB of prom_b
    against the same KN5000 ROM: 4,399 runs, 126,327 bytes.  Exactly EIGHT of
    them land inside the panel driver, and all eight are the SC1 module's.  A
    bijection, not a cluster.
    Reproduce: notes/wsa1-probes/wsa1_kn5000_panel_bytediff.py (the module scan)
    and notes/wsa1-probes/wsa1_panel_report_refutation.py --selftest (the null).

    The correspondence is routine for routine, at the same offset inside the
    routine (notes/wsa1-probes/wsa1_kn5000_panel_map.py):

      WSA1 SC1_RxOp6_Run      0xF5B179  ==  KN5000 CPanel_RX_MultiBytePacket 0xFC4A40   22/22 bytes
      WSA1 SC1_RxOp6_Run+0x22           ==  KN5000 CPanel_RX_MultiBytePacket+0x22       15 bytes
      WSA1 SC1_RxOp0_ThreeByte+0x2E     ==  KN5000 CPanel_RX_ButtonPacket+0x2E          12 bytes
      WSA1 SC1_State20_RxFirstByte+0x2F ==  KN5000 CPanel_SM_RXByte1+0x2F               10 bytes
      WSA1 SC1_State04_TxByte1+0x1F     ==  KN5000 CPanel_SM_StartTX+0x1F                8 bytes
      WSA1 INTTX1_SC1_Dispatch+0x10     ==  KN5000 INTTX1_HANDLER+0x10                   8 bytes
      WSA1 SC1_WaitTicks2/6/51          ==  KN5000 DELAY_{2,6,51}_TICKS  (same 2/6/51!)

    And the two packet dispatchers are THE SAME INSTRUCTION with a different
    table pointer -- ten bytes, of which THREE differ (offsets 2, 3 and 4, the
    low three bytes of the 32-bit immediate; the fourth immediate byte is 0x00
    in both):

      WSA1  0xF5B0AB: eb c8 b5 b0 f5 00 a3 23 b3 d8   add XHL,SC1_RxOpTable
      KN5K  0xFC4959: eb c8 65 49 fc 00 a3 23 b3 d8   add XHL,CPanel_RX_PacketHandlers
      WSA1  0xF5B28F: eb c8 99 b2 f5 00 a3 23 b3 d8   add XHL,SC1_TxOpTable
      KN5K  0xFC4B79: eb c8 85 4b fc 00 a3 23 b3 d8   add XHL,CPanel_LED_PacketHandlers

    and the tables they name have the same shape and the same grouping:

      RX  8 entries   [0][1] button   [2] analogue   [3][4][5] sync   [6][7] multi-byte
      TX  4 entries   [0][1][2] two-byte LED frame   [3] multi-byte LED frame

    That closes gap E of notes/WSA1-EMULATION-DISASM-GAPS.md.  Three of the four
    WSA1 receive handlers get their name from the KN5000 symbol at the matching
    slot; the fourth, slot 2, is CPanel_RX_EncoderPacket there and is called
    "analogue" here because prom_a's own curve dispatcher treats all of
    0xD0..0xD7 alike, which is a WSA1 fact rather than a KN5000 name.

    Gap B (what the 0x7A0000 / 0x7B0004 device is) is closed by its own evidence
    and not by elimination.  Dev7A_StartDma (prom_a 0xFE596A) selects on ten
    command bytes and every one of them is a legal uPD765 command with exactly
    the MT/MFM flags that command may carry: 0x4D FORMAT|MFM, 0xC5/0xC9
    WRITE/WRITE-DELETED|MT|MFM, 0xC6/0xCC READ/READ-DELETED|MT|MFM, 0x42 READ
    TRACK|MFM, 0x4A READ ID|MFM, 0xD1/0xD9/0xDD SCAN EQ/LE/HE|MT|MFM.  Only 59
    of the 256 byte values are legal uPD765 commands, so ten arbitrary bytes all
    landing legal has probability ~4.2e-7.  prom_a 0xFE6891 then does
    `and L,0xF0 / cp L,0x80` (RQM=1, DIO=0, EXM=0, CB=0) and pushes 0x08 --
    SENSE INTERRUPT STATUS, the textbook post-reset result drain.  The parts
    list has a uPD72070GF3BE.
      ⚠ 10/10 on the opcodes, 7/10 on the DIRECTION: the three SCAN commands
        (0xD1, 0xD9, 0xDD) need a CPU->FDC data phase and sit in the device->RAM
        group.  Recorded, not explained.
      ⚠ That 0x7A0000 and 0x7B0004/5 are ONE device is not shown here; it is
        wsa1-roms-disasm/notes/FINDINGS-dev7b-and-int5.md:107-109 that shows it,
        and this note leans on that file.

    THE WIRE
    --------
    P8.3 = TXD1 -> panel SIN        P8.5 = SCLK1, driven by whoever transmits
    P8.4 = RXD1 <- panel SOUT       INT6 <- the panel's attention/request line
    PB.4 <- the panel's busy line   (idle: P8.5 high AND PB.4 LOW -- 0xF5AB7B)

    ⚠ The PIN NAMES are the databook's, and no databook is in these trees.  What
    IS established is that the SC1 module owns bits 3 and 5 of P8CR/P8FC, reads
    P8 bit 5 and PB bit 4 as inputs, and will not transmit unless P8.5 reads
    HIGH and PB.4 reads LOW (0xF5AB7B `bit 5,(P8)` / `bit 4,(PB)`).

    SC1MOD = 0x00 (0xF5A8AF) is I/O-interface mode.  SC1CR bit 0 is the clock
    source and the firmware flips it at every turn of the conversation: cleared
    in SC1_StartWordTx (0xF5ABFC, the CPU clocks out), set in
    INT6_SC1_PeerRequest (0xF5AC1E, the panel clocks in).  ⚠ That named pair is
    one of FOUR `or (SC1CR),0x01` sites and one of NINE `and (SC1CR),0xFE`
    sites; "flips at every turn" describes the two turns that were read, not a
    census.  Half duplex, one INT6 per inbound MESSAGE.

    THE FRAME, from the firmware's own length rule -- prom_b 0xF5ADD7 (transmit)
    and 0xF5AF33 (receive; 0xF5AF41 is inside the preceding instruction, not a
    boundary):

        len = ((first & 0x3F) >= 0x30) ? (first & 0x0F) + 3 : 2

    so every frame is [ADDR][DATA] unless bits 5:4 of the address byte are 11,
    in which case it is [HDR][FIRST_ADDR][DATA] x ((HDR & 0x0F) + 1).

    THE ADDRESS BYTE -- FOUR MASKS, NOT ONE FIELD LAYOUT
    ---------------------------------------------------
    There is no single bit-field decode to state, because the firmware reads the
    same byte through four different masks in four places.  All four are quoted
    from the instruction that computes them:

      0xF5B0A1  (a & 0x38) >> 1        byte offset into SC1_RxOpTable (8 x LE32)
                                       -- this is the PACKET TYPE, bits 5:3
      0xF8A0A3  (a & 0x1F) | ((a & 0xC0) >> 1)
                                       index into the wire -> group table.  Bit 5
                                       is a DON'T CARE here, so 0xC0 and 0xE0
                                       alias onto one entry
      0xF89807  ((a & 0xC0) >> 1) | ((a & 7) << 2)
                                       byte offset into the 32-entry analogue
                                       CURVE table.  Masks a & 7, so 0xC3 and
                                       0xD3 land in the same slot
      0xF5B0FD  W = a & 0x4F; if (W & 0x40) W -= 0x30; -> 0x2B20 + W
                                       the button change-mask shadow.  Only 16 of
                                       the 32 shadow bytes are reachable from
                                       addresses with bit 6 set

    ⚠ Bits 7:6 are NOT a "panel id".  In the curve dispatcher they select one of
    four SOURCE BANKS and bank 00 is live: the thunk 0xF405F0 (= jp 0xF89800)
    has EIGHT prom_a callers -- 0xF8DC63, 0xF8DC96, 0xF8DCC9, 0xF8DCFC, 0xF8DD54,
    0xF8DD69, 0xF8DDC3, 0xF8DDD8 -- each immediately preceded by `ld W,0x00`..
    `0x05` (channels 4 and 5 are called from two sites each), which are CPU 1's
    own six on-chip analogue channels.  So 00 = the A/D converter and 11 =
    the panel link; neither ROM ever compares those two bits with a constant.
    In practice every address that arrives over THIS link has bits 7:6 = 11,
    which is why 0xC0..0xCF are button segments and 0xD0..0xD7 analogue controls.

    THE MODEL STRAP -- PB BIT 0
    ---------------------------
    prom_a 0xF82882, called from RESET at 0xF827D8, is the only write to RAM
    (0xC4) in 512 KiB:

        ld A,0x01 / bit 0,(PB) / jr NZ,+2 / ld A,0x02 / ld (0xC4),A / ret

    PB.0 HIGH -> (0xC4)=1, PB.0 LOW -> (0xC4)=2, and ONE HUNDRED AND ELEVEN
    well-formed `cp (0xC4),#imm / jr cc` sites across 27 distinct 4 KiB blocks
    branch on it (109 in prom_a, 2 in prom_b at 0xF440C4 and 0xF44582).  Roughly
    a third of them are in the panel / analogue / LED region; the panel's own two
    TABLES are the wire-address -> group map (0xF8A109 for 1, 0xF8A189 for 2) and
    the LED-register -> wire-address map (0xF8C8AC for 1, 0xF8C8B7 for 2).

        (0xC4)=1  eleven button segments 0xC0..0xCA, four pots 0xD0..0xD3,
                  encoder 0xD7, LED wires C0 C1 C2 C4 C5 C9 CC CD
        (0xC4)=2  nine button segments (0xC6 and 0xCA absent), ONE pot 0xD3,
                  encoder 0xD7, LED wires C1 C2 C9 CA CB CC C3 00

    ⚠ EIGHT LED registers are walked in BOTH variants: Panel_RefreshLeds
    (0xF8C456) starts `ld B,0x08` either way, so variant 2's eighth slot really
    is emitted, with wire address 0x00.

    WHICH ARM IS WHICH MODEL is corroboration, not decode.  No string in any of
    the four images names either model, and only the SX-WSA1R's service manual
    is available here -- there is no SX-WSA1 document to check the other arm
    against.  Two independent readings of the rack's own manual point the same
    way:

      * its specification page lists the disk menu as DISK LOAD, DISK SAVE,
        MIDI FILE DIRECT PLAY, DISK FORMAT, LOAD SINGLE SOUND, LOAD SINGLE
        COMBINATION -- no MIDI FILE LOAD and no MIDI FILE SAVE, which is exactly
        the difference between the two display lists prom_a 0xFF42EE picks
        between (0xF580B0 has all four entries, 0xF58127 only the last two);
      * its MECHANICAL PARTS LIST has one VOLUME KNOB and one DIAL WHEEL and no
        bender or wheel of any other kind.  Variant 2 keeps exactly one pot
        (0xD3) and one encoder (0xD7), and the three channels it drops are the
        ones a rack has no room for: 0xD0 and 0xD1 and 0xD2 each carry their own
        `cp (0xC4),0x02` gate (0xF89A2A, 0xF899FA, 0xF89A5B) that substitutes a
        FIXED REST VALUE (0x00, 0x80, 0x40) and returns no-carry, while 0xD3's
        handler (0xF89A8B) has no strap test at all.  Two of the three dropped
        curves are CENTRE-DETENTED -- 0xF89CB4 has 18 x 0x80 at index 120 of 256
        and 0xF89B34 has 13 x 0x40 at index 58 of 128 -- i.e. sprung bipolar
        controls, which is what a keyboard has and a rack does not.

    ⚠ NOT the count of "continuous controls" on the specification page.  That
    line reads "OTHERS VOLUME, DATA ENTRY DIAL/KEYS, COMPARE", which is an
    "others" row and not a control census; an earlier version of this note used
    it as a second independent match and it is not one.

    ★ THE RACK's MATRIX IS NOW READ.  An earlier version of this note said
    "NOT ESTABLISHED: which physical button is which bit, and which LED is
    which bit"; that was true of the manual's PANEL page alone.  The CP1/CP2
    P.C. DIAGRAM (PDF p.32 = manual II-29/30) prints a legend beside 29 of the
    58 switches and the P.C. BOARD page (p.31) places the other 29, and prom_a's
    own switch->LED table at 0xF95088 agrees with both on segment, bit and
    population (15/15, notes/wsa1-probes/wsa1_sch_vs_rom_matrix.py).  Every
    ioport below now carries its rack legend, and src/mame/layout/wsa1r.lay
    binds all 58 with a per-button provenance tier.

    ★ AND THE LAST GEOMETRIC READING WAS SETTLED BY THE FIRMWARE.  Which of the
    two mirror-image five-key columns beside the LCD is SEG3 and which is SEG9
    rested on the board page's orientation alone.  The DISK menu (family-B screen
    0x40) draws FOUR entries down the left of the LCD and TWO down the right;
    pressing rows 1..5 of each column moves the screen to 47/4C/45/50/-- on SEG9
    and 54/53/--/--/-- on SEG3.  Four live rows on SEG9, two on SEG3 -- SEG9 is
    the LEFT column.  notes/wsa1-probes/wsa1_softkey_columns.sh.

    ⚠ STILL NOT ESTABLISHED:
      * which of {reg2 bit0, reg2 bit1, reg3 bit0, reg3 bit1} is which of the
        four REALTIME CREATOR ring lamps.  The SET is fixed by the ROM; the
        order is not, and the layout leaves those four unbound.
    ⚠ And NONE of it transfers to the SX-WSA1 KEYBOARD (variant 1), which is a
    different panel board with two more scan columns and three more pots, and
    for which no document exists in these trees.

***************************************************************************/

#ifndef MAME_MATSUSHITA_WSA1_CPANEL_H
#define MAME_MATSUSHITA_WSA1_CPANEL_H

#pragma once

class wsa1_cpanel_device : public device_t
{
public:
	wsa1_cpanel_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock = 0);

	// 1 = the SX-WSA1 keyboard's panel, 2 = the SX-WSA1R rack's panel.  MUST agree with
	// whatever the driver returns for PB bit 0, because the firmware derives (0xC4) from
	// that pin and this device's maps have to be the ones the firmware is using.  The
	// driver pushes it from machine_reset(), so flipping the PORT_CONFNAME takes effect
	// on the next reset -- which is what a strap does.
	void set_variant(u8 v) { m_variant = v; }

	// --- to CPU 1 ---
	auto atn()  { return m_atn_cb.bind(); }    // the panel's request line -> INT6
	auto busy() { return m_busy_cb.bind(); }   // PB bit 4: 1 while the panel holds the link
	auto sclk() { return m_sclk_cb.bind(); }   // P8 bit 5: 1 when the clock line is idle high
	auto rxd()  { return m_rxd_cb.bind(); }    // one byte -> SC1BUF, and raise INTRX1

	// --- from CPU 1 ---
	void tx_byte(u8 data);        // sc1buf_w: one byte clocked out to the panel
	void rx_enable(int state);    // SC1MOD bit 5 (RXE): the firmware is ready to receive

	// Firmware-authoritative LED state, for a layout or a debug view.
	u8 led_register(int n) const { return (n >= 0 && n < 8) ? m_led[n] : 0; }

protected:
	virtual void device_start() override ATTR_COLD;
	virtual void device_reset() override ATTR_COLD;
	virtual ioport_constructor device_input_ports() const override ATTR_COLD;

	TIMER_CALLBACK_MEMBER(scan_tick);     // periodic matrix + analogue scan
	TIMER_CALLBACK_MEMBER(deliver_byte);  // one queued reply byte
	TIMER_CALLBACK_MEMBER(request_tick);  // the attention line's pulse / retry

private:
	static constexpr int NUM_SEG = 11;    // SEG0..SEG10, the CP1 MCU's scan lines
	static constexpr int RESP_MAX = 64;

	void queue_frame(const u8 *bytes, int n);
	void start_request();
	void frame_complete();
	bool led_frame(u8 addr, u8 data);
	bool segment_is_wired(int seg) const;
	static s32 dial_delta(optional_ioport &port, s32 &prev, bool &synced, s32 modulus);

	u8 m_variant;

	// Inbound frame assembly (CPU -> panel).  m_len is set from the first byte by the
	// firmware's own rule, so a run frame is consumed whole.
	u8  m_frame[19];              // max = (0x0F) + 3 = 18, plus one for safety
	int m_pos, m_len;

	// Outbound queue (panel -> CPU).
	u8  m_resp[RESP_MAX];
	int m_resp_len, m_resp_pos;
	bool m_rx_enabled;

	emu_timer *m_scan_timer;
	emu_timer *m_byte_timer;
	emu_timer *m_req_timer;
	bool m_requesting;            // a message is queued and INT6 has not been taken yet
	attotime m_last_tx;           // when CPU 1 last put a byte on the wire (see request_tick)

	// Scan shadows, so only CHANGED segments are reported -- which is what the firmware's
	// own change-mask table at RAM 0x2B20 expects to be fed.
	u8   m_seg_prev[NUM_SEG];
	u8   m_vol_prev;
	bool m_vol_synced;
	s32  m_dial_prev;
	bool m_dial_synced;
	s32  m_dial_drag_prev;
	bool m_dial_drag_synced;

	devcb_write_line m_atn_cb;
	devcb_write_line m_busy_cb;
	devcb_write_line m_sclk_cb;
	devcb_write8     m_rxd_cb;

	optional_ioport_array<NUM_SEG> m_seg;
	optional_ioport m_volume;   // wire 0xD3
	optional_ioport m_dial;      // wire 0xD7, the DATA ENTRY DIAL (keys / mouse axis)
	optional_ioport m_dial_drag; // the SAME wheel, dragged in a circle by the layout

	// 8 LED registers x 8 bits, output led%u with %u = register*8 + bit.  The NAME stays
	// positional because the wire position is what the ROM establishes for BOTH variants;
	// which lamp sits there is a per-variant fact and belongs in the layout.
	//
	// ★ For the RACK, 14 of the 18 lamps are now identified, and from the firmware rather
	// than from the schematic.  prom_a's variant-2 switch->LED table at 0xF95088 holds one
	// u16 per switch, and that u16 is (register << 8) | bit mask: sub_F94E1C reads it with
	// `ld WA,(XHL)` and calls 0xF40670, which is `jp 0xF8C846` -- the unguarded entry of
	// Panel_SetLedRegister -- and that routine maps W through the register->wire table
	// (0xF8C8B7 for variant 2) and queues [wire][A].  W is therefore the register and A the
	// data byte.  A button with its own indicator lights its own indicator, so:
	//
	//   reg1 bits 0..3  PLAY MODE SOUND / COMBI, EDIT MODE SOUND / COMBI   (D116-119, green)
	//   reg0 bits 0..3  BANK USER 1 / USER 2 / ROM-EXT / RE-MAP            (D120-123, red)
	//   reg4 bits 0,1   MENU PART / MENU SYSTEM                            (D160, D161, green)
	//   reg5 bits 0,1   MENU MIDI / MENU DISK                              (D162, D163, green)
	//   reg6 bit 2      COMPARE          (D130, red)   -- the LCD-key family indicator
	//   reg6 bit 3      MIDI/NUMBER PAD  (D131, green) -- the numeric family indicator
	//
	// and {reg2 bit0, reg2 bit1, reg3 bit0, reg3 bit1} are the four REALTIME CREATOR ring
	// lamps as a SET, in an order nothing read so far pins down.
	// Reproduce every line of that: notes/wsa1-probes/wsa1_lamp_identification.py.
	//
	// ★ ONLY 47 OF THE 64 ARE REAL LAMPS, and the firmware says so itself.  The PANEL
	// SW&LED CHECK screen's all-on sweep (sub_F956B0, prom_a 0xF956B0) walks the word
	// table at 0xF95C68 until 0xFFFF, writing register index and data as pairs, and that
	// table is exactly eight entries:
	//
	//     reg0=FF reg1=FF reg2=FF reg3=FF reg4=FF reg5=03 reg6=0F reg7=02   -> 47 bits
	//
	// The driver's output index is reg*8 + bit, so the SEVENTEEN outputs the firmware's
	// own all-lamps test never lights are led42-47, led52-56 and led58-63.  DO NOT wire a
	// layout lamp to any of those.  Cross-checked, and this is what makes 47 a measurement
	// rather than a reading: the union of every mask in the two switch->LED adjacency
	// tables (0xF94F58 for variant 1, 0xF95088 for variant 2, read by the SW&LED CHECK
	// decoder sub_F94E1C) is a SUBSET of that sweep, register by register.  Two unrelated
	// tables agree.  Both are re-read from the ROM by
	// notes/wsa1-probes/wsa1_service_screen_refutation.py, section 4 and section 10.
	//
	// The numbering is deliberately NOT compacted to 47: led%u is the wire position, and
	// renumbering it would break the one thing these names do establish.
	//
	// ⚠ And the lamps have TWO writers on the firmware side, not one.  Panel_SetLedRegister's
	// guarded front door at prom_a 0xF8C84A opens with `cp (0x207A),0xDB / jr Z` -- it REFUSES
	// every normal LED write while the PANEL SW&LED CHECK screen (id 0xDB) is up -- while the
	// service module reaches the unguarded entry at 0xF8C846 directly.  On that screen the
	// lamps belong to the test, and a layout that assumes otherwise will look broken there.
	u8 m_led[8];
	output_finder<64> m_led_out;
};

DECLARE_DEVICE_TYPE(WSA1_CPANEL, wsa1_cpanel_device)

#endif // MAME_MATSUSHITA_WSA1_CPANEL_H

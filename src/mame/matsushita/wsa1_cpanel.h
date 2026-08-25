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
    control-panel driver, 0xFC3E65-0xFC4C33 -- 2,767 bytes, 0.13% of that ROM.
    Reproduce: notes/wsa1-probes/wsa1_kn5000_panel_bytediff.py.

    The correspondence is routine for routine, at the same offset inside the
    routine (notes/wsa1-probes/wsa1_kn5000_panel_map.py):

      WSA1 SC1_RxOp6_Run      0xF5B179  ==  KN5000 CPanel_RX_MultiBytePacket 0xFC4A40   22/22 bytes
      WSA1 SC1_RxOp6_Run+0x22           ==  KN5000 CPanel_RX_MultiBytePacket+0x22       15 bytes
      WSA1 SC1_RxOp0_ThreeByte+0x2E     ==  KN5000 CPanel_RX_ButtonPacket+0x2E          12 bytes
      WSA1 SC1_State20_RxFirstByte+0x2F ==  KN5000 CPanel_SM_RXByte1+0x2F               10 bytes
      WSA1 SC1_State04_TxByte1+0x1F     ==  KN5000 CPanel_SM_StartTX+0x1F                8 bytes
      WSA1 INTTX1_SC1_Dispatch+0x10     ==  KN5000 INTTX1_HANDLER+0x10                   8 bytes
      WSA1 SC1_Spin2/6/10/100/500       ==  KN5000 DELAY_{2,6,10,300,1500,3000}_LOOPS
      WSA1 SC1_WaitTicks2/6/51          ==  KN5000 DELAY_{2,6,51}_TICKS  (same 2/6/51!)

    And the two packet dispatchers are THE SAME INSTRUCTION with a different
    table pointer -- ten bytes, of which the four immediate bytes differ:

      WSA1  0xF5B0AB: eb c8 b5 b0 f5 00 a3 23 b3 d8   add XHL,SC1_RxOpTable
      KN5K  0xFC4959: eb c8 65 49 fc 00 a3 23 b3 d8   add XHL,CPanel_RX_PacketHandlers
      WSA1  0xF5B28F: eb c8 99 b2 f5 00 a3 23 b3 d8   add XHL,SC1_TxOpTable
      KN5K  0xFC4B79: eb c8 85 4b fc 00 a3 23 b3 d8   add XHL,CPanel_LED_PacketHandlers

    and the tables they name have the same shape and the same grouping:

      RX  8 entries   [0][1] button   [2] analogue   [3][4][5] sync   [6][7] multi-byte
      TX  4 entries   [0][1][2] two-byte LED frame   [3] multi-byte LED frame

    That closes gap E of notes/WSA1-EMULATION-DISASM-GAPS.md.  It also closes
    gap B by elimination and by its own evidence: the ten direction codes
    Dev7A_StartDma selects on are uPD765 command bytes with the MT/MFM flags
    (0x45+0xC0 = 0xC5 WRITE DATA, 0xC6 READ DATA, 0xCC READ DELETED DATA,
    0x42 READ TRACK, 0x4A READ ID, 0x4D FORMAT TRACK, and 0xD1/0xD9/0xDD =
    SCAN EQUAL / LOW-OR-EQUAL / HIGH-OR-EQUAL), and INT5's handler writes 0x08
    -- SENSE INTERRUPT STATUS -- when the status register reads RQM=1/DIO=0.
    The parts list has a uPD72070GF3BE.  So 0x7B0004/5 is the FLOPPY
    CONTROLLER's MSR/FIFO pair and 0x7A0000 its DACK data window.

    THE WIRE
    --------
    P8.3 = TXD1 -> panel SIN        P8.5 = SCLK1, driven by whoever transmits
    P8.4 = RXD1 <- panel SOUT       INT6 <- the panel's attention/request line
    PB.4 <- the panel's busy line   (idle: P8.5 high AND PB.4 LOW -- 0xF5AB7B)

    SC1MOD = 0x00 (0xF5A8AF) is I/O-interface mode.  SC1CR bit 0 is the clock
    source and the firmware flips it at every turn: cleared in SC1_StartWordTx
    (0xF5ABFC, the CPU clocks out), set in INT6_SC1_PeerRequest (0xF5AC1E, the
    panel clocks in).  Half duplex, one INT6 per inbound MESSAGE.

    THE FRAME, from the firmware's own length rule at prom_b 0xF5ADD7/0xF5AF41:

        len = ((first & 0x3F) >= 0x30) ? (first & 0x0F) + 3 : 2

    so every frame is [ADDR][DATA] unless bits 5:4 of the address byte are 11,
    in which case it is [HDR][FIRST_ADDR][DATA] x ((HDR & 0x0F) + 1).

    THE ADDRESS BYTE
        bits 7:6   panel id.  Every live address on this machine is 11.
        bits 5:3   packet type: 0/1 buttons, 2 analogue, 3/4/5 sync, 6/7 run
        bits 3:0   button SEGMENT (0..15), or, when bit 4 is set, the analogue
                   SUB-channel (0..7) -- i.e. 0xC0..0xCF are segments and
                   0xD0..0xD7 are analogue controls.

    THE MODEL STRAP -- PB BIT 0
    ---------------------------
    prom_a 0xF82882, called from RESET at 0xF827D8, is the only write to RAM
    (0xC4) in 512 KiB:

        ld A,0x01 / bit 0,(PB) / jr NZ,+2 / ld A,0x02 / ld (0xC4),A / ret

    PB.0 HIGH -> (0xC4)=1, PB.0 LOW -> (0xC4)=2, and 109 sites branch on it.
    The panel is one of them, twice over: the wire-address -> group map is
    0xF8A109 for 1 and 0xF8A189 for 2, and the LED-register -> wire-address
    map is 0xF8C8AC for 1 and 0xF8C8B7 for 2.

        (0xC4)=1  eleven button segments 0xC0..0xCA, four pots 0xD0..0xD3,
                  encoder 0xD7, eight LED registers 0xC0 C1 C2 C4 C5 C9 CC CD
        (0xC4)=2  nine button segments (0xC6 and 0xCA absent), ONE pot 0xD3,
                  encoder 0xD7, seven LED registers 0xC1 C2 C9 CA CB CC C3

    notes/wsa1-probes/README.md identifies (0xC4)=2 as the RACK from the
    manual's own specification page (its disk menu lacks MIDI FILE LOAD/SAVE,
    which the (0xC4)=1 display list has, and it lists two continuous controls,
    not six).  The panel side agrees independently: in variant 2 the panel
    sends exactly two analogue addresses, 0xD3 and 0xD7, and the rack's
    controls are VOLUME and the DATA ENTRY DIAL; and the variant-1-only
    analogue channel 0xD1 is the only one of the ten whose curve
    (prom_a 0xF89CB4) is a full 8-bit 0..255 map with an eighteen-entry flat
    dead zone at 0x80 and a power-on default of 0x80 -- a centre-detented
    bipolar wheel, i.e. a bender, which a rack module does not have.

    ⚠ NOT ESTABLISHED: which physical button is which bit, and which LED is
    which bit.  The service manual scan has the legends (PLAY MODE SOUND/COMBI,
    EDIT MODE SOUND/COMBI, BANK USER1/USER2/ROM-EXT/RE-MAP, PAGE up/down, six
    soft keys, a ten-key number pad, REALTIME CREATOR 1-6 + RESET, PART,
    SYSTEM, MIDI, DISK, MENU, COMPARE, EXIT) but not the S-number -> SEG/SW
    matrix, so this device declares the matrix POSITIONALLY.  The only bits
    the ROM names are the three power-on service combinations, and they are
    marked in the ioports below.

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
	// that pin and this device's maps have to be the ones the firmware is using.
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

private:
	static constexpr int NUM_SEG = 11;    // SEG0..SEG10, the CP1 MCU's scan lines
	static constexpr int RESP_MAX = 64;

	void queue_frame(const u8 *bytes, int n);
	void frame_complete();
	void led_frame(u8 addr, u8 data);
	bool segment_is_wired(int seg) const;

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

	// Scan shadows, so only CHANGED segments are reported -- which is what the firmware's
	// own change-mask table at RAM 0x2B20 expects to be fed.
	u8   m_seg_prev[NUM_SEG];
	u8   m_vol_prev;
	bool m_vol_synced;
	s32  m_dial_prev;
	bool m_dial_synced;

	devcb_write_line m_atn_cb;
	devcb_write_line m_busy_cb;
	devcb_write_line m_sclk_cb;
	devcb_write8     m_rxd_cb;

	optional_ioport_array<NUM_SEG> m_seg;
	optional_ioport m_volume;   // wire 0xD3
	optional_ioport m_dial;     // wire 0xD7, the DATA ENTRY DIAL

	// 8 LED registers x 8 bits.  Named positionally on purpose: no schematic net has been
	// read, so "led3_5" is a claim about the WIRE, which the ROM does establish, and not
	// about the legend, which it does not.
	u8 m_led[8];
	output_finder<64> m_led_out;
};

DECLARE_DEVICE_TYPE(WSA1_CPANEL, wsa1_cpanel_device)

#endif // MAME_MATSUSHITA_WSA1_CPANEL_H

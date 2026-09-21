# SX-WSA1R control panel: the firmware archaeology behind the HLE

MAME asks that code comments carry hardware facts and what a constant means, while the
reasoning — which routine established a value, which RAM address holds it, what was
rejected — belongs in the pull request or the project's own notes. On PR #16204 a
reviewer asked for exactly that trim on the panel module, which was 32 % comment lines
against 2–13 % elsewhere in the same PR.

This file is where that material went, verbatim, so nothing established by reverse
engineering is lost when the source is tidied. Each block is quoted as it stood, with the
line it sat on in `src/mame/matsushita/wsa1r_cpanel.{cpp,h}` at commit `afa89323a28`.



## wsa1r_cpanel.cpp

### line 1

```
// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************
```

### line 29

```
//-------------------------------------------------
//  the scan matrix
//
//  Eleven ports because the CP1 microcomputer drives SEG0..SEG10 and reads
//  SW0..SW7 (block diagram, manual page II-1).  The (0xC4) == 2 variant, the
//  rack, leaves SEG6 and SEG10 unwired -- PanelWireGroupMap_Variant2 has no entry for
//  wire 0xC6 or 0xCA -- so segment_is_wired() refuses them and a key bound
//  there is inert rather than injecting a packet the firmware files under
//  group id 0x20, "no such control".
//
//  Port names carry the wire position first and the legend in parentheses.
//  Legends printed beside the switch on the CP1/CP2 P.C. Diagram (PDF p.32)
//  cover SEG0..SEG2 and CP2's SEG7/SEG8; the rest are read off the P.C. board
//  page (PDF p.31).  The SX-WSA1 keyboard has two more scan columns and three
//  more pots and will need its own port map.
//
//  A handful of bits have a FUNCTION named by the ROM, marked below: three
//  power-on chords tested by the boot block (Panel_Chord_FactoryClear, Panel_Chord_RomVersion,
//  Panel_Chord_ThirdEntry) and the four service-screen keys in SEG1 (Panel_ServiceScreenSelect).
//
//  All of them read the panel's per-wire shadow at
//  RAM 0x2B20 + ((wire & 0x0F) | ((wire & 0x40) >> 2)), which holds the LAST
//  VALUE, not a change mask: SC1_RxOp0_ThreeByte does
//  `ex (XHL),A` then `xor A,(XHL)`, so the shadow takes the new value and the
//  mask is what gets queued.  Every chord test compares that byte for
//  EQUALITY, so an extra button held in the same segment kills the chord.
//-------------------------------------------------
```

### line 69

```
	// SEG1 is the service-screen keypad.  sub_F953CD, reached from RESET
	// at Boot_ChordCall_ServiceScreen when the model strap says (0xC4) == 2, compares (0x2B31) --
	// wire 0xC1, this segment -- for equality:
	//
	//     0x02 -> recognised, no screen           SvcScreen_None
	//     0x04 -> screen 0xD9  PANEL CPU CHECK    SvcScreen_PanelCpuCheck
	//     0x08 -> screen 0xDA  SINE WAVE CHECK    SvcScreen_SineWaveCheck
	//     0x10 -> screen 0xDB  PANEL SW&LED CHECK SvcScreen_PanelSwLedCheck
	//     0x20 -> screen 0xDC  the screen cycler  SvcScreen_Cycler
	//
	// then stores the id at (0x2070) and sets (0x2071) = 0x80.  Equality, so one
	// key at a time.  Variant 2 only: on the SX-WSA1 the same call reads the
	// keybed instead (sub_F9530B).
	//
	// The boot block tests four chords in address order -- FACTORY CLEAR
	// Boot_ChordCall_FactoryClear, this one Boot_ChordCall_ServiceScreen, ROM VERSION Boot_ChordCall_RomVersion, then Boot_ChordCall_Fourth -- and
	// Panel_Chord_RomVersion's matched arm never returns, so a held ROM-version chord pre-empts
	// a service screen this test already latched.
```

### line 169

```
	// Wire 0xD3.  The handler at Ctrl_G3Ch3_Normalise maps the byte through the plain,
	// strictly monotone 0..127 ramp at Ctrl_Curve_Identity128 (no plateau anywhere in it).  The
	// rack's mechanical parts list has exactly one VOLUME KNOB.
```

### line 175

```
	// Wire 0xD7.  Its dispatch slot (Ctrl_HandlerTable entry 31 -> Ctrl_ReportChanged) is a bare
	// `scf` -- no curve, no previous-value compare -- so every packet is accepted.  A
	// control that must never be de-duplicated is a RELATIVE encoder, and the KN5000's
	// twin protocol uses the same wire address 0xD7 for its endless wheel as
	// [0xD7, signed detent count] (kn5000_cpanel.cpp:269-271).  The rack's parts list
	// has exactly one DIAL WHEEL.  The signed-step encoding is inferred from those
	// two facts; prom_a's group-0x0F consumer has not been read.
```

### line 185

```
	// The SAME wheel, dragged in a circle by src/mame/layout/wsa1r.lay's widget
	// script, which writes it through user_value.  It cannot be the field above:
	// an analog field's only Lua write path, set_value(), latches
	// m_use_adjoverride permanently and detaches the field from the input system,
	// so one drag would kill the keys and the mouse axis for the rest of the
	// session.  An adjuster's user_value has no such side effect, so the two
	// controls coexist and scan_tick() sums their wrap-aware deltas.  Same split,
	// and for the same reason, as the KN5000's ENCODER / ENCODER_DRAG pair
	// (kn5000_cpanel.cpp).  It carries no key binding and needs none.
```

### line 270

```
	// The two lines SC1_WaitTxDrain and SC1_TxFlush_Body test before they will touch the
	// link (SC1_WaitTxDrain / SC1_LineFree_PBBit4): "free" is P8 bit 5 HIGH and PB bit 4 LOW.  Get
	// this wrong and nothing is ever transmitted -- the four-way test bails to
	// SC1_TxFlush_Exit and no LED frame and no command leaves the CPU.
```

### line 284

```
//-------------------------------------------------
//  variant geometry
//-------------------------------------------------
```

### line 296

```
//-------------------------------------------------
//  CPU 1 -> panel
//
//  The frame length rule is the firmware's own, from the two places it sets
//  the "bytes still expected" counter (0x2A81) after a first byte:
//  SC1_State08_TxFromRing (transmit, SC1_State08_TxFromRing) and SC1_State20_RxFirstByte
//  (receive, SC1_State20_RxFirstByte).  Both are
//      (0x2A81) = 2 ; if ((b & 0x3F) >= 0x30) (0x2A81) = (b & 0x0F) + 3
//  which is exactly what SC1_TxOp3_Run emits (header + (n & 0x0F) + 2 more)
//  and what SC1_RxOp6_Run consumes (header + address + (n & 0x0F) + 1 data).
//
//  So the two run encoders agree, at n+3 bytes per message, and the length
//  counter is a third independent witness to it.
//-------------------------------------------------
```

### line 338

```
		// Run frame: [HDR][FIRST_ADDR][DATA] x ((HDR & 0x0F) + 1), addresses stepping by 1.
		// SC1_TxOp3_Run builds it; nothing in this firmware has been seen
		// to produce one, but the codec accepts it, so decode it.
```

### line 350

```
	// The LED wire table is the authority, not the shape of the address: register 7
	// maps to wire address 0x00, and Panel_RefreshLeds walks all eight registers
	// (`ld B,0x08` at Panel_RefreshLeds), so that frame really is emitted and does not
	// look like an LED address at all.
```

### line 364

```
	// Everything else is a command.  The seven the firmware ever sends first are, in ROM
	// order: 0xDF 0xD2 / 0xDF 0x1A / 0xDD 0x03 / 0xDE 0x80 (SC1_ConfigurePort, prom_b
	// SC1_ConfigurePort_Cmds..SC1_ConfigurePort_LastCmd), 0xE0 0x00 (SC1_Cmd_E0_ReadStatus), 0xE3 0x00 / 0xE2 0x08 /
	// 0xE3 0x10 (SC1_Cmd_E3_E2_E3) and 0xEF 0x00 (SC1_Cmd_EF).
	//
	// What they ask for is not established.  What is, is what the firmware does with
	// the answer: SC1_Cmd_E0_ReadStatus zeroes both rx ring indices,
	// sends (0xE0,0x00), waits six ticks and sets bit 3 of (0x2A85) if the WRITE index
	// moved.  So the only thing it measures is "did the panel answer at all".  Answering
	// with a two-byte packet whose type field is 3, 4 or 5 satisfies that and is then
	// DISCARDED by SC1_RxOp3_Discard without entering the message queue --
	// exactly the KN5000's TYPE 3 sync packet (kn5000_cpanel.cpp, send_sync_packet).
	//
	// The header byte itself is a CHOICE: 0xD8 is type 3 (bits 5:3) with bits 7:6 = 11,
	// which is what every live address on THIS link carries.  The KN5000 sends 0x18, the
	// same type with bits 7:6 = 00.  Only the TYPE field is decoded by the receiver, so
	// both work; the exact byte a real M37471M2196S sends here is unknown.
```

### line 395

```
//-------------------------------------------------
//  LED registers
//
//  Panel_RefreshLeds walks EIGHT registers, comparing the
//  want-buffer at RAM 0x20D0..0x20D7 with the sent-shadow at 0x20F0..0x20F7
//  and calling Panel_SetLedRegister for each one that differs.
//  That routine maps the register INDEX through one of two tables --
//  Panel_LedWireTable on this machine -- to the wire address, then pushes [ADDR][DATA]
//  into the outbound queue at 0x2BA0.
//
//  Eight, not seven: the table ends C1 C2 C9 CA CB CC C3 00 and the loop emits
//  that trailing 0x00 as a wire address like any other.
//-------------------------------------------------
```

### line 430

```
//-------------------------------------------------
//  panel -> CPU 1
//
//  One INT6 per MESSAGE, not per byte: INT6_SC1_PeerRequest
//  turns RXE on, sets SC1CR bit 0 (the panel now clocks), selects INTES1=0x05
//  (receive only) and sets state 0x20.  SC1_State20_RxFirstByte then takes the
//  length from the first byte and SC1_State24_RxNextByte counts the rest down,
//  re-arming INT6 when it is done.  So: raise ATN, wait for the firmware to
//  enable RX, then push the message's bytes one at a time.
//-------------------------------------------------
```

### line 441

```
//  Every message this device sends is exactly two bytes, and the queue is a FIFO
//  of two-byte messages rather than a byte stream, because the CPU's receive
//  state machine is per message: INT6_SC1_PeerRequest accepts one request,
//  SC1_State20_RxFirstByte takes the length from the first byte -- 2 for every
//  address this device uses, since (addr & 0x3F) < 0x30 for 0xC0..0xD7 -- and
//  SC1_State24_RxNextByte re-arms INT6 when the count runs out.  Concatenating
//  two messages into one delivery would hand the second one to a state machine
//  that has stopped expecting bytes.
```

### line 470

```
//-------------------------------------------------
//  the attention line: a pulse, and a retry
//
//  Holding the line high does not work.  INT6's request flag is bit 3 of
//  INTE67, and the SC1 module writes that register with bit 3 clear at
//  eighteen sites -- 0x85 to arm INT6 at level 5, 0x8F to park it at level 7,
//  which is never dispatched (SC1_Inte67_Arm, SC1_Inte67_Park and sixteen more).  A
//  request raised while the module is transmitting latches into a masked flag
//  and is discarded by the write that re-arms INT6.
//
//  So the panel asks again: a short pulse, repeated every 2 ms until the CPU
//  turns RXE on.  The real part's pulse width and retry interval are not
//  known; neither constant below is claimed to be the hardware's.
//
//  The busy line is not raised while merely asking.  PB bit 4 blocks CPU 1
//  from transmitting at all (SC1_WaitTxDrain), so asserting it before the CPU
//  has accepted the request would silence the conversation the panel is trying
//  to join.  It goes high in rx_enable() and low when the last byte is gone.
//-------------------------------------------------
```

### line 500

```
		// Never ask while CPU 1 is mid-frame.  INT6_SC1_PeerRequest (prom_b
		// INT6_SC1_PeerRequest) opens `cp (0x2A81),0x00` -- the bytes-still-expected counter,
		// used for transmit as well as receive -- and if it is not zero it takes
		// the arm at INT6_PeerRequest_BusyArm, which steps the RX ring's write index back one on
		// the assumption that the peer will re-send the byte it just took.  This
		// device never re-sends, so such an edge desynchronises the ring by one
		// byte permanently and every later message pairs the previous message's
		// data byte with this one's address byte.
		//
		// m_pos alone is not enough: the firmware sets (0x2A81) before writing the
		// first byte to SC1BUF and clears it after the last (SC1_State08_TxFromRing / SC1_RxDone_ClearCount),
		// so a quiet window is needed as well.  1 ms is a driver choice, like the
		// pulse width above it.
```

### line 559

```
	// Message complete: give the link back.  Anything still queued has to ask again,
	// because the firmware re-arms INT6 at the end of a message and expects the next
	// one to arrive the same way this one did.
```

### line 573

```
//-------------------------------------------------
//  the periodic scan
//
//  Buttons are reported as [0xC0 | segment][bitmask].  The header's type field
//  falls out of the segment number for free -- segments 0..7 give type 0 and
//  8..15 type 1, which is exactly why SC1_RxOpTable entries [0] and [1] are
//  the same handler.  SC1_RxOp0_ThreeByte then XORs the mask against its own
//  shadow at RAM 0x2B20 + ((addr & 0x0F) | ((addr & 0x40) >> 2)) -- the +0x10 is
//  CONDITIONAL on address bit 6 (SC1_RxOp0_ThreeByte does `and W,0x4F` and then
//  `sub W,0x30` only when bit 6 is set), which is true of every 0xC0..0xCF
//  address but is not the rule -- and hands the foreground
//  {address, mask, CHANGED-bits} -- so sending the whole segment state, not
//  just the change, is correct and is what the shadow table is there for.
//
//  Analogue controls are [0xD0 | sub][value]; the firmware appends its own
//  0xFF third byte (SC1_RxOp2_AppendFF), so it must NOT be sent here.
//-------------------------------------------------
```

### line 623

```
	// Wire 0xD7, the DATA ENTRY DIAL.  Sent as a SIGNED STEP -- see the ioport comment for
	// why, and for the fact that this is inference and not decode.
	//
	// TWO controls feed one wheel: the IPT_DIAL (keys and the mouse axis, 256 positions)
	// and the layout's drag adjuster (0..100, wrapped by the script).  Both are relative,
	// so their deltas simply add; neither one's absolute value means anything.
```

### line 642

```
//-------------------------------------------------
//  one relative control's movement since the last scan
//
//  Wrap-aware, because both fields wrap: the IPT_DIAL at 256 and the layout's
//  adjuster at 101 (the script does `user_value = (user_value + n) % 101`).  The
//  first read only ADOPTS the position -- a step reported before the firmware is
//  servicing the link would sit in the queue and block every later request.
//-------------------------------------------------
```


## wsa1r_cpanel.h

### line 1

```
// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************
```

### line 109

```
	// 8 LED registers x 8 bits, output led%u with %u = register * 8 + bit.  The
	// name stays positional because the wire position is what the ROM
	// establishes for both variants; which lamp sits there is per-variant and
	// belongs in the layout.
	//
	// For the rack, prom_a's variant-2 switch->LED table at Panel_SwitchLedTable_V2 holds one
	// u16 per switch, and that u16 is (register << 8) | bit mask: Panel_SetSwitchLed
	// reads it with `ld WA,(XHL)` and calls Panel_SetLedRegister_Unguarded, which maps W
	// through the register->wire table and queues [wire][A].  A button with an indicator
	// lights its own, so
	//
	//   reg1 bits 0..3  PLAY MODE SOUND / COMBI, EDIT MODE SOUND / COMBI
	//   reg0 bits 0..3  BANK USER 1 / USER 2 / ROM-EXT / RE-MAP
	//   reg4 bits 0,1   MENU PART / MENU SYSTEM
	//   reg5 bits 0,1   MENU MIDI / MENU DISK
	//   reg6 bit 2      COMPARE           -- the LCD-key family indicator
	//   reg6 bit 3      MIDI/NUMBER PAD   -- the numeric family indicator
	//
	// and {reg2 bit0, reg2 bit1, reg3 bit0, reg3 bit1} are the four REALTIME
	// CREATOR ring lamps as a set, in an order nothing read so far pins down.
	//
	// Only 47 of the 64 positions are real lamps.  The PANEL SW&LED CHECK
	// screen's all-on sweep (sub_F956B0) walks the table at Panel_LedCheckMaskTable, which is
	//
	//     reg0=FF reg1=FF reg2=FF reg3=FF reg4=FF reg5=03 reg6=0F reg7=02
	//
	// so led42-47, led52-56 and led58-63 are never lit by the firmware's own
	// all-lamps test and no layout lamp may bind to them.  led%u is the wire
	// position, so the numbering runs to 63.
	//
	// The lamps have two writers.  Panel_SetLedRegister opens with
	// `cp (0x207A),0xDB / jr Z`, so it refuses every LED write while the PANEL SW&LED
	// CHECK screen (id 0xDB) is up.  The service module uses
	// Panel_SetLedRegister_Unguarded, which does not make that test.  On that
	// screen the lamps belong to the test.
```


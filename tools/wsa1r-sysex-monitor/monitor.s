;; monitor.s -- a SysEx debug monitor for the SX-WSA1R, living in prom_a's padding.
;;
;; PURPOSE (notes/HARDWARE-CUSTOM-DSP-PROGRAMS-WSA1R.md sect. A5): give the uPD6383 decode a
;; bidirectional debug channel over MIDI, so probe microcode can be loaded and results read back
;; as exact integers instead of inferred from audio.
;;
;; TARGET   TMP95C061 (TLCS-900/H), CPU 1, prom_a = qsigcwsa1ax.ic12, mapped at 0xF80000.
;; ASSEMBLER llvm-mc -triple=tlcs900 (the project's own backend).  Every encoding this file
;;          relies on has been checked byte-for-byte against the ROM's own listing:
;;            call 0xf41e3c -> 1d 3c 1e f4   (as at 0xFA5860 / 0xFA5867 / 0xFA587D)
;;            pushw de      -> 2a            inc 2,xsp -> ef 62
;;            pushw 0x0002  -> 0b 02 00      push xbc  -> 39
;;
;; ---------------------------------------------------------------------------------------------
;; WHERE IT LIVES
;;   prom_a module 0xFB9000's tail padding: 0xFBA236-0xFBABFF, 2506 bytes, verified ALL 0x0E
;;   (RET) byte by byte, with a non-0x0E byte immediately before it.  Nothing in the ROM
;;   references it (FINDINGS-prom_a-remote-flash.md sect. 2).
;;
;; HOW IT IS REACHED
;;   ONE four-byte patch.  `MIDI_RX_SysExData' (0xFA586E) is called for every data byte inside an
;;   accepted System Exclusive message.  Its first four bytes `f0 a9 c9 66' are replaced with
;;   `jp MON_ENTRY'.  The routine is only ever entered at its first byte (sole caller
;;   MIDI_RX_DataByte, 0xFA576D), so nothing after the patch is reachable and the remaining
;;   original bytes are left in place as documentation.  Restoring the ROM is a four-byte write.
;;
;; THE STATE BIT, AND WHY IT IS FREE
;;   (0xA9) is the firmware's own SysEx state byte: bit 0 "identifier accepted", bit 1
;;   "in-message", and **bit 5 which MIDI_RX_SysExData TESTS AND NOTHING IN THE FIRMWARE EVER
;;   SETS** (FINDINGS-midi-port.md).  So bit 5 is a free per-message flag with exactly the right
;;   lifecycle: `MIDI_RX_SysExStart' does `ld (0xa9),0x01', which clears it at every F0.
;;   This monitor uses it as "this message is MINE".  No RAM is allocated anywhere.
;;
;; PROTOCOL (milestone 1)
;;   in    F0 7E 7D 01 F7      -> IDENT
;;   out   F0 7E 7D 7F 01 00 F7
;;   0x7E is one of the two identifiers the firmware accepts (the other is 0x50); 0x7D is this
;;   monitor's marker.  Once the marker is seen the monitor CLAIMS the message and stops
;;   forwarding it to the stock ring, so our traffic never reaches the stock parser.
;;
;; ⚠ NOT YET PROVEN, and the emulator is where it gets tested: calling the transmit primitive
;;   0xF40ED4 from inside the MIDI receive interrupt.  Its 47 callers look like main-loop code.
;;   If it turns out not to be re-entrant the reply must move to a main-loop hook instead.
;; ---------------------------------------------------------------------------------------------

	.set	MON_BASE,   0xFBA236		; start of the padding
	.set	IDENT_TBL,  MON_BASE		; +0x00  the constant reply, 7 bytes
	.set	MON_ENTRY,  MON_BASE + 0x10	; +0x10  code entry (the jp target)

	.set	SYSEX_ST,   0xA9		; firmware SysEx state byte
	.set	MIDI_ACT,   0x216F		; "MIDI activity" bit the original sets
	.set	RING_PUT,   0xF41E3C		; T_Ring601646_Put -- the stock SysEx sink
	.set	MIDI_SEND,  0xF40ED4		; transmit: (port, len, ptr) pushed, 8 bytes cleaned

	.set	MARKER,     0x7D		; our sub-id
	.set	CMD_IDENT,  0x01
	.set	CMD_PEEK,   0x02		; read CPU-1 memory back over MIDI

;; ---------------------------------------------------------------------------------------------
;; MILESTONE 2 STATE.  Milestone 1 used no RAM at all; PEEK needs a little.
;;
;; ⚠ THE ADDRESS IS MEASURED, NOT ASSUMED.  A write-tap census over a full 12-second boot
;; (`ramscan.lua') found 0x67F000-0x67FFFF NEVER written, while 0x007F00 took 227 writes and
;; 0x640000 / 0x660000 took 6 each.  CPU 1's RAM is 0x000080-0x007FFF plus 0x600000-0x67FFFF,
;; and this is the top of the large block.
;; ⚠ CAVEAT, stated because it matters: twelve seconds of BOOT is not the machine's whole life.
;; Loading a disk or entering an unvisited mode could touch it.  Re-run the census under more
;; activity before trusting this on hardware.
	.set	MST,        0x67FF00		; monitor state block
	.set	MST_POS,    MST + 0x00		; byte position within our message
	.set	MST_CMD,    MST + 0x01		; the command byte
	.set	MST_ADDR,   MST + 0x04		; 32-bit address accumulator
	.set	MST_NIB,    MST + 0x08		; nibble parity while assembling a byte
	.set	MST_BUF,    MST + 0x10		; reply buffer

	.set	PEEK_LEN,   8			; milestone 2 reads a FIXED 8 bytes
	.set	REPLY_LEN,  4 + 2 * PEEK_LEN + 1	; F0 7E 7D 7E + nibble pairs + F7

;; ---------------------------------------------------------------------------------------------
;; WIRE FORMAT.  MIDI data bytes carry only 7 bits, so every payload byte travels as TWO bytes,
;; each holding one nibble (high first).  That is wasteful and completely unambiguous, which is
;; the right trade for a debug channel.
;;
;;   PEEK   in   F0 7E 7D 02  a5 a4 a3 a2 a1 a0   F7      (24-bit address, 6 nibbles, MSB first)
;;          out  F0 7E 7D 7E  <8 bytes as 16 nibbles>  F7
;;
;; ⚠ NOT YET IMPLEMENTED and deliberately so: writes, and anything touching the DSP.  The DSP
;; host port belongs to CPU 2, so LOAD/POKE of I-RAM or C-RAM must cross the inter-processor
;; link -- a separate piece of work.  PEEK is CPU-1-only and needs none of it.

	.text
;; ---- +0x00 : the IDENT reply, a ROM constant so milestone 1 needs no RAM at all ----
	.byte	0xF0, 0x7E, MARKER, 0x7F, 0x01, 0x00, 0xF7
	.byte	0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00	; pad to +0x10

;; ---- +0x10 : entry.  Reached by `jp' from 0xFA586E; must behave as MIDI_RX_SysExData ----
MON_ENTRY:
	bitm	0, (SYSEX_ST)		; identifier accepted?  (original: bit 0,(0xA9))
	jr	z, .Lret		;   no -> do nothing, exactly as the original
	bitm	5, (SYSEX_ST)		; already claimed by us?
	jr	nz, .Lours
	cp	e, MARKER		; is this byte our marker?
	jr	z, .Lclaim

;; ---- the stock path, reproducing the original instruction for instruction ----
	setm	0, (MIDI_ACT)		; original: m_set 0, MD16, 0x216f
	pushw	de
	call	RING_PUT
	inc	2, xsp
.Lret:
	ret

.Lclaim:
	setm	5, (SYSEX_ST)		; claim the message; swallow the marker byte
	xor	a, a			; ⚠ and RESET the byte position.  (0xA9) bit 5 is cleared by
	ld	(MST_POS), a		;   MIDI_RX_SysExStart at every F0, so this runs once per
					;   message -- which is exactly the state reset we need.
	;; ⚠ AND CLEAR THE WHOLE ADDRESS.  Only 6 nibbles arrive, which fill bytes +0..+2; byte
	;; +3 would keep whatever was there and `ld xde,(MST_ADDR)' reads all four.  Caught by
	;; reading the code before running it, not by a wrong answer afterwards.
	ld	(MST_ADDR + 0), a
	ld	(MST_ADDR + 1), a
	ld	(MST_ADDR + 2), a
	ld	(MST_ADDR + 3), a
	ret

;; ---- our message: dispatch, byte by byte ----
;; Entered with the data byte in E and the message already claimed.  MST_POS says where we are:
;;   0        the COMMAND byte
;;   1..6     the six address nibbles, high first
;;   >6       ignored (the F7 that ends the message never reaches here -- it is a status byte and
;;            the firmware routes it elsewhere -- so state is reset by the NEXT F0 instead, via
;;            MIDI_RX_SysExStart clearing (0xA9), which makes .Lclaim re-initialise MST_POS)
.Lours:
	ld	a, (MST_POS)
	cp	a, 0x00
	jr	nz, .Lp1
;; ---- position 0: the command ----
	ld	a, e
	ld	(MST_CMD), a
	cp	a, CMD_IDENT
	jr	z, .Lident
	cp	a, CMD_PEEK
	jr	z, .Ladvance
	ret				; unknown command: ignore the rest
.Ladvance:
	ld	a, 0x01
	ld	(MST_POS), a
	ret

;; ---- positions 1..6: address nibbles, high first ----
.Lp1:
	cp	a, 0x01
	jr	nz, .Lp2
	ld	a, e
	sla	a, 4
	ld	(MST_ADDR + 2), a
	ld	a, 0x02
	ld	(MST_POS), a
	ret
.Lp2:
	cp	a, 0x02
	jr	nz, .Lp3
	ld	a, (MST_ADDR + 2)
	or	a, e
	ld	(MST_ADDR + 2), a
	ld	a, 0x03
	ld	(MST_POS), a
	ret
.Lp3:
	cp	a, 0x03
	jr	nz, .Lp4
	ld	a, e
	sla	a, 4
	ld	(MST_ADDR + 1), a
	ld	a, 0x04
	ld	(MST_POS), a
	ret
.Lp4:
	cp	a, 0x04
	jr	nz, .Lp5
	ld	a, (MST_ADDR + 1)
	or	a, e
	ld	(MST_ADDR + 1), a
	ld	a, 0x05
	ld	(MST_POS), a
	ret
.Lp5:
	cp	a, 0x05
	jr	nz, .Lp6
	ld	a, e
	sla	a, 4
	ld	(MST_ADDR + 0), a
	ld	a, 0x06
	ld	(MST_POS), a
	ret
.Lp6:
	cp	a, 0x06
	jr	nz, .Lret2
	ld	a, (MST_ADDR + 0)
	or	a, e
	ld	(MST_ADDR + 0), a
	ld	a, 0x07
	ld	(MST_POS), a
	;; the address is complete -- fall into the read
	jr	.Lpeek
.Lret2:
	ret

;; ---- PEEK: read PEEK_LEN bytes from the assembled address, reply as nibble pairs ----
;; ⚠ The reply is built in RAM (MST_BUF) rather than being a ROM constant like IDENT's, which is
;; the whole reason milestone 2 needs RAM at all.
.Lpeek:
	push	xbc
	push	xde
	push	xhl
	ld	xhl, MST_BUF
	;; header  F0 7E 7D 7E
	ld	a, 0xF0
	ld	(xhl), a
	inc	1, xhl
	ld	a, 0x7E
	ld	(xhl), a
	inc	1, xhl
	ld	a, MARKER
	ld	(xhl), a
	inc	1, xhl
	ld	a, 0x7E			; PEEK reply tag
	ld	(xhl), a
	inc	1, xhl
	;; the payload
	ld	xde, (MST_ADDR)
	ld	b, PEEK_LEN
.Lploop:
	ld	a, (xde)
	push	wa
	srl	a, 4			; high nibble first
	and	a, 0x0F
	ld	(xhl), a
	inc	1, xhl
	pop	wa
	and	a, 0x0F			; then the low nibble
	ld	(xhl), a
	inc	1, xhl
	inc	1, xde
	dec	1, b
	jr	nz, .Lploop
	ld	a, 0xF7
	ld	(xhl), a
	;; hand the whole thing to the firmware's transmitter: (port, len, ptr)
	ld	xbc, MST_BUF
	push	xbc
	ldw	de, REPLY_LEN
	pushw	de
	pushw	0x0002
	call	MIDI_SEND
	inc	0, xsp
	pop	xhl
	pop	xde
	pop	xbc
	ret

;; ---- IDENT: the milestone-1 constant reply, unchanged ----
.Lident:
	push	xbc			; ⚠ MIDI_RX_Byte brackets this with Load/SaveContext,
	push	xde			;   so the parser's registers live in RAM at 0x0900 --
					;   clobbering one corrupts persistent parser state.
	lda	xbc, (IDENT_TBL)
	push	xbc			; ptr
	ldw	de, 0x0007
	pushw	de			; len
	pushw	0x0002			; port
	call	MIDI_SEND
	inc	0, xsp			; clean the 8 bytes pushed (4 + 2 + 2)
	pop	xde
	pop	xbc
	ret

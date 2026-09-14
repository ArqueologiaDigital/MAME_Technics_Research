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
	ret

;; ---- our message: dispatch on the byte ----
;; ⚠ Milestone 1 has NO byte counter, so it acts on any 0x01 while claimed.  The test message
;;    carries exactly one such byte.  A counter needs RAM and arrives with milestone 2.
.Lours:
	cp	e, CMD_IDENT
	jr	nz, .Lret
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

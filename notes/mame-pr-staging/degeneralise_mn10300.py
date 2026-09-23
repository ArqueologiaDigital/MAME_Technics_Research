"""Make the MN10300 core read as a CPU core.

QUESTION IT ANSWERS
  "Does anything in cpu/mn10300 only make sense to somebody who has the KN7000
  overlay repository open?"

  Three classes of leftover, all invisible to the compiler:
    * firmware addresses of one machine (0x484..., 0x4C03..., 0x50...)
    * pointers to notes/*.md files that do not exist in the MAME tree
    * the core's own porting history ("byte-exact port of kn7000.cpp ...")

  The facts they carry are kept; the provenance ceremony is dropped.

RUN   python3 degeneralise_mn10300.py     (from the PR worktree root)
PASS  prints "ok"; the greps at the end of the PR prep must come back empty.
"""

CPP = 'src/devices/cpu/mn10300/mn10300.cpp'
H = 'src/devices/cpu/mn10300/mn10300.h'


def shift(text, n):
    """Re-indent a whole block by n tabs (n<0 removes)."""
    out = []
    for line in text.split('\n'):
        if n < 0:
            out.append(line[min(-n, len(line) - len(line.lstrip('\t'))):])
        else:
            out.append(('\t' * n + line) if line.strip() else line)
    return '\n'.join(out)


def edit(path, pairs):
    """Apply each (old, new) once.

    The blocks were transcribed by eye, so a block may be written one tab off.
    Retry at +/-2 tabs and shift the replacement by the same amount, rather
    than let an indentation typo pass as "nothing to do".
    """
    s = open(path, encoding='utf-8').read()
    for old, new in pairs:
        for d in (0, -1, 1, -2, 2):
            cand = shift(old, d)
            if cand in s:
                s = s.replace(cand, shift(new, d), 1)
                break
        else:
            raise AssertionError('%s MISSING: %r' % (path, old[:80]))
    open(path, 'w').write(s)
    print('rewrote', path)


edit(CPP, [
# --- address space -------------------------------------------------------
("""	// Flat 32-bit little-endian space, 32-bit data bus. The KN7000 peripherals
	// (program flash @0x48400000, table flash @0x48000000, work RAM @0x50000000,
	// picture flash @0x57800000, I/O banks) are decoded by the machine driver's
	// external address map. The internal map supplied here decodes the on-chip
	// peripherals (INTC, SIO, TM4/TM5 timers); MAME appends it after the
	// driver's map, so it takes priority over any overlapping driver entry
	// while leaving the surrounding 0x34xxxxxx driver mappings intact.
""",
 """	// Flat 32-bit little-endian space, 32-bit data bus. The internal map supplied
	// here decodes the on-chip peripherals (INTC, SIO, TM4/TM5 timers) and is
	// appended after the driver's map, so it takes priority over any overlapping
	// driver entry while leaving the surrounding mappings intact.
"""),

# --- reset ----------------------------------------------------------------
("""	// KN7000: program flash maps at 0x48400000 and file offset 0 is
	// "jmp 0x48407EFF", so the first fetched instruction is at the flash base.
	// TODO: if the boot/library ROM @0x4C000000 is dumped, the true reset PC
	// may originate there instead.
	m_pc  = 0x48400000;
	m_sp  = 0x50021CF8;   // initial SP established by the KN7000 firmware
""",
 """	// Boot address and initial stack are strapped per board, so the machine
	// supplies them (set_reset_pc/set_reset_sp).
	m_pc  = m_reset_pc;
	m_sp  = m_reset_sp;
"""),

# --- INTC section header --------------------------------------------------
("""// Byte-exact port of the KN7000 driver's HLE (kn7000.cpp intc_r/intc_w/
// intc_assert/intc_recompute/irq_ack); the register model and its quirks are
// documented in mn10300.h and in the kn7000_mame overlay's
// notes/interrupt-mechanism.md. The library-ROM interrupt handler (self-
// loaded, entry 0x4C03DDA0) reads the pending group from the IAGR at
// 0x34000100, indexes its handler table, and calls the registered ISR
// callback. `offset` is the 16-bit word index within 0x34000100; group =
// offset/2, register = 0x34000100 + group*4.
""",
 """// The register model and its quirks are documented in mn10300.h. An interrupt
// handler reads the pending group from the IAGR at 0x34000100, indexes its
// handler table and calls the ISR registered for that group. `offset` is the
// 16-bit word index within 0x34000100; group = offset/2, register =
// 0x34000100 + group*4.
"""),

("""	// Among enabled+requested groups, the winner is the highest-priority one =
	// the LOWEST ICR LEVEL value (bits 14:12). KN7000 firmware programs: SIO
	// panel/MIDI groups 0x12-0x15 LEVEL=1, 0x0F/0x19 LEVEL=3, group 7 LEVEL=4,
	// and the system tick (group 6) LEVEL=6 -- the lowest priority in the system.
""",
 """	// Among enabled+requested groups the winner is the highest-priority one,
	// which is the LOWEST ICR LEVEL value (bits 14:12).
"""),

("""// Freeze the arbitration result (group AND vector, atomically) at the instant
// the CPU accepts the interrupt -- the real INTC latches IAGR at acknowledge.
// (This was the driver's set_irq_acknowledge_callback, irq_ack.)
""",
 """// Freeze the arbitration result (group and vector, atomically) at the instant
// the CPU accepts the interrupt -- the INTC latches IAGR at acknowledge.
"""),

("""		// Board hook (KN7000: group 0x11 accepted -> its panel transfer-
		// complete "unserviced" flag clears; see intc_ack_cb in the header).
""",
 """		// Board hook: this group was latched into the IAGR (see intc_accept_cb).
"""),

("""		// Vector selection is board policy (per-level table): the KN7000 maps
		// every level to the firmware quick-dispatch handler 0x4C03DDA0 except
		// the level-6 scheduler entry 0x4C03DE26; the KN6000/KN6500 map ALL
		// levels to their firmware trampoline slot 0 (0x90000000) -- see
		// intc_recompute for why the split matters.
""",
 """		// Vector selection is board policy: a per-level table the machine fills
		// in (see intc_recompute for why the level split matters).
"""),

# --- DETECT ack -----------------------------------------------------------
("""	// A write carrying DETECT-ack bits: report it outward. The KN7000 binds
	// this to its panel transfer-complete re-delivery -- group 0x11 is level-
	// like until serviced: the firmware's ISR-exit ack (full-word 0x0101 at
	// 0x484AC736) w1c-clears DETECT, and on real hardware the NEXT byte's
	// completion always arrives after that ack (the serial shift is slower
	// than the ISR exit). If the deferred completion landed before the ack
	// (and was thus wiped un-serviced), the driver re-delivers it after the
	// ack (its c11_unserviced flag + 40us one-shot).
""",
 """	// A write carrying DETECT-ack bits: report it outward, so a board that needs
	// level-like re-delivery for one of its sources can implement it.
"""),

# --- group 0x17 software trigger -----------------------------------------
("""	// Effects-DSP self-test handshake (group 0x17 == GxICR 0x3400015c). During init the
	// KN7000 firmware SOFTWARE-TRIGGERS this interrupt (writes bit0) then spin-polls bit4
	// (REQUEST) to confirm the ADSP-21065L answered its power-on self-test (fw 0x48404d25).
	// On the 0x3ffff-count timeout it marks the DSP ABSENT (stores 0x500066CC=0xFF), which
	// slams shut the runtime effect-upload gate (fw 0x48404ef5 checks 0x500066CC==0) -- so
	// after that, selecting a reverb/chorus in the sound menus never reaches the DSP and
	// "the sound doesn't change". The real DSP asserts group 0x17 on self-test completion;
	// the booted SHARC in the emulator is present, so model the ack: latch REQUEST here so
	// the poll succeeds and 0x500066CC stays "present". The firmware's write is 0x0001, so
	// the ENABLE byte stays 0 -> no spurious dispatch. Group 0x17 has no other user (no ISR
	// is registered against it; its only refs are this handshake + the INTC bulk-clear).
	// (The driver gated this on dsp_present(), which was constant-true on every machine
	// sharing the config -- so the quirk is unconditional here.)
""",
 """	// Software trigger on group 0x17 (GxICR 0x3400015c): writing a DETECT bit
	// latches REQUEST, so a poll of REQUEST succeeds without an external source
	// asserting. Software uses this to hand-shake a device self-test. Writing
	// DETECT alone leaves ENABLE clear, so nothing is dispatched. Only this group
	// is known to be used that way; generalising it awaits evidence.
"""),

("""	m_gxicr[group & (NUM_INTC_GROUPS - 1)] |= 0x0011;
	// (REQUEST + DETECT bit0 were just set above; the scheduler-level dispatcher at 0x4C03DE72 scans the DETECT bits 0-3 to pick the sub-source within the group)
""",
 """	// REQUEST + DETECT bit0; a handler scans DETECT bits 0-3 to pick the
	// sub-source within the group.
	m_gxicr[group & (NUM_INTC_GROUPS - 1)] |= 0x0011;
"""),

# --- recompute ------------------------------------------------------------
("""	// The AM33 dispatches each interrupt LEVEL through its own vector. The
	// KN7000 firmware installs two distinct handlers:
	//  - 0x4C03DDA0: quick dispatch (no stack switch) -- used by the high-
	//    priority device levels (reads IAGR at 0x34000100).
	//  - 0x4C03DE26: the SCHEDULER entry -- outermost entry saves the interrupted
	//    task's SP into its TCB (*0x5038002C), switches to the scheduler stack
	//    (*0x50380CBC), dispatches (reads the group register at 0x34000200), and
	//    on exit reloads SP from the (possibly re-chosen) current TCB. Only the
	//    system tick (group 6, LEVEL=6, the lowest priority) uses this one.
	// Routing the tick to the quick handler instead desynchronizes the TCB
	// saved-SPs from reality (the scheduler moves *0x5038002C but nothing
	// switches stacks), which corrupts the next yield -- so the vector must be
	// selected per pending level. The level -> vector mapping is the board-
	// configured table (set_maskable_vector); the KN6000/KN6500 route ALL
	// maskable IRQs to their firmware trampoline slot 0 (0x90000000 -> the
	// general handler, which reads the latched group at 0x34000200 and
	// dispatches). Slot 1 (0x90000006 -> 0x4847b19d) is the KN6000's
	// EXCEPTION/fault handler (disables IRQs + halts), NOT an IRQ dispatch --
	// routing IRQs there halts the boot. See notes/kn6000-kn6500-boot.md.
""",
 """	// The AM33 dispatches each interrupt LEVEL through its own vector, so the
	// vector must be selected from the pending level rather than fixed once. A
	// system that runs its scheduler from one level and quick device handlers
	// from the others relies on this: sending a scheduler-level interrupt to a
	// handler that does not switch stacks corrupts the next task switch. The
	// level -> vector table is board policy (set_maskable_vector).
"""),

# --- timers ---------------------------------------------------------------
("""//  on-chip 16-bit timers @ 0x34001080 (TM4/TM5) -- TM5 = the KN7000 tempo timer
//**************************************************************************
//
// Byte-exact port of the KN7000 driver's model (kn7000.cpp tmr7_*, named after
// its INTC group there). TM5 is the clock behind ALL sequenced playback: the
// firmware registers ISR 0x48447084 -- a 96-PPQN tick counter (increments a
// mod-0x60 beat phase at 0x50149664 and drives five sub-tick consumers) -- on
// INTC group 7 (GxICR 0x3400011C, level 4, registration at 0x4844780C), and
// programs this timer's reload to the current tempo. Semantics modeled from
// the firmware's own driver code:
//   start   (0x484477D3): write mode -> write base -> bset 0x40 (load counter
//            from base) -> bclr 0x40 -> bset 0x80 (count enable)
//   restart (0x484478C8): bclr 0x80 -> bset/bclr 0x40 -> bset 0x80
//   tempo   (0x48447888): movhu newbase, (0x34001092) while running -- takes
//            effect on the next underflow (hardware auto-reload semantics).
// Prescale: low mode bits select the source clock; PRESCALE is fixed from the
// 96-PPQN math (see tm5_rearm). The KN6000/KN6500 firmware programs the same
// registers (mode 0x81, base 0xFA0) for its ms-counter tick, also on group 7.
""",
 """//  on-chip 16-bit timers @ 0x34001080 (TM4/TM5)
//**************************************************************************
//
// TM5 underflow asserts INTC group 7. Control sequences, read off the software
// that drives the timer:
//   start   write mode -> write base -> bset 0x40 (load counter from base) ->
//           bclr 0x40 -> bset 0x80 (count enable)
//   restart bclr 0x80 -> bset/bclr 0x40 -> bset 0x80
//   tempo   write a new base to 0x34001092 while running -- takes effect on the
//           next underflow (auto-reload).
// The low mode bits select the source clock; see tm5_rearm for the prescale.
"""),

("""	intc_assert(0x07);      // GxICR 0x3400011C -> KN7000: the 96-PPQN sequencer tick ISR 0x48447084
""",
 """	intc_assert(0x07);      // GxICR 0x3400011C
"""),

# --- SIO ------------------------------------------------------------------
("""// Byte-exact port of the KN7000 driver's HLE (kn7000.cpp sio_r/sio_w); the
// register model and its deliberate omissions are documented in mn10300.h and
// in the kn7000_mame overlay's notes/panel-serial-protocol.md. Precedent for
// on-chip serial living in the CPU core: the MN10200 (m_serial[] block).
""",
 """// The register model and its deliberate omissions are documented in mn10300.h.
// Precedent for on-chip serial living in the CPU core: the MN10200 (m_serial[]).
"""),

("""		// KN7000 ch2 is the MIDI-2 UART (adversarially verified RE 2026-07-10;
		// an earlier "CPSD/SD link" attribution was wrong). Its RX classifier
		// 0x484b28ee treats bit7 as RX-empty and its TX path polls bit6 as
		// TxRDY, but modeling those bits changes boot-time MIDI-2 behaviour and
		// wedged the boot (black LCD) -- keep the historical RxRDY-only status
		// until MIDI-2 OUT modeling is actually wanted.
""",
 """		// Only RxRDY is modelled. The status byte also carries RX-empty (bit7)
		// and TxRDY (bit6); supplying them changes boot-time behaviour on the
		// machines tested here, so they wait until TX is actually modelled.
"""),

("""			// Bit 15 = transfer START on the synchronous panel link (ch0): the
			// firmware sets it to clock one byte and then polls the register until
			// the hardware self-clears it on completion. The HLE completes
			// transfers instantly. Bit15 is the start/busy for the boot's POLLED
			// bit-bang path only; it just self-clears here. The per-byte transfer
			// trigger is the DATA write itself: the KN7000 TX state machine's
			// state-2 (0x484AC8D2) and later payload states write data with NO
			// bit15 write at all -- an armed/pending model makes each such transfer
			// complete only on the NEXT retry's arm, advancing the state machine
			// one step per retry (observed as parking). Completion is signaled per
			// data write in sio_tx_byte.
""",
 """			// Bit 15 = transfer START on the synchronous link (ch0): software sets
			// it to clock one byte, then polls until the hardware self-clears it.
			// Transfers complete instantly here, so it just self-clears. The actual
			// per-byte trigger is the DATA write -- software drives whole payloads
			// without touching bit15 again -- so completion is signalled per data
			// write in sio_tx_byte, not per bit15 write.
"""),

("""			// RX enable (bit14, set by the KN7000's group-0x1A ISR pass 2 together
			// with mode low3=7 and state:=8): notify the endpoint (the panel now
			// sends its queued reply, one byte per RX interrupt).
""",
 """			// RX enable (bit14): notify the endpoint, which may now send its queued
			// reply, one byte per RX interrupt.
"""),

# --- udf notes ------------------------------------------------------------
("""				// already implements (low 32 -> Dn, high 32 -> MDRQ). Verified by RE of
				// the firmware's fixed-point coefficient-multiply usage
				// (e.g. `udf00 0x59ba,d1 ; add 0x2000,d1 ; asr 14,d1`, coeffs signed).
				// See notes/mn10300-udf-instructions-unimplemented.md.
""",
 """				// already implements (low 32 -> Dn, high 32 -> MDRQ). Confirmed against
				// fixed-point coefficient-multiply code
				// (`udf00 0x59ba,d1 ; add 0x2000,d1 ; asr 14,d1`, signed coefficients).
"""),

("""// [3:2]=Dm. (binutils also lists a colliding `mov Am,Rn` for F5xx, but the
// KN7000 firmware's F5 uses are the DSP put-ops; see notes/interrupt-mechanism.md.)
""",
 """// [3:2]=Dm. (binutils also lists a colliding `mov Am,Rn` for F5xx; every F5 use
// seen so far is a DSP put-op.)
"""),

("""	case 0x7: {  // udf07 Dm,Dn -- BSCH (bit search): Dn = position (0..15) of the most-significant
		// set bit in Dm's low 16 bits (0 if none). RE-CONFIRMED: this is the sole unimplemented
		// op in the software JPEG decoder (Huffman leading-run decode @0x4840FBB9); with it the
		// boot splash decodes pixel-clean (music notes / KN7000 logo) instead of noise.
		const uint32_t v = m_d[src] & 0xffff;
		m_d[dst] = v ? uint32_t(31 - __builtin_clz(v)) : 0u;
""",
 """	case 0x7: {  // udf07 Dm,Dn -- BSCH (bit search): Dn = position (0..15) of the
		// most-significant set bit in Dm's low 16 bits (0 if none). Used by the
		// Huffman leading-run decode in software JPEG decoders.
		const uint32_t v = m_d[src] & 0xffff;
		m_d[dst] = v ? uint32_t(31 - count_leading_zeros_32(v)) : 0u;
"""),
])

edit(H, [
("""// External interrupt input lines (placeholder; wire to KN7000 IRQ sources)
""",
 """// External interrupt input lines
"""),

("""	// Legacy external-INTC hooks (the on-chip INTC now lives in this core; these
	// remain so a machine may still override the vector/level directly -- the
	// KN7000 driver used them before the INTC-in-core migration). The core's own
	// INTC recompute/accept paths overwrite both from the per-level vector table.
""",
 """	// Direct vector/level override, for a machine that drives interrupts without
	// the on-chip INTC. The INTC's own recompute/accept paths overwrite both from
	// the per-level vector table.
"""),

("""	// Byte-exact port of the KN7000 driver's proven HLE (kn7000.cpp intc_r/
	// intc_w/intc_assert/intc_recompute/irq_ack before the INTC-in-core
	// refactor); the behavior was reverse-engineered from the KN7000 firmware
	// (kn7000_mame overlay: notes/interrupt-mechanism.md).
	//
	// GxICR(group)""",
 """	// Reverse-engineered from software that drives it; no datasheet was available.
	//
	// GxICR(group)"""),

("""	//  * 0x34000100/0x104 double as the IAGR the (self-loaded) library
	//    dispatcher reads: 0x34000100 returns the latched group << 3; the
""",
 """	//  * 0x34000100/0x104 double as the IAGR an interrupt dispatcher reads:
	//    0x34000100 returns the latched group << 3; the
"""),

("""	//  * group 0x17 software-trigger self-ack: writing DETECT bit0 latches
	//    DETECT+REQUEST (the KN7000 effects-DSP self-test handshake; its
	//    dsp_present() gate was constant-true, so this is unconditional).
	//  * EXTMD (0x34000280) is a latched read-back register; every write is
	//    reported outward via intc_extmd_cb (the KN7000 decodes the panel-ATN
	//    edge re-arm transition there -- board policy, stays driver-side).
	//
	// Vector delivery: the AM33 vectors each interrupt LEVEL through a machine-
	// specific handler address (KN7000: firmware quick-dispatch 0x4C03DDA0 for
	// all levels except the level-6 scheduler entry 0x4C03DE26; KN6000/KN6500:
	// trampoline 0x90000000 for every level). That mapping is board policy:
	// the machine fills the per-level table with set_maskable_vector().
""",
 """	//  * group 0x17 software-trigger self-ack: writing DETECT bit0 latches
	//    DETECT+REQUEST, which software uses to hand-shake a device self-test.
	//  * EXTMD (0x34000280) is a latched read-back register; every write is
	//    reported outward via intc_extmd_cb, so a board can decode transitions.
	//
	// Vector delivery: the AM33 vectors each interrupt LEVEL through its own
	// handler address. That mapping is board policy: the machine fills the
	// per-level table with set_maskable_vector().
"""),

("""	// Raw ICR access for POLLED lines a board drives directly (e.g. the KN7000
	// SD card-detect pin on group 0x1B). Deliberately NO recompute -- byte-
	// exact with the driver HLE's direct m_gxicr pokes (such polled lines never
	// have ENABLE set, so delivery is unaffected).
""",
 """	// Raw ICR access for POLLED lines a board drives directly (a card-detect pin,
	// say). Deliberately NO recompute: such lines never have ENABLE set, so
	// delivery is unaffected.
"""),

("""	//   intc_ack_cb    (write8, data = group): a GxICR write carried DETECT-ack
	//        bits (data & mem_mask & 0x000f). The KN7000 uses it for the panel
	//        transfer-complete "level-like until serviced" re-delivery (its
	//        c11_unserviced flag + deferred re-assert stay driver-side).
	//   intc_accept_cb (write8, data = group): this group was latched into the
	//        IAGR at interrupt accept (KN7000: group 0x11 accept clears the
	//        c11_unserviced flag).
	//   intc_extmd_cb  (write16): new EXTMD value after each write (the driver
	//        keeps its own previous-value shadow to decode transitions).
""",
 """	//   intc_ack_cb    (write8, data = group): a GxICR write carried DETECT-ack
	//        bits (data & mem_mask & 0x000f).
	//   intc_accept_cb (write8, data = group): this group was latched into the
	//        IAGR at interrupt accept.
	//   intc_extmd_cb  (write16): new EXTMD value after each write.
"""),

("""	// Modeled in the core, following the MN10200 core's precedent (its on-chip
	// serial lives in mn10200_device::m_serial[] behind an internal address
	// map). The register semantics are a byte-exact port of the KN7000 driver's
	// proven HLE (kn7000.cpp sio_r/sio_w before the SIO-in-core refactor); the
	// behavior they encode was reverse-engineered from the KN7000 firmware --
	// see notes/panel-serial-protocol.md and notes/sd-card-emulation-plan.md in
	// the kn7000_mame overlay repo.
	//
	// Channel map (KN7000): ch0 = control-panel sync link, ch1 = MIDI 1,
	// ch2 = MIDI 2. Register layout per channel (stride 0x10, 16-bit regs):
	//   +0  config   bit15 = sync-transfer START (ch0; self-clears instantly in
	//                        this HLE -- the polled boot path only)
	//                bit14 = RX enable (ch0: panel may send its queued reply)
""",
 """	// Modeled in the core, following the MN10200 core's precedent (its on-chip
	// serial lives in mn10200_device::m_serial[] behind an internal address map).
	// Reverse-engineered from software that drives it; no datasheet was available.
	//
	// Register layout per channel (stride 0x10, 16-bit regs):
	//   +0  config   bit15 = sync-transfer START (self-clears instantly here,
	//                        since transfers complete instantly)
	//                bit14 = RX enable (the endpoint may send its queued reply)
"""),

("""	//   +C  status   bit4 = RxRDY only. ch2's bit7 (RX-empty) / bit6 (TxRDY)
	//                are deliberately NOT modeled (doing so wedged boot).
""",
 """	//   +C  status   bit4 = RxRDY only; bit7 (RX-empty) and bit6 (TxRDY) are
	//                deliberately not modelled (see sio_r).
"""),

("""	// Interrupt-worthy events are routed OUT through per-channel callbacks and
	// the driver forwards them to the INTC (now also on this core -- the
	// forward is typically a thin intc_assert() call; keeping the routing in
	// the driver preserves the board-specific group numbers and deferrals):
	//   sio_tx_cb        (write8): byte written to the TX data register
	//   sio_tx_done_cb   (write_line, called with 1 per event): the transfer of
	//        that byte completed (instant-completion HLE). Invoked BEFORE
	//        sio_tx_cb, mirroring the driver HLE's order (it scheduled its
	//        deferred group-0x11 completion before handing the byte to the
	//        panel). The KN7000 driver defers this ~40us before asserting INTC
	//        group 0x11 (ch0) -- that deferral + the "level-like until
	//        serviced" re-delivery is INTC policy and stays driver-side.
	//   sio_rx_rdy_cb    (write_line, called with 1 per byte): a byte was
	//        pushed into the RX FIFO (KN7000 INTC groups: ch0 -> 0x10,
	//        ch1 -> 0x12, ch2 -> 0x14)
	//   sio_rx_enable_cb (write_line, called with 1): config bit14 written set
	//        -- ch0 only (the panel sub-CPU may now send its queued reply)
""",
 """	// Interrupt-worthy events are routed OUT through per-channel callbacks; the
	// machine forwards them to the INTC, which keeps the board-specific group
	// numbers and any deferral driver-side:
	//   sio_tx_cb        (write8): byte written to the TX data register
	//   sio_tx_done_cb   (write_line, 1 per event): that byte's transfer
	//        completed. Invoked BEFORE sio_tx_cb.
	//   sio_rx_rdy_cb    (write_line, 1 per byte): a byte was pushed into the
	//        RX FIFO
	//   sio_rx_enable_cb (write_line, called with 1): config bit14 written set
"""),

("""	// Byte-exact port of the KN7000 driver's "tempo timer" model (kn7000.cpp
	// tmr7_* -- named after its INTC group there; the register addresses are
	// the AM33 TM5: mode byte @0x34001082, 16-bit reload @0x34001092, down-
	// counter @0x340010A2). TM5 underflow asserts INTC group 7 = the KN7000
	// firmware's 96-PPQN sequencer tick (and the KN6000/KN6500 firmware's
	// ms-counter tick -- both program THIS timer). The TM4 half of each
	// register word (offset 0 of each window) keeps the driver behaviour:
	// reads 0, writes dropped; TM5BC writes fall through to the machine map
	// (the driver mapped the counter window read-only). Full RE in the
	// members' comments and kn7000_mame notes/sequenced-playback-and-style-
	// data-rootcause.md.
""",
 """	// TM5: mode byte @0x34001082, 16-bit reload @0x34001092, down-counter
	// @0x340010A2. Underflow asserts INTC group 7. The TM4 half of each register
	// word (offset 0 of each window) reads 0 and drops writes; TM5BC writes fall
	// through to the machine map, which maps the counter window read-only.
"""),

("""	// TODO(MN10300): the MN10200 overrides execute_clocks_to_cycles/cycles_to_clocks
	// for its internal /2 divider. Only add those if the KN7000 MN10300 clocking
	// requires it; otherwise the 1:1 base-class defaults are correct.
""",
 """	// TODO(MN10300): the MN10200 overrides execute_clocks_to_cycles/cycles_to_clocks
	// for its internal /2 divider. The 1:1 base-class defaults are used until a
	// machine is found that needs otherwise.
"""),

("""	// The on-chip interrupt controller (0x34000100 block, above) drives the
	// single maskable IRQ input line and supplies the address the AM33 maskable
	// vector jumps to (per-level table). On accept the core latches IAGR, pushes
	// PC+PSW and clears IE; the (self-loaded library-ROM) handler reads IAGR,
	// dispatches, acks, and returns via rti. See notes/interrupt-mechanism.md.
""",
 """	// The on-chip interrupt controller (0x34000100 block, above) drives the
	// single maskable IRQ input line and supplies the address the AM33 maskable
	// vector jumps to (per-level table). On accept the core latches IAGR, pushes
	// PC+PSW and clears IE; the handler reads IAGR, dispatches, acks and rti's.
"""),
])
print('ok')

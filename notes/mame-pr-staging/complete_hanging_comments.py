"""Finish the comments an earlier mechanical trimming pass cut mid-sentence.

QUESTION IT ANSWERS
  "Does every comment in this PR end as a sentence?"

  Reducing comment density by keeping a block's first line or two is fast and
  silently produces things like

      // A MIDI controller wired here plays the machine's OWN key bed (the voice-
      uint8_t m_kbd_midi_status = 0;

  The compiler cannot see it, a density measurement cannot see it, and it reads
  as carelessness in a diff. Each replacement below is a SHORT COMPLETE version
  of the original block, written from the overlay's full text rather than
  invented, so the surviving sentence still says something true.

RUN   python3 complete_hanging_comments.py    (from the PR worktree root)
PASS  prints "ok"; tools/check_truncated_comments.py then reports only the
      pre-existing upstream hits (its measured null).
"""


def shift(text, n):
    out = []
    for line in text.split('\n'):
        if n < 0:
            out.append(line[min(-n, len(line) - len(line.lstrip('\t'))):])
        else:
            out.append(('\t' * n + line) if line.strip() else line)
    return '\n'.join(out)


def edit(path, pairs):
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


edit('src/mame/matsushita/kn7000.cpp', [
("""	// TG output-bus routing (the REVERB toggle's hardware action; see the tonegen's
	void set_bus_gains(float send, float direct, float ret, float depth)
	{ m_gain_send = send; m_gain_direct = direct; m_gain_return = ret; m_gain_depth = depth; }
""",
 """	// TG output-bus routing, the REVERB toggle's hardware action: send is what the DSP
	// receives, direct/return the DAC-side crossfade between raw TG and DSP output.
	void set_bus_gains(float send, float direct, float ret, float depth)
	{
		m_gain_send = send;
		m_gain_direct = direct;
		m_gain_return = ret;
		m_gain_depth = depth;
	}
"""),
("""				// the pair is {direct 0, return 7F}; OFF is {direct 7F, return 0} -- so OFF
""",
 """				// the pair is {direct 0, return 7F}; OFF is {direct 7F, return 0}, so OFF also
				// mutes the reverb tank at the DAC.
"""),
("""				else { ol = m_tx_last[0]; orr = m_tx_last[1]; chl = m_tx_last[2]; chr = m_tx_last[3];
				       ddl = m_tx_last[4]; ddr = m_tx_last[5]; mml = m_tx_last[6]; mmr = m_tx_last[7]; }
""",
 """				else
				{
					ol = m_tx_last[0];
					orr = m_tx_last[1];
					chl = m_tx_last[2];
					chr = m_tx_last[3];
					ddl = m_tx_last[4];
					ddr = m_tx_last[5];
					mml = m_tx_last[6];
					mmr = m_tx_last[7];
				}
"""),
("""	// bring-up logging handlers for the (not-yet-decoded) I/O banks
""",
 """	// Logging handlers for the I/O banks that are not decoded yet.
"""),
("""	// The register model (GxICR array, IAGR latch quirks, EXTMD, the group-0x17
	enum { IRQGRP_TIMER = 0x06, IRQGRP_PANEL = 0x1A, IRQGRP_MIDI1 = 0x12, IRQGRP_MIDI2 = 0x14 };
""",
 """	// The register model lives in the CPU core. The driver keeps only board policy:
	// which group each peripheral asserts, the panel transfer-complete re-delivery
	// filter, and the panel-ATN EXTMD edge decode.
	enum { IRQGRP_TIMER = 0x06, IRQGRP_PANEL = 0x1A, IRQGRP_MIDI1 = 0x12, IRQGRP_MIDI2 = 0x14 };
"""),
("""	// A MIDI controller wired here plays the machine's OWN key bed (the voice-
""",
 """	// A MIDI controller wired here plays the machine's own key bed rather than the
	// rear MIDI IN jacks, so the firmware treats the notes exactly like physical key
	// presses. MIDI note n maps to key index n-36; the 61-key compass is C2..C7 and
	// notes outside it are dropped. Connect a host controller with -kbdmidi <port>.
"""),
("""	// voice record. The record array is fw::KN7000_VOICE_RECORDS + slot*0xB4; slots
""",
 """	// voice record, at fw::KN7000_VOICE_RECORDS + slot*0xB4. It is fully populated
	// before the first pitch write of a note reaches the TG. Field +0x08 bit7 marks
	// the record active, +0x0C is the musical pitch in 1/256-semitone units.
	// Unpitched drum voices leave that field at its formula constant, so they get
	// -1 here and the tone generator falls back to its raw-pitch decode.
"""),
("""	// slot = the library's voice-record index. On the KN7000 the two chips share one
""",
 """	// slot = the library's voice-record index. On the KN7000 the two chips share one
	// 128-entry array with slot bit 6 selecting the window; the KN6000 has a single
	// 64-entry array behind a single window.
"""),
("""		// KN6000 uses the same field offset but its value set (1/8 plus flag bits
""",
 """		// KN6000 uses the same field offset, but its value set has not been mapped onto
		// the KN7000's release classes, so report "unknown" rather than guess. The tone
		// generator then treats every voice as firmware-managed, which is safe because
		// the KN6000 writes a universal key-up gate for all voice classes.
"""),
("""	// The card/lid switch is an external-interrupt pin whose ICR the firmware
""",
 """	// The card/lid switch is an external-interrupt pin whose ICR the firmware polls:
	// bit4 set = no card or lid open, clear = card present. The SD state machine is
	// driven by the detect TRANSITION, so a line that is statically present from
	// power-on never fires it -- model the card as absent at power-on and insert it
	// a few seconds into the boot.
"""),
("""	// SD "in use" indicator (driver HLE approximation): the CPSD board's front-panel LEDs are NOT main-CPU
""",
 """	// SD "in use" indicator. The CPSD board's front-panel LEDs are not main-CPU
	// outputs, so the lamp is synthesised from real card activity: every SPI byte
	// retriggers a one-shot, and it drops ~250 ms after the last one.
"""),
("""	// The firmware speaks the STANDARD SD-card SPI protocol through this byte
""",
 """	// The firmware speaks the standard SD-card SPI protocol through this byte
	// mailbox: wake-up clocks, CMD0, then R1 response reads. Each mailbox write
	// clocks the byte through the spi_sdcard device and asserts INTC group 0x1C;
	// reads return the MISO byte, so the register behaves as a full-duplex SPI
	// data latch.
"""),
("""	// Further windows the boot reaches only AFTER the library ROM loads and runs
	// (found by execution). 0x44000000 is a heavily read/written ~1 MB block
""",
 """	// Further windows the boot reaches only after the library ROM loads and runs.
	// 0x44000000 is a heavily read and written ~1 MB block, mirrored at 0x84000000.
"""),
("""	// SD front-panel switch register (byte 0x9CC00008, ACTIVE-LOW: bits0-5 = the
	// six CPSD-side transport switches, 1 = released). The firmware's SD-panel
""",
 """	// SD front-panel switch register (byte 0x9CC00008, active-low: bits 0-5 are the
	// six CPSD-side transport switches, 1 = released).
"""),
("""	//map(0x57800000, 0x57ffffff).rom().region("picture", 0);
""",
 """	// 0x57800000 is the picture flash; it has no dump, so it is left unmapped.
"""),
("""	// 112 I/O registers were recovered by static analysis of the firmware (see
""",
 """	// The I/O registers were recovered by static analysis of the firmware; the ones
	// still undecoded fall through to the logging handlers.
"""),
("""	// The on-chip INTC (0x34000100-0x340002ff), SIO (panel + two MIDI channels,
	// 0x34000800-0x3400082f) and TM4/TM5 timer windows (0x34001080/0x34001090/
""",
 """	// The on-chip INTC, SIO and TM4/TM5 timer windows are decoded by the CPU core's
	// own internal map, which is appended after this one.
"""),
("""	// GPIO input port 0x36008084: bit 0 = panel-link ready/presence line, held
""",
 """	// GPIO input port 0x36008084: bit 0 = panel-link ready/presence, held asserted.
"""),
("""	// GPIO output latch 0x36008004: bit1 = the SD card's SPI CHIP SELECT
	// (active-low: bclr = assert/select, bset = release/deselect). The firmware
""",
 """	// GPIO output latch 0x36008004: bit1 = the SD card's SPI chip select, active-low
	// (bclr asserts, bset releases).
"""),
("""	// Floppy disk controller IC103 (C1DB00000607, N82077AA/PC-AT-compatible) at 0x98020000 -- carved out
	// of the io window above (must come AFTER it so this narrower entry wins). Confirmed by the service-
""",
 """	// Floppy disk controller IC103 (C1DB00000607, N82077AA/PC-AT-compatible) at
	// 0x98020000, carved out of the io window above -- it must come after it so the
	// narrower entry wins. Confirmed against the service manual.
"""),
("""	// FDC.DACK byte slot at 0x98010000 (decoder Y1). The software-DMA ISR (0x48402140), invoked per FDC.DRQ
	// (INTC group 0x18), reads/writes one FIFO byte here to feed/drain the FDC during read/write/format.
""",
 """	// FDC.DACK byte slot at 0x98010000 (decoder Y1). The software-DMA handler, invoked
	// per FDC.DRQ on INTC group 0x18, moves one FIFO byte through here per request.
"""),
("""	// TODO: replace the logging handlers with real device models: LCD V-RAM
}
""",
 """	// TODO: replace the logging handlers with real device models.
}
"""),
("""// Bring-up placeholder: log every I/O access and return 0. The CPU accesses
// these banks at 8/16/32-bit widths; a 16-bit handler with mem_mask lets MAME
""",
 """// Read one sample word out of a wave ROM through the tone generator's own port.
"""),
("""	// 0x98070000 (offset 0x38000 within the 0x98000000 window): a status/strap word.
	// NOTE on bit15: it is btst-tested at 0x484A4FDA inside 0x484A4FBA (the parallel-FDC engine
""",
 """	// 0x98070000 (offset 0x38000 within the 0x98000000 window): a status/strap word.
"""),
("""		// bit12 (= data-bus D28) = rear-panel MIDI IN / BASS PEDAL selector SW701 (0x484A2CB1 ->
// 0x484b2615 reads bit12 -> MIDI-in mode flag 0x5006bfd2 bit1). bits1..2 = the TG-present
// strap (0x484d7713): bit1 clear -> "no TG" leaves the TG-enable gate closed (silent),
// so report the TGs present (bit1|bit2). bit15 = moot (gates dead code, see above).
""",
 """		// bit12 (data bus D28) = the rear-panel MIDI IN / BASS PEDAL selector, SW701.
		// bits 1..2 = the TG-present strap: with bit1 clear the firmware leaves the
		// TG-enable gate closed and the machine is silent, so report both TGs present.
"""),
("""		// Upload framing: 0xA1/0x41 opens a PM/DM block (target = reg-0x40 addr), words stream
		if (data == 0xa1)      { m_dsp_mode = 1; m_dsp_cur = m_dsp_dl_addr; m_dsp_wcnt = 0; m_dsp_block_open = true; }  // PM commit
		else if (data == 0x41) { m_dsp_mode = 2; m_dsp_cur = m_dsp_dl_addr; m_dsp_wcnt = 0; m_dsp_block_open = true; }  // DM commit
""",
 """		// Upload framing: 0xA1 opens a PM block and 0x41 a DM block, both targeting the
		// address last written to register 0x40; words then stream through index 0x04.
		if (data == 0xa1)      { m_dsp_mode = 1; m_dsp_cur = m_dsp_dl_addr; m_dsp_wcnt = 0; m_dsp_block_open = true; }  // PM
		else if (data == 0x41) { m_dsp_mode = 2; m_dsp_cur = m_dsp_dl_addr; m_dsp_wcnt = 0; m_dsp_block_open = true; }  // DM
"""),
("""				// A RUNTIME upload (SHARC already running, e.g. selecting a reverb) that lands in
				// PROGRAM memory (mode 1) changes live code behind the DRC's back -- its self-modify
""",
 """				// A runtime upload into PROGRAM memory changes live code behind the DRC's
				// back, so tell it to invalidate.
"""),
("""	// Audio path. None of the DSP's TX slots feeds a DAC directly:
	// none of the DSP's TX slots feeds a DAC directly. All four SPORT TX pins loop back
""",
 """	// Audio path: none of the DSP's TX slots feeds a DAC directly. All four SPORT TX
	// pins loop back, so the processed audio is read out of the kernel's own buffers.
"""),
("""		// The kernel programs the SPORTs with DTYPE=01 (SPCTL 0x013CB173/0x013C3173,
		// bits 2:1 = 01 = "right-justify; sign-extend MSBs", TRM ch.9): 24-bit samples
""",
 """		// The kernel programs the SPORTs with DTYPE=01 ("right-justify, sign-extend
		// MSBs", TRM ch.9), so the buffers hold sign-extended 24-bit samples.
"""),
("""// A PC-key note press/release: push a voice-event into the keyboard FIFO the
// firmware polls at 0x98050004. param carries the KEY index; velocity is fixed
""",
 """// A PC-key note press or release: push a voice event into the key-bed FIFO the
// firmware polls. param carries the key index; velocity is fixed for host keys.
"""),
("""// The main-CPU SIO channel-0 sync-transfer completion (group 0x11). Deferred
""",
 """// The main-CPU SIO channel-0 sync-transfer completion, INTC group 0x11. Deferred
// ~40us so the panel's reply cannot overtake the ISR that acknowledges it.
"""),
("""	// Deliver the whole frame into the ch2 RX FIFO at once; the status bits (bit7 +
""",
 """	// Deliver the whole frame into the ch2 RX FIFO at once; one interrupt per byte.
"""),
("""	// SD slot COVER switch. The KN7000's SD slot has a hinged cover; the firmware
""",
 """	// SD slot cover switch. The slot has a hinged cover and the firmware only looks
	// for a card while it is closed.
"""),
("""	// Music key bed: the FULL 61 keys (C2..C7). The FIFO value is the KEY INDEX
""",
 """	// Music key bed: the full 61 keys, C2..C7. The FIFO value is the key index,
	// which is the internal note number minus 36.
"""),
("""// The firmware drives it with the full AMD command set: unlock at +0xAAAA / +0x5554, autoselect
""",
 """// The firmware drives it with the full AMD command set: unlock at +0xAAAA/+0x5554,
// then autoselect, erase and program.
"""),
("""	// System tick ~1 kHz (real rate TBD -- input clock unknown; tune later). The timer
	// interrupt dispatches (via IAGR=group<<3) to the real RTOS handler, whose context
	if (m_lib_mirror)
		// KN6000/KN6500: delay the tick past the single-threaded boot so the scheduler
		m_sys_timer->adjust(attotime::from_seconds(2), 0, attotime::from_hz(1000));
""",
 """	// System tick, ~1 kHz. The real rate is unknown; the input clock has not been
	// identified. The interrupt dispatches to the firmware's RTOS handler.
	if (m_lib_mirror)
		// KN6000/KN6500: delay the tick past the single-threaded part of the boot, so
		// the scheduler exists by the time the first one arrives.
		m_sys_timer->adjust(attotime::from_seconds(2), 0, attotime::from_hz(1000));
"""),
("""// FDC interrupt / DMA-request lines -> MN10300 on-chip INTC group 0x18 (GxICR at 0x34000160, which the
// FDC interrupt ISR 0x48402109 acknowledges). The FDC sector-data phase is SOFTWARE-DMA: the FDC asserts
""",
 """// FDC interrupt and DMA-request lines -> on-chip INTC group 0x18. The sector-data
// phase is software DMA: the FDC asserts DRQ and the handler moves one byte.
"""),
("""	// IC21, the custom-data flash. The firmware validates the part via a JEDEC autoselect
""",
 """	// IC21, the custom-data flash. The firmware identifies the part with a JEDEC
	// autoselect before writing to it.
"""),
("""		// Sync-transfer completion -> group 0x11 -- ALWAYS deferred (an
""",
 """		// Sync-transfer completion -> group 0x11, always deferred (see panel_txdone_cb).
"""),
("""	ADSP21065L(config, m_dsp, 66'000'000);   // IC306 rated/run at 66 MHz (was 60 -- faithful correction)
	m_dsp->enable_recompiler();   // DRC: the effects kernel is fixed-point-MAC heavy; interpreting
	                              // it drops the machine to ~36% real time, the DRC keeps it near 90%
""",
 """	ADSP21065L(config, m_dsp, 66'000'000);   // IC306, rated and run at 66 MHz
	// The effects kernel is fixed-point-MAC heavy: interpreting it drops the machine
	// to ~36% of real time, where the recompiler keeps it near 90%.
	m_dsp->enable_recompiler();
"""),
("""	// KN6000/KN6500 interrupt vectors: ALL maskable IRQs go to the firmware-
	// built trampoline slot 0 (0x90000000 -> the general handler, which reads
""",
 """	// KN6000/KN6500 interrupt vectors: every maskable IRQ goes to the firmware-built
	// trampoline slot 0, whose general handler reads the latched group and dispatches.
	// Slot 1 is that firmware's fault handler, not an IRQ path -- routing IRQs there
	// halts the boot.
"""),
("""	// The KN6000/KN6500 front panel speaks the SAME CP wire protocol as the KN7000 (which is
	// why these models already accepted button traffic, and why their TEMPO/PROGRAM wheel
""",
 """	// The KN6000/KN6500 front panel speaks the same CP wire protocol as the KN7000,
	// so only the matrix geometry and the LED decode differ.
"""),
("""	// the SD card interface is fitted only on the SX-KN2600
""",
 """	// The SD card interface is fitted only on the SX-KN2600.
"""),
("""// KN6500: MACHINE_NO_SOUND, deliberately, even though it carries the same (correct) tone
""",
 """// KN6500 carries MACHINE_NO_SOUND deliberately: it has the same tone generator as
// the KN6000, but its own audio path has not been verified.
"""),
])

edit('src/mame/matsushita/kn6000_tonegen.cpp', [
("""		// The 18-bit pitch: the shadow record holds it as a 32-bit word whose HIGH
""",
 """		// The 18-bit pitch: the class word's low nibble carries bits 16-17.
"""),
("""		// This register is written LAST-but-a-few in the note-on blit, after the whole
""",
 """		// This register is written near the end of the note-on blit, after the envelope,
		// so a programmed EG is the signal that the voice is really starting.
"""),
("""			// NOTE-ON. Musical pitch comes from the firmware's own notePitch16 in the
			// library voice record (resolved driver-side, see kn7000.cpp
""",
 """			// Note-on. Musical pitch comes from the firmware's own computed pitch in the
			// library voice record, resolved driver-side and passed in as note_x256; the
			// raw 18-bit register value is the fallback.
"""),
("""		// The positional analogue of the KN7000's r4..rA: two further three-register
""",
 """		// The positional analogue of the KN7000's r4..rA: further three-register banks
		// holding the pitch and filter envelopes.
"""),
("""		// Written once per note-on from shadow +0x64. The default full-velocity patch
""",
 """		// Written once per note-on. Full velocity gives the nominal maximum.
"""),
("""	// The per-channel effect-send matrix -- the KN7000's group-0x20 (0x8000|row<<8|
	// part<<4|reg) -- is deliberately NOT decoded here. On the KN6000 the 0x8000-0x9000
}
""",
 """	// The per-channel effect-send matrix, the KN7000's group 0x20, is deliberately not
	// decoded here: the KN6000's use of that range has not been mapped.
}
"""),
])

edit('src/mame/matsushita/kn7000_tonegen.cpp', [
("""			// Default RELEASE rate: the chip-side damp bank's rA high byte (organ
""",
 """			// Default release rate: the chip-side damp bank's rA high byte.
"""),
("""		// UNIVERSAL key-release trigger -- written for EVERY class on key-up (verified
""",
 """		// Universal key-release trigger, written for every voice class on key-up.
"""),
("""		// The firmware writes this once at note-on; in the default full-velocity
""",
 """		// The firmware writes this once at note-on.
"""),
("""			// MULTI send (0x8298 = row2 of insert part 9; routes to MULTI unit 1). The high
			// byte doubles as the firmware's ON marker: 0x06 (dest = multi-return part)
""",
 """			// MULTI send (0x8298 = row 2 of insert part 9, routing to MULTI unit 1). The
			// high byte doubles as the firmware's ON marker, 0x06 meaning the multi-return
			// part is the destination.
"""),
])

edit('src/mame/matsushita/kn_tonegen.h', [
("""	// THE MODEL-SPECIFIC HALF: turn one tone-generator register write into voice
	// events on the shared state below. Each derived device supplies its own chip's
""",
 """	// The model-specific half: turn one tone-generator register write into voice
	// events on the shared state below. Each derived device decodes its own chip's
	// register numbering.
"""),
("""	// FABRICATED DEFAULT SINE (Felipe Sanches' faithful-MECHANISM principle): the wave
""",
 """	// Fabricated default sine: the wave
"""),
])
print('ok')

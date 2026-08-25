// license:GPL-2.0+
// copyright-holders:Felipe Sanches
/***************************************************************************

    Technics SX-WSA1R

    *** THIS IS THE DEVELOPMENT VERSION OF THIS DRIVER ***

    It lives in the kn7000_mame overlay repository and is built by that
    repository's build.sh, alongside kn5000, kn7000, kn6000, kn6500, kn2400,
    kn2600 and kn1500.  A second, deliberately smaller copy of this file is
    the one offered upstream: it sits on the branch `technics-wsa1` in the
    MAME checkout, and it carries only the two processors, the clock and the
    part of the memory map that is evidence-complete enough to submit.

    The two files WILL DIVERGE, and that is intentional.  Everything added
    here beyond the upstream copy is work in progress: the LCD controller and
    its screen, the link between the two processors, and a set of write-only
    register-file stubs for the devices on the second processor's chip-select
    zero cluster.  Several of those rest on inferences that a MAME reviewer
    would rightly refuse until a schematic or a real machine confirms them,
    and each such inference is marked where it is made.  Do not treat this
    file as the submission candidate, and do not "sync" one from the other
    mechanically -- move a piece across only once its evidence is complete.

    A 1995 rack-mounted "Acoustic Modeling Synthesis" synthesizer module:
    64 notes over up to 32 parts, 256 preset sounds, 16 preset drum kits and
    128 preset combinations, a 320 x 240 dot LCD, two sets of MIDI IN/OUT/THRU
    and a built-in 3.5 inch floppy drive.

    This driver does not run the machine yet, but both processors are now
    instantiated, with the clock and the part of the memory map that could be
    established.  Unlike the MN10300-based Technics keyboards in kn5000.cpp and
    kn7000.cpp, the CPU core is not what is missing here: the two processors are
    Toshiba TLCS-900/H parts, TMP95C061, and MAME already implements that device
    in src/devices/cpu/tlcs900/tmp95c061.h.  What was missing was a clock and a
    memory map, and both were recovered from the images rather than from the
    book, by a byte-exact disassembly of the two boot paths kept outside this
    tree in wsa1-roms-disasm: notes/FINDINGS-system-clock.md,
    notes/FINDINGS-memory-map.md, and the two reset blocks themselves converted
    to assembly in prom_a/wsa1_prom_a.s and prom_c/wsa1_prom_c.s.

    The clock is fc = 28 MHz, and the firmware is what says so.  prom_c does not
    hard-code a serial divisor, it computes one: at 0xF991A2 it reads the byte at
    0xFFFFEF and writes BR0CR = (M >> 1) & 0x0F.  Under that rule the bit rate
    comes out at 31250 for any M provided fc = 1,000,000 * M, so the byte is fc
    in MHz, and prom_c[0xFFFFEF] = 0x1C = 28.  Two constants that share nothing
    with it agree: the sequencer tempo divide at 0xFAA378 uses 140,000,000,
    which is 5 * fc for timer 4 running at fc/8 with 96 ticks per beat, and the
    (*) see the prescaler note below
    MIDI init at 0xFA58F8 sets BR0CR = 0x0E, that is fc/896 = 31250 baud.  The
    MIDI divisor alone would not have settled it: both boot blocks first program
    a divide by 768 (0xF82754, 0xFFF078), which is self-consistent with a 24 MHz
    part, and the parts list has a 24 MHz ceramic oscillator as well as a 28 MHz
    one.  The tempo constant is what excludes that reading.

    The memory map below is only what the code establishes: the chip-select
    programming in the two boot blocks (0xF8272D onwards on the first processor,
    0xFFF038 onwards on the second), the RAM those blocks clear, and the
    peripheral addresses the firmware demonstrably reads or writes.  Everything
    else is left unmapped on purpose.  The service manual scan available here
    resolves the names of the ROM chip-select nets (PROMACS, PROMBCS, PROMCCS
    and PROMDCS) without resolving the address ranges the decoders assign to
    them, so the ranges come from the firmware alone; the MAMR window sizes in
    particular rest on an elimination over eight candidate decoders fed this
    machine's own register values, not on a databook, and one window, the first
    processor's CS0, survives that elimination in two readings that differ.  The
    devices on it are mapped because each address is referenced directly by the
    code; the window itself is not asserted anywhere below.

    ONE INFERENCE THE MAP RESTS ON.  CPU 2's CS2 is proven 16 bits wide (the
    flash unlock addresses at 0xFC8662/0xFC8672 are 0xAAAA/0x5554, twice the
    AMD byte-mode pair).  CPU 1 carries the same B2CS = 0x1B, so prom_a and
    prom_b are taken to be x16 as well -- inferred, not proven.  The mapping
    below asserts a flat byte image per device, which is only correct under
    that inference.  It is corroborated empirically rather than assumed: the
    reset chain 0xF827C4 -> prom_b file 0x42D60 -> prom_a 0x5606, and the SWI7
    vector 0xFFFF1C -> prom_b file 0x400A4, all land on sane instructions, and
    one byte of base error would destroy every one of those cross-references.

    (*) A WARNING FOR ANYONE CHECKING THAT AGAINST THE INSTANTIATED DEVICE.
    The fc/8 tap above is the TMP94C241 prescaler scale, not the one MAME's
    tmp95c061 implements: src/devices/cpu/tlcs900/tmp95c061.cpp:683-689 gives
    phi-T1 as m_timer_pre >> 7, that is fc/128, a factor of 16 away, and that
    device does not implement the 16-bit timers 4-7 at all (treg45_w at :1012
    and t4mod_r/w at :1028-1035 are register stubs with no counting logic).
    The firmware itself adjudicates, with a ratio that does not depend on fc:
    the tempo path multiplies by 1750 (muls WA,0x06D6 at 0xFA5553), which fits
    the TMP94C241 tap scale to 2.3% and misses the tmp95c061 scale by 16.4x.
    So the ROM picks the fc/8 reading, and the implication is that MAME's
    tmp95c061 prescaler is probably wrong for this part.  Nothing in this
    driver depends on it -- no timer is wired up here -- but it is the first
    thing that will look inconsistent to a reader, so it is stated rather than
    left to be rediscovered.

    Still not established, and therefore not modelled: the part number of most
    devices on either processor's CS0 area (the notes mostly describe register
    interfaces rather than parts; the display controller at 0x790000 is the one
    exception, see the TODO below), which of IC1 "MAIN" and IC2 "SUB" fetches
    which pair of EPROMs, the bit layout of BnCS, BEXCS, DREFCR and DMEMCR, and
    the base address of the fourth EPROM image.  Recursive descent from the
    vectors currently reaches 36.7% of the first processor's two EPROMs and
    42.6% of the second's, so a device touched only from code that has not been
    reached would still be missing from the map.

    Hardware inventory below is taken from the SX-WSA1R service manual,
    ORDER NO. EMiD951604, (c) 1995 Matsushita Electric Industrial.  That book
    covers the rack module only.  A keyboard version of this instrument
    exists, the SX-WSA1, and it is not declared in this driver: the only claim
    that it runs the same ROM set is the redistributor's, and no SX-WSA1
    material was available here to check it against.

    The scan available here is photocopy grade.  Several part numbers are
    printed differently on the schematic sheets and in the parts list, and a
    number of reference designators did not survive at all.  Where the two
    disagree, both readings are given below; where a designator is derived
    rather than read, it is marked as derived.

    *** PROVENANCE OF THE IMAGES BELOW - PLEASE READ BEFORE CHANGING THEM ***

    These are not chip reads.  Nobody working on this driver has read an
    SX-WSA1R EPROM.  The four images below are the firmware set that has been
    publicly redistributed for this machine, as an "SX-WSA1(R) v2 firmware"
    archive on synthesizer preservation sites; the copy used here was
    downloaded in August 2026 and is also mirrored on archive.org.  Its
    uploader states the set was read from a rack SX-WSA1R.  They are declared
    without a dump-quality flag because nothing suggests the bytes are wrong:
    what is second-hand here is the provenance, not the integrity.  Four
    checks, all reproducible from the images and the manual, agree with each
    other:

      - each image is 524,288 bytes, exactly one device of the width the
        block diagram requires of the program EPROMs.  It draws them on
        A1-A18 with D0-D15, that is 256K x 16 = 4 Mbit.  (The parts list gives
        the service blank as M27C400210F1, but that is one degraded token and
        the block diagram is the better source for the organisation.)

      - three of the four images end with their own build tag: "wsaa_822",
        "wsac_230" and "wsad_54", the first two separated from a trailing
        "ssf" by a 0x02 byte and the third by a period.  Those A, C and D
        letters match the AX, CX and DX endings of the factory part numbers
        QSIGCWSA1AX, QSIGCWSA1CX and QSIGCWSA1DX printed in the manual.

      - the firmware's own ROM VERSION screen, in the A image at file offset
        0x2B09, has exactly three slots, labelled "WSA-A:", "WSA-C:" and
        "WSA-D:".  The one image that carries no build tag is the fourth one,
        and there is no "WSA-B:" line for it.

      - the A and C images each carry a TLCS-900/H interrupt vector table in
        their last 256 bytes: 33 of those 64 words point into 0xF00000-0xFFFFFF,
        against 3 and 0 for the other two images, which serve as the negative
        control.  Each of the two reset entries disassembles as TMP95C061
        startup code, storing to the watchdog and memory-controller registers
        in the internal I/O area.  That matches the two TMP95C061AF the manual
        places at IC1 and IC2.

    "v2.0" is the name the set circulates under.  It appears in neither the
    service manual nor any of the four images; the only version strings the
    firmware carries are the three build tags above.

    TODO:
      - identify the remaining devices on both processors' CS0 areas.  The
        display controller at 0x790000 IS NOW WIRED UP: it is an SED1330-family
        part, established from the images (the driver writes 13 distinct command
        bytes, all of them inside MAME's SED1330 instruction table, and its
        SYSTEM SET at 0xF8E81E describes a 320 x 240 single-bit panel with three
        OR-composited layers), which agrees with the SED1330FBA the parts list
        puts at IC7.  Still unidentified: 0x7A0000, 0x7B0004/5, 0x7E0008 and
        0x7F0000 on the first processor, and the register file at 0x104000 on
        the second
      - work out which processor is IC1 "MAIN" and which is IC2 "SUB".  The link
        between them IS NOW WIRED UP (byte port plus strobe/busy handshake plus
        micro-DMA channels 2 and 3, at 0x7C0000 on one side and 0x100000 on the
        other), but the cross-wiring of the four handshake pins is derived from
        the firmware and not from a schematic -- see the block comment on the
        handlers
      - fix the base address of the fourth EPROM image, which is strongly
        supported as the content of the 512 KiB flash at 0xE80000 on the second
        processor but not proven
      - dump the six 16 Mbit wave mask ROMs, the AM29F400T flash, and the
        internal ROM of the control panel microcontroller
      - devices with no MAME implementation yet: the L7A1429 modeling LSI, the
        uPD6383GF-3BA DSP, the M37471M2196S panel MCU and the uPD72070 floppy
        disk controller

***************************************************************************/

#include "emu.h"

#include "cpu/tlcs900/tmp95c061.h"
#include "video/sed1330.h"

#include "emupal.h"
#include "screen.h"

#define LOG_LINK     (1U << 1)   // every byte and handshake edge on the CPU link
#define LOG_LINKLOST (1U << 2)   // a link latch overwritten before it was read
#define LOG_TG       (1U << 3)   // tone generator, 0x10C000
#define LOG_SYNTH2   (1U << 4)   // the second register file, 0x104000
#define LOG_KEYBED   (1U << 5)   // keybed data/status, 0x108000
#define LOG_CHANREG  (1U << 6)   // the 4 x 32 channel register file, 0xE00000

// LOG_LINKLOST is on by default on purpose: the one-byte-deep model of the link
// can only drop a byte silently, and this is how that shows up.  See risk (1)
// in the block comment on the link handlers.
#define VERBOSE (LOG_LINKLOST)
#include "logmacro.h"


namespace {

class wsa1_state : public driver_device
{
public:
	wsa1_state(const machine_config &mconfig, device_type type, const char *tag)
		: driver_device(mconfig, type, tag)
		, m_cpu1(*this, "cpu1")
		, m_cpu2(*this, "cpu2")
		, m_lcdc(*this, "lcdc")
	{ }

	void wsa1r(machine_config &config) ATTR_COLD;

protected:
	virtual void machine_start() override ATTR_COLD;
	virtual void machine_reset() override ATTR_COLD;

private:
	void cpu1_map(address_map &map) ATTR_COLD;
	void cpu2_map(address_map &map) ATTR_COLD;
	void lcdc_map(address_map &map) ATTR_COLD;

	void palette_init(palette_device &palette) ATTR_COLD;

	// The link between the two processors.  See the block comment above the
	// handler bodies for what each line does and where the firmware says so.
	uint8_t cpu1_link_r();
	void cpu1_link_w(uint8_t data);
	uint8_t cpu2_link_r();
	void cpu2_link_w(uint8_t data);

	uint8_t cpu1_p7_r();
	void cpu1_p7_w(uint8_t data);
	uint8_t cpu2_pa_r();
	void cpu2_pa_w(uint8_t data);

	// ---------------- CPU 2's CS0 device cluster: STUBS ----------------------
	//
	// MSAR0 = 0x10 / MAMR0 = 0x07 (0xFFF038, 0xFFF03B) put a 256 KiB window at
	// 0x100000-0x13FFFF, and the firmware touches exactly four 0x4000-aligned
	// points inside it -- 0x100000, 0x104000, 0x108000, 0x10C000 -- which reads
	// as A14/A15 driving a two-to-four decoder.  That is a READING of the
	// address pattern; no decoder is legible in the manual scan available here.
	//
	// Each of the four is an address-latch plus data-register pair.  NOTHING
	// BELOW SYNTHESISES ANYTHING: the register files are storage, so that the
	// debugger can see what the firmware programmed, and every read answers with
	// the value that means "idle", which is what lets the firmware's polls
	// terminate.
	//
	// The reads are the load-bearing part.  A register file that answers 0 to
	// the voice-status queries reports "no voice is sounding", so the firmware's
	// allocator always finds a free voice and never waits for one.
	static constexpr unsigned TG_REG_COUNT = 0x1000;   // register = (plane << 6) | voice

	// 0x10C000 -- the tone generator.  TC183C230002 (IC4), the same part number
	// the KN5000 carries at IC303 (see kn5000_tonegen.h).
	void     tg_addr_w(uint16_t data);
	void     tg_data_w(uint16_t data);
	uint16_t tg_status_r();

	// 0x104000 -- a second 64-slot register file of the same family.  Part NOT
	// IDENTIFIED.  Write-only in every code path reached so far.
	void     synth2_addr_w(uint16_t data);
	void     synth2_data_w(uint16_t data);
	uint16_t synth2_data_r();

	// 0x108000 -- keybed DATA (+0) and STATUS (+2).
	uint16_t keybed_data_r();
	uint16_t keybed_status_r();
	void     keybed_data_w(uint16_t data);
	void     keybed_status_w(uint16_t data);

	// 0xE00000 -- the 4-channel x 32-register board-level file.
	void     chanreg_addr_w(uint16_t data);
	void     chanreg_data_w(uint16_t data);
	uint16_t chanreg_data_r();

	required_device<tmp95c061_device> m_cpu1;
	required_device<tmp95c061_device> m_cpu2;
	required_device<sed1330_device> m_lcdc;

	uint8_t  m_link_to_cpu2 = 0;            // the byte CPU 1 last wrote to 0x7C0000
	uint8_t  m_link_to_cpu1 = 0;            // the byte CPU 2 last wrote to 0x100000
	bool     m_link_to_cpu2_full = false;   // instrumentation only, see LOG_LINKLOST
	bool     m_link_to_cpu1_full = false;
	uint8_t  m_cpu1_p7 = 0xff;              // CPU 1's P7 output latch
	uint8_t  m_cpu2_pa = 0x03;              // CPU 2's PA output latch

	uint16_t m_tg_latch = 0;
	uint16_t m_tg_regs[TG_REG_COUNT]{};
	uint16_t m_synth2_latch = 0;
	uint16_t m_synth2_regs[TG_REG_COUNT]{};
	uint8_t  m_chanreg_addr = 0;
	uint8_t  m_chanreg[0x100]{};
};


/***************************************************************************

    THE LINK BETWEEN THE TWO PROCESSORS

    One byte-wide port on each side - 0x7C0000 on CPU 1, 0x100000 on CPU 2 -
    plus four handshake pins, plus one micro-DMA channel in each direction.
    The protocol is written up in wsa1-roms-disasm/notes/FINDINGS-interprocessor-link.md;
    what matters for the model is this:

      * a byte written to the port lands in the far processor's latch and
        raises its INT0.  INT0 is LEVEL triggered on both sides
        (0xF8277B ldio IIMC,0x05 and 0xFFF00B ldio IIMC,0x04, bit 1 clear),
        so the far read is what releases the line;

      * the FIRST byte of a message is taken by the CPU, which reads it as a
        command, works out how many bytes follow, arms micro-DMA channel 3 for
        them (DMAD3/DMAC3, DMAM3 = 0x00 = destination-increment, source pinned
        at the port by the link init at 0xF8E01E / 0xF99970) and then writes
        DMA3V = 0x0A.  0x0A << 2 = 0x28 = INT0's own vector, so every FURTHER
        byte is absorbed by the DMA engine and never reaches the CPU.  Nothing
        here has to know that: the DMA reads go through the address space like
        any other read, so the same read handler serves both;

      * the sender pushes its bytes with micro-DMA channel 2 (DMAS2/DMAC2,
        DMAM2 = 0x08 = source-increment, destination pinned at the port by
        0xF8E011 / 0xF99963), paced by timer 2 - DMA2V = 0x12, 0x12 << 2 =
        0x48 = INTT2 (0xF8E166 / 0xF99A2A).  With T23MOD = 0x0E and TREG2 = 5
        that is on the order of one byte every couple of thousand cycles.

    Both halves run the SAME driver, mirrored: the micro-DMA helper block at
    prom_a 0xF8E6A2-0xF8E6E1 is byte-identical to prom_c 0xF99FF8-0xF9A037.

    THE HANDSHAKE PINS.  P7CR = 0x33 (0xF826CA) makes CPU 1's P7 bits 0, 1, 4
    and 5 outputs; PACR = 0x03 (0xFFF02C) makes CPU 2's PA bits 0 and 1
    outputs.  Bit 0 is a strobe, held low from just before the header byte
    until the far side answers; bit 1 is a "receiver busy", driven low by the
    INT0 handler once channel 3 is armed and released when the exchange ends.
    Bits 2 and 3 are the far side's bit 0 and bit 1:

        CPU 1 P7.0 -> CPU 2 PA.2      CPU 2 PA.0 -> CPU 1 P7.2
        CPU 1 P7.1 -> CPU 2 PA.3      CPU 2 PA.1 -> CPU 1 P7.3

    (*) THAT CROSS-WIRING IS DERIVED FROM THE FIRMWARE, NOT FROM A SCHEMATIC,
    and the manual scan available here does not resolve these nets.  It is the
    only assignment that satisfies all three uses at once: the sender waits for
    bit 3 to FALL after writing the header (0xF8E136), which under this mapping
    means "the far side has armed its DMA and can absorb the burst"; the INT0
    handler drops the interrupt when bit 2 is SET (0xF8E489), which means "no
    far strobe, so nobody is talking to me"; and the general sender waits for
    bit 3 to be SET before starting (0xF999D0), which means "the far receiver
    is idle".  The one competing reading - that bits 2 and 3 are full/empty
    flags of a latch in glue logic - is rejected because a latch-empty flag
    would fall when the receiver READS the byte (0xF99BD3), which is BEFORE the
    DMA is armed, and the sender would then start the burst too early.  If a
    legible schematic ever contradicts this, only the four lines in
    cpu1_p7_r() and cpu2_pa_r() have to change.

    WHAT THIS MODEL DOES NOT GUARANTEE.  The latch is one byte deep, and real
    hardware has no per-byte handshake during a burst: the strobe is released
    BEFORE the body and the receiver's DMA is expected to keep up.  The model
    relies on set_input_line() enqueuing on a zero-delay timer, which aborts
    the sending processor's timeslice, plus the shortened scheduling quantum in
    wsa1r().  That is a scheduling argument, not a proof, which is why
    LOG_LINKLOST is compiled in by default.  If it ever fires, the remedy used
    on the KN5000 was a perfect_quantum() inside each write handler; see
    notes/upstream-patches/kn5000-26-intercpu-latch-int0-handshake.patch.

    NO CPU-CORE CHANGE IS PROPOSED, deliberately.  The KN5000 needed
    tmp94c241_device::clear_int0_level() because that device re-asserts a
    level-detect INT0 flag from tlcs900_check_irqs(); tmp95c061 has no such
    code, so the deferred CLEAR_LINE is benign here.  If that re-assertion
    block is ever ported into tmp95c061, THIS DRIVER BREAKS and will need the
    same treatment.

***************************************************************************/

void wsa1_state::cpu1_link_w(uint8_t data)
{
	if (m_link_to_cpu2_full)
		LOGMASKED(LOG_LINKLOST, "%s: CPU 1 overwrote an unread link byte (0x%02X -> 0x%02X)\n",
			machine().describe_context(), m_link_to_cpu2, data);

	LOGMASKED(LOG_LINK, "%s: CPU 1 -> CPU 2: 0x%02X\n", machine().describe_context(), data);

	m_link_to_cpu2 = data;
	m_link_to_cpu2_full = true;
	m_cpu2->set_input_line(TLCS900_INT0, ASSERT_LINE);
}

uint8_t wsa1_state::cpu1_link_r()
{
	if (!machine().side_effects_disabled())
	{
		m_link_to_cpu1_full = false;
		m_cpu1->set_input_line(TLCS900_INT0, CLEAR_LINE);
	}

	return m_link_to_cpu1;
}

void wsa1_state::cpu2_link_w(uint8_t data)
{
	if (m_link_to_cpu1_full)
		LOGMASKED(LOG_LINKLOST, "%s: CPU 2 overwrote an unread link byte (0x%02X -> 0x%02X)\n",
			machine().describe_context(), m_link_to_cpu1, data);

	LOGMASKED(LOG_LINK, "%s: CPU 2 -> CPU 1: 0x%02X\n", machine().describe_context(), data);

	m_link_to_cpu1 = data;
	m_link_to_cpu1_full = true;
	m_cpu1->set_input_line(TLCS900_INT0, ASSERT_LINE);
}

uint8_t wsa1_state::cpu2_link_r()
{
	if (!machine().side_effects_disabled())
	{
		m_link_to_cpu2_full = false;
		m_cpu2->set_input_line(TLCS900_INT0, CLEAR_LINE);
	}

	return m_link_to_cpu2;
}


// P7CR = 0x33 (0xF826CA): bits 0, 1, 4 and 5 are outputs, 2, 3, 6 and 7 inputs.
// port_r<PORT_7>() returns the callback's value verbatim - it does not merge in
// the output latch - and `res 0,(P7)` is a read-modify-write, so this has to
// hand back the driven bits too or the first bit instruction would clear them.
uint8_t wsa1_state::cpu1_p7_r()
{
	uint8_t data = (m_cpu1_p7 & 0x33) | 0xc0;   // bits 6-7: nothing wired, read high

	data |= BIT(m_cpu2_pa, 0) << 2;             // CPU 2's strobe
	data |= BIT(m_cpu2_pa, 1) << 3;             // CPU 2's receiver-busy

	return data;
}

void wsa1_state::cpu1_p7_w(uint8_t data)
{
	// Bits 4 and 5 are also outputs, and the power-fail NMI handler sets them as
	// its first act; what they drive is NOT ESTABLISHED, so they are stored and
	// ignored rather than given an invented destination.
	m_cpu1_p7 = data;
}

// PACR = 0x03 (0xFFF02C): bits 0 and 1 are outputs.  Port A's write path is
// already masked with PACR inside the CPU, so only those two bits arrive here.
// Port A is four bits wide on this part; 4-7 do not exist and read high.
//
// One boot transient a reader will spot: 0xFFF026 ldio PA,0xFF runs while PACR
// still holds the core's reset value, so this handler briefly sees 0x00 - both
// of CPU 2's outputs reading low - for the handful of instructions until
// 0xFFF02C.  Harmless, because no link traffic exists that early, but real.
uint8_t wsa1_state::cpu2_pa_r()
{
	uint8_t data = (m_cpu2_pa & 0x03) | 0xf0;

	data |= BIT(m_cpu1_p7, 0) << 2;             // CPU 1's strobe
	data |= BIT(m_cpu1_p7, 1) << 3;             // CPU 1's receiver-busy

	return data;
}

void wsa1_state::cpu2_pa_w(uint8_t data)
{
	m_cpu2_pa = data;
}


/***************************************************************************

    CPU 2's CS0 DEVICE CLUSTER - STUBS ONLY

***************************************************************************/

// ---- 0x10C000: the tone generator ---------------------------------------

void wsa1_state::tg_addr_w(uint16_t data)
{
	m_tg_latch = data;
}

void wsa1_state::tg_data_w(uint16_t data)
{
	// Register number = (plane << 6) | voice, 64 voices - the same field split
	// MAME's KN5000 tone generator uses.  The identification of this port as the
	// same part as the KN5000's IC303 rests on five agreements with that
	// device's firmware, not on the parts list alone: the 64-voice boot reset at
	// 0xFA6690 writes the same four planes with the same iteration count and two
	// byte-identical values (plane 0x0C0 <- 0x0000, plane 0x000 <- 0x7E00, the
	// KN5000's "voice free"); the damp pair 0xA200/0xA280 appears on the same
	// two planes (0xFAC275, 0xFAC298); the +4 read-back has the same shape as
	// the KN5000's AUDIO_HW_WRITE_READ; and two upper-plane bursts (0xFACE67,
	// 0xFACEA2) match the KN5000 note-on burst in BOTH register number and
	// parameter-block word offset.  It is still an identification by twin: a
	// register whose value was not compared could differ.
	if (m_tg_latch < TG_REG_COUNT)
		m_tg_regs[m_tg_latch] = data;

	LOGMASKED(LOG_TG, "tg: reg 0x%04X (plane 0x%03X voice %2d) = 0x%04X\n",
		m_tg_latch, m_tg_latch >> 6, m_tg_latch & 0x3f, data);
}

uint16_t wsa1_state::tg_status_r()
{
	// Two queries reach this port, and both are answered "nothing is sounding":
	//
	//   latch 0x0180 + voice  -> that voice's envelope level.  0xFA69AF latches
	//        it, 0xFA69B1 reads here, 0xFA69B6/0xFA69BA keep (V & 0x3FFF) >> 5.
	//        0 = silent.
	//   latch 0x0000..n       -> the active-voice bitmap of a bank of 16.
	//        0xFA6901 latches, 0xFA690A reads, 0xFA6920 ORs it into a shadow.
	//        0 = every voice free.
	//
	// Both answers are 0, so one branch would do; they are written out so that
	// the next person can see WHICH query is being answered and change one
	// without the other.  Answering 0 is a DECISION, not a fact: it is safe only
	// because nothing in prom_c waits for a voice to become busy.
	if ((m_tg_latch >= 0x0180) && (m_tg_latch < 0x0180 + 64))
	{
		LOGMASKED(LOG_TG, "tg: envelope level of voice %2d -> 0 (stub)\n", m_tg_latch - 0x0180);
		return 0;
	}

	LOGMASKED(LOG_TG, "tg: status read, latch 0x%04X -> 0 (stub)\n", m_tg_latch);
	return 0;
}

// ---- 0x104000: the second register file ----------------------------------

void wsa1_state::synth2_addr_w(uint16_t data)
{
	m_synth2_latch = data;
}

void wsa1_state::synth2_data_w(uint16_t data)
{
	if (m_synth2_latch < TG_REG_COUNT)
		m_synth2_regs[m_synth2_latch] = data;

	LOGMASKED(LOG_SYNTH2, "synth2: reg 0x%04X (plane 0x%03X slot %2d) = 0x%04X\n",
		m_synth2_latch, m_synth2_latch >> 6, m_synth2_latch & 0x3f, data);
}

uint16_t wsa1_state::synth2_data_r()
{
	// NOTHING in prom_c reads this device - all twelve literal-address sites are
	// stores.  A read here therefore means either a code path the analysis has
	// not reached or a decode error, so it is logged unconditionally.
	logerror("%s: UNEXPECTED read of 0x104002 (latch 0x%04X)\n",
		machine().describe_context(), m_synth2_latch);
	return 0;
}

// ---- 0x108000 / 0x108002: keybed data and status -------------------------

uint16_t wsa1_state::keybed_status_r()
{
	// 0xF99762 reads here; 0xF9976F tests bit 0 ("an event is waiting") and
	// 0xF9979A tests bit 1.  Returning 0 means "no key event", which is the
	// honest state for a rack SX-WSA1R with no keybed attached, and it is what
	// makes the reader at 0xF99740 return its 0xFFFF "queue empty" at once
	// instead of running its 1000-tick timeout.
	return 0;
}

uint16_t wsa1_state::keybed_data_r()
{
	// The word is (touch << 8) | (note_on << 7) | note - 0xF99780..0xF99792
	// splits it and the velocity decoder at 0xF995DF consumes it.  0 = note 0,
	// key up, which is inert.
	//
	// The reader at 0xF99776 only gets here after the status bit says an event
	// is waiting, so it never does; but the SECOND reader, the bounded drain at
	// 0xF998C6, reads the data port unconditionally.  Measured: exactly 16
	// reads, all from PC 0xF998CD, once per boot - which is the drain's 0x10
	// iteration count, so it is expected traffic and not a surprise.  Hence
	// LOGMASKED and not logerror.  (notes/wsa1-probes/, error.log census.)
	LOGMASKED(LOG_KEYBED, "%s: keybed data read with no event pending\n",
		machine().describe_context());
	return 0;
}

void wsa1_state::keybed_status_w(uint16_t data)
{
	// The boot preload at 0xF99125 writes 0x0080..0x00BF here, 64 of them, from
	// RESET (0xFFF081) and from the NMI handler (0xFFF0AE).  What they configure
	// is NOT ESTABLISHED.
	LOGMASKED(LOG_KEYBED, "keybed: +2 <- 0x%04X\n", data);
}

void wsa1_state::keybed_data_w(uint16_t data)
{
	LOGMASKED(LOG_KEYBED, "keybed: +0 <- 0x%04X\n", data);
}

// ---- 0xE00000: the 4 x 32 channel register file --------------------------

void wsa1_state::chanreg_addr_w(uint16_t data)
{
	m_chanreg_addr = data & 0xff;
}

void wsa1_state::chanreg_data_w(uint16_t data)
{
	m_chanreg[m_chanreg_addr] = data & 0xff;

	LOGMASKED(LOG_CHANREG, "chanreg: ch %d reg 0x%02X = 0x%02X\n",
		m_chanreg_addr >> 5, m_chanreg_addr & 0x1f, data & 0xff);
}

uint16_t wsa1_state::chanreg_data_r()
{
	return m_chanreg[m_chanreg_addr];
}


void wsa1_state::machine_start()
{
	save_item(NAME(m_link_to_cpu2));
	save_item(NAME(m_link_to_cpu1));
	save_item(NAME(m_link_to_cpu2_full));
	save_item(NAME(m_link_to_cpu1_full));
	save_item(NAME(m_cpu1_p7));
	save_item(NAME(m_cpu2_pa));
	save_item(NAME(m_tg_latch));
	save_item(NAME(m_tg_regs));
	save_item(NAME(m_synth2_latch));
	save_item(NAME(m_synth2_regs));
	save_item(NAME(m_chanreg_addr));
	save_item(NAME(m_chanreg));
}

void wsa1_state::machine_reset()
{
	// Both boot blocks write their port latch all-ones before enabling the
	// outputs (0xF826C4 ldio P7,0xFF and 0xFFF026 ldio PA,0xFF), so idle is high
	// on every handshake line.  Seeding the shadows the same way keeps the lines
	// idle for the handful of instructions before P7CR / PACR are written.
	m_cpu1_p7 = 0xff;
	m_cpu2_pa = 0x03;
	m_link_to_cpu2_full = false;
	m_link_to_cpu1_full = false;
}


void wsa1_state::lcdc_map(address_map &map)
{
	// 32 KiB of display RAM.  Established by the firmware, not assumed: the
	// power-on clear at 0xF8E92B writes 0x800 x 16 = 32768 bytes from cursor 0
	// (0xF8E92F ldw BC,0x0800), and the highest address any layer reaches is
	// SAD3 + 240 * AP = 0x4C00 + 0x2580 = 0x7180.  Whether the physical part is
	// larger is not established.
	map(0x0000, 0x7fff).ram();
}

void wsa1_state::palette_init(palette_device &palette)
{
	// Two pens, dark on light.  The panel's actual appearance - reflective or
	// backlit, and in what colour - is NOT ESTABLISHED: the service manual scan
	// available here gives the part number of the controller but says nothing
	// about the module, and no photograph of a powered SX-WSA1R was consulted.
	// A neutral monochrome pair is the honest placeholder.
	palette.set_pen_color(0, rgb_t(0xc8, 0xc8, 0xc8));
	palette.set_pen_color(1, rgb_t(0x20, 0x20, 0x20));
}


// Every range below is a range the firmware itself establishes, and the address
// that establishes it is quoted next to it.  Ranges the disassembly could not
// establish are left out rather than guessed: an unmapped range says "nobody
// knows", a mapped one would say "somebody checked".
//
// 0x000000-0x00007F is the TMP95C061 internal I/O area on both processors.  It
// is not listed here because the device supplies its own internal_mem() and
// that map is applied last, so it wins over anything a driver puts there
// (src/emu/addrmap.cpp, address_map::address_map).
//
// One mechanical caveat: these are 16-bit spaces, so a few of the entries below
// are a byte wider than the address the firmware actually touches, and the ones
// that are genuinely byte wide say so with a byte-sized handler or an explicit
// umask16.  The exact addresses are in the comment on each entry.

void wsa1_state::cpu1_map(address_map &map)
{
	// Static RAM on CS1 (MSAR1 = 0x00, 0xF82730).  The boot block clears
	// 0x1460 longwords upward from 0x000080 (0xF8278A), which is the only
	// thing in the firmware that puts a size on this chip - and it is a lower
	// bound, not the size, so only the cleared span is mapped.
	map(0x000080, 0x0051ff).ram();

	// Work DRAM on CS3 (MSAR3 = 0x60, 0xF82736; P6FC = 0x1F at 0xF826B2 turns
	// the CS3 pin into LCAS, which is what identifies CS3 as the DRAM area).
	// Two clear loops cover 0x600000-0x6033FF (0xF8279A) and 0x604000-0x60FFFF
	// (0xF827AF).  The 3 KiB between them is skipped on purpose and is live -
	// prom_b reads it at 0xF440A5 - so it is the same DRAM, preserved across a
	// warm restart, and the whole span is mapped as one.  The first stack
	// pointer this machine has lands inside it, at 0x60EB80 (0xF85606).
	map(0x600000, 0x60ffff).ram();

	// Not mapped, deliberately: a 256-byte-record array based at 0x617800
	// (0xF61F5B, and the inverse at 0xF5E2F4).  It is real work DRAM, but
	// nothing in the reached code fixes how many records there are, so there
	// is no honest end address for it.

	// The devices below are all referenced directly by prom_a, and all sit in
	// the CS0 area.  Which addresses that area covers is the one row of the
	// chip-select elimination that stays ambiguous - MSAR0 = 0x78 with
	// MAMR0 = 0x3F reads either as 0x600000-0x7FFFFF or as 0x780000-0x97FFFF,
	// and both readings survive - so no window is asserted; only the addresses
	// the code touches are mapped.  None of these parts is identified, so none
	// is modelled.

	// LCD controller, the SED1330FBA the parts list puts at IC7.  The port
	// pairing is read straight off the firmware and is the same asymmetric one
	// every other sed1330 consumer in MAME uses, so no swap is needed:
	//   0x790000  read  = status (busy in bit 6, polled at 0xF8ECF4)
	//             write = data   (CSRW parameters at 0xF8ED0D / 0xF8ED1E)
	//   0x790001  read  = data   (the byte after MREAD, 0xF8ED41)
	//             write = command (0xF8ECFB ld (0x790001),0x46)
	// cf. skeleton/textelcomp.cpp, nec/pc8401a.cpp, yamaha/ympsr2000.cpp.  CS0
	// is an 8-bit area - B0CS = 0x14 lacks the bit 3 that B2CS = 0x1B and
	// B3CS = 0x19 carry - so A0 really is this chip's register select, and a
	// byte handler at an odd address in a 16-bit space is what that means.
	//
	// The busy poll is harmless whatever else happens: sed1330_device's m_bf is
	// never set, so status_r() returns 0 and the `jr nz` is never taken.
	map(0x790000, 0x790000).rw(m_lcdc, FUNC(sed1330_device::status_r), FUNC(sed1330_device::data_w));
	map(0x790001, 0x790001).rw(m_lcdc, FUNC(sed1330_device::data_r),   FUNC(sed1330_device::command_w));

	// A byte port, ring buffered in both directions through the pointer at
	// (0x605A3E): 0xFE680F ld C,(0x7A0000) and 0xFE682B ld (0x7A0000),C.
	map(0x7a0000, 0x7a0001).noprw();

	// Control/status and data of an unidentified byte-wide device.  A census
	// of the 24-bit memory-operand form over prom_a and prom_b finds exactly
	// five accesses to 0x7B0000-0x7B000F, all in one 54-byte block
	// (0xFE54B6, 0xFE54BC, 0xFE54C5, 0xFE54DD, 0xFE54E6), and the only
	// consumer is the INT5 handler at 0xFE6866: it tests bit 7 and bit 6 of
	// 0x7B0004 and reads a byte from 0x7B0005 for each one that arrives.
	map(0x7b0004, 0x7b0005).noprw();

	// The data port of the link to the other processor.  Writing it hands one
	// byte to CPU 2 and raises that processor's INT0; reading it takes the byte
	// CPU 2 last sent and releases this processor's INT0.  Both the CPU (for the
	// header byte) and micro-DMA channel 3 (for the body) come through the same
	// read handler.  0xF8E12B ld XBC,0x007C0000 then ld (XBC),0xE2;
	// 0xF8E494 ld H,(XBC).  P7 bit 0 is the strobe (0xF8E122, 0xF8E14A) and
	// P7 bit 3 the busy input (0xF8E136); the body is pushed by micro-DMA
	// channel 2 (0xF8E166 ldio DMA2V,0x12).  Byte wide, low lane.
	map(0x7c0000, 0x7c0001).rw(FUNC(wsa1_state::cpu1_link_r),
	                           FUNC(wsa1_state::cpu1_link_w)).umask16(0x00ff);

	// A 16-bit port read as a FIFO.  The accessor at 0xFE4CE0 forms the
	// address as 0x7E0000 + ((n & 7) | 0x08) or | 0x10, but in the only traced
	// caller (0xFE50A0) both indices are zero for all 256 iterations, so
	// 0x7E0008 is the only address the code is known to reach and the rest of
	// the block is left unmapped.  CS0 access timing is changed for the
	// duration of that transfer (B0CS 0x14 -> 0x10 -> 0x14, 0xFE509B and
	// 0xFE50D5), which is also what proves this device is on CS0.
	map(0x7e0008, 0x7e0009).noprw();

	// Address register and data register of an unidentified device, eight
	// writes per slot: 0xF8319A ld XIX,0x007F0000, then
	// 0xF831A8 ld (XIX),W and 0xF831AA ld (XIX+0x02),A.  The other processor
	// drives something with a byte-identical shape at 0xE00000; whether that
	// is one dual-ported chip or two instances is not established.
	map(0x7f0000, 0x7f0003).noprw();

	// The two program EPROMs, on CS2 (MSAR2 = 0xE0, 0xF82733).  prom_a's
	// vector table is at 0xFFFF00, where a TMP95C061 fetches vectors from, and
	// prom_b's base is fixed by four independent checks, the shortest being
	// that the reset path ends in jp 0xF42D60 (0xF827C4) and prom_b file
	// 0x42D60 holds jp 0xF85606, which is the ld XSP that sets up the first
	// stack.
	map(0xf00000, 0xf7ffff).rom().region("prom_ab", 0x000000);   // IC13
	map(0xf80000, 0xffffff).rom().region("prom_ab", 0x080000);   // IC12
}

void wsa1_state::cpu2_map(address_map &map)
{
	// Work DRAM on CS3 (MSAR3 = 0x00 and MAMR3 = 0x03, 0xFFF04A and 0xFFF04D;
	// P6FC = 0x1F at 0xFFF01A makes the CS3 pin LCAS here too).  The boot
	// block clears 0x8000 words upward from 0x000080 (0xFFF085) and its stack
	// starts at 0x00FFF0 (0xFFF006); the main entry moves the stack down to
	// 0x00FA00 (0xF9816B) and a 0x10D8-byte RAM image is copied into 0x00E2DF
	// (0xF989EF).  All of that is inside the cleared span, which as on the
	// other processor is a lower bound on the chip rather than its size.
	map(0x000080, 0x01007f).ram();

	// The CS0 device cluster.  MSAR0 = 0x10 (0xFFF038) is the one place in
	// either image where the meaning of MSAR is proven rather than assumed:
	// 0x2F bytes further down the same routine, ld XIX,0x00100000 (0xFFF067)
	// loads the base of the cluster the chip select has just been aimed at.
	// Both surviving decoders agree on this processor's four windows.

	// Data port of the link to the other processor, the mirror image of
	// 0x7C0000 there: 0xF999F9 / 0xF99A6D ld XBC,0x00100000 then ld (XBC),A,
	// with PA bit 0 as the strobe (0xF99AE0, 0xF99AFF), PA bit 3 as busy
	// (0xF999D0, 0xF99A06) and the same micro-DMA channel 2 (0xF99A2A ldio
	// DMA2V,0x12).  Byte wide: every access in prom_c is `ld (XBC),A`,
	// `ld (XBC),H` or `ld (XBC),imm8`.  The low lane is an inference from CS2's
	// proven x16 width, not a measurement of CS0.
	map(0x100000, 0x100001).rw(FUNC(wsa1_state::cpu2_link_r),
	                           FUNC(wsa1_state::cpu2_link_w)).umask16(0x00ff);

	// A second 64-slot register file with the same address-register at +0 /
	// data-register at +2 shape, strided 0x40 per plane.  0xFB7802
	// ld XBC,0x00104000, then the fifteen-plane burst at 0xFB7807-0xFB791B,
	// whose first six planes and block-word offsets are identical to the KN5000
	// tone generator's note-on burst.  THE PART IS NOT IDENTIFIED: the only
	// synthesis LSI in the parts list not otherwise accounted for is IC3
	// L7A1429 "MODELING LSI", which is elimination and not evidence, so the
	// stub is named synth2 rather than modeling.
	map(0x104000, 0x104001).w(FUNC(wsa1_state::synth2_addr_w));
	map(0x104002, 0x104003).rw(FUNC(wsa1_state::synth2_data_r), FUNC(wsa1_state::synth2_data_w));

	// Keybed: +0 data, +2 status with bit 0 = "an event is waiting".  0xF99762
	// reads the status, 0xF99776 and 0xF998C6 read the data, and the consumer is
	// the velocity decoder at 0xF995DF.  The KN5000 has the identical interface
	// at 0x110000/0x110002, which MAME already models as kbd_data_r/kbd_status_r
	// in kn5000.cpp.  The boot preload at 0xF99125 writes 64 pairs here.  The
	// physical scanner part is NOT ESTABLISHED, and a rack SX-WSA1R has no
	// keyboard, so this is presumably live only on the SX-WSA1.
	map(0x108000, 0x108001).rw(FUNC(wsa1_state::keybed_data_r),   FUNC(wsa1_state::keybed_data_w));
	map(0x108002, 0x108003).rw(FUNC(wsa1_state::keybed_status_r), FUNC(wsa1_state::keybed_status_w));

	// THE TONE GENERATOR, TC183C230002 (IC4) - the same part number the KN5000
	// carries at IC303.  This processor's busiest device by far, 102 references:
	// +0 address (0xFAC12D), +2 data (0xFAC132, followed by five nops for bus
	// timing), +4 read back (0xFA6905 inc 4,XBC / 0xFA690A ld HL,(XBC)).
	map(0x10c000, 0x10c001).w(FUNC(wsa1_state::tg_addr_w));
	map(0x10c002, 0x10c003).w(FUNC(wsa1_state::tg_data_w));
	map(0x10c004, 0x10c005).r(FUNC(wsa1_state::tg_status_r));

	// Not mapped, deliberately:
	//  - 0xC00000 on CS1, where prom_c reads an expansion board header at +0x18
	//    and +0x31 (0xFB6B6E) and compares a signature against the string
	//    "WSA1 EXTBD" it carries twice.  Leaving it unmapped is the "no option
	//    board fitted" case, which is the only case this driver can honestly
	//    represent: neither the SY-EW1 nor the SY-ES1 is documented in the
	//    manual beyond its name.
	//  - 0xE80000-0xEFFFFF on CS2, the flash.  Its size is established - the
	//    sector-erase routine at 0xFC8646 takes 0xE80000 as the device base
	//    (0xFC864B), unlocks at base+0xAAAA / base+0x5554, and special-cases
	//    the first and last 64 KiB blocks, the last of which puts its highest
	//    sector base at base+0x7C000 (0xFC8701), so the device ends at
	//    0xEFFFFF - but the part is not dumped, and the
	//    fourth EPROM image is only strongly supported as its content, not
	//    proven.  Mapping it would put undumped bytes on the bus as if they
	//    were read from the machine.

	// A board-level register file on CS2 (MSAR2 = 0xE0, 0xFFF044), four channels
	// of 32 registers: 0xF98057 ld XBC,0x00E00000, then ld (XBC),A (address) and
	// ld (XBC+0x02),E (data).  Channel n owns registers n*0x20+0x10..+0x17 plus
	// n*0x20+0x1F.  Eighty of the eighty-one bytes of the writer at 0xF98099 are
	// identical to the KN5000 sub-CPU's routine at payload 0x1FD27; the one byte
	// that differs is this base address.  MAME models the KN5000 twin the same
	// way at 0x130000/0x130002 in kn5000.cpp, with the standing correction that
	// it is NOT the uPD6383GF host interface but a separate register file.  Same
	// driver shape as 0x7F0000 on the other CPU.
	map(0xe00000, 0xe00001).w(FUNC(wsa1_state::chanreg_addr_w));
	map(0xe00002, 0xe00003).rw(FUNC(wsa1_state::chanreg_data_r), FUNC(wsa1_state::chanreg_data_w));

	// This processor's program EPROM, also on CS2, with its own independent
	// vector table at 0xFFFF00 giving reset = 0xFFF000.  The device also holds
	// data: a "ZZZZ" headed bank at file 0x000000-0x0165BF, code from 0x018000
	// to 0x0621E4, and the boot block and vectors from 0x07F000.
	map(0xf80000, 0xffffff).rom().region("prom_c", 0);           // IC28
}


static INPUT_PORTS_START(wsa1r)
INPUT_PORTS_END


void wsa1_state::wsa1r(machine_config &config)
{
	// fc = 28 MHz on both processors.  It is derived from the firmware, not
	// from the book: prom_c[0xFFFFEF] = 0x1C = 28 is read at 0xF991A2 and
	// turned into the serial divisor BR0CR = (M >> 1) & 0x0F, a rule that
	// yields 31250 baud for any M as long as fc = 1,000,000 * M, so the byte
	// is fc in MHz.  fc is the frequency every divisor in this firmware is
	// expressed against, and it is what MAME's TLCS-900 devices take as their
	// clock argument, so it is what goes here.
	//
	// Written as a plain 28 MHz crystal rather than as a doubled 14 MHz one:
	// the parts list has a 28 MHz ceramic oscillator, no 14 MHz part appears
	// in it at all, and so the internal-clock-doubler reading has no crystal
	// to stand on.  That is evidence and not exclusion - a doubler sits
	// downstream of the crystal, where a parts list cannot see it, and the
	// sibling TMP94C241 in kn5000.cpp is configured as 2*10_MHz_XTAL for
	// exactly that reason.  If a doubler is ever shown here, this line becomes
	// 2 * 14_MHz_XTAL and fc, and every divisor above, stays as it is.
	//
	// The tags are neutral on purpose: "cpu1" is the processor that fetches
	// prom_a and prom_b, "cpu2" the one that fetches prom_c, and which of them
	// is IC1 "MICROCOMPUTER (MAIN)" and which is IC2 "MICROCOMPUTER (SUB)" is
	// not established.
	TMP95C061(config, m_cpu1, 28_MHz_XTAL);
	m_cpu1->set_addrmap(AS_PROGRAM, &wsa1_state::cpu1_map);
	m_cpu1->port7_read().set(FUNC(wsa1_state::cpu1_p7_r));
	m_cpu1->port7_write().set(FUNC(wsa1_state::cpu1_p7_w));

	TMP95C061(config, m_cpu2, 28_MHz_XTAL);
	m_cpu2->set_addrmap(AS_PROGRAM, &wsa1_state::cpu2_map);
	m_cpu2->porta_read().set(FUNC(wsa1_state::cpu2_pa_r));
	m_cpu2->porta_write().set(FUNC(wsa1_state::cpu2_pa_w));

	// The link handshake is a pair of spin loops with a 0x4E20 iteration limit
	// (0xF8E113, 0xF999D9), which is on the order of milliseconds of emulated
	// time.  The default quantum is long enough for one processor to run a whole
	// spin loop to timeout without the other ever updating the line it is
	// waiting on, so it has to be shortened.  50 us is comfortably below the
	// spin limit and well under the interval timer 2 puts between two outgoing
	// bytes.  This is a tuning knob, and it costs speed: see the LOG_LINKLOST
	// note in the block comment on the link handlers.
	config.set_maximum_quantum(attotime::from_usec(50));

	// --- the 320 x 240 dot LCD, on CPU 1's CS0 area -------------------------
	//
	// The geometry is not the brochure's; it is what the firmware's own SYSTEM
	// SET says, and it says it three times identically - at 0xF8E81E in the
	// power-on init and again in SWI7 services 0x0F (0xF8FA65) and 0x10
	// (0xF8FB88), all three writing 30 07 00 27 35 EF 28 00:
	//   FX = 8 pixels per byte, FY = 1, C/R = 40 bytes displayed per line
	//   (= 320 pixels), TC/R = 54, L/F = 240 lines, AP = 40 bytes per line.
	// Two unrelated pieces of code agree: the coordinate clamps at 0xF8EB6B and
	// 0xF8EB82 are 319 and 239, and the pixel plotter at 0xF8ECB5 forms
	// Y * AP + X / 8 and picks a bit with the MSB-first mask table at 0xF8EDAC.
	//
	// What the two runtime services differ in is the LAYER COUNT, not the
	// geometry: service 0x10 rebuilds the boot layout (SAD1/2/3 =
	// 0x0000/0x2600/0x4C00, OVLAY 0x1C, OV = 1, three layers) while service 0x0F
	// sets up two layers only (SAD1/SAD2 = 0x0000/0x4000, OVLAY 0x0C, OV = 0)
	// and clears exactly 0x6580 bytes, which is SAD2 + 240 * AP.  That is why
	// the overlay copy of sed1330_device gates layer 3 on OV.
	auto &palette = PALETTE(config, "palette", FUNC(wsa1_state::palette_init), 2);

	screen_device &screen = SCREEN(config, "screen").set_lcd();
	screen.set_refresh_hz(60);
	screen.set_screen_update(m_lcdc, FUNC(sed1330_device::screen_update));
	screen.set_size(320, 240);
	screen.set_visarea_full();
	screen.set_palette(palette);

	// Clock deliberately 0: the SED1330's own oscillator is a part this scan
	// does not resolve, and sed1330_device only uses clock() to re-derive the
	// frame rate from TC/R and L/F.  With 0 it leaves the screen's nominal 60 Hz
	// alone rather than deriving a refresh rate from a crystal nobody has read.
	// Fill it in if the part is ever identified; nothing else depends on it.
	SED1330(config, m_lcdc, 0);
	m_lcdc->set_screen("screen");
	m_lcdc->set_addrmap(0, &wsa1_state::lcdc_map);

	// DELIBERATELY NOT WIRED, and here is the one that will tempt you.  CPU 2's
	// uPD6383GF microcode upload polls the DSP's READY line on P9 bit 3
	// (0xF9A19F ld C,(0x19) / and C,0x08) and does it at eighteen sites.  MAME's
	// unbound port read returns 0, so every byte of the upload burns the poll's
	// full 0x1F40 iteration bound and sets the firmware's timeout flag at
	// (0x00F35C).  Measured: in a six second run, CPU 2's program counter is
	// concentrated in 0xF9A347-0xF9A399, inside exactly that loop, so this is
	// where its boot time goes (notes/wsa1-probes/wsa1_pc_sample.lua).
	//
	// One line would make the handshake complete instantly:
	//
	//     m_cpu2->port9_read().set_constant(0x08);
	//
	// IT IS NOT ENABLED, because it is a FAKE: no schematic net has been read
	// for that pin, and the poll is bounded, so nothing hangs without it - it is
	// only slow.  Turning a measured stall into a fabricated ready signal would
	// buy speed with a claim about the hardware that nobody has checked.  Enable
	// it only as a labelled experiment, never as the default.
	//
	// Still absent, so neither program gets past its own hardware checks: the
	// tone generator's actual synthesis, the three DSPs and their microcode
	// upload path, the serial EEPROM, the AM29F400T flash (whose data-poll and
	// erase-verify loops are unbounded and will spin if reached), the floppy
	// controller and the panel microcontroller.
}


/***************************************************************************

    SX-WSA1R, MAIN board

    IC1          TMP95C061AF    Toshiba TLCS-900/H, "MICROCOMPUTER (MAIN)"
    IC2          TMP95C061AF    Toshiba TLCS-900/H, "MICROCOMPUTER (SUB)"
    IC3          L7A1429        "MODELING LSI"
    IC4          TC183C230002   "TONE GENELATOR LSI" [sic].  Two uncertainties
                                here.  The parts list reads TC183C230002 and
                                the schematic reads TC1830230002, differing in
                                one character, a C against a 0, which is the
                                confusion this scan makes most often.  And the
                                IC4 designator is a line away from the part
                                label in an interleaved two-column render
                                rather than beside it.
    IC5, IC6,    D6383GF-3BA    NEC digital signal processor.  Only the IC30
    IC30                        designator is printed cleanly; the other two
                                schematic instances read as IC5 and IC6, and
                                the block diagram shows three DSP blocks, so
                                three is the count used here.
    IC7          SED1330FBA     LCD controller, for the 320 x 240 dot panel.
                                MAME has a device for this part already, in
                                src/devices/video/sed1330.h
    IC12         QSIGCWSA1AX    4 Mbit programmed EPROM, chip select PROMACS
    IC13         QSIGCWSA1BX    4 Mbit programmed EPROM, chip select PROMBCS
    (derived)    QSIGCWSA1DX    4 Mbit programmed EPROM, chip select PROMDCS.
                                The designator column is missing from both
                                places this part is printed.  The redistributed
                                set names the file after IC21 and the parts
                                list row order agrees with that, but nothing in
                                the scan available here confirms it, so no
                                designator is asserted.
    (derived)    AM29F400T      4 Mbit flash memory.  Same situation: the part
                                is printed on the MAIN (B) sheet and in the
                                parts list, the designator is not.  The parts
                                list row order puts it at IC22.
    IC14, IC15   M5256CFP70LL,  256 kbit static RAM and 4 Mbit dynamic RAM.
                 M5M44170AJ7S   The self-diagnostic calls the pair "RAM (IC14,
                                15)"; only the IC15 designator is legible on
                                the schematic, so IC14 is derived from that
                                sentence.  The parts list spells the dynamic
                                RAM M5M44170AN7S.
    IC23,        LC321664AJ80   1 Mbit dynamic RAM
    IC31, IC32,
    IC51, IC61
    IC27         D74HC139GS     decoder; it generates PROMCCS and PROMDCS
    IC28         QSIGCWSA1CX    4 Mbit programmed EPROM, chip select PROMCCS
    IC33, IC34   M5M44260AJ7S   4 Mbit dynamic RAM.  The parts list spells it
                                M5M44260AJN7S.
    IC43         QSIGH3C16DT8   16 Mbit wave mask ROM (schematic: ...DT3)
    IC44         QSIGH3C16EA0   16 Mbit wave mask ROM (schematic: ...EA9)
    IC45         QSIGH3C16EA2   16 Mbit wave mask ROM (parts list: QSIGH38C...)
    IC47         QSIGH3C16DT7   16 Mbit wave mask ROM
    IC48         QSIGH3C16DT9   16 Mbit wave mask ROM
    IC49         QSIGH3C16EA1   16 Mbit wave mask ROM
    IC52 - IC54, PCM1702U       D/A converter, four of them
    IC59
    IC55 - IC58  M5218AFP       operational amplifier
    IC71         LH5P832N-10    256 kbit RAM.  The schematic calls it pseudo
                                static, the parts list just static.
    (unknown)    D72070GF3BE    NEC floppy disk controller, for the 3.5 inch
                                2HD 1.44 MB / 2DD 720 KB drive.  Its row in
                                the parts list falls outside the run of rows
                                whose designators can be recovered, and the
                                schematic label is not adjacent to a legible
                                designator either.

    SX-WSA1R, CONTROL PANEL 1 board

    (unknown)    M37471M2196S   Mitsubishi control panel microcontroller, the
                                same part as the two MCUs emulated in
                                kn5000_cpanel.cpp.  This board's parts list has
                                no designator column at all.  The internal mask
                                ROM is not dumped and no region is declared for
                                it here, because the manual does not give its
                                capacity and guessing one would be worse than
                                leaving it out.
    (unknown)    HD74LS07P      hex buffer

    Capacities above are the manual's own, which writes memory sizes in
    megabits: the wave devices are each "IC, MASK ROM 16M BIT", the four
    program EPROMs "IC, 4M EPROM" / "4M BIT PROGRAMMED EP ROM", and the flash
    "IC, FLASH MEMORY 4M BIT".  The manual never says what any of the four
    EPROMs holds; the roles given in the ROM definitions below were read out of
    the images, not out of the book.

    Only devices whose part number is legible are listed.  Discrete logic,
    photocouplers and the power supply are omitted, as are the SY-EW1 and
    SY-ES1 option boards, which the schematics name but do not document.

***************************************************************************/

ROM_START(wsa1r)
	// The regions below are named after the chip-select nets in the service
	// manual rather than after processors.  There are certainly two CPUs, but
	// which of IC1 ("MAIN") and IC2 ("SUB") fetches which pair of EPROMs is
	// not established: both processors are drawn on the MAIN (A) sheet, next
	// to the A and B EPROMs, while C and D are on the MAIN (B) sheet off the
	// IC27 decoder.

	// A and B share one address space and call into each other constantly.
	// B sits at 0xF00000: its first 20 bytes are a five entry jump table (four
	// times "jp 0xf00014", once "jp 0xf00015") whose targets are the bytes
	// immediately after the table itself, and A's interrupt vectors point at
	// real code inside it.  A sits at 0xF80000: that places its vector table
	// at 0xFFFF00, which is where a TMP95C061 fetches vectors from, and the
	// reset entry there (0xF826A9) is the startup code described at the top of
	// this file.  B holds most of the user interface text, in English, German
	// and French, plus the service test screens.
	ROM_REGION16_LE(0x100000, "prom_ab", 0)
	ROM_LOAD("qsigcwsa1bx.ic13", 0x000000, 0x080000, CRC(f3f84441) SHA1(93adec2a04b7d93a2ec2bfb059227ff3959906e0)) // B, at 0xf00000
	ROM_LOAD("qsigcwsa1ax.ic12", 0x080000, 0x080000, CRC(5f34af46) SHA1(90a2369f8e4d2fcdf26875272267624b07bc200d)) // A, at 0xf80000

	// C is the program of the other processor, at 0xF80000 in its own address
	// space: it has a second, independent vector table at 0xFFFF00 giving
	// reset 0xFFF000, and the startup code there writes a different set of
	// memory-controller values than A's, so the two are not halves of one
	// image.  The device also holds a data bank: 0x000000-0x0165BF is a "ZZZZ"
	// headed block naming the model, with a 16 entry category table and 128
	// combinations of 704 bytes each.  Code runs from 0x018000 to 0x0621E4,
	// and the boot code and vectors sit from 0x07F000.
	ROM_REGION16_LE(0x080000, "prom_c", 0)
	ROM_LOAD("qsigcwsa1cx.ic28", 0x000000, 0x080000, CRC(855c8ac4) SHA1(9b2911e4b21a08d9744b91844630489f54dde856)) // at 0xf80000

	// D holds no executable content at all: no vector table, and essentially
	// no branch structure.  It is a tone bank, addressed through a table of
	// 32-bit image-relative offsets at 0x000000 and a 274 entry pointer
	// directory at 0x000B80 (256 sounds followed by 18 drum kit records, where
	// the specification page advertises 16 preset kits), with a 16 byte
	// printable name at the head of every record.  The payload ends at
	// 0x050B08 and the rest of the device is erased.  The address the device
	// is mapped at was not determined, which is why it is a region of its own
	// rather than the other half of "prom_c".
	//
	// The file is named after the part number alone because this device's
	// reference designator is not legible anywhere in the manual scan
	// available here.  See the parts list above.
	ROM_REGION16_LE(0x080000, "prom_d", 0)
	ROM_LOAD("qsigcwsa1dx.bin", 0x000000, 0x080000, CRC(735ae465) SHA1(82df50816c20cd8f2d29551326d2633e7791f306))

	// The wave ROMs are not held here.  The self-diagnostic's wave ROM test
	// covers IC43 to IC45 and IC47 to IC49, and maps them to six buttons; there
	// is no IC46 in either the parts list or the self-diagnostic.  The OCR of
	// the button map loses the circled digits, so which button drives which
	// device is not reproduced here.  The manual gives the capacity of these
	// devices as 16 Mbit but not their organisation, and the scan does not
	// resolve which one sits on which of the tone generator's address buses, so
	// each gets a region of its own rather than being concatenated into a bank.
	ROM_REGION(0x200000, "waveform_ic43", 0)
	ROM_LOAD("qsigh3c16dt8.ic43", 0x000000, 0x200000, NO_DUMP)

	ROM_REGION(0x200000, "waveform_ic44", 0)
	ROM_LOAD("qsigh3c16ea0.ic44", 0x000000, 0x200000, NO_DUMP)

	ROM_REGION(0x200000, "waveform_ic45", 0)
	ROM_LOAD("qsigh3c16ea2.ic45", 0x000000, 0x200000, NO_DUMP)

	ROM_REGION(0x200000, "waveform_ic47", 0)
	ROM_LOAD("qsigh3c16dt7.ic47", 0x000000, 0x200000, NO_DUMP)

	ROM_REGION(0x200000, "waveform_ic48", 0)
	ROM_LOAD("qsigh3c16dt9.ic48", 0x000000, 0x200000, NO_DUMP)

	ROM_REGION(0x200000, "waveform_ic49", 0)
	ROM_LOAD("qsigh3c16ea1.ic49", 0x000000, 0x200000, NO_DUMP)

	// A 4 Mbit flash device that the block diagram puts on the same address
	// group as the program EPROMs.  Not held here, and the manual does not say
	// what it holds.  Named after the part number because its designator is
	// not legible either.
	ROM_REGION(0x080000, "flash", 0)
	ROM_LOAD("am29f400t.bin", 0x000000, 0x080000, NO_DUMP)
ROM_END

} // anonymous namespace


//   YEAR  NAME   PARENT  COMPAT  MACHINE  INPUT  CLASS       INIT        COMPANY     FULLNAME    FLAGS
SYST(1995, wsa1r, 0,      0,      wsa1r,   wsa1r, wsa1_state, empty_init, "Technics", "SX-WSA1R", MACHINE_NOT_WORKING|MACHINE_NO_SOUND)

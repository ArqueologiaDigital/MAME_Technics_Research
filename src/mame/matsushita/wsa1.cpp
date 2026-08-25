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
    its screen, the link between the two processors, the 61-key keybed scanner
    and the calibration EEPROM on the second processor, and a set of largely
    write-only register-file stubs for the rest of that processor's chip-select
    zero cluster.  Several of those rest on inferences that a MAME reviewer
    would rightly refuse until a schematic or a real machine confirms them,
    and each such inference is marked where it is made.  Do not treat this
    file as the submission candidate, and do not "sync" one from the other
    mechanically -- move a piece across only once its evidence is complete.

    A 1995 rack-mounted "Acoustic Modeling Synthesis" synthesizer module:
    64 notes over up to 32 parts, 256 preset sounds, 16 preset drum kits and
    128 preset combinations, a 320 x 240 dot LCD, two sets of MIDI IN/OUT/THRU
    and a built-in 3.5 inch floppy drive.

    (*) fc/8 for phiT1 is the firmware's own arithmetic.  MAME's tmp95c061
    prescaler is a uniform factor of 16 slower than that, which costs boot time
    but nothing else; the measurement and the reasoning are in the machine
    configuration, next to the LCD.

    HOW FAR IT BOOTS, as measured on 2026-08-25 with the probes in
    notes/wsa1-probes/ (each one names the question it answers):

      t=0.00 s  RESET at 0xF826A9; watchdog off, ports, timers, chip selects,
                RAM cleared, then into prom_b through the thunk table.
      t=0.00 s  the 488 Hz timer tick at RAM 0x0080 starts counting (it counts
                at 30 Hz here - see the prescaler note in the machine config).
      t=0.00 s  the boot sequence at 0xF827C8 CAN blink an 8-bit RAM/ROM verdict
                on P5 bit 3, and used to do it on every boot because P5 bit 4
                read back 0 and that burned 3.13 s.  P5 bit 4 is now known to be
                the service CHECKING DEVICE's switch (see cpu1_p5_r()); with
                nothing on CN4 -- the default -- the routine returns at once.
      t=0.013 s the battery-RAM checksum pair at 0xF82C80 runs: 0x100 words
                summed from 0x007620 and complemented against (0x007FD2), then
                the same from 0x617800 against (0x007FD4).  The helper at
                0xF82CD3 returns carry CLEAR on a match (0xF82CE6 rcf) and the
                callers only `set` their verdict bit on that path (0xF82C97,
                0xF82CA8), so in (0x007FD1) a SET bit means PASS.  Measured:
                0x00 - both FAIL (wsa1_checksum_result.lua).  That is the right
                answer for a machine with no battery-backed contents, and
                0xF82CAB then takes its bit-0-clear arm at 0xF82CBD, which
                forces the boot-mode byte (0x0097) |= 0x01.
      t=5.01 s  the SC1 module opens the control panel link and the panel
                answers - see the paragraph below.
      t=7.21 s  the SED1330 is initialised, from 0xF8E822 in LCD_Init_SED1330.
                (It was 10.39 s before the CHECKING DEVICE switch was modelled;
                the difference is the 3.13 s blink that no longer runs.  Both
                figures are from wsa1_boot_milestones.lua on the build of the
                day; the SWI7 access counts quoted in earlier revisions of this
                comment were measured with the blink and are NOT re-measured
                here, so they are dropped rather than restated.)
      t=70.5 s  CPU 2 reaches MAIN and its key scanner goes live.  Both of the
                firmware's own gates are open by then and both were measured
                (notes/wsa1-probes/wsa1_cpu2_tick_and_keyscan.lua): the one-shot
                latch at (0x00F329) is set once the INTT1 tick counter at
                (0x00F2F3) passes 1000, and from then on the status port at
                0x108002 is polled about 34,500 times a second of emulated time.
                So a key pressed after this point is seen.
      t=75 s    the panel reads ALL INITIAL SETTING! and stops changing, while
                CPU 1 keeps running ordinary code across prom_a and prom_b -
                a live system sitting on the message, not a hang.  Snapshots
                every 15 s: blank at t=60, the message from t=75 through t=195,
                unchanged (wsa1_panel_link.lua, -str 200).  The message
                is consistent with the failed checksums above; the path from
                (0x0097) to those particular glyphs has NOT been traced, so
                read that as agreement, not as a proven causal chain.

    THE CONTROL PANEL IS NOW WIRED, and the link works in both directions.
    Measured on the same build (notes/wsa1-probes/wsa1_sc1_handshake.lua): CPU 1
    clocks out exactly the seven command frames the disassembly says the SC1
    module sends first, in ROM order --

        (DF,D2) (DF,1A) (DD,03) (DE,80) (E3,00) (E2,08) (E3,10)

    -- the panel answers each one, INT6 is dispatched (the SC1 state machine
    enters state 0x20 seven times), INTRX1 hands both reply bytes back, and
    later the firmware's LED want-buffer at RAM 0x20D0 stops being all-zero and
    its sent-shadow at 0x20F0 follows it, while the SC1BUF write count steps from
    49 to 63 in the same five-second window - two LED registers changed, so two
    frames, and the shadows alone would only have proved they were QUEUED.
    Two things had to be right for any of that: P8 bit 5 has to read HIGH (see
    cpu1_p8_r()), and a byte must only reach the panel when SCLK1's pin function
    is selected (see the gate in the overlay tmp95c061.cpp's sc1buf_w -- nine of
    the firmware's eleven SC1BUF writes are dummies that carry a register shadow,
    not payload).

    So the machine boots to correct, legible screen content, has a front panel,
    and CPU 2 takes a key.  How far the key gets is measured and stated exactly, because the two
    halves of that sentence are not the same claim:

      * the SCANNER works.  Press C4 after t=71 s and prom_c reads 0x5C98 off
        0x108000 and 0x5C18 on release -- touch 0x5C, key 24, bit 7 for down --
        which is byte for byte what keybed_push() queued
        (notes/wsa1-probes/wsa1_keybed_note.lua).
      * the LINK does not carry it.  CPU 2 -> CPU 1 sends exactly one packet per
        boot and then wedges on a handshake line CPU 1 never releases, so
        KeyEvents_ToLink's channel-5 packet is dropped.  The measurement and
        where to look are in the block comment on the link handlers.

    So no note reaches the tone generator, and nothing makes a sound in any case:
    nothing synthesises, the wave ROMs are undumped, and the sequencer clock
    cannot tick (see the machine config).  The three DSPs and the flash are still
    absent; the panel microcontroller is HLE'd on serial channel 1 and the FLOPPY
    CONTROLLER IS NOW A REAL DEVICE, uPD765-family, with a 3.5 inch drive on it
    (see the block comment above fdc_ctrl_w).  Unlike the MN10300-based Technics keyboards in
    kn5000.cpp and kn7000.cpp, the CPU core is not what is missing here: the
    two processors are
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
    which is 5 * fc for timer 4 running at fc/8 with 96 ticks per beat (*), and
    the MIDI init at 0xFA58F8 sets BR0CR = 0x0E, that is fc/896 = 31250 baud.  The
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
        puts at IC7.  0x7A0000 AND 0x7B0004/5 ARE NOW IDENTIFIED TOO: they are
        the data register, main status register and data-rate register of a
        uPD765-family FLOPPY DISK CONTROLLER, and both are wired to one.  Still
        unidentified: 0x7E0008 and 0x7F0000 on the first processor, and the
        register file at 0x104000 on the second.  0x7F0000 IS NOW MODELLED as
        the 4 x 32 register file its driver shape says it is, without a part
        name; 0x7E0008 is known to be the SECOND UNIT of the same block-device
        layer that drives the floppy, which is a role and not a part, so it
        stays inert
      - work out which processor is IC1 "MAIN" and which is IC2 "SUB".  The link
        between them IS NOW WIRED UP (byte port plus strobe/busy handshake plus
        micro-DMA channels 2 and 3, at 0x7C0000 on one side and 0x100000 on the
        other), but the cross-wiring of the four handshake pins is derived from
        the firmware and not from a schematic -- see the block comment on the
        handlers
      - fix the base address of the fourth EPROM image, which is strongly
        supported as the content of the 512 KiB flash at 0xE80000 on the second
        processor but not proven
      - dump the six 16 Mbit wave mask ROMs, the AM29F400T flash, the serial
        EEPROM that holds the per-key touch calibration, and the internal ROM of
        the control panel microcontroller
      - devices with no MAME implementation yet: the L7A1429 modeling LSI and
        the uPD6383GF-3BA DSP.  (The M37471M2196S panel MCU is HLE'd in
        wsa1_cpanel.cpp.  The uPD72070 floppy controller has no MAME device of
        its own either, but the family does -- the driver instantiates
        upd765a_device and says at the code why that is the right member of it.)

***************************************************************************/

#include "emu.h"

#include "cpu/tlcs900/tmp95c061.h"
#include "wsa1_cpanel.h"

#include "imagedev/floppy.h"
#include "machine/eepromser.h"
#include "machine/upd765.h"
#include "video/sed1330.h"

#include "emupal.h"
#include "screen.h"

#define LOG_LINK     (1U << 1)   // every byte and handshake edge on the CPU link
#define LOG_LINKLOST (1U << 2)   // a link latch overwritten before it was read
#define LOG_TG       (1U << 3)   // tone generator, 0x10C000
#define LOG_SYNTH2   (1U << 4)   // the second register file, 0x104000
#define LOG_KEYBED   (1U << 5)   // keybed data/status, 0x108000
#define LOG_CHANREG  (1U << 6)   // the 4 x 32 channel register files, 0x7F0000 / 0xE00000
#define LOG_KEYS     (1U << 7)   // key presses queued for the scanner at 0x108000
#define LOG_EEPROM   (1U << 8)   // the serial EEPROM's CS / SK / DI / DO lines
#define LOG_FDC      (1U << 9)   // floppy: the control register, TC and CPU 1's PA bit 3

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
		, m_eeprom(*this, "eeprom")
		, m_cpanel(*this, "cpanel")
		, m_fdc(*this, "fdc")
		, m_keybed(*this, "KEY%u", 0U)
		, m_touch(*this, "TOUCH")
		, m_checkdev(*this, "CHECKDEV")
		, m_check_led(*this, "check_led")
	{ }

	void wsa1_base(machine_config &config) ATTR_COLD;
	void wsa1r(machine_config &config) ATTR_COLD;
	void wsa1(machine_config &config) ATTR_COLD;

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

	// CPU 1's port 8 and port B carry the control panel's serial link, and PB
	// bit 0 carries the MODEL STRAP.  See the block comment above the bodies.
	uint8_t cpu1_p8_r();
	void cpu1_p8_w(uint8_t data);
	uint8_t cpu1_pb_r();
	void cpu1_pb_w(uint8_t data);
	void cpu1_pa_w(uint8_t data);

	// The floppy controller's write-side register at 0x7B0004.  See the block
	// comment above the body.
	void fdc_ctrl_w(uint8_t data);

public:
	// The only thing that differs between the two declared systems, besides
	// which inputs exist.  PB bit 0 is an input strap on the MAIN board
	// (PBCR = 0x0C at 0xF826E5 makes only bits 2 and 3 outputs); the boot block
	// samples it once at 0xF82884 and stores 1 or 2 in RAM (0xC4), and 111 sites
	// across 27 blocks of prom_a branch on that byte.
	void init_wsa1r() { m_model = 2; }      // PB.0 low
	void init_wsa1()  { m_model = 1; }      // PB.0 high

private:

	// CPU 1's port 5 carries the service CHECKING DEVICE's switch and its LED.
	uint8_t cpu1_p5_r();
	void cpu1_p5_w(uint8_t data);

	// 1 = SX-WSA1 (keyboard), 2 = SX-WSA1R (rack).  Fixed per DRIVER, not chosen
	// at runtime: the two are declared as separate systems below, because that is
	// what they are - two products, one ROM set - and a MAME user picks a machine
	// by name rather than by flipping a config bit inside one.
	//
	// The value is what PB bit 0 makes the firmware store in RAM (0xC4), and it
	// is pushed to the panel device at reset so the firmware's own copy and the
	// panel model can never disagree.
	uint8_t variant() const { return m_model; }

	// CPU 2's port 6 and port 8 carry the serial EEPROM.  See the block comment
	// above the handler bodies.
	void cpu2_p6_w(uint8_t data);
	uint8_t cpu2_p8_r();
	void cpu2_p8_w(uint8_t data);

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
	//
	// A per-channel register number is `parameter_block * 0x40 + channel`, with
	// 64 channels -- 64 from a literal loop counter (`ldb d,0x40` at 0xFB810E in
	// Dev10C_ResetAllChannels), not from an address stride.  The highest
	// per-channel block the firmware is known to use is 0x0A40, from the
	// twenty-two-register unrolled writer Dev10C_WriteAllChanRegs (0xFB713A), so
	// the per-channel ceiling is 0x0A7F.  The GLOBAL registers sit above it and
	// are NOT of that form: Dev10C_WriteGlobalRegs (0xFB7715) takes no channel
	// argument and writes 0x0200-0x0205, 0x0C00-0x0C05 and 0x0E00 as immediates.
	// 0x1000 covers all of it.
	// (wsa1-roms-disasm/notes/FINDINGS-prom_c-tone-generator.md sec.2, 3 and 7.)
	static constexpr unsigned TG_REG_COUNT   = 0x1000;
	static constexpr unsigned TG_CHAN_REG_TOP = 0x0a7f;   // 0x0A40 + 0x3F

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

	// 0x108000 -- the 61-key keybed scanner: event (+0) and status (+2).
	uint16_t keybed_data_r();
	uint16_t keybed_status_r();
	void     keybed_data_w(uint16_t data);
	void     keybed_status_w(uint16_t data);

	TIMER_CALLBACK_MEMBER(keybed_scan);
	void     keybed_push(uint8_t key, bool pressed);

	// 0x7F0000 on CPU 1 and 0xE00000 on CPU 2 -- two 4-channel x 32-register
	// files with a byte-identical driver shape.
	void     cpu1_chanreg_addr_w(uint16_t data);
	void     cpu1_chanreg_data_w(uint16_t data);
	uint16_t cpu1_chanreg_data_r();
	void     cpu2_chanreg_addr_w(uint16_t data);
	void     cpu2_chanreg_data_w(uint16_t data);
	uint16_t cpu2_chanreg_data_r();

	required_device<tmp95c061_device> m_cpu1;
	required_device<tmp95c061_device> m_cpu2;
	required_device<sed1330_device> m_lcdc;
	required_device<eeprom_serial_93c46_16bit_device> m_eeprom;
	required_device<wsa1_cpanel_device> m_cpanel;
	required_device<upd765a_device> m_fdc;
	// OPTIONAL, not required: these ports exist only on the SX-WSA1 driver.  A
	// rack has no keybed, so declaring them required makes -validate fail on
	// wsa1r with "Required I/O port ':KEY0' not found" - which is validation
	// doing its job, and the reason the split is expressed here as well as in
	// the port lists.
	optional_ioport_array<6> m_keybed;    // 61 keys, 6 ports x 12 bits (the last holds 1)
	optional_ioport m_touch;
	required_ioport m_checkdev;
	output_finder<> m_check_led;

	uint8_t  m_link_to_cpu2 = 0;            // the byte CPU 1 last wrote to 0x7C0000
	uint8_t  m_link_to_cpu1 = 0;            // the byte CPU 2 last wrote to 0x100000
	bool     m_link_to_cpu2_full = false;   // instrumentation only, see LOG_LINKLOST
	bool     m_link_to_cpu1_full = false;
	uint8_t  m_cpu1_p7 = 0xff;              // CPU 1's P7 output latch
	uint8_t  m_cpu2_pa = 0x03;              // CPU 2's PA output latch

	uint8_t  m_cpu2_p6 = 0;                 // CPU 2's P6 output latch (bit 5 = EEPROM CS)
	uint8_t  m_cpu2_p8 = 0;                 // CPU 2's P8 output latch (bits 3, 4 = SK, DI)

	uint8_t  m_cpu1_p5 = 0xff;              // CPU 1's P5 output latch
	uint8_t  m_cpu1_p8 = 0xff;              // CPU 1's P8 output latch
	uint8_t  m_cpu1_pa = 0xf9;              // CPU 1's PA output latch (RESET: ldio PA,0xF9)
	uint8_t  m_cpu1_pb = 0xf3;              // CPU 1's PB output latch (RESET: ldio PB,0xF3)
	uint8_t  m_panel_sclk = 1;              // P8 bit 5, the serial clock line: idle HIGH
	uint8_t  m_panel_busy = 0;              // PB bit 4, the panel's busy line: idle LOW
	uint8_t  m_model = 2;                   // set by init_wsa1() / init_wsa1r(), see variant()
	uint8_t  m_strap = 2;                   // latched copy of variant(), sampled at reset

	uint16_t m_tg_latch = 0;
	uint16_t m_tg_regs[TG_REG_COUNT]{};
	uint16_t m_synth2_latch = 0;
	uint16_t m_synth2_regs[TG_REG_COUNT]{};
	uint8_t  m_cpu1_chanreg_addr = 0;
	uint8_t  m_cpu1_chanreg[0x100]{};
	uint8_t  m_cpu2_chanreg_addr = 0;
	uint8_t  m_cpu2_chanreg[0x100]{};

	// The keybed model.  KEY_EVENTS is this driver's queue depth, not the
	// hardware's: nothing establishes how deep the real scanner's queue is.
	static constexpr unsigned KEY_COUNT  = 61;
	static constexpr unsigned KEY_EVENTS = 32;

	emu_timer *m_keybed_timer = nullptr;
	uint64_t m_keybed_prev = 0;             // one bit per key, 1 = held
	uint16_t m_key_fifo[KEY_EVENTS]{};
	uint8_t  m_key_fifo_read = 0;
	uint8_t  m_key_fifo_count = 0;
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

    ** MEASURED 2026-08-25, AND IT IS A REAL LIMITATION: THE CPU 2 -> CPU 1
    DIRECTION SENDS EXACTLY ONE PACKET AND THEN WEDGES.  CPU 1 -> CPU 2 carries
    56 bytes over a boot and is fine.  CPU 2 -> CPU 1 writes two bytes -- one
    header plus one payload -- at about t=72 s, and after that CPU 1 leaves P7
    bit 1 LOW for good (it writes P7 = 0xE7 up to t=70 and P7 = 0xC5 from t=72),
    so `Link_SendChunk`'s opening wait for PA bit 3 (0xF999D0) never passes and
    every later packet burns its 0x4E20 spins and is dropped.  The visible
    consequence is that a key press IS decoded by prom_c and its
    { 0x90, note, velocity } packet never reaches CPU 1.
    notes/wsa1-probes/wsa1_link_handshake.lua is the measurement.
    NOT DIAGNOSED FURTHER HERE.  It is on CPU 1's side -- INT0_LinkByte
    (0xF8E47F) arms micro-DMA channel 3 and drops the busy line, and either
    INTTC3_LinkDmaDone (0xF8E54F) never runs or it does not raise the line -- and
    that path is not converted in the disassembly tree yet.  It is not caused by
    the keybed model and not by the P6 fix below: every port write the probe sees
    on CPU 1 is to P7 (0x13), never to P6 (0x12).

    WHAT THIS MODEL DOES NOT GUARANTEE.  The latch is one byte deep, and real
    hardware has no per-byte handshake during a burst: the strobe is released
    BEFORE the body and the receiver's DMA is expected to keep up.  The model
    relies on set_input_line() enqueuing on a zero-delay timer, which aborts
    the sending processor's timeslice, plus the shortened scheduling quantum in
    wsa1r().  That is a scheduling argument, not a proof, which is why
    LOG_LINKLOST is compiled in by default.  If it ever fires, the remedy used
    on the KN5000 was a perfect_quantum() inside each write handler; see
    notes/upstream-patches/kn5000-26-intercpu-latch-int0-handshake.patch.

    NO CPU-CORE CHANGE IS PROPOSED FOR THE LINK, deliberately.  The KN5000
    needed tmp94c241_device::clear_int0_level() because that device re-asserts a
    level-detect INT0 flag from tlcs900_check_irqs(); tmp95c061 has no such
    code, so the deferred CLEAR_LINE is benign here.  If that re-assertion
    block is ever ported into tmp95c061, THIS DRIVER BREAKS and will need the
    same treatment.

    (One unrelated core change IS made, in the overlay copy of tmp95c061.cpp: a
    one-line fix so that a write to P6 reaches the PORT_6 write callback rather
    than PORT_7's.  It matters here twice over - for the EEPROM's chip select on
    CPU 2, and because CPU 1's `ldio P6,0x1B` at 0xF826AF was landing on
    cpu1_p7_w() and overwriting the handshake shadow above.  See the comment at
    the fixed line.)

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

    THE CONTROL PANEL LINK, AND THE MODEL STRAP -- CPU 1's PORT 8 AND PORT B

    The panel microcontroller itself is HLE'd in wsa1_cpanel.cpp; that file's
    header carries the byte evidence that serial channel 1 is the panel at all.
    What lives here is only the four port bits the link needs.

    ⚠ WITHOUT cpu1_p8_r() THE EMULATED MACHINE CANNOT TRANSMIT ON SC1 AT ALL,
    and that is a measured statement about MAME rather than about the hardware:
    SC1_WaitTxDrain (prom_b 0xF5AB7B) will not touch the link unless P8 bit 5
    reads HIGH and PB bit 4 reads LOW, and an unbound MAME port read returns 0,
    so P8 bit 5 read low, the four-way test never passed, its 200 retries burned
    out and no command and no LED frame ever left CPU 1.

    P8: P8CR = 0x09 and P8FC = 0x29 at RESET (0xF826D3, 0xF826D0), so bits 0 and
    3 are outputs -- the two transmit-data lines -- and bit 5 is on its function.
    The SC1 module then drives P8CR/P8FC bits 3 and 5 itself, and bit 5 is read
    back at TWO points that between them fix what it means:

      0xF5AB7B  SC1_WaitTxDrain will not start a transfer unless bit 5 reads
                HIGH and PB bit 4 reads LOW.
      0xF5AD09  SC1_State04_TxByte1, having just made bit 5 an INPUT
                (`and (0x2A86),0xDF` then `ld (0x1A),A`), tests it: HIGH carries
                on to the next state, LOW takes 0xF5AD0E, which ABORTS -- state
                and byte count zeroed, INTES1 = 0xFF, (0x2A84) |= 2.

    So the pin is released by both ends and sampled, and high means "nobody is
    holding the clock down".  ⚠ THAT THE IDLE STATE IS HIGH IS AN INFERENCE: no
    databook here names the pin and no schematic net has been read.  What is NOT
    an inference is that 0 is not a neutral default -- MAME's unbound read gave 0,
    and with 0 every single frame took the abort path at 0xF5AD0E.  Measured,
    before and after: notes/wsa1-probes/wsa1_sc1_handshake.lua.

    PB: PBCR = 0x0C (0xF826E5), so only bits 2 and 3 are outputs and every other
    bit is an input.  Two of the inputs are known:

      bit 0  THE MODEL STRAP.  prom_a 0xF82882 -- `ld A,1 / bit 0,(PB) / jr NZ /
             ld A,2 / ld (0xC4),A` -- is called once from RESET at 0xF827D8 and
             is the ONLY write to RAM (0xC4) in 512 KiB; 111 well-formed
             `cp (0xC4),#imm` sites across 27 distinct 4 KiB blocks read it back.
             HIGH gives (0xC4)=1, LOW gives (0xC4)=2.
      bit 4  the panel MCU's busy line, tested together with P8 bit 5 above.

    The other PB inputs read high, which is a driver choice for pins nobody has
    read: bit 1 is INT5, the floppy controller's result-phase interrupt, and
    that interrupt is asserted through set_input_line() rather than through this
    port, so the level here does not matter to it.

    PB also has an OUTPUT that matters now: bit 3, pulsed by PortB3_Pulse
    (prom_a 0xFE594C) at every micro-DMA channel-0 end of count and taken here
    as the floppy controller's TC.  Its write handler is cpu1_pb_w(), next to
    the floppy block comment; the read handler above hands the latch back
    because that pulse is a read-modify-write.

***************************************************************************/

uint8_t wsa1_state::cpu1_p8_r()
{
	// P8 is six bits wide on this part.  Bits 1, 2 and 4 are the receive-data and
	// handshake inputs; nothing is wired to them here, so they read high, and the
	// output latch supplies bits 0 and 3 so that a `res`/`set` on P8 -- which is a
	// read-modify-write -- does not clear the driven lines.
	uint8_t data = (m_cpu1_p8 & 0x09) | 0xd6;

	if (m_panel_sclk)
		data |= 0x20;

	return data;
}

void wsa1_state::cpu1_p8_w(uint8_t data)
{
	m_cpu1_p8 = data;
}

/***************************************************************************

    THE SERVICE CHECKING DEVICE, ON CPU 1's PORT 5

    ★ This closes gap L.  The routine at prom_a 0xF95137, reached from the boot
    sequence at 0xF827D1 through prom_b thunk 0xF40144, is

        ld C,(P5) / and C,0x10 / srl 4,C / and C,1 / jr NZ,ret

    -- it RETURNS IMMEDIATELY if P5 bit 4 reads 1, and otherwise calls 0xF95158
    twice (at 0xF95149 and 0xF95153, each after a `push WA`).  0xF95158 starts
    `ld E,0x04`, so it is FOUR flashes, and each flash writes P5 bit 3 with
    `stcf 3,(P5)` around a software delay of either 0x4000 or 0xC000 outer counts
    chosen by bit 0 of (XIZ+0x08) -- a short or a long flash.

    The SX-WSA1R service manual names all of it (OCR lines 793-801):

        "Connect the CHECKING DEVICE to CN4 on the MAIN P.C.B., and turn on the
         CHECKING DEVICE switch. ... the LED of the CHECKING DEVICE flashes 8
         times.  The first 4 flashes are for the RAM check, and the latter 4
         flashes are for the ROM check. ... If an IC is defective, the
         corresponding flash time is longer."

    Eight flashes as two calls of four, a long flash for a failure, and a switch
    that decides whether any of it runs.  So P5 bit 4 is the CHECKING DEVICE
    SWITCH -- low when it is on -- and P5 bit 3 is that device's LED.

    ⚠ DEFAULT = NOT CONNECTED, and it changes behaviour from every build before
    this one.  MAME's unbound port read returns 0, so bit 4 read low, the
    emulated machine behaved as though a service jig were plugged into CN4 with
    its switch on, and it spent the first 3.13 s of emulated time blinking a code
    at nobody.  A machine with nothing on CN4 is the normal one.

***************************************************************************/

// P5CR = 0x2C and P5FC = 0x24 (0xF826C1, 0xF826BE): bits 2, 3 and 5 are outputs
// and bit 4 is an input.  port_r<PORT_5>() returns this callback's value
// verbatim, and the blink writes bit 3 with `stcf 3,(P5)`, a read-modify-write,
// so the driven bits have to come back out of the latch.
uint8_t wsa1_state::cpu1_p5_r()
{
	uint8_t data = (m_cpu1_p5 & 0x2c) | 0xc3;   // 0, 1, 6, 7 do not exist on this port

	if (!BIT(m_checkdev->read(), 0))
		data |= 0x10;                           // switch off / nothing on CN4

	return data;
}

void wsa1_state::cpu1_p5_w(uint8_t data)
{
	m_cpu1_p5 = data;
	m_check_led = BIT(data, 3);
}

uint8_t wsa1_state::cpu1_pb_r()
{
	// Bits 2 and 3 are the port's only OUTPUTS (PBCR = 0x0C, 0xF826E5) and the
	// firmware read-modify-writes them: PortB3_Pulse (prom_a 0xFE594C) is
	// `ld A,(PB) / or A,0x08 / ld (PB),A` ... `and A,0xF7 / ld (PB),A`.  So the
	// output latch HAS to be handed back here, exactly as on P5, P7 and P8, or
	// the pulse could never fall again.  Bits 1, 5, 6 and 7 are inputs nobody
	// has read, and read high; bit 4 is the panel's busy line and idles low;
	// bit 0 is the model strap.
	uint8_t data = (m_cpu1_pb & 0x0c) | 0xe3;

	if (m_strap == 2)
		data &= ~0x01;                          // PB.0 low  -> (0xC4) = 2, the rack

	if (m_panel_busy)
		data |= 0x10;

	return data;
}


/***************************************************************************

    THE FLOPPY DISK CONTROLLER -- 0x7B0004 / 0x7B0005 and 0x7A0000 ON CPU 1

    ★ This closes gap B.  The device the two previous revisions of this file
    mapped .noprw() and called "unidentified" is a uPD765-FAMILY FLOPPY DISK
    CONTROLLER, and the identification is the disassembly's, not a resemblance
    argument: wsa1-roms-disasm/notes/FINDINGS-prom_a-fdc.md, from 4,794
    substantive bytes converted as one contiguous module at prom_a
    0xFE54EC-0xFE594B, 0xFE5A41-0xFE6850 plus four jump tables at
    0xFE6E3A-0xFE6E83, and re-derived from the ROM by that tree's
    notes/prom_a_fdc_checks.py (138 named checks).

    THE DECISIVE FACT is a 32-value truth table.  Fdc_ClassifyCommandOpcode
    (0xFE5CE8) is the firmware's own opcode validator; it masks the command byte
    with 0x1F -- so MT, MFM and SK are ignored, which is how a uPD765 decodes --
    and accepts exactly

        02 03 04 05 06 07 08 09 0A 0C 0D 0F 11 19 1D      (15 of 32)

    rejecting the other 17.  That is, value for value, the truth table of
    upd765_family_device::check_command() in src/devices/machine/upd765.cpp.
    Everything else agrees with it independently: the per-opcode parameter
    counts, SPECIFY taken before the drive byte is built (it is the one command
    with no HD/US byte), STP substituted for DTL on the three SCANs, the drive
    byte formed as (head & 1) << 2 | (unit & 3), FORMAT TRACK's 0xE5 filler, and
    a result decoder that tests ST0 bits 3 and 4, all six DEFINED ST1 bits and
    neither undefined one.

    WHICH PART.  The service manual's parts list has a NEC D72070GF3BE, and MAME
    has no uPD72070.  upd765a_device is used instead, and the reason is not
    "nearest by name": the firmware's validator implements the BASE uPD765
    opcode map, and upd765a_device is a base-command-set device
    (ps2_fdc_device, which upd72065/6/7/9 derive from, additionally accepts
    CONFIGURE, VERSION, LOCK, PERPENDICULAR and DUMPREG).  Nothing in this
    firmware can tell the two apart in any case: Fdc_IssueCommand has a
    well-formed CONFIGURE arm (0x00, 0x0C, 0xFF after opcode 0x13) and it is
    UNREACHABLE, because the routine classifies the opcode first and 0x13 is one
    of the 17 rejected values.  So the part runs in its power-on mode either way.
    ⚠ This is a substitution, and it is the one thing in this block that a
    reviewer should push back on if a uPD72070 ever appears in MAME.

    THE REGISTERS, each read off the driver rather than off a databook:

      0x7B0004 read   Main Status Register.  The five accessors at
                      0xFE54B6-0xFE54EB are the ENTIRE software interface to
                      this device in 1 MiB of ROM, and INT5_Dev7B_Receive
                      (0xFE6866) never stores what it reads here -- it tests
                      bit 7 (RQM) or bit 6 (DIO) and branches, every time.
      0x7B0004 write  see fdc_ctrl_w() below.
      0x7B0005 rw     Data Register.  0xFE54BC reads it and stores each byte
                      into the result buffer at 0x605A51; 0xFE54E6 writes it.
      0x7A0000 rw     THE SAME data register on the DMA-acknowledged decode.
                      Two paths reach it and both move one byte per request:
                      micro-DMA channel 0 (Dev7A_Dma_DeviceToRam 0xFE59BB sets
                      DMAS0 = 0x7A0000 FIXED with DMAD0 walking; _RamToDevice
                      0xFE59D2 is the mirror) and the programmed-I/O handler
                      Fdc_ServiceDataByte (0xFE680F / 0xFE682B).  A census of
                      both images finds four references to 0x7A0000 and none to
                      any other address in that window.

    INTERRUPTS, and the firmware names both of them in one instruction pair.
    Fdc_EnableInterrupts (0xFE5C03) is `ldio INTE45,0x40 / ldio INTETC01,0x05`
    and arms exactly two sources and no others:

      INT5    the RESULT-PHASE interrupt -> intrq.  INTE45 = 0x40 gives INT5
              priority 4 and leaves INT4 masked.
      INTTC0  micro-DMA channel 0's end of count, which is internal to the CPU.

    ★ AND INT5 IS ALREADY ARMED BEFORE ANY OF THAT.  The boot sequence at
    0xF827C8 writes the same value -- `ldio INTE45,0x40` at 0xF827CB, between
    `ldio 0x73,0x30` and `ldio 0x75,0x03` -- so INT5 is live at priority 4 from
    the first second of boot, not from the first floppy request.  (Found while
    checking the RESET port writes; notes/wsa1-probes/wsa1_port_reset_writes.py
    prints the whole `ldio` run this comes from.  It does not contradict
    Fdc_EnableInterrupts' own evidence, which is about what THAT routine arms.)
    It matters here because it means a spurious intrq from this device WOULD be
    dispatched into INT5_Dev7B_Receive, which contains an unbounded poll.
    Measured, and it does not happen: over 200 emulated seconds of either
    variant the handler's very first instruction on the device -- a read of
    0x7B0004 -- never executes (notes/wsa1-probes/wsa1_fdc_probe.lua reports
    msr_r=0).  upd765a_device's drive-ready polling only raises intrq on a
    CHANGE of ready, and with no motor line the drive never changes.

    The per-BYTE request line is INT7, and that is arithmetic rather than
    inference: uDMA0_ArmOnINT7 (0xFE5966) is `ldio DMA0V,0x0E`, MAME computes a
    channel's trigger as (DMAnV & 0x1F) << 2 (tmp95c061.cpp:353-366), and
    0x0E << 2 = 0x38 = INT7's vector.  So drq goes to INT7.  Note that INT7's
    own INTERRUPT LEVEL is never programmed, so it stays 0 and
    tlcs900_check_irqs() never dispatches it -- which is what makes vector slot
    0x38 pointing at the deliberate hang (0xF82D09) harmless.  The line exists
    only to feed the DMA engine.

    ⚠ ONE INFERENCE, AND IT IS THE ONLY ONE HERE: PB BIT 3 IS TC.
    PortB3_Pulse (0xFE594C) drives PB bit 3 high for five NOPs and low again,
    and the disassembly says in as many words that WHAT IT IS WIRED TO IS NOT
    ESTABLISHED.  It is wired to the controller's terminal-count input below,
    for three reasons that are together strong enough to state but not to call
    established:
      * it is pulsed from INTTC0_uDMA0Done (0xFE6858) -- i.e. at the instant
        micro-DMA channel 0's byte count reaches zero, and nowhere else;
      * the PROGRAMMED-I/O path ends its transfer with the same PortB3_Pulse +
        uDMA0_ArmOnINT7 pair, so two independent data paths pulse it at exactly
        the end of the data phase;
      * on a uPD765-family part there is no other input pin that means "the
        transfer is over", and the polarity matches: RESET writes
        `ldio PB,0xF3` at 0xF826DF, six bytes before the `ldio PBCR,0x0C` at
        0xF826E5 that makes bits 2 and 3 outputs, so PB bit 3 IDLES LOW and the
        pulse is a genuine low-high-low, which is TC's active-high shape.
    If a legible schematic ever contradicts this, one line in cpu1_pb_w()
    changes.  Nothing here fabricates a status byte either way.

    ⚠ WHAT IS DELIBERATELY *NOT* WIRED: CPU 1's PA BIT 3.  Operation 7 sets it
    and operation 6 clears it and waits 5 ticks (0xFE661F, 0xFE65EF), and the
    disassembly's verdict is "a drive-motor or drive-select line is the obvious
    reading and is NOT claimed here".  A motor is exactly what MAME's
    floppy_image_device needs before it will report READY, so wiring it would
    make an attached image work -- and would be a hardware claim nobody has
    checked, on a pin that RESET leaves HIGH (`ldio PA,0xF9` at 0xF826D6, with
    `ldio PACR,0x0E` at 0xF826DC making bits 1-3 outputs) which is the wrong way
    round for an active-high motor enable that operation 7 has to assert.  So it is LOGGED and not acted on, and the honest consequence is
    stated where it bites: with no motor line modelled the drive never becomes
    ready, so a read of an attached image will report the firmware's own "drive
    not ready" (error 0x31).  That is a real gap, and it is written up as one in
    notes/WSA1-EMULATION-DISASM-GAPS.md.

    THE GEOMETRIES the driver programmes, all three read off 30 immediates in
    Fdc_SelectFormatParameters (0xFE57FF), are the standard ones: 720 KB
    (N=2, EOT=9, GPL 0x1B/0x54, 80 cylinders), 1.2 MB (N=3, EOT=8, GPL
    0x53/0x74, 77 cylinders) and 1.44 MB (N=2, EOT=0x12, GPL 0x1B/0x6C, 80
    cylinders) -- which is why the drive below is a 3.5 inch HD one and the
    formats are the PC set.

    ONE THING AN EMULATOR MUST KNOW.  Fdc_WaitReadyForCommandByte (0xFE5A8F)
    contains an UNBOUNDED drain: when it sees MSR with CB masked out equal to
    0xC0 it reads the data register, stores the byte, reads MSR, DISCARDS that
    MSR and loops, with no exit test.  MAME's msr_r() returns RQM|DIO|CB in
    PHASE_RESULT, which is 0xC0 once CB is masked off -- so a controller left in
    result phase at a command-phase boundary wedges CPU 1 there.  It is the
    firmware's own code and it is reproduced faithfully; it is recorded here so
    that a future hang at 0xFE5AB7 is recognised instead of re-diagnosed.

***************************************************************************/

// PB bit 3 -> TC.  See the ⚠ INFERENCE paragraph above; this is the one line
// that changes if it is ever contradicted.
void wsa1_state::cpu1_pb_w(uint8_t data)
{
	if (BIT(data ^ m_cpu1_pb, 3))
		LOGMASKED(LOG_FDC, "%s: fdc TC %d\n", machine().describe_context(), BIT(data, 3));

	m_cpu1_pb = data;
	m_fdc->tc_w(BIT(data, 3));
}

// PACR = 0x0E (0xF826DC): PA bits 1, 2 and 3 are outputs, and the latch RESET
// writes is 0xF9 (0xF826D6), so bit 3 starts HIGH.  Bit 3 is the floppy module's only output outside
// its two device windows (operations 6 and 7 are its only writers, prom_a
// 0xFE65EF / 0xFE661F) and WHAT IT DRIVES IS NOT ESTABLISHED, so this handler
// records the transition and does nothing else.  Bits 1 and 2 are outputs whose
// writers have not been located at all; they are logged with it.
void wsa1_state::cpu1_pa_w(uint8_t data)
{
	if ((data ^ m_cpu1_pa) & 0x0e)
		LOGMASKED(LOG_FDC, "%s: CPU 1 PA <- 0x%02X (bit 3 = %d, unmodelled)\n",
			machine().describe_context(), data, BIT(data, 3));

	m_cpu1_pa = data;
}

// 0x7B0004, WRITE side.  The disassembly could only say "a control register,
// written with 0x80, 0x02 and 0x00, which does not read back -- which bit does
// what is NOT established" (FINDINGS-prom_a-fdc.md sec.5).  Reading it as the
// uPD765-family DATA RATE SELECT REGISTER accounts for all three values at once
// and for the offset, and every step is checkable in the ROM:
//
//   * THE OFFSETS ARE THE PC-COMPATIBLE ONES.  This device is decoded at base+4
//     (status/control) and base+5 (data), which is exactly MSR/DSR and the FIFO
//     in the standard uPD765-family register layout.
//   * 0x80 is DSR bit 7, SOFTWARE RESET, and it is SELF-CLEARING.  It has to be:
//     Fdc_ResetAndIdentifyMedia writes it at 0xFE55C5, waits two ticks, and then
//     issues SENSE INTERRUPT STATUS and SPECIFY -- commands the part could not
//     accept if the write had left it held in reset.  Fdc_PulseControlReset
//     (0xFE5576) does the same two instructions with no matching clear.
//   * 0x00 and 0x02 ARE THE DATA RATE, and the ROM proves it by WHICH GEOMETRY
//     gets which.  Fdc_ResetAndIdentifyMedia dispatches the media nibble through
//     Fdc_MediaTypeJumpTable (0xFE6E3A) and then:
//         geometry 2 (1.2 MB, 1024 B x 8) and 3 (1.44 MB, 512 B x 18)
//             -> 0xFE5690: pushw 0x00, then Dev7B_WriteControl_Shadowed
//         geometry 0, 4, 5 (720 KB, 512 B x 9)
//             -> 0xFE56B2: pushw 0x02, then Dev7B_WriteControl_Shadowed
//     MAME's rate table is { 500000, 300000, 250000, 1000000 } (upd765.h:231),
//     so 0 is 500 kbps and 2 is 250 kbps -- which is precisely 500 kbps for both
//     high-density geometries and 250 kbps for the double-density one.  Two
//     values, two correct answers, and no other reading of a two-bit field gives
//     that pairing.
//
// MAME's dsr_w() is a faithful model of the self-clearing bit and needs no help:
// its soft_reset() ends with `if(BIT(dor, 2)) end_reset();`, and a device with no
// DOR keeps dor = 0x0C, so the part comes straight back out into command phase
// (upd765.cpp:403-405).  Measured, not assumed -- notes/wsa1-probes/
// wsa1_fdc_selftest.lua drives this register with the firmware's own byte
// sequence and MSR reads 0x80 on the first poll afterwards.
void wsa1_state::fdc_ctrl_w(uint8_t data)
{
	LOGMASKED(LOG_FDC, "%s: fdc DSR <- 0x%02X%s\n", machine().describe_context(),
		data, BIT(data, 7) ? " (software reset)" : "");

	m_fdc->dsr_w(data);
}


/***************************************************************************

    THE SERIAL EEPROM ON CPU 2's PORT 6 AND PORT 8

    Ten routines at prom_c 0xFC89C5 bit-bang a Microwire device, and the four
    command words they shift out are what identify the protocol -- each is nine
    bits, MSB first (`ldb h,9`, test 0x0100, shift left):

        0xFC89C5  0x130          1 00 110000   EWEN   erase/write enable
        0xFC89F7  0x100          1 00 000000   EWDS   erase/write disable
        0xFC8A29  0x180 | addr   1 10 aaaaaa   READ
        0xFC8A62  0x140 | addr   1 01 aaaaaa   WRITE

    One start bit, two opcode bits, six address bits, and 16 data bits in both
    the write path and the read-back path (`ldb h,0x10`), i.e. a 64 x 16 organ-
    isation -- a 93C46-class part.  THE PART NUMBER IS AN INFERENCE FROM THE
    PROTOCOL: nothing in the ROM names it and the manual scan available here
    does not resolve it.  See
    wsa1-roms-disasm/notes/FINDINGS-prom_c-eeprom-and-runtime.md sec.1.

    The pins, each read off the driver's own instructions:

        P6 bit 5   CS   set 5,(P6) at 0xFC89CA opens every frame,
                        res 5,(P6) at 0xFC89F1 closes it
        P8 bit 3   SK   set 3,(P8) / res 3,(P8) once per bit (0xFC89DF/0xFC89E8)
        P8 bit 4   DI   driven from the bit being sent, before SK rises
                        (0xFC89D7 / 0xFC89DC)
        P8 bit 5   DO   only ever read -- bit 5,(P8) at 0xFC8ACC.  There is no
                        `set 5,(P8)` or `res 5,(P8)` anywhere in the driver

    RESET corroborates from the other side: `ldio P6FC,0x1F` (0xFFF01A) leaves
    P6 bit 5 a plain port pin, and `ldio P8CR,0x19` (0xFFF06F) makes bits 0, 3
    and 4 outputs and leaves bit 5 an input.

    WHAT IS IN IT.  EEPROM_LoadCalibration (0xFC8B0B) reads words 0..0x1E into
    RAM 0x00E2A1, requires word 0x1F to equal their sum and word 0x20 to equal
    0x5AA5, and hands the 62 bytes to NoteTrim_BuildFromCalibration (0xF997FA),
    which turns each into a signed per-note velocity trim at 0x0084DA.  So this
    device holds the factory per-key touch calibration.  It is NOT DUMPED, and
    no default_data is supplied here: a blank device fails the firmware's own
    checksum, 0xF997FA then takes its null-pointer arm and zeroes all 61 trims,
    and the touch response is the untrimmed curve.  That is an honest "no
    calibration stored", not a fake.

    !! ONE MAME CORE DEFECT IS IN THE WAY, and it is worked around in the CPU
    core rather than here.  tmp95c061.cpp mapped internal address 0x12 -- P6 --
    with `port_w<PORT_7>`, so every write to P6 was delivered to the PORT_7
    write callback.  The overlay copy of that file fixes it to `port_w<PORT_6>`;
    without the fix the EEPROM never sees CS and CPU 1's link-handshake shadow
    is clobbered by `ldio P6,0x1B` at 0xF826AF.  See the note at the top of
    src/devices/cpu/tlcs900/tmp95c061.cpp in this overlay.

***************************************************************************/

// P6 has no control register on this part (there is no P6CR in the SFR map) and
// MAME binds no read callback for it, so `set 5,(P6)` reads 0 and writes 0x20.
// Only bit 5 is a plain port pin here -- P6FC = 0x1F (0xFFF01A) turns bits 0-4
// into CS0, CS1, CS3/LCAS, RAS and REFOUT -- so only bit 5 is acted on.
void wsa1_state::cpu2_p6_w(uint8_t data)
{
	if (BIT(data ^ m_cpu2_p6, 5))
		LOGMASKED(LOG_EEPROM, "eeprom: CS %d\n", BIT(data, 5));

	m_cpu2_p6 = data;
	m_eeprom->cs_write(BIT(data, 5) ? ASSERT_LINE : CLEAR_LINE);
}

// P8CR = 0x19 (0xFFF06F): bits 0, 3 and 4 are outputs.  As with CPU 1's P7,
// port_r<PORT_8>() returns this callback's value verbatim rather than merging
// the output latch, and the EEPROM driver drives SK and DI with separate
// read-modify-write bit instructions -- so the latch HAS to be handed back here
// or `set 3,(P8)` would knock DI down again on every clock edge.
uint8_t wsa1_state::cpu2_p8_r()
{
	uint8_t data = m_cpu2_p8 & 0x19;

	data |= m_eeprom->do_read() << 5;           // 0xFC8ACC bit 5,(P8)

	// Bit 2 is an input the firmware polls at 0xF99543: on a change it sends
	// MIDI START (0xFA) or STOP (0xFB) on link channel 6.  WHAT IT IS WIRED TO
	// IS NOT ESTABLISHED (wsa1-roms-disasm/prom_c/wsa1_prom_c.s, the
	// MIDI_Watchdogs_And_TransportSwitch header), so it is left reading low --
	// which is what MAME's unbound port read did before this callback existed,
	// i.e. this is not a new claim about the hardware.  Bits 1, 6 and 7 are
	// unknown and read low for the same reason.
	return data;
}

void wsa1_state::cpu2_p8_w(uint8_t data)
{
	m_cpu2_p8 = data;

	m_eeprom->di_write(BIT(data, 4));           // 0xFC89D7 / 0xFC89DC
	m_eeprom->clk_write(BIT(data, 3));          // 0xFC89DF / 0xFC89E8
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

	// Only the per-channel range decodes as block/channel; the thirteen global
	// registers do not, so they are not printed as though they did.
	//
	// The decode now also names the STAGING WORD each per-channel block is fed
	// from, which is the one thing about this device that IS established.
	// Dev10C_WriteAllChanRegs (prom_c 0xFB713A) moves 22 words out of the struct
	// at CPU 2 work RAM 0x00D75E into 22 blocks of one channel, and
	// wsa1-roms-disasm/notes/FINDINGS-prom_c-dev10c-producers.md sec.2 lists,
	// per word, the routines that write it -- 70 sites over 21 of the 22 words.
	// So a trace that says "block 0x0A40" can be joined to a producer list, and
	// a trace that says only "reg 0x0A7F" cannot.
	//
	// ⚠ NONE OF THIS IS A MEANING.  Every producer in that note is a bare
	// sub_XXXXXX address; not one register is called pitch, level or wave there
	// or here.  The table below is a wiring diagram inside the firmware, not a
	// register description -- see gap A in notes/WSA1-EMULATION-DISASM-GAPS.md.
	if (m_tg_latch <= TG_CHAN_REG_TOP)
	{
		// Indexed by block number (register >> 6).  -1 = a block the unrolled
		// writer does not touch.  Blocks 0-6, 0x10-0x14 and 0x20-0x29 carry
		// staging words 0-6, 7-11 and 12-21 respectively.
		static const int8_t s_staging_word[0x2a] =
		{
			 0,  1,  2,  3,  4,  5,  6, -1,   -1, -1, -1, -1, -1, -1, -1, -1,
			 7,  8,  9, 10, 11, -1, -1, -1,   -1, -1, -1, -1, -1, -1, -1, -1,
			12, 13, 14, 15, 16, 17, 18, 19,   20, 21
		};

		const unsigned block = m_tg_latch >> 6;
		const int word = (block < sizeof(s_staging_word)) ? s_staging_word[block] : -1;

		// Word 0 is the exception and it is worth printing as one: it has no
		// staging producer anywhere, because Dev10C_WriteAllChanRegs writes
		// block 0 with the literal 0x8100 out of the writer itself.
		const char *note =
			(block == 0) ? " [literal 0x8100 in the writer, no staging word]" :
			(block == 2) ? " [the bit-15 gate, pulsed 1 then 0]" :
			(block == 6) ? " [the block 0xFA69B1 reads back -- see tg_status_r]" : "";

		if (word >= 0)
			LOGMASKED(LOG_TG, "tg: reg 0x%04X (block 0x%03X channel %2d) = 0x%04X"
				" <- staging word %d%s\n",
				m_tg_latch, block, m_tg_latch & 0x3f, data, word, note);
		else
			LOGMASKED(LOG_TG, "tg: reg 0x%04X (block 0x%03X channel %2d) = 0x%04X"
				" <- NO staging word (block outside Dev10C_WriteAllChanRegs)\n",
				m_tg_latch, block, m_tg_latch & 0x3f, data);
	}
	else
	{
		// Dev10C_WriteGlobalRegs (0xFB7715) writes 0x0200-0x0205, 0x0C00-0x0C05
		// and 0x0E00 as immediates and takes no channel argument, so anything
		// else up here is a register no converted routine is known to write.
		const bool known = ((m_tg_latch >= 0x0200) && (m_tg_latch <= 0x0205))
			|| ((m_tg_latch >= 0x0c00) && (m_tg_latch <= 0x0c05))
			|| (m_tg_latch == 0x0e00);

		LOGMASKED(LOG_TG, "tg: global reg 0x%04X = 0x%04X%s\n", m_tg_latch, data,
			known ? "" : " (NOT one of Dev10C_WriteGlobalRegs' thirteen)");
	}
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
	//
	// WHERE THE ANSWER WOULD COME FROM, now that the producers are located:
	// block 0x0180 is staging word 6, and FINDINGS-prom_c-dev10c-producers.md
	// sec.2 gives it exactly TWO producers, sub_FA96F7__FA9801 and
	// sub_FA9C60__FA9F06.  Neither is named for what it computes, so this stub
	// cannot be replaced yet -- but it is two routines away rather than a module
	// away, and that is gap F's shortest path.
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

	// Nineteen registers per channel, same `block * 0x40 + channel` numbering:
	// Dev104_WriteAllChanRegs (0xFB77EF) writes block k for k = 1..0x12 from
	// staging word 2*k and block 0 LAST.  Two of the smaller accessors in the
	// same bank write block 0 FIRST (0xFB7983, 0xFB79E5), so "block 0 is a
	// commit register" holds for the unrolled writer and is contradicted for
	// those two -- it is a property of each routine, not of the register.
	// (notes/FINDINGS-prom_c-tone-generator.md sec.4.)
	LOGMASKED(LOG_SYNTH2, "synth2: reg 0x%04X (block 0x%03X channel %2d) = 0x%04X\n",
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

// ---- 0x108000 / 0x108002: THE 61-KEY KEYBED SCANNER ----------------------
//
// The port is fully decoded, and the decode is not a resemblance argument: the
// two bytes the firmware pulls out of it are pushed STRAIGHT into
// ToneGen_VelocityFromTouch (0xF995DF), whose argument meanings were converted
// before this block was.
//
//   +2  read   status word.  Bit 0 gates everything -- KeyScan_ReadEvent
//              (0xF9973D) returns "no event" unless it is set
//              (0xF9976F and BC,0x0001).  The whole word is separately compared
//              against 2 at 0xF9979A; what value 2 MEANS is NOT ESTABLISHED, so
//              this model never produces it.
//   +0  read   one 16-bit key event:
//                  low  byte   bit 7 = note ON, bits 6..0 = key number
//                  high byte   the touch measurement
//
// (wsa1-roms-disasm/notes/FINDINGS-prom_c-keyboard-and-touch.md sec.1;
//  prom_c/wsa1_prom_c.s, the block comment at 0xF9973D.)
//
// SIXTY-ONE KEYS, and the count comes out twice in the firmware:
// KeyScan_InitKeyStateBitmap (0xF9988D) folds events into an 8-byte bitmap at
// work RAM 0x0000FFF0, and NoteTrim_BuildFromCalibration (0xF997FA) walks note
// 0..0x3C inclusive -- 61 -- which is the same index ToneGen_VelocityFromTouch
// uses.  KeyEvents_ToLink (0xF98CB9) then packs each decoded event as
// { 0x90, note, velocity } and sends up to ten of them to CPU 1 on link channel
// 5 (0xF98D24 ld (XBC+0xde),0x90; 0xF98D45 push 0x0005), with the note
// transposed by +36 inside ToneGen_VelocityFromTouch (0xF995EC), so key 0..60
// become MIDI 36..96 = C2..C7.
//
// WHAT THIS MODEL CHOOSES, and it is a choice, not a hardware fact:
//
//  * the QUEUE.  The firmware polls a status bit and takes one event at a time,
//    so the device plainly buffers at least one.  How deep the real queue is is
//    NOT ESTABLISHED; KEY_EVENTS = 32 here, and an overflow is logged rather
//    than silently dropped.
//  * the SCAN RATE.  1 kHz, chosen so a human keypress cannot be missed.  The
//    real scanner's rate is NOT ESTABLISHED.
//  * the TOUCH byte.  The hardware measures a key-contact TRAVEL TIME, not a
//    velocity: ToneGen_Velocity_Input_Curve (ROM 0xFCC61A) is non-increasing
//    over all 256 entries, so a LARGER touch value means a SOFTER note.  A PC
//    keyboard has no such measurement, so it comes from the "Key touch"
//    adjuster, mapped so that 100 = hardest.  Index 144 is the curve's pivot --
//    the only index at which it equals the 77 that 0xFCC5C5 subtracts -- and at
//    the firmware's default curve mode 6 the adjuster's default of 64 lands on
//    MIDI velocity 65.  0xFF is never sent: it is the firmware's "no travel
//    time was measured" code (0xF99795), which makes it drop the note-on.

uint16_t wsa1_state::keybed_status_r()
{
	// Read at 0xF99762, roughly 34,500 times a second of emulated time once
	// MAIN is running, so nothing is logged here.
	return m_key_fifo_count ? 1 : 0;
}

uint16_t wsa1_state::keybed_data_r()
{
	if (m_key_fifo_count == 0)
	{
		// The reader at 0xF99776 only gets here after the status bit said an
		// event was waiting, so it never does; but the SECOND reader, the
		// bounded drain in KeyScan_InitKeyStateBitmap at 0xF998C6, reads the
		// data port unconditionally, exactly 0x10 times, once per boot.  That
		// is expected traffic, hence LOGMASKED and not logerror.
		LOGMASKED(LOG_KEYBED, "%s: keybed data read with no event pending\n",
			machine().describe_context());
		return 0;
	}

	const uint16_t event = m_key_fifo[m_key_fifo_read];

	if (!machine().side_effects_disabled())
	{
		m_key_fifo_read = (m_key_fifo_read + 1) % KEY_EVENTS;
		m_key_fifo_count--;

		LOGMASKED(LOG_KEYS, "keybed: -> 0x%04X (key %2d %s, touch 0x%02X)\n",
			event, event & 0x7f, BIT(event, 7) ? "down" : "up  ", event >> 8);
	}

	return event;
}

void wsa1_state::keybed_status_w(uint16_t data)
{
	// The boot preload Dev108000_Preload_80toBF (0xF99125) writes 0x0080 + i
	// here and then 0x8000 to +0, 64 pairs, from RESET (0xFFF081) and from the
	// NMI handler (0xFFF0AE).  Note the order: +2 FIRST.  What it configures is
	// NOT ESTABLISHED, so nothing is done with it.
	LOGMASKED(LOG_KEYBED, "keybed: +2 <- 0x%04X\n", data);
}

void wsa1_state::keybed_data_w(uint16_t data)
{
	LOGMASKED(LOG_KEYBED, "keybed: +0 <- 0x%04X\n", data);
}

void wsa1_state::keybed_push(uint8_t key, bool pressed)
{
	// 0..100 from the adjuster, inverted onto the firmware's travel-time scale
	// and kept clear of 0xFF (see the block comment above).
	const unsigned adjust = std::min<unsigned>(100, m_touch->read());
	const uint8_t  touch  = std::min<unsigned>(0xfe, 255 - (adjust * 255) / 100);

	if (m_key_fifo_count >= KEY_EVENTS)
	{
		logerror("keybed: event queue full, key %d %s dropped\n",
			key, pressed ? "down" : "up");
		return;
	}

	m_key_fifo[(m_key_fifo_read + m_key_fifo_count) % KEY_EVENTS] =
		(uint16_t(touch) << 8) | (pressed ? 0x80 : 0x00) | key;
	m_key_fifo_count++;

	LOGMASKED(LOG_KEYS, "keybed: key %2d %s queued (touch 0x%02X)\n",
		key, pressed ? "down" : "up  ", touch);
}

TIMER_CALLBACK_MEMBER(wsa1_state::keybed_scan)
{
	// The ports themselves are absent on the rack driver, so guard on that
	// before the strap: an optional_ioport that was never found reads as null.
	if (!m_keybed[0])
		return;

	// A RACK HAS NO KEYS.  The SX-WSA1R's own service manual describes a 2U
	// module and its mechanical parts list has no keybed assembly, so in rack
	// mode this scanner has nothing to scan and must never queue an event.
	//
	// ⚠ This gate is a statement about the BOX, not about the firmware: the model
	// strap does NOT reach the keybed path.  prom_c -- the processor that owns
	// the scanner -- contains no PB read at all, there is not one `cp (0xC4)` in
	// the whole interprocessor-link block 0xF8E000-0xF8FFFF, and CPU 1 never
	// sends the variant over the link in any code path that has been read.  The
	// rack's firmware scans a keybed unconditionally; it simply finds none.  The
	// KEY ioports carry the same condition, so they also grey out in rack mode.
	if (m_strap != 1)
		return;

	uint64_t state = 0;

	for (unsigned port = 0; port < 6; port++)
		state |= uint64_t(m_keybed[port]->read() & 0xfff) << (port * 12);

	const uint64_t changed = state ^ m_keybed_prev;

	if (changed == 0)
		return;

	for (unsigned key = 0; key < KEY_COUNT; key++)
		if (BIT(changed, key))
			keybed_push(key, BIT(state, key));

	m_keybed_prev = state;
}

// ---- 0x7F0000 (CPU 1) and 0xE00000 (CPU 2): two 4 x 32 register files -----
//
// The same driver runs on both processors and on the KN5000's sub-CPU: an
// address register at +0 and a data register at +2, eight writes per slot, and
// a slot number formed as (channel << 5) | reg.  On CPU 1 the writer is
// Dev7F_WriteSlot8 (0xF83197: ld XIX,0x007F0000 at 0xF8319A, ld (XIX),W at
// 0xF831A8, ld (XIX+0x02),A at 0xF831AA) and DSP_Init_Channels (0xF85F0F) walks
// four channels with a stride of 0x20, setting register (ch << 5) | 0x1F of
// each to 1.  On CPU 2 it is 0xF98057 / 0xF98099, whose eighty-one bytes are
// identical to the KN5000 sub-CPU routine at payload 0x1FD27 bar the base
// address, and DSP_ChannelRegs_Write8 fills channels 0..3 from one 8-byte block
// (0xFC8719).  (wsa1-roms-disasm/notes/FINDINGS-prom_a-tasks-and-dsp-refresh.md
// sec. "DSP_Init_Channels"; notes/FINDINGS-prom_c-flash.md sec.5;
// notes/FINDINGS-memory-map.md, the 0x7F0000 and 0xE00000 rows.)
//
// WHETHER THE TWO ARE ONE DUAL-PORTED CHIP OR TWO INSTANCES IS NOT ESTABLISHED,
// so they are modelled as two independent register files with no connection
// between them.  Neither synthesises anything: they are storage, so that the
// debugger can see what the firmware programmed.  The KN5000 driver models its
// twin the same way at 0x130000/0x130002, with the standing correction that it
// is NOT the uPD6383GF host interface but a separate register file.

void wsa1_state::cpu1_chanreg_addr_w(uint16_t data)
{
	m_cpu1_chanreg_addr = data & 0xff;
}

void wsa1_state::cpu1_chanreg_data_w(uint16_t data)
{
	m_cpu1_chanreg[m_cpu1_chanreg_addr] = data & 0xff;

	LOGMASKED(LOG_CHANREG, "chanreg1: ch %d reg 0x%02X = 0x%02X\n",
		m_cpu1_chanreg_addr >> 5, m_cpu1_chanreg_addr & 0x1f, data & 0xff);
}

uint16_t wsa1_state::cpu1_chanreg_data_r()
{
	// No converted code reads this port; a read means an unreached path or a
	// decode error, so it is logged unconditionally.
	if (!machine().side_effects_disabled())
		logerror("%s: UNEXPECTED read of 0x7F0002 (slot 0x%02X)\n",
			machine().describe_context(), m_cpu1_chanreg_addr);

	return m_cpu1_chanreg[m_cpu1_chanreg_addr];
}

void wsa1_state::cpu2_chanreg_addr_w(uint16_t data)
{
	m_cpu2_chanreg_addr = data & 0xff;
}

void wsa1_state::cpu2_chanreg_data_w(uint16_t data)
{
	m_cpu2_chanreg[m_cpu2_chanreg_addr] = data & 0xff;

	LOGMASKED(LOG_CHANREG, "chanreg2: ch %d reg 0x%02X = 0x%02X\n",
		m_cpu2_chanreg_addr >> 5, m_cpu2_chanreg_addr & 0x1f, data & 0xff);
}

uint16_t wsa1_state::cpu2_chanreg_data_r()
{
	return m_cpu2_chanreg[m_cpu2_chanreg_addr];
}


void wsa1_state::machine_start()
{
	save_item(NAME(m_link_to_cpu2));
	save_item(NAME(m_link_to_cpu1));
	save_item(NAME(m_link_to_cpu2_full));
	save_item(NAME(m_link_to_cpu1_full));
	save_item(NAME(m_cpu1_p7));
	save_item(NAME(m_cpu2_pa));
	save_item(NAME(m_cpu2_p6));
	save_item(NAME(m_cpu2_p8));
	save_item(NAME(m_cpu1_p5));
	save_item(NAME(m_cpu1_p8));
	save_item(NAME(m_cpu1_pa));
	save_item(NAME(m_cpu1_pb));
	save_item(NAME(m_panel_sclk));
	save_item(NAME(m_panel_busy));
	save_item(NAME(m_strap));
	save_item(NAME(m_tg_latch));
	save_item(NAME(m_tg_regs));
	save_item(NAME(m_synth2_latch));
	save_item(NAME(m_synth2_regs));
	save_item(NAME(m_cpu1_chanreg_addr));
	save_item(NAME(m_cpu1_chanreg));
	save_item(NAME(m_cpu2_chanreg_addr));
	save_item(NAME(m_cpu2_chanreg));
	save_item(NAME(m_keybed_prev));
	save_item(NAME(m_key_fifo));
	save_item(NAME(m_key_fifo_read));
	save_item(NAME(m_key_fifo_count));

	// 1 kHz is this driver's choice, not the scanner's rate -- see the block
	// comment above keybed_status_r().
	m_keybed_timer = timer_alloc(FUNC(wsa1_state::keybed_scan), this);
	m_keybed_timer->adjust(attotime::from_msec(1), 0, attotime::from_msec(1));
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

	// CPU 2's P6 and P8 latches: EEPROM_PortInit (0xFC8B9D) drops CS, SK and DI
	// as its first act, so all-zero is where the driver puts them anyway.
	m_cpu2_p6 = 0;
	m_cpu2_p8 = 0;

	m_keybed_prev = 0;
	m_key_fifo_read = 0;
	m_key_fifo_count = 0;

	// THE MODEL STRAP IS SAMPLED HERE AND NOWHERE ELSE, which is what a strap is:
	// the firmware reads PB bit 0 exactly once, from RESET (prom_a 0xF827D8 ->
	// 0xF82882), so flipping the configuration switch takes effect on the next
	// machine reset and not in the middle of a run.  Latching it means the panel
	// device and cpu1_pb_r() cannot end up describing different machines.
	m_strap = variant();
	m_cpanel->set_variant(m_strap);

	m_cpu1_p5 = 0xff;
	m_cpu1_p8 = 0xff;

	// RESET programmes these two explicitly, `ldio PA,0xF9` at 0xF826D6 and
	// `ldio PB,0xF3` at 0xF826DF, so the shadows are seeded with the firmware's
	// own values rather than with all-ones.  PB bit 3 starting LOW is what makes
	// PortB3_Pulse a real low-high-low TC pulse; see the FDC block comment.
	// The four instructions are re-read out of the ROM by
	// notes/wsa1-probes/wsa1_port_reset_writes.py.
	m_cpu1_pa = 0xf9;
	m_cpu1_pb = 0xf3;

	m_panel_sclk = 1;
	m_panel_busy = 0;
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
	// Light on blue, the pen pair src/mame/yamaha/ympsr2000.cpp:46-47 uses for
	// its own SED1330 panel - the same controller at the same 320x240 geometry
	// on a contemporary instrument.
	//
	// This is still a DRIVER CHOICE, not a measurement.  The SX-WSA1R panel's
	// actual appearance is NOT ESTABLISHED: the service manual scan available
	// here names the controller but says nothing about the module, and no
	// photograph of a powered unit was consulted.  Borrowing a sibling driver's
	// palette makes it look like the class of part it is rather than like a
	// neutral placeholder; it does not make it verified.
	palette.set_pen_color(0, rgb_t(0x36, 0x41, 0xcf));
	palette.set_pen_color(1, rgb_t(0xdb, 0xe9, 0xff));
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
	// Static RAM on CS1 (MSAR1 = 0x00, 0xF82730).  MAMR1 = 0x7F (0xF8273C) is
	// the largest value that register takes, i.e. "everything left over", so
	// unlike MAMR3 below it puts no size on the chip inside the window.  The
	// chip is sized here from the firmware's own references instead, and comes
	// out at 32 KiB:
	//
	//   - the boot block clears 0x1460 longwords upward from 0x000080
	//     (0xF8278A).  That is a lower bound of 0x0051FF, and it is all the
	//     previous revision of this map had;
	//   - the boot path at 0xF82C80 works well above that bound.  It sums
	//     0x100 words from 0x007620 and compares the complement with
	//     (0x007FD2), then does the same over 0x617800 against (0x007FD4),
	//     leaving the two results as bits 0 and 1 of (0x007FD1) for 0xF82CAB
	//     to branch on.  What sits up there is the standard
	//     top-of-a-preserved-chip furniture: a 0x5AA5 magic word at 0x007FCA
	//     (0xF8292A) and the two checksum words (0xF8291D, 0xF82921).  The
	//     highest address any of it names is 0x007FD4, 44 bytes below the top
	//     of a 32 KiB device;
	//   - and this is MEASURED, not just read out of the disassembly.  With
	//     the chip mapped only to 0x0051FF every one of those accesses fell
	//     off the end of the map.  Mapped to 0x007FFF,
	//     notes/wsa1-probes/wsa1_boot_milestones.lua records the reads landing
	//     at t=3.13 s -- cksum1 at 0x007620 from PC 0xF82CDB, the flag word
	//     0x007FD0-0x007FD5 from 0xF82C88/0xF82CE2, cksum2 at 0x617800 -- and
	//     boot then proceeds into prom_b.  Before this change it did not.
	//
	// No claim is made about 0x008000 and up: sizing the chip at exactly
	// 32 KiB is an inference from the furniture sitting just under 0x008000,
	// not something the firmware states.
	//
	// 0x008000-0x3FFFFF is deliberately left unmapped, so a stray access above
	// the chip still shows up in the error log instead of silently aliasing.
	map(0x000080, 0x007fff).ram();

	// Work DRAM on CS3 (MSAR3 = 0x60, 0xF82736; P6FC = 0x1F at 0xF826B2 turns
	// the CS3 pin into LCAS, which is what identifies CS3 as the DRAM area).
	// Two clear loops cover 0x600000-0x6033FF (0xF8279A) and 0x604000-0x60FFFF
	// (0xF827AF).  The 3 KiB between them is skipped on purpose and is live -
	// prom_b reads it at 0xF440A5 - so it is the same DRAM, preserved across a
	// warm restart, and the whole span is mapped as one.  The first stack
	// pointer this machine has lands inside it, at 0x60EB80 (0xF85606).
	//
	// The mapped span is the whole CS3 window and not just the cleared part.
	// Here, unlike CS1, the window size is a statement about the chip: the
	// boot block writes MAMR3 = 0x0F (0xF82742), a specific value rather than
	// the register's maximum, and under the 32 KiB-per-unit decode that the
	// firmware's own elimination leaves standing that is 32 KiB x 16 =
	// 512 KiB, 0x600000-0x67FFFF.  That decode is the one the disassembly
	// tree's committed elimination leaves standing -- run
	// wsa1-roms-disasm/scripts/analysis/mamr_reading_elimination.py, which
	// kills 64 KiB-per-unit outright against eight facts taken from these
	// ROMs.  The firmware backs the size up by using memory well past the
	// cleared region: the 256-byte-record array based at 0x617800 (0xF61F5B,
	// and the inverse at 0xF5E2F4) is read during boot, and 0x617800-0x6179FF
	// is one of the two blocks the 0xF82C80 checksum pair covers -- the read
	// at 0x617800 is one of the milestones the probe above records.
	//
	// 512 KiB is therefore the DECODED window, and is what is mapped; it is
	// not a measured extent, because nothing in the reached code touches the
	// top of it.
	map(0x600000, 0x67ffff).ram();

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

	// ONE byte-wide data register, not a range: the FLOPPY CONTROLLER's data
	// register on the DMA-ACKNOWLEDGED decode.  A census over prom_a and prom_b
	// of the 24-bit memory-operand forms and the imm32 loads finds exactly four
	// sites in 0x7A0000-0x7A000F and all four name 0x7A0000: programmed I/O at
	// 0xFE680F ld C,(0x7A0000) and 0xFE682B ld (0x7A0000),C through the pointer
	// at (0x605A3E), and micro-DMA channel 0 through the pointer at (0x605A3C)
	// -- Dev7A_Dma_DeviceToRam (0xFE59BB) sets DMAS0 = 0x7A0000 fixed with
	// DMAD0 walking, Dev7A_Dma_RamToDevice (0xFE59D2) is the mirror.  The
	// per-byte request line is INT7 (uDMA0_ArmOnINT7 at 0xFE5966,
	// ldio DMA0V,0x0E, 0x0E << 2 = 0x38).  0x7A0001 is not referenced by
	// anything, so only the one byte is mapped.
	// (wsa1-roms-disasm/notes/FINDINGS-prom_a-fdc.md sec.5 and
	//  notes/FINDINGS-dev7b-and-int5.md; see the block comment on fdc_ctrl_w.)
	map(0x7a0000, 0x7a0000).rw(m_fdc, FUNC(upd765a_device::dma_r),
	                                  FUNC(upd765a_device::dma_w));

	// THE FLOPPY DISK CONTROLLER, Main Status Register / Data Rate Select
	// register (+4) and Data Register (+5).  A census of the 24-bit
	// memory-operand form over prom_a and prom_b finds exactly five accesses to
	// 0x7B0000-0x7B000F, all in one 54-byte block (0xFE54B6, 0xFE54BC,
	// 0xFE54C5, 0xFE54DD, 0xFE54E6), and those five accessors are the entire
	// software interface to the part.  Which register is which is read off the
	// callers, not assumed: INT5_Dev7B_Receive (0xFE6866) never STORES what it
	// reads from 0x7B0004 -- it tests bit 7 (RQM) or bit 6 (DIO) and branches,
	// every time -- while every read of 0x7B0005 is immediately stored into the
	// result buffer at 0x605A51.  The write side of +4 does not read back,
	// which is why Dev7B_WriteControl_Shadowed keeps a copy at RAM (0x605B09).
	//
	// See the block comment above fdc_ctrl_w() for the identification, for why
	// upd765a_device stands in for the parts list's uPD72070, and for how the
	// three values written to +4 decode.
	map(0x7b0004, 0x7b0004).r(m_fdc, FUNC(upd765a_device::msr_r))
	                       .w(FUNC(wsa1_state::fdc_ctrl_w));
	map(0x7b0005, 0x7b0005).rw(m_fdc, FUNC(upd765a_device::fifo_r),
	                                  FUNC(upd765a_device::fifo_w));

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

	// A 16-bit port read as a FIFO -- and it now has a ROLE, which is gap J
	// closed: it is the SECOND STORAGE UNIT of the same two-unit block-device
	// layer that drives the floppy.  Fdc_Request (0xFE66C7) takes a `unit` field
	// at request+0x02, every one of its twelve operations begins
	// `cp (0x605A32),1`, and all seven unit-1 arms in 0xFE4CE0-0xFE544D reach
	// the four accessors of this port (0xFE4C73 / 0xFE4C99 / 0xFE4CBF /
	// 0xFE4CE0), which are the only `add Xrr,0x007E0000` instructions in the
	// converted text of either image.  (FINDINGS-prom_a-fdc.md sec.6, checked by
	// that tree's notes/prom_a_unit1_backend_check.py.)
	//
	// STILL INERT, deliberately.  Knowing which block-device layer drives it is
	// not knowing what the device IS: no part is named, no register in either
	// bank has a meaning, and the accessor's index construction
	// (0x7E0000 + ((n & 7) | 0x08) or | 0x10) is all that says there are two
	// banks of eight -- in the only traced caller (0xFE50A0) both indices are
	// zero for all 256 iterations, so 0x7E0008 is the only address the code is
	// known to reach.  CS0 access timing is relaxed for the duration of that
	// transfer (B0CS 0x14 -> 0x10 -> 0x14, 0xFE509B and 0xFE50D5), which is also
	// what proves this device is on CS0.
	map(0x7e0008, 0x7e0009).noprw();

	// Address register (+0) and data register (+2) of a 4-channel x 32-register
	// file: 0xF8319A ld XIX,0x007F0000, then 0xF831A8 ld (XIX),W and
	// 0xF831AA ld (XIX+0x02),A, eight writes per slot with the slot formed as
	// (channel << 5) | reg.  The other processor drives a byte-identical shape
	// at 0xE00000.  See the block comment on the handlers.
	map(0x7f0000, 0x7f0001).w(FUNC(wsa1_state::cpu1_chanreg_addr_w));
	map(0x7f0002, 0x7f0003).rw(FUNC(wsa1_state::cpu1_chanreg_data_r),
	                           FUNC(wsa1_state::cpu1_chanreg_data_w));

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
	// (0xF989EF).
	//
	// The map now covers the WHOLE CS3 window, 0x000000-0x01FFFF, which both
	// surviving decoders agree on, and not just the cleared 0x000080-0x01007F.
	// The reason is a device the firmware puts above the clear: the FLASH
	// STAGING BUFFER at 0x010000-0x01FFFF, one whole 64 KiB flash sector held
	// in RAM.  Flash_ReadSectorToBuffer (0xFC89AF), Flash_ProgramSectorFromBuffer
	// (0xFC88F9) and Flash_ProgramSlice1K (0xFC893B) all load 0x00010000
	// literally (0xFC8903, 0xFC8945, 0xFC89B3), and the block writers form the
	// destination as `flash address - 0x00E70000` (0xFC87AE, 0xFC881B,
	// 0xFC8851), which is 0x00010000 + (address - 0x00E80000).
	// (wsa1-roms-disasm/notes/FINDINGS-prom_c-flash.md sec.3.)
	map(0x000080, 0x01ffff).ram();

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

	// THE 61-KEY KEYBED SCANNER: +0 event, +2 status with bit 0 = "an event is
	// waiting".  0xF99762 reads the status, 0xF99776 and 0xF998C6 read the
	// event, and the consumer is the velocity decoder at 0xF995DF.  The KN5000
	// has the identical interface at 0x110000/0x110002, which MAME already
	// models as kbd_data_r/kbd_status_r in kn5000.cpp.  Note that this device
	// is NOT the "+0 select / +2 data" pair the two rows either side of it are:
	// the boot preload at 0xF99125 writes +2 first and +0 second.  See the
	// block comment on the handlers.
	//
	// !! THE RACK SX-WSA1R HAS NO KEYBOARD.  The scanner is presumably live only
	// on the keyboard model, the SX-WSA1, which this driver does not declare
	// because no SX-WSA1 material was available to check the ROM set against.
	// It is wired up anyway, because it is the only way anything in this
	// machine can be made to play a note without a working MIDI IN, and because
	// the firmware in these images is the firmware that reads it.
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
	map(0xe00000, 0xe00001).w(FUNC(wsa1_state::cpu2_chanreg_addr_w));
	map(0xe00002, 0xe00003).rw(FUNC(wsa1_state::cpu2_chanreg_data_r),
	                           FUNC(wsa1_state::cpu2_chanreg_data_w));

	// This processor's program EPROM, also on CS2, with its own independent
	// vector table at 0xFFFF00 giving reset = 0xFFF000.  The device also holds
	// data: a "ZZZZ" headed bank at file 0x000000-0x0165BF, code from 0x018000
	// to 0x0621E4, and the boot block and vectors from 0x07F000.
	map(0xf80000, 0xffffff).rom().region("prom_c", 0);           // IC28
}


static INPUT_PORTS_START(wsa1r)
	// ------------------------------------------------------------------------
	// THE MODEL STRAP: SX-WSA1 (keyboard) or SX-WSA1R (rack)
	//
	// Technics shipped the same v2 ROM set in two boxes, and the firmware asks
	// the board which one it is in.  prom_a 0xF82882, reached once from RESET at
	// 0xF827D8, is the ONLY write to RAM (0xC4) in 512 KiB:
	//
	//     ld A,0x01 / bit 0,(PB) / jr NZ,+2 / ld A,0x02 / ld (0xC4),A / ret
	//
	// PB bit 0 is an input -- RESET writes PBCR = 0x0C at 0xF826E5, making only
	// bits 2 and 3 outputs -- and PBCR is written exactly once in either image.
	// ONE HUNDRED AND ELEVEN well-formed `cp (0xC4),#imm / jr cc` sites in 27
	// distinct 4 KiB blocks read the answer back, and every one of them compares
	// against 1 or 2 and nothing else.  What they switch is not cosmetic:
	//
	//   0xF8DC25  (0xC4)=2 skips all four A/D channel scans (the first skipped
	//             call is 0xF8DC3E `ld WA,(0x60)`, and SFR 0x60 is ADREG0L)
	//   0xFF42EE  (0xC4)=1 picks the display list at 0xF580B0 -- MIDI FILE LOAD /
	//             MIDI FILE SAVE / LOAD SINGLE SOUND / LOAD SINGLE COMBI. --
	//             while (0xC4)=2 picks 0xF58127, only the last two entries
	//   0xF8A109 / 0xF8A189   the panel's wire-address -> group map
	//   0xF8C8AC / 0xF8C8B7   the panel's LED-register -> wire-address map
	//   0xF898AD + 6 more     (0xC4)=2 forces a controller value to 0x40
	//
	// WHICH ARM IS WHICH MODEL is corroboration and not decode.  No string in
	// any of the four images names either model, and only the SX-WSA1R's service
	// manual exists here -- there is no SX-WSA1 document to check the other arm
	// against.  Two independent readings of the rack's own manual agree that the
	// rack is (0xC4)=2: its specification page's disk menu has no MIDI FILE LOAD
	// and no MIDI FILE SAVE, matching the shorter display list; and its
	// mechanical parts list has one VOLUME KNOB and one DIAL WHEEL and no bender,
	// matching the one pot (wire 0xD3) and one encoder (wire 0xD7) that variant 2
	// keeps -- where variant 1 additionally carries 0xD0, 0xD1 and 0xD2, two of
	// which have centre-detented curves (18 x 0x80 at index 120 of 256 in the
	// table at 0xF89CB4; 13 x 0x40 at index 58 of 128 at 0xF89B34), i.e. sprung
	// bipolar controls a rack module does not have.
	//
	// DEFAULT = RACK, deliberately.  It is what the dumped ROM set was read from,
	// what the service manual documents, and what this machine already did before
	// the strap was modelled at all: MAME's unbound port read returns 0, so PB
	// bit 0 read low and the firmware has been taking the (0xC4)=2 arm of all 111
	// gates since the driver was written.  Selecting the keyboard changes machine
	// behaviour, so it is the user's choice to make and to save, never a default
	// this driver quietly writes into their cfg.
	// ------------------------------------------------------------------------
	// ------------------------------------------------------------------------
	// THE SERVICE CHECKING DEVICE, plugged into CN4 on the MAIN P.C.B.
	// See the block comment above cpu1_p5_r() for the ROM and the manual page
	// that between them name the switch (P5 bit 4) and the LED (P5 bit 3).
	// Turn it on and the boot block blinks its eight-flash RAM/ROM verdict on
	// the "check_led" output before doing anything else.
	// ------------------------------------------------------------------------
	PORT_START("CHECKDEV")
	PORT_CONFNAME(0x01, 0x00, "Service checking device (CN4)")
	PORT_CONFSETTING(   0x00, DEF_STR(Off))
	PORT_CONFSETTING(   0x01, DEF_STR(On))
	PORT_BIT(0xfe, IP_ACTIVE_HIGH, IPT_UNUSED)

INPUT_PORTS_END


// The keyboard adds one thing the rack cannot have.  Everything else - the panel,
// the service checking device - comes in unchanged from the rack's port list.
static INPUT_PORTS_START(wsa1)
	PORT_INCLUDE(wsa1r)

	// THE 61-KEY KEYBED, six ports of twelve bits with one key in the last.
	// Key 0 is the lowest; the firmware adds 36 inside ToneGen_VelocityFromTouch
	// (0xF995EC), so key 0..60 are MIDI 36..96 = C2..C7 and the octave numbers
	// below are the MIDI ones.  61 is the firmware's own count, twice over --
	// see the block comment above keybed_status_r().
	//
	// Two octaves carry a default PC-keyboard mapping, the usual tracker
	// layout; nothing else in this driver claims a key, so there is no conflict
	// to work around.  Assign the rest from MAME's input menu.
	//
	// These fields exist only on the SX-WSA1 driver, so a rack module has no way
	// to press a key at all.  keybed_scan() carries the same gate as belt and
	// braces; see the comment there for why this is a claim about the BOX and not
	// about the firmware, which scans unconditionally on both variants - the
	// strap is not tested anywhere in the keybed or the link code.

	PORT_START("KEY0")
	PORT_BIT( 0x001, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("C2")
	PORT_BIT( 0x002, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("C#2")
	PORT_BIT( 0x004, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("D2")
	PORT_BIT( 0x008, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("D#2")
	PORT_BIT( 0x010, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("E2")
	PORT_BIT( 0x020, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("F2")
	PORT_BIT( 0x040, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("F#2")
	PORT_BIT( 0x080, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("G2")
	PORT_BIT( 0x100, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("G#2")
	PORT_BIT( 0x200, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("A2")
	PORT_BIT( 0x400, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("A#2")
	PORT_BIT( 0x800, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("B2")

	PORT_START("KEY1")
	PORT_BIT( 0x001, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("C3")
	PORT_BIT( 0x002, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("C#3")
	PORT_BIT( 0x004, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("D3")
	PORT_BIT( 0x008, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("D#3")
	PORT_BIT( 0x010, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("E3")
	PORT_BIT( 0x020, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("F3")
	PORT_BIT( 0x040, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("F#3")
	PORT_BIT( 0x080, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("G3")
	PORT_BIT( 0x100, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("G#3")
	PORT_BIT( 0x200, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("A3")
	PORT_BIT( 0x400, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("A#3")
	PORT_BIT( 0x800, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("B3")

	PORT_START("KEY2")
	PORT_BIT( 0x001, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("C4") PORT_CODE(KEYCODE_Z)
	PORT_BIT( 0x002, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("C#4") PORT_CODE(KEYCODE_S)
	PORT_BIT( 0x004, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("D4") PORT_CODE(KEYCODE_X)
	PORT_BIT( 0x008, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("D#4") PORT_CODE(KEYCODE_D)
	PORT_BIT( 0x010, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("E4") PORT_CODE(KEYCODE_C)
	PORT_BIT( 0x020, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("F4") PORT_CODE(KEYCODE_V)
	PORT_BIT( 0x040, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("F#4") PORT_CODE(KEYCODE_G)
	PORT_BIT( 0x080, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("G4") PORT_CODE(KEYCODE_B)
	PORT_BIT( 0x100, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("G#4") PORT_CODE(KEYCODE_H)
	PORT_BIT( 0x200, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("A4") PORT_CODE(KEYCODE_N)
	PORT_BIT( 0x400, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("A#4") PORT_CODE(KEYCODE_J)
	PORT_BIT( 0x800, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("B4") PORT_CODE(KEYCODE_M)

	PORT_START("KEY3")
	PORT_BIT( 0x001, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("C5") PORT_CODE(KEYCODE_Q)
	PORT_BIT( 0x002, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("C#5") PORT_CODE(KEYCODE_2)
	PORT_BIT( 0x004, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("D5") PORT_CODE(KEYCODE_W)
	PORT_BIT( 0x008, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("D#5") PORT_CODE(KEYCODE_3)
	PORT_BIT( 0x010, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("E5") PORT_CODE(KEYCODE_E)
	PORT_BIT( 0x020, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("F5") PORT_CODE(KEYCODE_R)
	PORT_BIT( 0x040, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("F#5") PORT_CODE(KEYCODE_5)
	PORT_BIT( 0x080, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("G5") PORT_CODE(KEYCODE_T)
	PORT_BIT( 0x100, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("G#5") PORT_CODE(KEYCODE_6)
	PORT_BIT( 0x200, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("A5") PORT_CODE(KEYCODE_Y)
	PORT_BIT( 0x400, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("A#5") PORT_CODE(KEYCODE_7)
	PORT_BIT( 0x800, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("B5") PORT_CODE(KEYCODE_U)

	PORT_START("KEY4")
	PORT_BIT( 0x001, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("C6")
	PORT_BIT( 0x002, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("C#6")
	PORT_BIT( 0x004, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("D6")
	PORT_BIT( 0x008, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("D#6")
	PORT_BIT( 0x010, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("E6")
	PORT_BIT( 0x020, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("F6")
	PORT_BIT( 0x040, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("F#6")
	PORT_BIT( 0x080, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("G6")
	PORT_BIT( 0x100, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("G#6")
	PORT_BIT( 0x200, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("A6")
	PORT_BIT( 0x400, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("A#6")
	PORT_BIT( 0x800, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("B6")

	PORT_START("KEY5")
	PORT_BIT( 0x001, IP_ACTIVE_HIGH, IPT_OTHER ) PORT_NAME("C7")

	PORT_START("TOUCH")
	// The touch measurement the scanner puts in the high byte of a key event is
	// a key-contact TRAVEL TIME, and the firmware's input curve at ROM 0xFCC61A
	// is non-increasing, so a bigger number is a softer note.  This adjuster is
	// inverted for the player's sake -- 100 is the hardest strike -- and mapped
	// onto 0x00..0xFE in keybed_push().  IT IS A DRIVER CONTROL, NOT A HARDWARE
	// REGISTER: a PC keyboard cannot measure a travel time, and no default is
	// established.  64 is chosen because at the firmware's power-on curve mode 6
	// (RAM 0x00F32A, boot value from ROM 0xFCC535) it lands on MIDI velocity 65.
	PORT_ADJUSTER(64, "Key touch (100 = hardest strike)")
INPUT_PORTS_END


// The service manual's parts list gives the drive as a 3.5 inch 2HD 1.44 MB /
// 2DD 720 KB unit, and the firmware programmes exactly the three geometries a
// drive like that carries (see the FDC block comment).  Only that one option is
// offered, because that is the only drive the manual describes.
static void wsa1_floppies(device_slot_interface &device)
{
	device.option_add("35hd", FLOPPY_35_HD);
}


void wsa1_state::wsa1_base(machine_config &config)
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
	m_cpu1->port5_read().set(FUNC(wsa1_state::cpu1_p5_r));
	m_cpu1->port5_write().set(FUNC(wsa1_state::cpu1_p5_w));
	m_cpu1->port8_read().set(FUNC(wsa1_state::cpu1_p8_r));
	m_cpu1->port8_write().set(FUNC(wsa1_state::cpu1_p8_w));
	m_cpu1->portb_read().set(FUNC(wsa1_state::cpu1_pb_r));
	m_cpu1->portb_write().set(FUNC(wsa1_state::cpu1_pb_w));
	m_cpu1->porta_write().set(FUNC(wsa1_state::cpu1_pa_w));
	m_cpu1->sc1_txd().set(m_cpanel, FUNC(wsa1_cpanel_device::tx_byte));
	m_cpu1->sc1_mod().set([this] (uint8_t data) { m_cpanel->rx_enable(BIT(data, 5)); });

	TMP95C061(config, m_cpu2, 28_MHz_XTAL);
	m_cpu2->set_addrmap(AS_PROGRAM, &wsa1_state::cpu2_map);
	m_cpu2->porta_read().set(FUNC(wsa1_state::cpu2_pa_r));
	m_cpu2->porta_write().set(FUNC(wsa1_state::cpu2_pa_w));
	m_cpu2->port6_write().set(FUNC(wsa1_state::cpu2_p6_w));
	m_cpu2->port8_read().set(FUNC(wsa1_state::cpu2_p8_r));
	m_cpu2->port8_write().set(FUNC(wsa1_state::cpu2_p8_w));

	// --- the control panel microcontroller ---------------------------------
	//
	// M37471M2196S on CONTROL PANEL 1, HLE'd; wsa1_cpanel.h carries the evidence
	// that this is what serial channel 1 talks to.  The four lines it needs are
	// the two port bits above, INT6 and SC1BUF, and every one of them is quoted
	// from the firmware in the block comment on cpu1_p8_r().
	//
	// ⚠ THE SERIAL CHANNEL AND INT6 BOTH REQUIRED CORE WORK, and the overlay copy
	// of tmp95c061 carries it: upstream's device has no serial engine at all
	// (sc1buf_r() returned 0, nothing ever set INTES1 bit 3, so INTRX1 could not
	// be raised from outside and inte_w() refuses to set it from a register
	// write), and execute_set_input() implemented neither INT6 nor INT7, so
	// set_input_line(TLCS900_INT6) was silently a no-op.  Both additions are
	// default-inert for every other tmp95c061 machine.
	WSA1_CPANEL(config, m_cpanel);
	m_cpanel->atn().set([this] (int state) {
			m_cpu1->set_input_line(TLCS900_INT6, state ? ASSERT_LINE : CLEAR_LINE); });
	m_cpanel->busy().set([this] (int state) { m_panel_busy = state; });
	m_cpanel->sclk().set([this] (int state) { m_panel_sclk = state; });
	m_cpanel->rxd().set([this] (uint8_t data) { m_cpu1->sc1_rxd(data); });

	// --- the floppy disk controller ----------------------------------------
	//
	// The evidence, the substitution of upd765a_device for the parts list's
	// uPD72070, and the one inference this costs are all in the block comment
	// above fdc_ctrl_w().  Only the wiring is here.
	//
	// The clock is INERT: upd765.cpp contains no call to clock() at all, and the
	// part's crystal is not established -- the manual's scan does not resolve a
	// value and nothing in the ROM divides one.  8 MHz is written because that
	// is the usual uPD765-family crystal, and nothing in this driver depends on
	// it; the data rate comes from the DSR writes instead.
	//
	// ready and select are both left CONNECTED, which is the device's default:
	// the firmware decodes ST3's RY bit in Fdc_Op11_SenseDriveStatus (0xFE6668)
	// and builds a US1/US0 drive byte in Fdc_IssueCommand (0xFE5C81), so both
	// lines are things this firmware expects to exist.  Note the unit field of a
	// request selects the BACK END rather than a second drive -- unit 1 is the
	// device at 0x7E0008, not a floppy -- so there is exactly one drive here.
	UPD765A(config, m_fdc, 8'000'000, true, true);
	m_fdc->intrq_wr_callback().set_inputline(m_cpu1, TLCS900_INT5);
	m_fdc->drq_wr_callback().set_inputline(m_cpu1, TLCS900_INT7);

	// PC formats rather than the bare MFM container set: the geometries the
	// firmware programmes are the IBM ones down to the gap lengths, so a raw
	// sector image of a 720 KB or 1.44 MB disk is the thing a user is most
	// likely to have.  No SX-WSA1 disk is dumped here, so this is untested
	// against real media.
	FLOPPY_CONNECTOR(config, "fdc:0", wsa1_floppies, "35hd",
		floppy_image_device::default_pc_floppy_formats).enable_sound(true);

	// The calibration EEPROM.  64 x 16 with a 6-bit address, which is a 93C46
	// class part; the identification is from the protocol the driver at
	// prom_c 0xFC89C5 bit-bangs, not from a part number, and the device itself
	// is not dumped.  See the block comment above cpu2_p6_w().
	EEPROM_93C46_16BIT(config, m_eeprom);

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
	// P5 bit 4 USED TO BE ON THIS LIST and is not any more: it is the service
	// CHECKING DEVICE's switch, the service manual says so in as many words, and
	// it is wired above.  See the block comment on cpu1_p5_r().
	//
	// ⚠ The 8-bit TIMER RATE IS 16x TOO SLOW, and it is a CPU-core issue, not
	// a driver one.  The boot block programs timer 1 as TREG1 = 0x1C counts of
	// phiT256 (TREG1 at 0xF826F4; T01MOD = 0x0D at 0xF826EB selects that tap),
	// which at fc = 28 MHz and phiT256 = fc/2048 is the
	// 488.28 Hz tick that every prom_b delay routine and the link's 500-tick
	// timeout are written against.  MAME's tmp95c061 implements that tap as
	// `m_timer_pre >> 15` = fc/32768 (tmp95c061.cpp:726-728), giving
	// 28e6/32768/28 = 30.5 Hz - and 30.4 Hz is exactly what the tick counter
	// at RAM 0x0080 is measured advancing at
	// (notes/wsa1-probes/wsa1_tick_counter.lua).  All four taps are shifted by
	// the same factor of 16 (tmp95c061.cpp:682-690, 720-728), so the whole
	// prescaler is uniformly scaled, and the disassembly tree's independent
	// derivation of fc from the sequencer tempo constant needs phiT1 = fc/8
	// where MAME uses fc/128 (wsa1-roms-disasm/notes/FINDINGS-system-clock.md,
	// lever B).  NOT CHANGED HERE: tmp95c061 is shared with ngp, namcos10 and
	// three other drivers, and no databook is present in these trees to settle
	// the tap numbering.  The consequence is only that boot takes ~90 s of
	// emulated time instead of ~6 s.
	//
	// Related, and also core-side: MAME's tmp95c061 never counts the 16-bit
	// timers 4-7 at all - m_t16_reg is written by treg45_w/treg67_w and read
	// by nothing (tmp95c061.cpp:1012-1063), and no code path sets INTET54 - so
	// INTTR4, this machine's musical clock (vector 0x50 -> 0xF82EA2), cannot
	// fire.  The sequencer cannot run until that is addressed.
	//
	// Still absent: the tone generator's actual synthesis, the three DSPs and
	// their microcode upload path, the AM29F400T flash (whose data-poll and
	// erase-verify loops are unbounded and will spin if reached) and the MIDI
	// port (MAME's tmp95c061 has no serial engine at all on channel 0 -
	// sc0buf_r returns 0 and sc0buf_w only fakes "transmit complete", so there
	// is nothing to connect a midiin/midiout to).  The floppy controller and the
	// panel microcontroller are no longer on this list; the floppy's one
	// remaining hole is that whatever drives the drive motor has not been
	// identified, so an attached image never becomes READY - see the ⚠ paragraph
	// about PA bit 3 in the block comment above fdc_ctrl_w().
	// CPU 1 nevertheless boots all the way to rendered text on the panel, and
	// CPU 2 will take a note from the keybed - see the boot walkthrough at the
	// top of this file.
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

// The keyboard runs the same four images.  The redistributed set is documented as
// working unmodified in both boxes, and nothing in the firmware selects ROMs by
// strap - the strap picks code paths, not images.
#define rom_wsa1 rom_wsa1r

// The two variants share EVERY device.  One ROM set runs in both boxes, both
// carry the same pair of TMP95C061s, the same panel link, the same LCD; the
// firmware branches on a strap rather than being built twice.  So the machine
// configuration is genuinely identical, and the difference lives where it
// actually is: in the strap value each driver initialises, and in which inputs
// the box physically has.
void wsa1_state::wsa1r(machine_config &config)
{
	wsa1_base(config);
}

void wsa1_state::wsa1(machine_config &config)
{
	wsa1_base(config);
}


} // anonymous namespace


// One ROM set, two products.  wsa1 is declared a clone of wsa1r and shares its
// ROM definitions verbatim (rom_wsa1 is rom_wsa1r above) - not because the rack
// matters more, but because every document this driver rests on is the rack's:
// the service manual is SX-WSA1R only (ORDER NO. EMiD951604) and the redistributed
// image set came out of a rack.  No SX-WSA1 material was available here, so which
// strap arm is which model is corroborated from the rack's own specification
// rather than decoded from a string - see the strap block comment above.
//
//   YEAR  NAME   PARENT  COMPAT  MACHINE  INPUT  CLASS       INIT        COMPANY     FULLNAME    FLAGS
SYST(1995, wsa1r, 0,      0,      wsa1r,   wsa1r, wsa1_state, init_wsa1r, "Technics", "SX-WSA1R", MACHINE_NOT_WORKING|MACHINE_NO_SOUND)
SYST(1995, wsa1,  wsa1r,  0,      wsa1,    wsa1,  wsa1_state, init_wsa1,  "Technics", "SX-WSA1",  MACHINE_NOT_WORKING|MACHINE_NO_SOUND)

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

    The clock is fc = 28 MHz.  ★ The schematic agrees: sheet II-9/II-10 draws
    X1, a 28 MHz crystal, across IC16 (a T7WU04F inverter pack), and that
    oscillator reaches both processors' X1 pins through 220 pF -- C198 into IC1,
    C199 into IC2.  The other crystal on that sheet, X5 at 24 MHz, is the floppy
    controller's, which is one reading of the parts list's second oscillator.
    The firmware said 28 MHz first, and that argument is kept because it is the
    one a reader without the book can check.  prom_c does not
    hard-code a serial divisor, it computes one: at 0xF991A2 it reads the byte at
    0xFFFFEF and writes BR0CR = (M >> 1) & 0x0F.  Under that rule the bit rate
    comes out at 31250 for any M provided fc = 1,000,000 * M, so the byte is fc
    in MHz, and prom_c[0xFFFFEF] = 0x1C = 28.  Two constants that share nothing
    with it agree: the sequencer tempo divide at 0xFAA378 uses 140,000,000,
    which is 5 * fc for timer 4 running at fc/8 with 96 ticks per beat (*) --
    an absolute frequency, so unlike the ratio retracted below this one really
    does pin fc once the tap scale is known -- and
    the MIDI init at 0xFA58F8 sets BR0CR = 0x0E, that is fc/896 = 31250 baud.  The
    MIDI divisor alone would not have settled it: both boot blocks first program
    a divide by 768 (0xF82754, 0xFFF078), which is self-consistent with a 24 MHz
    part, and the parts list has a 24 MHz ceramic oscillator as well as a 28 MHz
    one.  The tempo constant is what excludes that reading.

    The memory map below was derived from what the code establishes: the
    chip-select programming in the two boot blocks (0xF8272D onwards on the
    first processor, 0xFFF038 onwards on the second), the RAM those blocks
    clear, and the peripheral addresses the firmware demonstrably reads or
    writes.  Everything else is left unmapped on purpose.  ★ THE DECODERS ARE
    NOW READ OFF THE SHEETS as well, and they agree with the firmware
    everywhere: IC17 and IC18 on CPU 1, IC27 on CPU 2, with every output that
    the firmware touches carrying a net name.  Both tables are at the maps.
    What the sheets do NOT give is the MAMR window sizes; those still rest on
    an elimination over eight candidate decoders fed this machine's own register
    values, and one window, the first processor's CS0, survives that elimination
    in two readings that differ.  The devices on it are mapped because each
    address is referenced directly by the code, and because IC18 only decodes
    with A19 high, which puts all of them in 0x780000-0x7FFFFF under either
    reading; the window itself is not asserted anywhere below.

    ONE INFERENCE THE MAP USED TO REST ON, NOW PROVEN.  CPU 2's CS2 is proven
    16 bits wide by the firmware (the flash unlock addresses at
    0xFC8662/0xFC8672 are 0xAAAA/0x5554, twice the AMD byte-mode pair), and CPU
    1 carries the same B2CS = 0x1B, so prom_a and prom_b were TAKEN to be x16 as
    well.  ★ Sheet II-7/II-8 draws IC12 and IC13 with A1..A18 on the EPROM's
    A0..A17 and D0..D15 on its data pins -- the CPU's A0 is not connected, which
    is exactly what a x16 device on a byte-addressed bus looks like -- so the
    flat byte image per device that the mapping below asserts is correct.  The
    empirical corroboration is kept: the reset chain 0xF827C4 -> prom_b file 0x42D60 -> prom_a 0x5606, and the SWI7
    vector 0xFFFF1C -> prom_b file 0x400A4, all land on sane instructions, and
    one byte of base error would destroy every one of those cross-references.

    (*) WHERE THE fc/8 COMES FROM.  It is the part's own databook: Toshiba
    "TLCS-900 Series CMOS 16-bit Microcontrollers TMP95C061", Table 3.8 (1)
    p.81, "oT1 (8/fc)  oT4 (32/fc)  oT16 (128/fc)  oT256 (2048/fc)", repeated
    for the 16-bit timers in Figure 3.9 (3) p.95.  MAME's tmp95c061 used to
    implement those taps 16x slower and to not count the 16-bit timers at all;
    both are fixed in src/devices/cpu/tlcs900/tmp95c061.cpp, which carries the
    citation at the constants.  Re-check the quotes with
    notes/wsa1-probes/tlcs900_datasheet_quotes.py.

    ⚠ RETRACTED, and it must not come back: this paragraph used to argue the
    tap scale from the tempo tracker's 1750 multiplier (muls WA,0x06D6 at
    0xFA5553), claiming it fits fc/8 to 2.3% and misses fc/128 by 16.4x.  That
    ratio is oT256 over oT1, i.e. 2048/8 = 256 on the databook scale and
    32768/128 = 256 on the old one -- the SAME prediction either way.  It
    cannot adjudicate anything, and the "16.4x" came from pairing this part's
    oT256 with the sibling TMP94C241's oT1.  The same retraction is owed to
    wsa1-roms-disasm/notes/FINDINGS-system-clock.md, lever B, which is
    read-only from here.

    ★ MUCH OF WHAT THIS PARAGRAPH USED TO LIST AS OPEN WAS SETTLED ON
    2026-09-02/03, and not by the images: the service manual's P.C. diagrams on
    pages 19-23 are legible, and every text search of that book had come back
    empty only because it has no text layer.  Both chip-select decoders, the
    MAIN/SUB assignment, the fourth EPROM's designator and base, the parts on
    CPU 2's CS0 cluster and the whole port side of both processors are read off
    those sheets and cited where each is used below.  Still not established, and
    therefore not modelled: the bit layout of BnCS, BEXCS, DREFCR and DMEMCR,
    and what is behind the two decoder outputs that carry no net (0x7F0000 and
    0xE00000).  Recursive descent from the vectors currently reaches 36.7% of
    the first processor's two EPROMs and 42.6% of the second's, so a device
    touched only from code that has not been reached would still be missing from
    the map.

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
      - THE DEVICES ON BOTH CS0 AREAS ARE IDENTIFIED.  IC18 splits CPU 1's into
        LCDCS (IC7 SED1330FBA, wired), FDDAK and FDCS (IC8 D72070GF3BE, wired
        as an upd765a_device), MIF (the CPU link, wired) and HDCS; IC27 splits
        CPU 2's into SMIF (the link), WFICS (IC3 L7A1429), KSCS and SGCS (both
        ports of IC4 TC183C230002).  What each entry in the two memory maps
        below says about its device is now cited to a sheet.
        Two things are still only PARTLY modelled and say so at the map: the
        L7A1429 is a placeholder that holds its register file and makes no
        sound (acoustic_modeling.cpp), and the tone generator is a set of
        handlers with no synthesis behind them.
      - 0x7E0008 IS AN ATA HARD DISK -- IC18's HDCS, an ATA task file, and a
        FAT16 boot sector in prom_a for a 261.7 MB fixed disk.  It stays inert
        because nothing traced reaches the unit-1 path and whether a drive was
        ever fitted to a rack is open; see the map entry
      - 0x7F0000 on CPU 1 and 0xE00000 on CPU 2 are the two decoder outputs
        with no net on the schematic.  Both are modelled as the 4 x 32 register
        file their shared driver shape says they are, written and never read,
        with no part asserted
      - dump the six 16 Mbit wave mask ROMs, the AM29F400T flash, the serial
        EEPROM that holds the per-key touch calibration, and the internal ROM of
        the control panel microcontroller
      - the three D6383GF-3BA DSPs (IC5, IC6, IC30) have no MAME device and no
        model here.  Their host bus is fully mapped -- see the block comment
        above cpu2_p9_r() -- so the byte stream CPU 2 uploads to them is
        visible and goes nowhere.  (The M37471M2196S panel MCU is HLE'd in
        wsa1_cpanel.cpp.  The uPD72070 has no MAME device of its own either,
        but the family does -- the driver instantiates upd765a_device and says
        at the code why that is the right member of it.)

***************************************************************************/

#include "emu.h"

#include "cpu/tlcs900/tmp95c061.h"
#include "wsa1_cpanel.h"
#include "acoustic_modeling.h"
#include "wsa1_tonegen.h"

#include "imagedev/floppy.h"
#include "speaker.h"
#include "machine/eepromser.h"
#include "machine/upd765.h"
#include "video/sed1330.h"

#include "emupal.h"
#include "screen.h"

// The SX-WSA1R control panel, drawn from the service manual's own ARRANGEMENT OF
// CONTROL PANEL page (I-4/I-5) and wired from the CP1/CP2 schematic (II-29/30).
// See the header comment of src/mame/layout/wsa1r.lay for what is bound and what
// is only drawn.  The SX-WSA1 KEYBOARD deliberately gets no layout: its panel is
// a different board (two more scan columns, three more pots) and no document for
// it exists in these trees, so reusing the rack's would be a fabrication.
#include "wsa1r.lh"

#define LOG_LINK     (1U << 1)   // every byte and handshake edge on the CPU link
#define LOG_LINKLOST (1U << 2)   // a link latch overwritten before it was read
#define LOG_TG       (1U << 3)   // tone generator, 0x10C000
// (1U << 4) was LOG_SYNTH2, the second register file at 0x104000.  That device
// now lives in acoustic_modeling.cpp and carries its own VERBOSE mask; the bit is
// left unused rather than renumbered, so an old capture's mask still reads.
#define LOG_KEYBED   (1U << 5)   // keybed data/status, 0x108000
#define LOG_CHANREG  (1U << 6)   // the 4 x 32 register files, 0x7F0000 / 0xE00000
#define LOG_KEYS     (1U << 7)   // key presses queued for the scanner at 0x108000
#define LOG_EEPROM   (1U << 8)   // the serial EEPROM's CS / SK / DI / DO lines
#define LOG_FDC      (1U << 9)   // floppy: the control register, TC and CPU 1's PA bit 3
#define LOG_TGVOICE  (1U << 10)  // one decoded dump of a channel's 22 tone-generator registers

// LOG_LINKLOST is on by default on purpose: the one-byte-deep model of the link
// can only drop a byte silently, and this is how that shows up.  See risk (1)
// in the block comment on the link handlers.
#define VERBOSE (LOG_LINKLOST)
// Turn LOG_TG on to get the whole 0x0010C000 decode with a legend, and LOG_TGVOICE
// to get one 22-register dump per channel at every falling edge of block 0x0080's
// gate bit.  Both are compile-time; notes/wsa1-probes/wsa1_tg_lifecycle.lua taps
// the same port from Lua when a rebuild is not worth it.
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
		, m_modeling(*this, "modeling")
		, m_tonegen(*this, "tonegen")
		, m_fdc(*this, "fdc")
		, m_floppy(*this, "fdc:0")
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
	uint8_t cpu2_p9_r();

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
	// as A14/A15 driving a two-to-four decoder.  ★ IT IS ONE: IC27, a
	// D74HC139GS, with 1E = SCS0, 1DA = SA14 and 1DB = SA15, and all four
	// outputs named -- SMIF, WFICS, KSCS, SGCS.  The table is in cpu2_map().
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
	// 64 channels -- 64 from a literal loop counter, `ld D,0x40` at 0xFB8116 in
	// Dev10C_ResetAllChannels, whose `dec 1,D` bottom is at 0xFB8140.  (This
	// comment used to cite 0xFB8116's neighbour 0xFB810E, which is `ld HL,0x0840`
	// -- a register-block base that merely CONTAINS the byte 0x40.  Re-derived by
	// notes/wsa1-gapF-probes/gapF_refutation_probes.py, section P3.)  The count is
	// not from an address stride.  The highest
	// per-channel block the firmware is known to use is 0x0A40, from the
	// twenty-two-register unrolled writer Dev10C_WriteAllChanRegs (0xFB713A), so
	// the per-channel ceiling is 0x0A7F.  The GLOBAL registers sit above it and
	// are NOT of that form: Dev10C_WriteGlobalRegs (0xFB7715) takes no channel
	// argument and writes 0x0200-0x0205, 0x0C00-0x0C05 and 0x0E00 as immediates.
	// 0x1000 covers all of it.
	// (wsa1-roms-disasm/notes/FINDINGS-prom_c-tone-generator.md sec.2, 3 and 7.)
	static constexpr unsigned TG_REG_COUNT   = 0x1000;
	static constexpr unsigned TG_CHAN_REG_TOP = 0x0a7f;   // 0x0A40 + 0x3F
	static constexpr unsigned TG_VOICES      = 64;        // `ld D,0x40`, 0xFB8116

	// 0x10C000 -- the tone generator.  TC183C230002 (IC4), the same part number
	// the KN5000 carries at IC303 (see kn5000_tonegen.h).
	void     tg_addr_w(uint16_t data);
	void     tg_data_w(uint16_t data);
	uint16_t tg_status_r();
	void     tg_log_legend() ATTR_COLD;
	void     tg_dump_channel(unsigned chan);

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
	// 0x104000 on CPU 2 -- the second 64-slot per-channel register file, a
	// placeholder device that synthesises no audio.  The window decodes to IC3,
	// the L7A1429, on the schematic (IC27 1Y1 = WFICS -> IC3 NSGCE); what is
	// still inference is the part's INTERNAL signal path, and
	// acoustic_modeling.h grades every claim and carries the firmware citations.
	required_device<l7a1429_device> m_modeling;
	// IC4 tone generator (TC183C230002).  A PLACEHOLDER SINE backend while the
	// six wave mask ROMs are undumped -- just like the KN5000's RENDER_SINE.
	// Fed by the real 0x0010C000 register writes in tg_data_w; wsa1_tonegen.h.
	required_device<wsa1_tonegen_device> m_tonegen;
	required_device<upd765a_device> m_fdc;
	required_device<floppy_connector> m_floppy;
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

	// The tone generator's BUSY LATCH, in the firmware's own encoding: word
	// `chan >> 4`, bit `chan & 15`.  That encoding is imposed twice by unrelated
	// code -- by Dev10C_PollBankAndRetire on the word it reads (0xFA694A start
	// channel, 0xFA695C walker, 0xFA69E7 sllw), and by Shift16_Left(1, chan & 15)
	// stored at index chan >> 4 for the two RAM masks (0xFA6CE3-0xFA6CF6).  It is
	// NOT derivable from m_tg_regs[chan]: on a note-on the computed word
	// voicerec[+0x29] lands on block 0 AFTER the gate (Dev10C_WriteReg_c at
	// 0xFB39AD / 0xFB371D), so the last value there is not 0x8100.  See the long
	// comment in tg_data_w() for why joining block 0's write to block 0's read is
	// a MODEL and what bounds it.
	uint16_t m_tg_busy[4]{};

	// Log aid only: block 0x0080's bit 15 per channel, as last written.  Nothing
	// in the emulated machine reads it.
	uint64_t m_tg_gate = 0;
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

    ★ AND THE HARDWARE IS TWO OCTAL LATCHES, which is the strongest thing the
    schematic says about this driver's model (sheet II-9/II-10, manual page 20):

        IC24  D74HC374GS   D <- SD0..SD7 (CPU 2), Q -> D0..D7 (CPU 1)
                           CK  <- SIFINT       /OE <- MIF OR RD      (IC26)
        IC25  D74HC374GS   D <- D0..D7 (CPU 1), Q -> SD0..SD7 (CPU 2)
                           CK  <- IFINT        /OE <- SMIF OR SRD    (IC26)
        IC26  D74HC32GS    SIFINT = SMIF OR SWR,  IFINT = MIF OR WR

    Three things follow; the driver already models the first two.  The latch is
    ONE BYTE DEEP in each direction, so a second write before the far read
    overwrites it with nothing to say so -- which is what LOG_LINKLOST exists
    for.  There is no full/empty flag anywhere in the glue: the four handshake
    pins above are the ONLY flow control, done in software.  And each interrupt
    is the far side's own write strobe: SIFINT is asserted while CPU 2 is
    writing SMIF, IFINT while CPU 1 is writing MIF.

    ⚠ SO THE INTERRUPT IS A PULSE ON THE BOARD AND A HELD LEVEL HERE.  This
    driver asserts INT0 on the write and clears it when the far side reads the
    latch, because reading the latch is what the firmware's handler does and
    the model has to end the request somewhere; the gates above end it when the
    write cycle ends instead, and nothing in the glue notices the read at all
    (a read only turns the latch's outputs on).  Changing the model to a pulse
    is NOT proposed on this evidence: what a level-triggered INT0 does with a
    one-bus-cycle pulse depends on when the core samples the line, and the held
    level is what the measured traffic below was taken with.

    THE HANDSHAKE PINS.  P7CR = 0x33 (0xF826CA) makes CPU 1's P7 bits 0, 1, 4
    and 5 outputs; PACR = 0x03 (0xFFF02C) makes CPU 2's PA bits 0 and 1
    outputs.  Bit 0 is a strobe, held low from just before the header byte
    until the far side answers; bit 1 is a "receiver busy", driven low by the
    INT0 handler once channel 3 is armed and released when the exchange ends.
    Bits 2 and 3 are the far side's bit 0 and bit 1:

        CPU 1 P7.0 -> CPU 2 PA.2      CPU 2 PA.0 -> CPU 1 P7.2
        CPU 1 P7.1 -> CPU 2 PA.3      CPU 2 PA.1 -> CPU 1 P7.3

    (*) ★ THE CROSS-WIRING IS CONFIRMED BY THE SCHEMATIC, 2026-09-03.  It was
    derived from the firmware first; the four nets are named on the P.C.
    diagrams -- IC1 on sheet II-7/II-8 (manual page 19), IC2 on sheet
    II-9/II-10 (page 20):

        MSTAT0   IC1 pin 2  P70  --R149 1K-->  IC2 pin 34  PA2
        MSTAT1   IC1 pin 3  P71  --R150 1K-->  IC2 pin 35  PA3
        SSTAT0   IC2 pin 32 PA0  --R162 1K-->  IC1 pin 4   P72
        SSTAT1   IC2 pin 33 PA1  --R163 1K-->  IC1 pin 5   P73

    -- exactly the mapping below, and the two direction registers agree with it:
    P7CR = 0x33 makes IC1's P7 bits 0 and 1 outputs and PACR = 0x03 makes IC2's
    PA bits 0 and 1 outputs.  Re-render the crops with
    notes/wsa1-probes/wsa1_sch_cpu_ports.sh.  The firmware argument below is
    kept because it is the one a reader without the book can check.  It is the
    only assignment that satisfies all three uses at once: the sender waits for
    bit 3 to FALL after writing the header (0xF8E136), which under this mapping
    means "the far side has armed its DMA and can absorb the burst"; the INT0
    handler drops the interrupt when bit 2 is SET (0xF8E489), which means "no
    far strobe, so nobody is talking to me"; and the general sender waits for
    bit 3 to be SET before starting (0xF999D0), which means "the far receiver
    is idle".  The one competing reading - that bits 2 and 3 are full/empty
    flags of a latch in glue logic - is rejected because a latch-empty flag
    would fall when the receiver READS the byte (0xF99BD3), which is BEFORE the
    DMA is armed, and the sender would then start the burst too early.

    ** MEASURED 2026-08-25 -- ⚠ FIXED 2026-08-27, KEPT BECAUSE THE SYMPTOM IS
    WORTH RECOGNISING: THE CPU 2 -> CPU 1 DIRECTION SENT EXACTLY ONE PACKET AND
    THEN WEDGED.  CPU 1 -> CPU 2 carries
    56 bytes over a boot and is fine.  CPU 2 -> CPU 1 writes two bytes -- one
    header plus one payload -- at about t=72 s, and after that CPU 1 leaves P7
    bit 1 LOW for good (it writes P7 = 0xE7 up to t=70 and P7 = 0xC5 from t=72),
    so `Link_SendChunk`'s opening wait for PA bit 3 (0xF999D0) never passes and
    every later packet burns its 0x4E20 spins and is dropped.  The visible
    consequence is that a key press IS decoded by prom_c and its
    { 0x90, note, velocity } packet never reaches CPU 1.
    notes/wsa1-probes/wsa1_link_handshake.lua is the measurement.
    ★ CAUSE FOUND 2026-08-27, AND IT WAS IN THE CPU CORE.  Two earlier
    paragraphs stood here and both were wrong, for the same reason: they quoted
    notes/wsa1-probes/wsa1_link_stage.lua, whose three counters were all read
    through taps that cover more than the thing they name.  "INTTC3_LinkDmaDone
    runs 12 times" was INTTC2_uDMA2Done RETURNING six times -- its `reti` sits at
    0xF8E54E, one byte below INTTC3's entry, and RDOP()'s four-byte prefetch
    (tlcs900.cpp:81-99) reads both.  "DMA3V is written 11 times" counted DMA2V
    (SFR 0x7E) too, which the transmit block arms from nine sites.

    The unaliased measurement is notes/wsa1-probes/wsa1_udma3_audit.lua, which
    counts INTTC3 entries as reads of the selector word (0x6007DA) -- the one
    read of it in prom_a, prom_b or prom_c is INTTC3's own, at 0xF8E555, proved
    by notes/wsa1-probes/wsa1_udma3_xref.py.  Over a 100 s boot:

        INTTC3 entries               0        (not twelve -- ZERO)
        DMA3V arms                   5        1 x 0x0A, 4 x 0x00 (aborts)
        CPU 1 reads of 0x7C0000      1
        CPU 2 writes to 0x100000     2

    The whole boot contains ONE received message, at t = 70.843: header 0xC0
    arrives, INT0_LinkByte reads it, arms channel 3 (DMAC3 = 1, DMAD3 =
    0x6007B3, DMAS3 = 0x7C0000, DMAM3 = 0x00), writes DMA3V = 0x0A and drops P7
    bit 1.  CPU 2 then writes the payload byte 0xFB -- and nobody ever reads it.
    DMAC3 stays at 1 for twelve Link_ServiceTask samples and the watchdog aborts
    at t = 72.012.

    notes/wsa1-probes/wsa1_int0_steal.lua says why, counting interrupt
    dispatches the only unambiguous way there is -- reads of the vector table,
    which nothing but a dispatch touches:

        t=70.8434  CPU2 -> latch 0xC0
        t=70.8434  DISPATCH INT0 #1        INTE0AD=0x89 (request bit set)
        t=70.8434  CPU1 reads latch -> 0xC0
        t=70.8434  DMA3V := 0x0A           DMAC3=1
        t=70.8434  CPU2 -> latch 0xFB
        t=70.8435  DISPATCH INT0 #2   <--  the CPU took the DMA's interrupt

    On a TLCS-900/H the second INT0 belongs to micro-DMA channel 3, because
    DMA3V points at INT0's vector.  MAME's tmp95c061.cpp dispatched it to the
    CPU instead, and INT0_LinkByte's own `bit 2,(P7)` guard at 0xF8E489 then
    returned WITHOUT reading the port, so the byte was neither delivered nor
    consumed.  Fixed as OVERLAY FIX 6 in tmp95c061_device::tlcs900_check_irqs():
    skip any interrupt a micro-DMA channel is armed for -- which is exactly what
    MAME already does in tmp94c241_device::tlcs900_check_irqs() ("HDMA priority:
    skip interrupts targeted by active HDMA channels").  tmp95c061 was the odd
    one out.  ⚠ NOT a driver bug: this block's model of the link was right, and
    the deferred CLEAR_LINE below was never the problem.

    WHAT THIS MODEL DOES NOT GUARANTEE.  The latch is one byte deep, and real
    hardware has no per-byte handshake during a burst: the strobe is released
    BEFORE the body and the receiver's DMA is expected to keep up.  The model
    relies on set_input_line() enqueuing on a zero-delay timer, which aborts
    the sending processor's timeslice, plus the shortened scheduling quantum in
    wsa1r().  That is a scheduling argument, not a proof, which is why
    LOG_LINKLOST is compiled in by default.

    ** AND IT BIT, 2026-08-27.  With OVERLAY FIX 6 in place the link runs -- and
    then notes/wsa1-probes/wsa1_udma3_audit.lua measured CPU 2 writing 71 bytes
    to its port over a 100 s boot while CPU 1 read its port 21 times.  The cure
    is the per-burst perfect_quantum() in cpu2_link_w() below, and the number
    that identifies it is in that function's comment: one byte-time is 6 us and
    the quantum was 50 us.

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

// How long each latch write holds the processors in lockstep.
//
// THE NUMBER THAT SETS IT IS 42 us, NOT 6 us.  One byte-time inside a burst is
// ~6 us (measured, see cpu2_link_w()), and this constant was first chosen
// against that.  Wrong gap: the window is armed by the HEADER byte, and the
// sender takes 42 us to get from the header to the first byte of the burst
// (notes/wsa1-probes/wsa1_wire_window.lua).  A 20 us window expires inside that
// gap -- device_scheduler::add_quantum() measures expiry from the scheduler's
// current time, so a shortened quantum only bites from the NEXT timeslice and
// the slice already granted runs to its end -- and CPU 2 then empties five
// byte-times into the one-byte latch before the receiver runs.
//
// MEASURED over the same 95 s boot, everything else equal:
//
//     window   {LE32 dest, LE16 count} record CPU 1 assembles   CPU2->CPU1 w/r
//      20 us   02 78 10 20 20 44  dest 0x20107802 count 17440    711 / 706
//     200 us   00 73 00 00 C0 02  dest 0x00007300 count 704      719 / 719
//
// 0x20107802 is not even drivable on a 24-address-pin part; 0x00007300 is inside
// map(0x000080, 0x007fff).ram() and 1 + 6 + 704 = 711 accounts for every byte
// the boot sends.  At 200 us the exchange is in lockstep from byte #2, INTTC3
// reaches selector 4 (INTTC3_Sel4_BlockDone) instead of stalling in selector 2,
// and the block of sound-name text lands where the record says.
// notes/wsa1-probes/wsa1_e1_record.lua prints the record; wsa1_udma3_audit.lua
// prints the counts.
//
// It buys accuracy, not speed: the fine interleave is paid only while a message
// is actually moving.
static constexpr int BURST_QUANTUM_US = 200;

void wsa1_state::cpu1_link_w(uint8_t data)
{
	if (m_link_to_cpu2_full)
		LOGMASKED(LOG_LINKLOST, "%s: CPU 1 overwrote an unread link byte (0x%02X -> 0x%02X)\n",
			machine().describe_context(), m_link_to_cpu2, data);

	LOGMASKED(LOG_LINK, "%s: CPU 1 -> CPU 2: 0x%02X\n", machine().describe_context(), data);

	m_link_to_cpu2 = data;
	m_link_to_cpu2_full = true;
	m_cpu2->set_input_line(TLCS900_INT0, ASSERT_LINE);

	// Interleave finely for the rest of the burst -- see cpu2_link_w().
	machine().scheduler().perfect_quantum(attotime::from_usec(BURST_QUANTUM_US));
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

	// A BURST NEEDS THE TWO PROCESSORS INTERLEAVED FINER THAN 6 us, 2026-08-27.
	//
	// The latch is one byte deep and a burst has no per-byte handshake: the
	// sender's micro-DMA channel 2 pushes bytes paced by timer 2 alone and the
	// receiver's channel 3 is expected to keep up, which on the real part it
	// does -- a micro-DMA cycle is a handful of states.
	//
	// MEASURED, and this is the number that decides the fix
	// (notes/wsa1-probes/wsa1_link_burst_timing.lua, 75 s boot):
	//
	//     SENDER GAPS  n=70  min=5.857 us  median=6.036 us  max=75.679 us
	//
	// 6 us is a plausible HARDWARE pacing, not a bug -- reading T23MOD = 0x0E as
	// the phi-T16 tap, TREG2 = 5 at fFPH = 14 MHz gives 5 x 16 x 71.4 ns =
	// 5.71 us.  (⚠ that bit decode is the TLCS-900/H convention, not a databook
	// this tree has; the fix does not depend on it, only on the 6 us : 50 us
	// ratio.)
	// The trouble is that wsa1r()'s scheduling quantum is 50 us, so CPU 1 runs up
	// to EIGHT byte-times ahead, CPU 2 then fills the same one-byte latch eight
	// times, and CPU 1 can only ever collect the last one -- measured 71 writes
	// against 24 reads, with the reads landing 40 us after the byte they took.
	// The 0xE1 answer's {LE32 dest, LE16 count} record therefore arrives corrupt
	// and INTTC3_Sel2_ArmPayload arms DMAC3 with 0xFFEF.
	//
	// perfect_quantum() for one burst-length window is the cheap cure: the fine
	// interleave costs emulation speed only while a message is actually moving,
	// and a plain set_maximum_quantum() this small would pay it for the whole
	// run.  ⚠ abort_timeslice() -- the KN5000's remedy,
	// notes/upstream-patches/kn5000-26-intercpu-latch-int0-handshake.patch -- was
	// tried first and MEASURED at 21 -> 24 reads out of 71: it cannot help,
	// because it only ends the SENDER's slice and the receiver is already ahead
	// in local time.  (Re-measured 2026-08-27 in the cell that was missing: with
	// perfect_quantum() ALSO in, abort_timeslice() is a complete no-op -- the
	// wire trace is timestamp-identical and the t=95 s screenshot byte-identical.
	// The 21 -> 24 result reproduces exactly.  See BURST_QUANTUM_US above for
	// what does move it.)
	machine().scheduler().perfect_quantum(attotime::from_usec(BURST_QUANTUM_US));
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


// CPU 1'S PORT 7, ALL SIX PINS NAMED BY THE SCHEMATIC (IC1, sheet II-7/II-8,
// manual page 19; notes/wsa1-probes/wsa1_sch_cpu_ports.sh re-renders it):
//
//     pin 2  P70  MSTAT0   out, R149 1K, to IC2 PA2    the link strobe
//     pin 3  P71  MSTAT1   out, R150 1K, to IC2 PA3    the link receiver-busy
//     pin 4  P72  SSTAT0   in,  from IC2 PA0
//     pin 5  P73  SSTAT1   in,  from IC2 PA1
//     pin 6  P74  LCDOFF   out
//     pin 7  P75  MUTE     out
//     pins 8, 9  P76, P77  no net -- unconnected on the sheet
//
// P7CR = 0x33 (0xF826CA) makes exactly bits 0, 1, 4 and 5 outputs, which is the
// four named output pins and nothing else.
// port_r<PORT_7>() returns the callback's value verbatim - it does not merge in
// the output latch - and `res 0,(P7)` is a read-modify-write, so this has to
// hand back the driven bits too or the first bit instruction would clear them.
uint8_t wsa1_state::cpu1_p7_r()
{
	uint8_t data = (m_cpu1_p7 & 0x33) | 0xc0;   // bits 6-7: P76/P77, no net, read high

	data |= BIT(m_cpu2_pa, 0) << 2;             // SSTAT0, CPU 2's strobe
	data |= BIT(m_cpu2_pa, 1) << 3;             // SSTAT1, CPU 2's receiver-busy

	return data;
}

void wsa1_state::cpu1_p7_w(uint8_t data)
{
	// Bit 4 is LCDOFF and bit 5 is MUTE (see the pin table above), and
	// NMI_PowerFail_SaveAndHalt (0xF8306E) sets both as its first act - blank
	// the panel and mute the audio on power fail.  Neither is modelled: there is
	// no audio to mute, and blanking the SED1330 from outside its own registers
	// would need the LCD module's own enable, which is not on this sheet.  They
	// are stored so the debugger can see them.
	m_cpu1_p7 = data;
}

// CPU 2's PORT A is the other end of the same four nets (IC2, sheet II-9/II-10):
// pin 32 PA0 = SSTAT0 out through R162 1K, pin 33 PA1 = SSTAT1 out through
// R163 1K, pin 34 PA2 = MSTAT0 in, pin 35 PA3 = MSTAT1 in.
// PACR = 0x03 (0xFFF02C) makes bits 0 and 1 outputs, which is those two nets.
// Port A's write path is
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

	data |= BIT(m_cpu1_p7, 0) << 2;             // MSTAT0, CPU 1's strobe
	data |= BIT(m_cpu1_p7, 1) << 3;             // MSTAT1, CPU 1's receiver-busy

	return data;
}

void wsa1_state::cpu2_pa_w(uint8_t data)
{
	m_cpu2_pa = data;
}


/*  CPU 2's PORTS, AND THE HOST BUS OF THE THREE DSPs

    ★ THE WHOLE PORT SIDE OF IC2 IS NAMED ON THE SCHEMATIC (sheet II-9/II-10,
    manual page 20, plus the three DSPs on sheet II-15/II-16, page 23).  Every
    net below was read off those two sheets on 2026-09-03; re-render them with
    notes/wsa1-probes/wsa1_sch_cpu_ports.sh.

        IC2 pin  port  net        IC2 pin  port  net
        -------  ----  ---------  -------  ----  --------------------------
         2- 9    P70-7 DSPD0-7      37     PB1   DSP2RST2
        32       PA0   SSTAT0       38     PB2   DSPRST
        33       PA1   SSTAT1       39     PB3   DSP0RST2
        34       PA2   MSTAT0       40     PB4   DSP1RST2
        35       PA3   MSTAT1       41     PB5   DSPWR
        36       INT4  KBEVNT       42     PB6   DSPRD
        11-13    TXD0/RXD0/P82      43     INT0  IFINT
                 MIDI2OUT/IN/SNS    23     P93   DSPRDY
        91       P53   DSPCD        64     P27   DSP2CS   (R189 1K pull-up)
        92       P54   DSP0CS       93     P55   DSP1CS   (R167/R179 1K)

    ★ THAT IS THE P7 EFFECT-MICROCODE TRANSPORT, PIN BY PIN.  prom_c drives a
    byte to the DSPs as `ld (P7),byte` with P5 bit 3 low for a command byte and
    high for data, one of P5.4 / P5.5 / P2.7 pulsed as the strobe for
    destination 0 / 1 / 2, PB bit 5 pulsed around the byte, and P9 bit 3 polled
    twice per byte with a 0x1F40 bound (the sequence is quoted in
    wsa1-roms-disasm/notes/FINDINGS-prom_c-p7-group-and-naming.md sec. 0).
    Each D6383GF-3BA takes /CS from its own DSPnCS, C/D from the shared DSPCD,
    /WRITE from DSPWR, /READ from DSPRD, D0-D7 from DSPD0-DSPD7, RDY out on the
    shared DSPRDY, /RST from the shared DSPRST and /RST2 from its own DSPnRST2:

        destination 0  ->  IC6   DSP0CS = P5.4, DSP0RST2 = PB3
        destination 1  ->  IC5   DSP1CS = P5.5, DSP1RST2 = PB4
        destination 2  ->  IC30  DSP2CS = P2.7, DSP2RST2 = PB1

    so the firmware's three destinations are the parts list's three DSPs and the
    numbering matches the net names.  (⚠ P5.4 against P5.5: the two nets cross
    other lines between the label row and IC2's pins 91-93 on this scan.  What
    is unambiguous is that the pair lands on P54/P55; DSP0CS on the lower bit is
    the reading the firmware's own destination index agrees with.)  None of the
    three DSPs is emulated - the part has no MAME device - so a byte written to
    P7 reaches the port latch and nothing else, which is why DSPRDY's idle level
    below is what makes the upload finish at all.

    ⚠ INT4 IS THE KEYBED'S EVENT LINE, NOT MODELLED.  KBEVNT leaves IC4, the
    tone generator LSI, and arrives on IC2 pin 36.  prom_c's INT4 vector is a
    bare RETI at 0xF995C2, so the interrupt exists to wake the processor and
    the event is then read through the polled status port at 0x108002, which is
    what this driver models.  Raising it would change when CPU 2 runs and
    nothing else; the sheet does not give the pulse shape, so it is not raised.

    Service manual page 20 (MAIN (A)/MB2 P.C. Diagram, sheet II-9/10), IC2
    TMP95C061AF "MICROCOMPUTER (SUB)", left pin column, read 2026-08-27:

        pin 18  VREF   <- +5D through R38 220
        pin 19  VCC    <- +5D
        pin 20  AN0    <- +5D          (same node as pin 19; junction dots on both)
        pin 21  AN1    <- JOYX through R180 1K, 0.1 uF to ground
        pin 22  AN2    <- JOYY through R181 1K, 0.1 uF to ground
        pin 23  P93    <- net DSPRDY, R79 4.7K UP to the VREF node, 0.22 uF to ground

    and pins 2-9 of the same chip are P70-P77 carrying DSPD0-DSPD7.  Re-crop it
    with notes/wsa1-probes/wsa1_sch_dsprdy.sh, which prints the two commands and
    the coordinates.  DSPRDY is the RDY output of all three DSPs, wired together
    (sheet II-15/II-16), which is why it is a pulled-up net and not a driven
    one.

    So P9 bit 3 is a PULLED-UP net whose only other drivers are the three
    (undumped, unemulated) uPD6383GF DSPs, and P9 bit 0 is an analog input
    STRAPPED to +5D.
    Both idle HIGH on the board.  MAME's unbound port read returns 0, which is
    not "no information" -- it is the WRONG LEVEL, and the firmware notices:

      * P9 bit 3 is polled at EIGHTEEN sites in prom_c, all of the shape
        `ld C,(0x19) / and C,0x08 / srl 3,C / cp C,0` inside the DSP microcode
        upload (0xF9A19F 0xF9A1DD 0xF9A219 0xF9A257 0xF9A293 0xF9A2D1 0xF9A347
        0xF9A382 0xF9A3BB 0xF9A3F6 0xF9A42F 0xF9A46A 0xF9A4DD 0xF9A518 0xF9A551
        0xF9A58C 0xF9A5C5 0xF9A600 -- census in wsa1_sch_dsprdy.sh).  Each poll
        is bounded by 0x1F40 = 8000 iterations and sets the firmware's timeout
        flag at (0x00F35C) when it expires.  Reading 0 made EVERY poll of EVERY
        byte burn the full bound.
      * P9 bit 0 is read once, `bit 0,(0x19)` at prom_c 0xFB050B, and picks
        between `and (0x14FF),0xFFFB` (bit set) and `or (0x14FF),0x0004` (bit
        clear).  prom_a, prom_b and prom_d contain no read of SFR 0x19 at all.

    WHAT IT COST, and this is the measurement that found it
    (notes/wsa1-probes/wsa1_cpu2_timeline.lua, 80 s boot, PC sampled per frame):
    CPU 2's program counter never left 0xF9A347-0xF9A490 -- the upload's timeout
    loops -- for the whole boot.  Its main loop therefore never ran, and the one
    sound-name request CPU 1 posts (t = 6.876, `05 80 00 04 00 00 00` on link
    stream 0, every byte of it read by CPU 2) was never answered: CPU 1 polled
    ring 0x604800 65535 times, got nothing, and prom_a 0xFC1BAE substituted the
    string "Sound Name *****".  See the SOUND NAME block comment below.

    ⚠ BITS 1 AND 2 ARE ANALOG AND ARE NOT MODELLED.  They are the joystick's two
    axes through a 1K/0.1uF network; no firmware in this set reads them as
    digital bits, so returning 0 for them asserts nothing.  Port 9 is four bits
    wide on this part.  */
uint8_t wsa1_state::cpu2_p9_r()
{
	return 0x09;   // bit 0 = AN0 strapped to +5D; bit 3 = DSPRDY, R79 pull-up
}


/***************************************************************************

    ★ THE SOUND NAME -- the whole chain, and the one thing that broke it

    SYMPTOM (fixed 2026-08-27): the SOUND MODE screen printed `Sound Name
    *****` where a voice name belongs, with `R1- 001` beside it -- so a sound
    was selected and only its name was missing.

    THE STRING IS THE FIRMWARE'S OWN FALLBACK, not corruption.  prom_a
    0xFC1C49 holds sixteen bytes "Sound Name *****" (and 0xFC1CC1 holds "Combi
    Name *****"), and exactly one instruction reaches it:

        sub_FC1B81 (prom_a):
          0xFC1B8E  ld XIY,0x00000800        the request/answer buffer
          0xFC1B93  call sub_FC1BB9          build {0x80, W, 0x04, A, 0, 0} and
                                             post it on link stream 0
          0xFC1B97  ld DE,0x11 ; ld C,0x00   17 bytes expected
          0xFC1B9C  call sub_FC1BDC          collect the answer
          0xFC1BA6  cp XIY,0xffffffff
          0xFC1BAE  ld XIY,0x00fc1c49  <---- THE FALLBACK

    sub_FC1BDC reads the answer a byte at a time through Ring60480A_Get (prom_b
    slot T_F41CF4 -> prom_a 0xF84382, ring at 0x604800), first re-syncing on the
    six request bytes coming back (`cp (XIX),A` at 0xFC1BF5) and then copying 17
    bytes to 0x000810.  sub_FC1C29 gives up after 0xFFFF empty polls and leaves
    XIY = -1.

    WHAT WAS MEASURED, and where it stopped
    (notes/wsa1-probes/wsa1_soundname_path.lua and wsa1_name_request_window.lua,
    110 s boot, before the fix):

        t = 6.876   the six request bytes are written to 0x000800
        t = 6.876   `05 80 00 04 00 00 00` crosses the wire; CPU 2 reads the
                    header at prom_c 0xF99BD5 and its micro-DMA absorbs the
                    other six -- so THE REQUEST ARRIVES, in full
        t = 6.876 .. 7.576   CPU 1 polls ring 0x604800.  262140 reads, which is
                    4 x 65535, and ZERO writes: nothing is ever put in it
        t = 7.576   the fallback string is fetched, pc = 0xF8F20F (SWI7 text)
        t = 70.88   CPU 2's FIRST transmission of the entire boot

    So the link was not the blocker -- by then it carried 5080 bytes one way and
    719 the other without loss.  CPU 2 simply never ran the code that answers.
    notes/wsa1-probes/wsa1_cpu2_timeline.lua says why in one line: CPU 2's
    program counter never left 0xF9A347-0xF9A490 for the whole 80 s sample.
    That range is six copies of the DSP microcode upload's per-byte handshake,
    each `ld C,(0x19) / and C,0x08` polling DSPRDY with a 0x1F40 = 8000
    iteration bound -- and P9 was unbound, so every poll read 0 and burned the
    whole bound.  cpu2_p9_r() above is the fix and carries the schematic.

    THE A/B, same binary, no rebuild (notes/wsa1-probes/wsa1_p9_control.lua
    masks bits 0 and 3 back off with a read tap, which is what an unbound port
    used to give; ⚠ it needs -autoboot_delay 0, because with the fix in place
    the upload is already finished by t = 1 s):

        control (P9 forced to 0)   ring 0x604800  262140 r / 138 w   name buffer
                                   untouched, t=95 screenshot byte-identical to
                                   screens/wsa1r_udma3fix_t95_sound_mode.png
        fixed                      ring 0x604800     322 r / 117 w   0x000810
                                   receives "     Piano      " and the screen
                                   prints `Piano`
                                   (screens/wsa1r_p9fix_t95_sound_mode.png)

    ⚠ THE KEYBED WAS ALREADY FIXED BEFORE THIS, and the same control proves it:
    with P9 masked back to 0, a C4 press still crosses as `A2 90 3C 3C` and CPU
    1 still answers `03 90 00 3C 3C` (notes/wsa1-probes/wsa1_keybed_note.lua).
    The note path was cured by OVERLAY FIX 6 and the burst quantum, not by this.

***************************************************************************/


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
    holding the clock down".  ★ AND THE PIN IS NOW NAMED: IC1 pin 16, SCLK1,
    through R31 220 into CN3 and the panel's CN1, where the M37471M2196S's CLK
    (CP1 board, sheet II-29/II-30) is the other end -- so it really is a clock
    line both ends can drive, not an input of this processor's alone.  P83 and
    P84, IC1 pins 14 and 15, are TXD1 and RXD1 on the same connector.
    ⚠ THAT THE IDLE STATE IS HIGH IS STILL AN INFERENCE: no pull-up is drawn on
    SCLK1 on either sheet at the resolution rendered here, and no databook is at
    hand.  What is NOT an inference is that 0 is not a neutral default -- MAME's
    unbound read gave 0, and with 0 every single frame took the abort path at
    0xF5AD0E.  Measured, before and after:
    notes/wsa1-probes/wsa1_sc1_handshake.lua.

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

    ★ THE WHOLE PORT SIDE OF THIS DEVICE IS NAMED ON THE SCHEMATIC, and every
    line the firmware argument below reached is on it.  IC1's bottom pin row
    (sheet II-7/II-8, manual page 19; re-render with
    notes/wsa1-probes/wsa1_sch_cpu_ports.sh):

        pin 32  PA0    grounded            pin 38  PB2    FDRST
        pin 33  PA1    FS1   (R151 0R)     pin 39  PB3    FDTC
        pin 34  PA2    FS2   (R152 0R)     pin 40  INT6   tied to +5D
        pin 35  PA3    FDMON (R153 0R)     pin 41  INT7   FDDRQ
        pin 36  INT4   HDINT               pin 42  PB6    HDIORDY
        pin 37  INT5   FDINT               pin 43  INT0   SIFINT

    So intrq -> INT5 and drq -> INT7, which is how they are wired in the machine
    configuration; PB bit 3 is FDTC; the three PA output bits PACR = 0x0E makes
    are the three FDD control lines; and INT4/PB6 are the hard disk's, not this
    device's.  The INT4 trap in the vector table is therefore the hard disk's
    interrupt going nowhere.

    ⚠ THE ONE INFERENCE THAT REMAINS: PB BIT 3 IS TC.  The net is FDTC, so the
    pin's ROLE is now read rather than deduced; what a schematic net name does
    not give is the controller pin it lands on, and the argument for TC is
    unchanged.
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
    Nothing here fabricates a status byte either way.

    CPU 1's PA BIT 3 IS THE DRIVE MOTOR, active low -- wired in cpu1_pa_w(),
    and no longer an inference: the net FDMON reaches the FDD connector's MOT
    pin through Q10 and Q9, and the controller's own ME0-ME3 outputs are not
    connected.  The block comment on the handler traces it.  This paragraph
    used to say the opposite, so the reasoning that changed is worth keeping.

    The old refusal rested on operations 6 and 7 (0xFE65EF, 0xFE661F): op 7 SETS
    the bit and op 6 clears it and waits 5 ticks, so the asserted direction
    looked like HIGH -- and a pin that RESET leaves high (`ldio PA,0xF9` at
    0xF826D6, `ldio PACR,0x0E` at 0xF826DC making bits 1-3 outputs) is the wrong
    way round for an active-high enable.  That objection was sound on the
    evidence it had.

    A writer census over both CPU 1 images then found TWO MORE WRITERS
    (notes/prom_a_pa3_census.py in the disassembly tree, 19 checks):
    Disk_PortA3_ClearAndSettle (0xFE18E9) does `res 3,(PA)` then Delay_150Ticks,
    and Disk_PortA3_Release (0xFE18F7) does `set 3,(PA)` with no wait, across 15
    calr sites -- asserting at routine heads before disk requests, releasing on
    exit paths.  Only the CLEAR direction is ever followed by a wait, and 150
    ticks at this CPU's measured 488.28 Hz is 307 ms, which is a spin-up and not
    a select.  Read active-low, RESET-high means the motor is OFF at reset, and
    the old objection is answered rather than overruled.

    ⚠ WHAT IS STILL NOT ESTABLISHED here is only the drive's own behaviour:
    with a motor line that works, Fdc_WaitReadyForCommandByte (0xFE5A8F, the
    unbounded drain described below) is on a reachable path.

    ⚠ AND THIS MAKES A LATENT HANG REACHABLE.  With no motor the drive never
    became ready, so a read reported the firmware's own error 0x31 and stopped.
    A live drive lets the transfer proceed, which puts Fdc_WaitReadyForCommandByte
    (0xFE5A8F, the unbounded drain described below) on a reachable path for the
    first time.  If the machine wedges on a disk read rather than failing it,
    that drain is the first place to look, not this line.

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

// PB bit 3 -> TC.  The net is FDTC (IC1 pin 39); see the ⚠ paragraph above for
// what a net name does and does not settle.  PB bit 2 is FDRST and is NOT wired
// to the controller's reset: the sheet names the net but not its polarity, and
// getting that backwards would hold a working device in reset.
void wsa1_state::cpu1_pb_w(uint8_t data)
{
	if (BIT(data ^ m_cpu1_pb, 3))
		LOGMASKED(LOG_FDC, "%s: fdc TC %d\n", machine().describe_context(), BIT(data, 3));

	m_cpu1_pb = data;
	m_fdc->tc_w(BIT(data, 3));
}

// PACR = 0x0E (0xF826DC): PA bits 1, 2 and 3 are outputs, and the latch RESET
// writes is 0xF9 (0xF826D6), so bit 3 starts HIGH.  The schematic names all
// three: PA1 = FS1, PA2 = FS2, PA3 = FDMON, each through a 0 ohm link, and PA0
// is grounded.  Bit 3 is the floppy module's only output outside its two device
// windows (operations 6 and 7 are its only writers, prom_a 0xFE65EF /
// 0xFE661F).  ⚠ WHAT FS1 AND FS2 SELECT IS NOT ESTABLISHED: drive select on the
// FDD side is IC8's own DS0 pin, so they are not that, and no writer of either
// bit has been located in prom_a or prom_b.  They are logged.
void wsa1_state::cpu1_pa_w(uint8_t data)
{
	if ((data ^ m_cpu1_pa) & 0x0e)
		LOGMASKED(LOG_FDC, "%s: CPU 1 PA <- 0x%02X (bit 3 = %d)\n",
			machine().describe_context(), data, BIT(data, 3));

	// Bit 3 drives the drive motor, through two transistors, onto the FDD
	// connector's MOT pin.  mon_w takes 0 = motor on and the line is active
	// low, so the bit goes straight through with no inversion.
	//
	// ★ SETTLED BY THE SCHEMATIC, END TO END.  The net is FDMON (IC1 pin 35,
	// sheet II-7/II-8).  On sheet II-9/II-10 it drives the base divider
	// R57/R58 of Q10, a 2SB709AR, whose collector drives Q9, a 2SD601AQ,
	// through R59/R60; Q9's collector, with R61 10K pulling it up to +5D, is
	// CN6 pin 3, and CN6 is the FDD connector -- 1 INDEX, 2 DS0, 3 MOT, 4 DIR,
	// 5 STP, 6 WDT, 7 WE, 8 TRKO, 9 WPRT, 10 RDT, 11 SIDE, 12 DCH.  Two
	// inverting stages, so FDMON LOW turns MOT on, which is the active-low
	// sense this handler already uses.  IC8's own motor-enable outputs ME0-ME3
	// carry no net at all, so the controller is not what spins the drive.
	// The reasoning that got here without the sheet is kept: a
	// writer census over both CPU 1 images (that tree's notes/prom_a_pa3_census.py,
	// 19 checks): bit 3 is the ONLY bit of PA the firmware changes after reset,
	// and it has four writers, not the two this driver used to know.  The two
	// new ones decide the polarity:
	//     Disk_PortA3_ClearAndSettle 0xFE18E9   res 3,(PA) then Delay_150Ticks
	//     Disk_PortA3_Release        0xFE18F7   set 3,(PA), no wait at all
	// 15 calr sites, asserting at routine heads before disk requests and
	// releasing on exit paths.  Only the CLEAR direction is followed by a wait,
	// and 150 ticks at CPU 1's measured 488.28 Hz is 307 ms -- a spin-up, not a
	// select, which would need no settle at all.  That also answers the
	// objection this driver used to carry: RESET leaving the pin HIGH is the
	// wrong way round for an active-HIGH enable, and exactly right for an
	// active-LOW one -- high at reset means the motor is off.
	if (BIT(data ^ m_cpu1_pa, 3))
		if (floppy_image_device *floppy = m_floppy->get_device())
			floppy->mon_w(BIT(data, 3));

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
	// MIDI START (0xFA) or CONTINUE (0xFB) on link channel 6.  (0xFB is
	// CONTINUE; Stop is 0xFC, which this firmware does not send here.  The
	// three literals sit together at prom_c 0xFCC5C2-C4 and read FF FA FB, so
	// the same block also carries 0xFF SYSTEM RESET, sent on the
	// active-sensing timeout.)  WHAT IT IS WIRED TO
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

/***************************************************************************

    0x0010C000 -- THE PER-CHANNEL REGISTER DECODE, AND WHERE EACH NAME COMES FROM

    Dev10C_WriteAllChanRegs (prom_c 0xFB713A) issues 23 register writes to ONE
    channel out of a 0x2C-byte staging struct at CPU 2 work RAM 0x00D75E.  The
    numbers matter and are measured, not paraphrased
    (notes/wsa1-gapA-audit-probes/gapA_listing_checks.py, checks 1a-1d):

      * 22 DISTINCT registers, numbered block * 0x40 + channel;
      * 23 writes, because block 0x0080 is written twice (gate in, gate out);
      * 21 staging WORDS are read, at struct offsets 0x02..0x2A.  Struct word 0
        is never read: block 0 is written with the literal 0x8100 out of the
        writer itself, at 0xFB7239.
      * the burst is NOT issued in ascending register order (check 1d).

    ⚠ THE THREE KINDS OF CLAIM BELOW ARE DELIBERATELY NOT FLATTENED.  Flattening
    them is exactly how a borrowed name turns into a fact about this machine.

      TG_LOCAL    the QUANTITY is established from the WSA1's own firmware.
      TG_SHAPE    this firmware fixes the FIELD SPLIT and nothing more -- a byte
                  pair, a payload width, a clamp bound.  True, and not a name.
      TG_SIBLING  there is no local statement of any kind and the label printed
                  is the KN5000's word.  Exactly ONE register is in this state.
      TG_NONE     no statement anywhere, in either firmware.

    Rows that carry a `sibling` string have a KN5000 name available with NO WSA1
    EVIDENCE BEHIND THE QUANTITY, and every log line says so in as many words.
    THE CORRESPONDENCE IS STRUCTURAL, NOT A CODE TRANSPLANT: the KN5000 sub-CPU's
    ToneGen_WriteVoiceParams stages THE SAME WORD-INDEX -> REGISTER MAP
    (kn5000-roms-disasm/v142/subcpu/kn5000_subprogram_v142.s:6938-6959), and the
    same file at :24686-24690 carries a second, independent witness --
    ToneGen_ProbeVoice_ParamBlock, which labels word 0 "TG reg 0x000" and words
    1..21 as 0x040..0xA40.  But of the bytes the counterpart routines share,
    19/20, 100/102 and 116/120 DIFFER, and the two machines do not even write the
    registers in the same ORDER (the KN5000's burst is ascending, this one is
    not).  Nothing was copied; a structure was recognised.

    Its calibration is FIVE agreements out of five, on the registers this image
    answers for itself: 0x0040's 4/12 split, 0x0080's level + 3-bit field + gate,
    0x0400's pitch, 0x0800's (curve << 8) | ramp packing at tone offset 0x28, and
    the 3-and-3 grouping of 0x0900-0x0A40.  No contradiction -- but these names
    are the ones a measurement on real hardware would overturn FIRST.

    (wsa1-roms-disasm/notes/FINDINGS-prom_c-dev10c-register-meanings.md,
     .../FINDINGS-prom_c-dev10c-sibling-register-map.md,
     .../FINDINGS-prom_c-dev10c-producers.md, .../FINDINGS-prom_c-voice-readback.md.
     Re-derived from ROM bytes by notes/wsa1-gapA-audit-probes/, 0 failures.)

***************************************************************************/

enum tg_grade : uint8_t { TG_LOCAL, TG_SHAPE, TG_SIBLING, TG_NONE };

// Printed on every write line, straight after the name, so that a single line
// out of a trace is self-describing.
static const char *const s_tg_grade_tag[] =
{
	" [WSA1]",              // the quantity is established in this machine's own firmware
	" [SPLIT ONLY]",        // the field split is measured; the quantity is not named
	" [KN5000 NAME ONLY]",  // no local statement at all
	" [UNKNOWN]"            // no statement in either firmware
};

struct tg_regdesc
{
	uint16_t    block;      // register number of channel 0
	int8_t      word;       // staging word that feeds it; -1 = not fed by the burst
	tg_grade    grade;      // grade of `name`
	const char *name;       // the label printed on every write
	const char *sibling;    // the KN5000's name, when one exists and is not `name`
};

static const tg_regdesc s_tg_chanreg[] =
{
	// block   word  grade       name (what THIS firmware supports)    KN5000-only name
	{ 0x0000,   -1, TG_SHAPE,   "lifecycle word",                     "control / gate" },
	{ 0x0040,    1, TG_LOCAL,   "key-zone word 0",                    "recording selector, (class << 12) | entry" },
	{ 0x0080,    2, TG_LOCAL,   "OUTPUT LEVEL + gate",                nullptr },
	{ 0x00c0,    3, TG_SIBLING, "coarse level + expression",          nullptr },
	{ 0x0100,    4, TG_SHAPE,   "7-bit value, clamp 36..120 (pair A)", "TVF cutoff" },
	{ 0x0140,    5, TG_SHAPE,   "7-bit value, clamp 36..120 (pair B)", "TVF depth / bias" },
	{ 0x0180,    6, TG_SHAPE,   "7-bit control",                      "pan, 0x0040 = centre" },
	{ 0x0400,    7, TG_LOCAL,   "PITCH",                              "absolute log pitch" },
	{ 0x0440,    8, TG_SHAPE,   "7-bit payload + 2-bit field",        nullptr },
	{ 0x0480,    9, TG_SHAPE,   "6-bit payload",                      nullptr },
	{ 0x04c0,   10, TG_SHAPE,   "base 0x4400 + 4-bit cfg + payload",  "oscillator config + slot" },
	{ 0x0500,   11, TG_SHAPE,   "two 7-bit bytes, low biased +0x7F",  "detune / bend pair" },
	// ⚠ 0x0800 is SHAPE, not LOCAL, and the reason is a trap worth naming: the two
	// tables it is built from, Voice_LevelPair_AttackCurve (0xFDEF74) and
	// Voice_EnvelopeRate_Table (0xFDF03E), carry KN5000 TRANSPLANTED LABELS
	// (wsa1-roms-disasm/notes/kn5000-label-transplant-generated.md, rows 0xFDEF74
	// and 0xFDF03E).  So "envelope", "level" and
	// "rate" are the sibling's words too, and calling this row `(level<<8)|rate`
	// with no tag would smuggle three borrowed names in under a local one.  What
	// IS local: a byte pair, high from a 101-entry descending curve, low from a
	// 101-entry monotone ramp indexed by tone offset 0x28.
	{ 0x0800,   12, TG_SHAPE,   "byte pair, (curve << 8) | ramp",     "amplitude envelope segment 0" },
	{ 0x0840,   13, TG_SHAPE,   "byte pair",                          "amplitude envelope segment 1" },
	{ 0x0880,   14, TG_SHAPE,   "byte pair",                          "amplitude envelope segment 2" },
	{ 0x08c0,   15, TG_SHAPE,   "byte pair, both detune-curve",       "amplitude envelope segment 3" },
	{ 0x0900,   16, TG_SHAPE,   "byte pair",                          "second envelope, segment 0" },
	{ 0x0940,   17, TG_SHAPE,   "byte pair",                          "second envelope, segment 1" },
	{ 0x0980,   18, TG_SHAPE,   "byte pair",                          "second envelope, segment 2" },
	{ 0x09c0,   19, TG_SHAPE,   "byte pair",                          "third envelope, segment 0" },
	{ 0x0a00,   20, TG_SHAPE,   "byte pair",                          "third envelope, segment 1" },
	{ 0x0a40,   21, TG_SHAPE,   "byte pair",                          "third envelope, segment 2" },

	// NOT in the burst, but the same device and the same channel numbering: the
	// three parallel gate/value SLOTS the first accessor bank writes out of the
	// 0x44-byte struct at RAM 0x00D8DB (a DIFFERENT object from the 0x2C-byte
	// staging struct above), fields 0x38..0x42, each pulsed bit-15 1-then-0.
	// (FINDINGS-prom_c-tone-generator.md sec.5.)  ⚠ 0x8100 is the strobe word on
	// three of these as well -- 0xFB7EFF, 0xFB7D13, 0xFB7E09, 0xFB80D6 -- which is
	// why the busy latch in tg_data_w() is gated on `latch < TG_VOICES` and not
	// on the value alone.
	{ 0x0540,   -1, TG_NONE,    "slot 1 gate",                        nullptr },
	{ 0x01c0,   -1, TG_NONE,    "slot 1 value",                       nullptr },
	{ 0x0580,   -1, TG_NONE,    "slot 2 gate",                        nullptr },
	{ 0x0600,   -1, TG_NONE,    "slot 2 value",                       nullptr },
	{ 0x05c0,   -1, TG_NONE,    "slot 3 gate",                        nullptr },
	{ 0x0640,   -1, TG_NONE,    "slot 3 value",                       nullptr }
};

static const tg_regdesc *tg_lookup(uint16_t reg)
{
	for (const tg_regdesc &d : s_tg_chanreg)
		if (d.block == (reg & 0xffc0))
			return &d;
	return nullptr;
}

// Decode one register's VALUE.  Every constant here has a ROM address behind it;
// nothing is invented to make a line read nicely, and where the firmware leaves
// a reading undecided BOTH readings are printed rather than one being picked.
static std::string tg_format_value(uint16_t reg, uint16_t value)
{
	switch (reg & 0xffc0)
	{
	case 0x0000:
		// The two lifecycle literals, and the third thing that lands here.
		return (value == 0x8100) ? "GATE (the 0x8100 literal, 0xFB7239)" :
			(value == 0x7e00) ? "FREE (the 0x7E00 literal, 0xFB0AB5)" :
			util::string_format("computed voicerec[+0x29] = 0x%04X -- NOT a lifecycle word", value);

	case 0x0040:
		// The firmware splits this 4 over 12 itself: Voice_SelectKeyZone_Reg0040's
		// fix-up `cp HL,0x6000 / jr NC` is at 0xFA8248 (NOT at 0xFA82F0 -- the
		// copy there has no 0x6000 in it at all and doubles the nibble
		// unconditionally; gapA_listing_checks.py 5a/5b).
		return util::string_format("top field %X, payload 0x%03X", value >> 12, value & 0x0fff);

	case 0x0080:
	{
		// Bits 11..0 = 2 * Voice_OutputLevel_Table[idx] (table at 0xFDDE2B).  The
		// closed form T[16e+m] = 128e + round(128*log2(1+m/16)) holds for ALL 256
		// entries (gapA_rom_checks.py 1a, 0 mismatches), so the field is a base-2
		// LOGARITHM with 256 counts per octave and a full span of 0x0FF4 counts.
		//
		// ⚠ NO SIGN AND NO REFERENCE ARE ASSERTED.  Whether the chip reads this
		// as a level or as an attenuation at the pin is NOT established -- the
		// same doubt the finding raises for 0x0800's descending curve applies
		// here, one register earlier.  So a DISTANCE from the table's top value
		// is printed, which is sign-free, and no decibel figure with a sign is
		// emitted for anyone to believe.
		const unsigned lvl = value & 0x0fff;
		return util::string_format(
			"gate %d, level field 0x%03X = %.3f octaves from the table's top (0x0FF4);"
			" 256 counts/octave, SENSE AT THE PIN NOT ESTABLISHED; 3-bit field %u",
			BIT(value, 15), lvl, (0x0ff4 - double(lvl)) / 256.0, (value >> 12) & 7);
	}

	case 0x0100:
	case 0x0140:
	{
		// (voice_word & 0xFF80) | Clamp_36_to_120(...); the clamp's only two
		// immediates are 0x78 and 0x24 (0xFA76B2), and all eight of that
		// routine's callers are on this path.
		//
		// ⚠ 36..120 IS A PROPERTY OF THAT PRODUCER, NOT OF THE REGISTER.  The boot
		// burst reaches these two registers with a staging struct the producer
		// never touched, and 0x7C = 124 duly turns up on channel 0 at t = 0.  So
		// the range is printed as a CHECK that can fail, not as a description --
		// a value outside it is real information, and asserting the clamp would
		// have buried it.
		const unsigned v = value & 0x007f;
		return util::string_format("7-bit value %u%s, bits 15..7 pass through as 0x%04X",
			v, (v < 36 || v > 120) ? "  <- OUTSIDE the producer's 36..120 clamp" : " (within the producer's 36..120 clamp)",
			value & 0xff80);
	}

	case 0x0180:
		// Write side.  ⚠ The READ at this block is a DIFFERENT quantity -- see
		// tg_status_r().  0x80 on the write side means "choose at random"
		// (Rand_FromTickSquared, 0xFA978F / 0xFA9EDF), so two identical note-ons
		// legitimately differ here: never treat a change in this register as a
		// response to a stimulus without a no-stimulus control first.
		return util::string_format("%u of 0..127%s", value & 0x007f,
			(value & 0xff80) ? ", plus high-byte flags" : "");

	case 0x0400:
		// Seeded note*256 + 0x80 at 0xFA7F3A-0xFA7F48 and saturated to 0..0x7FFF.
		// ⚠ THE HALF-STEP DATUM IS NOT ESTABLISHED: whether the device reads the
		// field as value/256 or as (value-128)/256 turns on the seed's +0x80 being
		// an offset or a rounding bias, and no instruction in prom_c settles it.
		// Both are printed; neither is chosen.
		return util::string_format("%.3f semitones (or %.3f if the seed's +0x80 is a rounding bias)",
			value / 256.0, (int(value) - 128) / 256.0);

	case 0x0440:
		// sub_FA9915 has two arms: (record[+0x1E] & 0x00C0) | (v & 0x7F) at
		// 0xFA99F0, and sub_FB5E39(...,1) | (v & 0x7F) at 0xFA9B23.  ⚠ The 0x00C0
		// field and the 7-bit payload OVERLAP AT BIT 6, so bit 6 is printed in
		// both places on purpose.  ⚠ The routine ZEROES words 8 and 9 first
		// (0xFA991C / 0xFA9923), so 0x0000 here means "no arm fired", not "0".
		return util::string_format("%spayload bits 6..0 = %u; bits 7..6 = %u (arm 1's 0x00C0 field, OVERLAPS at bit 6); rest 0x%04X",
			value ? "" : "no arm fired -- ", value & 0x007f, (value >> 6) & 3, value & 0xff00);

	case 0x0480:
		// sub_FB5E39(...,0) | (v & 0x3F) at 0xFA9B90.  The SAME routine feeds
		// 0x0440; the two call sites differ in exactly one pushed immediate,
		// 1 versus 0 -- so that immediate, not two separate producers, is what
		// discriminates these two registers.  (sub_FA78E8, which an earlier
		// reading credited with 0x0440's high half, is a memset and returns
		// nothing: it stores 0 into offsets 0..5 and 7 and push/pops both HL and
		// DE.  gapA_listing_checks.py check 4.)
		return util::string_format("%spayload %u (6 bits), high half 0x%04X",
			value ? "" : "no arm fired -- ", value & 0x003f, value & 0xffc0);

	case 0x04c0:
		// sub_FA9F19 seeds the word with the literal 0x4400 (0xFA9F20) and ORs in
		// (record_word[+0x22] & 0x3300) | (v & 0x7F) at 0xFA9FE5-0xFA9FEE.  ⚠ That
		// record is (voice[+0x25])'s, NOT the tone record (voice[+0x17]) --
		// 0xFA9F32 `ld IY,(XBC+0x25)`.  The same routine uses the low two bits of
		// the same word as a FOUR-WAY selector (0xFA9F48), and its sibling field
		// +0x1E has the identical shape on the 0x0440 path (0xFA9951-0xFA9967).
		return util::string_format("%s, cfg %X, payload %u",
			((value & 0x4400) == 0x4400) ? "base 0x4400 present" : "base 0x4400 ABSENT",
			((value >> 12) & 3) << 2 | ((value >> 8) & 3), value & 0x007f);

	case 0x0500:
		// hi = Clamp(sub_FA75BA(...) + DetuneCurve_LookupUNSIGNED(|tone[+0x07]|)),
		// lo = Clamp(sub_FA75BA(...) + 0x7F); packed `sll 8 / or` at
		// 0xFA96AB-0xFA96B0 and stored to word 11 at 0xFA96B0.  ★ The wrapper is
		// the UNSIGNED one (0xFA7654), not the signed one: BOTH results of
		// DetuneCurve_LookupSIGNED (0xFA7602) are packed at 0xFA96BC-0xFA96C1 and
		// stored to word 15 = register 0x08C0 at 0xFA96C3.  The evidence tree's
		// own sibling-map note has these two swapped; it is corrected here and
		// re-derived by gapA_listing_checks.py check 4 (HL survives both callees).
		return util::string_format("hi %u, lo %u (both 7-bit; lo is centred on 0x7F)",
			(value >> 8) & 0x7f, value & 0x7f);

	case 0x0800:
		// High byte from the 101-entry descending curve at 0xFDEF74 (0xFF..0x09),
		// low byte from the 101-entry monotone ramp at 0xFDF03E (0x00..0x7F)
		// indexed by tone[+0x28]; packed at 0xFAA640-0xFAA649.  Both table NAMES
		// are KN5000 transplants, so "level" and "rate" are not printed here.
		return util::string_format("curve 0x%02X, ramp 0x%02X%s", value >> 8, value & 0xff,
			(value == 0xff80) ? "  [the quiescent pair Dev10C_ResetAllChannels writes, 0xFB8132]" : "");

	case 0x0840:
		return util::string_format("hi 0x%02X, lo 0x%02X%s", value >> 8, value & 0xff,
			(value == 0xff00) ? "  [the quiescent pair Dev10C_ResetAllChannels writes, 0xFB811E]" : "");

	case 0x0880: case 0x08c0: case 0x0900: case 0x0940:
	case 0x0980: case 0x09c0: case 0x0a00: case 0x0a40:
		// Every one of the ten registers fed by staging words 12..21 is assembled
		// as two 8-bit fields: 22 computed stores over those words, two idioms,
		// no third (gapA_listing_checks.py 3a).
		return util::string_format("hi 0x%02X, lo 0x%02X", value >> 8, value & 0xff);

	default:
		return util::string_format("0x%04X", value);
	}
}

// Printed once at machine_start, so that a captured trace carries its own legend
// and nobody has to open the notes to tell a local name from a borrowed one.
void wsa1_state::tg_log_legend()
{
	LOGMASKED(LOG_TG, "tg: 0x0010C000 per-channel registers.  register = block * 0x40 + channel.\n");
	LOGMASKED(LOG_TG, "tg:   [WSA1]            the quantity is established in THIS machine's firmware\n");
	LOGMASKED(LOG_TG, "tg:   [SPLIT ONLY]      the field split is measured here; the quantity is not named\n");
	LOGMASKED(LOG_TG, "tg:   [KN5000 NAME ONLY] no local statement of any kind\n");
	LOGMASKED(LOG_TG, "tg:   [UNKNOWN]         no statement in either firmware\n");
	LOGMASKED(LOG_TG, "tg:   a `KN5000-only:` name has NO WSA1 EVIDENCE behind the quantity.\n");
	LOGMASKED(LOG_TG, "tg:   0x0800's two source tables are themselves KN5000-transplanted labels,\n");
	LOGMASKED(LOG_TG, "tg:   so 'envelope', 'level' and 'rate' are borrowed words there as well.\n");
	for (const tg_regdesc &d : s_tg_chanreg)
	{
		char w[4];
		if (d.word < 0) { w[0] = ' '; w[1] = '-'; w[2] = 0; }
		else            snprintf(w, sizeof(w), "%2d", d.word);
		LOGMASKED(LOG_TG, "tg:   0x%04X  word %s  %-38s%s%s%s\n",
			d.block, w, d.name, s_tg_grade_tag[d.grade],
			d.sibling ? "   KN5000-only: " : "", d.sibling ? d.sibling : "");
	}
}

// One channel's 22 registers, as they stand right now.  See the caller for why
// the trigger this hangs off is NOT "the parameters are complete".
void wsa1_state::tg_dump_channel(unsigned chan)
{
	LOGMASKED(LOG_TGVOICE, "tg: ---- channel %2u, the 22 burst registers as they stand ----\n", chan);
	for (const tg_regdesc &d : s_tg_chanreg)
	{
		if (d.word < 0)
			continue;
		const uint16_t v = m_tg_regs[d.block + chan];
		LOGMASKED(LOG_TGVOICE, "tg:   0x%04X %-38s = 0x%04X  %s%s\n",
			d.block + chan, d.name, v, tg_format_value(d.block, v).c_str(), s_tg_grade_tag[d.grade]);
	}
}

void wsa1_state::tg_data_w(uint16_t data)
{
	// Register number = (block << 6) | channel, 64 channels - the same field split
	// MAME's KN5000 tone generator uses.  The identification of this port as the
	// same part as the KN5000's IC303 rests on five agreements with that
	// device's firmware, not on the parts list alone: the 64-channel boot reset at
	// 0xFA6690 writes the same four blocks with the same iteration count and two
	// byte-identical values (block 0x0C0 <- 0x0000, block 0x000 <- 0x7E00, the
	// KN5000's "voice free"); the damp pair 0xA200/0xA280 appears on the same
	// two blocks (0xFAC275, 0xFAC298); the +4 read-back has the same shape as
	// the KN5000's AUDIO_HW_WRITE_READ; and two upper-block bursts (0xFACE67,
	// 0xFACEA2) match the KN5000 note-on burst in BOTH register number and
	// parameter-block word offset.  It is still an identification by twin: a
	// register whose value was not compared could differ.
	if (m_tg_latch < TG_REG_COUNT)
		m_tg_regs[m_tg_latch] = data;

	// ⚠ THE GLOBAL TEST HAS TO COME FIRST, and this is a defect the decode exposed:
	// Dev10C_WriteGlobalRegs (0xFB7715) writes 0x0200-0x0205, and 0x0200 is INSIDE
	// the per-channel range (it would read as block 8, channels 0..5).  Block 8 is
	// not one of the burst's 22, so the old ordering printed six global writes per
	// boot as "a block NO converted routine is known to write" -- which is exactly
	// backwards: the routine that writes them is named, and it takes no channel.
	const bool is_global = ((m_tg_latch >= 0x0200) && (m_tg_latch <= 0x0205))
		|| ((m_tg_latch >= 0x0c00) && (m_tg_latch <= 0x0c05))
		|| (m_tg_latch == 0x0e00);

	if (!is_global && (m_tg_latch <= TG_CHAN_REG_TOP))
	{
		const unsigned    chan = m_tg_latch & 0x3f;
		const tg_regdesc *d    = tg_lookup(m_tg_latch);

		if (d)
			LOGMASKED(LOG_TG, "tg: ch %2u  reg 0x%04X word %s  %s%s%s%s = 0x%04X  %s\n",
				chan, m_tg_latch,
				(d->word < 0) ? " -" : util::string_format("%2d", d->word).c_str(),
				d->name, s_tg_grade_tag[d->grade],
				d->sibling ? "  KN5000-only: " : "", d->sibling ? d->sibling : "",
				data, tg_format_value(m_tg_latch, data).c_str());
		else
			LOGMASKED(LOG_TG, "tg: ch %2u  reg 0x%04X (block 0x%03X) = 0x%04X"
				"  -- a block NO converted routine is known to write\n",
				chan, m_tg_latch, m_tg_latch >> 6, data);

		// Placeholder-sine parameters: push the registers the sine backend uses as
		// they are written, so a voice that gates later already has them -- PITCH
		// (chan+0x0400, 1/256 semitone), OUTPUT LEVEL (chan+0x0080, log amplitude),
		// and the two envelope-marker halves (chan+0x0800 / chan+0x0840) whose
		// quiescent pair marks the channel idle.
		switch (m_tg_latch & 0xffc0)
		{
		case 0x0400: m_tonegen->set_pitch(chan, data); break;
		case 0x0080: m_tonegen->set_level(chan, data); break;
		case 0x0800: m_tonegen->set_env0(chan, data);  break;
		case 0x0840: m_tonegen->set_env1(chan, data);  break;
		}

		// ---------------- THE BUSY LATCH: A MODEL, NOT A FINDING --------------
		//
		// Block 0 per channel is the lifecycle register, and two literals move
		// the latch that tg_status_r() answers block 0's READ out of:
		//
		//   0x8100  GATE   0xFB7239 (Dev10C_WriteAllChanRegs), 0xFB755E, 0xFB7663
		//   0x7E00  FREE   0xFA66C7 (VoiceSubsystem_Init), 0xFB0AB5
		//                  (Dev10C_ChanReset), 0xFB8211 (Dev10C_ResetAllChannels)
		//
		// Those two censuses are complete for prom_c: three `ld (Xrr),0x7E00`
		// sites and no `ld r16,0x7E00` anywhere (notes/wsa1-gapF-probes/, P2/P2b).
		//
		// ⚠ TYING THE READ TO THE WRITE IS THIS DRIVER'S MODEL.  The disassembly
		// note records block 0's read (select 0..3, per BANK) and its write
		// (select 0..0x3F, per CHANNEL) separately and deliberately declines to
		// argue from one to the other.  The warrant used here is the twin:
		// kn5000_tonegen.cpp:1010-1018 records, MEASURED on that machine's live
		// bus, that the same TC183C230002 accepts exactly two lifecycle commands
		// on register 0x0000 + chan -- 0x81xx GATE and 0x7E00 FREE -- and answers
		// block 0 out of the matching latch.  Three things weaken it and are
		// written down rather than smoothed over:
		//   (a) 0x8100 is the strobe word on FOUR register blocks in this ROM
		//       (0x0000 and the three slot gates 0x0540/0x0580/0x05C0), so it
		//       reads as a generic gate encoding.  Hence `latch < TG_VOICES`.
		//   (b) the KN5000 text says 0x81xx, a family; this firmware emits
		//       exactly 0x8100.  The agreement is one value wide.
		//   (c) block 0 ALSO receives a computed word, voicerec[+0x29], whose
		//       high byte is a shifted parameter -- DE = (p - 16) << 8 at
		//       0xFAA395-0xFAA39C, and IX << 9 / DE << 12 at 0xFAA499/0xFAA4AA --
		//       so 0x7E00 and 0x8100 are ARITHMETICALLY REACHABLE by a parameter
		//       combination.  That collision is bounded rather than dismissed:
		//       a spurious FREE puts that ONE channel back into the teardown the
		//       stub used to inflict on EVERY channel, and a spurious GATE only
		//       keeps a bit set that this model can never clear anyway.  The
		//       worst case is therefore the OLD behaviour on a subset, never
		//       something new -- but it is a value-dependent failure, and if a
		//       voice is ever seen to die on one particular sound, look here.
		//
		// Anything except these two values is a parameter and MUST NOT move the
		// latch.
		if (m_tg_latch < TG_VOICES)
		{
			const uint16_t bit = uint16_t(1u << (chan & 15));
			if (data == 0x8100)
				m_tg_busy[chan >> 4] |= bit;
			else if (data == 0x7e00)
				m_tg_busy[chan >> 4] &= uint16_t(~bit);

			// Placeholder-sine gate: block 0's lifecycle latch IS the voice's
			// note-on/off, so mirror the busy bit to the sine backend.
			m_tonegen->set_gate(chan, (m_tg_busy[chan >> 4] & bit) != 0);
		}

		// Block 0x0080 bit 15 is a gate the CPU pulses 1-then-0 around a
		// parameter update: set at 0xFB717E, cleared at 0xFB7307, then shadowed
		// to RAM 0x0000D85B + 2*chan at 0xFB7317-0xFB7322.
		//
		// ⚠ THE FALLING EDGE IS *NOT* "THIS CHANNEL'S PARAMETERS ARE COMPLETE",
		// and the dump below is labelled accordingly.  Inside one burst for
		// channel c, Dev10C_ChanMinus2_SetReg_0080_Bit15 runs twice (0xFB7148,
		// 0xFB714C) and its clear counterpart once (0xFB729D) on channel
		// (c - 2) & 0x3F; sub_FB6F2C does five sets then one clear; and
		// Dev10C_SetChanReg_0080_ClrBit15 (0xFB7038) writes a bare clear.  So
		// edges arrive mid-burst on OTHER channels.  describe_context() is
		// printed with each dump precisely so a reader can tell which writer
		// produced it instead of assuming.
		//
		// ⚠ WHAT THE PULSE DOES IS NOT ESTABLISHED -- "trigger", "latch" and
		// "key-on" all fit the shape and nothing here distinguishes them.
		if ((m_tg_latch & 0xffc0) == 0x0080)
		{
			const bool gate = BIT(data, 15);
			if (!gate && BIT(m_tg_gate, chan))
			{
				LOGMASKED(LOG_TGVOICE, "tg: %s: block 0x0080 gate FELL on channel %u"
					" (NOT necessarily the end of that channel's burst)\n",
					machine().describe_context(), chan);
				tg_dump_channel(chan);
			}
			m_tg_gate = (m_tg_gate & ~(uint64_t(1) << chan)) | (uint64_t(gate) << chan);
		}
	}
	else
	{
		// Dev10C_WriteGlobalRegs (0xFB7715) writes those thirteen as immediates and
		// takes no channel argument, so anything else up here is a register no
		// converted routine is known to write.
		LOGMASKED(LOG_TG, "tg: global reg 0x%04X = 0x%04X%s\n", m_tg_latch, data,
			is_global ? "" : " (NOT one of Dev10C_WriteGlobalRegs' thirteen)");
	}
}

uint16_t wsa1_state::tg_status_r()
{
	// Two queries reach this port, both out of Dev10C_PollBankAndRetire (prom_c
	// 0xFA68DC) -- the ONLY reader of 0x0010C000 in any of the four images: of
	// 102 immediate loads of that address, exactly one is followed by the +4
	// pointer step, at 0xFA68FC (notes/wsa1-gapF-probes/, P1).
	const uint16_t latch = m_tg_latch;

	// QUERY 1 -- select 0..3: the BUSY BITMAP of a bank of sixteen channels, bit
	// `chan & 15` of word `chan >> 4`.  Select at 0xFA6901, read at 0xFA690A.
	// The firmware then computes
	//     ended = 0x0087BF[bank] & ~(word | 0x0087C7[bank])
	// (0xFA6918-0xFA6931) and TEARS DOWN every channel in `ended`: ChanRec_Release
	// + Dev10C_ChanReset + 0xFA5CE9, at 0xFA6989-0xFA6998.  A set bit means "still
	// busy"; a bit that GOES AWAY is a note end.
	//
	// ★ IT HAS TO BE A LATCH, NOT A LEVEL TEST, and the firmware itself is what
	// says so: the allocator ARMS the teardown edge before the gate is even
	// written.  sub_FA6BB5's not-held arm sets the channel's bit in 0x0087BF
	// with `lda XBC,0x0087bf / add XBC,(XIZ+0xe3) / or (XBC),HL` at
	// 0xFA6D39-0xFA6D41.  So a model that answers "is it loud yet" reports 0 on
	// the first poll after the gate, while the attack is still ramping, and the
	// firmware retires the brand-new note.  The KN5000 firmware pre-arms
	// identically and kn5000_tonegen.cpp:1049-1054 gives that as its own reason.
	//
	// THE STUB THIS REPLACED WAS NOT NEUTRAL: answering 0 put every non-held
	// channel into `ended` on the first sweep after it was allocated, so every
	// voice was torn down within a few MAIN passes and a held voice died the
	// instant its hold bit cleared, with no release at all.
	if (latch < 4)
		return m_tg_busy[latch];

	// QUERY 2 -- select 0x0180 + chan: a per-channel MAGNITUDE.  Select at
	// 0xFA69AF, read at 0xFA69B1, then `and BC,0x3fff / srl 0x05,BC / ld E,C`
	// (0xFA69B6-0xFA69BD) keeps BITS 12..5 as an 8-bit field -- bit 13 is lost to
	// the truncation, not to the mask -- caches it in the channel record's +0x15
	// and only ever COMPARES it against 0x80.
	//
	// ⚠ CROSSING BELOW 0x80 DOES NOT RETIRE THE VOICE.  The retire path is the
	// bitmap difference above, alone.  Below 0x80, and only with the record's
	// flag bit 2 set (0xFA69D4), the record goes to sub_FA65BD -- a different
	// action, which clears flag bits 2 and 3, sets bit 1 and calls 0xFA62DA.
	//
	// The firmware uses this read as a PREDICATE and never as a number, so a
	// predicate is all this driver may answer.  0x1000 is the SMALLEST word whose
	// bits 12..5 equal 0x80: the least this model can claim while still saying
	// "not yet below half scale".
	//
	// ⚠ IT IS NOT A LEVEL, AND IT IS THE ONE FAKE IN THIS HANDLER.  Nothing in
	// this driver knows a level -- there is no synthesis here, no sound device at
	// all, and the six wave mask ROMs are undumped -- and this value must never
	// be read as an amplitude or an envelope.  "Envelope" is not asserted by the
	// disassembly either; the previous log line here called it an "envelope
	// level" and that name had nothing behind it.
	//
	// What it buys: with the bitmap above answering, a voice survives the poll,
	// so the poll's own guard `and A,0x81 / jr NZ` at 0xFA69A7 lets QUERY 2 run
	// at all -- under the old stub it could not, because the record was already
	// released.  At note-off sub_FA65F6 then takes its RELEASE arm (0xFA6621:
	// clear flag bit 3, SET FLAG BIT 2 at 0xFA6632, call 0xFA62DA with the
	// record's own +0x16) instead of its "this voice already died" arm.  Flag
	// bit 2 has no other producer in the voice module -- 0xFA6632 is the only
	// `set 0x02` in 0xFA6528-0xFA6EF9 -- so this is what makes the comparison at
	// 0xFA69C7/0xFA69D4 reachable at all.  ⚠ Stage three (flag bit 1, "finished")
	// stays unreachable, because 0x1000 never satisfies `< 0x80`.
	if ((latch >= 0x0180) && (latch < 0x0180 + TG_VOICES))
	{
		const unsigned chan = latch - 0x0180;
		const bool     busy = BIT(m_tg_busy[chan >> 4], chan & 15);

		LOGMASKED(LOG_TG, "tg: magnitude of channel %2u -> 0x%04X (%s)\n",
			chan, busy ? 0x1000 : 0x0000, busy ? "busy: not below half scale" : "free");
		return busy ? 0x1000 : 0x0000;
	}

	// ⚠ THE ONE THING THIS MODEL STILL CANNOT DO, written here so nobody has to
	// rediscover it: THE BUSY BIT NEVER FALLS BY ITSELF.  It clears only when the
	// firmware writes 0x7E00, and the only per-note writer of 0x7E00 is
	// Dev10C_ChanReset -- called ONLY from the retire path, which is driven by
	// the bit falling.  Real hardware breaks that loop because the chip decides
	// when the voice has ended; this driver has no voice to end.  Consequence:
	// ChanRec_Release has exactly two call sites (0xFA6892, all 64 at boot, and
	// 0xFA6989, the poll), so between one VoiceSubsystem_Init and the next, no
	// channel record returns to the pool.
	//
	// But that does NOT starve the allocator, and it is now settled from the
	// disassembly (prom_c note_engine.s; 0xFA62DA / 0xFA643F are the queue-relink
	// helpers ChanRec_RelinkToPoolQueue / ChanRec_RelinkToPartQueue, not
	// undecoded): ChanAlloc_ForNoteRequest asks ChanAlloc_FindVictim (0xFA69FD),
	// which walks the per-part priority list at 0xFE1220 -- idle, then releasing,
	// then SOUNDING (the list ends at the part's own queue 0) -- and STEALS the
	// first non-empty queue.  It yields 0xFF (silent) only if every queue,
	// sounding included, is empty.  So the pool never replenishing costs no
	// polyphony: a note-on steals a sounding voice rather than being refused.
	// The fake above is therefore benign for allocation; a faithful retire (and a
	// true magnitude) still needs a synthesis model, which is gap A's job.
	LOGMASKED(LOG_TG, "tg: status read, latch 0x%04X -> 0 (no query is known at this select)\n", latch);
	return 0;
}

// ---- 0x108000 / 0x108002: THE 61-KEY KEYBED SCANNER ----------------------
//
// ★ IT IS A PORT OF THE TONE GENERATOR, NOT A PART OF ITS OWN.  IC4, the
// TC183C230002 at 0x10C000, takes a second chip select NKSCE <- KSCS, and the
// key-scan matrix (KS0-KS3, KF0-KF3, KB0-KB4) and its touch-sense inputs LEL
// and LER are on the same die (sheet II-13/II-14).  The event line KBEVNT
// leaves IC4 for CPU 2's INT4.  The handlers stay separate from tg_* because
// the register pair is a different one, with a different access order.
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
//
// ⚠ AND THE SCHEMATIC DOES NOT PUT A CHIP ON EITHER WINDOW.  Both decoder
// outputs are unnamed: IC18's Y7 = 0x7F0000 on CPU 1 (the table in cpu1_map)
// and IC27's 2Y0 = 0xE00000 on CPU 2.  They are the only decoder outputs in
// this machine that the firmware writes and the schematic leaves without a net
// -- every other unnamed output sits at an address no code touches.  Both
// windows are also write-only in every path in every image.  The reading that
// fits is that this is shared source inherited from the KN5000 sub-CPU, where
// the twin at 0x130000 is fitted, recompiled here for two windows that are not.
// An unlabelled stub on a photocopy is an absence, so nothing is removed on the
// strength of it; storing the writes and logging a read is exactly the right
// model for a window whose device is in doubt.  What would settle it is the
// parts list for the MAIN (A)/(B) boards or the foil-side pages 25-28.

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
	save_item(NAME(m_tg_busy));
	save_item(NAME(m_tg_gate));
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

	// So that a captured -log carries its own legend and a reader can tell a
	// locally established register name from a borrowed one without opening the
	// notes.  Costs nothing unless LOG_TG is on.
	tg_log_legend();
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

	// VoiceSubsystem_Init (0xFA66C7) and Dev10C_ResetAllChannels (0xFB8211) both
	// write 0x7E00 to every channel out of RESET, so "all free" is where the
	// firmware puts the device anyway.
	std::fill(std::begin(m_tg_busy), std::end(m_tg_busy), 0);
	m_tg_gate = 0;

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
	// the code touches are mapped.
	//
	// ★ WHAT SITS ON EACH OF THEM IS ON THE SCHEMATIC, though.  IC18, a
	// D74HC138GS (sheet II-9/II-10, manual page 20), takes A = A16, B = A17,
	// C = A18, G1 = A19 and /G2A = /G2B = CS0, so it only decodes with A19
	// HIGH -- every output below is inside 0x780000-0x7FFFFF whichever reading
	// of the CS0 window is right:
	//
	//     Y0  0x780000  (no net)      Y4  0x7C0000  MIF     the CPU link
	//     Y1  0x790000  LCDCS         Y5  0x7D0000  (no net)
	//     Y2  0x7A0000  FDDAK         Y6  0x7E0000  HDCS
	//     Y3  0x7B0000  FDCS          Y7  0x7F0000  (no net)
	//
	// Five named outputs on the five addresses the firmware reaches, with the
	// roles the disassembly gave them.

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
	// layer that drives the floppy, and the storage is an ATA hard disk.
	// Fdc_Request (0xFE66C7) takes a `unit` field
	// at request+0x02, every one of its twelve operations begins
	// `cp (0x605A32),1`, and all seven unit-1 arms in 0xFE4CE0-0xFE544D reach
	// the four accessors of this port (0xFE4C73 / 0xFE4C99 / 0xFE4CBF /
	// 0xFE4CE0), which are the only `add Xrr,0x007E0000` instructions in the
	// converted text of either image.  (FINDINGS-prom_a-fdc.md sec.6, checked by
	// that tree's notes/prom_a_unit1_backend_check.py.)
	//
	// ★ AND IT IS AN ATA (IDE) HARD DISK.  IC18's Y6 is HDCS (the table above),
	// IC1 carries HDINT on INT4 and HDIORDY on PB6, and the register protocol
	// is the ATA task file: a census of the 41 accessor calls with a literal
	// bank and register (wsa1-roms-disasm/notes/prom_a_census_round8.py --ata)
	// puts the command block at 0x7E0008-0x7E000F -- data, features/error,
	// sector count, sector number, cylinder low, cylinder high, device/head,
	// command/status -- and device control at 0x7E0016, written 0x0C then 0x08
	// (0xFE50E9 / 0xFE50F5), which is SRST asserted and released.  Seven
	// opcodes are issued, each with the data phase its opcode demands: 0x20
	// READ SECTOR(S), 0x30 WRITE SECTOR(S), 0xEC IDENTIFY DEVICE, 0x91
	// INITIALIZE DEVICE PARAMETERS, 0xEF SET FEATURES, 0x94 and 0x95.  The
	// status bits are used as ATA uses them: BSY polled with a 500-tick
	// timeout, DRQ required before each 512-byte transfer, ERR after one, DRDY
	// after a command that moves no data.  prom_a 0xFE69BF even holds a FAT16
	// boot sector for a fixed disk (media 0xF8, drive 0x80, 60 sectors x 15
	// heads x 568 cylinders = 261.7 MB) carrying the string "This is Technics
	// HDD.", and INITIALIZE DEVICE PARAMETERS is issued with that geometry.
	//
	// STILL INERT, deliberately, and the reason is no longer the part: nothing
	// traced sets a request block's unit field to 1, and the ROM's boot-sector
	// image has no consumer at all, so whether a drive was ever fitted to a
	// rack is open.  Wiring an ata_interface would put a drive on the bus of a
	// machine that may never have had one.  Only the data register is silenced
	// here; a reach into the rest of the task file stays unmapped so that it
	// shows up in the log.  CS0 access timing is relaxed for the duration of a
	// transfer (B0CS 0x14 -> 0x10 -> 0x14, 0xFE509B and 0xFE50D5), which is
	// what proves the device is on CS0.
	//
	// ⚠ The opcode and register NAMES above are the ATA standard's; no image
	// spells them, exactly as the floppy half of the same module declines to
	// name its uPD765.
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
	//
	// ★ AND THE DECODER IS ON THE SCHEMATIC, with all four outputs named
	// (IC27, a D74HC139GS, sheet II-11/II-12, manual page 21; first half,
	// 1E = SCS0, 1DA = SA14, 1DB = SA15):
	//
	//     1Y0  pin 4   SMIF    0x100000   the inter-processor link
	//     1Y1  pin 5   WFICS   0x104000   IC3, the modelling LSI
	//     1Y2  pin 6   KSCS    0x108000   the keybed port of IC4
	//     1Y3  pin 7   SGCS    0x10C000   IC4, the tone generator
	//
	// - the four windows the firmware reaches, in the order the disassembly
	// derived them.  The same package's second half decodes SCS2 on SA19/SA20
	// into SFLSHCS 0xE80000, PROMDCS 0xF00000 and PROMCCS 0xF80000, with 2Y0
	// (0xE00000) carrying no net.

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
	// tone generator's note-on burst.
	//
	// ★ THE PART AND THE DECODE ARE SETTLED BY THE SCHEMATIC.  IC27's 1Y1 is
	// WFICS at 0x104000 (the table above) and IC3, the L7A1429 "MODELING LSI",
	// takes NSGCE <- WFICS, NWR <- SWR, MD0..MD15 <-> SD0..SD15 and NAD <- SA1
	// -- that last one being this driver's +0 select / +2 data pair, off a
	// single address line.  IC3's product leaves on RQWFI and IOWFI(0..12) into
	// pins 25-40 of IC4 at 0x10C000, so the modelling LSI feeds the tone
	// generator a 13-bit word on request: the two windows are two stages of ONE
	// signal path, and this one's output is not audio.
	//
	// ⚠ WHAT IS STILL INFERENCE IS THE INTERNAL SIGNAL PATH -- series or
	// parallel, where the excitation enters, how MAIN and SUB couple.  No ROM
	// can close it: nothing reads the device, so there is no readback to
	// calibrate against, and the KN5000 sub-CPU has no counterpart device to
	// borrow meanings from.  acoustic_modeling.h grades each register claim.
	// The disassembly deliberately keeps its routines under the address-stating
	// prefix `Dev104_`, and the device name is not a reason to change them.
	// (The stub was `synth2` until 2026-09-01, then `modeling`.)
	map(0x104000, 0x104001).w(m_modeling, FUNC(l7a1429_device::addr_w));
	map(0x104002, 0x104003).rw(m_modeling, FUNC(l7a1429_device::data_r),
	                                       FUNC(l7a1429_device::data_w));

	// THE 61-KEY KEYBED SCANNER: +0 event, +2 status with bit 0 = "an event is
	// waiting".  0xF99762 reads the status, 0xF99776 and 0xF998C6 read the
	// event, and the consumer is the velocity decoder at 0xF995DF.  The KN5000
	// has the identical interface at 0x110000/0x110002, which MAME already
	// models as kbd_data_r/kbd_status_r in kn5000.cpp.  Note that this device
	// is NOT the "+0 select / +2 data" pair the two rows either side of it are:
	// the boot preload at 0xF99125 writes +2 first and +0 second.  See the
	// block comment on the handlers.
	//
	// ★ IT IS NOT A SEPARATE PART.  IC4, the TC183C230002 tone generator at
	// 0x10C000, takes TWO chip selects: NSGCE <- SGCS and NKSCE <- KSCS (sheet
	// II-13/II-14, manual page 22).  So this window is a SECOND PORT ON THE
	// TONE GENERATOR, and KS0-KS3 / KF0-KF3 / KB0-KB4 / LEL / LER on IC4's left
	// edge are the key-scan matrix and its touch-sense lines.  The handlers
	// below stay separate from tg_*: they are a different register pair with a
	// different access order, on the same die.
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
	//
	// What the sheet adds for whoever writes the sound device (page 22):
	// crystal X4 = 33.8688 MHz = 768 x 44100, so the audio rate is 44.1 kHz;
	// LRCK, BCK and SDO0-SDO7, i.e. EIGHT serial audio lanes; two independent
	// 21-bit wave address buses ADX0-20 / ADY0-20 with four output enables each
	// (XCS0-3, YCS0-3) reaching the six mask ROMs on sheet II-15/II-16; MD0-15
	// on SD0-15 with NAD <- SA1; and the 13-bit RQWFI / DWFI0-DWFI12 input from
	// IC3 on pins 25-40.
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
	// --- the tone database, prom_d, on CPU 2's bus -------------------------
	//
	// 512 KiB at 0x00F00000.  The base is established twice over, and neither
	// reading is this driver's:
	//   * prom_a reads the image's build tag REMOTELY at 0x00F7FFF0 over the
	//     inter-CPU link (wsa1-roms-disasm/notes/FINDINGS-memory-map.md sec.5).
	//     0x00F7FFF0 - 0x00F00000 = 0x7FFF0, which is exactly where the tail tag
	//     sits in the 512 KiB image -- the size and the base agree.
	//   * prom_c's ExtBoard_ProbeAndInstallBases stores 0x00F00000 into RAM
	//     0x00D7ED (0xFB051E / 0xFB0523), and Voice_SelectKeyZone_Reg0040
	//     relocates three nested 32-bit 0-based offsets of a voice's tone object
	//     against it.
	//
	// It was left unmapped until now because the base was NOT established when
	// this driver was written -- the note then said so, and the driver refused
	// to guess.  The disassembly corrected that on 2026-08-25; this maps it.
	//
	// ★ AND THE SCHEMATIC IS A THIRD, PHYSICAL WITNESS (sheet II-11/II-12,
	// manual page 21): IC27's 2Y2 is PROMDCS, which is SA20 high and SA19 low
	// inside CS2, i.e. 0xF00000-0xF7FFFF, and the part it enables is IC21
	// QSIGCWSA1DX "4M BIT PROGRAMMED EP ROM" on SA1..SA18 with SD0..SD15.  So
	// the fourth EPROM and the AM29F400T flash at SFLSHCS 0xE80000 are
	// different chips, which is what the superseded hypothesis had wrong.
	//
	// ⚠ prom_d's own linker script in the disassembly tree still carries the
	// superseded 0xE80000 hypothesis and says "BASE -- NOT ESTABLISHED".  That
	// file is stale; the corrected reading is the one cited above.
	map(0xf00000, 0xf7ffff).rom().region("prom_d", 0);           // IC21, tone database

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


	// The tone generator's PLACEHOLDER sine, on by default: the six wave mask
	// ROMs are undumped, so this stands in for real samples (wsa1_tonegen.h).
	// Off silences it without disturbing the register file.
	PORT_START("TGSINE")
	PORT_CONFNAME(0x01, 0x01, "Placeholder sine (wave ROMs undumped)")
	PORT_CONFSETTING(   0x00, DEF_STR(Off))
	PORT_CONFSETTING(   0x01, DEF_STR(On))
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
	//
	// ------------------------------------------------------------------------
	// ★ THE KEYBOARD MODEL ENTERS SERVICE MODE FROM THE KEYBED, not from the
	// panel -- something no sibling in these trees does.
	//
	// On the (0xC4) == 1 arm, the RESET-path service test at prom_a 0xF827F8
	// (-> 0xF40148 -> 0xF952FC) calls sub_F9530B, which does a LINK REMOTE READ
	// of EIGHT BYTES from CPU 2's address 0x0000FFF0 (0xF95311-0xF9531E, through
	// the 0xE2 remote-read op at 0xF8E0FE), pops all eight bytes, and does
	// nothing unless EXACTLY TWO BITS ARE SET (`cps L,0x02 / jrl NZ`, 0xF95346).
	//
	// 0x0000FFF0 is CPU 2's 61-key key-state bitmap: KeyScan_InitKeyStateBitmap
	// (prom_c 0xF9988D) clears eight bytes there and folds scanner events in at
	// byte (key >> 3) & 7, bit key & 7, with the base as the 32-bit constant at
	// ROM 0xFCC81A.  ★ That closes an open question in the disassembly tree,
	// which had found no consumer of the bitmap in prom_c: the consumer is on the
	// OTHER processor.
	//
	// The five bit pairs are all EXACTLY TWELVE KEYS APART -- a self-check on the
	// bit -> key decode that could have failed and did not -- so every chord is
	// two of the same note an octave apart.  Key 0 is MIDI 36, so:
	//
	//     C4 + C5   keys 24, 36   recognised and REJECTED (0xF95359)
	//     D4 + D5   keys 26, 38   screen 0xD9  PANEL CPU CHECK      (0xF9536C)
	//     E4 + E5   keys 28, 40   screen 0xDA  SINE WAVE CHECK      (0xF95383)
	//     F4 + F5   keys 29, 41   screen 0xDB  PANEL SW&LED CHECK   (0xF953A7)
	//     G4 + G5   keys 31, 43   screen 0xDC  the screen cycler    (0xF953BE)
	//
	// With the default PC mapping below those are Z+Q, X+W, C+E, V+R and B+T.
	// Re-read from the ROM by notes/wsa1-probes/wsa1_service_screen_refutation.py
	// section 2, and reachable in the emulator by
	// notes/wsa1-probes/wsa1_service_entry.lua.
	//
	// ★ MEASURED, AND THE MEASUREMENT CONFIRMS THE DECODE WHILE THE CHORD STILL
	// DOES NOT FIRE.  Holding D4 + D5 from t = 0 on `wsa1`, CPU 2's bitmap reads
	//
	//     0x0000FFF0 = 00 00 00 04 40 00 00 00      popcount 2
	//
	// steadily from t = 5 s onwards -- byte +3 bit 2 = key 26 = D4 and byte +4
	// bit 6 = key 38 = D5, EXACTLY the pair sub_F9530B tests for screen 0xD9.  So
	// the keybed model, the scanner, CPU 2's bitmap builder and the bit -> key
	// decode above are all correct, live, against a criterion that could have
	// failed.  And yet RAM (0x2070) is never written with 0xD9 and (0x207C) never
	// leaves the play screen (notes/wsa1-probes/wsa1_service_entry.lua).
	//
	// That localises the failure to CPU 1's side of the remote read, and rules
	// out the two other candidates: the bitmap is not empty, and nothing
	// pre-empts a screen that was never requested.  The live hypothesis is
	// ORDERING -- CPU 1 issues the read at 0xF827F8, very early in RESET, before
	// even its own 0x384-tick wait at 0xF82804, while CPU 2 does not build the
	// bitmap until MAIN's init chain reaches 0xF997FA, and until 0xF9816B moves
	// XSP those same eight bytes are CPU 2's boot stack.  NOT YET PROVEN: the
	// remote read could also simply be failing.
	//
	// The chords are documented here because they are established, not because
	// they work.
	// ------------------------------------------------------------------------

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
	m_cpu2->port9_read().set(FUNC(wsa1_state::cpu2_p9_r));

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

	// --- IC3, the L7A1429 modelling LSI, 0x104000 on CPU 2 ------------------
	//
	// A PLACEHOLDER: it holds the register file the firmware writes, and makes
	// no sound.  It has no lines to wire HERE -- CPU 2 reaches it through the
	// address map alone, and nothing in prom_c reads it back -- but it is not a
	// leaf on the board: its product leaves on RQWFI/DWFI0-DWFI12 into the tone
	// generator, so the two are two stages of one signal path.  What the part
	// is, what it is not, and the grade of each claim are in
	// acoustic_modeling.h.
	L7A1429(config, m_modeling);

	// --- IC4, the tone generator (TC183C230002), 0x10C000 on CPU 2 ---------
	//
	// PLACEHOLDER SINE backend while the six wave mask ROMs are undumped -- the
	// same stand-in the KN5000 driver uses (kn5000_tonegen.cpp RENDER_SINE).  It
	// is driven ONLY by the register writes tg_data_w already issues (PITCH
	// chan+0x0400 and the block-0 gate latch), and routed to a stereo speaker.
	// wsa1_tonegen.h explains why it is a sine, why it stays silent until the
	// CPU2->CPU1 link carries a note, and how a real IC4 replaces it.
	SPEAKER(config, "lspeaker").front_left();
	SPEAKER(config, "rspeaker").front_right();
	WSA1_TONEGEN(config, m_tonegen, 0);
	m_tonegen->set_enable_port(":TGSINE");
	m_tonegen->add_route(0, "lspeaker", 1.0);
	m_tonegen->add_route(1, "rspeaker", 1.0);

	// --- the floppy disk controller ----------------------------------------
	//
	// The evidence, the substitution of upd765a_device for the parts list's
	// uPD72070, and the one inference this costs are all in the block comment
	// above fdc_ctrl_w().  Only the wiring is here.
	//
	// The clock is INERT -- upd765.cpp contains no call to clock() at all -- but
	// it is now the real one: sheet II-9/II-10 draws IC8 D72070GF3BE "FLOPPY
	// DISK CONTROLLER" with X5, a 24 MHz crystal, across its XA1/XA2/XB pins
	// (59-61).  It was 8 MHz here, which was only "the usual uPD765-family
	// crystal".  Nothing in this driver depends on the value; the data rate
	// comes from the DSR writes instead.
	//
	// ready and select are both left CONNECTED, which is the device's default:
	// the firmware decodes ST3's RY bit in Fdc_Op11_SenseDriveStatus (0xFE6668)
	// and builds a US1/US0 drive byte in Fdc_IssueCommand (0xFE5C81), so both
	// lines are things this firmware expects to exist.  Note the unit field of a
	// request selects the BACK END rather than a second drive -- unit 1 is an
	// ATA hard disk at 0x7E0008, not a floppy -- so there is exactly one drive
	// here.
	//
	// The two interrupt lines are the schematic's: IC1 pin 37 INT5 = FDINT and
	// pin 41 INT7 = FDDRQ (sheet II-7/II-8).  Both were derived from the
	// firmware first - see the block comment above fdc_ctrl_w() - and the sheet
	// agrees with both.
	UPD765A(config, m_fdc, 24'000'000, true, true);   // IC8's X5
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

	// ★ THE OSCILLATOR IS X2, 8 MHz, across IC7's OSC1/OSC2 (sheet II-9/II-10,
	// manual page 20), so the frame rate is no longer left at the screen's
	// nominal 60 Hz.  sed1330_device uses clock() for exactly one thing --
	// `screen().configure(tcr*fx, lf, visible_area, clocks_to_attotime(tcr*lf*9))`
	// when SYSTEM SET's L/F byte arrives (sed1330.cpp) -- so this makes the
	// refresh rate the panel's own, derived from the firmware's TC/R and L/F:
	// MEASURED 68.5871 Hz (notes/wsa1-probes/wsa1_lcd_frame_rate.lua), which is
	// 8000000 / (54 * 240 * 9) exactly, so SYSTEM SET asks for 54 characters per
	// line and 240 lines.  The rendered image does not change -- snapshots at
	// the same boot point before and after are pixel-identical.
	// This comment used to say the part was one the scan does not resolve.
	SED1330(config, m_lcdc, 8'000'000);   // IC7's X2
	m_lcdc->set_screen("screen");
	m_lcdc->set_addrmap(0, &wsa1_state::lcdc_map);

	// ✅ P9 IS NOW WIRED, AND IT WAS NOT A FAKE AFTER ALL -- 2026-08-27.
	// This paragraph used to say that CPU 2's P9 bit 3 (the DSP READY poll, 18
	// sites in prom_c) must be left unbound because "no schematic net has been
	// read for that pin", and that the only cost was boot speed.  Both halves
	// were wrong.  The net IS on the schematic -- IC2 pin 23, `DSPRDY`, with R79
	// 4.7K pulling it UP -- so an unbound read of 0 was the wrong LEVEL rather
	// than a neutral one; and the cost was not speed, it was the SOUND MODE
	// screen's sound name.  cpu2_p9_r() above carries the evidence, the pin
	// numbers and the measurement.
	//
	// P5 bit 4 USED TO BE ON THIS LIST and is not any more: it is the service
	// CHECKING DEVICE's switch, the service manual says so in as many words, and
	// it is wired above.  See the block comment on cpu1_p5_r().
	//
	// ✅ THE TWO TIMER DEFECTS THIS COMMENT USED TO DESCRIBE ARE FIXED, in the
	// CPU core where they belonged, and the paragraph is kept only so that the
	// numbers it quoted are not left standing.  It said the 8-bit prescaler was
	// 16x too slow and that the 16-bit timers were never counted, and that
	// neither could be changed because "no databook is present in these trees
	// to settle the tap numbering".  The databook turned up
	// (notes/wsa1-probes/tlcs900_datasheet_quotes.py has the quotes and the
	// URL) and settles it: Table 3.8 (1) p.81 gives phiT1 = 8/fc, phiT4 =
	// 32/fc, phiT16 = 128/fc, phiT256 = 2048/fc.
	//
	// Measured here, same source tree, timers reverted vs fixed
	// (notes/wsa1-probes/tlcs900_timer_control.sh switches between them,
	// notes/wsa1-probes/wsa1_inttr4_dispatch.lua does the counting):
	//
	//                              reverted        fixed
	//   INTT1 (RAM 0x0080 tick)    30.5 Hz         488.3 Hz   firmware wants 488.28
	//   INTTR4 (vector 0x50)       never fired     192.0 Hz   into 0xF82EA2
	//   SED1330 first write        t = 7.21 s      t = 0.50 s
	//   SWI7 text drawing          t = 72.24 s     t = 19.62 s
	//
	// so boot to a drawn screen is ~4x quicker in emulated time, and the
	// machine's musical clock exists at all for the first time.
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

    IC1          TMP95C061AF    Toshiba TLCS-900/H, "MICROCOMPUTER (MAIN)",
                                on sheet II-7/II-8 with IC12 and IC13
    IC2          TMP95C061AF    Toshiba TLCS-900/H, "MICROCOMPUTER (SUB)",
                                on sheet II-9/II-10, and IC28 and IC21 are on
                                its bus on sheet II-11/II-12
    IC3          L7A1429        "MODELING LSI"
    IC4          TC183C230002   "TONE GENELATOR LSI" [sic].  Sheet II-13/II-14
                                prints the part label directly under the IC4
                                designator and both readings now agree on
                                TC183C230002.  It takes TWO chip selects,
                                NSGCE <- SGCS (0x10C000) and NKSCE <- KSCS
                                (0x108000), so the keybed port is a second port
                                on this die; its crystal X4 is 33.8688 MHz =
                                768 x 44100.
    IC5, IC6,    D6383GF-3BA    NEC digital signal processor, three of them on
    IC30                        sheet II-15/II-16, sharing one 8-bit host bus
                                off CPU 2's ports: IC6 answers DSP0CS, IC5
                                DSP1CS and IC30 DSP2CS, which are the three
                                destinations of the firmware's effect-microcode
                                transport.  See the block comment above
                                cpu2_p9_r().
    IC7          SED1330FBA     LCD controller, for the 320 x 240 dot panel,
                                with crystal X2 = 8 MHz on OSC1/OSC2 and IC71
                                as its display RAM.  MAME has a device for this
                                part already, in src/devices/video/sed1330.h
    IC16         T7WU04F        inverter pack; X1, the 28 MHz crystal both
                                processors are clocked from, is across it
    IC24, IC25   D74HC374GS     the inter-processor mailbox: one octal latch
                                per direction, CPU 1's bus to CPU 2's and back
    IC26         D74HC32GS      OR gates that form the two mailbox interrupts,
                                SIFINT = SMIF OR SWR and IFINT = MIF OR WR, and
                                the two output enables
    IC12         QSIGCWSA1AX    4 Mbit programmed EPROM, chip select PROMACS
    IC13         QSIGCWSA1BX    4 Mbit programmed EPROM, chip select PROMBCS
    IC21         QSIGCWSA1DX    4 Mbit programmed EPROM, chip select PROMDCS,
                                at 0xF00000 on CPU 2.  The designator column is
                                missing from the parts list rows, but sheet
                                II-11/II-12 prints IC21 twice beside this part,
                                which is also the name the redistributed set
                                gives the image.
    IC22         AM29F400T      "4MBIT FLASH MEMORY", chip select SFLSHCS at
                                0xE80000 on CPU 2, drawn SA1..SA18 with
                                SD0..SD15, so x16 like the EPROMs.  Sheet
                                II-11/II-12 prints the designator above the
                                part label; the parts list does not carry it.
    IC14, IC15   M5256CFP70LL,  256 kbit static RAM and 4 Mbit dynamic RAM.
                 M5M44170AJ7S   The self-diagnostic calls the pair "RAM (IC14,
                                15)"; only the IC15 designator is legible on
                                the schematic, so IC14 is derived from that
                                sentence.  The parts list spells the dynamic
                                RAM M5M44170AN7S.
    IC23,        LC321664AJ80   1 Mbit dynamic RAM
    IC31, IC32,
    IC51, IC61
    IC17         D74HC139GS     decoder on CPU 1's bus: CS1 with A19/A20 gives
                                RAMCS, CS2 with A19/A20 gives EXTCS, PROMBCS
                                and PROMACS
    IC18         D74HC138GS     decoder on CPU 1's bus: A16/A17/A18 gated by
                                A19 and CS0, giving LCDCS, FDDAK, FDCS, MIF and
                                HDCS
    IC27         D74HC139GS     decoder, both halves used: SCS0 with SA14/SA15
                                gives SMIF, WFICS, KSCS and SGCS, and SCS2 with
                                SA19/SA20 gives SFLSHCS, PROMDCS and PROMCCS
    IC28         QSIGCWSA1CX    4 Mbit programmed EPROM, chip select PROMCCS
    IC33, IC34   M5M44260AJ7S   4 Mbit dynamic RAM.  The parts list spells it
                                M5M44260AJN7S.
    IC43         QSIGH3C16DT8   16 Mbit wave mask ROM (schematic: ...DT3)
    IC44         QSIGH3C16EA0   16 Mbit wave mask ROM (schematic: ...EA9)
    IC45         QSIGH3C16EA2   16 Mbit wave mask ROM (parts list: QSIGH38C...)
    IC47         QSIGH3C16DT7   16 Mbit wave mask ROM
    IC48         QSIGH3C16DT9   16 Mbit wave mask ROM
    IC49         QSIGH3C16EA1   16 Mbit wave mask ROM
                                Sheet II-15/II-16 puts IC43-IC45 on the tone
                                generator's Y address bus and IC47-IC49 on its
                                X bus, and draws all six with A0..A19, a BYTE
                                pin and TGD0..TGD15, i.e. 1M x 16 each.
    IC52 - IC54, PCM1702U       D/A converter, four of them
    IC59
    IC55 - IC58  M5218AFP       operational amplifier
    IC71         LH5P832N-10    256 kbit RAM, the SED1330's display memory
                                (VD0-VD7, VA0-VA14).  The schematic calls it
                                pseudo static, the parts list just static.
    IC8          D72070GF3BE    NEC "FLOPPY DISK CONTROLLER", for the 3.5 inch
                                2HD 1.44 MB / 2DD 720 KB drive.  Its row in
                                the parts list falls outside the run of rows
                                whose designators can be recovered, but sheet
                                II-9/II-10 prints IC8 above the part label.
                                Crystal X5 = 24 MHz on XA1/XA2/XB; /CS, A0-A2,
                                D0-D7, /DMAAK, INT, DMARQ and TC on the CPU
                                side; DS0 but none of ME0-ME3 on the drive
                                side.

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
	// manual rather than after processors.  ★ WHICH PROCESSOR FETCHES WHICH
	// PAIR IS NOW SETTLED, by the P.C. diagrams rather than the parts list:
	// IC1 TMP95C061AF "MICROCOMPUTER (MAIN)" is drawn on sheet II-7/II-8 with
	// IC12 QSIGCWSA1AX (/OE = PROMACS) and IC13 QSIGCWSA1BX (/OE = PROMBCS) on
	// its unprefixed bus, while IC2 TMP95C061AF "MICROCOMPUTER (SUB)" is on
	// sheet II-9/II-10 with the S-prefixed bus, and IC28 QSIGCWSA1CX (PROMCCS)
	// and IC21 QSIGCWSA1DX (PROMDCS) are on that bus on sheet II-11/II-12.  So
	// A and B belong to the MAIN processor and C and D to the SUB one.
	//
	// ★ THE x16 INFERENCE IS PROVEN TOO.  IC12 and IC13 are drawn with A1..A18
	// on the EPROM's A0..A17 and D0..D15 on its data pins -- the CPU's A0 is
	// not connected, which is what a x16 device on a byte-addressed bus looks
	// like -- so the flat byte image per device that this map asserts is right.
	// (See ONE INFERENCE THE MAP RESTS ON at the top of this file.)

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
	// 0x050B08 and the rest of the device is erased.  It is a region of its own
	// rather than the other half of "prom_c" because it is a separate chip on a
	// separate chip select: IC27's 2Y2 = PROMDCS puts it at 0xF00000-0xF7FFFF,
	// where cpu2_map maps it.
	//
	// ⚠ THE FILE WAS RENAMED on 2026-09-03, from qsigcwsa1dx.bin.  The
	// designator is legible after all -- sheet II-11/II-12 draws IC21
	// QSIGCWSA1DX beside the IC27 decoder, printed twice on that sheet -- and
	// it agrees with the name the redistributed set gives the image.
	ROM_REGION16_LE(0x080000, "prom_d", 0)
	ROM_LOAD("qsigcwsa1dx.ic21", 0x000000, 0x080000, CRC(735ae465) SHA1(82df50816c20cd8f2d29551326d2633e7791f306))

	// The wave ROMs are not held here.  The self-diagnostic's wave ROM test
	// covers IC43 to IC45 and IC47 to IC49, and maps them to six buttons; there
	// is no IC46 in either the parts list or the self-diagnostic.  The OCR of
	// the button map loses the circled digits, so which button drives which
	// device is not reproduced here.
	//
	// ★ THE ORGANISATION AND THE BUSES ARE ON SHEET II-15/II-16 (manual page
	// 23).  Each device is drawn with A0..A19, a BYTE pin, and sixteen data
	// pins on TGD0..TGD15, so a 16 Mbit part is 1M x 16 = 2 MiB -- the size
	// each region below already has.  IC43, IC44 and IC45 sit on the tone
	// generator's Y address bus (YA0..YA20, chip enables YCS0..YCS3) and IC47,
	// IC48 and IC49 on its X bus (XA0..XA20, XCS0..XCS3), which is why there
	// are six devices on two buses of four selects each.  Each still gets a
	// region of its own: nothing establishes which select each device answers,
	// so concatenating them into a bank would assert an order.
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

	// IC22, a 4 Mbit flash device on CPU 2's SFLSHCS at 0xE80000, drawn with
	// SA1..SA18 and SD0..SD15 (sheet II-11/II-12).  Not held here, and the
	// manual does not say what it holds; the firmware's erase and program
	// routines are described at the "Not mapped, deliberately" note in
	// cpu2_map().
	ROM_REGION(0x080000, "flash", 0)
	ROM_LOAD("am29f400t.ic22", 0x000000, 0x080000, NO_DUMP)
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
	config.set_default_layout(layout_wsa1r);
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

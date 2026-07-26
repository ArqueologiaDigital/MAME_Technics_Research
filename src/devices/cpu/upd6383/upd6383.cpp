// license:BSD-3-Clause
// copyright-holders:Felipe Sanches
/***************************************************************************

    upd6383.cpp

    NEC uPD6383GF digital signal processor.

    *** DRAFT / RESEARCH INSTRUMENT -- MACHINE_NOT_WORKING GRADE. ***
    *** NO AUDIO.  INSTANTIATED DISABLED AS A CPU (see below). ***
    *** There IS a serial-audio frame entry point since 2026-07-26 --
    *** run_frame(), one LRCK period -- but it is opt-in behind a
    *** default-OFF driver option and it produces silence BY
    *** CONSTRUCTION: most of the words on the frame path are still
    *** undecoded, so every frame is discarded.
    *** What it produces is the decoding worklist.  See run_frame().
    ***
    *** SINCE 2026-07-26 (K6) A SAMPLE DOES ENTER THE CHIP.  The kernel's
    *** twelve audio-input words are executed for their ADDRESSING -- the
    *** DI latches are deposited in the two D-RAM cells the microcode
    *** reads, and an audit measures every frame that it read them back
    *** unchanged.  Their ALU is still open, so they count as PARTIAL and
    *** the frame is still discarded: silence, but now an OBSERVABLE
    *** machine.  notes/dsp-k6-input-stage.md, ...-applied.md.

    WHAT THIS IS
        The effects DSP of the Technics SX-KN5000 (IC311).  The same part is
        documented -- block diagram and pin table only, no instruction set --
        as IC302 in the Pioneer CDJ-500/CDJ-500G service manual, pp. 1-15..1-17.
        100-pin, 44.1 kHz frame rate, and per that diagram:

            I-RAM  384 x 36  (instruction RAM, host-uploaded -- NOT a ROM)
            C-RAM  256 x 24, D-RAM 256 x 24, both on one 24-bit IDB
            MPLY   24 x 24 with K and L input latches -> P
            ALU    44 bits, ACCA/ACCB, two shifters, OVC
            PC + a TWO-level stack, STA-R, CNT-R, UCPC, LC1-LC3, TR0-TR3
            pointers CP/DP/BP1/BP2/PR1/PR2, bank register BNK-R
            external DRAM controller (RAS/CAS/WE, A0-A16, 16-bit I/O)
            serial audio DI1-DI3 / DO1-DO3
            host flags GF1-GF3 (set by instructions) and RQ1-RQ3 (set by the
            host, testable by an instruction's COND field), and a BRAKST
            instruction

    WHAT THIS IS NOT
        A working CPU core.  The instruction set is NOT decoded.  Six word
        forms are established (see upd6383d.cpp, which carries the evidence for
        each); this device executes exactly those and TRAPS AND LOGS every
        other word without changing any state.  A partially-correct effects DSP
        produces audio that DIVERGES, and plausible-but-wrong audio is worse
        than silence because nobody can hear that it is wrong -- so run_frame()
        DISCARDS the whole frame's return the moment any word traps, which today
        is every frame.  When the ISA is known, that is the moment to make
        noise.

        The Technics KN5000 instantiates this device so that the host interface
        is really exercised and the uploaded microcode really lands in I-RAM,
        but instantiates it DISABLED (machine config calls set_disable()), so
        execute_run() never runs in a shipping machine.  Everything below the
        uC-IF is therefore reachable only from the debugger and from unidasm.

    MODELLING CHOICES THAT ARE NOT FACTS  (each is flagged again at its use)
        * PC is counted in BYTES, five per instruction word, and I-RAM is
          modelled as a byte space.  The hardware I-RAM is 384 x 36; the host
          uploads it as 5-byte records and the same byte view lets one
          disassembler serve both unidasm and this device.
        * The implicit coefficient cursor is read from AS_CRAM and the pointer
          operand from AS_DRAM.  What the notes establish is that the
          coefficient bank is loaded through the `801.0.NN.821' pointer space
          and the state cells are cleared through the `000.1.NN.000' pointer
          space, i.e. that they are two DIFFERENT spaces
          (notes/kn5000-dsp-cursor-general.md sect. 5.1).  WHICH of C-RAM and
          D-RAM is which is UNKNOWN; this assignment is arbitrary.
        * `ldptr' loads a single modelled data pointer.  The chip has six
          pointer registers and the corpus shows four variants of the load
          (lo12 = 0x820/0x821/0x825/0x827); which variant loads which register
          is UNKNOWN, and only the 0x821 form is decoded at all.
        * The terminator word ends the frame here.  That it is the last word of
          91 of 91 programs is MEASURED; that it means "end of frame" rather
          than "return" is NOT.  Stopping is a convenience so a draft core does
          not run away, not a decode.

    THE SOURCE OF EVERY IMPLEMENTED SEMANTIC is documented next to it, and in
    the DECODED FORMS block at the top of upd6383d.cpp.

***************************************************************************/

#include "emu.h"
#include "upd6383.h"
#include "upd6383d.h"

#include <fstream>

#define LOG_TRAP   (1U << 1)    // words we cannot execute
#define LOG_EXEC   (1U << 2)    // words we can
#define LOG_HOST   (1U << 3)    // uC-IF command/data bytes
#define LOG_UPLOAD (1U << 4)    // completed I-RAM uploads
#define LOG_FRAME  (1U << 5)    // per-LRCK-period frame summaries (rate-limited)
#define LOG_INPUT  (1U << 6)    // the audio input stage: what entered, and where

// LOG_INPUT is on by default and costs nothing: it emits the first 8 frames in
// which a NON-SILENT sample entered the chip, plus one frame per 48000.  Those
// eight lines are the standing evidence that audio really does reach the
// microcode -- the thing this device could not say at all before K6.
#define VERBOSE (LOG_TRAP | LOG_INPUT)
#include "logmacro.h"

// device type definition
DEFINE_DEVICE_TYPE(UPD6383, upd6383_device, "upd6383", "NEC uPD6383GF (draft)")


//**************************************************************************
//  CONSTRUCTION
//**************************************************************************

upd6383_device::upd6383_device(const machine_config &mconfig, const char *tag, device_t *owner, u32 clock) :
	cpu_device(mconfig, UPD6383, tag, owner, clock),
	// ON-CHIP.  I-RAM: 384 words of 36 bits, seen as 384 * 5 = 1920 bytes.
	m_iram_config("iram", ENDIANNESS_BIG, 8, 11, 0,
			address_map_constructor(FUNC(upd6383_device::iram_map), this)),
	// ON-CHIP.  C-RAM / D-RAM: 256 x 24, carried in 32-bit cells.
	m_cram_config("cram", ENDIANNESS_BIG, 32, 10, -2,
			address_map_constructor(FUNC(upd6383_device::cram_map), this)),
	m_dram_config("dram", ENDIANNESS_BIG, 32, 10, -2,
			address_map_constructor(FUNC(upd6383_device::dram_map), this)),
	// OFF-CHIP.  The delay memory is a separate DRAM on the host board, driven
	// by this chip's own RAS/CAS/WE, A0-A16 and I/O1-16 pins; the machine
	// config supplies it, and how much of the 128K x 16 space is populated is a
	// property of that board, not of the part.
	//
	// The 18 here is the SPACE, i.e. the widest address the part could carry --
	// LEFT AS IS DELIBERATELY.  How many bits the chip actually emits is OPEN:
	// on the KN5000 only A0-A8 reach the DRAM (nine lines, MEASURED -- IC311
	// pins 55..62 carry no net) and the chip multiplexes row/column itself, so
	// the total is 9+8 = 17 or 9+9 = 18 and the strap that decides it,
	// MD1-MD4 = 0b1111, has no known encoding.  The DRIVER's map() is what
	// limits the reachable range (kn5000.cpp, dsp1_delay_map), and widening
	// either one on a guess would silently change every delay tap length.
	m_delay_config("delay", ENDIANNESS_BIG, 16, 18, -1),
	m_icount(0),
	m_pc(0), m_ucpc(0), m_sta(0), m_cnt(0),
	m_acc(0), m_accb(0), m_p(0), m_k(0), m_l(0), m_ta(0), m_tb(0),
	m_cursor(0), m_cp(0), m_dp(0), m_bp1(0), m_bp2(0), m_pr1(0), m_pr2(0),
	m_bnk(0), m_lc1(0), m_lc2(0), m_lc3(0),
	m_gf(0), m_rq(0), m_ovc(0), m_frame_done(0), m_sp(0),
	m_host_cmd(0), m_host_pos(0), m_host_addr(0),
	m_capture_base(nullptr), m_capture_open(false),
	m_program_id(0), m_trap_total(0),
	m_in_base(0), m_in_seen_mask(0),
	m_frames_run(0), m_frames_trapped(0), m_frames_partial(0), m_frames_capped(0), m_frames_overrun(0),
	m_last_slots(0), m_last_traps(0), m_last_partials(0), m_partial_total(0),
	m_in_frames(0), m_in_ok(0), m_in_bad(0), m_in_nonzero(0), m_in_peak(0),
	m_in_log_left(INPUT_LOG_FRAMES),
	m_frame_detail_left(FRAME_DETAIL_FRAMES),
	m_order_n(0), m_order_total(0), m_order_slots(0), m_order_before(0),
	m_order_partials(0), m_order_valid(false)
{
	std::fill(std::begin(m_stack), std::end(m_stack), 0);
	std::fill(std::begin(m_tr), std::end(m_tr), 0);
	std::fill(std::begin(m_host_word), std::end(m_host_word), 0);
	std::fill(std::begin(m_order_iw), std::end(m_order_iw), 0);
	std::fill(std::begin(m_order_word), std::end(m_order_word), 0);
	std::fill(std::begin(m_in_addr), std::end(m_in_addr), 0);
	std::fill(std::begin(m_in_val), std::end(m_in_val), 0);
	std::fill(std::begin(m_in_seen), std::end(m_in_seen), 0);
	for (auto &p : m_di) { p[0] = 0; p[1] = 0; }
	for (auto &p : m_do) { p[0] = 0; p[1] = 0; }
}


device_memory_interface::space_config_vector upd6383_device::memory_space_config() const
{
	return space_config_vector {
		std::make_pair(AS_IRAM,  &m_iram_config),
		std::make_pair(AS_CRAM,  &m_cram_config),
		std::make_pair(AS_DRAM,  &m_dram_config),
		std::make_pair(AS_DELAY, &m_delay_config)
	};
}


std::unique_ptr<util::disasm_interface> upd6383_device::create_disassembler()
{
	return std::make_unique<upd6383_disassembler>();
}


//**************************************************************************
//  THE ON-CHIP MEMORIES
//**************************************************************************

//  All three are internal to the package and are therefore mapped here rather
//  than by a driver.  Sizes come straight off the CDJ-500 block diagram
//  (p. 1-15): I-RAM 384 x 36, C-RAM 256 x 24, D-RAM 256 x 24.

void upd6383_device::iram_map(address_map &map)
{
	map(0x000, 0x77f).ram();      // 384 words x 5 bytes
}

void upd6383_device::cram_map(address_map &map)
{
	map(0x00, 0xff).ram();        // 256 x 24
}

void upd6383_device::dram_map(address_map &map)
{
	map(0x00, 0xff).ram();        // 256 x 24
}


//**************************************************************************
//  START / RESET / STOP
//**************************************************************************

void upd6383_device::device_start()
{
	space(AS_IRAM).cache(m_iram);
	space(AS_CRAM).specific(m_cram);
	space(AS_DRAM).specific(m_dram);
	space(AS_DELAY).specific(m_delay);

	set_icountptr(m_icount);

	state_add(STATE_GENPC, "GENPC", m_pc).noshow();
	state_add(STATE_GENPCBASE, "CURPC", m_pc).noshow();
	state_add(UPD6383_PC,     "PC",     m_pc);
	state_add(UPD6383_IW,     "IW",     m_pc).callexport().formatstr("%5s");
	state_add(UPD6383_ACC,    "ACC",    m_acc).formatstr("%011X");
	state_add(UPD6383_P,      "P",      m_p).formatstr("%012X");
	state_add(UPD6383_K,      "K",      m_k).formatstr("%06X");
	state_add(UPD6383_L,      "L",      m_l).formatstr("%06X");
	state_add(UPD6383_TA,     "TA",     m_ta).formatstr("%06X");
	state_add(UPD6383_TB,     "TB",     m_tb).formatstr("%06X");
	state_add(UPD6383_CURSOR, "CUR",    m_cursor);
	state_add(UPD6383_CP,     "CP",     m_cp);
	state_add(UPD6383_DP,     "DP",     m_dp);
	state_add(UPD6383_BP1,    "BP1",    m_bp1);
	state_add(UPD6383_BP2,    "BP2",    m_bp2);
	state_add(UPD6383_PR1,    "PR1",    m_pr1);
	state_add(UPD6383_PR2,    "PR2",    m_pr2);
	state_add(UPD6383_BNK,    "BNK",    m_bnk);
	state_add(UPD6383_STA,    "STA",    m_sta);
	state_add(UPD6383_CNT,    "CNT",    m_cnt);
	state_add(UPD6383_UCPC,   "UCPC",   m_ucpc);
	state_add(UPD6383_LC1,    "LC1",    m_lc1);
	state_add(UPD6383_LC2,    "LC2",    m_lc2);
	state_add(UPD6383_LC3,    "LC3",    m_lc3);
	state_add(UPD6383_TR0,    "TR0",    m_tr[0]);
	state_add(UPD6383_TR1,    "TR1",    m_tr[1]);
	state_add(UPD6383_TR2,    "TR2",    m_tr[2]);
	state_add(UPD6383_TR3,    "TR3",    m_tr[3]);
	state_add(UPD6383_GF,     "GF",     m_gf);
	state_add(UPD6383_RQ,     "RQ",     m_rq);
	state_add(UPD6383_OVC,    "OVC",    m_ovc);

	save_item(NAME(m_pc));
	save_item(NAME(m_stack));
	save_item(NAME(m_ucpc));
	save_item(NAME(m_sta));
	save_item(NAME(m_cnt));
	save_item(NAME(m_acc));
	save_item(NAME(m_accb));
	save_item(NAME(m_p));
	save_item(NAME(m_k));
	save_item(NAME(m_l));
	save_item(NAME(m_ta));
	save_item(NAME(m_tb));
	save_item(NAME(m_cursor));
	save_item(NAME(m_cp));
	save_item(NAME(m_dp));
	save_item(NAME(m_bp1));
	save_item(NAME(m_bp2));
	save_item(NAME(m_pr1));
	save_item(NAME(m_pr2));
	save_item(NAME(m_bnk));
	save_item(NAME(m_lc1));
	save_item(NAME(m_lc2));
	save_item(NAME(m_lc3));
	save_item(NAME(m_tr));
	save_item(NAME(m_gf));
	save_item(NAME(m_rq));
	save_item(NAME(m_ovc));
	save_item(NAME(m_frame_done));
	save_item(NAME(m_sp));
	save_item(NAME(m_di));
	save_item(NAME(m_do));
	save_item(NAME(m_host_cmd));
	save_item(NAME(m_host_pos));
	save_item(NAME(m_host_addr));
	save_item(NAME(m_host_word));
}


void upd6383_device::device_reset()
{
	// The reset entry point is UNKNOWN.  I-RAM 0..59 is the common header,
	// 60..82 the algorithm-change stub, 84.. and 200.. the two effect-unit
	// bodies (MEASURED, notes/kn5000-dsp-header.md sect. 0), and no branch
	// word carrying 84 or 200 has ever been found -- entry may well be
	// host-driven via the PC-RST / Fs-RST pins.  Starting at 0 is a placeholder.
	m_pc = 0;
	m_acc = m_accb = m_p = 0;
	m_k = m_l = m_ta = m_tb = 0;
	m_cursor = 0;
	m_gf = 0;
	m_frame_done = 0;
	m_sp = 0;
	std::fill(std::begin(m_stack), std::end(m_stack), 0);
	for (auto &p : m_di) { p[0] = 0; p[1] = 0; }
	for (auto &p : m_do) { p[0] = 0; p[1] = 0; }
	m_frame_detail_left = FRAME_DETAIL_FRAMES;
	m_in_seen_mask = 0;     // per-frame; the audit COUNTERS are a whole-run census
}


void upd6383_device::device_stop()
{
	if (m_frames_run != 0)
		dump_frame_report();

	if (m_trap_total != 0)
		dump_trap_histogram();

	capture_flush();
	capture_write_files();

	// The pointer trace rides on the same opt-in as the upload capture: it is
	// instrumentation, it is inert unless a machine config asked for capture,
	// and it needs no driver change of its own.
	if (m_capture_base != nullptr)
		write_pointer_trace((std::string(m_capture_base) + "_ptrtrace.txt").c_str());
}


void upd6383_device::state_string_export(const device_state_entry &entry, std::string &str) const
{
	switch (entry.index())
	{
	case UPD6383_IW:
		// the I-RAM word index is what every note in this project counts in
		str = string_format("%d", m_pc / upd6383_disassembler::WORD_BYTES);
		break;
	}
}


//**************************************************************************
//  THE PARALLEL uC-IF
//**************************************************************************

void upd6383_device::host_w(bool cd, u8 data)
{
	capture_byte(cd, data);

	if (!cd)
	{
		// command byte -- restarts the payload
		m_host_cmd = data;
		m_host_pos = 0;
		LOGMASKED(LOG_HOST, "uC-IF CMD %02X\n", data);
		return;
	}

	LOGMASKED(LOG_HOST, "uC-IF cmd %02X data[%u] <- %02X\n", m_host_cmd, m_host_pos, data);

	// Command 0x01 = WRITE I-RAM: a 16-bit BIG-ENDIAN word address followed by
	// N * 5 bytes, one 36-bit instruction word each.  MEASURED two independent
	// ways (notes/kn5000-dsp-header.md sect. 0):
	//   * in the Technics KN5000 Sub CPU ROM the bytecode op-3 record is
	//     {cmd, addr_hi, addr_lo, 5-byte words} -- tools/kn5000_dsp_extract.py
	//     pulls all 100 algorithms out statically using exactly this layout;
	//   * at runtime every command-0x01 payload is 2 bytes plus a multiple of
	//     5, and the addresses tile I-RAM without overlap: 0..59 common header,
	//     60..82 algorithm-change stub, 84.. unit-0 body, 200.. unit-1 body,
	//     352..382 host poke slots.
	//
	// Every other command is ACCEPTED AND IGNORED.  Command 0x02 carries
	// 24-bit coefficient words, but its 2-byte prefix takes values above 0x100
	// (e.g. 0x0161), so it is not a plain 256-word C-RAM address and routing it
	// would put invented data in a real memory.  Ignoring is not a stall: the
	// host is never held up, which is what keeps the machine booting.
	if (m_host_cmd != 0x01)
	{
		m_host_pos++;
		return;
	}

	if (m_host_pos == 0)
		m_host_addr = u16(data) << 8;
	else if (m_host_pos == 1)
		m_host_addr |= data;
	else
	{
		const u32 byte_in_word = (m_host_pos - 2) % upd6383_disassembler::WORD_BYTES;
		m_host_word[byte_in_word] = data;

		if (byte_in_word == upd6383_disassembler::WORD_BYTES - 1)
		{
			const u32 word_index = m_host_addr + (m_host_pos - 2) / upd6383_disassembler::WORD_BYTES;

			if (word_index < IRAM_WORDS)
			{
				address_space &iram = space(AS_IRAM);
				for (u32 i = 0; i < upd6383_disassembler::WORD_BYTES; i++)
					iram.write_byte(word_index * upd6383_disassembler::WORD_BYTES + i, m_host_word[i]);

				LOGMASKED(LOG_UPLOAD, "I-RAM[%u] <- %02X%02X%02X%02X%02X\n", word_index,
						m_host_word[0], m_host_word[1], m_host_word[2], m_host_word[3], m_host_word[4]);

				// A NEW MICROPROGRAM is the only thing that can put a word we
				// have never seen on the frame path, so re-arm the full
				// per-word trap accounting for a window of frames (see the
				// FRAME_DETAIL_FRAMES comment in the header).
				m_frame_detail_left = FRAME_DETAIL_FRAMES;
			}
			else
			{
				// the corpus contains malformed streams whose load addresses
				// fall outside the 384-word I-RAM; refuse rather than wrap
				logerror("uC-IF: I-RAM write to word %u is outside %d -- ignored\n", word_index, IRAM_WORDS);
			}
		}
	}

	m_host_pos++;
}



//**************************************************************************
//  RESEARCH INSTRUMENTATION: the uC-IF upload capture
//**************************************************************************

//  Because I-RAM is RAM, the microprogram MUST be uploaded at runtime, so the
//  program image is reachable without decoding a single opcode.  This capture
//  is what produced the corpus every note in notes/kn5000-dsp-*.md is built on
//  (see notes/data/kn5000_dsp1_upload_coldboot.txt).  It is instrumentation,
//  not chip behaviour: it is inert unless set_capture_file() was called, and
//  m_transfers is deliberately not a save-state item.
//
//  A payload whose length is 2 + a multiple of 5 is an I-RAM instruction run
//  (36-bit words in 40-bit containers); a multiple of 3 is a C-RAM/D-RAM run
//  (24-bit words).  Both divide 15, so multiples of 15 are AMBIGUOUS and are
//  reported as such rather than being claimed for either.

void upd6383_device::capture_byte(bool cd, u8 data)
{
	if (m_capture_base == nullptr)
		return;

	if (!cd)
	{
		// a command byte ends whatever data run preceded it
		capture_flush();
		m_capture_current.cmd = data;
		m_capture_current.payload.clear();
		m_capture_open = true;
		return;
	}

	if (!m_capture_open)
	{
		// data with no preceding command: captured with a sentinel so it is
		// not silently merged into the next run
		m_capture_current.cmd = 0xff;
		m_capture_current.payload.clear();
		m_capture_open = true;
	}

	m_capture_current.payload.push_back(data);
}


void upd6383_device::capture_flush()
{
	if (!m_capture_open)
		return;

	if (!m_capture_current.payload.empty())
		m_transfers.push_back(m_capture_current);

	m_capture_open = false;
	m_capture_current.payload.clear();
}


void upd6383_device::capture_write_files()
{
	if (m_capture_base == nullptr || m_transfers.empty())
		return;

	std::string const base(m_capture_base);
	std::ofstream bin(base + ".bin", std::ios::binary);
	std::ofstream txt(base + ".txt");

	if (!txt)
		return;

	txt << "NEC uPD6383GF host uploads (uC-IF capture)\n";
	txt << "I-RAM capacity is " << IRAM_WORDS << " words of 36 bits; a program may use FEWER.\n";
	txt << "5 bytes = one 36-bit I-RAM word, 3 bytes = one 24-bit C-RAM/D-RAM word (confirmed:\n";
	txt << "the KN5000 Sub CPU bytecode handlers divide by literal 5 and 3, and captured uploads\n";
	txt << "tile I-RAM exactly). Command 0x01 payloads are a 16-bit word address + N*5 bytes.\n\n";

	size_t total = 0;
	for (size_t i = 0; i < m_transfers.size(); i++)
	{
		auto const &t = m_transfers[i];
		size_t const n = t.payload.size();
		total += n;

		if (bin)
			bin.write(reinterpret_cast<char const *>(t.payload.data()), n);

		char const *shape;
		if (n % 15 == 0)      shape = "ambiguous (multiple of both 5 and 3)";
		else if (n % 5 == 0)  shape = "groups of 5 -> candidate I-RAM instruction words";
		else if (n % 3 == 0)  shape = "groups of 3 -> candidate C-RAM/D-RAM words";
		else                  shape = "neither";

		util::stream_format(txt, "transfer %4u: cmd 0x%02X  %5u bytes", unsigned(i), t.cmd, unsigned(n));
		if (n % 5 == 0)
			util::stream_format(txt, "  (%u x5)", unsigned(n / 5));
		if (n % 3 == 0)
			util::stream_format(txt, "  (%u x3)", unsigned(n / 3));
		if (t.cmd == 0x01 && n >= 2 && ((n - 2) % 5) == 0)
			util::stream_format(txt, "  I-RAM[%u..%u]",
					unsigned((t.payload[0] << 8) | t.payload[1]),
					unsigned(((t.payload[0] << 8) | t.payload[1]) + (n - 2) / 5 - 1));
		util::stream_format(txt, "  %s\n", shape);

		for (size_t j = 0; j < n; j++)
		{
			if ((j % 16) == 0)
				util::stream_format(txt, "    %04X:", unsigned(j));
			util::stream_format(txt, " %02X", t.payload[j]);
			if ((j % 16) == 15 || j == n - 1)
				txt << "\n";
		}
	}

	util::stream_format(txt, "\n%u transfers, %u payload bytes total\n",
			unsigned(m_transfers.size()), unsigned(total));

	osd_printf_info("upd6383: wrote %u transfers (%u bytes) to %s.{bin,txt}\n",
			unsigned(m_transfers.size()), unsigned(total), base);
}


//**************************************************************************
//  EXECUTION
//**************************************************************************

u64 upd6383_device::fetch(offs_t pc)
{
	u64 word = 0;
	for (u32 i = 0; i < upd6383_disassembler::WORD_BYTES; i++)
		word = (word << 8) | m_iram.read_byte(pc + i);

	// bits 36..39 are always zero in every one of the 2974 corpus words
	// (MEASURED, notes/kn5000-dsp-encoding.md)
	return word & 0xfffffffffULL;
}


void upd6383_device::trap(u64 word, offs_t pc)
{
	m_trap_total++;
	m_trap_hist[word]++;

	// (word, PC, program, context).  Rate-limited to the first sighting of each
	// distinct word so that a 44.1 kHz frame loop does not drown the log.
	if (m_trap_hist[word] == 1)
	{
		LOGMASKED(LOG_TRAP, "UNDECODED %010X  iw=%d (pc=%04X)  program=%u  cursor=%02X dp=%02X acc=%011X : %s\n",
				word, pc / upd6383_disassembler::WORD_BYTES, pc, m_program_id,
				m_cursor, m_dp, m_acc, upd6383_disassembler::text(word));
	}
}


//**************************************************************************
//  THE AUDIO INPUT STAGE (K6)
//**************************************************************************

//  PRESENT THE SAMPLES.  Called once per frame, BEFORE I-RAM word 0, which is
//  where the hardware does it: the serial-port receivers fill the DI latches
//  every LRCK period whatever the microcode is doing.
//
//  The chain this closes is, in full:
//
//      IC303 SDOA/SDOB/SDO1  ->  DI1/DI2/DI3 pins  ->  m_di[port][ch]
//                            ->  D-RAM[X+2], D-RAM[X+5]
//                            ->  header w4 / w8 read them as ordinary memory
//
//  The last hop is the K6 result and the reason nothing entered before: there is
//  no "read DI" INSTRUCTION on this chip.  The port-ness of a read is entirely
//  in its ADDRESS, so a core that waits for an I/O opcode waits forever.
//
//  X is the data pointer as the frame starts -- NOT a constant, and deliberately
//  not treated as one: the register file threads across frames (run_frame()
//  restarts the PC and only the PC), so the input window moves with it and the
//  deposit follows.  In steady state the epilogue's `ldptr #$90' at I-RAM 69
//  and its w79 (-1) leave X = 0x8F, giving 0x91 and 0x94 -- which is the
//  0x8F..0x97 window notes/dsp-k6-input-stage.md sect. 5 predicts.  Nothing here
//  depends on that: only the OFFSETS are used, and they are the forced part.

void upd6383_device::latch_inputs_to_dram()
{
	m_in_base = m_dp;
	m_in_addr[0] = u8(m_in_base + IN_LATCH_L_OFF);
	m_in_addr[1] = u8(m_in_base + IN_LATCH_R_OFF);
	m_in_val[0] = m_di[IN_PORT][0];
	m_in_val[1] = m_di[IN_PORT][1];

	m_dram.write_dword(m_in_addr[0], u32(m_in_val[0]) & 0xffffff);
	m_dram.write_dword(m_in_addr[1], u32(m_in_val[1]) & 0xffffff);

	m_in_seen[0] = m_in_seen[1] = 0;
	m_in_seen_mask = 0;
}


//  EXECUTE THE ADDRESSING OF A K6 INPUT-STAGE WORD -- and NOTHING else.
//
//  Three effects, all MEASURED, none of them this file's invention:
//      hi12 bit 4    -> the word STORES the accumulator to mem[ptr]
//      class4 bit 3  -> the word FETCHES the next coefficient (cursor += 1)
//      addr8         -> a SIGNED pointer post-increment
//
//  What is NOT done, on purpose: the ALU.  The `lo12' field that selects the
//  arithmetic is undecoded for all twelve words, so the accumulator is left
//  exactly as it was.  That is why a frame containing one of these is DISCARDED
//  like a frame that trapped -- see run_frame().  The value the stores write is
//  therefore arbitrary; it lands only in cells the input stage and the epilogue
//  own (X+0, X+1, X+3, X+4, X+6), never in the two input latches, and the audit
//  in run_frame() is what checks that claim every single frame instead of
//  asserting it.

void upd6383_device::exec_addressing_only(u64 word)
{
	const u16 hi = upd6383_disassembler::hi12(word);
	const u8  cl = upd6383_disassembler::class4(word);
	const s8  dd = s8(upd6383_disassembler::addr8(word));

	// The one C-format word of the stage carries no class4, no addr8 and no
	// memory operand: a SAFE NO-OP, not a word we execute badly.
	if ((hi & 0xf00) == 0xc00)
		return;

	const u8 cell = m_dp;

	// THE PORT READ.  Record what the microcode really took out of the cell, so
	// the frame can compare it with what was deposited.  The read itself has no
	// modelled consequence -- the ALU is open -- but the VALUE is the whole
	// question, so it is captured rather than thrown away.
	bool right;
	if (upd6383_disassembler::is_input_latch_read(word, right))
	{
		m_in_seen[right ? 1 : 0] = s32(util::sext(m_dram.read_dword(cell) & 0xffffff, 24));
		m_in_seen_mask |= right ? 2 : 1;
	}

	if (hi & upd6383_disassembler::HI_ST)
		m_dram.write_dword(cell, u32(m_acc & 0xffffff));

	if (cl & 8)
		m_cursor++;

	m_dp = u8(m_dp + dd);
}


//**************************************************************************
//  THE ALU (the lo12 field)
//**************************************************************************

//  ONE OPERATION, EVERY WORD.  There is no per-word "accumulator op": the
//  accumulator always takes the pending product, and the two things that used
//  to look like different accumulator ops are (a) the store on hi12 bit 4 also
//  CLEARING the accumulator and (b) the product register being consumed by the
//  add.  Derived from, and verified against, the PARAMETRIC EQ biquad -- the
//  one block whose transfer function is known independently, because the
//  firmware designs its coefficients itself (notes/dsp-alu-biquad.md).
//
//      L    := bus[ lo12[7:6] ]      00 acc   01 tempA   02 tempB   03 mem[p]
//      if hi12 bit 4 :  mem[p] <- acc ; acc := 0
//      acc  += P ; P := 0
//      lo12[3:0] :  3 -> tempA <- L   4 -> tempB <- L   7 -> mem[p] <- L
//      if class4 == A :  P := coef[cursor++] * L
//      if class4 & 7 == 2 :  p += (s8)addr8
//
//  ORDER MATTERS AND IS FORCED, not chosen: the bus source is latched BEFORE
//  the ALU step (same rule R1 forced for the bit-4 store -- "store = after" has
//  zero survivors, analysis/r1-allpass-motif.md F2), which is what lets
//  `212.A.FF.407' both write the accumulator to memory and multiply by it.

s32 upd6383_device::acc_to_datum(u64 acc)
{
	// the 44-bit accumulator read as a 24-bit datum, with saturation.  The
	// chip has two shifters and an OVC on the CDJ-500 block diagram; whether it
	// saturates or wraps is UNKNOWN, and saturation is the choice that cannot
	// turn a loud sound into a louder one.
	const s64 v = s64(util::sext(acc, 44)) >> ACC_SHIFT;

	if (v >  0x7fffff) return  0x7fffff;
	if (v < -0x800000) return -0x800000;
	return s32(v);
}


void upd6383_device::exec_alu(u64 word)
{
	const u16 hi = upd6383_disassembler::hi12(word);
	const u8  cl = upd6383_disassembler::class4(word);
	const s8  dd = s8(upd6383_disassembler::addr8(word));
	const u8  src = upd6383_disassembler::lo_src(word);
	const u8  op = upd6383_disassembler::lo_op(word);

	// ---- the operand bus, latched before anything else ---------------------
	// alu_decoded() is an eight-value whitelist, so only the four ANCHORED
	// source codes can reach this switch; there is deliberately no default
	// case that guesses at the other fourteen the corpus contains.
	s32 L = 0;
	switch (src)
	{
	case upd6383_disassembler::LO_SRC_ACC:
		L = acc_to_datum(m_acc);
		break;
	case upd6383_disassembler::LO_SRC_TA:
		L = s32(util::sext(m_ta, 24));
		break;
	case upd6383_disassembler::LO_SRC_TB:
		// THE ONE-BIT SHIFT.  Without it the biquad is 77 dB wrong, so it is
		// FORCED; that it sits on the tempB BUS SOURCE rather than on the
		// tempB CAPTURE is NOT -- the two are indistinguishable inside the
		// section, and the alternative is listed in the note.  Its origin is
		// the coefficient format: the firmware writes -a1/a0 at 2^22 and
		// -a2/a0 at 2^23 (MEASURED, notes/kn5000-dsp-biquad-coeffs.md sect. 4),
		// so the y[n-2] cell must hold half the scale of the y[n-1] cell, and
		// the tempB path is the only path between them.
		L = s32(util::sext(m_tb, 24)) >> 1;
		break;
	default:
		L = s32(util::sext(m_dram.read_dword(m_dp) & 0xffffff, 24));
		break;
	}

	// ---- hi12 bit 4: store the accumulator to mem[ptr] AND CLEAR IT --------
	// The store is MEASURED and its "before the word's own ALU step" timing is
	// FORCED (R1 F2).  The CLEAR is new here and is forced by the biquad: the
	// two words of the section that carry bit 4 are exactly the two at which
	// the accumulator must restart from zero, and without it the section is
	// 57 dB wrong.
	if (hi & upd6383_disassembler::HI_ST)
	{
		m_dram.write_dword(m_dp, u32(acc_to_datum(m_acc)) & 0xffffff);
		m_acc = 0;
	}

	// ---- the ALU: the pending product, consumed -----------------------------
	// *** ONE OF TWO NUMERICALLY IDENTICAL READINGS (notes/dsp-alu-biquad.md
	// *** sect. 7-A8).  The alternative is that the product register is NOT
	// *** consumed and hi12[3:1] selects the accumulator op (0 -> acc <- P,
	// *** 1 -> acc += P).  Over the eight whitelisted lo12 codes the two agree
	// *** to the LAST BIT on all eight ROM coefficient banks, so the biquad
	// *** cannot choose between them -- but notes/dsp-alu-crossval.md B1 shows
	// *** independently (from the LFO's 092/094 minimal pair) that hi12[3:1]
	// *** DOES select an operation somewhere, so the alternative is the one to
	// *** expect to win once a second block is decoded.  Nothing downstream
	// *** changes if it does: swap these three lines.
	m_acc = (m_acc + m_p) & 0xfffffffffffULL;
	m_p = 0;

	// ---- the lo12[3:0] side effect ------------------------------------------
	switch (op)
	{
	case upd6383_disassembler::LO_OP_CAP_TA:
		m_ta = u32(L) & 0xffffff;
		break;
	case upd6383_disassembler::LO_OP_CAP_TB:
		m_tb = u32(L) & 0xffffff;
		break;
	case upd6383_disassembler::LO_OP_ST_BUS:
		m_dram.write_dword(m_dp, u32(L) & 0xffffff);
		break;
	default:
		break;                  // 0x2 and 0x5: no temp / memory side effect
	}

	// ---- the multiply (class A only -- class 8 is bit 23 but does NOT fetch)
	if (cl == 0xa)
	{
		const u32 coef = m_cram.read_dword(m_cursor) & 0xffffff;
		m_k = coef;
		m_l = u32(L) & 0xffffff;
		m_p = u64((s64(util::sext(coef, 24)) * s64(L)) >> P_SHIFT) & 0xfffffffffffULL;
		m_cursor++;
	}

	// ---- the pointer post-increment (classes 2 and A) -----------------------
	if ((cl & 7) == 2)
		m_dp = u8(m_dp + dd);
}


void upd6383_device::dump_trap_histogram() const
{
	logerror("upd6383: %d undecoded words executed, %d distinct:\n",
			u32(m_trap_total), u32(m_trap_hist.size()));
	for (const auto &e : m_trap_hist)
		logerror("    %010X  x%-8d  %s\n", e.first, u32(e.second), upd6383_disassembler::text(e.first));
}


void upd6383_device::execute_run()
{
	while (m_icount > 0)
	{
		debugger_instruction_hook(m_pc);

		const u64 raw = fetch(m_pc);

		// END OF PROGRAM is hi12 bit 10 with bit 11 clear, and it is a
		// MODIFIER: the halting instruction STILL PERFORMS ITS NORMAL WORK.
		// MEASURED (notes/kn5000-dsp-hi12.md sect. 3): 38 such words in 2974,
		// exactly one per image, all 38 the final word, and stripping the bit
		// leaves an ordinary working hi12 in 9 of 9 cases (612 = END|212,
		// 604 = END|204, 602 = END|202, 504 = END|104, 42C, 428, 424, 420,
		// 400 = END alone).  An ENUMERATED opcode field has no reason to place
		// nine halt codes at a constant offset 0x400 from nine ordinary codes.
		// So the model is: strip the bit, execute what is left, then halt --
		// NOT "the terminator is a separate halt instruction", which is what
		// the old class4==1 && addr8 in {0E,0F} test implied.
		// ...but ONLY where the measurement actually reaches.  The 38 words it
		// was measured on are all unit-index terminators, and the pointer
		// trace shows the COMMON HEADER carrying bit-10 words in its interior
		// (word 6, 400.A.00.419), so the "it is the halt" half of the reading
		// does not generalise off the body corpus.  The core therefore applies
		// the strip-and-halt model to the form it was measured on and traps
		// the rest, rather than extrapolating.
		const bool ending = upd6383_disassembler::is_end(raw)
				&& upd6383_disassembler::class4(raw) == 1
				&& (upd6383_disassembler::addr8(raw) == 0x0e
					|| upd6383_disassembler::addr8(raw) == 0x0f);
		const u64 word = ending
				? (raw & ~(u64(upd6383_disassembler::HI_END) << 24))
				: raw;

		const u16 hi = upd6383_disassembler::hi12(word);
		const u8  cl = upd6383_disassembler::class4(word);
		const u8  ad = upd6383_disassembler::addr8(word);
		const u16 lo = upd6383_disassembler::lo12(word);
		const s8  dd = s8(ad);      // signed pointer POST-increment (MEASURED)

		m_pc += upd6383_disassembler::WORD_BYTES;
		m_icount--;

		if (!upd6383_disassembler::decoded(word))
		{
			// K6: the twelve input-stage words are neither decoded nor unknown.
			// Their ADDRESSING is executed (see exec_addressing_only()); their
			// arithmetic is not, so they are still counted on the worklist.
			if (upd6383_disassembler::addressing_only(word))
			{
				exec_addressing_only(word);
				m_partial_total++;
			}
			else
			{
				// TRAP AND LOG.  No state is changed -- an undecoded word must
				// not silently corrupt the model.  In particular bit 4 (= store
				// the accumulator to mem[ptr]) is NOT acted on here: one bit of
				// a 36-bit word is not a decode, and performing half a word is
				// how a draft core starts producing plausible-but-wrong results.
				trap(raw, m_pc - upd6383_disassembler::WORD_BYTES);
			}
			(void)cl;

			if (ending)
			{
				m_frame_done = 1;
				m_icount = 0;       // "wait for the next sample" -- SPECULATIVE
			}
			continue;
		}

		LOGMASKED(LOG_EXEC, "%010X  %s\n", raw, upd6383_disassembler::text(raw));

		if (hi == 0x000 && cl == 2 && lo == 0x000)
		{
			// nop -- PROVEN BY CONSTRUCTION (sub-CPU writer LABEL_038922 builds
			// this exact pattern, setting the class4 nibble to 2 explicitly)
		}
		else if (hi == 0x801 && lo == 0x821)
		{
			// ldptr #NN -- PROVEN BY CONSTRUCTION (the firmware assembles these
			// bytes at sub-CPU LABEL_0387E6; in the host poke region such a word
			// always opens a burst of 1..30 data words).
			// WHICH of CP/DP/BP1/BP2/PR1/PR2 it loads is UNKNOWN; the model
			// keeps one data pointer.
			m_dp = ad;
		}
		else if (hi == 0x801 && lo == 0x021)
		{
			// rstcur -- resets the implicit coefficient cursor.  VERIFIED on
			// algo39 (PARAMETRIC EQ): its class-A count at the ten section
			// starts runs 0,6,12,18,24 | rstcur | 0,6,12,18,24.
			m_cursor = 0;
		}
		else
		{
			exec_alu(word);     // the lo12 field decode -- see exec_alu()
		}
		(void)dd;
	}
}


//**************************************************************************
//  ONE LRCK PERIOD -- THE SERIAL AUDIO FRAME
//**************************************************************************

//  WHY THE FRAME IS DRIVEN BY THE TONE GENERATOR AND NOT BY THE SCHEDULER
//
//      The KN5000's topology is a CYCLE: IC303 (tone generator) -> IC311
//      (this chip) -> IC303.  MEASURED off the service manual, pp. 34/35:
//
//          IC303 SDOA (pin 4, R308) -> IC311 DI1 (pin 20)
//          IC303 SDOB (pin 6, R309) -> IC311 DI2 (pin 21)
//          IC303 SDO1 (pin 197, R313) -> IC311 DI3 (pin 22)
//          IC311 DO1 (pin 23, R333) -> IC303 SDIA (pin 3)
//          IC311 DO2 (pin 24, R332) -> IC303 SDIB (pin 5)
//          IC311 DO3 (pin 25, R331) -> leaves the tone-generator block
//
//      and the MAIN MIX does not pass through here at all: it leaves IC303 on
//      SDO0 (pin 196) -> IC310 (MN19413) -> IC313 (PCM69AU) -> the analog board.
//      So IC311 is a SEND/RETURN INSERT.  It can only ever ADD to the output;
//      it cannot remove or attenuate the dry sound.  That safety property is a
//      property of the HARDWARE, not a bypass this model invents.
//      (notes/dsp-audiopath-wiring.md sect. 1, sect. 2 -- MEASURED.)
//
//      IC303 also GENERATES the clocks: LRCK on pin 208 through R311 and BCK on
//      pin 207 through R312 fan out to IC311 pins 18/17/19, to IC310 and to the
//      DAC.  IC311's pin 13 (Fs-RST) and pin 14 (Fs-MASK) are both strapped to
//      +5D -- per the CDJ-500 pin table those are emulator-mode overrides,
//      "pull up in regular modes" -- so the per-frame program-counter restart is
//      the chip's own internal PC-RST off the TIMING block, cadenced by LRCKI,
//      and it CANNOT be inhibited on this board.  MEASURED, p. 35.
//
//      Therefore "one PC sweep per LRCK period" IS "one PC sweep per tone
//      generator output sample", and calling run_frame() from the tone
//      generator's sound_stream_update() is the hardware relationship, not a
//      shortcut.  It also keeps the chip boundary honest: this entry point is
//      DI1..DI3 / DO1..DO3 over one LRCK period, which is a real pin interface;
//      no device reads another device's memory.
//
//  *** EDUCATED GUESS G-1 -- THE ABSOLUTE SAMPLE RATE IS UNRESOLVED ***
//      WHAT IS DECIDED: exactly one frame per tone-generator output sample.
//      WHY: correct IN KIND regardless of the number, because IC303 generates
//      LRCKI, so the DSP's frame rate IS the tone generator's sample rate
//      whatever that turns out to be.
//      WHAT IS NOT KNOWN: the number itself.  The sub-CPU firmware converts a
//      user millisecond parameter with `ms * 0xAC44 / 0x3E8' = ms * 44100/1000
//      (LABEL_03925E) -- so the FIRMWARE says 44,100 Hz.  MAME's tone generator
//      allocates its stream at 48,000 Hz (kn5000_tonegen.cpp, device_start).
//      IC303's crystal X301 reads `36.8688 MHz' on the 1996 scan, which divides
//      to NEITHER (36.864 = 768 x 48k and 33.8688 = 768 x 44.1k are the two
//      stock parts that would).
//      WHAT WOULD SETTLE IT: Felipe reading X301's marking off the board (his
//      testimony outranks the scan), or locating IC303's LRCK divider.
//      WHAT CHANGES IF IT IS WRONG: every delay time and reverb time in
//      SECONDS, and the interpretation scale of any frequency-domain
//      coefficient -- by the ratio 48000/44100 = +8.8 %.  What does NOT change:
//      the per-frame instruction budget (25 MHz / 44.1 kHz = 566.9 cycles for
//      256..326 slots; at 48 kHz it is 520.8, still comfortable), the wiring,
//      or anything in this function.
//
//  *** WHAT THIS PRODUCES TODAY: NOTHING AUDIBLE, AND THAT IS THE EXPECTATION ***
//      Most of the words on the floor of every frame are still undecoded (the
//      83-word kernel and the 133-word reverb -- notes/dsp-next-steps-roadmap.md
//      sect. 3.2, MEASURED).  Every frame therefore traps, every frame's return
//      is DISCARDED, and the audible result is exactly the dry sound.  The useful
//      output is the trap report.
//
//      WHAT CHANGED WITH K6: the frame no longer stops being informative at its
//      very first word.  The audio INPUT STAGE (I-RAM 0..11) is executed for its
//      addressing, so a real sample from the tone generator is deposited in
//      D-RAM and really is read by the microcode -- measured, every frame, by the
//      audit in this function.  The first trap has moved off word 0, which is
//      what makes everything downstream reachable at all.

bool upd6383_device::run_frame(const s32 (&di)[3][2], s32 (&do_)[3][2])
{
	// ---- latch the inputs (the DI1L-R .. DI3R-R registers) -----------------
	// 24-bit two's complement: the internal IDB is 24 lines wide on the CDJ-500
	// block diagram, and the coefficient format is signed Q0.23.
	for (int port = 0; port < 3; port++)
		for (int ch = 0; ch < 2; ch++)
			m_di[port][ch] = s32(util::sext(u32(di[port][ch]) & 0xffffff, 24));

	// ---- restart the PC, and ONLY the PC -----------------------------------
	// The register file is NOT reset.  Words 0..41 -- including the whole input
	// stage at 0..11 -- run on pointers left behind by the PREVIOUS frame's
	// epilogue (its last loads are I-RAM 62 `825<-$26', 69 `821<-$90', 77
	// `822<-$86'); the first load in the frame that can set an 8-bit D-RAM
	// pointer is at I-RAM 42.  Zeroing m_dp / m_cursor / m_acc here would break
	// the machine's own state threading.  (MEASURED positions,
	// notes/dsp-next-steps-roadmap.md sect. 2.2 step 3.)
	m_pc = 0;
	m_sp = 0;
	m_frame_done = 0;

	// ---- PRESENT THE SAMPLES (K6) ------------------------------------------
	// The DI latches land in the two D-RAM cells the input stage reads, at
	// offsets +2 and +5 from the pointer the previous frame left.  Unconditional
	// and before the first word, because that is what the serial receivers do:
	// they do not wait to see whether the microcode is interested.
	latch_inputs_to_dram();

	const bool detail = (m_frame_detail_left > 0);
	const bool capture_order = detail;
	u32 order_n = 0;
	u32 order_before = 0;           // slots executed before this frame's first trap

	u32 slots = 0;
	u32 traps = 0;
	u32 partials = 0;               // addressing executed, ALU unknown
	bool hit_wait = false;
	bool overrun = false;

	while (slots < FRAME_SLOT_CAP)
	{
		// ---- TERMINATION 3: the PC left the 384-word I-RAM ------------------
		// MEASURED DEFECT, found by running this the first time: with the
		// call/return sequencer below, a frame whose body region has not been
		// uploaded yet (or whose body carries no tagged return) walks the PC
		// straight off the end of I-RAM -- 3.4 million "unmapped iram memory
		// read" complaints in a 24-second run.  What the real chip does with a
		// PC past word 383 is UNKNOWN (wrap? stall until the next PC-RST?), so
		// this does NOT invent a wrap: it ends the frame, counts it, and
		// discards the return like any other anomaly.
		if (m_pc >= IRAM_WORDS * upd6383_disassembler::WORD_BYTES)
		{
			overrun = true;
			break;
		}

		const offs_t pc = m_pc;
		const u64 raw = fetch(pc);

		// ---- TERMINATION 1: the frame-wait word ----------------------------
		// C00.A.47.407 at I-RAM 82.  The evidence is POSITIONAL, not a decode:
		// it is the last word of the frame, and the 23-word epilogue at 60..82
		// contains no end-of-block word at all -- a block that never ends is a
		// block closed by hardware.  MEASURED (notes/dsp-perframe-execution.md
		// sect. 1).  NOT MODELLED: whatever datapath work this word also does.
		// It is class 0xA, so under the cursor rule it would advance the
		// coefficient cursor, and it is simultaneously C-format, which would
		// make class4 immediate data instead -- an open contradiction
		// (dsp-next-steps-roadmap.md K2).  Rather than pick a side, the frame
		// stops here and the word performs nothing.
		if (raw == FRAME_WAIT_WORD)
		{
			hit_wait = true;
			m_frame_done = 1;
			break;
		}

		// ---- the UNIT-TAGGED TRANSFER word ---------------------------------
		// *** EDUCATED GUESS G-5 -- THE CALL/RETURN SEQUENCER ***
		// WHAT IS DECIDED: a word with the END bit (hi12 bit 10, bit 11 clear),
		// class4 == 1 and addr8 in {0x0E, 0x0F} transfers control -- it CALLS
		// the tagged unit's body when the stack is empty and RETURNS when it is
		// not.  The chip has exactly a TWO-level stack (CDJ-500 block diagram:
		// STACK1/STACK2), which is exactly deep enough for one call at a time.
		// WHY: without it the frame is a straight line 0..82 and the two effect
		// BODIES never execute, so the trap report -- the entire value of the
		// experimental path today -- would cover the kernel only.  The sequence
		// itself is PROVEN BY CONSTRUCTION: the common header loads the same
		// three pointer registers TWICE, at I-RAM 42-44 (#$70/#$6C/#$25) and
		// 50-52 (#$50/#$64/#$25), and no body word anywhere in the 2974-word
		// corpus contains a pointer load -- so unit 0's body must run BETWEEN
		// 44 and 50.  I-RAM 49 and 59 are the only two tagged words in the
		// header; the LAST word of 38 of 38 bodies is tagged; and there are
		// ZERO tagged words anywhere else in 7108 words.
		// WHAT IS NOT KNOWN: the MECHANISM by which the target is chosen.  The
		// entry addresses 84 and 200 are NOT in the word (addr8 is 8 bits and
		// two exhaustive bitfield scans for them were negative), so they are
		// either a hard-wired 2-entry vector or host-loaded entry registers.
		// The table below (0x0E -> 84, 0x0F -> 200) is OBSERVED in every
		// captured upload -- it is where the host puts the bodies -- NOT
		// derived.  Also unknown: what hi12 = 0x612 (= END | 0x212, an
		// accumulator store) does in addition, on the 5 words that carry it.
		// WHAT WOULD SETTLE IT: an effect whose body the host loads somewhere
		// other than 84/200, or the uPD6383 instruction set.
		// WHAT CHANGES IF IT IS WRONG: the PC ORDER within the frame, hence
		// which words appear in the trap report and in what order.  It cannot
		// change the audio, because every frame is discarded anyway.
		const bool tagged = upd6383_disassembler::is_end(raw)
				&& upd6383_disassembler::class4(raw) == 1
				&& (upd6383_disassembler::addr8(raw) == 0x0e
					|| upd6383_disassembler::addr8(raw) == 0x0f);

		// END OF BLOCK is a MODIFIER: the word still performs its normal
		// datapath work (MEASURED, notes/kn5000-dsp-hi12.md sect. 3 -- stripping
		// the bit leaves an ordinary working hi12 in 9 of 9 cases).  Same model
		// as execute_run(); only the CONTROL half differs, because
		// execute_run() halts here and a frame must not.
		const u64 word = tagged
				? (raw & ~(u64(upd6383_disassembler::HI_END) << 24))
				: raw;

		const u16 hi = upd6383_disassembler::hi12(word);
		const u8  cl = upd6383_disassembler::class4(word);
		const u8  ad = upd6383_disassembler::addr8(word);
		const u16 lo = upd6383_disassembler::lo12(word);
		const s8  dd = s8(ad);      // signed pointer POST-increment (MEASURED)

		m_pc += upd6383_disassembler::WORD_BYTES;
		slots++;

		if (upd6383_disassembler::addressing_only(word))
		{
			// K6 -- A THIRD STATE, and it is deliberately not folded into
			// either of the other two.  The word's ADDRESSING is executed, so
			// the sample enters, the pointer walks and the frame becomes
			// observable; its ALU is unknown, so the frame is still not
			// KEPT (see `clean' below) and the audible result is still exactly
			// the dry sound.  Counting these separately is what turns "100 % of
			// frames trap" into a number that can go down.
			partials++;
			m_partial_total++;
			exec_addressing_only(word);
			(void)cl;
		}
		else if (!upd6383_disassembler::decoded(word))
		{
			// TRAP.  No state is changed -- exactly as in execute_run().  The
			// frame's return will be discarded (see below), so a trap is a
			// no-op twice over.
			if (traps == 0)
				order_before = slots - 1;   // this word is already counted in `slots'
			traps++;
			if (detail)
				trap(raw, pc);
			else
				m_trap_total++;

			if (capture_order && order_n < TRAP_ORDER_MAX)
			{
				m_order_iw[order_n] = pc / upd6383_disassembler::WORD_BYTES;
				m_order_word[order_n] = raw;
				order_n++;
			}
			(void)cl;
		}
		else
		{
			LOGMASKED(LOG_EXEC, "%010X  %s\n", raw, upd6383_disassembler::text(raw));

			// The decoded semantics are IDENTICAL to execute_run()'s; see the
			// per-form evidence there and in upd6383d.cpp.
			if (hi == 0x000 && cl == 2 && lo == 0x000)
			{
				// nop
			}
			else if (hi == 0x801 && lo == 0x821)
			{
				m_dp = ad;
			}
			else if (hi == 0x801 && lo == 0x021)
			{
				m_cursor = 0;
			}
			else
			{
				exec_alu(word);
			}
			(void)dd;
		}

		// ---- the transfer, AFTER the word has done its datapath work -------
		if (tagged)
		{
			if (m_sp == 0)
			{
				m_stack[m_sp++] = m_pc;     // return to the word after this one
				m_pc = (upd6383_disassembler::addr8(raw) == 0x0e ? UNIT0_ENTRY : UNIT1_ENTRY)
						* upd6383_disassembler::WORD_BYTES;
			}
			else
			{
				m_pc = m_stack[--m_sp];
			}
		}
	}

	// ---- TERMINATION 2: the hard slot cap ----------------------------------
	// ALL THREE terminations are needed and none is redundant.  The cap alone
	// would silently MASK a mis-decode of the wait word (which is itself
	// undecoded); the wait word alone would HANG MAME on any program that never
	// reaches it -- and at boot, before the host has uploaded anything, I-RAM is
	// all zeros and there is no wait word to reach.
	const bool capped = !hit_wait && !overrun;

	m_frames_run++;
	m_last_slots = slots;
	m_last_traps = traps;
	m_last_partials = partials;
	if (traps != 0)
		m_frames_trapped++;
	if (partials != 0)
		m_frames_partial++;
	if (capped)
		m_frames_capped++;
	if (overrun)
		m_frames_overrun++;
	if (m_frame_detail_left > 0)
		m_frame_detail_left--;

	// ---- THE INPUT-STAGE AUDIT ---------------------------------------------
	// Did a sample actually enter, and did the microcode read THE SAME sample?
	// This runs on every frame in which both port-read words executed, and it is
	// a comparison, not an assertion: if the deposit landed one cell away, or if
	// one of the stage's own stores overwrote a latch before it was read, `bad'
	// becomes every frame and the report says so.  (Verified to be capable of
	// failing: moving the deposit to X+1/X+4 turns 100 % ok into 100 % bad.)
	if (m_in_seen_mask == 3)
	{
		m_in_frames++;

		if (m_in_seen[0] == m_in_val[0] && m_in_seen[1] == m_in_val[1])
			m_in_ok++;
		else
			m_in_bad++;

		if (m_in_val[0] != 0 || m_in_val[1] != 0)
		{
			m_in_nonzero++;
			for (int ch = 0; ch < 2; ch++)
			{
				const s32 mag = (m_in_seen[ch] < 0) ? -m_in_seen[ch] : m_in_seen[ch];
				if (mag > m_in_peak)
					m_in_peak = mag;
			}

			if (m_in_log_left > 0)
			{
				m_in_log_left--;
				LOGMASKED(LOG_INPUT, "IN frame %u: X=%02X  DI%d L=%06X R=%06X -> D-RAM[%02X]/[%02X];"
						" microcode read back L=%06X R=%06X  %s\n",
						u32(m_frames_run), m_in_base, IN_PORT + 1,
						m_in_val[0] & 0xffffff, m_in_val[1] & 0xffffff,
						m_in_addr[0], m_in_addr[1],
						m_in_seen[0] & 0xffffff, m_in_seen[1] & 0xffffff,
						(m_in_seen[0] == m_in_val[0] && m_in_seen[1] == m_in_val[1])
								? "MATCH -- the sample entered the chip" : "*** MISMATCH ***");
			}
		}
	}

	// A frame is only worth keeping as the WORKLIST if it actually ran a whole
	// program: it must have reached the frame-wait word AND executed at least
	// FRAME_ORDER_MIN_SLOTS.  Frames that pass are kept, most recent wins --
	// which matters because the host RELOADS the bodies when the user changes
	// effect, and the newest program is the one worth working on.
	if (capture_order && hit_wait && slots >= FRAME_ORDER_MIN_SLOTS)
	{
		m_order_valid = true;
		m_order_n = order_n;
		m_order_total = traps;
		m_order_slots = slots;
		m_order_before = traps ? order_before : slots;
		m_order_partials = partials;
	}

	// rate-limited: the first three frames, then roughly one per second
	if (m_frames_run <= 3 || (m_frames_run % 48000) == 0)
	{
		LOGMASKED(LOG_FRAME, "frame %u: %u slots, %u partial, %u traps, ended on %s -> return %s\n",
				u32(m_frames_run), slots, partials, traps,
				hit_wait ? "wait word" : (overrun ? "I-RAM OVERRUN" : "SLOT CAP"),
				(traps || partials) ? "DISCARDED" : "kept");
	}

	// ---- present the outputs (the DO1L-R .. DO3R-R registers) --------------
	// SAFETY PROPERTY, MANDATORY: if ANY word trapped -- OR ran with its ALU
	// undecoded -- this frame's result is arbitrary, not "slightly wrong".
	// Discard it entirely.  The DO latches themselves are chip state and are
	// left alone; it is the value handed to the caller that is zeroed, so an
	// unchecked caller is still safe.
	//
	// `partials' MUST be in this test.  Executing a word's addressing is real
	// progress and it is what lets a sample enter, but the accumulator it leaves
	// behind is not the accumulator the real chip leaves behind, so a frame full
	// of half-executed words is exactly the plausible-but-wrong audio this
	// project refuses to emit.  The day the `lo12' ALU field is decoded, these
	// words move from `partials' to the decoded set and the frame starts being
	// kept -- with no other change here.
	const bool clean = (traps == 0) && (partials == 0) && hit_wait && !overrun;
	for (int port = 0; port < 3; port++)
		for (int ch = 0; ch < 2; ch++)
			do_[port][ch] = clean ? m_do[port][ch] : 0;

	return clean;
}


void upd6383_device::dump_frame_report() const
{
	// NB: plain %u / %d only, matching the rest of this file.  (A u64 count only
	// overflows u32 after ~25 hours of emulated audio at 48 kHz.)
	logerror("upd6383: FRAME REPORT (experimental IC311 audio path)\n");
	logerror("    frames run          %u\n", u32(m_frames_run));
	logerror("    frames that TRAPPED %u (%d.%02d %%) -- their return was DISCARDED\n",
			u32(m_frames_trapped),
			u32(m_frames_run ? (100 * m_frames_trapped) / m_frames_run : 0),
			u32(m_frames_run ? ((10000 * m_frames_trapped) / m_frames_run) % 100 : 0));
	logerror("    frames with PARTIAL words (addressing executed, ALU unknown) %u\n",
			u32(m_frames_partial));
	logerror("    partial words executed, all frames %u\n", u32(m_partial_total));
	logerror("    ended on the wait word %010X: %u\n", FRAME_WAIT_WORD,
			u32(m_frames_run - m_frames_capped - m_frames_overrun));
	logerror("    ended on the %u-slot CAP:      %u\n", FRAME_SLOT_CAP, u32(m_frames_capped));
	logerror("    ended by I-RAM OVERRUN:        %u\n", u32(m_frames_overrun));
	logerror("    last frame: %u slots, %u partial, %u traps\n",
			m_last_slots, m_last_partials, m_last_traps);

	// ---- THE INPUT-STAGE AUDIT (K6) ----------------------------------------
	// The one measurement that says whether audio reaches the microcode at all.
	// It is a COMPARISON of the value the microcode read against the value this
	// device latched off the DI pins, so it can come out negative; a criterion
	// that cannot fail would not be worth printing.
	logerror("    INPUT-STAGE AUDIT (the two D-RAM cells at ptr+%u / ptr+%u, read by header w4/w8):\n",
			IN_LATCH_L_OFF, IN_LATCH_R_OFF);
	logerror("        frames in which both port reads executed  %u\n", u32(m_in_frames));
	logerror("        ... value read back == value latched off DI%d  %u   MISMATCHED %u\n",
			IN_PORT + 1, u32(m_in_ok), u32(m_in_bad));
	logerror("        ... of those, frames carrying a NON-ZERO sample  %u\n", u32(m_in_nonzero));
	logerror("        peak |sample| that entered and was read  0x%06X (%d)\n",
			u32(m_in_peak) & 0xffffff, m_in_peak);
	if (m_in_frames == 0)
		logerror("        NOTHING ENTERED THE CHIP -- the input stage never ran to completion\n");
	else if (m_in_bad != 0)
		logerror("        *** THE DEPOSIT AND THE READ DISAGREE -- the cell map is wrong ***\n");

	if (m_order_valid)
	{
		logerror("    MOST RECENT REPRESENTATIVE FRAME: %u slots, %u partial, %u traps.\n",
				m_order_slots, m_order_partials, m_order_total);
		logerror("    %u words EXECUTED before the first trap.  The first %u offending words\n",
				m_order_before, m_order_n);
		logerror("    IN EXECUTION ORDER -- THIS IS THE DECODING WORKLIST:\n");
		for (u32 i = 0; i < m_order_n; i++)
			logerror("      %2u.  iw %3u  %010X  %s\n", i, m_order_iw[i], m_order_word[i],
					upd6383_disassembler::text(m_order_word[i]));
	}
	else
	{
		logerror("    no representative frame was captured (no frame ever reached the\n");
		logerror("    frame-wait word %010X with >= %u slots -- was a program uploaded?)\n",
				FRAME_WAIT_WORD, FRAME_ORDER_MIN_SLOTS);
	}
}


//**************************************************************************
//  RESEARCH INSTRUMENTATION: THE POINTER-ORIGIN TRACE
//**************************************************************************

//  WHY THIS EXISTS
//      notes/kn5000-dsp-hi12.md sect. 5 showed that the data pointer's ORIGIN
//      cannot be pinned from the ROM: no class subset, wrap modulus or hi12
//      bit gate makes any image's pointer return to where it started (net
//      delta -87..+1149, zero in 0 of 38), and the one PROVEN pointer-load
//      form `801.0.NN.821' occurs ZERO times in the 38 effect bodies.  Its
//      stated remedy was "run the core and watch the address bus".
//
//      This is that instrument -- and running it makes visible what every
//      static search had EXCLUDED BY CONSTRUCTION.  The corpus statistic
//      "2974 words over 38 images" counts effect BODIES only; the common
//      header at I-RAM 0..59 and the algorithm-change stub at 60..82 are 83
//      words that every effect executes and that no search covered.  They are
//      in the live I-RAM, and they contain the pointer loads:
//
//          I-RAM 42  801.0.70.821   |
//          I-RAM 43  801.0.6C.827   +-  unit 0 setup, then 49: END, unit 0
//          I-RAM 44  801.0.25.825   |
//          I-RAM 50  801.0.50.821   |
//          I-RAM 51  801.0.64.827   +-  unit 1 setup, then 59: END, unit 1
//          I-RAM 52  801.0.25.825   |
//
//      MEASURED.  See notes/kn5000-dsp-pointer.md for the full argument, the
//      candidate discrimination, and the misses.
//
//  WHAT IT IS NOT
//      It is not execution of the machine.  The core stays DISABLED; this
//      walks the resident I-RAM under the decoded subset, changes no device
//      state, and produces no audio.  Everything it reports about which words
//      MOVE the pointer rests on a rule that is NOT established, and the file
//      it writes says so at the top rather than in a footnote.

void upd6383_device::write_pointer_trace(const char *path)
{
	std::ofstream f(path);
	if (!f)
		return;

	f << "NEC uPD6383GF -- data-pointer trace over the RESIDENT I-RAM\n";
	f << "Written by upd6383_device::write_pointer_trace().  See\n";
	f << "notes/kn5000-dsp-pointer.md.  The core is DISABLED; nothing here is\n";
	f << "machine execution and there is no audio.\n\n";
	f << "CAUTION, stated up front: WHICH words move the pointer is NOT\n";
	f << "established.  addr8 is a signed post-increment (MEASURED) but the set\n";
	f << "of classes that carry one is not; classes 1/3/5/6/8 provably do not\n";
	f << "(their addr8 is a bracket code, unit index or table selector), so the\n";
	f << "rule used below is `classes 2 and A move it'.  Two independent checks\n";
	f << "say that rule is still WRONG -- see the note.  Read the p821/p827/p825\n";
	f << "columns as three parallel candidates, not as an answer.\n\n";
	f << "  iw  word          fields         hi12                    d   p821 p827 p825\n";
	f << "  --  ----------    ------------   ---------------------  ---  ---- ---- ----\n";

	// three pointer registers, seeded by the header's own loads.  0x821 is the
	// PROVEN form; 0x825/0x827 are INFERRED siblings whose target register is
	// unknown, which is exactly why all three are carried side by side.
	int p821 = -1, p827 = -1, p825 = -1;

	auto dump_region = [&](const char *label, u32 first, u32 last)
	{
		util::stream_format(f, "\n--- %s (I-RAM %u..%u) ---\n", label, first, last);

		for (u32 iw = first; iw <= last && iw < IRAM_WORDS; iw++)
		{
			u64 w = 0;
			for (u32 i = 0; i < upd6383_disassembler::WORD_BYTES; i++)
				w = (w << 8) | m_iram.read_byte(iw * upd6383_disassembler::WORD_BYTES + i);
			w &= 0xfffffffffULL;

			const u16 hi = upd6383_disassembler::hi12(w);
			const u8  cl = upd6383_disassembler::class4(w);
			const u8  ad = upd6383_disassembler::addr8(w);
			const u16 lo = upd6383_disassembler::lo12(w);
			const s8  dd = s8(ad);

			// the pointer LOADS -- absolute 8-bit immediates
			if (hi == 0x801 && cl == 0)
			{
				if (lo == 0x821) p821 = ad;
				else if (lo == 0x827) p827 = ad;
				else if (lo == 0x825) p825 = ad;
			}

			const bool moves = (cl == 2 || cl == 0xa);
			util::stream_format(f, "  %3u  %010X    %03X.%X.%02X.%03X   %-21s  %+4d  ",
					iw, w, hi, cl, ad, lo,
					upd6383_disassembler::hi12_text(hi), moves ? int(dd) : 0);

			auto col = [&f](int v) { if (v < 0) f << "  -- "; else util::stream_format(f, "  %02X ", v & 0xff); };
			col(p821); col(p827); col(p825);

			// the store -- LOGGED, never performed (one bit is not a decode)
			if ((hi & upd6383_disassembler::HI_ST) && !(hi & upd6383_disassembler::HI_ESC))
				f << "  ST->mem[p]";
			if (upd6383_disassembler::cursor_fetch(w))
				f << "  cur+";
			// *** A CONTRADICTION THE INTERPRETER FOUND, reported not buried ***
			// notes/kn5000-dsp-hi12.md sect. 3 measured "bit 10 with bit 11
			// clear = END OF PROGRAM: 38 such words in 2974, exactly one per
			// image, zero anywhere else".  That corpus is the 38 effect
			// BODIES.  Run the same rule over the RESIDENT I-RAM and the
			// COMMON HEADER carries bit-10 words in its interior -- word 6
			// (400.A.00.419) is the first.  So the rule does NOT generalise
			// off the corpus it was measured on.  Either bit 10 is "end of
			// SEGMENT / return" and the header is a chain of short segments
			// (which fits the dispatch reading below), or it is not the halt
			// at all.  The trace therefore stops ONLY at a unit-index END and
			// flags every interior one.
			const bool unit_end = upd6383_disassembler::is_end(w)
					&& cl == 1 && (ad == 0x0e || ad == 0x0f);
			if (unit_end)
				util::stream_format(f, "  <== END, unit index %02X", ad);
			else if (upd6383_disassembler::is_end(w))
				f << "  <== !! bit 10 set MID-PROGRAM -- the END rule does not"
					 " generalise off the 38 body images";
			f << "\n";

			if (moves)
			{
				if (p821 >= 0) p821 = (p821 + dd) & 0xff;
				if (p827 >= 0) p827 = (p827 + dd) & 0xff;
				if (p825 >= 0) p825 = (p825 + dd) & 0xff;
			}

			if (unit_end)
				break;
		}
	};

	// The dispatch model (INFERRED, strong -- see the note): the header's two
	// segments each set a unit's pointers and end with that unit's index, the
	// body then runs and ends with the SAME index.  It is what makes four
	// separately-recorded facts one fact, including "no branch word carrying
	// the entry addresses 84 or 200 has ever been found" -- because the
	// dispatch is by unit index, not by an immediate.
	dump_region("common header, unit-0 segment", 0, 49);
	dump_region("effect body, unit 0", 84, 199);
	dump_region("common header, unit-1 segment", 50, 59);
	dump_region("effect body, unit 1", 200, 351);

	f << "\nORIGINS NAMED BY THE HEADER (MEASURED, they are in I-RAM):\n";
	f << "    unit 0   lo12 821 -> #$70   lo12 827 -> #$6C   lo12 825 -> #$25\n";
	f << "    unit 1   lo12 821 -> #$50   lo12 827 -> #$64   lo12 825 -> #$25\n";
	f << "  0x825 holds the SAME value in both segments, so it cannot be the\n";
	f << "  per-unit state pointer: both units are resident simultaneously\n";
	f << "  (MEASURED) and would alias completely.  That leaves two candidates.\n";

	osd_printf_info("upd6383: wrote pointer trace to %s\n", path);
}

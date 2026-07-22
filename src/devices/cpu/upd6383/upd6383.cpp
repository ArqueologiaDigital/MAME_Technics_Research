// license:BSD-3-Clause
// copyright-holders:Felipe Sanches
/***************************************************************************

    upd6383.cpp

    NEC uPD6383GF digital signal processor.

    *** DRAFT / RESEARCH INSTRUMENT -- MACHINE_NOT_WORKING GRADE. ***
    *** NO SOUND INTERFACE.  NO AUDIO.  INSTANTIATED DISABLED (see below). ***

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
        other word without changing any state.  There is deliberately no sound
        interface: a partially-correct effects DSP produces audio that
        DIVERGES, and plausible-but-wrong audio is worse than silence because
        nobody can hear that it is wrong.  When the ISA is known, that is the
        moment to make noise.

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

#define VERBOSE (LOG_TRAP)
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
	m_delay_config("delay", ENDIANNESS_BIG, 16, 18, -1),
	m_icount(0),
	m_pc(0), m_ucpc(0), m_sta(0), m_cnt(0),
	m_acc(0), m_accb(0), m_p(0), m_k(0), m_l(0), m_ta(0), m_tb(0),
	m_cursor(0), m_cp(0), m_dp(0), m_bp1(0), m_bp2(0), m_pr1(0), m_pr2(0),
	m_bnk(0), m_lc1(0), m_lc2(0), m_lc3(0),
	m_gf(0), m_rq(0), m_ovc(0), m_frame_done(0),
	m_host_cmd(0), m_host_pos(0), m_host_addr(0),
	m_capture_base(nullptr), m_capture_open(false),
	m_program_id(0), m_trap_total(0)
{
	std::fill(std::begin(m_stack), std::end(m_stack), 0);
	std::fill(std::begin(m_tr), std::end(m_tr), 0);
	std::fill(std::begin(m_host_word), std::end(m_host_word), 0);
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
}


void upd6383_device::device_stop()
{
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
			// TRAP AND LOG.  No state is changed -- an undecoded word must not
			// silently corrupt the model.  In particular bit 4 (= store the
			// accumulator to mem[ptr]) is NOT acted on here: one bit of a
			// 36-bit word is not a decode, and performing half a word is how a
			// draft core starts producing plausible-but-wrong results.
			trap(raw, m_pc - upd6383_disassembler::WORD_BYTES);
			(void)cl;

			if (ending)
			{
				m_frame_done = 1;
				m_icount = 0;       // "wait for the next sample" -- SPECULATIVE
			}
			continue;
		}

		LOGMASKED(LOG_EXEC, "%010X  %s\n", raw, upd6383_disassembler::text(raw));

		if (hi == 0x000 && cl == 2)
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
		else if (hi == 0x202 && (lo == 0x1d5 || lo == 0x1d4))
		{
			// mac / mac.lb -- DETERMINED by the exhaustive constraint search of
			// notes/kn5000-dsp-semantics.md sect. 3.1 (144 survivors out of
			// 19,674,720 enumerated assignments all agree), and validated by an
			// impulse response matching the transfer function of nine real ROM
			// coefficient banks at max|err| = 0.000e+00.
			//     acc += P ; P = coef[cursor++] * mem[dp] ; dp += (s8)addr8
			const u32 operand = m_dram.read_dword(m_dp) & 0xffffff;
			const u32 coef = m_cram.read_dword(m_cursor) & 0xffffff;

			if (lo == 0x1d4)
				m_tb = operand;     // "read into carry latch B" (INFERRED)

			m_acc = (m_acc + m_p) & 0xfffffffffffULL;   // 44-bit ALU
			m_k = coef;
			m_l = operand;
			m_p = u64(s64(util::sext(coef, 24)) * s64(util::sext(operand, 24))) & 0xfffffffffffULL;
			m_cursor++;
			m_dp = u8(m_dp + dd);
		}
		else if (hi == 0x212 && lo == 0x407)
		{
			// mulst -- DETERMINED uniquely, with no residual freedom, by all 144
			// survivors of the same search: the make-up gain multiplies the
			// ACCUMULATOR and the ACCUMULATOR is written to the state cell.
			//     mem[dp] <- acc ; P = coef[cursor++] * acc ; dp += (s8)addr8
			const u32 coef = m_cram.read_dword(m_cursor) & 0xffffff;
			const u32 accval = u32(m_acc & 0xffffff);

			m_dram.write_dword(m_dp, accval);
			m_k = coef;
			m_l = accval;
			m_p = u64(s64(util::sext(coef, 24)) * s64(util::sext(accval, 24))) & 0xfffffffffffULL;
			m_cursor++;
			m_dp = u8(m_dp + dd);
		}
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

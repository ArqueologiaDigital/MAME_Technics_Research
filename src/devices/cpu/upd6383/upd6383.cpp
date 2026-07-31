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
    ***
    *** AND SINCE THE SAME DAY THE ADDRESS GENERATOR RUNS FOR THE WHOLE
    *** FRAME.  The pointer post-increment and the coefficient cursor read
    *** no part of lo12, so they never needed the ALU decode; confining
    *** them to those twelve words meant the ~92 words that DID execute
    *** were addressing the wrong cells and the wrong coefficients.
    *** 199 of 285 words now execute something; 80 execute FULLY.
    *** notes/dsp-frame-advance.md.

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
        * ★ STALE AS WRITTEN UNTIL 2026-07-26 (retraction-sweep.md, P1); this
          entry used to say "`ldptr' loads a single modelled data pointer ...
          and only the 0x821 form is decoded at all".  Both halves are dead.
          `ldptr' (0x821) loads m_cp, a COEFFICIENT-space pointer -- K3 FORCED
          that it is neither the D-RAM operand pointer nor the implicit cursor;
          `ldptr.d' (0x825) loads m_dsc, the delay-DESCRIPTOR pointer (PROVEN BY
          CONSTRUCTION); `rstcur' resets m_cursor.  The chip has six pointer
          registers and the corpus shows four variants of the load
          (lo12 = 0x820/0x821/0x825/0x827).  What is genuinely UNKNOWN now is
          NARROWER and WORSE: 0x820's register is OPEN, 0x827 was falsified as
          the D-RAM origin at 0 of 85 streams, and so NOTHING IN THE DECODED SET
          LOADS m_dp AT ALL -- the operand pointer moves only by post-increment.
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

#include <cstring>
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
	m_cursor(0), m_cp(0), m_dp(0), m_dsc(0), m_bp1(0), m_bp2(0), m_pr1(0), m_pr2(0),
	m_bnk(0), m_lc1(0), m_lc2(0), m_lc3(0),
	m_gf(0), m_rq(0), m_ovc(0), m_frame_done(0), m_sp(0),
	m_host_cmd(0), m_host_pos(0), m_host_addr(0),
	m_capture_base(nullptr), m_capture_open(false),
	m_program_id(0), m_trap_total(0),
	m_in_base(0), m_in_seen_mask(0),
	m_frames_run(0), m_frames_trapped(0), m_frames_partial(0), m_frames_capped(0), m_frames_overrun(0),
	m_last_slots(0), m_last_traps(0), m_last_partials(0), m_partial_total(0),
	m_last_dp_delta(0), m_frames_dp_closed(0), m_frames_dp_measured(0),
	m_dp_delta_min(127), m_dp_delta_max(-128),
	m_calls_u0(0), m_calls_u1(0), m_rebase_agreed_u0(0), m_rebase_agreed_u1(0),
	m_in_frames(0), m_in_ok(0), m_in_bad(0), m_in_nonzero(0), m_in_peak(0),
	m_in_log_left(INPUT_LOG_FRAMES),
	m_frame_detail_left(FRAME_DETAIL_FRAMES),
	m_order_n(0), m_order_total(0), m_order_slots(0), m_order_before(0),
	m_order_partials(0), m_order_valid(false)
{
	std::fill(std::begin(m_stack), std::end(m_stack), 0);
	std::fill(std::begin(m_vec), std::end(m_vec), 0);
	std::fill(std::begin(m_tr), std::end(m_tr), 0);
	std::fill(std::begin(m_host_word), std::end(m_host_word), 0);
	std::fill(std::begin(m_order_iw), std::end(m_order_iw), 0);
	std::fill(std::begin(m_order_word), std::end(m_order_word), 0);
	std::fill(std::begin(m_in_base_hist), std::end(m_in_base_hist), 0);
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
	state_add(UPD6383_DSC,    "DSC",    m_dsc);
	state_add(UPD6383_VEC0,   "VEC0",   m_vec[0]);
	state_add(UPD6383_VEC1,   "VEC1",   m_vec[1]);
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
	save_item(NAME(m_rf));          // §97: the mode-1 register file
	if (const char *e = getenv("UPD6383_LAND"))
		m_land = std::clamp<u32>(u32(strtoul(e, nullptr, 10)), 1, 7);
	if (const char *e = getenv("UPD6383_SPEC"))
	{
		m_specmask = u64(strtoull(e, nullptr, 16));
		logerror("upd6383: §32 bisection mask UPD6383_SPEC = 0x%X\n", m_specmask);
	}
	if (const char *e = getenv("UPD6383_TRACE_FRAME"))
		m_trace_frame = u64(strtoull(e, nullptr, 10));
	//  ★ §133: unpack the bank-entry demultiplexer's mask fields ONCE, and say every
	//  one of them out loud.  A silent selector is how §121 ran seven arms that were
	//  all the same arm.
	m_bx_on       = (m_specmask & (1ull << 39)) != 0;
	m_bx_distinct = (m_specmask & (1ull << 40)) != 0;
	m_bx_sweep    = (m_specmask & (1ull << 41)) != 0;
	m_bx_sel0d    = u32((m_specmask >> 42) & 7);
	m_bx_sel0e    = u32((m_specmask >> 45) & 7);
	m_bx_f4       = u32((m_specmask >> 48) & 3);
	m_bx_f5       = u32((m_specmask >> 50) & 3);
	m_bx_supp_ta  = (m_specmask & (1ull << 52)) != 0;
	if (m_bx_on || m_bx_sweep)
		logerror("upd6383: ★ §133 DEMUX injector=%d distinct=%d sweep=%d "
				"sel0D=%d sel0E=%d f31_4=%d f31_5=%d suppressTA=%d\n",
				m_bx_on, m_bx_distinct, m_bx_sweep, m_bx_sel0d, m_bx_sel0e,
				m_bx_f4, m_bx_f5, m_bx_supp_ta);
	//  ★ §128: say the arm frame out loud.  An effect selected from the panel lands
	//  at t ~ 40-50 s = frame 1.8-2.2 M; tracing at the 420 000 default would silently
	//  describe the cold-boot default (CHORUS) instead of the selected program.
	//  ⚠ §132: the EMULATED frame rate is the tone generator's stream rate, 48 000
	//  (kn5000_tonegen.cpp), NOT the 44 100 the firmware designs its filters for.
	//  §128 printed this in 44 100ths and so overstated the arm time by 8.8 %.
	//  The same 48000/44100 = 1.0884 factor applies to every predicted FREQUENCY.
	logerror("upd6383: §128 frame trace arms after frame %u (t = %.1f s at the emulated "
			"48000 Hz frame rate)\n",
			u32(m_trace_frame), double(m_trace_frame) / 48000.0);
	//  ★ §109: say bits 28/29 out loud, so an arm can never be confused with a null.
	logerror("upd6383: §109 ACT-07 store target = %s-increment (mask bit 28 = %d)\n",
			(m_specmask & 0x10000000) ? "POST" : "PRE",
			(m_specmask & 0x10000000) ? 1 : 0);
	logerror("upd6383: §109 bit-4 store gate = %s (mask bit 29 = %d)\n",
			(m_specmask & 0x20000000) ? "b7 && f31 != 2  (the CO-EQUAL survivor)"
					: "b7 && f31 == 1  (SHIPPED)",
			(m_specmask & 0x20000000) ? 1 : 0);
	//  ★ §104 A/B (DIAGNOSTIC ONLY, off by default): suppress the ACTION-0x07 store
	//  when the bus source is SRC 0x08.  This is NOT a proposed fix -- it is the
	//  one-word counterfactual that turns "cell 0x07 goes constant across kernel
	//  iw32" from a correlation into a causal claim.  Prediction stated in advance:
	//  with it set, §104's `mem' column at body-0 iw89/90/91 must go from IDENTICAL
	//  to DIFFERS, and acc at iw90 with it.  If it does not, the mechanism is wrong.
	if (const char *e = getenv("UPD6383_AB_NOSTORE08"))
	{
		m_ab_nostore08 = (strtoul(e, nullptr, 10) != 0);
	}
	//  ★★★ §213: the store-probe fix, announced UNCONDITIONALLY so a run can never be
	//  read against the wrong accounting.  It changes NO machine state -- only which
	//  visits the §96/§109/§46 write censuses record.  See upd6383.h `m_stprobe'.
	if (const char *es = getenv("UPD6383_STPROBE"))
		m_stprobe = (strtoul(es, nullptr, 10) != 0);
	logerror("upd6383: §213 UPD6383_STPROBE = %d  (1 = store bookkeeping follows the "
			"STORE; 0 = the pre-§213 accounting, which records the §112 latch arm as "
			"a phantom store)\n", m_stprobe ? 1 : 0);
	//  ★★★ §215: the rival reading of SRC 0x0B on a NON-DELAY word.  DEFAULT OFF, and
	//  announced UNCONDITIONALLY (same rule as §209/§213) so a log can never be read
	//  against the wrong arm.  See upd6383.h `m_src0b2' and data/PREDICT_215.md.
	if (const char *e7 = getenv("UPD6383_SRC0B2"))
		m_src0b2 = (strtoul(e7, nullptr, 10) != 0);
	logerror("upd6383: §215 UPD6383_SRC0B2 = %d  (0 = SHIPPED: SRC 0x0B is the delay-read "
			"register everywhere; 1 = RIVAL: on a word with no delay access it is "
			"mem[ptr])\n", m_src0b2 ? 1 : 0);
	//  ★★★ §217: the publish schedule.  DEFAULT OFF, announced UNCONDITIONALLY so a log
	//  can never be read against the wrong arm.  See upd6383.h `m_drpub' and
	//  data/PREDICT_217.md, committed before this build.
	if (const char *e8 = getenv("UPD6383_DRPUB"))
		m_drpub = (strtoul(e8, nullptr, 10) != 0);
	logerror("upd6383: §217 UPD6383_DRPUB = %d  (0 = SHIPPED: `m_dr' is written ONLY by "
			"the §78 per-line publish, which fires only at a DELAY WORD; 1 = a delay "
			"READ also puts its datum on the bus register immediately)\n",
			m_drpub ? 1 : 0);
	//  ★★★ §220: the OVERWRITE half of §219 §8.  DEFAULT OFF, announced
	//  UNCONDITIONALLY so a log can never be read against the wrong arm.  See
	//  upd6383.h `m_noz05' and data/PREDICT_220.md, committed before this build.
	if (const char *e9 = getenv("UPD6383_NOZ05"))
		m_noz05 = u8(strtoul(e9, nullptr, 10));
	logerror("upd6383: §220/§223 UPD6383_NOZ05 = %d  (0 = SHIPPED: the site-2 bit-4 store "
			"writes cell 0x05 in kernel A at iw9/iw35/iw45; 1 = §220 DIAGNOSTIC: EVERY "
			"kernel-A site-2 store to 0x05 is suppressed -- which is EIGHT words, not "
			"three, iw9 among them; 2 = §223 DIAGNOSTIC: iw35 and iw45 ONLY, so iw9 "
			"survives)\n",
			(int)m_noz05);
	//  ★★★ §221 `§E1': the epilogue/handover OPERAND-PROVENANCE census.  READ-ONLY --
	//  it changes no decode, no route and no value; it only records WHICH ARRAY,
	//  WHICH INDEX and WHICH `iw' LAST WROTE each operand the output stage fetches.
	//  DEFAULT OFF and announced UNCONDITIONALLY (rule 8, as §220 sharpened it: a
	//  fired count printed under `if (count)' makes "fired zero times" and "never
	//  ran" the same log line).  See data/PREDICT_221.md, committed before this build.
	if (const char *e10 = getenv("UPD6383_EPIBUS"))
		m_epibus = (strtoul(e10, nullptr, 10) != 0);
	logerror("upd6383: §221 UPD6383_EPIBUS = %d  (0 = SHIPPED: no provenance tracking; "
			"1 = §E1: shadow the last writer of every D-RAM / register-file cell and of "
			"tempA/tempB/ACCA/ACCB, and census the operands of iw60..81 + the handover "
			"slots 54/152/153/200 on settled frames)\n", m_epibus ? 1 : 0);
	e1_init();
	//  ★★★ §222 `§E-D85' -- THE EPILOGUE CROSSBAR ARM.  DEFAULT OFF, announced
	//  UNCONDITIONALLY with every fired count (rule 8).  See upd6383.h §222(a) and
	//  data/PREDICT_222.md, committed before this build.
	if (const char *e11 = getenv("UPD6383_XB85"))
		m_xb85 = std::clamp<u32>(u32(strtoul(e11, nullptr, 10)), 0, 3);
	logerror("upd6383: §222 UPD6383_XB85 = %d  (0 = SHIPPED: ACT 0x03 is a no-op, SRC 0x03 "
			"is mask bit 25's accumulator, and both w63's read and w70's store use the "
			"REGISTER FILE; 1 = the full crossbar; 2 = the ARRAY ROUTE only; 3 = the "
			"LATCH+LOAD only -- 2 and 3 are the pre-registered bisection)\n", m_xb85);
	//  ★★★ §222 `§E-D0' -- the pickup address-and-provenance audit.  READ-ONLY: it
	//  changes no decode, no route and no value.
	if (const char *e12 = getenv("UPD6383_PICKUP"))
		m_pickup = (strtoul(e12, nullptr, 10) != 0);
	logerror("upd6383: §222 UPD6383_PICKUP = %d  (0 = SHIPPED: no pickup audit; 1 = census "
			"every lo12 0x1CD word -- pointer BEFORE and AFTER its own post-increment as "
			"SEPARATE columns, array+index, operand, ACCA/ACCB before and after -- plus a "
			"writer census of the two pickup cells 0x05 and 0x85 on settled frames)\n",
			m_pickup ? 1 : 0);
	if (const char *e2 = getenv("UPD6383_ROTSIGN"))
	{
		m_rotsign = (strtoul(e2, nullptr, 10) != 0);
		logerror("upd6383: §200 UPD6383_ROTSIGN = %d\n", m_rotsign ? 1 : 0);
	}
	if (const char *e3 = getenv("UPD6383_BODYIX"))
	{
		m_bodyix = (strtoul(e3, nullptr, 10) != 0);
		logerror("upd6383: §201 UPD6383_BODYIX = %d\n", m_bodyix ? 1 : 0);
	}
	if (const char *e4 = getenv("UPD6383_CFMTIX"))
	{
		m_cfmtix = (strtoul(e4, nullptr, 10) != 0);
		logerror("upd6383: §203 UPD6383_CFMTIX = %d\n", m_cfmtix ? 1 : 0);
		logerror("upd6383: §104 A/B UPD6383_AB_NOSTORE08 = %d\n", m_ab_nostore08 ? 1 : 0);
	}
	//  ★★★ §209: the two halves of the per-unit descriptor ring, INDEPENDENTLY
	//  gated so the 2x2 identifies each rather than shipping a bundle.
	//  ⚠ Announced UNCONDITIONALLY, unlike the three gates above: those log only
	//  when the env var is present, so a default run leaves no record of the arm
	//  it was in.  Same rule as the fired counts.
	if (const char *e5 = getenv("UPD6383_DSCPRE"))
		m_dscpre = (strtoul(e5, nullptr, 10) != 0);
	if (const char *e6 = getenv("UPD6383_DSCRING"))
		m_dscring = (strtoul(e6, nullptr, 10) != 0);
	logerror("upd6383: §209 UPD6383_DSCPRE = %d  UPD6383_DSCRING = %d\n",
			m_dscpre ? 1 : 0, m_dscring ? 1 : 0);
	save_item(NAME(m_p));
	save_item(NAME(m_k));
	save_item(NAME(m_l));
	save_item(NAME(m_ta));
	save_item(NAME(m_tb));
	save_item(NAME(m_cursor));
	save_item(NAME(m_cp));
	save_item(NAME(m_dp));
	save_item(NAME(m_dsc));
	save_item(NAME(m_dr));
	save_item(NAME(m_delay_ix));
	save_item(NAME(m_vec));
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
	if (!m_dts_store) { m_dts_store = std::make_unique<u32[]>(0x10000); m_dts = m_dts_store.get(); }
	m_acc = m_accb = m_p = 0;
	std::fill(std::begin(m_rf), std::end(m_rf), 0);   // §97
	for (int i = 0; i < 256; i++)
	{ m_kq_min[i] = m_kl_min[i] = INT32_MAX; m_kq_max[i] = m_kl_max[i] = INT32_MIN; }
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


//  ★ §25 follow-up instrumentation: record stores landing on 0x8C / 0x8D.
void upd6383_device::watch_store(u32 addr, s32 val, u8 site)
{
	const int w = (addr == 0x8c) ? 0 : (addr == 0x8d) ? 1
			: (addr == m_in_addr[0]) ? 2 : (addr == m_in_addr[1]) ? 3 : -1;
	if (w < 0) return;
	if (w >= 2) m_watch_word[w] = m_cur_word;
	m_watch_hits[w]++;
	if (val) m_watch_nz[w]++;
	m_watch_site[w] = site;
}

//======================================================================
//  ★★★ §109 (2026-07-30) THE STORE-SITE PROBE -- INSTRUMENTATION ONLY.
//  See upd6383.h.  Nothing here changes execution.
//
//  THE SLOT SET, and why each one is in it:
//    11   the ONE K6 input-stage word carrying ACTION 0x07 -- the only place the
//         ACT-07 store runs after exec_addressing_only() already advanced the
//         pointer, so it is the internal control on pre- vs post-increment.
//    30   `09A.A.00.200' -- bit 4 AND bit 7 with f31 = 5.  The word under test.
//    32   `000.A.FF.207' -- ACTION 0x07, delta -1.  The word under test.
//    33/34/37/39   the rest of the kernel's descending store block, as the
//         CALIBRATION: iw34 stores SRC 0x10 (the accumulator, ANCHORED) with the
//         same addr8 = 0xFF, so whatever geometry iw32 shows, iw34 must show too.
//    89/90/91/92   body-0's LFO block and its `447' follower -- the cells the
//         kernel block is accused of clobbering.
//======================================================================
//  ★★★ §109 mask bit 29: the CO-EQUAL surviving store gate.  See upd6383.h.
//  With the bit clear this is st_suppressed() exactly, bit for bit.
bool upd6383_device::st_suppressed_live(u64 w)
{
	const bool shipped = upd6383_disassembler::st_suppressed(w);
	if (!(m_speculative && (m_specmask & 0x20000000)))
		return shipped;
	const u16 hi = upd6383_disassembler::hi12(w);
	const bool alt = (hi & upd6383_disassembler::HI_B7)
			&& upd6383_disassembler::hi_f31(hi) != 2;
	if (alt != shipped) m_stgate_alt_n++;
	return alt;
}

int upd6383_device::sprobe_idx(u16 iw)
{
	//  ★ iw88 `000.2.F4.407' added 2026-07-30 AFTER the first four arms: under bit 28
	//  the §96 writer census named it as a NEW writer of the phase cell 0x07, which my
	//  writer list had missed.  It is class 2, addr8 = 0xF4 = -12, ACTION 0x07, and its
	//  SRC is 0x10 = the accumulator -- ANCHORED, and the whole word is DECODED.  So it
	//  is measured rather than reasoned about.
	//  ★ §119 added 93/94/95/98: the CHORUS delay-tap branch that iw92's move feeds
	//  under bit 34 (94 reads cell 0x10, 95 reads cell 0x50, 98 is the external
	//  delay-DRAM READ).  Without them the probe can see whether the phase LEAVES Q
	//  but not whether it reaches a consumer.
	//  ★★★ §211 added the OUTPUT STAGE's eight store-bearing words.  §150 §4:
	//  "The discriminating observable is whether the store fires at iw73 and what
	//  it writes ... Point it at slot 73 (SPROBE list) and read it -- no new
	//  mechanism needed, and it distinguishes 'the store-and-clear zeroed it' from
	//  'something else did'."  That was written 60 sections ago and never done.
	//  63/70 are the two per-unit BASE words, 64/71 the two setvec words, 72 the
	//  unit-0 LEVEL read, 73/78 THE TWO PRESENTATIONS, 77 the unit-1 level pointer
	//  and 79 the frame-closing D-RAM store.
	static const u16 SLOTS[] = { 11, 30, 32, 33, 34, 37, 39, 88, 89, 90, 91, 92,
								 93, 94, 95, 98,
								 63, 64, 70, 71, 72, 73, 77, 78 };
	for (u32 i = 0; i < sizeof(SLOTS) / sizeof(SLOTS[0]); i++)
		if (SLOTS[i] == iw) return int(i);
	return -1;
}

void upd6383_device::store_probe(u8 addr, s32 val, u8 site)
{
	if (m_sprobe_cur < 0) return;
	sprobe_t &s = m_sprobe[m_sprobe_cur];
	u32 q = 0;
	for (; q < s.nst; q++)
		if (s.st_site[q] == site && s.st_addr[q] == addr) break;
	if (q == s.nst)
	{
		if (s.nst >= SPROBE_ST) return;
		s.nst++;
		s.st_site[q] = site; s.st_addr[q] = addr;
		s.st_lo[q] = s.st_hi[q] = val; s.st_n[q] = 0;
	}
	if (val < s.st_lo[q]) s.st_lo[q] = val;
	if (val > s.st_hi[q]) s.st_hi[q] = val;
	s.st_n[q]++;
}

//  ★★★ §217: a keyed histogram over at most PROV_SLOTS distinct `iw' values, with an
//  overflow bucket.  Keyed, NOT pooled -- standing rule 10's second occurrence was
//  "36 M firings POOLED ACROSS SITES instead of keyed", which made the measurement
//  answer a different question than the one asked.  `nz' may be null.
void upd6383_device::prov_bump(u16 *key, u64 *n, u64 *nz, u32 &cnt, u64 &other,
		u16 k, bool isnz)
{
	for (u32 q = 0; q < cnt; q++)
		if (key[q] == k) { n[q]++; if (nz && isnz) nz[q]++; return; }
	if (cnt < PROV_SLOTS)
	{
		key[cnt] = k; n[cnt] = 1; if (nz) nz[cnt] = isnz ? 1 : 0;
		cnt++;
		return;
	}
	other++;
}

//  ★ §86: record a kernel D-RAM write, split by input presence.
//  ★★★ §98: the pointer window, measured live.  See upd6383.h.
u32 upd6383_device::pw_region(u16 iw)
{
	if (iw <  50) return PW_KERNEL_A;
	if (iw <  60) return PW_KERNEL_B;
	if (iw <  83) return PW_EPILOGUE;
	if (iw < 200) return PW_BODY0;
	return PW_BODY1;
}

const char *upd6383_device::pw_name(u32 r)
{
	static const char *const n[PW_NREGION] =
			{ "kernel A  (iw 0..49)", "body 0    (iw 84..199)",
			  "kernel B  (iw 50..59)", "body 1    (iw 200..332)",
			  "epilogue  (iw 60..82)" };
	return n[r];
}

void upd6383_device::pwatch(u8 cell, bool wr, bool mode1)
{
	//  Same boot gate as kwatch(): §46 established that three statistics which
	//  looked like standing faults were one contiguous boot transient ending at
	//  the last program upload.  Counting it would put phantom cells in the
	//  window.
	if (m_frames_run <= 420000) return;
	const u32 r = pw_region(m_cur_iw);
	if (mode1) (wr ? m_rw_wr : m_rw_rd)[r][cell]++;
	else       (wr ? m_pw_wr : m_pw_rd)[r][cell]++;
}

//**************************************************************************
//  ★★★ §221 `§E1' -- THE EPILOGUE / HANDOVER OPERAND-PROVENANCE CENSUS
//
//  RULE 17, mechanised.  Every earlier attempt to localise the output-stage
//  null asked "is the operand ALIVE?", and rule 15 says why that decides
//  nothing: on a live cell EVERY candidate reading scores 4/4.  This asks the
//  question liveness cannot fake -- WHICH ARRAY, WHICH INDEX, WHICH `iw' LAST
//  WROTE IT -- and it is two-sided: `F1' predicts 0 of 14 epilogue operands
//  trace to a body-0 word, and a single one that does NAMES THE ROUTING ERROR.
//  See dsp/analysis/data/PREDICT_221.md, committed before this build.
//**************************************************************************

const char *upd6383_device::e1_route_name(u8 r)
{
	switch (r)
	{
	case E1_DEF:      return "DEFAULT(no reading)";
	case E1_DRAM_PTR: return "m_dram[m_dp]";
	case E1_DRAM_IDX: return "m_dram[addr8]";
	case E1_RF_IDX:   return "m_rf[addr8]";
	case E1_CRAM:     return "m_cram[cursor]";
	case E1_ACCA:     return "ACCA";
	case E1_ACCB:     return "ACCB";
	case E1_TA:       return "tempA";
	case E1_TB:       return "tempB";
	case E1_DR:       return "m_dr(delay)";
	default:          return "?";
	}
}

void upd6383_device::e1_init()
{
	for (u32 i = 0; i < 384; i++) m_e1_map[i] = -1;
	for (u32 i = 0; i < 256; i++)
	{
		m_pv_dram_iw[i] = m_pv_dram_ziw[i] = m_pv_dram_ciw[i] = E1_PV_NONE;
		m_pv_rf_iw[i]   = m_pv_rf_ziw[i]   = m_pv_rf_ciw[i]   = E1_PV_NONE;
		m_pv_dram_fr[i] = m_pv_dram_zfr[i] = m_pv_rf_fr[i] = m_pv_rf_zfr[i] = 0;
		m_pv_dram_last[i] = m_pv_rf_last[i] = 0;
	}
	m_pv_acc_iw[0] = m_pv_acc_iw[1] = m_pv_acc_ziw[0] = m_pv_acc_ziw[1] = E1_PV_NONE;
	m_pv_acc_ciw[0] = m_pv_acc_ciw[1] = E1_PV_NONE;
	//  the watch list, IN EXECUTION ORDER so the printed table reads as the frame
	//  does: kernel-B handover, the epilogue, then body-0 exit and body-1 entry.
	static const u16 watch[] = { 54, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71,
			72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 152, 153, 200 };
	m_e1_rows = 0;
	for (u16 iw : watch)
	{
		if (m_e1_rows >= E1_SLOTS) break;
		m_e1_iw[m_e1_rows] = iw;
		m_e1_map[iw] = s8(m_e1_rows);
		m_e1_rows++;
	}
}

//  a tiny key-histogram, so a column that turns out to be MULTI-VALUED reports
//  the split instead of the last value.  Standing rule: a census that can only
//  print one answer cannot show that the answer varies.
void upd6383_device::e1_bump(u16 *keys, u64 *cnt, u32 &nk, u64 &other, u16 key)
{
	for (u32 q = 0; q < nk; q++)
		if (keys[q] == key) { cnt[q]++; return; }
	if (nk < E1_HIST) { keys[nk] = key; cnt[nk] = 1; nk++; return; }
	other++;
}

void upd6383_device::e1_record(u8 route, u16 idx, s32 L)
{
	const s8 row = m_e1_map[m_cur_iw];
	if (row < 0) return;
	e1_row_t &r = m_e1[u32(row)];
	r.word = m_cur_word;
	const int k = ((m_in_val[0] != 0) || (m_in_val[1] != 0)) ? 1 : 0;
	if (r.n[k]++ == 0) { r.lo[k] = r.hi[k] = L; }
	else { if (L < r.lo[k]) r.lo[k] = L; if (L > r.hi[k]) r.hi[k] = L; }

	//  the ROUTE and the RESOLVED INDEX, keyed together: a route that resolves to
	//  two different cells on different frames is a different fact from a route
	//  that is stable, and pooling them would hide it.
	{
		const u16 key = u16((u16(route) << 9) | (idx & 0x1ff));
		u32 q = 0;
		for (; q < r.rcnt; q++)
			if (r.route[q] == route && r.idx[q] == (idx & 0x1ff)) break;
		if (q < r.rcnt) r.rn[q]++;
		else if (r.rcnt < E1_HIST)
		{ r.route[r.rcnt] = route; r.idx[r.rcnt] = u16(idx & 0x1ff); r.rn[r.rcnt] = 1; r.rcnt++; }
		else r.rother++;
		(void)key;
	}

	//  ★ THE PROVENANCE.  Two columns, because they answer different questions:
	//  `pw' = the last word to write this operand at all (which is usually the
	//  slot before it, and says little); `pz' = the last word to leave it
	//  NON-ZERO, which is the one that names a producer.
	u16 pw = E1_PV_NONE, pz = E1_PV_NONE, pc = E1_PV_NONE;
	u64 fr = 0; bool have = false;
	switch (route)
	{
	case E1_DRAM_PTR: case E1_DRAM_IDX:
		pw = m_pv_dram_iw[idx & 0xff]; pz = m_pv_dram_ziw[idx & 0xff];
		pc = m_pv_dram_ciw[idx & 0xff];
		fr = m_pv_dram_fr[idx & 0xff]; have = (pw != E1_PV_NONE);
		break;
	case E1_RF_IDX:
		pw = m_pv_rf_iw[idx & 0xff]; pz = m_pv_rf_ziw[idx & 0xff];
		pc = m_pv_rf_ciw[idx & 0xff];
		fr = m_pv_rf_fr[idx & 0xff]; have = (pw != E1_PV_NONE);
		break;
	case E1_ACCA:
		pw = m_pv_acc_iw[0]; pz = m_pv_acc_ziw[0]; pc = m_pv_acc_ciw[0];
		fr = m_pv_acc_fr[0]; have = (pw != E1_PV_NONE);
		break;
	case E1_ACCB:
		pw = m_pv_acc_iw[1]; pz = m_pv_acc_ziw[1]; pc = m_pv_acc_ciw[1];
		fr = m_pv_acc_fr[1]; have = (pw != E1_PV_NONE);
		break;
	case E1_TA: pw = m_pv_ta_iw; pz = m_pv_ta_ziw; pc = m_pv_ta_ciw;
		fr = m_pv_ta_fr; have = (pw != E1_PV_NONE); break;
	case E1_TB: pw = m_pv_tb_iw; pz = m_pv_tb_ziw; pc = m_pv_tb_ciw;
		fr = m_pv_tb_fr; have = (pw != E1_PV_NONE); break;
	case E1_DR:
		//  §217 already carries this tag with the datum; reuse it rather than
		//  building a second, divergable one.
		pw = pz = pc = m_dr_prov_iw; fr = m_dr_prov_frame; have = (pw != E1_PV_NONE);
		break;
	case E1_CRAM:
		//  C-RAM has no I-RAM writer in this device: the host fills it.
		pw = pz = pc = E1_PV_HOST;
		break;
	default: break;                          // E1_DEF: there is no operand
	}
	e1_bump(r.pw, r.pwn, r.pwcnt, r.pwother, pw);
	e1_bump(r.pz, r.pzn, r.pzcnt, r.pzother, pz);
	e1_bump(r.pc, r.pcn, r.pccnt, r.pcother, pc);
	if (have)
	{
		const u64 age = (m_frames_run >= fr) ? (m_frames_run - fr) : 0;
		if (age < r.age_min) r.age_min = age;
		if (age > r.age_max) r.age_max = age;
	}
	if (route == E1_DEF) e1_counterfactual(L);
}

//  ★ §E1b -- THE COUNTERFACTUAL OPERANDS OF THE FOUR DECODE GAPS.
//  `w60'/`w61'/`w68'/`w78' read NOTHING, so they have no provenance -- which is
//  exactly the situation OUTPUT-STAGE-NULL_findings.md §5.1 reasons about
//  STATICALLY, from cell-content counters that are known to be broken (the
//  `D-RAM WRITES nonzero/total' column counts VISITS, not content).  Measure it:
//  record the value AND the provenance of all three candidate readings the note
//  enumerates.  If any of them is input-dependent with a body-0 provenance,
//  decoding that source WOULD be load-bearing and §5.1 is overturned.
void upd6383_device::e1_counterfactual(s32 /*L*/)
{
	const u8 a  = upd6383_disassembler::addr8(m_cur_word);
	const u8 ru = u8(a | (m_cur_unit1 ? 0x80 : 0x00));
	const u8 src = upd6383_disassembler::lo_src(m_cur_word);
	u32 q = 0;
	for (; q < m_e1cf_n; q++) if (m_e1cf[q].iw == m_cur_iw) break;
	if (q == m_e1cf_n)
	{
		if (m_e1cf_n >= E1_GAPS) return;
		m_e1cf_n++;
		m_e1cf[q].iw = m_cur_iw; m_e1cf[q].src = src;
		m_e1cf[q].ridx = ru; m_e1cf[q].didx = ru; m_e1cf[q].pidx = m_dp;
	}
	e1cf_t &c = m_e1cf[q];
	const int k = ((m_in_val[0] != 0) || (m_in_val[1] != 0)) ? 1 : 0;
	const s32 vr = s32(util::sext(m_rf[ru] & 0xffffff, 24));
	const s32 vd = s32(util::sext(m_dram.read_dword(ru) & 0xffffff, 24));
	const s32 vp = s32(util::sext(m_dram.read_dword(m_dp) & 0xffffff, 24));
	if ((k ? c.nl : c.nq)++ == 0)
	{ c.rf_lo[k] = c.rf_hi[k] = vr; c.dm_lo[k] = c.dm_hi[k] = vd; c.dp_lo[k] = c.dp_hi[k] = vp; }
	else
	{
		if (vr < c.rf_lo[k]) c.rf_lo[k] = vr;
		if (vr > c.rf_hi[k]) c.rf_hi[k] = vr;
		if (vd < c.dm_lo[k]) c.dm_lo[k] = vd;
		if (vd > c.dm_hi[k]) c.dm_hi[k] = vd;
		if (vp < c.dp_lo[k]) c.dp_lo[k] = vp;
		if (vp > c.dp_hi[k]) c.dp_hi[k] = vp;
	}
	c.n++;
	c.pidx = m_dp;
	c.rf_pw = m_pv_rf_iw[ru];
	c.dm_pw = m_pv_dram_iw[ru];
	c.dp_pw = m_pv_dram_iw[m_dp];
}

std::string upd6383_device::e1_pv_name(u16 k)
{
	switch (k)
	{
	case E1_PV_NONE: return "NONE";
	case E1_PV_HOST: return "HOST";
	case E1_PV_IN:   return "IN";
	case E1_PV_BOOT: return "BOOT";
	default:         return string_format("iw%u", k);
	}
}

void upd6383_device::e1_report() const
{
	//  ★ RULE 8, as §220 sharpened it: the fired count prints UNCONDITIONALLY,
	//  with the gate's own state beside it, so "fired zero times" and "the block
	//  was never compiled in" are never the same log line.
	logerror("upd6383: ★★★ §221 §E1 OPERAND-PROVENANCE CENSUS "
			"(UPD6383_EPIBUS = %d, fired %llu, settled frames > 900000)\n",
			m_epibus ? 1 : 0, (unsigned long long)m_epibus_fired);
	if (!m_epibus)
	{
		logerror("            (gate OFF -- no shadow tables were maintained and no row was "
				"recorded.  This is a CONTROL line, not a null.)\n");
		return;
	}
	logerror("            ⚠ §104's `L' column is STICKY (`m_last_l' survives a word that never "
			"reaches the bus); THIS census hooks the fetch itself, so a slot absent below "
			"performed NO operand fetch at all.\n");
	logerror("     iw  word        SRC  route[idx]              nq/nl            "
			"L quiet[..]        L loud[..]         prov LAST-WRITER        prov LAST-NONZERO       "
			"prov PRODUCER(changed)  age\n");

	u32 f1_body0 = 0, f1_body1 = 0, zero_rows = 0, live_rows = 0;
	std::string f1_where, f1b_where;
	for (u32 i = 0; i < m_e1_rows; i++)
	{
		const e1_row_t &r = m_e1[i];
		const u16 iw = m_e1_iw[i];
		if (!r.n[0] && !r.n[1]) continue;             // never fetched -- see the note above
		std::string rt;
		for (u32 q = 0; q < r.rcnt; q++)
			rt += string_format("%s%s[%02X]x%llu", q ? "," : "",
					e1_route_name(r.route[q]), r.idx[q],
					(unsigned long long)r.rn[q]);
		if (r.rother) rt += string_format(",+%llu", (unsigned long long)r.rother);
		std::string pw, pz, pc;
		for (u32 q = 0; q < r.pwcnt; q++)
			pw += string_format("%s%s:%llu", q ? "," : "", e1_pv_name(r.pw[q]),
					(unsigned long long)r.pwn[q]);
		for (u32 q = 0; q < r.pzcnt; q++)
			pz += string_format("%s%s:%llu", q ? "," : "", e1_pv_name(r.pz[q]),
					(unsigned long long)r.pzn[q]);
		for (u32 q = 0; q < r.pccnt; q++)
			pc += string_format("%s%s:%llu", q ? "," : "", e1_pv_name(r.pc[q]),
					(unsigned long long)r.pcn[q]);
		const bool live = (r.lo[0] != r.hi[0]) || (r.lo[1] != r.hi[1])
				|| (r.n[0] && r.n[1] && r.lo[0] != r.lo[1]);
		const bool zero = !r.lo[0] && !r.hi[0] && !r.lo[1] && !r.hi[1];
		if (zero) zero_rows++;
		if (live) live_rows++;
		logerror("    %3u  %010llX  %02X  %-24s %llu/%llu  %11d..%-11d %11d..%-11d  %-22s  %-22s  %-22s  %llu..%llu %s\n",
				iw, (unsigned long long)r.word,
				upd6383_disassembler::lo_src(r.word), rt.c_str(),
				(unsigned long long)r.n[0], (unsigned long long)r.n[1],
				r.lo[0], r.hi[0], r.lo[1], r.hi[1], pw.c_str(), pz.c_str(), pc.c_str(),
				(unsigned long long)(r.age_min == ~0ull ? 0 : r.age_min),
				(unsigned long long)r.age_max, live ? "*" : "=");

		//  ★★★ F1 / F1b -- THE DECISIVE TEST.  Provenance, not liveness (RULE 17).
		//  An epilogue operand whose LAST NON-ZERO WRITER is a body word means the
		//  epilogue IS wired to the bodies and the loss is a routing error that can
		//  be named.  F1 is BODY 0 (iw84..153); F1b is BODY 1 (iw200..332) and is
		//  PREDICTED to occur once, at w65 via m_rf[0x8F] -- pre-registered so a
		//  pass is not misread as a fail.
		//  ⚠ SCAN ALL THREE COLUMNS.  Grading F1 on the LAST-NON-ZERO column alone
		//  MISSES the case that matters most: a cell a body writes EVERY FRAME WITH
		//  ZERO has no non-zero writer at all, so the wiring is invisible in that
		//  column while being plain in the last-writer one.  Measured in arm A:
		//  `w65's `m_rf[0x8F]' is written by `iw332' -- body 1's LAST word -- 540 000
		//  times, and its non-zero column is NONE.  A test that could not see that
		//  would have called an existing link an absence.
		if (iw >= 60 && iw <= 81)
		{
			const u16 *cols[3] = { r.pw, r.pz, r.pc };
			const u32  cnts[3] = { r.pwcnt, r.pzcnt, r.pccnt };
			static const char *cn[3] = { "w", "z", "p" };
			for (u32 c = 0; c < 3; c++)
				for (u32 q = 0; q < cnts[c]; q++)
				{
					const u16 k = cols[c][q];
					if (k >= 84 && k <= 153)
					{ f1_body0++; f1_where += string_format(" w%u<-iw%u(%s)", iw, k, cn[c]); }
					else if (k >= 200 && k <= 332)
					{ f1_body1++; f1b_where += string_format(" w%u<-iw%u(%s)", iw, k, cn[c]); }
				}
		}
	}
	logerror("            rows with an operand identically ZERO in both buckets: %u | rows whose "
			"operand VARIES: %u\n", zero_rows, live_rows);
	logerror("upd6383: ★★★ §221 F1 (RULE 17, the decisive one): epilogue operands (iw60..81) whose "
			"LAST-NON-ZERO provenance names BODY 0 (iw84..153): %u%s  -- PREDICTED 0; >= 1 "
			"OVERTURNS OUTPUT-STAGE-NULL_findings.md §5.1 and NAMES the routing error\n",
			f1_body0, f1_where.c_str());
	logerror("upd6383: ★ §221 F1b: ...naming BODY 1 (iw200..332): %u%s  -- PREDICTED >= 1, at w65 "
			"via m_rf[0x8F] (§99 8F:1176000).  A 0 here is a MISS, not a pass\n",
			f1_body1, f1b_where.c_str());

	//  ★★★ F2 -- the PRESENTATION's own operand.  `w73' SOURCES the accumulator
	//  (SRC 0x10, ANCHORED), so its provenance is the accumulator's last non-zero
	//  writer.  PREDICTED: a KERNEL-B word (iw50..59), never a body-0 one.
	{
		const s8 row = m_e1_map[73];
		if (row < 0 || (!m_e1[u32(row)].n[0] && !m_e1[u32(row)].n[1]))
			logerror("upd6383: ⚠ §221 F2: w73 recorded NO operand fetch -- the census cannot "
					"grade the presentation's own operand.  Treat F2 as NOT RUN.\n");
		else
		{
			const e1_row_t &r = m_e1[u32(row)];
			std::string hz, hp; u64 tot = 0, kb = 0, b0 = 0;
			for (u32 q = 0; q < r.pzcnt; q++)
				hz += string_format("%s%s:%llu", q ? " " : "", e1_pv_name(r.pz[q]),
						(unsigned long long)r.pzn[q]);
			for (u32 q = 0; q < r.pccnt; q++)
			{
				hp += string_format("%s%s:%llu", q ? " " : "", e1_pv_name(r.pc[q]),
						(unsigned long long)r.pcn[q]);
				tot += r.pcn[q];
				if (r.pc[q] >= 50 && r.pc[q] <= 59) kb += r.pcn[q];
				if (r.pc[q] >= 84 && r.pc[q] <= 153) b0 += r.pcn[q];
			}
			logerror("upd6383: ★★★ §221 F2: ACCA at w73 -- LAST-NON-ZERO writer: %s | "
					"PRODUCER (last writer that CHANGED it): %s | kernel B (iw50..59) %llu of "
					"%llu (%.2f %%) | BODY 0 (iw84..153) %llu\n"
					"            ⚠ ONE HOP.  A word that re-writes the SAME constant is the "
					"last non-zero writer without producing anything -- which is why the "
					"PRODUCER column exists.  Neither column traces the whole chain.\n",
					hz.c_str(), hp.c_str(), (unsigned long long)kb, (unsigned long long)tot,
					tot ? 100.0 * double(kb) / double(tot) : 0.0, (unsigned long long)b0);
		}
	}

	//  ★★★ F3 -- THE CALIBRATION THAT CAN FAIL.  `w72' must resolve to index 0x06
	//  with L = 4 194 304 in both buckets.  If it does not, the instrument is
	//  mis-wired and NO OTHER NUMBER IN THIS RUN MAY BE QUOTED (the §46
	//  unguarded-sample trap, fourth occurrence).
	{
		const s8 row = m_e1_map[72];
		bool ok = false; s32 lq = 0, ll = 0; u16 gotidx = 0xffff; u8 gotroute = E1_NONE;
		if (row >= 0)
		{
			const e1_row_t &r = m_e1[u32(row)];
			if (r.rcnt) { gotroute = r.route[0]; gotidx = r.idx[0]; }
			lq = r.lo[0]; ll = r.lo[1];
			ok = (r.n[0] || r.n[1]) && r.rcnt == 1 && gotidx == 0x06
					&& r.lo[0] == 4194304 && r.hi[0] == 4194304
					&& r.lo[1] == 4194304 && r.hi[1] == 4194304;
		}
		logerror("upd6383: ★★★ §221 F3 CALIBRATION (w72 = the host's unit-0 OUTPUT LEVEL): "
				"route %s idx %02X  L quiet %d loud %d  ==>  %s\n",
				e1_route_name(gotroute), gotidx, lq, ll,
				ok ? "PASS -- the census resolves a KNOWN cell to its KNOWN value"
				   : "★ VOID -- instrument mis-wired; NO OTHER NUMBER IN THIS RUN MAY BE QUOTED");
	}

	//  ★★★ §E1b -- the COUNTERFACTUAL operands of the four decode gaps.
	logerror("upd6383: ★★★ §221 §E1b COUNTERFACTUAL OPERANDS OF THE DECODE GAPS "
			"(what SRC 0x01/0x05/0x06/0x0A WOULD have read under each candidate addressing)\n");
	if (!m_e1cf_n)
		logerror("            (no gap slot was reached -- if the four SRC codes are still "
				"counted by `SRC CODES STILL READING ZERO', this instrument is mis-wired)\n");
	for (u32 q = 0; q < m_e1cf_n; q++)
	{
		const e1cf_t &c = m_e1cf[q];
		logerror("            iw%-3u SRC %02X n=%llu (q %llu / l %llu) | m_rf[%02X] q %d..%d l %d..%d "
				"prov %s | m_dram[%02X] q %d..%d l %d..%d prov %s | m_dram[m_dp=%02X] q %d..%d "
				"l %d..%d prov %s\n",
				c.iw, c.src, (unsigned long long)c.n,
				(unsigned long long)c.nq, (unsigned long long)c.nl,
				c.ridx, c.rf_lo[0], c.rf_hi[0], c.rf_lo[1], c.rf_hi[1], e1_pv_name(c.rf_pw).c_str(),
				c.didx, c.dm_lo[0], c.dm_hi[0], c.dm_lo[1], c.dm_hi[1], e1_pv_name(c.dm_pw).c_str(),
				c.pidx, c.dp_lo[0], c.dp_hi[0], c.dp_lo[1], c.dp_hi[1], e1_pv_name(c.dp_pw).c_str());
	}
}

//**************************************************************************
//  ★★★ §222 `§E-D0' -- THE PICKUP ADDRESS-AND-PROVENANCE AUDIT.  READ-ONLY.
//
//  IW205-DRAM-D0_findings.md §6 asked for exactly this and named its own wrong
//  numbers.  Two halves:
//
//    (1) every `lo12 == 0x1CD' word -- the per-unit INPUT PICKUP, 38 of 38
//        corpus images place the first one at base+0 against a 2.1 % null --
//        with the pointer BEFORE and AFTER its own post-increment as SEPARATE
//        COLUMNS.  `F1's named wrong number is `0xD0' at iw205: an instrument
//        that samples m_dp after the post-increment reports the cell the NEXT
//        word reads, and that mis-reading survived two sections.
//
//    (2) a writer census of the two PICKUP CELLS ONLY, 0x05 and 0x85, over
//        EVERY write route in the device, split by ARRAY (m_dram / m_rf) and by
//        SITE.  `F2': does ANY route write D-RAM[0x85]?  Predicted none -- and a
//        failure NAMES the word that is supposed to fill the reverb's input,
//        which is the better outcome.
//        ⚠ The boot zeroing writes 0x50..0x53 and can never name 0x05 or 0x85,
//        so it is out of scope BY CONSTRUCTION rather than by omission.
//
//  ⚠ This exists because `D-RAM WRITES (nonzero/total)' CANNOT answer either
//  question: at :1503 it counts VISITS, and at :3671 it tests `L' -- the datum --
//  rather than the cell.  A statistic that cannot distinguish "measured zero"
//  from "not measured" is the defect this instrument is built not to repeat.
//**************************************************************************

void upd6383_device::pk_write(u8 idx, u32 v, u8 site, bool rf, u16 iw)
{
	if (!m_pickup || m_frames_run <= 900000) return;      // RULE 16
	if (idx != 0x05 && idx != 0x85) return;               // the two pickup cells ONLY
	u32 q = 0;
	for (; q < m_pkw_rows; q++)
		if (m_pkw[q].idx == idx && m_pkw[q].rf == rf
				&& m_pkw[q].site == site && m_pkw[q].iw == iw) break;
	if (q == m_pkw_rows)
	{
		if (m_pkw_rows >= PKW_ROWS) { m_pkw_over++; return; }
		m_pkw[q].idx = idx; m_pkw[q].rf = rf; m_pkw[q].site = site; m_pkw[q].iw = iw;
		m_pkw_rows++;
	}
	const u32 b = ((m_in_val[0] != 0) || (m_in_val[1] != 0)) ? 1 : 0;
	const s32 sv = s32(util::sext(v & 0xffffff, 24));
	m_pkw[q].n++;
	m_pkw[q].lo[b] = std::min(m_pkw[q].lo[b], sv);
	m_pkw[q].hi[b] = std::max(m_pkw[q].hi[b], sv);
}

void upd6383_device::pk_fetch(u8 dp_pre, u8 route, u16 idx, s32 L)
{
	m_pickup_fired++;
	u32 q = 0;
	for (; q < m_pk_rows; q++) if (m_pk[q].iw == m_cur_iw) break;
	if (q == m_pk_rows)
	{
		if (m_pk_rows >= PK_ROWS) { m_pk_over++; m_pk_pending = -1; return; }
		m_pk[q].iw = m_cur_iw; m_pk[q].word = m_cur_word;
		m_pk[q].dp_pre = dp_pre; m_pk[q].route = route; m_pk[q].idx = idx;
		m_pk_rows++;
	}
	else
	{
		if (m_pk[q].dp_pre != dp_pre) m_pk[q].pre_var++;
		if (m_pk[q].route != route || m_pk[q].idx != idx) m_pk[q].route_var++;
	}
	const u32 b = ((m_in_val[0] != 0) || (m_in_val[1] != 0)) ? 1 : 0;
	const s64 a = s64(util::sext(m_acc, 44)), bb = s64(util::sext(m_accb, 44));
	m_pk[q].n[b]++;
	m_pk[q].l_lo[b] = std::min(m_pk[q].l_lo[b], L);
	m_pk[q].l_hi[b] = std::max(m_pk[q].l_hi[b], L);
	m_pk[q].pa_lo[b] = std::min(m_pk[q].pa_lo[b], a);
	m_pk[q].pa_hi[b] = std::max(m_pk[q].pa_hi[b], a);
	m_pk[q].pb_lo[b] = std::min(m_pk[q].pb_lo[b], bb);
	m_pk[q].pb_hi[b] = std::max(m_pk[q].pb_hi[b], bb);
	m_pk_pending = s16(q);
}

void upd6383_device::pk_after()
{
	const u32 q = u32(m_pk_pending);
	m_pk_pending = -1;
	if (q >= m_pk_rows) return;
	m_pickup_post++;
	const u32 b = ((m_in_val[0] != 0) || (m_in_val[1] != 0)) ? 1 : 0;
	const s64 a = s64(util::sext(m_acc, 44)), bb = s64(util::sext(m_accb, 44));
	if (!m_pk[q].npost[0] && !m_pk[q].npost[1]) m_pk[q].dp_post = m_dp;
	else if (m_pk[q].dp_post != m_dp) m_pk[q].post_var++;
	m_pk[q].npost[b]++;
	m_pk[q].qa_lo[b] = std::min(m_pk[q].qa_lo[b], a);
	m_pk[q].qa_hi[b] = std::max(m_pk[q].qa_hi[b], a);
	m_pk[q].qb_lo[b] = std::min(m_pk[q].qb_lo[b], bb);
	m_pk[q].qb_hi[b] = std::max(m_pk[q].qb_hi[b], bb);
}

void upd6383_device::pk_report() const
{
	//  rule 8, §220-sharpened: printed UNCONDITIONALLY, with the gate's state beside
	//  it, so "fired zero times" can never look like "never ran".
	logerror("upd6383: ★★★ §222 §E-D0 PICKUP AUDIT (UPD6383_PICKUP = %d): fetches %llu, "
			"post-increment records %llu, rows %u (PREDICTED 5), dropped %u | writer rows "
			"%u, dropped %u\n",
			m_pickup ? 1 : 0, (unsigned long long)m_pickup_fired,
			(unsigned long long)m_pickup_post, m_pk_rows, m_pk_over,
			m_pkw_rows, m_pkw_over);
	if (!m_pickup) return;
	logerror("upd6383:    lo12 0x1CD -- THE PER-UNIT INPUT PICKUP.  dpPRE is the cell the "
			"word READS; dpPOST is the cell it PARKS for the NEXT word.  They differ, and "
			"quoting dpPOST as the operand address is the trap that cost §1.2, §104's dp "
			"column and §221's w79.\n");
	logerror("upd6383:      iw  word        dpPRE dpPOST var  route[idx]           "
			"nq/nl            L quiet / loud                ACCA after quiet / loud\n");
	for (u32 q = 0; q < m_pk_rows; q++)
	{
		const pk_row_t &r = m_pk[q];
		logerror("upd6383:     %3u %010llX   %02X    %02X   %u/%u/%u  %-14s[%02X] %llu/%llu  "
				"%11d..%-11d %11d..%-11d  %lld..%lld %lld..%lld\n",
				r.iw, (unsigned long long)r.word, r.dp_pre, r.dp_post,
				r.pre_var, r.post_var, r.route_var,
				e1_route_name(r.route), r.idx,
				(unsigned long long)r.n[0], (unsigned long long)r.n[1],
				r.n[0] ? r.l_lo[0] : 0, r.n[0] ? r.l_hi[0] : 0,
				r.n[1] ? r.l_lo[1] : 0, r.n[1] ? r.l_hi[1] : 0,
				(long long)(r.npost[0] ? r.qa_lo[0] : 0),
				(long long)(r.npost[0] ? r.qa_hi[0] : 0),
				(long long)(r.npost[1] ? r.qa_lo[1] : 0),
				(long long)(r.npost[1] ? r.qa_hi[1] : 0));
		logerror("upd6383:         ACCB before %lld..%lld ‖ %lld..%lld   ACCB after %lld..%lld "
				"‖ %lld..%lld   ACCA before %lld..%lld ‖ %lld..%lld\n",
				(long long)(r.n[0] ? r.pb_lo[0] : 0), (long long)(r.n[0] ? r.pb_hi[0] : 0),
				(long long)(r.n[1] ? r.pb_lo[1] : 0), (long long)(r.n[1] ? r.pb_hi[1] : 0),
				(long long)(r.npost[0] ? r.qb_lo[0] : 0),
				(long long)(r.npost[0] ? r.qb_hi[0] : 0),
				(long long)(r.npost[1] ? r.qb_lo[1] : 0),
				(long long)(r.npost[1] ? r.qb_hi[1] : 0),
				(long long)(r.n[0] ? r.pa_lo[0] : 0), (long long)(r.n[0] ? r.pa_hi[0] : 0),
				(long long)(r.n[1] ? r.pa_lo[1] : 0), (long long)(r.n[1] ? r.pa_hi[1] : 0));
	}
	logerror("upd6383:    WRITERS OF THE TWO PICKUP CELLS (settled frames only).  site: "
			"1=K6 bit-4  2=exec_alu bit-4  3=ACT-07  4=HOST tag-0x15  5=input latch  "
			"6=ACT 0x0D/0x0E case 4  7=§106 mirror  8=bx_stim.  iw FFFF=HOST FFFE=IN\n");
	for (u32 c = 0; c < 2; c++)
	{
		const u8 cell = c ? 0x85 : 0x05;
		for (u32 arr = 0; arr < 2; arr++)
		{
			u32 seen = 0;
			for (u32 q = 0; q < m_pkw_rows; q++)
			{
				const pk_wr_t &w = m_pkw[q];
				if (w.idx != cell || (w.rf ? 1u : 0u) != arr) continue;
				seen++;
				logerror("upd6383:      %s[%02X] site %u iw %u  n %llu  val quiet %d..%d "
						"loud %d..%d\n",
						arr ? "m_rf " : "D-RAM", cell, w.site, w.iw,
						(unsigned long long)w.n, w.lo[0] == 0x7fffffff ? 0 : w.lo[0],
						w.hi[0] == -0x7fffffff - 1 ? 0 : w.hi[0],
						w.lo[1] == 0x7fffffff ? 0 : w.lo[1],
						w.hi[1] == -0x7fffffff - 1 ? 0 : w.hi[1]);
			}
			if (!seen)
				logerror("upd6383:      %s[%02X]  NO WRITER AT ALL on settled frames\n",
						arr ? "m_rf " : "D-RAM", cell);
		}
	}
}

//  ★★★ §99: one rule for both store sites.  See upd6383.h.
//  ★ §222: the two callers now ALSO agree about the unit rebase -- see upd6383.h §222(c).
//  `site' and `force_dram' are §222's; both default to the shipped behaviour.
void upd6383_device::store_mode(u8 mode, u8 dest, u32 v, u8 site, bool force_dram)
{
	//  ★★★ §106 DIAGNOSTIC (mask bit 26): mirror the kernel's 0x06 result into 0x05
	//  -- ⛔ RUN IN §220 AND REFUTED.  DEAD-END 30.  DO NOT FLIP IT.
	//  §220 armed it for the first time (arm `data/B_mirror06_220.log.gz'): it FIRED
	//  5 881 351 times -- exactly 5 per kernel-A pass, at `iw19/21/27/33/39' (mode 2,
	//  dest 0x06) and NOT at `iw72' (mode 1, so §99 routes it to the register file) --
	//  and body 0's §104 pickup at `iw84' stayed 0 in BOTH buckets, because every one
	//  of those sites is UPSTREAM of `iw45', whose zero store is the last write to
	//  0x05 before the CALL at `iw49'.  Worse, it made kernel A STRICTLY LESS
	//  input-dependent (s104: acc 27->22, mem 21->10, L 18->12): with `iw35' reading
	//  `iw33's mirrored constant 6 039 795, the accumulator at `iw38' goes constant,
	//  so `iw39's store to 0x06 goes constant, and THAT propagates across the frame
	//  boundary into the next frame's `iw12..iw21'.  ⇒ the mirror DESTROYS input
	//  dependence; it does not create it.
	//  ★ The question it was built to ask was answered the other way, by `m_noz05'
	//  (§220, exec_alu below): cell 0x05 IS body 0's pickup -- suppress `iw35'/`iw45'
	//  and body 0 goes from 0/0/0 input-dependent slots to 28/32/28.
	//  ---- the original §106 rationale, kept because it is still the right question:
	//  §105 called the deposit/pickup mismatch an OFF-BY-ONE.  It is not: the
	//  kernel's audio pair is ADJACENT (0x06/0x07) while the body's pickup is
	//  base+0 / base+2 = 0x05/0x07 (stride 2, §94, 12 of 12 reverbs).  No single
	//  offset aligns a stride-1 pair to a stride-2 pair, and the kernel's window
	//  cannot slide anyway -- the frame closure pins it, residue exactly 0.
	//
	//  So instead of moving a FORCED anchor on a premise that does not hold, this
	//  MIRRORS the kernel's 0x06 result into 0x05 as well, to ask ONE question:
	//  is base+0 the right pickup?  Two-sided:
	//    * if body 0's accumulator becomes input-dependent, the pickup model is
	//      right and the DEPOSIT ADDRESS is the defect;
	//    * if it does not, base+0 is not an input cell either and the whole
	//      pair identification is wrong -- which is worth as much.
	//  It deliberately does NOT touch 0x07, so the CHORUS LFO phase cell keeps
	//  whatever it has and the two effects stay separable.
	if (m_speculative && (m_specmask & 0x4000000) && mode != 1 && dest == 0x06)
	{
		m_dram.write_dword(0x05, v & 0xffffff);
		pv_wr_dram(0x05, v);                                  // ★ §221 §E1
		pk_write(0x05, v, 7, false, m_cur_iw);                // ★ §222 §E-D0
		m_mirror06_n++;
	}
	const bool m1 = (mode == 1);
	//  ★ §222 §E-D85: `force_dram' is the NARROW form of mask bit 23 -- it moves ONE
	//  word (w70) instead of the five sites bit 23 controls, three of which decide the
	//  output path.  Bit 23 itself is a filed DEAD END (PREDICT_D0_producer.md §1).
	if (m1 && m_speculative && (m_specmask & 0x800000) && !force_dram)
	{
		m_rf[dest] = v & 0xffffff;
		pv_wr_rf(dest, v, m_cur_iw);                          // ★ §221 §E1
		pk_write(dest, v, site, true, m_cur_iw);              // ★ §222 §E-D0
		m_rf_st[dest]++;
	}
	else
	{
		m_dram.write_dword(dest, v & 0xffffff);
		pv_wr_dram(dest, v);                                  // ★ §221 §E1
		pk_write(dest, v, site, false, m_cur_iw);             // ★ §222 §E-D0
	}
	//  the WORD's mode, not the routing decision -- so the census stays honest
	//  with the bit off as well as on.
	pwatch(dest, true, m1);
}

void upd6383_device::kwatch(u8 cell, s32 v)
{
	if (m_frames_run <= 420000) return;   // ★ §95: ALL slots, not just iw < 60 --
	                                      //   the epilogue (60..82) holds the per-unit
	                                      //   deposit pair iw72 -> 0x06, iw77 -> 0x86
	const bool nz = (m_in_val[0] != 0) || (m_in_val[1] != 0);
	s32 &lo = nz ? m_kl_min[cell] : m_kq_min[cell];
	s32 &hi = nz ? m_kl_max[cell] : m_kq_max[cell];
	if (v < lo) lo = v;
	if (v > hi) hi = v;
	m_kw_n[cell]++;
	//  ★ §96: WHICH word writes it?  §71 (host) and §86 (kernel) both claim 0x06.
	//  §98: 0x85 and 0x8A added -- the live pointer window shows body 1 READS 0x85
	//  and NO region writes it with input-dependent data, and kernel B writes 0x8A
	//  where symmetry with kernel A wants 0x85.  Name the writers.
	//  §110: 0x05 added.  The iw11 timing fix made cell 0x05 input-dependent when
	//  WRITTEN, yet §104's residency column still reports body 0 reading it as
	//  constant -- so something overwrites it between deposit and pickup, exactly as
	//  iw32 does to 0x07.  Name the writers, in execution order.
	//  ★★★ §219 -- AND THIS CENSUS ANSWERED IT, IN EVERY LOG SINCE.  Cell 0x05 is
	//  THE UNIT-0 SEND (body 0's input pickup, `[05r]' in §98's window) and it has
	//  FOUR writers per frame: `iw9' (`mac (p),(p)-1') and `iw11' DEPOSIT the audio
	//  -- §86 grades the cell INPUT-DEPENDENT when written, loud [0 .. 16 760 298] --
	//  and then `iw35' and `iw45' OVERWRITE it before the CALL at `iw49'.
	//  §104's residency, same log, states the destruction slot by slot: `mem' under
	//  the pointer is INPUT-DEPENDENT before `iw35', the constant 4 194 304
	//  (= acc_to_datum(2^38), the accumulator `iw34' leaves) at `iw36..iw45', and
	//  0 at `iw46' and at body 0's own `iw84'.  `iw35's store also plants the
	//  constant that `iw36'/`iw37' re-read as the multiplicand, which is why `P'
	//  -- and the accumulator from `iw39' on -- stops depending on the input.
	//  ⇒ ONE store, `iw35', accounts for both deaths.  DO NOT look for the send
	//  defect in a SOURCE-field decode; see the `case 0x0B' note below.
	//  §120: 0x0E/0x0F/0x10 added.  §119's verifier argues these are the real
	//  modulation cells -- small magnitudes (0..264 / 0..203, tap-offset sized) and
	//  fed by CHORUS's two table-lookup idioms, producing the quadrature pair the
	//  disassembly header names.  Name their writers and measure their ranges.
	if ((cell == 0x05 || cell == 0x06 || cell == 0x07 || cell == 0x0e || cell == 0x0f
			|| cell == 0x10 || cell == 0x85 || cell == 0x86
			|| cell == 0x87 || cell == 0x8a) && m_kw_who_n < 40)
	{
		bool seen = false;
		for (u32 q = 0; q < m_kw_who_n; q++)
			if (m_kw_who[q] == m_cur_iw && m_kw_cell[q] == cell) seen = true;
		if (!seen)
		{
			m_kw_who[m_kw_who_n] = m_cur_iw;
			m_kw_cell[m_kw_who_n] = cell;
			m_kw_word[m_kw_who_n] = m_cur_word;
			m_kw_who_n++;
		}
	}
}

void upd6383_device::device_stop()
{
	if (m_frames_run != 0)
	{
		dump_frame_report();
		//  ★ §130: the rebase's FIRED-COUNT.  0 with the bit off is the null arm;
		//  0 with the bit ON would mean the gate never ran and any "no change"
		//  reading of the arm would be an artefact rather than a result.
		logerror("upd6383: §130 per-unit coefficient-cursor rebase (mask bit 38 = %d): "
				"FIRED %u times\n",
				(m_specmask & 0x4000000000ull) ? 1 : 0, u32(m_cursor_rebase_n));
		//  ★ §138: the output-stage erasure guard.  0 with the bit off is the null.
		{   //  ★★★ §157 THE DECIDING CENSUS: per I-RAM SLOT, so voices cannot pool.
			//  A real sweep gives each slot a NON-ZERO range; four signed constants
			//  give every slot range 0.  §155's per-cell figure cannot tell these
			//  apart, because CHORUS's depths are +240 +240 -240 -240.
			std::string sl;
			for (u32 q = 0; q < 384; q++)
				if (m_tapslot_seen[q])
					sl += string_format(" iw%u:%d..%d(r%d)", q, m_tapslot_lo[q],
							m_tapslot_hi[q], m_tapslot_hi[q] - m_tapslot_lo[q]);
			logerror("upd6383: ★★ §157 TAPMOD PER SLOT:%s\n",
					sl.empty() ? " (none)" : sl.c_str());
		}
		{   //  ★ §153: did the tap actually SWEEP?  A correct depth gives a range
			//  of about 2 x |depth| samples; 0 means the modulation never reached
			//  the address, which is the state this change exists to end.
			std::string ln;
			for (u32 k = 0; k < 64; k++)
				if (m_tap_seen[k] && m_tap_hi[k] != m_tap_lo[k])
					ln += string_format(" [%02X]%d..%d(range %d)", k, s32(m_tap_lo[k]),
							s32(m_tap_hi[k]), s32(m_tap_hi[k]) - s32(m_tap_lo[k]));
			logerror("upd6383: ★ §153 TAP MODULATION (mask bit 60 = %d): FIRED %u | "
					"tapmod excursion per cell:%s\n", (m_specmask & (1ull << 60)) ? 1 : 0,
					u32(m_tapmod_n), ln.empty() ? " NONE -- the modulation term never moved" : ln.c_str());
		}
		//  ⛔ §156 fix: this printed bit 57's state while reporting firings driven by
		//  bit 58 or 59 -- a gate reporting the wrong gate.  Name whichever is active.
		logerror("upd6383: ★ §145 SRC 0x00 = coef [%s]: FIRED %u times\n",
				(m_specmask & (1ull << 59)) ? "bit 59: f98==1 && coeff_consumer"
				: (m_specmask & (1ull << 58)) ? "bit 58: coeff_consumer only"
				: (m_specmask & (1ull << 57)) ? "bit 57: ALL SRC 0x00 words"
				: "OFF", u32(m_src00_coef_n));
		logerror("upd6383: ★ §142 ACT 0x0D/0x0E accumulator write (mask bit 56 = %d): "
				"routed to ACCB %u times\n", (m_specmask & (1ull << 56)) ? 1 : 0, u32(m_acc_w_unit1_n));
		logerror("upd6383: ★ §138 stale-LOAD guard (mask bit 55 = %d): FIRED %u times "
				"| ⚠ a non-zero DO1 means NOTHING until §70 ACCA min != max\n",
				(m_specmask & (1ull << 55)) ? 1 : 0, u32(m_stale_load_n));
		//  ★ §136: which half of the multiplier register file did the class-A ACT-07
		//  latch write, and did the multiply actually READ the input latch?
		logerror("upd6383: ★ §136 class-A ACT-07 latch: -> PRODUCT m_p %u times, "
				"-> INPUT m_k %u times (bit 54 = %d) | multiply reads the INPUT LATCH: "
				"%s (§40, bit 4 = %d)\n",
				m_act07_latchp_n, m_act07_latchk_n,
				(m_specmask & (1ull << 54)) ? 1 : 0,
				(m_specmask & 0x10) ? "YES" : "no -- it uses the freshly-read coef",
				(m_specmask & 0x10) ? 1 : 0);
		logerror("upd6383: PRESENTATION WORDS: %d executed, %d wrote NON-ZERO, datum peak %d\n",
				u32(m_pres_seen), u32(m_pres_nonzero), m_pres_peak);
		logerror("upd6383:   raw accumulator peak at presentation = %lld (datum would be %lld)\n",
				(long long)m_pres_accpeak, (long long)(m_pres_accpeak >> ACC_SHIFT));
		{   // ★ which C-RAM CELL does each kernel slot read?
			std::string ln;
			for (u32 i = 0; i <= 24; i++)
				if (m_curprof_seen[i])
					ln += string_format(" %d:cur=0x%02X(val=%06X)", i, m_curprof[i] & 0xff,
							m_cram.read_dword(m_curprof[i] & 0xff) & 0xffffff);
			logerror("upd6383: KERNEL CURSOR:%s\n", ln);
			std::string lp;
			for (u32 i = 0; i <= 24; i++)
				if (m_curprof_seen[i]) lp += string_format(" %d:P=%lld", i, (long long)m_pprof[i]);
			logerror("upd6383: PRODUCT REGISTER:%s\n", lp);
			{
				std::string su;
				for (u32 i = 0; i < 32; i++)
					if (m_src_unread[i]) su += string_format(" 0x%02X:%d", i, m_src_unread[i]);
				logerror("upd6383: SRC CODES STILL READING ZERO:%s\n", su.empty() ? " none" : su.c_str());
				std::string so;
				for (u32 i = 0; i < 6; i++)
					so += string_format(" slot%d:%d/%d", i, m_out_slot_nonzero[i], m_out_slot_writes[i]);
				logerror("upd6383:   WATCH 0x8C: %d stores (%d nonzero) site %d | "
						"0x8D: %d stores (%d nonzero) site %d\n",
						m_watch_hits[0], m_watch_nz[0], m_watch_site[0],
						m_watch_hits[1], m_watch_nz[1], m_watch_site[1]);
				logerror("upd6383:   WATCH INPUT LATCH L(0x%02X): %d stores site %d word %09llX | "
						"R(0x%02X): %d stores site %d word %09llX\n",
						m_in_addr[0], m_watch_hits[2], m_watch_site[2],
						(unsigned long long)m_watch_word[2],
						m_in_addr[1], m_watch_hits[3], m_watch_site[3],
						(unsigned long long)m_watch_word[3]);
				logerror("upd6383: OUTPUT SLOT WRITES (nonzero/total):%s\n", so);
				for (int i = 0; i < 6; i++)
				{
					if (m_out_slot_reg[i] == 0xffff) continue;
					logerror("upd6383:   slot%d SRC 0x%02X  reads reg 0x%02X  word %09X  peak %d  (%d/%d nonzero)\n",
							i, i + 1, m_out_slot_reg[i], u32(m_out_slot_word[i] & 0xffffffff),
							m_out_slot_peak[i], m_out_slot_nonzero[i], m_out_slot_writes[i]);
				}
				std::string s7;
				for (u32 q = 0; q < m_st07n; q++)
					s7 += string_format(" [dest %02X src %02X ptr %02X L %d]",
							m_st07_dest[q], m_st07_src[q], m_st07_ptr[q], m_st07_val[q]);
				logerror("upd6383: MODE-1 ACT-07 STORES:%s\n", s7);
				logerror("upd6383: epilogue pointer on entry (last frame) = 0x%02X\n", m_epi_ptr_before);
				std::string ep;
				for (u32 q = 0; q < 23; q++) ep += string_format(" %d:%02X", 60 + q, m_epi_ptr[q]);
				logerror("upd6383: EPILOGUE POINTER WALK:%s\n", ep);
				std::string sd;
				for (u32 i = 0; i < 256; i++)
					if (m_dwr[i]) sd += string_format(" %02X:%d/%d", i, m_dwr_nz[i], m_dwr[i]);
				logerror("upd6383: D-RAM WRITES (nonzero/total):%s\n", sd);
			}
			logerror("upd6383: BIGGEST MULTIPLY: pre-shift %lld = coef %d (0x%06X) x L %d, SRC 0x%02X at iw%d\n",
					(long long)m_mulmax, m_mul_coef, m_mul_coef, m_mul_L, m_mul_src, m_mul_iw);
		}
		{   // ★ which C-RAM BANKS did the coefficient stream actually fill?
			if (m_cwr_runlen && m_nruns < 32)
			{ m_run_base[m_nruns] = m_cwr_start; m_run_len[m_nruns] = m_cwr_runlen; m_nruns++; }
			std::string ln;
			for (u32 i = 0; i < m_nruns; i++)
				ln += string_format(" [0x%02X..0x%02X]=%d", m_run_base[i],
						(m_run_base[i] + m_run_len[i] - 1) & 0xff, m_run_len[i]);
			logerror("upd6383: C-RAM WRITE RUNS (%d):%s\n", m_nruns, ln);
		}
		if (m_trace_n)
		{   // ★★★ THE TIME-ORDERED FRAME TRACE, in execution order
			logerror("upd6383: ==== TIME-ORDERED FRAME TRACE, %d slots ====\n", m_trace_n);
			logerror("upd6383:   n  iw   word         dp  mem[dp]        acc            P         tA        tB cur   coef  MUL          L\n");
			for (u32 q = 0; q < m_trace_n; q++)
			{
				const trace_t &t = m_trace[q];
				logerror("upd6383:  %3d %3d  %d %010llX %02X %14lld %14lld %14lld %02X %06X  %c %8d\n",
						q, t.iw, t.u1 ? 1 : 0, (unsigned long long)t.word, t.dp,
						(long long)t.acc, (long long)t.accb, (long long)t.p,
						t.cur, t.coef, t.mul ? 'Y' : '.', t.l);
			}
		}
		{   // ★ WHERE DOES THE SIGNAL DIE?  peak |acc| per I-RAM slot.
			logerror("upd6383: ACCUMULATOR PROFILE (peak |acc| per I-RAM slot)\n");
			std::string ln;
			for (u32 i = 0; i < 285; i++)
			{
				if (!m_slotseen[i]) continue;
				ln += string_format(" %d:%lld", i, (long long)m_accprof[i]);
				if (ln.size() > 110) { logerror("upd6383:  %s\n", ln); ln.clear(); }
			}
			if (!ln.empty()) logerror("upd6383:  %s\n", ln);
		}
		{   // ★ did the coefficients land where the cursor reads?
			u32 nz = 0;
			for (u32 i = 0; i < 256; i++)
				if ((m_cram.read_dword(i) & 0xffffff) != 0) nz++;
			logerror("upd6383:   C-RAM cells written: %d of 256 non-zero, %d coefficients routed\n",
					nz, u32(m_cwr));
			std::string ln;
			for (u32 i = 0; i < 256; i++)
			{
				const u32 v = m_cram.read_dword(i) & 0xffffff;
				if (v) ln += string_format(" %02X=%06X", i, v);
				if (ln.size() > 100) { logerror("upd6383:   CRAM%s\n", ln); ln.clear(); }
			}
			if (!ln.empty()) logerror("upd6383:   CRAM%s\n", ln);
		}
	}

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
	//  ★★★ COMMAND 0x02 -- THE COEFFICIENT STREAM, SPECULATIVE, 2026-07-28.
	//  This command was ACCEPTED AND IGNORED, so C-RAM was NEVER LOADED and the
	//  emulated DSP ran with no effect coefficients at all.  The captured stream
	//  verifies itself against work done entirely outside this device:
	//      transfer 37:  01 61 | 00 00 72 | 7F FF FF | ...
	//  0x000072 = 114 is CHORUS's LFO ramp step, floor(f * 2^23 / 44100), and
	//  0x7FFFFF is the wrap constant -- the two numbers dsp/tools/lfo_ramp.py
	//  derives from the ROM.  transfer 23 opens 0x200000 / 0x400000 = 0.25 / 0.5.
	//
	//  MEASURED: the framing.  Every cmd-0x02 payload is a 2-byte prefix 0x0161
	//  (host-side.md C4 calls it "the 24-bit coefficient port", NOT an address)
	//  followed by a whole number of 3-byte 24-bit words.
	//  ⛔ GUESSED: that the words land in C-RAM sequentially from 0, and that the
	//  write pointer restarts at each transfer.  A zero-payload 0x0161 transfer
	//  (transfer 10) is treated as a reset.  Register row 17.
	if (m_host_cmd == 0x02 && m_speculative)
	{
		if (m_host_pos == 0)      m_cwr_hi = data;
		else if (m_host_pos == 1) { m_cwr_port = (u16(m_cwr_hi) << 8) | data; }
		else
		{
			const u32 b = (m_host_pos - 2) % 3;
			m_cwr_word[b] = data;
			if (b == 2)
			{
				const u32 v = (u32(m_cwr_word[0]) << 16) | (u32(m_cwr_word[1]) << 8)
						| m_cwr_word[2];
				//  ★ land AT THE POINTER, auto-incrementing.  The pointer is NOT
				//  reset per transfer -- it is set by an `801.0.NN.821' ldptr word
				//  in the program stream (below).  Sequential-from-0 was the round-4
				//  guess and it was wrong: it changed the wet on 0.03 % of samples.
				if (m_cram_wp_set)
				{
					if (m_cwr_runlen == 0) m_cwr_start = m_cram_wp;
					m_cram.write_dword(m_cram_wp, v & 0xffffff);
					m_cram_wp = (m_cram_wp + 1) & 0xff;
					m_cwr++; m_cwr_runlen++;
				}
			}
		}
		m_host_pos++;
		return;
	}

	if (m_host_cmd != 0x01)
	{
		m_host_pos++;
		return;
	}

	if (m_host_pos == 0)
		m_host_addr = u16(data) << 8;
	else if (m_host_pos == 1)
	{
		m_host_addr |= data;
		//  ★★★ §59 P1.1: 0x0160 is the POKE PORT.  Everything after it is a packet
		//  stream, NOT I-RAM words -- writing it to I-RAM[352+] (past the 285-slot
		//  frame) silently dropped all 881 tag-0x15 D-RAM writes and all 870 tag-0x4C
		//  descriptor writes, which is why every delay descriptor read 0x0000 and no
		//  per-effect parameter ever reached the chip.
		m_poke_active = (m_host_addr == POKE_PORT);
		m_poke_n = 0;
	}
	else if (m_poke_active)
	{
		m_poke[m_poke_n++] = data;
		if (m_poke_n == 5)
		{
			m_poke_n = 0;
			//  ★★★ §197: THE LEADING NIBBLE IS A FLAG, NOT A CONSTANT.
			//  `k3-pointers.md' §7 item 6 and `register-space.md' §1.1 both record
			//  `0B .. .. .. 15' as the SAME tag-0x15 packet with one extra flag bit.
			//  Testing `== 0x0a' dropped every 0x0B packet -- 44 of 3456 in the
			//  TYPE-walk capture -- AND stalled the auto-increment, shifting the rest
			//  of the stream one cell low.
			//  ★ CONTROL, bit-exact and independent: the four lost values
			//  400 / 1440 / 2480 / 3520 sit cell-for-cell in the DELAY-DESCRIPTOR
			//  space at 0x26 / 0x28 / 0x2A / 0x2C (§189's live dump, taken for an
			//  unrelated purpose), written by a different writer through a different
			//  pointer register into a different memory -- register-space.md §6.2's
			//  "CHORUS writes the same four tap lengths twice".
			//  ⚠ This ACCEPTS the packet; the flag bit's MEANING stays undecoded.
			if ((m_poke[0] & 0xfe) == 0x0a)
			{   // DATA packet: 0A | dd dd dd | TAG
				u32 v = (u32(m_poke[1]) << 16) | (u32(m_poke[2]) << 8) | m_poke[3];
				//  ★★★ §111 SPECULATIVE (mask bit 31): THE HOST PAYLOAD IS 2x THE RAW
				//  THREE BYTES.  r3-delaydram.md states it; §71/A3 reproduced it as a
				//  control that could have failed -- the cold-boot record says
				//  `reg 0x06 <- +0.500000' and `reg 0x86 <- +0.183992' while the wire
				//  carries +0.250000 and +0.091996, HALF of each to six decimal
				//  places.  We have been storing the raw bytes ever since, and every
				//  host-programmed quantity in this device is consequently half.
				//
				//  ★ TWO INDEPENDENT KNOWN-RIGHT ANSWERS, from different notes and
				//  different subsystems -- this is why it is worth doing now:
				//    (1) unit-0 OUTPUT LEVEL  0x200000 -> 0x400000 = +0.5, the
				//        documented cold-boot value (register-space.md A1/A3).
				//    (2) CHORUS LFO INCREMENT      57 -> 114 = 0x72, which
				//        lfo-ramp.md derives independently at 11 sites and ties to a
				//        real modulation rate of 0.5993 Hz.
				//  Neither was fitted to the other; a wrong scaling cannot satisfy
				//  both.  If only one moves, this reading is wrong.
				if (m_speculative && (m_specmask & 0x80000000u))
				{ v = (v << 1) & 0xffffff; m_pk_x2_n++; }
				//==========================================================
				//  ★★★ §188 SPECULATIVE (mask bit 63): RESTORE THE PAYLOAD'S
				//  LSB.  `k5-output-stage.md' item 9 and `k3-pointers.md'
				//  §1.1 item 3 both give the packet decode as
				//      V = ((aa&0x7F)<<17) | (bb<<9) | (cc<<1) | (dd>>7)
				//  -- PROVEN BY CONSTRUCTION, off the firmware's own writers.
				//  §111's x2 above reproduces the three shifts but DROPS
				//  `dd>>7', so a third of every host-programmed quantity in
				//  this device is 1 LSB low (32% of packets carry it set).
				//  ⚠ `adjudication-round4.md' item D records that this
				//  retraction "never reached" six downstream documents and
				//  leaves 7 LIVE sites; this is one of them.
				//
				//  ★ MEASURED STATICALLY before implementing, against the LFO
				//  sine the host uploads -- decoding those 24 packets both ways
				//  and comparing with round(0.95 * 2^23 * sin(2*pi*k/24 + 0.1)):
				//      PROVEN decode : max err 1 LSB, RMS 0.707   (pure rounding)
				//      DEVICE decode : max err 2 LSB, RMS 1.291
				//      tag bit 7 set in 12 of 24 -- half, as a sine's LSBs should be
				if (m_speculative && (m_specmask & (1ull << 63)))
				{
					if (m_poke[4] & 0x80) { v |= 1; m_pk_lsb_n++; }
					m_pk_lsb_seen++;
				}
				const u8  tag = m_poke[4];
				if (m_poke[0] == 0x0b) m_pk_0b_n++;     // §197 fired-count
				m_pk_tag[tag]++;
				switch (tag & 0x7f)
				{
				case 0x15:                       // D-RAM register file
					// ★ §97: "register file" is what host-side.md C4 calls this
					//  tag, and it is the MODE-1 space -- not the pointer-walked
					//  D-RAM.  Writing it into m_dram put the host's parameters
					//  in the same array the kernel uses as scratch, which is
					//  the §71/§86 conflict.  See upd6383.h `m_rf'.
					//  ★★★ §186 PROBE (read-only): WHICH cells does the host write?
					//  §185 infers `C63' RESETS register 0x63, and a reset
					//  presupposes a WRITER.  The roadmap counts 65 cells written by
					//  this tag; the census shows non-zero at only 06 and 1D..40
					//  (~37).  Recording every TARGET -- not only the ones that end
					//  non-zero -- decides whether 0x63 is in the host's range at all.
					//  Two-sided: in range -> the reset has something to reset and the
					//  reading becomes testable; not in range -> the selector space is
					//  not m_rf and §185 §2's identification is wrong.
					m_hostw_cell[m_dram_wp & 0xff]++;
					if (v & 0xffffff) m_hostw_nz[m_dram_wp & 0xff]++;
					if (m_speculative && (m_specmask & 0x800000))
					{
						m_rf[m_dram_wp & 0xff] = v & 0xffffff;
						pv_wr_rf(u8(m_dram_wp), v, E1_PV_HOST);   // ★ §221 §E1
						pk_write(u8(m_dram_wp), v, 4, true, PK_IW_HOST);   // §222
					}
					else
					{
						m_dram.write_dword(m_dram_wp, v & 0xffffff);
						pv_wr_dram_tag(u8(m_dram_wp), v, E1_PV_HOST);  // ★ §221 §E1
						pk_write(u8(m_dram_wp), v, 4, false, PK_IW_HOST);  // §222
					}
					m_dram_wp = u8(m_dram_wp + 1);
					m_pk_dram++;
					break;
				case 0x4c:                       // the DESCRIPTOR bank -- its OWN space
					m_dscbank[m_dsc_wp] = u16(v & 0xffff);
					m_dsc_wp = u8(m_dsc_wp + 1);
					m_pk_dsc++;
					break;
				case 0x26:                       // C-RAM
					if (m_cram_wp_set)
					{
						m_cram.write_dword(m_cram_wp, v & 0xffffff);
						m_cram_wp = u8(m_cram_wp + 1);
					}
					m_pk_cram++;
					break;
				default: m_pk_other++; break;
				}
			}
			else
			{   // an instruction word that aims a pointer
				u64 w = 0;
				for (int i = 0; i < 5; i++) w = (w << 8) | m_poke[i];
				w &= 0xfffffffffULL;
				const u16 lo = upd6383_disassembler::lo12(w);
				const u8  ad = upd6383_disassembler::addr8(w);
				if (lo == 0x825)      { m_dsc_wp  = ad; m_pk_ptr++; }   // ldptr.d
				else if (lo == 0x821) { m_cram_wp = ad; m_cram_wp_set = true; m_pk_ptr++; }
				else if (upd6383_disassembler::class4(w) == 1 && lo == 0x000)
					{ m_dram_wp = ad; m_pk_ptr++; }                     // mode-1 register addr
				else m_pk_other++;
			}
		}
	}
	else
	{
		const u32 byte_in_word = (m_host_pos - 2) % upd6383_disassembler::WORD_BYTES;
		m_host_word[byte_in_word] = data;

		if (byte_in_word == upd6383_disassembler::WORD_BYTES - 1)
		{
			const u32 word_index = m_host_addr + (m_host_pos - 2) / upd6383_disassembler::WORD_BYTES;

			//  ★★★ THE C-RAM WRITE POINTER -- PROVEN BY CONSTRUCTION.
			//  `801.0.NN.821' loads the C-RAM POINTER (writer LABEL_0387E6; K3
			//  confirmed the host-stream and in-program meanings are the same
			//  space), and the command-0x02 coefficients that follow land AT that
			//  pointer, auto-incrementing.  dsp/tools/lfo_ramp.py cram_of_algo()
			//  replays exactly this to recover every coefficient this project has
			//  measured, so the rule is not a guess -- only its use here is new.
			//  The word arrives through the ordinary cmd-0x01 path, including at
			//  the host poke port (I-RAM 352+), e.g. captured transfer 26:
			//      01 60 | 08 01 09 78 21 | ...   -> ldptr 0x09
			{
				u64 hw = 0;
				for (int i = 0; i < upd6383_disassembler::WORD_BYTES; i++)
					hw = (hw << 8) | m_host_word[i];
				if (upd6383_disassembler::hi12(hw) == 0x801
						&& upd6383_disassembler::class4(hw) == 0
						&& upd6383_disassembler::lo12(hw) == 0x821)
				{
					if (m_cwr_runlen && m_nruns < 32)
					{
						m_run_base[m_nruns] = m_cwr_start;
						m_run_len[m_nruns] = m_cwr_runlen;
						m_nruns++;
					}
					m_cwr_runlen = 0;
					m_cram_wp = upd6383_disassembler::addr8(hw);
					m_cram_wp_set = true;
				}
			}

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
//  deposit follows.
//
//  ★ RETRACTED SENTENCE, kept visible (retraction-sweep.md, P1).  This comment
//  used to continue: "In steady state the epilogue's `ldptr #$90' at I-RAM 69
//  and its w79 (-1) leave X = 0x8F, giving 0x91 and 0x94".  THAT IS NOT TRUE OF
//  THIS CODE and never becomes true: `ldptr' stopped writing m_dp when K3
//  withdrew the 0x821 = data-pointer reading, so I-RAM 69 does not place X at
//  all.  For a while NOTHING placed it, and the pointer moved only by
//  post-increment -- which is where the +121 frame-closure residue came from.
//
//  ★ THERE IS A STEADY STATE AGAIN, and X IS 0xFF (2026-07-27).  Not because
//  the retracted sentence came back, but because the PER-UNIT REBASE at the CALL
//  does place the pointer (DRAM_UNIT_BASE, FORCED): the unit-1 body starts at
//  0x85, walks -133, the output stage walks -1, and the frame ends on 0xFF.
//  So the two deposits below land on cells 0x01 and 0x04 -- exactly the two DI
//  latches of dsp/analysis/output-stage-decode.md sect. 3.5's map, which is a
//  PREDICTION of that map and not an input to it.
//
//  THE CODE IS UNCHANGED ANYWAY, and that is deliberate: nothing here depends on
//  X.  Only the OFFSETS +2 / +5 are used and those come from an origin-free
//  pointer-rule walk of the twelve input words, so if the origin is ever
//  re-adjudicated this function does not move.  The audit in run_frame() is what
//  would notice: it COMPARES what the microcode read against what was latched.

void upd6383_device::latch_inputs_to_dram()
{
	m_in_base = m_dp;
	m_in_addr[0] = u8(m_in_base + IN_LATCH_L_OFF);
	m_in_addr[1] = u8(m_in_base + IN_LATCH_R_OFF);
	m_in_val[0] = m_di[IN_PORT][0];
	m_in_val[1] = m_di[IN_PORT][1];

	//  ★ 2026-07-28: also arm unconditionally once the machine is well past boot.
	//  The trace used to fire only on live input, so a run with no notes played
	//  produced NO trace at all -- yet the accumulator profile shows the epilogue
	//  dead in every frame regardless of input, so the diagnosis does not need a note.
	//  ⚠ The fallback is deliberately LATE (2M frames ~= 45 s of audio) so that it
	//  NEVER preempts a real note: live input must always win the arming race, or
	//  the trace silently documents a silent chip.
	//  ⚠⚠ AND the threshold is a MAGNITUDE, not "nonzero": arming on the first
	//  nonzero sample catches boot noise seconds before any note is played, which
	//  is exactly how a trace can claim to be "with input" and not be.
	//  ★ note_spec.lua presses its triad at t = 20 s; 970 000 frames = 22 s, so this
	//  lands DETERMINISTICALLY inside the held note -- no reliance on the input latch,
	//  whose audit peak is exactly 0x800000 (the rail) and so cannot be trusted to
	//  distinguish "a note is sounding" from "the latch is railed".
	//  ★ §128: the arm frame is settable, because an effect SELECTED from the panel
	//  cannot be loaded before the boot settles.  PARAMETRIC EQ lands at t ~ 40-50 s
	//  = frame 1.8-2.2 M, so the 420 000 default traces a frame of the cold-boot
	//  default (CHORUS) and calls it the selected effect.  UPD6383_TRACE_FRAME sets
	//  it; the default is unchanged so every existing harness traces what it did.
	if (!m_trace_done && !m_trace_armed && m_frames_run > m_trace_frame)
	{ m_trace_armed = true; m_trace_n = 0; }
	m_dram.write_dword(m_in_addr[0], u32(m_in_val[0]) & 0xffffff);
	m_dram.write_dword(m_in_addr[1], u32(m_in_val[1]) & 0xffffff);
	//  ★ §221 §E1: the audio entry point gets its OWN provenance tag, so an operand
	//  fed straight from the port is distinguishable from one an `iw' wrote.
	pv_wr_dram_tag(m_in_addr[0], u32(m_in_val[0]), E1_PV_IN);
	pv_wr_dram_tag(m_in_addr[1], u32(m_in_val[1]), E1_PV_IN);
	pk_write(m_in_addr[0], u32(m_in_val[0]), 5, false, PK_IW_IN);      // ★ §222 §E-D0
	pk_write(m_in_addr[1], u32(m_in_val[1]), 5, false, PK_IW_IN);

	m_in_seen[0] = m_in_seen[1] = 0;
	m_in_seen_mask = 0;
}


//  EXECUTE A WORD'S ADDRESSING -- and NOTHING else.
//
//  Four effects.  The first is K6-only; the other three read NO PART of `lo12'
//  and are therefore available on EVERY word, decoded or not:
//      hi12 bit 4    -> the word STORES the accumulator to mem[ptr]   (K6 only)
//      bit 23        -> the word FETCHES a coefficient...
//      class4 == 0xA -> ...and ONLY then does the cursor ADVANCE
//      class4 & 7 == 2 -> a SIGNED pointer post-increment by addr8
//
//  ★ THIS IS NO LONGER RESTRICTED TO THE TWELVE K6 WORDS, and restricting it was
//  a LIVE DEFECT rather than a safety property -- see upd6383d.h has_addressing()
//  for the measurement.  In one sentence: the ~92 words that execute were
//  addressing D-RAM and C-RAM through an address generator that had skipped every
//  undecoded word's contribution, so they read the wrong cells and the wrong
//  coefficients.  `k6' below selects the ONE extra effect the whitelist earns.
//
//  ★ FETCH IS NOT ADVANCE (K4, FORCED -- dsp/analysis/k4-cursor.md item I).
//  This used to read `if (cl & 8) m_cursor++', i.e. it advanced the cursor on
//  classes 8, 9, A, B, C, D, E and F.  Only class A advances: the PARAMETRIC EQ
//  body's ten class-8 words sit inside a cursor map proven to the bit at 6 cells
//  per band, and if class 8 advanced, band k would start at cell 7k.
//
//  What is NOT done, on purpose: the ALU, and -- off the K6 whitelist -- the
//  bit-4 STORE.  The store needs a CORRECT accumulator, and the accumulator of a
//  frame full of undecoded words is not the chip's, so performing it generally
//  would write invented data into real cells.  On the twelve it is kept because
//  the note established where those stores can land (X+0, X+1, X+3, X+4, X+6 --
//  never the two input latches) and because the audit in run_frame() re-checks
//  that claim every single frame instead of asserting it.
//
//  The word is still UNDECODED either way: its arithmetic is unknown, so the
//  frame that contains it is discarded exactly as before, and it still appears on
//  the decoding worklist.  EXECUTE WHAT ADDRESSES, NEVER WHAT COMPUTES.

//  ★ The K6 ALU: exec_alu()'s arithmetic with the pointer walk left to
//  exec_addressing_only(), which has already performed the MEASURED version.
void upd6383_device::exec_alu_k6(u64 word)
{
	const u8 dp_save = m_dp;
	const u32 cur_save = m_cursor;
	m_in_k6 = true;                 // stop exec_alu() re-entering the K6 branch
	exec_alu(word);
	m_in_k6 = false;
	m_dp = dp_save;                 // addressing already done by the caller
	m_cursor = cur_save;
}


void upd6383_device::exec_addressing_only(u64 word, bool k6)
{
	const u16 hi = upd6383_disassembler::hi12(word);

	// A C-format word carries no class4 and no addr8 at all, so there is no
	// addressing to execute: a SAFE NO-OP, not a word we execute badly.
	if (upd6383_disassembler::c_format(word))
		return;

	const u8 cell = m_dp;

	if (k6)
	{
		// THE PORT READ.  Record what the microcode really took out of the cell,
		// so the frame can compare it with what was deposited.  The read itself
		// has no modelled consequence -- the ALU is open -- but the VALUE is the
		// whole question, so it is captured rather than thrown away.
		bool right;
		if (upd6383_disassembler::is_input_latch_read(word, right))
		{
			m_in_seen[right ? 1 : 0] = s32(util::sext(m_dram.read_dword(cell) & 0xffffff, 24));
			pwatch(u8(cell), false);                                   // §98
			//  ★ §33: the DEPOSIT uses m_in_base = m_dp at FRAME START; this read uses
			//  the pointer as it is NOW.  If words 0..3 moved it, the two disagree.
			m_in_readbase[right ? 1 : 0] = m_dp;
			m_in_delta_hist[u8(m_dp - m_in_base)]++;
			//  ★ §33 one-shot: the addresses are supposed to be IDENTICAL, so dump
			//  every quantity at one read and see which identity actually breaks.
			if (m_frames_run > 970000 && m_dbg_once < 4)
			{
				m_dbg_once++;
				logerror("upd6383: §33 READ ch%d  in_base=%02X dp=%02X cell=%02X "
						"in_addr=%02X/%02X | mem[cell]=%08X mem[in_addr]=%08X "
						"in_val=%08X\n", right ? 1 : 0, m_in_base, m_dp, cell,
						m_in_addr[0], m_in_addr[1],
						m_dram.read_dword(cell) & 0xffffff,
						m_dram.read_dword(m_in_addr[right ? 1 : 0]) & 0xffffff,
						u32(m_in_val[right ? 1 : 0]) & 0xffffff);
			}
			m_in_seen_mask |= right ? 2 : 1;
		}

		// the SAME bit-7 gate the ALU now applies -- a store that is suppressed
		// there must be suppressed here, or the twelve whitelisted words would
		// be the one place in the machine running the falsified model.
		// MEASURED: none of the twelve carries bit 7, so this changes nothing
		// today; it closes the hole before it opens.
		if ((hi & upd6383_disassembler::HI_ST)
				&& !st_suppressed_live(word))           // ★ §109 bit 29
		{
			m_dram.write_dword(cell, u32(m_acc & 0xffffff));
			pv_wr_dram(u8(cell), u32(m_acc));                          // ★ §221 §E1
			pk_write(u8(cell), u32(m_acc), 1, false, m_cur_iw);        // ★ §222 §E-D0
			pwatch(u8(cell), true);                                    // §98
			kwatch(cell, s32(u32(m_acc & 0xffffff)));
			watch_store(cell, s32(m_acc & 0xffffff), 1);
			store_probe(u8(cell), s32(m_acc & 0xffffff), 1);           // §109
		}
		{ m_dwr[cell & 0xff]++; if (m_dram.read_dword(cell) & 0xffffff) m_dwr_nz[cell & 0xff]++; }
	}

	// bit 23 FETCHES; class A ADVANCES.  The fetch is modelled because it is what
	// the bit means -- the value lands in the K latch, which is chip state the
	// debugger shows -- but nothing consumes it here, because the ALU of this
	// word is exactly what is NOT decoded.
	if (upd6383_disassembler::cursor_fetch(word))
		m_k = m_cram.read_dword(m_cursor) & 0xffffff;
	if (upd6383_disassembler::coeff_consumer(word))
		m_cursor++;

	if (upd6383_disassembler::ptr_postinc(word) && !ptrd_a_suppressed(word))
		m_dp = u8(m_dp + s8(upd6383_disassembler::addr8(word)));
}


//**************************************************************************
//  THE ALU (the lo12 field)
//**************************************************************************

//  TWO FIELDS, TWO JOBS.  lo12 is the OPERAND ROUTING and hi12[3:1] is the
//  OPERATION.  That split is the reconciliation of three concurrent analyses
//  (notes/dsp-alu-applied.md), and it FALSIFIES the framing they all started
//  from -- "lo12 is the ALU field".  Three independent minimal pairs put the
//  operation outside lo12, and the strongest of them, the LFO's
//  `092.A.dd.200' / `094.A.dd.200', differs in NOTHING but hi12[3:1] while its
//  two words must do different things to one D-RAM cell.
//
//      L    := src[ lo12[10:6] ]     07 mem[p]   10 acc   19 tempA   1A tempB
//      if hi12 bit 4 :  mem[p] <- acc ; acc := 0            store AND clear
//      hi12[3:1] :  0 -> acc <- P    1 -> acc += P    2 -> acc unchanged
//      lo12[4:0] :  13 -> tempA <- L  14 -> tempB <- L  07 -> mem[p] <- L
//      if class4 == A :  P := coef[cursor++] * L
//      if class4 & 7 == 2 :  p += (s8)addr8
//
//  THE PRODUCT REGISTER IS NOT CONSUMED.  It holds until the next multiply
//  writes it, which is what a hardware MPLY output latch does; the accumulator
//  op says whether to take it, add it or ignore it.  (The superseded reading
//  had one uniform `acc += P; P := 0'.  On the biquad the two are identical to
//  the last bit -- MEASURED, 0.074 dB either way -- which is exactly why that
//  block could not choose and why the LFO had to.)
//
//  ORDER MATTERS AND IS FORCED, not chosen: the bus source is latched BEFORE
//  the ALU step (same rule R1 forced for the bit-4 store -- "store = after" has
//  zero survivors, analysis/r1-allpass-motif.md F2), which is what lets
//  `212.A.FF.407' both write the accumulator to memory and multiply by it.

s32 upd6383_device::acc_to_datum(u64 acc) const
{
	// the 44-bit accumulator read as a 24-bit datum, with saturation.  The
	// chip has two shifters and an OVC on the CDJ-500 block diagram; whether it
	// saturates or wraps is UNKNOWN, and saturation is the choice that cannot
	// turn a loud sound into a louder one.
	const s64 v = s64(util::sext(acc, 44)) >> ACC_SHIFT;

	//  ★★★★ §223 `§S1' -- THE SATURATION CENSUS.  Recorded HERE, on the PRE-CLAMP
	//  value, because this is the one point in the machine where "the accumulator is
	//  bigger than the datum can hold" is knowable.  READ-ONLY: it changes nothing
	//  and it cannot change anything, so every arm can carry it.  See upd6383.h.
	s1_record(v);

	//  ★★★ §114 SPECULATIVE (mask bit 32): WRAP mod 2^23 instead of saturating.
	//  The comment above states the choice was UNKNOWN and saturation was picked as
	//  the safe default.  lfo-ramp.md §11 settles it for at least one datapath, in
	//  the simulation it uses to derive the LFO rates:
	//        094.A.00.200   ST mem[Q] <- (phase + INC) mod 2**23
	//  MEASURED consequence of clamping: once §112 removes iw32's clobber the CHORUS
	//  phase runs up to 0x7FFFFF -- the 24-bit maximum -- and STICKS.  A clamped
	//  accumulator stops dead at full scale; a wrapped one is the sawtooth an LFO is.
	//
	//  ★ TWO-SIDED AND CURRENTLY FAILING: the phase's per-frame min..max at body
	//  iw89 is a SINGLE value (8388607..8388607).  If the publish wraps it becomes a
	//  wide range.  ⚠ And the risk the original comment names is real and is the
	//  falsifier: wrapping an AUDIO accumulator turns a loud sample into an inverted
	//  one, so if this is wrong the §54 DC leak should rise or the tracking verdict
	//  should get worse.  Both are watched.
	//  ★ §116: the wrap is selected PER UNIT by m_ovc bit 3 (see above).  Bit 33
	//  routes through the register; bit 32 (§114) is the unconditional global wrap
	//  kept for comparison.  The FALSIFIER is explicit: under bit 33 unit 0's AUDIO
	//  wraps too, which is exactly the risk this function's own comment defends
	//  against.  If the §54 tracking worsens while the LFO ramps, bit 3 is a
	//  per-unit flag but NOT the overflow mode.
	if (m_speculative && (m_specmask & 0x200000000ull))
	{
		//  ★★★ §118: THE PER-UNIT ENABLE AND THE PER-DATAPATH MODULUS ARE TWO
		//  DIFFERENT THINGS, and §117 recorded that conflating them was known-wrong
		//  (unit 0's AUDIO came out unsigned).  Separated here:
		//
		//    m_ovc bit 3        -- does this UNIT contain a wrapping datapath?
		//    the WRAP-WORD form -- is THIS STORE the wrapping one?
		//
		//  The second is exceptionless in the corpus.  Of the 678 bit-4 store words,
		//  the family carrying BOTH the gate bit 7 AND f31 == 2 is:
		//        29 words, hi12 forms {0x094: 29}, SRC {0x08: 29}
		//  -- a single hi12 form and a single operand source, and lfo-ramp.md item C
		//  independently counts "29 LFO blocks in 16 programs".  29 words, 29 blocks.
		//  The wrap-word family IS the set of LFO publishers, exactly.
		//  (It is also the only bit-7 store shape that survives store-gate.md item
		//  C's co-equal survivor, which is why iw91 publishes and iw30 does not.)
		const u16 hi_w = upd6383_disassembler::hi12(m_cur_word);
		const bool wrapword = (hi_w & 0x10) && (hi_w & 0x80)
				&& (((hi_w >> 1) & 7) == 2);
		if ((m_ovc & 0x08) && wrapword)
		{
			//  ★★★ §117: the modulus is 2^23 UNSIGNED, not a signed 24-bit wrap.
			//  lfo-ramp.md §11's simulation states it as `mem[Q] <- (phase + INC)
			//  mod 2**23', and its measured phase series is 000072 / 0000E4 / 000156
			//  -- small POSITIVE values ramping, i.e. the accumulator lives in
			//  0..0x7FFFFF and wraps to 0, never going negative.
			//  §114 measured the consequence of getting this wrong: a signed 24-bit
			//  wrap runs the LFO at 0.2997 Hz where mod 2^23 with increment 114
			//  gives 0.5993 Hz -- the rate lfo-ramp.md item C anchors across 29 LFO
			//  blocks in 16 programs with 9 distinct increments.
			//  ⚠ COST, stated: this is applied per UNIT (m_ovc bit 3), so unit 0's
			//  AUDIO also becomes non-negative, which is wrong for a signal.  That
			//  is evidence the modulus really belongs to the DATAPATH and the OVC
			//  bit only selects which units have a wrapping datapath at all.
			m_wrap_n++;
			return s32(u32(v) & 0x7fffff);
		}
	}
	else if (m_speculative && (m_specmask & 0x100000000ull))
	{
		m_wrap_n++;
		return s32(util::sext(u32(v) & 0xffffff, 24));
	}
	if (v >  0x7fffff) return  0x7fffff;
	if (v < -0x800000) return -0x800000;
	return s32(v);
}


//  ★ §29: the deferred output presentation, run AFTER exec_alu()'s arithmetic.
void upd6383_device::do_presentation()
{
	//  addr8 bit 7 selected the unit; it was latched when the word deferred.
	const int unit = m_pres_unit;
	{
			//  ★ FIXED-POINT REGIME, MEASURED 2026-07-28 and still a GUESS as to
			//  which side is wrong.  acc_to_datum() shifts right by ACC_SHIFT = 16.
			//  Instrumented at this very word: the raw accumulator peaks at
			//  4 988 928 while the sample that ENTERED the chip peaks at 5 232 896
			//  -- i.e. the signal traverses the chip at ~0.95x IN THESE UNITS, and
			//  applying the 16-bit shift here turns it into 76, which the tone
			//  generator's `wet = (DO1 + DO2) >> 8' then floors to ZERO.  That is
			//  the whole of the "no audible difference" the owner reported.
			//
			//  ⛔ WHICH SIDE IS WRONG IS OPEN.  Either (a) the accumulator at this
			//  point legitimately holds a DATUM and must not be shifted, or (b) some
			//  upstream path fails to scale a datum INTO accumulator units by
			//  ACC_SHIFT and the shift here is right.  ACT 0x00 does apply
			//  `L << ACC_SHIFT', which argues for (b) -- but the measurement says
			//  the value arriving here has not been through it.
			//  Presenting the raw value is the reading that makes the chip audible;
			//  it is SPECULATIVE and is row 16 of SPECULATIVE-APPLIED-REGISTER.md.
			//  ⛔ ROW 16 REVERTED, 2026-07-28.  Presenting the RAW accumulator made
			//  the chip "audible" -- but A/B analysis showed what it actually emits:
			//  a CONSTANT 4 988 928 every frame, from before any note is played,
			//  correlation with the input -0.0018 at every lag from -600 to +600,
			//  and 19488 = 4988928 >> 8 on 96.8 % of output samples.  That is a
			//  STUCK OUTPUT, not an effect, and DC is inaudible -- which is exactly
			//  what the owner reported hearing.  acc_to_datum() at least keeps the
			//  stuck value below the tone generator's >> 8 instead of injecting DC
			//  into the mix.  The REAL defect is that the accumulator is constant at
			//  this word; see SPECULATIVE-APPLIED-REGISTER.md sect. 3.4.
			//  ★ §27: unit 0 presents ACCA, unit 1 presents ACCB.
			//  ★ §62: present the accumulator that belongs to THIS unit.
			const u64 pacc = (m_speculative && (m_specmask & 0x4001) && unit)
					? m_accb : m_acc;
			const s64 rawacc = util::sext(pacc, 44);
			s64 scaled = acc_to_datum(pacc);
			(void)rawacc;
			//  ★★ SPECULATIVE, and the best-evidenced guess in this block: apply the
			//  PER-UNIT OUTPUT LEVEL.  Registers 0x06 (unit 0) and 0x86 (unit 1) are
			//  named per-unit OUTPUT LEVEL and their role is PROVEN BY CONSTRUCTION --
			//  the last four host actions of cold boot are
			//      setvec unit1,#200 / setvec unit0,#84 / reg 0x06 <- +0.500000
			//                                           / reg 0x86 <- +0.183992
			//  and both are cleared at reset.  dark-words.md sect. 4.3 calls testing
			//  them "the cheapest live experiment in the project ... a repeatable test
			//  with a known answer".
			//
			//  WHAT IS GUESSED: that the level applies HERE, at the presentation, as a
			//  Q0.23 multiply.  Its VALUE is measured; its point of application is not.
			//  Motivation is an observed defect -- with the raw accumulator presented,
			//  the wet peaks at 32696 against a dry peak of 20441, i.e. too hot, and
			//  0.5 / 0.184 are the right order to fix it.
			{
				//  ★★★ §42, 2026-07-28: THE LEVEL LIVES IN C-RAM, NOT D-RAM.
				//  The per-unit OUTPUT LEVEL is set by the HOST ("reg 0x06 <- +0.5,
				//  reg 0x86 <- +0.183992", the last two actions of cold boot), and
				//  the host's ONLY write path into this device writes m_cram.  There
				//  is no host write to D-RAM anywhere.  Reading D-RAM[0x06] therefore
				//  read a cell the host never touches: MEASURED 0x000000 at every
				//  presentation, so `if (lvl != 0)' skipped the level multiply
				//  entirely and the per-unit output level was never applied at all.
				//  Corroboration from the kernel cursor dump: C-RAM carries 0x400000
				//  -- exactly +0.5 -- among its coefficients.
				// ★ §97: the level lives in the MODE-1 REGISTER FILE.  The
				//  comment above -- "the host's ONLY write path into this device
				//  writes m_cram; there is no host write to D-RAM anywhere" --
				//  was overtaken by §71, which found the host poke port and its
				//  tag-0x15 writes to 0x06/0x86.  It read 0x000000 not because
				//  the host cannot reach the cell but because we dropped the
				//  packets, and then because the kernel's scratch overwrote it.
				//  Bit 23 reads the register file; bit 6 keeps the C-RAM
				//  workaround for bisection.
				const u32 lvl = (m_speculative && (m_specmask & 0x800000))
						? m_rf[unit ? 0x86 : 0x06]
						: (((m_specmask & 0x40) ? m_cram : m_dram)
								.read_dword(unit ? 0x86 : 0x06) & 0xffffff);
				m_lvl_seen[unit] = lvl;   // ★ §41: is the host's level still there?
				if (lvl) m_lvl_nz[unit]++;
				if (lvl != 0)
					scaled = (scaled * s64(util::sext(lvl, 24))) >> 23;
			}
			const s32 v = s32(std::clamp<s64>(scaled, -(1 << 23), (1 << 23) - 1));
			//  ★ §63: what is actually in the two accumulators at each presentation,
			//  and what unit context are we in?  §62 assumed body 1 leaves
			//  m_cur_unit1 SET -- but row 27 already clears it at :2858, so that
			//  diagnosis needs checking rather than fixing.
			if (m_dbg_pres < 6 && m_frames_run > 400000)
			{
				m_dbg_pres++;
				logerror("upd6383: §63 PRESENT unit%d  cur_unit1=%d  "
						"ACCA=%lld ACCB=%lld  pacc=%lld -> v=%d\n",
						unit, m_cur_unit1 ? 1 : 0,
						(long long)util::sext(m_acc, 44), (long long)util::sext(m_accb, 44),
						(long long)util::sext(pacc, 44), v);
			}
			if (unit == 0 && m_frames_run > S70_ARM_FRAME)
			{   // ★ §70: ACCA at w73, split by whether this frame had input
				const int k = ((m_in_val[0] != 0) || (m_in_val[1] != 0)) ? 1 : 0;
				const s64 a = util::sext(pacc, 44);
				if (a < m_pa_min[k]) m_pa_min[k] = a;
				if (a > m_pa_max[k]) m_pa_max[k] = a;
				m_pa_sum[k] += a;                       // ★ STANDING RULE 19 (§221)
				m_pa_n[k]++;
			}
			if (unit == 1 && m_frames_run > S70_ARM_FRAME)
			{   // ★★★ §211: the SAME test for unit 1 -- ACCB at w78.  Standing rule 1
				//  has never been applied to this port; §61's "DO2 peak 0" cannot tell
				//  an empty ACCB from an empty unit-1 OUTPUT LEVEL.  The level itself
				//  is already reported by §41 (m_lvl_seen), so printing both separates
				//  them without any new mechanism.
				const int k = ((m_in_val[0] != 0) || (m_in_val[1] != 0)) ? 1 : 0;
				const s64 b = util::sext(pacc, 44);
				if (b < m_pb_min[k]) m_pb_min[k] = b;
				if (b > m_pb_max[k]) m_pb_max[k] = b;
				m_pb_sum[k] += b;                       // ★ STANDING RULE 19 (§221)
				m_pb_n[k]++;
			}
			m_pres_u[unit]++;                                   // ★ §61 per-unit
			if (v) { m_pres_u_nz[unit]++; }
			if (std::abs(v) > std::abs(m_pres_u_peak[unit])) m_pres_u_peak[unit] = v;
			if (v) m_frame_out_nz = true;                       // ★ §54
			if (std::abs(v) > std::abs(m_frame_out_peak)) m_frame_out_peak = v;
			m_do[unit][0] = v;
			m_do[unit][1] = v;
			m_pres_seen++;
			if (v != 0) m_pres_nonzero++;
			if (std::abs(v) > std::abs(m_pres_peak)) m_pres_peak = v;
			{   // ★ diagnostic: is the ACCUMULATOR small, or only its datum?
				const s64 raw = util::sext(pacc, 44);
				if (std::abs(raw) > std::abs(m_pres_accpeak)) m_pres_accpeak = raw;
			}
	}
}

void upd6383_device::exec_alu(u64 word)
{
	//  ★★★ SPECULATIVE-ONLY FORMS.  Reached only when m_speculative is set and
	//  alu_decoded_speculative() admitted a word alu_decoded() refuses.  Each
	//  reading is a RESEARCHED GUESS; see upd6383d.h alu_decoded_speculative()
	//  and dsp/analysis/unblocking-and-discriminators.md.
	//  ★ §90: why does iw213 (000.2.BA.000) lose its -70 post-increment?
	if (m_cur_iw == 213 && m_dbg213 < 3 && m_frames_run > 420000)
	{
		m_dbg213++;
		logerror("upd6383: §90 iw213 %09llX alu_decoded=%d addressing_only=%d "
				"c_format=%d lo12=%03X cl=%X ptr_postinc=%d dp_in=%02X\n",
				(unsigned long long)word,
				upd6383_disassembler::alu_decoded(word) ? 1 : 0,
				upd6383_disassembler::addressing_only(word) ? 1 : 0,
				upd6383_disassembler::c_format(word) ? 1 : 0,
				upd6383_disassembler::lo12(word), upd6383_disassembler::class4(word),
				upd6383_disassembler::ptr_postinc(word) ? 1 : 0, m_dp);
	}
	if (m_speculative && !upd6383_disassembler::alu_decoded(word))
	{
		const u8 cl = upd6383_disassembler::class4(word);
		const bool hi_esc = (upd6383_disassembler::hi12(word) & 0xF00) == 0xA00;

		//  ★★★ K6 INPUT STAGE -- MUST KEEP ITS OWN ADDRESSING.  Found 2026-07-28
		//  by A/B capture: with the speculative gate admitting every word, these
		//  twelve took the generic path instead of exec_addressing_only(), their
		//  MEASURED pointer walk was lost, and the frame report went from
		//  "973440 frames in which both port reads executed" to ZERO --
		//  "NOTHING ENTERED THE CHIP".  The wet mix was then bit-identical to dry
		//  over 5 472 003 samples, which is exactly what the owner heard.
		//  Their addressing is MEASURED (notes/dsp-k6-input-stage.md); only the
		//  ALU is open, so run the measured part and leave the ALU alone.
		if (upd6383_disassembler::addressing_only(word) && !m_in_k6)
		{
			//  ★★★ THE K6 INPUT STAGE'S ALU -- 2026-07-28.  Measured cause of the
			//  whole audio failure: profiling peak |acc| at all 285 slots showed it
			//  is ZERO EVERYWHERE, because these twelve words deposit the sample and
			//  return BEFORE the arithmetic.  They are the only words that read the
			//  audio latches, so nothing downstream ever sees a signal.
			//
			//  Decoding their lo12 shows the block is far less open than "ALU OPEN"
			//  suggests.  Both fields are ANCHORED on five of them, and the refusals
			//  are narrow:
			//     iw6  400.A.00.419  SRC 0x10 acc, ACT 0x19  -- NOTHING refuses it
			//     iw9  012.2.FF.1D5  SRC 0x07 mem, ACT 0x15  -- NOTHING refuses it
			//     iw8  084.2.01.1C0  SRC 0x07 mem, ACT 0x00  -- refused ONLY by
			//     iw2  084.2.02.680  SRC 0x1A tB,  ACT 0x00     "f31==2 on class 2"
			//     iw4  204.2.02.1CE  SRC 0x07 mem, ACT 0x0E     (see below)
			//
			//  ★ iw8 IS "THE PORT READ of block B" (notes/dsp-k6-input-stage.md §7)
			//  and its ACTION is 0x00 = acc's input term <- bus.  Executing it hands
			//  the input sample to the accumulator as `L << ACC_SHIFT' -- exactly the
			//  link the profile showed missing.
			//
			//  ⛔ WHAT IS ASSUMED: that hi12[3:1] == 2 (HI_ACC_HOLD) means the same
			//  thing off class 8.  alu_decoded()'s own comment says it is "ONLY
			//  ESTABLISHED on class 8" -- established, not restricted -- so this
			//  extends a proven reading to a class where it was never tested.  It is
			//  register row 18 and it is a GUESS, not a decode.
			exec_addressing_only(word, true);   // the MEASURED part: pointer, store,
			                                    // cursor, latch capture
			exec_alu_k6(word);                  // the ALU, without re-walking the pointer
			return;
		}
		//  C-FORMAT: a 13-bit immediate.  status() already calls it MEASURED
		//  with the DESTINATION open; `acc' is one of six enumerated choices.
		if (upd6383_disassembler::c_format(word))
		{
			s32 imm = s32(upd6383_disassembler::c_imm13(word));
			if (imm & 0x1000)
				imm -= 0x2000;
			//  ⛔ ROW 5 UNDER TEST, 2026-07-28.  `cfmt = acc' writes the immediate
			//  into the ACCUMULATOR, and the stuck presentation value 4 988 928 is
			//  exactly 2436 << 11 -- the shape this line produces.  If a c-format
			//  word runs late in the frame it clobbers the signal every time.  The
			//  destination was always "1 of 6 enumerated"; parking it in a dedicated
			//  latch tests whether it is the clobber without inventing a new
			//  destination.
			m_cimm = s64(imm) << 11;
			return;
		}
		//  THE ALTERNATE lo12 ENCODING (bit 11).  sect. 9 of bit11-family.md
		//  proves it is a SECOND encoding with no SRC and no ACTION field, so
		//  the only honest execution is its ADDRESSING -- which IS decoded.
		//  ★ §116 MUST BE TESTED BEFORE THE ALTERNATE-ENCODING RETURN.  lo12 = 0x827
		//  carries bit 11, so a selector-0x27 word is swallowed here and never
		//  reaches the register-load dispatch further down -- the first placement
		//  measured 0 loads, caught by its own fired-count.  The bit-11 branch
		//  executes ADDRESSING ONLY, which is right for words whose ALU route is
		//  unmodelled but wrong for one whose whole job is to load a register.
		if (m_speculative && (m_specmask & 0x200000000ull)
				&& upd6383_disassembler::lo12(word) == 0x827)
		{
			m_ovc = upd6383_disassembler::addr8(word);
			m_ovc_loads++;
			m_ovc_hist[m_ovc]++;
			return;                     // a register aimed; accumulator untouched
		}
		if (upd6383_disassembler::lo12(word) & 0x800)
		{
			if (upd6383_disassembler::coeff_consumer(word))
				m_cursor++;
			if ((upd6383_disassembler::class4(word) & 7) == 2)
				m_dp = u8(m_dp + s8(upd6383_disassembler::addr8(word)));
			return;
		}
		//==================================================================
		//  ★★★ THE SPECULATIVE READING TABLE -- ROUND 2, 2026-07-28.
		//
		//  Round 1 removed 115 of the 123 trapping forms and left EIGHT, all of
		//  them in the SHARED kernel/epilogue so they blocked every frame.  Each
		//  is filled in below with its GRADE.  Grades, strongest first:
		//
		//    [PART-MEASURED]  some field of the word is independently measured
		//                     and only the arithmetic is guessed
		//    [INFERRED]       the disassembler already annotates an idiom
		//    [PLAIN GUESS]    nothing supports the reading; it exists so the
		//                     frame can close
		//
		//  form            grade            reading
		//  000.0.00.000    [INFERRED]       NOP -- the all-zero word is I-RAM's
		//                                   reset state and its own disassembly
		//  000.6.18.4CD    [INFERRED]       table-lookup idiom; no table is
		//  000.6.20.407    [INFERRED]       modelled, so: addressing only
		//  980.5.20.402    [PLAIN GUESS]    no side effect
		//  A00.0.00.015    [PLAIN GUESS]    no side effect (ACT 0x15 spelling)
		//  A00.0.00.041    [PLAIN GUESS]    no side effect
		//  A3C.D.9F.287    [PART-MEASURED]  OUTPUT PRESENTATION, unit 1
		//  E30.C.00.404    [PART-MEASURED]  OUTPUT PRESENTATION, unit 0
		//
		//  ★ THE TWO PRESENTATION WORDS ARE THE LOAD-BEARING ONES, and they are
		//  the only place in this device that writes m_do[][] AT ALL -- until
		//  now the output latch had NO WRITER, so even a clean frame returned
		//  silence.  What is MEASURED about them (output-stage-decode.md item I):
		//  w73's SRC 0x10 IS the accumulator (ANCHORED), and addr8 bit 7 assigns
		//  the unit -- 0x00 -> unit 0, 0x9F -> unit 1.  What is GUESSED is the
		//  ARITHMETIC: here, the identity.  output-stage-io.md sect. 10 proved
		//  both words UNDECIDABLE BY COMPARISON, so this is a placeholder that
		//  lets the frame close and NOT a decoding.
		//==================================================================
		const u16 lo = u16(upd6383_disassembler::lo12(word));
		const u8  ad = upd6383_disassembler::addr8(word);

		//==================================================================
		//  ★★★ THE EXTERNAL DELAY DRAM (IC309) -- SPECULATIVE, 2026-07-28.
		//
		//  AS_DELAY has been DECLARED and driver-MAPPED all along and NEVER
		//  ACCESSED: grep found zero reads and zero writes in this device.  A
		//  delay line that is never written cannot produce an echo, so every
		//  time-based effect -- delay, reverb, chorus, flanger -- was
		//  structurally impossible no matter how correct the ALU became.
		//  dark-words.md sect. 5.3 named this as the one failure "structurally
		//  out of reach of ALU decoding", 48.8 % of the dark set.
		//
		//  WHAT IS MEASURED
		//    * the DIRECTION field: addr8 0x20/0x30 = READ, 0x60 = WRITE
		//      (adjudication-round5 item D, FORCED by two independent routes).
		//    * the REGION split: unit 0 below 0x8000, unit 1 above
		//      (adjudication-round4 sect. 2, MEASURED over 486+384 cells).
		//    * the descriptor cells themselves, in D-RAM at m_dsc (ldptr.d).
		//
		//  WHAT IS GUESSED
		//    * that the Nth delay word of a frame consumes the Nth descriptor
		//      cell.  This mirrors how dsp/tools/delayline.py pairs `cons' with
		//      `cells', which is where every measured tap length in this project
		//      comes from -- but the pairing is an ASSUMPTION, not a decoding.
		//    * that the line rotates by ONE cell per frame, which is what makes
		//      a descriptor DIFFERENCE a delay in samples (SINGLE DELAY's
		//      501/500 and NO OPERATION's 4410 = exactly 100.000 ms at 44.1 kHz
		//      both fall out of this, which is the strongest support it has).
		//    * the 24 -> 16 bit truncation: the DRAM is 16 bits wide and the
		//      datum is 24, so the top 16 are stored.  UNVERIFIED.
		//==================================================================
		//  ★★★★ §77: re-entrancy guard.  §76 calls exec_alu() from inside this very
		//  branch so a delay word can run its ALU with the fetched datum on the bus.
		//  Without `!m_in_dram' the recursive call re-enters here, performs a SECOND
		//  port access and returns -- so the ALU half never ran and SRC 0x0B was
		//  reached 0 times out of 19 096 320 delay-path entries.  Same shape as the
		//  m_in_k6 guard the K6 input stage already needed.
		if (upd6383_disassembler::is_dram(word) && !m_in_dram)
		{
			const char dir = upd6383_disassembler::dram_dir(word);
			//  ★★★ §47 SPECULATIVE (mask bit 9): TAKE THE DESCRIPTOR FROM THE
			//  PER-UNIT C-RAM BANK, NOT FROM D-RAM AT m_dsc.
			//  MEASURED: with the D-RAM source, the descriptor cell is 0x0000 on
			//  essentially every one of ~64 M accesses (dsc 0x25..0x2C all read
			//  0000), so every tap addresses the SAME rotating cell and there is no
			//  delay line at all.  Nothing writes those D-RAM cells: the host's only
			//  write path reaches C-RAM.
			//  Where the descriptors ARE: the two host-written C-RAM runs the body's
			//  cursor is deliberately aimed at -- this file's own note records the
			//  three loads, "iw42 -> 0x70 (unit 0), iw50 -> 0x50 (unit 1), iw69 ->
			//  0x90 (the epilogue)".  And their CONTENTS match the MEASURED per-unit
			//  region split exactly:
			//      bank 0x70 (unit 0) : 0x0000..0x7FFF  -> unit 0 region, below 0x8000
			//      bank 0x50 (unit 1) : 0x8000..0xFC00  -> unit 1 region, above 0x8000
			//  (adjudication-round4 §2, "unit 0 below 0x8000, unit 1 above", measured
			//  over 486+384 cells).  Two independent structures agreeing.
			//  ⇒ a class-A delay word FETCHES ITS OWN ADDRESS from the per-unit bank.
			//  That also explains §44: read as Q0.23 those cells are ~0.007, and
			//  multiplying by them is what destroyed the signal.
			//  ★ §60: read the descriptor from the BANK the host now fills.
			//  ★★★ §209: ONE cell, computed ONCE, used by every probe below.
			//  `dsc_cell()' is the PER-UNIT RING (see upd6383.h): the base is not a
			//  register -- every register candidate is dead by the gcd(d,256)|38
			//  argument -- it is per-unit state established at the CALL.  ⚠ It has
			//  side effects (the fired counters), so it must be called EXACTLY once
			//  per consumer; that is also what §207/§208 demand, since the old
			//  re-derived `u8(m_dsc + m_delay_ix)' labels were read AFTER the
			//  increment at :1927 and were +1 for every body consumer.
			const u8  dsc   = dsc_cell();
			const u32 cellv = (m_speculative && (m_specmask & 0x200))
					? (m_cram.read_dword(m_cursor) & 0xffff)
					: u32(m_dscbank[dsc]);
			if (m_speculative && (m_specmask & 0x200)
					&& upd6383_disassembler::coeff_consumer(word))
				m_cursor++;
			//  ★ §46: is the delay port FED?  It reads its descriptors from D-RAM at
			//  m_dsc, but the host's only write path reaches C-RAM -- where two
			//  address-shaped ramps sit at 0x50..0x8B (§44).  Count what arrives.
			{
				if (dir == 'W') m_dly_w++; else if (dir == 'R') m_dly_r++;
				if (cellv) m_dly_cell_nz++;
				if (m_dly_n < 8)
				{
					bool seen = false;
					for (u32 q = 0; q < m_dly_n; q++)
						if (m_dly_dsc[q] == dsc) seen = true;      // ★ §209: the real cell
					if (!seen)
					{
						m_dly_dsc[m_dly_n] = dsc;
						m_dly_val[m_dly_n] = cellv;
						m_dly_dir[m_dly_n] = u8(dir);
						m_dly_n++;
					}
				}
			}
			//  ★★★ §204 CONSUMER-TO-CELL CENSUS (read-only).  round5 §1's IDENTITY
			//  map FORCES "the k-th class-1 format-escape consumer takes the k-th
			//  descriptor cell of ITS OWN BODY's block".  §203 could not be graded
			//  because the delay census only reports lines that RESOLVE.  This
			//  reports the mapping itself: per body, which index each consumer took.
			{
				//  ⚠ SAMPLE A SETTLED FRAME.  The first version recorded the first 16
				//  consumers EVER -- all from boot, before the program is uploaded:
				//  body 0 logged `iw12' sixteen times with cell 0000, and both arms of
				//  the CFMTIX A/B were identical because the gate never fires there.
				//  Same defect as §193's first probe.  §162 uses ~970 k as the settled
				//  threshold; this uses 900 k.
				const int b = (m_cur_iw >= 200) ? 1 : 0;
				if (m_frames_run > 900000 && m_c2c_n[b] < 16)
				{
					const int k = m_c2c_n[b]++;
					m_c2c_ix[b][k]  = u8(m_delay_ix);
					m_c2c_iw[b][k]  = m_cur_iw;
					m_c2c_cell[b][k] = u16(cellv);
					//  ★ §209: the cell NUMBER, recorded at the site that used it.
					//  §208 removed the printed label because it was RE-DERIVED at
					//  print time from an m_dsc the bodies never ran with; this is
					//  the addressed cell itself, so it is a measurement and not a
					//  reconstruction.  Both are printed: index, cell, value.
					m_c2c_dsc[b][k] = dsc;
				}
			}
			m_delay_ix++;
			//  ★★★ §153: + the modulation offset.  `m_frames_run' is the
			//  circular-buffer rotation G (r3-delaydram.md §5.1); `m_tapmod' is the
			//  swept-tap term the model has never had.
			//  ★★★ §200: THE ROTATION SIGN.  `adjudication-round5.md' §3 FORCES
			//  `delay = READ_CELL - WRITE_CELL'.  With G RISING a read at R+T returns
			//  the sample written at T' = T + (R-W) -- a FUTURE sample -- so the only
			//  consistent reading is the COMPLEMENT, 65536-(R-W): 1.478 s where 7.60 ms
			//  was intended.  With G FALLING it is (R-W) samples, correct. (§199)
			//  ⚠ The u64 spec mask is EXHAUSTED, so this uses an env gate, the same
			//  mechanism §104 used (UPD6383_AB_NOSTORE08).
			//  ⚠⚠ `G' CANCELS in R-W, so NO address measurement can grade this --
			//  every existing probe is bit-identical across it.  The falsifier is the
			//  §200 write-timestamp census below, and nothing else.
			const u32 rot = m_rotsign ? (0u - u32(m_frames_run)) : u32(m_frames_run);
			if (m_rotsign) m_rotsign_n++;
			const u32 addr = (cellv + rot
					+ ((m_speculative && (m_specmask & (1ull << 60)))
						? u32(s32(m_tapmod)) : 0u)) & 0xffff;
			//  ★ §200 PROBE: tag every delay WRITE with its frame; at every READ
			//  report how many frames ago that address was written.  THAT is the
			//  delay, and it is the only quantity the sign changes.
			{
				//  ⛔ §207/§209: this label WAS `u8(m_dsc + m_delay_ix)' read AFTER
				//  :1927's increment -- +1 for every body consumer, which is how
				//  §202's two "bit-exact" numbers came to be body-1 consumers
				//  reading body-0's block.  It is now the cell the consumer
				//  ACTUALLY read, computed once above.  ⚠ §202's numbers therefore
				//  MOVE, by construction; that is the correction, not a regression.
				if (dir == 'W') { m_dts[addr] = u32(m_frames_run); }
				else if (dir == 'R' && m_dts[addr])
				{
					const u32 age = u32(m_frames_run) - m_dts[addr];
					int sl = -1;
					for (int q = 0; q < m_age_n; q++) if (m_age_dsc[q] == dsc) { sl = q; break; }
					if (sl < 0 && m_age_n < AGE_SLOTS) { sl = m_age_n++; m_age_dsc[sl] = dsc;
						m_age_min[sl] = m_age_max[sl] = age; }
					if (sl >= 0)
					{
						m_age_min[sl] = std::min(m_age_min[sl], age);
						m_age_max[sl] = std::max(m_age_max[sl], age);
						m_age_hits[sl]++;
					}
				}
			}
			{   //  ⛔ §154 FIX: census the MODULATION TERM, not the absolute address.
				//  §153's census took the range of `addr' per cell over the whole run
				//  and got 65535 for every cell in BOTH arms -- because `m_frames_run'
				//  (the rotation G) ramps across the entire 16-bit space by itself, so
				//  an absolute-address range can only ever return 65535.  My own F2
				//  fired and voided that run: the census could not fail in the other
				//  direction.  The modulation term is what has to be measured.
				const u32 k = cellv & 0x3f;
				const s32 t = (m_speculative && (m_specmask & (1ull << 60))) ? m_tapmod : 0;
				if (!m_tap_seen[k]) { m_tap_seen[k] = true; m_tap_lo[k] = m_tap_hi[k] = u32(t); }
				else { if (s32(m_tap_lo[k]) > t) m_tap_lo[k] = u32(t);
				       if (s32(m_tap_hi[k]) < t) m_tap_hi[k] = u32(t); }
			}
			if (dir == 'W')
			{
				//  ★ §75: is anything with CONTENT being written?  The store takes
				//  acc_to_datum(m_acc) -- ACCA -- but under bit 14 the unit-1 body
				//  accumulates into ACCB, so this writes ACCA (empty during body 1).
				//  Same unit-blind defect as §66/§68, third instance.
				const u64 wacc = (m_speculative && (m_specmask & 0x4000) && m_cur_unit1)
						? m_accb : m_acc;
				const u16 wv = u16((u32(acc_to_datum(wacc)) >> 8) & 0xffff);
				if (wv) m_dly_w_nz++;
				if (m_dly_dbg < 6 && m_frames_run > 420000)
				{
					m_dly_dbg++;
					logerror("upd6383: §75 DLY %c addr %04X  cell %04X  frame %u  data %04X\n",
							dir, addr, cellv, u32(m_frames_run), wv);
				}
				m_delay.write_word(addr, wv);
			}
			//  ★★★★ §74 SPECULATIVE (mask bit 19): A DELAY WORD ALSO RUNS ITS ALU.
			//  MEASURED over the twelve unit-1 reverbs: ALL 168 words carrying
			//  SRC 0x0B (the delay-read register) are class4 == 1 with the escape
			//  bit -- i.e. is_dram claims EVERY one of them -- and every one has
			//  addr8 = 0x60, the WRITE direction.
			//  So the delay WRITE word is itself the delay-read CONSUMER: it stores
			//  to the line and reads the read-register onto its bus in the same
			//  word.  That is dram-datapath.md item F in its own words -- "the
			//  structural argument moves onto the WRITE word, which is the pipeline".
			//  This branch `return'ed after the port access, so their ALU never ran:
			//  §48 measured SRC 0x0B consumed 1.0 times per frame against ~20.8
			//  delay reads issued.  The ladder therefore had NO per-pass feedback
			//  term, which is §73's "a loop whose behaviour does not change when its
			//  gains change is not being attenuated by them at all".
			const bool run_alu = m_speculative && (m_specmask & 0x80000) && !m_in_dram;
			//  ★★★★ §76 (mask bit 20): THE PIPELINE IS KEYED TO THE PORT, NOT TO THE
			//  SLOT COUNTER.  dram-datapath.md item A: "THE DRAM PORT IS A ONE-DEEP
			//  PIPELINE" -- ONE OUTSTANDING ACCESS.  §49 implemented a slot-indexed
			//  ring (datum lands `land' slots later), which is a different machine:
			//  §75 measured 491 520 consumptions all seeing zero because the consumer
			//  never executes on the scheduled slot.
			//  §74 says why it cannot: the consumer is the delay WRITE word itself,
			//  which sits a VARIABLE number of ordinary words after its read.
			//  So: a read LATCHES into a pending register; the NEXT delay word
			//  publishes it, runs its ALU with the datum on the bus, and only then
			//  performs its own port access.  Order matters -- a write must store the
			//  accumulator AFTER the ALU has updated it.
			const bool port_pipe = m_speculative && (m_specmask & 0x100000);
			//  ★★★★ §78: THE OUTSTANDING ACCESS IS PER-LINE, NOT PER-PORT.
			//  §77 made all ~19 consumers per frame fire, and every one saw zero,
			//  because ONE pending register cannot serve nineteen.  Every delay word
			//  is both a consumer and an issuer.
			//  The line identity is the DESCRIPTOR VALUE: §59-60 measured the bank
			//  holding each value TWICE, five cells apart (51E2 at 02 and 07, 5460 at
			//  06 and 0B ...) -- one read and one write per line, sharing a descriptor.
			//  With addr = (desc + frame) & 0xffff, reading a walking address and then
			//  overwriting it is exactly a circular delay line whose lag is the buffer
			//  length.  So a read latches under ITS OWN descriptor and the write that
			//  shares that descriptor collects it.
			const u32 line = cellv & 0x3f;
			if (port_pipe) m_pub_try++;
			if (port_pipe && m_dr_line_v[line])
			{
				m_pub_hit++; if (m_dr_line[line]) m_pub_nz++;
				m_dr = m_dr_line[line];
				//  ★★★ §217: carry the tag with the datum.  Read-only, both arms.
				m_dr_prov_iw    = m_dr_line_iw[line];
				m_dr_prov_line  = u8(line);
				m_dr_prov_frame = m_dr_line_frame[line];
				//  WHERE does the datum `iw12' fetched actually get published?
				if (m_frames_run > 900000 && m_dr_prov_iw == 12)
					prov_bump(m_p12_iw, m_p12_n, nullptr, m_p12_cnt, m_p12_other,
							m_cur_iw, false);
				//  ...and does ANY publish fire between iw12 and iw25?  Structurally
				//  no -- the kernel has no delay word in iw13..iw24 -- but asserting
				//  that is not measuring it.
				if (m_cur_iw > 12 && m_cur_iw < 25) m_pub_between++;
				m_dr_line_v[line] = false;
				m_dr_landed++;
			}
			if (port_pipe && run_alu)
			{
				m_dly_alu++;                       // ★ §77: is this path taken at all?
				m_in_dram = true;
				exec_alu(word);
				m_in_dram = false;
			}
			else if (port_pipe)
				m_dly_noalu++;
			if (dir == 'R')
			{
				const u32 datum = u32(m_delay.read_word(addr)) << 8;
				if (m_dly_dbg < 6 && m_frames_run > 420000)
				{
					m_dly_dbg++;
					logerror("upd6383: §75 DLY R addr %04X  cell %04X  frame %u  got %06X\n",
							addr, cellv, u32(m_frames_run), datum);
				}
				if (datum) m_dly_r_nz++;
				if (port_pipe)
				{   // ★ §78: latch under this line's descriptor
					m_dr_line[line] = datum; m_dr_line_v[line] = true; m_latch_n++;
					if (datum) m_latch_nz++;
					//  ★ §217: tag the latch with the word that performed the READ
					m_dr_line_iw[line]    = m_cur_iw;
					m_dr_line_frame[line] = m_frames_run;
					//  ★★★ §217 (UPD6383_DRPUB, DEFAULT OFF): ALSO put the datum on the
					//  bus register now.  This site is AFTER `exec_alu' above, so a
					//  fused read+capture word still does not see its own datum
					//  (`dram-datapath.md' item A survives); and `m_dr_line[]' is
					//  untouched, so §79's pairing and §80's counters are identical
					//  across the arms -- which is PREDICT_217 N4.
					if (m_drpub)
					{
						m_drpub_fired++;
						m_dr = datum;
						m_dr_prov_iw    = m_cur_iw;
						m_dr_prov_line  = u8(line);
						m_dr_prov_frame = m_frames_run;
					}
				}
				else if (m_speculative && (m_specmask & 0x400))
				{   // ★ §49: schedule it `land' slots ahead, do NOT publish now
					const u32 k = (m_slotn + m_land) & 7;
					if (m_dr_pipe_v[k]) m_dr_lost++;   // ring collision = model too shallow
					m_dr_pipe[k] = datum;
					m_dr_pipe_v[k] = true;
				}
				else
					m_dr = datum;
			}
			if (run_alu && !port_pipe)
			{   // now let the word do its datapath work, with m_dr on the bus
				m_in_dram = true;
				exec_alu(word);
				m_in_dram = false;
			}
			return;
		}

		//  ★★★ CLASS-1 REGISTER-FILE WORDS: lo12[10:6] IS AN OUTPUT-SLOT SELECTOR,
		//  NOT A SOURCE.  Register section 5, INFERRED (strong):
		//    * SRC 0x02..0x06 are ABSENT from all 2974 body words and SRC 0x01
		//      occurs only as class 0 -- so these codes exist nowhere in the machine
		//      except here, ONCE EACH, in the kernel/epilogue.
		//    * six codes, and this chip's output latch is m_do[3][2] = SIX SLOTS.
		//  addr8 names the register supplying the value; ACT says what is done;
		//  lo12[10:6] says WHERE IT GOES.  ⛔ The slot->code MAPPING is untested --
		//  slot = SRC-1 in natural order is the obvious reading and nothing more.
		const u16 hi_sp = upd6383_disassembler::hi12(word);
		const u8  src_sp = upd6383_disassembler::lo_src(word);
		//  ★ ADJUDICATION sect.5 vs sect.6.1.  The two readings concern DIFFERENT
		//  fields -- sect.5 is lo12[10:6], sect.6.1 is lo12[4:0] and its store
		//  target -- and on the ten kernel/epilogue words those fields CO-VARY:
		//      ACT 0x07 (store) <-> SRC 0x00, 0x02, 0x03, 0x04
		//      ACT 0x1B         <-> SRC 0x01, 0x05, 0x06
		//      ACT 0x01         <-> SRC 0x07
		//  A free six-slot selector would pair with any ACT.  This partition says
		//  the routing reading belongs to the NON-STORE words, so an ACT 0x07 word
		//  falls through to the ALU and performs its mode-1 store instead.
		//  ⛔⛔ REFUTED 2026-07-28 by r2-output.md §3.2, which had already inventoried
		//  these very words -- and which this rule was written without reading (the
		//  "check the handover first" failure, again).  Instrumenting the three words
		//  this rule actually fires on gave:
		//        slot0  012.1.8D.05B   reads reg 0x8D   peak 0
		//        slot4  092.1.8D.15B   reads reg 0x8D   peak 0
		//        slot5  092.1.8C.19B   reads reg 0x8C   peak 504
		//  Those are exactly w61, w60 and w68, and §3.2 classifies all three as
		//  INTERNAL register writes -- w68 explicitly "read at w66 first => a state
		//  register".  They are not outputs at all.  The REAL presentations are
		//  w73 (E30.C.00.404, unit 0 -> DO1) and w78 (A3C.D.9F.287, unit 1 -> DO2),
		//  which are class 0xC / 0xD and are handled by the presentation path below.
		//  Keeping this rule hijacked three internal writes onto the output latches,
		//  which is why DO2 was never written and DO3 carried a signal that
		//  §3.2 predicts it never carries.  Disabled; the words now fall through to
		//  the ALU and perform their mode-1 store, which is what they are.
		if (false && cl == 1 && !(hi_sp & 0x800) && src_sp >= 0x01 && src_sp <= 0x06
				&& upd6383_disassembler::lo_act(word) != upd6383_disassembler::LO_ACT_ST_BUS)
		{
			const u32 slot = src_sp - 1;
			const s32 v = s32(util::sext(m_dram.read_dword(ad) & 0xffffff, 24));
			//  ⛔ The diagnostic remap onto ports 0/1 was tried and REVERTED: the
			//  resulting wet was rms 1.0 -- a +/-1 LSB constant present even in
			//  silence -- so the live presentation carries no audio signal, and
			//  asserting a routing the evidence does not support bought nothing.
			m_do[slot >> 1][slot & 1] = v;
			m_out_slot_writes[slot]++;
			if (v) m_out_slot_nonzero[slot]++;
			m_out_slot_reg[slot]  = u16(ad);
			m_out_slot_word[slot] = word;
			if (std::abs(v) > std::abs(m_out_slot_peak[slot])) m_out_slot_peak[slot] = v;
			return;
		}
		if (m_row13 && (cl == 0xC || cl == 0xD))
		{
			//  ★★★ §29 2026-07-28: DEFER THE PRESENTATION UNTIL AFTER THE ARITHMETIC.
			//  This branch used to `return', which skipped the multiply at the bottom
			//  of this very function -- so w73 (class C) and w78 (class D), the two
			//  output presentations, NEVER FORMED A PRODUCT.  MUL = '.' at both, in
			//  every frame.  r2-output.md §3.1 says these words fetch a coefficient
			//  (class4 bit 3) precisely because an output-level multiply needs one:
			//  w73 is `ACCA <- level x ACCA' and then presents.  So the word must run
			//  the ALU FIRST and present the RESULT, not present and return.
			m_pres_unit    = (ad & 0x80) ? 1 : 0;
			if (m_specmask & 8)
				m_pres_pending = true;      // present AFTER the arithmetic (§29)
			else
			{   // the pre-§29 behaviour: present the stale accumulator and return
				do_presentation();
				return;
			}
		}
		if (cl == 6)
		{
			//==================================================================
			//  ★★★ §162 PROBE (read-only, always on): WHAT IS THE INDEX?
			//
			//  K2 needs the table INDEX, and §161 only supplied the table.  The
			//  owning note (`lfo-ramp.md' §10) MEASURED the scale coefficient as
			//  `0x000018' = 24 at 8 of 8 sites and reads the idiom as
			//  `(coef x phase) >> 23' -> an integer 0..23.  That fixes the arith-
			//  metic but NOT where `phase' lives.  Guessing it would be a fourth
			//  hypothesis about a datapath I have not instrumented, so: measure.
			//
			//  ⚠ THE NULL, stated before running.  If the accumulator at this site
			//  is the phase it must SWEEP -- min != max, spanning a large fraction
			//  of 2^23, at the LFO rate.  If min == max the phase is NOT in the
			//  accumulator and the candidate is refuted, exactly as §158 refuted
			//  "the tap sweeps" by finding a constant.  A probe that cannot come
			//  back constant would not be a test.
			//  ★ And §137's rule is in force: read min AGAINST max before calling
			//  anything a signal.
			{
				int slot = -1;
				for (int i = 0; i < m_c6_n; i++) if (m_c6_word[i] == word) { slot = i; break; }
				if (slot < 0 && m_c6_n < 8) { slot = m_c6_n++; m_c6_word[slot] = word; }
				if (slot >= 0)
				{
					const s64 a = util::sext(m_cur_unit1 ? m_accb : m_acc, 44);
					//  ★★★ §167: `m_tb' IS THE CANDIDATE INDEX and this is the rule-4
					//  gate on it.  §166 measured C63 + class-6 as ONE idiom -- 53 of
					//  53 in BOTH directions, against a base-rate null of 0.94 -- and
					//  C63 is `SRC 0x11 / ACT 0x03' = `m_tb = L'.  So the shape is
					//  "load the index register, then read the table indexed by it".
					//  ⚠ BEFORE implementing `table[m_tb]', measure that m_tb VARIES.
					//  §162 censused acc/m_dp/cursor and never looked at the temps; if
					//  m_tb is constant the lookup is frozen and building it
					//  manufactures exactly the false null §162 exists to prevent.
					//  m_ta/m_k/m_l ride along -- they are the other registers a
					//  varying index could plausibly arrive in, and enumerating all
					//  four costs nothing while guessing one costs a run.
					const s64 tb = s64(s32(util::sext(m_tb, 24)));
					const s64 ta = s64(s32(util::sext(m_ta, 24)));
					const s64 kk = s64(s32(util::sext(m_k,  24)));
					//  ★★★ §169: `m_p' -- THE ONE REGISTER §167 DID NOT READ, and the
					//  one the arithmetic points at.  lfo-ramp.md §10 reads the idiom
					//  as `(coef x phase) >> 23' with coef = 24, and §167 MEASURED
					//  m_k = 24 here: the scale is already in the multiplier input
					//  latch.  Its product with the phase lands in m_p.
					const s64 pp = util::sext(m_p, 44);
					m_c6_pwseen[slot] |= (1u << (m_pw & 31));   // §175
					const s64 ll = s64(s32(util::sext(m_l,  24)));
					if (!m_c6_hits[slot])
					{
						m_c6_amin[slot] = m_c6_amax[slot] = a;
						m_c6_pmin[slot] = m_c6_pmax[slot] = m_dp;
						m_c6_cmin[slot] = m_c6_cmax[slot] = m_cursor;
						m_c6_tbmin[slot] = m_c6_tbmax[slot] = tb;
						m_c6_tamin[slot] = m_c6_tamax[slot] = ta;
						m_c6_kmin[slot]  = m_c6_kmax[slot]  = kk;
						m_c6_lmin[slot]  = m_c6_lmax[slot]  = ll;
					}
					else
					{
						m_c6_amin[slot] = std::min(m_c6_amin[slot], a);
						m_c6_amax[slot] = std::max(m_c6_amax[slot], a);
						m_c6_pmin[slot] = std::min<u32>(m_c6_pmin[slot], m_dp);
						m_c6_pmax[slot] = std::max<u32>(m_c6_pmax[slot], m_dp);
						m_c6_cmin[slot] = std::min<u32>(m_c6_cmin[slot], m_cursor);
						m_c6_cmax[slot] = std::max<u32>(m_c6_cmax[slot], m_cursor);
						m_c6_tbmin[slot] = std::min(m_c6_tbmin[slot], tb);
						m_c6_tbmax[slot] = std::max(m_c6_tbmax[slot], tb);
						m_c6_tamin[slot] = std::min(m_c6_tamin[slot], ta);
						m_c6_tamax[slot] = std::max(m_c6_tamax[slot], ta);
						m_c6_kmin[slot]  = std::min(m_c6_kmin[slot],  kk);
						m_c6_kmax[slot]  = std::max(m_c6_kmax[slot],  kk);
						m_c6_lmin[slot]  = std::min(m_c6_lmin[slot],  ll);
						m_c6_lmax[slot]  = std::max(m_c6_lmax[slot],  ll);
					}
					if (!m_c6_hits[slot]) { m_c6_pmin2[slot] = m_c6_pmax2[slot] = pp; }
					else
					{
						m_c6_pmin2[slot] = std::min(m_c6_pmin2[slot], pp);
						m_c6_pmax2[slot] = std::max(m_c6_pmax2[slot], pp);
						if (pp != m_c6_pprev[slot]) m_c6_pchg[slot]++;
					}
					m_c6_pprev[slot] = pp;
					if (m_c6_hits[slot] && tb != m_c6_tbprev[slot]) m_c6_tbchg[slot]++;
					m_c6_tbprev[slot] = tb;
					m_c6_hits[slot]++;
				}
			}
			// table-lookup idiom: no table is modelled, so execute the
			// addressing and leave the ALU alone.
			if (upd6383_disassembler::coeff_consumer(word))
				m_cursor++;
			return;
		}
		if (word == 0 || cl == 5 || (hi_esc && lo == 0x015) || (hi_esc && lo == 0x041))
			return;                 // NOP / no modelled side effect

		//  Everything else the speculative gate admits falls through into the
		//  normal path below, where the widened SRC/ACTION defaults apply.
	}

	const u16 hi = upd6383_disassembler::hi12(word);
	const u8  cl = upd6383_disassembler::class4(word);
	const s8  dd = s8(upd6383_disassembler::addr8(word));
	const u8  src = upd6383_disassembler::lo_src(word);
	const u8  act = upd6383_disassembler::lo_act(word);

	// ---- the operand bus, latched before anything else ---------------------
	// alu_decoded() admits only the four ANCHORED source codes, so there is
	// deliberately no default case that guesses at the other fourteen the
	// corpus contains.
	s32 L = 0;
	//  ★★★ §221 §E1: WHICH ROUTE DID THE C++ ACTUALLY TAKE, and to WHICH INDEX?
	//  Set INSIDE the case that runs -- never re-derived afterwards, because a
	//  re-derivation is a second copy of the decision that can drift from it (the
	//  `alu_guard_fail' lesson, and §218's lo12-by-eye lesson).  Read once, at the
	//  `m_last_l = L' statement below, which is the single point where the operand
	//  bus is final.
	u8  e1route = E1_NONE;
	u16 e1idx   = 0;
	//  ★ SRC 0x0B = the delay-DRAM data register.  A delay READ has to land
	//  somewhere for the next word to use, and 0x0B is the only source code in the
	//  corpus whose operand is otherwise unaccounted for.
	//  ⚠ IT WAS ORIGINALLY A GUESS (register row 14) AND IT IS NOT ONE ANY MORE --
	//  do not re-open it.  §215 ANCHORED it by the corpus over 41 listings / 3057
	//  words: `lo12 0x2D9' is a 36-word family whose consumer `0012201655'
	//  (`mac ta', 0.43 % base rate) is IMMEDIATELY preceded by a class-1 addr8 0x20
	//  DELAY READ at 13 of 13 sites, and ENSEMBLE fuses read+capture into one `2D9'
	//  where the kernel splits the identical `2D9' off one word ahead of its read.
	//  §217 graded it BY PROVENANCE and §218 re-verified the population (7 class-2
	//  words, below) with the disassembler's own field accessors.
	//  ★★★ §219: AND IT IS NOT WHAT CLOSES THE UNIT-0 SEND, which is the question
	//  it kept being re-opened for.  No SRC on the send path decides a stored value:
	//  the delay WRITE at :2081 and the HI_ST store at :2942 both take
	//  `acc_to_datum(m_acc)', never the bus, so `SRC 0x0B' reaches the delay line
	//  only as a MULTIPLICAND (tempA -> P = coef x tempA -> acc).  The send is D-RAM
	//  cell 0x05, and what closes it is kernel `iw35' overwriting the audio that
	//  `iw9'/`iw11' deposited there.  See dsp/tools/src0b_census.py sendpath.
	//  ★★★ THE UNANCHORED SOURCE CODES, 2026-07-28, register row 20.
	//  The default: branch below warns that widening alu_decoded() must not let an
	//  unanchored source quietly become a memory read, and that "leaving L at 0 is
	//  the failure that shows".  The speculative gate widened it, and that failure
	//  duly showed: SRC 0x00/0x08/0x11/0x13/0x1B/0x1C all read ZERO, so the
	//  multiplies feeding P multiplied by nothing and the accumulator died.
	//
	//  Readings taken from the research model (dsp/tools/action00_discriminate.py),
	//  where each is an ENUMERATED parameter rather than a fixed choice:
	//    SRC 0x08 = the COEFFICIENT.  ★ MEASURED: it is the setting under which the
	//               LFO's phase accumulator reproduces its ROM ramp constant exactly
	//               (mem[0x04] 1000 -> 1228, step +228 = coefficient 0x0000E4), and
	//               11 of 19 such constants across the corpus.  The rival "unity"
	//               saturates the accumulator on the LFO's first word.
	//    SRC 0x00 = mem[ptr]   ⛔ 1 of 6 enumerated, no independent support
	//    SRC 0x11 = ACCB       ★ §27 -- was mem[ptr] (1 of 7 enumerated); replaced
	//  0x13, 0x1B and 0x1C have NO reading anywhere and keep reading zero; they are
	//  counted so the next pass can see whether they matter.
	if (m_speculative)
	{
		switch (src)
		{
		case 0x0B:
			//  ★ §48: is the DELAY READ ever consumed?  The is_dram branch returns
			//  before the ALU, so a delay datum reaches the ladder ONLY through this
			//  source code.  If nothing reads it, the delay line is write-only and
			//  the ladder has no feedback term -- which is why removing the (bogus)
			//  tap multiplies in §44 left it with unity gain per stage, and why it
			//  saturates: acc peaks are exact small-integer multiples of one quantum
			//  and tA sits at 0x7FFFFF.
			m_dr_reads++;
		if (m_in_dram) m_dly_alu_0b++;      // ★ §77: reached from a delay word?
			if (m_dr) m_dr_reads_nz++;
			//  ★★★ §215: THE CLASS-2 SRC-0x0B WORD, WHICH THE 0x0B GUESS WAS NEVER
			//  MOTIVATED BY.  Of 106 corpus `SRC 0x0B' words, 99 are class-1 delay
			//  words (addr8 0x20 READ / 0x60 WRITE) and 7 are class 2 addr8 0x00 --
			//  ENSEMBLE's `020.2.00.2C7' x6 and the resident kernel's
			//  `000.2.00.2D9' x1, which is `iw25', the word that decides what the
			//  unit-0 send carries (§213 §4).  Counted UNCONDITIONALLY so a
			//  default run measures the null: what the rival WOULD have delivered.
			//  ⚠ c-format words have NO class4 field at all (upd6383d.h:49), so they
			//  are excluded rather than misclassified.  MEASURED over the 41 listings:
			//  0 of 3057 c-format words carry SRC 0x0B, so the guard is a no-op on
			//  every shipped program and exists only to keep the counter unambiguous.
			//  ★★★ §218: THE `7' ABOVE IS RIGHT AND HAS BEEN SINCE §215 -- DO NOT
			//  RE-DERIVE IT BY EYE.  §217 sect.5 recounted it in prose, read lo12's
			//  ACTION field (lo12[4:0]) as its SOURCE field (lo12[10:6]), and got 9 by
			//  sweeping in `000.2.00.40B' (ENSEMBLE w62) and `000.2.09.40B' (MULTI TAP
			//  w25) -- whose SRC is 0x10, THE ACCUMULATOR; only their ACTION is 0x0B.
			//  It then built a handover question on the two impostors.  Eleven distinct
			//  lo12 values occur on BOTH class-1 delay words and class-2 words (the
			//  kernel's own iw26 is `880.1.20.40B'), so lo12 carries no class
			//  information at all.  Census it with dsp/tools/src0b_census.py, which
			//  uses the disassembler's own lo_src()/lo_act().  (Standing rule 18.)
			//  ⛔ §218 also RETIRED the cross-frame rival for this word: the §217
			//  provenance histogram below is SINGLE-BIN `iw289' in the shipped arm, and
			//  41 delay words (21 READS) separate iw26 of frame N-1 from iw25 of frame
			//  N, so a one-deep m_dr cannot be carrying the FOLLOWING read's datum.
			//  `UPD6383_DRPUB's age 0 is CORRECT; it stays default OFF only because it
			//  is bit-identical to the control while the delay line is empty.
			if (cl != 1 && !upd6383_disassembler::c_format(word))
			{
				m_src0b2_n++;
				if (m_dram.read_dword(m_dp) & 0xffffff) m_src0b2_memnz++;
				if (m_dr) m_src0b2_drnz++;
				//  ★★★ §217 PROVENANCE, READ-ONLY, BOTH ARMS.  Not "is the operand
				//  alive" (standing rule 15 -- every live operand passes that) but
				//  WHICH WORD READ IT.  Settled frames only: before the host uploads
				//  the descriptor bank every cell reads 0000, so every line is 0 and
				//  the histogram would be boot, not steady state (§193/§204's trap).
				if (m_frames_run > 900000)
				{
					m_prov_tot++;
					prov_bump(m_prov_iw, m_prov_n, m_prov_nz, m_prov_cnt, m_prov_other,
							m_dr_prov_iw, m_dr != 0);
					const u64 age = m_frames_run - m_dr_prov_frame;
					if (age < m_prov_age_min) m_prov_age_min = age;
					if (age > m_prov_age_max) m_prov_age_max = age;
				}
				//  ⚠ DEFAULT OFF.  The rival: on a word that performs NO delay
				//  access the code cannot be naming the delay port, so it names
				//  what every other unanchored source in this device resolves to.
				//  ⛔ Passing the §1.2 falsifiers does NOT confirm this reading --
				//  `iw25's pointer sits on a LIVE cell, so any live operand scores
				//  4/4.  See data/PREDICT_215.md §0, committed before this build.
				if (m_src0b2)
				{
					m_src0b2_fired++;
					L = s32(util::sext(m_dram.read_dword(m_dp) & 0xffffff, 24));
					e1route = E1_DRAM_PTR; e1idx = m_dp;                 // §221 §E1
					break;
				}
			}
			L = s32(util::sext(m_dr, 24));
			e1route = E1_DR;                                            // §221 §E1
			break;
		case 0x08:
			L = s32(util::sext(m_cram.read_dword(m_cursor) & 0xffffff, 24));
			e1route = E1_CRAM; e1idx = u16(m_cursor);                   // §221 §E1
			break;
		case 0x00:
			//  ★ §123: this reading is BETTER SUPPORTED than the neighbouring
			//  comments suggest, and the elsewhere-quoted "1 of 6 enumerated, no
			//  independent support" is STALE.  action00-discriminator.md item I
			//  ran the constraint solve: of the rival readings, `zero` (a null
			//  routing) has 0 SURVIVORS and `DR` (the delay-RAM register) has 0,
			//  in every SINGLE DELAY variant, both windows, both mix settings.
			//  "SRC 0x00 carries data."
			//  ⚠ Item H states the limit precisely: mem[ptr] is NOT forced
			//  absolutely, it is forced GIVEN THE LOADED COEFFICIENTS.
			//  ⛔ The null-routing reading is attractive and WRONG: 572 of 599
			//  SRC-0x00 words are exactly lo12 == 0x000 and pair with ACTION 0x00,
			//  where anchored SRC 0x07 appears with nine different actions -- which
			//  is exactly what a null encoding looks like.  §122 re-derived that
			//  hypothesis from the corpus and item I had already killed it.
			//  ★★★ §145 (mask bit 57): SRC 0x00 = coef, i.e. C-RAM[cursor] -- what
			//  SRC 0x08 delivers.  NEVER ENUMERATED: action00_discriminate.py's
			//  src00 menu is {mem, P, acc, zero, DR, tA} while the *src08* menu
			//  beside it contains `coef'.  Every "1 of 6" statement about this
			//  source is a statement about those six.
			//  ⚠ And the §123 comment above cites action00-discriminator.md item I,
			//  which adjudication-round6.md:605 had already VOIDED -- at the forced
			//  delay polarity EVERY src00 reading scores 0, so nothing is excluded.
			//  THE CORPUS TWIN (§145, MEASURED here):
			//    092.A.xx.200  SRC 0x08  n=29, successor 082.2.00.1C0 in 29/29
			//    192.A.xx.000  SRC 0x00  n=29, successor 082.2.00.1C0 in 29/29
			//    base rate for that successor after any class-A word: 64/822 = 7.79%
			//  The two differ in exactly two bits (hi12 bit 8, SRC bit 3), sit in the
			//  same slot of the same idiom, and 082.2.00.1C0 is the ANCHORED LFO
			//  phase-read.  CHORUS's anchored word consumes C-RAM[0x00] = 114 = its
			//  known LFO increment (0.599 Hz); its four twins consume C-RAM[0x02]/
			//  [0x04]/[0x0D]/[0x0F], and 0x02/0x04 hold 240 = 1.262 Hz -- a second
			//  chorus rate.  Under `coef' the twins are LFO phase accumulators
			//  running at their own designed rates; under the shipped mem[ptr] they
			//  get whatever D-RAM holds, MEASURED as the rail at two of the four.
			//  ★ §146 (mask bit 58): `coef' ONLY ON A COEFFICIENT-CONSUMING WORD.
			//  Bit 57 applied `coef' to all 1610 SRC-0x00 words and RAILED unit 1
			//  (98.9 % at full scale, DC leak 99.94 %) -- while being bit-exact on
			//  the 29 twins.  The split explains both: only 111 of the 1610 are
			//  class A.  A class-2 word does NOT consume a cursor coefficient, so
			//  reading C-RAM[cursor] there returns whatever the last class-A word
			//  happened to leave -- garbage, and exactly the shape of a corpus-wide
			//  rail.  The twins are class A; the 1262-word class-2 majority is not.
			//  ★ §148 (mask bit 59): `coef' only where f98 == 1 AND the word consumes
			//  a coefficient.  §146 localised the railing to four words -- kernel
			//  iw14/iw36 (400.A.00.000, f98=0) and ROOM REVERB iw315/iw326
			//  (282.A.00.000, f98=2) -- and NONE of them is f98=1.
			//  ⚠ Gating on f98 BECAUSE it separates the twins from the railers would
			//  be fitting the gate to the outcome.  What licenses it is §147, an
			//  INDEPENDENT test on the other f98=1 form: the twelve 182.A.00.000
			//  words land on the 2/pi envelope idiom's one-pole time constants
			//  (0.004812 = 4.712 ms, 0.001927 = 11.764 ms), consumed in exactly the
			//  order the ROM's own upload script at 0x84CD writes them, and named
			//  ATTACK SENS.(s) / RELEASE SENS.(s) in the UI parameter list.
			//  So f98=1 collects {LFO phase accumulator, envelope smoother} -- two
			//  coefficient-consuming filter contexts.
			if (m_speculative
					&& ((m_specmask & (1ull << 59))
						? (upd6383_disassembler::coeff_consumer(word)
							&& (((upd6383_disassembler::hi12(word) >> 8) & 3) == 1))
					: (m_specmask & (1ull << 58))
						? upd6383_disassembler::coeff_consumer(word)
						: (m_specmask & (1ull << 57)) != 0))
			{
				L = s32(util::sext(m_cram.read_dword(m_cursor) & 0xffffff, 24));
				e1route = E1_CRAM; e1idx = u16(m_cursor);                   // §221 §E1
				m_src00_coef_n++;
				break;
			}
			L = s32(util::sext(m_dram.read_dword(m_dp) & 0xffffff, 24));
			e1route = E1_DRAM_PTR; e1idx = m_dp;                            // §221 §E1
			break;
		//  ⛔ SRC 0x11 WAS HERE, read as mem[ptr] -- "1 of 7 enumerated, no
		//  independent support".  §27 REPLACES that guess: 0x11 = ACCB, which has
		//  support (adjacent to 0x10 = ACCA; the block diagram gives this ALU two
		//  accumulators; and it predicts w73/w77/w78's roles correctly).  The old
		//  reading was also demonstrably inert -- the epilogue runs at dp = 0x46
		//  whose cell is 0, which is exactly why w64/w71 multiplied by zero.
		//  ★★★ SRC 0x02/0x03/0x04 -- register row 22, 2026-07-28.  These occur ONLY
		//  on the five class-1 mode-1 ACT-0x07 STORE words of the epilogue, whose
		//  destinations (0x8A, 0x0F, 0x8C, 0x85, 0x06) are now confirmed by cadence.
		//  Their SOURCE was unread, so those stores wrote zero.
		//  ⛔ PURE ENUMERATION: mem[ptr] is chosen because it is what every other
		//  unanchored source in this device resolves to and because the epilogue's
		//  pointer walks the cells the bodies deposit in.  No independent support.
		case 0x04:
			L = s32(util::sext(m_ta, 24));     // ★ row 29: the pair test
			e1route = E1_TA;                                                // §221 §E1
			break;
		case 0x02:
			//  ★★★ §100 SPECULATIVE (mask bit 24): SRC 0x02 = reg[addr8], the
			//  MODE-1 ADDRESSED REGISTER.  This is item J's own stated escape --
			//  "SRC 0x02, undecoded, might carry the level itself and make the
			//  write an identity" -- and it is the ONLY reading under which w72
			//  (`000.1.06.087') can execute without destroying the user's effect
			//  depth, which §99 measured it doing.
			//
			//  ⚠ 0x02 IS SPLIT FROM 0x03 HERE.  They were one case, and that merge
			//  is the same shape of error as the two memories: item J's escape
			//  needs w72 (SRC 0x02) to be an IDENTITY, while output-stage-decode.md
			//  §7.2's reading (R-2) needs w70 (SRC 0x03) to SUPPLY reg 0x85 with
			//  something new -- §98 measured that nothing else in the machine feeds
			//  unit 1 at all.  Both cannot hold of one route.  They are different
			//  codes, so nothing forces them to share one.
			//
			//  0x03 deliberately keeps the old mem[ptr] guess: this change tests
			//  ONE code, and the whole-chain-test lesson (Part 103) is that a
			//  reading must be allowed to show its own effect.
			if (m_speculative && (m_specmask & 0x1000000)
					&& !upd6383_disassembler::c_format(word)
					&& upd6383_disassembler::class4(word) == 1)
			{
				const u8 r = u8(upd6383_disassembler::addr8(word)
						| (m_cur_unit1 ? 0x80 : 0x00));
				L = s32(util::sext(((m_specmask & 0x800000) ? m_rf[r]
						: m_dram.read_dword(r)) & 0xffffff, 24));
				e1route = (m_specmask & 0x800000) ? E1_RF_IDX : E1_DRAM_IDX;  // §221 §E1
				e1idx = r;
				m_src02_n++;
				break;
			}
			L = s32(util::sext(m_dram.read_dword(m_dp) & 0xffffff, 24));
			e1route = E1_DRAM_PTR; e1idx = m_dp;                            // §221 §E1
			break;
		case 0x03:
			//  ★★★ §101 SPECULATIVE (mask bit 25): SRC 0x03 = THE ACCUMULATOR.
			//  SRC 0x03's ONLY corpus site is w70 (`2A6.1.85.0C7'), so like 0x02 it
			//  cannot be decoded by counting -- n = 1.  What CAN be tested is the
			//  consequence: output-stage-decode.md §7.2's reading (R-2) needs w70 to
			//  SUPPLY reg 0x85, and §98 measured that nothing in the machine feeds
			//  unit 1 at all.  For R-2 to be possible the value w70 stores must be
			//  input-dependent, and this is the only candidate operand at that point
			//  in the frame that could be: it is the epilogue, one word before the
			//  unit-1 entry vector, and the accumulator there holds unit 0's result.
			//
			//  ★ THE TEST IS TWO-SIDED AND CURRENTLY FAILING: §86 reports which
			//  written cells have DIFFERENT quiet and loud ranges, and today only
			//  0x06 and 0x07 do.  If the accumulator at w70 carries audio, cell 0x85
			//  joins them.  If it does not, R-2 dies here regardless of which memory
			//  receives the store -- which is worth knowing before resolving the
			//  §97/§98 routing conflict.
			//  ★★★ §222 §E-D85: the crossbar's LOAD half.  Takes precedence over mask
			//  bit 25's accumulator reading -- which PREDICT_D0_producer.md §4.4 already
			//  refuted WITHOUT a run: ACCA at w70 is the frame-invariant constant
			//  2 603 010 048 in all four arms, so an accumulator source can only ever
			//  publish a DC into unit 1's input cell.  Only a BUS latch can carry
			//  anything live.
			if (xb_latch())
			{
				L = s32(util::sext(m_xb, 24));
				e1route = E1_DEF;                    // a private latch, not an array
				m_xb_ld_n++;
				break;
			}
			if (m_speculative && (m_specmask & 0x2000000))
			{
				L = acc_to_datum((m_specmask & 0x4000) && m_cur_unit1
						? m_accb : m_acc);
				e1route = ((m_specmask & 0x4000) && m_cur_unit1)             // §221 §E1
						? E1_ACCB : E1_ACCA;
				break;
			}
			L = s32(util::sext(m_dram.read_dword(m_dp) & 0xffffff, 24));
			e1route = E1_DRAM_PTR; e1idx = m_dp;                            // §221 §E1
			break;
		case upd6383_disassembler::LO_SRC_MEM:
		case upd6383_disassembler::LO_SRC_ACC:
		case upd6383_disassembler::LO_SRC_ACCB:   // ★ §27
		case upd6383_disassembler::LO_SRC_TA:
		case upd6383_disassembler::LO_SRC_TB:
			break;                           // anchored -- handled by the switch below
		default:
			//  EVERY remaining source has no reading and silently returns 0.
			//  Counted so the next pass can see which ones actually matter.
			m_src_unread[src & 0x1f]++;
			e1route = E1_DEF;                                               // §221 §E1
			break;
		}
	}
	switch (src)
	{
	case upd6383_disassembler::LO_SRC_ACC:
		//  ★★★ §66: "the accumulator" means THIS UNIT'S accumulator.
		//  Under mask bit 14 the accumulator is selected by m_cur_unit1, but this
		//  source always read m_acc -- so during body 1 (unit 1, accumulating into
		//  ACCB) any word reading SRC = ACC got ACCA, which is 0.
		//  MEASURED: body 1's ladder ran correctly to iw305 (ACCB = 269 380 247 879,
		//  oscillating like a comb) and died at iw306 = `000.2.49.407' -- SRC = ACC,
		//  f31 = 0 => LOAD acc <- P.  It read ACCA = 0, formed P = 0, and loaded that
		//  into ACCB.  One reader of the wrong register killed the whole unit.
		L = acc_to_datum((m_speculative && (m_specmask & 0x4000) && m_cur_unit1)
				? m_accb : m_acc);
		e1route = (m_speculative && (m_specmask & 0x4000) && m_cur_unit1)   // §221 §E1
				? E1_ACCB : E1_ACCA;
		break;
	//  ★★★ §27 SPECULATIVE: SRC 0x11 = ACCB.  w64 and w71 -- the two
	//  coefficient-fetching LOAD-acc words of the output stage -- source this code,
	//  and with it unmodelled they multiplied the output level by a silent zero.
	case upd6383_disassembler::LO_SRC_ACCB:
		//  ★★★ §113 SPECULATIVE (mask bit 18): SRC 0x11 = mem[ptr], NOT ACCB.
		//  lfo-ramp.md item L enumerates mem[ptr] as the COMPLIANT reading of the
		//  `447' word iw92 (0000209447), and §8.4 FORCES the negative: the 447 word
		//  must not deposit a foreign value in the phase cell -- "a 447 that copied
		//  [acc] would overwrite the phase with unity every frame", which is exactly
		//  what our ACCB reading makes it do (measured: the phase pins at 0x7FFFFF
		//  once iw32's clobber is removed).  Under mem[ptr] the word stores
		//  mem[0x07] back to mem[0x07] -- an IDENTITY -- and the phase survives.
		//  Same shape as §100's SRC 0x02 = reg[addr8] identity at w72.
		//  ⚠ This CONTRADICTS §27's ACCB reading, which is live.  Gated, and the
		//  criterion is two-sided: the phase either ramps by 114 per frame or it
		//  does not.
		//  ★★★ §168 2026-07-30: TESTED AT LAST, and the two-sided criterion is
		//  decided on arm 2.  Gate FIRED 9 279 912 times -- so "nothing moved" is a
		//  decision, not an absence -- and `m_tb' at the class-6 site is UNCHANGED
		//  (0..5872025, chg 1).  Swapping SRC 0x11 from ACCB to mem[ptr] moves WHICH
		//  constant arrives, not whether it is constant.
		//  ⇒ The real defect is ADDRESSING: §162 measures m_dp = 12 (0x0C) at the
		//  class-6 word, and §164's exhaustive per-frame census lists every D-RAM
		//  cell 0x00..0x1F that moves -- 01 02 04 06 07 0E and nothing else.  Cell
		//  0x0C is not among them.  `C63' reads cell 0x0C; the LFO phase is in cell
		//  0x07.  It is reading the wrong cell.
		//  ⚠ NOT inert and still NOT shipped: one cell differs from the control
		//  (`06: chg 1100 -> 2'), everything else bit-identical.  Too small to
		//  overturn §27's live ACCB reading.  This bit is now TESTED-and-recorded,
		//  no longer "off because nobody ran it".
		if (m_speculative && (m_specmask & 0x40000u))
		{
			L = s32(util::sext(m_dram.read_dword(m_dp) & 0xffffff, 24));
			e1route = E1_DRAM_PTR; e1idx = m_dp;                            // §221 §E1
			m_src11_mem_n++;
			break;
		}
		L = !m_speculative ? 0
			: (m_specmask & 0x4000) ? acc_to_datum(m_cur_unit1 ? m_accb : m_acc)
			: (m_specmask & 2) ? acc_to_datum(m_accb)
			: s32(util::sext(m_dram.read_dword(m_dp) & 0xffffff, 24));   // old guess
		e1route = !m_speculative ? E1_DEF                                   // §221 §E1
			: (m_specmask & 0x4000) ? (m_cur_unit1 ? E1_ACCB : E1_ACCA)
			: (m_specmask & 2) ? E1_ACCB : E1_DRAM_PTR;
		if (e1route == E1_DRAM_PTR) e1idx = m_dp;
		break;
	case upd6383_disassembler::LO_SRC_TA:
		L = s32(util::sext(m_ta, 24));
		e1route = E1_TA;                                                    // §221 §E1
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
		//
		// ★ A SECOND BLOCK NOW HAS AN OPINION, AND IT DISAGREES -- recorded
		// 2026-07-27, unresolved, and deliberately NOT acted on.  The reverb
		// core's comb search enumerates this shift as `tbsh', and in every
		// STRICT row it has ever run it FORCES tbsh = 0: 112/112 in the
		// PUBLISHED row, 3206/3206 with the blocking read, 2310/2310
		// sequential.  ⛔ 2026-07-27: the two BLOCKING-READ rows (3206, 2310)
		// are VOID -- the blocking read was forced under the delay-DRAM
		// polarity round 5 reversed (adjudication-round6.md sect. 3).  The
		// 112/112 PUBLISHED row survives, and the tension it records is
		// unchanged in kind; only its width shrinks.
		// Stated at its real strength rather than its best: in
		// the JOINT row it is only a 92.1 % majority (32050 of 34815), so
		// this is a tension INSIDE a topology hypothesis, not a contradiction
		// between two determinations.  Every one of those numbers was
		// produced before this comment and NONE had ever been PRINTED, which
		// is why nobody noticed; the marginal is printed now
		// (dsp/analysis/blocking-read.md item H).
		//
		// The reverb's motif writes tempB at slot 0 and reads it at slot 3,
		// so a shift on the CAPTURE and a shift on the BUS are equally
		// excluded there: the disagreement is about the shift existing AT ALL
		// on a tempB->operand path, not about where it sits.  Candidates,
		// ENUMERATED and none chosen:
		//   (a) the shift is conditional on something neither search varies
		//       -- the class, or the capture code (the reverb captures with
		//       ACTION 0x14 on an ESCAPE word, the biquad on a mode-2 word);
		//   (b) the reverb's ROM gains are not the comb's loop gains, so
		//       tbsh = 1 is rejected by a mislabelled reference, not by the
		//       machine;
		//   (c) the biquad's factor of two lives somewhere else entirely and
		//       this is the wrong home for it.
		// IT STAYS AS IT IS, because the biquad's 77 dB is a MEASURED
		// reconstruction while the reverb's tbsh is a constraint inside a
		// hypothesis.
		L = s32(util::sext(m_tb, 24)) >> 1;
		e1route = E1_TB;                                                    // §221 §E1
		break;
	case upd6383_disassembler::LO_SRC_MEM:
	{
		//  ★★★ THE MODE-1 READ IS THE MIRROR OF THE MODE-1 STORE -- row 28.
		//  Row 27 established (from isa-adjudication.md behavioural note 1) that a
		//  mode-1 bit-4 store targets mem[addr8], not mem[ptr].  A register-file word
		//  names its register in addr8; there is no reason the SAME word class would
		//  address one way to write and another to read.
		//
		//  MEASURED motivation: the epilogue's iw65 `200.1.8F.1C1' is mode 1 with
		//  addr8 = 0x8F -- the register body 1 now fills 1 559 999 frames out of
		//  1 560 839 -- yet it was reading mem[m_dp] and getting nothing.  This is
		//  the link between 0x8F and the presentations that read 0x8C/0x8D.
		//
		//  ⛔ GUESSED: symmetry.  The store side is documented; the read side is not,
		//  and no note in this project states it.  It is applied because the two
		//  halves of one addressing mode disagreeing would be the odd claim, not
		//  because anything proves it.
		const u8 rdmode = upd6383_disassembler::c_format(word)
				? 2 : u8(upd6383_disassembler::class4(word) & 7);
		const bool regfile = (rdmode == 1) && !(hi & 0x800);
		const u8 rdsrc = regfile
				? u8(upd6383_disassembler::addr8(word) | (m_cur_unit1 ? 0x80 : 0x00))
				: m_dp;
		// ★ §97: this site ALREADY separated the two addressing modes -- the
		//  local is named `regfile' -- and then read both from m_dram.  That is
		//  the alias, in one line.  Bit 23 sends the mode-1 half to m_rf.
		//  ★★★ §222 §E-D85: the crossbar's READ half.  `ACT 0x03' is corpus-unique
		//  (w63), so this moves ONE word into pointer space -- where cell 0x05 is the
		//  LIVE unit-0 pickup that iw111 fills, and where m_rf[0x05] (which w63 reads
		//  today) is 0 forever, its only writer being the host, once, with zero.
		const bool xb_rd = xb_route() && regfile && act == 0x03;
		if (xb_rd) m_xb_rd_dram_n++;
		L = (regfile && m_speculative && (m_specmask & 0x800000) && !xb_rd)
				? s32(util::sext(m_rf[rdsrc] & 0xffffff, 24))
				: s32(util::sext(m_dram.read_dword(rdsrc) & 0xffffff, 24));
		//  ★ §221 §E1: `regfile' names the ADDRESSING MODE, bit 23 names the ARRAY.
		//  Both are recorded, because the epilogue's `w63'/`w65' resolve to mode-1
		//  indices (0x05, 0x8F) that COLLIDE with live mode-2 cells -- §5.1's trap.
		e1route = (regfile && m_speculative && (m_specmask & 0x800000) && !xb_rd)
				? E1_RF_IDX : (regfile ? E1_DRAM_IDX : E1_DRAM_PTR);
		e1idx = rdsrc;
		pwatch(rdsrc, false, regfile);                                 // §98
		break;
	}
	default:
		if (e1route == E1_NONE) e1route = E1_DEF;                           // §221 §E1
		// UNREACHABLE BY CONSTRUCTION -- alu_decoded() gates the four codes
		// above.  Spelled out rather than folded into the mem[ptr] case: if the
		// predicate is ever widened, an unanchored source must NOT quietly
		// become a memory read.  Leaving L at 0 is the failure that shows.
		break;
	}

	// ---- hi12 bit 4: store the accumulator to mem[ptr] AND CLEAR IT --------
	// The store is MEASURED and its "before the word's own ALU step" timing is
	// FORCED (R1 F2, and independently re-forced here: of 2160 enumerated
	// accumulator models only those that store BEFORE the ALU are bit-identical
	// to this one on the PARAMETRIC EQ section -- "after" and "store early,
	// clear late" both change it).  The CLEAR is forced by the biquad: the two
	// words of the section that carry bit 4 are exactly the two at which the
	// accumulator must restart from zero, and without it the section is 57 dB
	// wrong.
	//
	// THE TARGET IS mem[ptr] ONLY BECAUSE THE MODE SAYS SO.  R2 falsified the
	// class-independent reading (analysis/r2-output.md sect. 1, 4.4): bit 4's
	// destination is MODE-DEPENDENT and mem[ptr] is the MODE-2 target, so a
	// universal mem[ptr] manufactures four dead stores in the output stage.
	// alu_decoded() now refuses any bit-4 word outside mode 2, which is what
	// makes the write below sound.
	//
	// ★ AND IT IS NOT UNCONDITIONAL.  hi12 bit 7 SUPPRESSES it -- see
	// upd6383d.h HI_B7 for the falsification (the LFO cannot run at all if these
	// words store, 0 of 181440 machines) and for why the three surviving gates
	// let only two of the four cases through.  alu_decoded() guard 7 keeps the
	// disputed ones trapping, so the test below is the AGREED part and nothing
	// more.
	//
	// ★ 2026-07-27: guard 7 is now STRICTER, and st_suppressed() is therefore
	// unreachable from here.  Every bit-4 word carrying bit 7 with
	// hi12[3:1] == 1 traps (the ACTION-0x00 escape was withdrawn -- a clear
	// deferred past the ALU is visible at exactly those words), and the only
	// bit-7 case alu_decoded() still admits is hi12[3:1] == 2, where the store
	// FIRES.  The call is kept because st_suppressed() is also applied on the
	// input-stage path below and the two must never disagree; it is now a
	// belt-and-braces identity here rather than a live gate.
	// dsp/analysis/adjudication-round4.md sect. 6.
	if ((hi & upd6383_disassembler::HI_ST)
			&& !st_suppressed_live(word))               // ★ §109 bit 29
	{
		//  ★★★ THE BIT-4 STORE TARGET IS MODE-DEPENDENT -- register row 27.
		//  This site wrote mem[m_dp] UNCONDITIONALLY, which contradicts
		//  isa-adjudication.md behavioural note 1: "hi12 bit 4's target is
		//  mode-dependent -- mem[ptr] ONLY IN MODE 2.  Eight kernel words
		//  mis-execute otherwise."  do_store() implements the rule; this path did
		//  not.
		//
		//  MEASURED consequence: body 1's TERMINATOR `612.1.0F.000' is MODE 1, so
		//  it should deposit into register 0x0F -- instead it wrote mem[0x46], which
		//  is exactly the 504 the epilogue was seen holding at the pointer while the
		//  registers it actually reads stayed empty.
		//
		//  ★ AND THE UNIT BIT.  addr8 bit 7 selects the unit -- MEASURED in
		//  output-stage-decode.md item I ("0x00 -> unit 0, 0x9F -> unit 1"), named in
		//  this device's own register annotations ([06] unit 0 / [86] unit 1), and
		//  already applied to the pointer as DRAM_UNIT_BASE = 0x05 | unit<<7.  The
		//  microcode writes addr8 UNIT-RELATIVE and the hardware supplies the unit,
		//  so body 1's 0x0F is register 0x8F -- which is precisely what the epilogue
		//  reads at iw65 `200.1.8F.1C1'.
		//  ⛔ GUESSED: that the unit bit applies to REGISTER destinations and not only
		//  to the D-RAM pointer.  The parallel is strong and the two addresses meet,
		//  but it is a parallel.
		const u8 stmode = upd6383_disassembler::c_format(word)
				? 2 : u8(upd6383_disassembler::class4(word) & 7);
		u8 stdest = m_dp;
		if (stmode == 1)
			stdest = u8(upd6383_disassembler::addr8(word) | (m_cur_unit1 ? 0x80 : 0x00));
		//  ★★★ §33 2026-07-28: NEVER let the accumulator store land on the two
		//  INPUT-LATCH cells.  MEASURED: the header read at w4 was taking 0x2CCCCC
		//  (the previous frame's body datum) out of cell 0x47 while the deposit had
		//  just written 0x170800 there -- 1 565 758 mismatches against 31 682 matches
		//  -- so the chip processed its own stale output instead of its input, every
		//  frame.  The addresses were never wrong: in_base=45, dp=cell=in_addr=47.
		//
		//  THIS IS THE FAILURE THIS DEVICE'S OWN COMMENT PREDICTED, verbatim:
		//  "hi12 bit 4 (the accumulator store) ... needs a CORRECT ACCUMULATOR, and
		//  the accumulator of a frame full of undecoded words is not the chip's -- so
		//  performing it would write invented data into real cells. ... EXECUTE WHAT
		//  ADDRESSES, NEVER WHAT COMPUTES."  The speculative gate generalised the
		//  store and broke exactly that rule.
		//
		//  ⛔ A GUARD, NOT A DECODE.  K6's feedback store is FORCED at X+1; the latch
		//  cells are X+2 and X+5.  A store reaching them means our ADDRESSING is
		//  wrong, and that is still to be found -- this stops the corruption from
		//  masking every downstream measurement in the meantime.
		//  ★ §34: the ad-hoc latch guard is GONE -- st_suppressed()'s corrected
		//  condition removes these stores at the decode, which is where they belong.
		//  The counters stay as a REGRESSION ALARM: if anything ever stores onto the
		//  latch cells again, it is reported rather than silently corrupting the input.
		//  ★★★ §35 2026-07-28: DO NOT REPEAT THE STORE ON THE K6 PATH.
		//  The twelve input-stage words are executed as
		//      exec_addressing_only(word, true);   // pointer, STORE, cursor, latch
		//      exec_alu_k6(word);                  // "the ALU, without re-walking"
		//  and exec_addressing_only() ALREADY performs the bit-4 store, at `cell'
		//  -- the pointer BEFORE its post-increment, which is correct.  exec_alu()
		//  then performed it a SECOND time at `stdest = m_dp', i.e. at the pointer
		//  the first call had already advanced: one cell late.
		//  MEASURED, and it explains the input corruption exactly.  The documented
		//  walk (K6_INPUT_STAGE) has w3 store at X+3 and w7 at X+4, and our pointer
		//  trace matches that table at ALL TWELVE words -- yet the stores landed on
		//  X+2 and X+5, one step ahead, which are precisely the two input latches.
		//  They are the latches *because* the walk is built so the post-increment
		//  parks the pointer on the cell the NEXT word reads.
		//  ★★★ §36 2026-07-28: THE GUARD NO LONGER SUPPRESSES -- it only REPORTS.
		//  With §35's double store fixed, the whole residue is 609 stores in 1.6 M
		//  frames, and a census by word shows NONE of them is clobbering an input:
		//      01218D05B iw61 mode 1 dest 8D x203
		//      01190F446 iw71 mode 1 dest 0F x201
		//      01190E445 iw64 mode 1 dest 0E x203
		//      0902FB40E iw320 mode 2 dest 53 x2
		//  Every destination is a NAMED REGISTER (mode-1 stores aim at addr8), not a
		//  latch cell.  They matched only because `m_in_addr' had DRIFTED on top of
		//  them: X = m_dp at frame start, steady state 0x45 on 98.31 % of frames, and
		//  in the other 1.69 % the input window lands wherever the pointer failed to
		//  return to -- sometimes on 0x8D or 0x0E.
		//  So the residue is a SYMPTOM OF FRAME-CLOSURE FAILURE (936 959 of 962 880
		//  frames close), not a store defect, and suppressing it corrupted 607
		//  legitimate register writes to fake-fix 0.04 % of frames.  Letting the
		//  stores happen is the faithful choice; the drift is the real defect.
		if (m_in_k6)
			; // already stored, correctly, by exec_addressing_only()
		else
		{
			if (m_speculative && (stdest == m_in_addr[0] || stdest == m_in_addr[1]))
			{   // ★ observe only -- the regression alarm for §35
				m_latchguard_n++;
				m_latchguard_word = m_cur_word;
				m_latchguard_slot[m_cur_iw < 384 ? m_cur_iw : 383]++;
				u32 q = 0;
				for (; q < m_lg_n; q++) if (m_lg_word[q] == m_cur_word) break;
				if (q == m_lg_n && m_lg_n < 8)
				{
					m_lg_word[q] = m_cur_word; m_lg_dest[q] = stdest;
					m_lg_mode[q] = stmode;     m_lg_iw[q]   = m_cur_iw;
					m_lg_n++;
				}
				if (q < 8) m_lg_cnt[q]++;
			}
			//  ★★★ §68: the bit-4 store must READ and CLEAR the CURRENT UNIT'S
			//  accumulator, not ACCA unconditionally.  Same defect as §66, in the
			//  store path instead of the source path.
			//  MEASURED: kernel slots 50..59 leave ACCA = 769 657 969 049 (healthy);
			//  it is 0 by iw 202, one slot into body 1.  Under mask bit 14 body 1
			//  accumulates into ACCB, so every bit-4 store it executes was reading
			//  ACCA for its datum and then wiping it -- destroying unit 0's result,
			//  which has to survive body 1 to reach w73 and DO1.
			u64 &sacc = (m_speculative && (m_specmask & 0x4000) && m_cur_unit1)
					? m_accb : m_acc;
			//  ★★★ §220 DIAGNOSTIC (env UPD6383_NOZ05, DEFAULT OFF) -- the OVERWRITE
			//  half of §219 §8's pre-registered pair, and the twin of mask bit 26's
			//  DEPOSIT half.  It is NOT a fix and must not be promoted on the strength
			//  of a number moving.
			//
			//  §219 §3 located the unit-0 send: D-RAM cell 0x05 is body 0's input
			//  pickup, `iw9'/`iw11' DEPOSIT the audio into it, and then `iw35' and
			//  `iw45' -- both site-2 bit-4 stores, both in kernel A -- OVERWRITE it
			//  with acc_to_datum(2^38) = 4 194 304 and with 0, before the CALL at
			//  `iw49'.  §104's residency prints the collapse slot by slot.
			//
			//  This gate removes exactly those stores, to ask ONE question that the
			//  mirror cannot: is cell 0x05 body 0's pickup at all?  Two-sided, and
			//  both sides are worth the same:
			//    * if body 0's §104 columns become INPUT-DEPENDENT at `iw84', the
			//      pickup model is right and the defect is the store TARGET of
			//      `iw35'/`iw45' (or our HI_ST decode firing on words that do not
			//      store);
			//    * if `iw84' still reads 0 with the fired count non-zero, cell 0x05
			//      is NOT the pickup and `base = 0x05 | unit<<7' is wrong.
			//  ⚠⚠ IT CANNOT PRODUCE AUDIO, BY §216: the output stage is a null even
			//  when body 0 runs on live audio.  Grade it on §104, never on §70/§211.
			//  ⚠ `iw11's DEPOSIT is a site-3 ACT-0x07 store and is NOT touched here,
			//  so the audio still reaches 0x05.  `iw9' IS a site-2 store to 0x05 and
			//  IS suppressed -- it writes the constant 5 084 004 that `iw11' overwrites
			//  two slots later, so removing it costs nothing.  The per-iw breakdown is
			//  reported so "which words fired" is measured, not assumed.
			//  ★★★ §223: MODE 2 SUPPRESSES ONLY `iw35' AND `iw45'.
			//  Mode 1's own per-iw breakdown shows it deleting EIGHT words, and
			//  `iw9' -- 1 176 015 of them -- is not one of the two §219 §3 named.
			//  §222 argued `iw9' "costs nothing" because `iw11' overwrites the cell
			//  two slots later; that is true of the CELL and says nothing about the
			//  accumulator path that decides what `iw11' has to store.  Mode 2 is
			//  the narrower rig that tests exactly that difference, and mode 1 is
			//  left BIT-IDENTICAL so it stays the regression control.
			const bool noz05_hit = (m_noz05 == 1)
					|| (m_noz05 == 2 && (m_cur_iw == 35 || m_cur_iw == 45));
			if (noz05_hit && stdest == 0x05 && pw_region(m_cur_iw) == PW_KERNEL_A)
			{
				m_noz05_n++;
				u32 q = 0;
				for (; q < m_noz05_slots; q++) if (m_noz05_iw[q] == m_cur_iw) break;
				if (q == m_noz05_slots && m_noz05_slots < 8)
				{ m_noz05_iw[q] = m_cur_iw; m_noz05_slots++; }
				if (q < 8) m_noz05_cnt[q]++;
			}
			else
			{
			store_mode(stmode, u8(stdest), u32(acc_to_datum(sacc)), 2);   // §99, site 2
			kwatch(stdest, s32(u32(acc_to_datum(sacc)) & 0xffffff));
			watch_store(stdest, s32(acc_to_datum(sacc)) & 0xffffff, 2);
			store_probe(u8(stdest), s32(acc_to_datum(sacc)) & 0xffffff, 2);   // §109
			}
		}
		{ m_dwr[stdest]++; if (m_dram.read_dword(stdest) & 0xffffff) m_dwr_nz[stdest]++; }
		//  ★★★ §69 SPECULATIVE (mask bit 16 SUPPRESSES the clear).
		//  "store-and-clear" is one point in a set the round-4 adjudication leaves
		//  open -- item 2 there lists `no memory access', `store -> elsewhere' and
		//  `LOAD' as equally surviving, and says this code "implements 'no store, no
		//  clear', which is one point inside that set".
		//  MEASURED, and now specific evidence against it: ACCA survives body 1
		//  intact (769 657 969 049 at iw 332) and is 0 by iw 73.  The epilogue's
		//  FIRST word w60 = `092.1.8D.15B' carries HI_ST, so it stores AND CLEARS --
		//  destroying unit 0's result at the top of the very stage whose job is to
		//  present it.  A store that annihilates the value the next word must read
		//  is not a plausible chip behaviour.
		if (!(m_speculative && (m_specmask & 0x10000)))
		{
			//  ★ §221 §E1: a CLEAR is a write.  It updates the last-writer column
			//  and deliberately NOT the last-NON-ZERO-writer column, which is what
			//  makes the second column able to name a producer at all.
			if (m_speculative && (m_specmask & 0x4000) && m_cur_unit1)
			{ m_accb = 0; pv_wr_acc(true, 0); }
			else { m_acc = 0; pv_wr_acc(false, 0); }
		}
	}

	// ---- ★ THE ACCUMULATOR: ONE ADDER, TWO SELECTORS ------------------------
	// This REPLACES a two-step reading ("do the hi12[3:1] operation, then do the
	// ACTION") and it is the adjudication of a real contradiction between two
	// concurrent passes -- dsp/analysis/acc-adder.md.  Both of them are right
	// about the ANSWER and wrong about the MECHANISM:
	//
	//      LFO   082.2.00.1C0   hi12[3:1] = 1, ACTION 0x00, bus = phase
	//      SD    000.2.48.000   hi12[3:1] = 0, ACTION 0x00, bus = x
	//
	// both have to produce `bus + P'.  No ORDER does that -- act-first gives
	// `P' at hi12[3:1] == 0 and act-last gives `acc + P + bus' at 1 -- but a
	// single adder whose accumulator-feedback input is OVERRIDDEN by the bus
	// gives it at both.  So:
	//
	//      acc <- SRC_TERM + P_TERM
	//         SRC_TERM = bus                     if ACTION == 0x00
	//                  = 0                       if hi12[3:1] == 0  (acc <- P)
	//                  = acc                     otherwise
	//         P_TERM   = 0                       if hi12[3:1] == 2  (no P)
	//                  = P                       otherwise
	//
	// ★ ON EVERY WORD WHOSE ACTION IS NOT 0x00 THIS IS THE OLD CODE EXACTLY --
	// PROVEN BY CONSTRUCTION, and it is why the PARAMETRIC EQ reconstruction is
	// untouched (measured: bit-identical impulse response) and why the published
	// build's audio cannot move.  The product register is still NOT consumed:
	// an MPLY output latch holds until the next multiply overwrites it.
	//
	// A CONSEQUENCE, stated because it is a testable prediction and not a
	// convenience: on an ACTION-0x00 word hi12[3:1] == 0 and == 1 become
	// INDISTINGUISHABLE (both give `bus + P'), and the corpus does emit both.
	m_last_l = L;               // ★ §29: the bus operand actually selected
	//  ★★★ §221 `§E1' -- THE OPERAND-PROVENANCE CENSUS.  Read-only, settled frames
	//  only (rule 16: a census over a 1.44 M-frame run that includes boot measures
	//  boot).  It fires at the ONE point where `L' is final, so it can never
	//  disagree with what the ALU is about to use.
	if (m_epibus && m_frames_run > 900000 && m_cur_iw < 384)
	{
		m_epibus_fired++;
		e1_record(e1route, e1idx, L);
	}
	//  ★★★ §222 `§E-D0': the PICKUP AUDIT, at the same single point where the operand
	//  bus is final -- and, decisively, BEFORE the word's own post-increment.  The
	//  pre-increment trap has now cost three sections (iw205's `0xD0', §104's `dp'
	//  column, §221's `w79'), so the pointer is recorded HERE and again at the bottom
	//  of exec_alu(), as two SEPARATE columns that can be compared.
	if (m_pickup && m_frames_run > 900000 && m_cur_iw < 384
			&& upd6383_disassembler::lo12(word) == 0x1CD)
		pk_fetch(m_dp, e1route, e1idx, L);
	{
		const u16 f31 = upd6383_disassembler::hi_f31(hi);
		//  ★★★ ACTION 0x00 ADDS the bus; it does not REPLACE the accumulator.
		//  Register row 26, found 2026-07-28 by the time-ordered trace.
		//
		//  The old expression returned the bus ALONE whenever ACTION was 0x00,
		//  regardless of hi12[3:1].  On an hi12[3:1] == 2 (HI_ACC_HOLD) word that
		//  DISCARDS the accumulator the code is simultaneously being told to hold.
		//  MEASURED consequence: the reverb's 8-word allpass motif ends in exactly
		//  such a word (`104.2.00.000', f31 = 2, SRC 0x00, ACT 0x00) and it zeroed
		//  the accumulator at EVERY stage --
		//      n=158 acc 192 414 482 432 -> 0,  n=166, n=174, n=182, n=208, n=224 ...
		//  so no ladder stage could accumulate on the one before it, and the body
		//  delivered a datum of 504 instead of ~2 936 000.
		//
		//  The three operations are: 0 = LOAD (feedback cut, acc <- P), 1 = ADD
		//  (acc <- acc + P), 2 = HOLD (accumulator kept, no product).  ACTION 0x00
		//  contributes the bus as an EXTRA term to whichever of those applies, which
		//  is exactly what this device's own DELTA table describes ("hi12[3:1] == 1,
		//  act != 00: acc += P").  ⛔ For f31 = 0 and 1 the behaviour is UNCHANGED --
		//  0 still cuts the feedback, 1 still keeps it -- so the biquad and the LFO
		//  results are untouched; only the HOLD case, which alu_decoded() admits
		//  solely on class 8, changes.
		//  ★★★ §27 SPECULATIVE: f31[2] SELECTS THE ACCUMULATOR, f31[1:0] IS THE
		//  OPERATION.  hi12[3:1] is a THREE-bit field carrying only three known
		//  codes; the observed values are {0,1,2,3,4,6,7}.  Reading bit 2 as an
		//  ACCA/ACCB select turns that into a 4x2 grid and predicts the output
		//  stage exactly: w73 (unit 0) is f31 0 SRC ACCA => ACCA <- level x ACCA,
		//  the output-level multiply r2-output.md §3.1 independently says it must
		//  be; w77 (addr8 0x86, the unit-1 LEVEL register) is f31 4 => LOAD ACCB;
		//  w78 (unit 1) is f31 6 => HOLD ACCB, presenting without disturbing it.
		//  Operation 3 remains OPEN and is given HOLD's no-product behaviour.
		//  ★★★ §43 SPECULATIVE (mask bit 7): w72 / w77 ARE LEVEL-SELECT WORDS, NOT
		//  ACCUMULATOR OPERATIONS.
		//  w72 = 000.1.06.087 and w77 = 859.0.86.822 carry addr8 0x06 / 0x86 -- the
		//  per-unit OUTPUT LEVEL cells in C-RAM (§42), one per unit, each immediately
		//  before its own presentation (w73 -> DO1, w78 -> DO2).  r2-output.md §3.1
		//  describes w77 as the word that "aims a POINTER at reg 0x86".
		//  MEASURED (§40): decoded as f31 = 0 => LOAD acc <- P, w72 ZEROES THE
		//  ACCUMULATOR one slot before w73 presents it, because P is 0 there -- so the
		//  epilogue's whole ladder is discarded at the last step.
		//  The reading: these words LOAD THE COEFFICIENT (K <- C-RAM[addr8]) for the
		//  presentation that follows, and must leave the accumulator alone.
		const bool lvlsel = m_speculative && (m_specmask & 0x80)
				&& upd6383_disassembler::class4(word) == 1
				&& (upd6383_disassembler::addr8(word) == 0x06
					|| upd6383_disassembler::addr8(word) == 0x86);
		if (lvlsel)
		{
			m_k = m_cram.read_dword(upd6383_disassembler::addr8(word)) & 0xffffff;
			return;                 // accumulator untouched
		}
		//  ★★★ §62 SPECULATIVE (mask bit 14): THE ACCUMULATOR IS SELECTED BY THE
		//  UNIT, NOT BY f31[2].
		//  MEASURED (§61): with f31[2] as the select, unit0/DO1 presents 0 non-zero of
		//  483 840 while unit1/DO2 presents 455 998 -- one accumulator takes
		//  everything and the other is dead.
		//  Structural argument: body 0 and body 1 execute the SAME instruction
		//  encodings, so an INSTRUCTION field cannot separate them -- whatever f31[2]
		//  means, it cannot be "which unit's accumulator", because both units run
		//  identical words.  The per-unit separation must come from the CALL context,
		//  which this core already tracks as m_cur_unit1 (and which the FORCED
		//  per-unit D-RAM base 0x05 | unit<<7 is already keyed on).
		//  So: ACCA for unit 0, ACCB for unit 1; f31[1:0] still gives the operation.
		//  ★★★ §64 SPECULATIVE (mask bit 15): A POINTER-LOAD WORD IS NOT AN ALU OP.
		//  `801.0.NN.821' (ldptr, C-RAM cursor) and `801.0.PP.825' (ldptr.d, the
		//  descriptor pointer) carry hi12 = 0x801, so f31 = (0x801 >> 1) & 7 = 0 --
		//  which this ALU reads as LOAD acc <- P.  With P = 0 that WIPES THE
		//  ACCUMULATOR.
		//  MEASURED: the epilogue's SECOND word is `801.0.26.825', and 0x26 is
		//  exactly the dsc range the delay port reads -- so it is unambiguously the
		//  descriptor-pointer load, and it zeroes ACCA at the top of the epilogue on
		//  every frame.  That is why w73 has presented 0 in every configuration ever
		//  measured (§43, §48, §61, §63), while ACCB -- which no epilogue word
		//  reloads -- kept whatever the kernel put in it.
		//  A word whose whole job is to aim a pointer should not also clobber the
		//  accumulator; nothing in the ISA notes says hi12 = 0x801 means "load".
		//  ★★★ §116 SPECULATIVE (mask bit 33): SELECTOR 0x27 LOADS THE PER-UNIT
		//  OVERFLOW / MODE REGISTER (m_ovc).
		//
		//  m_ovc is declared, reset, saved and debugger-exposed by this device and
		//  NEVER written or read -- the shape m_accb had before §27.  The CDJ-500
		//  block diagram gives this ALU "two shifters and an OVC".
		//
		//  The common header loads a per-unit TRIPLE immediately before each body's
		//  CALL: cursor bank (0x821, K3 FORCED), selector 0x27, descriptor pointer
		//  (0x825, PROVEN BY CONSTRUCTION).  0x27 is the ONLY member whose target is
		//  unidentified and it occurs exactly twice -- iw43 payload 0x6C for unit 0,
		//  iw51 payload 0x64 for unit 1.  See §115.
		//
		//  ⚠ The device's "K3's 0x827 candidate stays falsified (0 of 85 streams)"
		//  does NOT block this: in full it is "falsified as the D-RAM ORIGIN", and
		//  this file also says 0x825/0x827 are "INFERRED siblings whose target
		//  register is unknown".  An overflow-mode register is compatible.
		//
		//  Gated independently of mask bit 15, which is CLEAR in the default -- the
		//  0x821/0x825 early-return below would otherwise never run and this with it.
		if (m_speculative && (m_specmask & 0x8000))
		{
			const u16 lo_pl = upd6383_disassembler::lo12(word);
			if (lo_pl == 0x821 || lo_pl == 0x825)
				return;                     // pointer aimed; accumulator untouched
		}
		const bool sel   = m_speculative && (m_specmask & 1);
		const bool use_b = (m_speculative && (m_specmask & 0x4000))
				? m_cur_unit1
				: (sel && (f31 & 4));
		//  ★ §133: f31 = 4 and 5 have never been decoded; with mask bit 0 set they
		//  execute SILENTLY as `f31 & 3' (4 -> LOAD, 5 -> ADD) with no fired-count
		//  anywhere -- a standing breach of this project's own rule, and it means an
		//  enumeration must A/B against that ALIAS, not against a trap.  Give each
		//  its own reading and its own counter.  Reading 0 reproduces the alias
		//  exactly, so the default arm is unchanged.
		u16 op = sel ? u16(f31 & 3) : f31;
		if (sel && f31 == 4) { m_bx_f4_n++; if (m_bx_f4) op = bx_f31_op(m_bx_f4); }
		if (sel && f31 == 5) { m_bx_f5_n++; if (m_bx_f5) op = bx_f31_op(m_bx_f5); }
		u64 &accum = use_b ? m_accb : m_acc;
		const u64 src_term =
				(op == upd6383_disassembler::HI_ACC_LOAD ? 0 : accum)
				+ ((act == upd6383_disassembler::LO_ACT_ACC_BUS
					//  ★★★★ §82 SPECULATIVE (mask bit 21): A DELAY WORD'S ACTION PUTS
					//  ITS DATUM ON THE ACCUMULATOR.
					//  The 168 delay-write words carry ACT 0x14 / 0x1A, which this
					//  register grades "PLAIN GUESS x5 -- capture into a temporary,
					//  NO independent evidence".  Under that reading the delay datum
					//  they fetch goes into tempA and is never summed, while their
					//  f31 = 0 (hi12 0x880) LOADs acc <- P with P stale -- so ~19
					//  words per frame WIPE the accumulator and nothing injects the
					//  tap.  §81 measured the consequence: the input reaches the
					//  kernel (iw12 range differs with input) and the body starts at
					//  exactly zero.
					//  A comb is y = x + g*delayed: the delayed sample must be SUMMED.
					//  Row 26 already established the mechanism -- ACTION 0x00 ADDS
					//  the bus rather than replacing the accumulator -- so this
					//  extends a MEASURED reading to the delay consumers rather than
					//  inventing one.
					|| (m_speculative && (m_specmask & 0x200000) && m_in_dram))
					? u64(s64(L) << ACC_SHIFT) : 0);
		// HI_ACC_HOLD contributes no product.  On the class-8 post-sum word the
		// biquad DETERMINES the accumulator comes out unchanged; whether the
		// code is a no-op or a wrap/limit that does not fire on an in-range sum
		// is still OPEN (the joint solve leaves "unchanged" and "AND 2^23-1"
		// both alive), and both ARE the identity there -- which is why class 8
		// is the only place alu_decoded() lets this code through.
		//  ★ SPECULATIVE: hi12[3:1] > 2 is undecoded; the research model gives it
		//  the same "no product" behaviour as HI_ACC_HOLD (`f31hi = hold'), which
		//  is one of four enumerated options and has no independent support.
		//  ★★★★ §83 SPECULATIVE (mask bit 22): A DELAY WORD DOES NOT LOAD THE
		//  ACCUMULATOR FROM A STALE PRODUCT.
		//  The 168 delay-write words carry hi12 = 0x880, so f31 = 0 = LOAD acc <- P.
		//  But they fetch NO coefficient (class 1, bit 3 clear), and §29 established
		//  the multiply issues only on coefficient-fetching words -- so their P is
		//  whatever an earlier word left. LOADing the accumulator from a stale
		//  product is not an operation; it is an erasure.
		//  MEASURED (§81/§83): the input reaches the kernel accumulator (iw12 range
		//  differs with input, 101e9..344e9 live at iw12-16) and body-0 ENTRY at iw84
		//  is already exactly zero -- ~20 delay words per frame each doing
		//  LOAD acc <- 0 drain it before the body ever starts.
		//  Treat the LOAD as a HOLD when the word brought no fresh product.
		//  ★★★ §138 (mask bit 55): THE SAME ERASURE, AT THE OUTPUT STAGE.
		//  §83 above was REFUTED -- but only for DELAY words, because its gate is
		//  `m_in_dram'.  The per-slot accumulator profile shows the identical shape
		//  in the EPILOGUE, on ordinary words, and that one is what gates the audio:
		//      iw60..64  acc = 1 102 114 506 752      the body's result DOES arrive
		//      iw65..72  acc = 0                      erased, eight slots running
		//      iw73      w73 presents -> DO1          so DO1 presents ZERO
		//  Every one of iw65..72 is `f31 = 0' (LOAD acc <- P), and the epilogue
		//  contains exactly ONE class-A word out of 23 (iw82, the last), so no
		//  multiply issues there at all and P is stale/zero throughout.
		//  ⇒ There are (at least) TWO drains, not one: §83's trace found iw47 before
		//  body 0, and this one is AFTER both bodies.  Fixing only the kernel drain
		//  cannot make unit 0 audible, because this one erases the result again.
		//  The guard: a LOAD that brought no fresh product is an erasure, not an
		//  operation -- treat it as HOLD.  §83's reading, with `m_in_dram' dropped.
		//  ⚠ Use §83's own STATIC predicate `!coeff_fetch(word)', not the runtime
		//  `m_mul_issued': the multiply is executed later in this same function, so
		//  the flag would refer to the PREVIOUS slot and the gate would silently
		//  test something other than what it claims.
		const bool stale83 = m_speculative && (m_specmask & 0x400000) && m_in_dram
				&& !upd6383_disassembler::coeff_fetch(word);
		const bool stale138 = m_speculative && (m_specmask & (1ull << 55))
				&& op == upd6383_disassembler::HI_ACC_LOAD
				&& !upd6383_disassembler::coeff_fetch(word);
		if (stale138)
			m_stale_load_n++;
		const bool stale_p = stale83 || stale138;
		const u64 p_term =
				(op == upd6383_disassembler::HI_ACC_HOLD
					|| (m_speculative && op > upd6383_disassembler::HI_ACC_HOLD)) ? 0 : m_p;
		if (stale_p) accum = (accum + ((act == upd6383_disassembler::LO_ACT_ACC_BUS
					|| (m_specmask & 0x200000)) ? u64(s64(L) << ACC_SHIFT) : 0))
				& 0xfffffffffffULL;
		else
		accum = (src_term + p_term) & 0xfffffffffffULL;
		pv_wr_acc(use_b, accum);                              // ★ §221 §E1
	}

	// ---- the lo12[4:0] side effect ------------------------------------------
	//  ★ SPECULATIVE: five further ACTION codes (0x01, 0x08, 0x0C, 0x11, 0x16)
	//  and the three long-open ones (0x0D, 0x0E, 0x1A) are given the SAME
	//  reading -- capture into a temporary.  There is NO independent evidence
	//  for any of them; sect. 5.3/6 show the LFO and the delay contexts cannot
	//  discriminate them at all, and the delay-line traffic is INVARIANT across
	//  every reading tried.  They are here only so the frame can complete.
	if (m_speculative)
	{
		switch (act)
		{
		//  ★★★ THE PAIR TEST, row 29.  iw65 `200.1.8F.1C1' (ACT 0x01) reads register
		//  0x8F -- which body 1 now fills on 1 559 999 of 1 560 839 frames -- and
		//  iw66 `000.1.8C.107' (SRC 0x04) stores into 0x8C.  For the link to carry,
		//  whatever ACT 0x01 writes must be what SRC 0x04 reads.  ACT 0x01 sits in
		//  the same family as 0x13/0x14/0x19, all of which are temp captures, so the
		//  pairing under test is ACT 0x01 = tempA <- bus and SRC 0x04 = tempA.
		//  ⛔ ONE PAIRING OF SIXTEEN.  This is the first test of these codes that CAN
		//  discriminate -- their source is live for the first time -- but a single
		//  pairing passing is weak evidence and a single pairing failing is weaker.
		case 0x01: case 0x08: case 0x0C: case 0x11: case 0x16:
		case 0x0D: case 0x0E:
			//  ⛔ §132: THIS BLANKET CAPTURE IS ONE OF THE TWO STRUCTURAL REASONS
			//  §121 COULD NOT WORK.  It runs for 0x0D/0x0E BEFORE their own
			//  destination switch below, so every arm was "destination X *and*
			//  tempA" and selector value 2 (-> tempA) was indistinguishable from
			//  value 0 (none).  With mask bit 52 an action that carries its own
			//  non-zero selector is excused from it, so the selector can be
			//  isolated.  The other five codes are untouched.
			if (m_bx_supp_ta
					&& ((act == 0x0d && m_bx_sel0d) || (act == 0x0e && m_bx_sel0e)))
			{
				m_bx_supp_n++;
				break;
			}
			m_ta = u32(L) & 0xffffff;
			pv_wr_ta(u32(L));                                  // ★ §221 §E1
			break;
		case 0x1A:
			m_tb = u32(L) & 0xffffff;
			pv_wr_tb(u32(L));                                  // ★ §221 §E1
			break;
		default:
			break;
		}
	}

	switch (act)
	{
	//  ★★★ §222 §E-D85: the crossbar's LATCH half.  `ACT 0x03' occurs ONCE in 2557
	//  plain corpus words -- w63, the epilogue's mode-1 read of index 0x05 -- and it
	//  has NO modelled effect today, so this case is unreachable on every shipped run
	//  and cannot alter one.  ⚠ n = 1: the corpus can neither support nor refute the
	//  latch reading, which is why the arm is graded on §104 and on provenance
	//  (RULE 17) and never by listening.
	case 0x03:
		if (xb_latch())
		{
			m_xb = u32(L) & 0xffffff;
			m_xb_st_n++;
			if (m_frames_run > 900000)
			{
				const u32 b = ((m_in_val[0] != 0) || (m_in_val[1] != 0)) ? 1 : 0;
				m_xb_n[b]++;
				m_xb_lo[b] = std::min(m_xb_lo[b], s32(util::sext(m_xb, 24)));
				m_xb_hi[b] = std::max(m_xb_hi[b], s32(util::sext(m_xb, 24)));
			}
		}
		break;
	//  ★★★ §121 SPECULATIVE (mask bits 35..37 = a 3-bit DESTINATION SELECTOR):
	//  ENUMERATE ACTION 0x0D's DESTINATION AGAINST A LIVE TWO-SIDED CRITERION.
	//
	//  ACT 0x0D is the last blocker on the AUDIO path.  body-0 iw85 (000.2.0E.1CD)
	//  reads the per-unit base+0 cell through SRC 0x07 (mem[ptr], ANCHORED) and
	//  hands the operand to ACT 0x0D, which routes it nowhere -- so the body never
	//  acquires its input (§106, §107).  §110 made base+0 carry audio and §106
	//  showed that filling the cell alone changes nothing.
	//
	//  §107 tried to decode this with a follow-on statistic and the test
	//  DISQUALIFIED ITSELF: its control, the ANCHORED tempA capture 0x13, scored
	//  0 of 40 where it had to score high.  So: enumeration against a LIVE criterion
	//  the §104 instrument already reports, and which is currently FAILING --
	//      "first acc DIFFERS at -1" over body-0 iw84..199        (-1 = never)
	//  If the destination is right, body 0's accumulator becomes INPUT-dependent and
	//  that stops being -1.  203 corpus words carry this action, so any survivor
	//  must then be checked against them.
	//
	//  ⚠ Rule 8: a candidate that merely makes something non-constant is NOT a pass.
	//  The criterion is specifically INPUT dependence -- quiet frames versus frames
	//  with notes playing -- which a free-running or DC quantity cannot fake.
	//  ★ §133: the selector now comes from m_bx_sel0d (mask bits 42-44, or the sweep
	//  counter), and gains value 7.  Values 1/2/3/4/5/6 keep §121's meanings so its
	//  arms stay reproducible; §121's own bits 35-37 remain honoured as a fallback.
	//  ⚠ value 5 ("-> P") writes a RAW datum while a multiply writes
	//  `(coef*L) >> P_SHIFT' (:3039) -- the two differ by 2^ACC_SHIFT = 2^16, which
	//  is the §132 §3 tension.  Value 7 is the same destination at the multiply's
	//  scale.  Both are kept and enumerated so the scale is DECIDED, not assumed;
	//  §131 makes this the load-bearing pair, since P is the only register that can
	//  carry the sample across the entry.
	case 0x0d:
		if (m_speculative && (m_bx_sel0d || ((m_specmask >> 35) & 7)))
		{
			const u32 s0d = m_bx_sel0d ? m_bx_sel0d : u32((m_specmask >> 35) & 7);
			m_act0d_n++;
			switch (s0d)
			{
			//  ⛔ §142: THESE TWO WERE UNIT-BLIND -- the FOURTH instance of a defect
			//  this file has already fixed three times (§66 source side, §68 the
			//  bit-4 store, §75 the delay write).  `m_acc' was written
			//  unconditionally, but mask bit 14 is SET in the default so unit 1
			//  accumulates into `m_accb', and the SRC 0x10 READER at :2143 is
			//  unit-aware.  So in unit 1 the pair wrote ACCA and read ACCB -- the
			//  write and the read targeted different registers, and ACT 0x0D's
			//  write went to a register nothing in unit 1 reads.
			//  ★ That is exactly why "ACT 0x0D -> acc alone is bit-identical to the
			//  default" (§135 §3): in unit 1 it wrote a dead register, and §133's
			//  decode was only ever validated in unit 0, where m_acc IS the live one.
			//  Gated on bit 56 so the correction is A/B-able rather than assumed.
			case 1: bx_acc_w(L, false); break;                 // -> accumulator (load)
			case 2: m_ta = u32(L) & 0xffffff; pv_wr_ta(u32(L)); break;   // -> tempA
			case 3: m_tb = u32(L) & 0xffffff; pv_wr_tb(u32(L)); break;   // -> tempB
			case 4: m_dram.write_dword(m_dp, u32(L) & 0xffffff);
			        pv_wr_dram(m_dp, u32(L));
			        pk_write(m_dp, u32(L), 6, false, m_cur_iw); break;   // -> mem[ptr]
			case 5: m_p = u32(L) & 0xffffff; m_pw = 1; break;            // -> P, RAW (suspect scale)
			case 6: bx_acc_w(L, true); break;                  // -> accumulator (add)
			case 7: m_p = u64(s64(L)) << ACC_SHIFT; m_pw = 2; break;     // -> P at the MULTIPLY's scale
			default: break;
			}
		}
		break;
	//  ★ §133: ACT 0x0E gets the SAME menu, which it has never had.  It needs one:
	//  in bank 1 the entry is w0 (ACT 0x0D) immediately followed by w1 (ACT 0x0E),
	//  so whatever 0x0D writes, 0x0E can overwrite one slot later -- they cannot be
	//  decoded separately, which is §125 point 4 and the constraint §121 broke.
	case 0x0e:
		//  ★ §135 diagnostic (mask bit 53): restrict the P write to BODY slots.
		//  Shipping `ACT 0x0E -> P' corpus-wide rails unit 1 at -0x800000 on 98.9 %
		//  of presentations (§135).  ACT 0x0D -> acc alone is harmless, so 0x0E is
		//  the whole cause.  Of the ten 0x0E sites in a live frame, FIVE are in the
		//  resident scaffolding -- 3 in the kernel and 2 in the EPILOGUE, which is
		//  the output stage that presents the accumulator.  A P write there lands
		//  between the last multiply and `acc <- P', so it would replace the
		//  accumulated result with a raw datum.  This gate tests exactly that: body
		//  slots are iw84..199 (unit 0) and iw200..332 (unit 1); the kernel is
		//  0..59 and the epilogue 60..82.
		if (m_speculative && (m_specmask & (1ull << 53)) && m_cur_iw < 84)
			break;
		if (m_speculative && m_bx_sel0e)
		{
			m_bx_act0e_n++;
			switch (m_bx_sel0e)
			{
			case 1: bx_acc_w(L, false); break;   // §142: unit-aware, see ACT 0x0D
			case 2: m_ta = u32(L) & 0xffffff; pv_wr_ta(u32(L)); break;
			case 3: m_tb = u32(L) & 0xffffff; pv_wr_tb(u32(L)); break;
			case 4: m_dram.write_dword(m_dp, u32(L) & 0xffffff);
			        pv_wr_dram(m_dp, u32(L));
			        pk_write(m_dp, u32(L), 6, false, m_cur_iw); break;
			case 5: m_p = u32(L) & 0xffffff; m_pw = 3; break;
			case 6: bx_acc_w(L, true); break;
			case 7: m_p = u64(s64(L)) << ACC_SHIFT; m_pw = 4; break;
			default: break;
			}
		}
		break;
	case upd6383_disassembler::LO_ACT_CAP_TA:
	case upd6383_disassembler::LO_ACT_CAP_TA2:
		// 0x13 and 0x19 both capture into tempA.
		// ⚠ THIS COMMENT USED TO ASSERT "0x13 and 0x19 are ONE OPERATION IN TWO
		// ENCODINGS".  That has NO POSITIVE EVIDENCE and is no longer stated as
		// fact: their consumer lags are DISJOINT (0x13's tempA reader sits at
		// lag EXACTLY 8 -- one 8-word motif repetition -- in 35 of 40 sites vs a
		// 5.1% base rate; 0x19's sits at lag 1), and 9 of 38 distinct body
		// images use BOTH, so it is not a per-program assembler convention.
		// Not refuted -- unsupported.  dsp/tools/adjudicate8.py `capture'.
		// ⛔ NOT FORCED: the "72/72 by SINGLE DELAY" came from a harness that
		// wires the delay line at the polarity round 5 REVERSED.  Round 6
		// blamed the corrected re-run's 0 of 5832 on that harness's one-cell
		// `Line'; ROUND 7 CORRECTS THE DIAGNOSIS -- on a genuine two-address
		// line the published-polarity window still scores 108, THE SAME 108
		// MACHINES.  ** IT WAS A POLARITY ARTEFACT, NOT A MEMORY ARTEFACT. **
		// And at the FORCED polarity SINGLE DELAY cannot score 0x19 at all:
		// both its loops cross w21..w24 (ACTIONs 0x0D/0x0E, undecoded), so
		// every cell of the enumeration is "no search", not "no survivors".
		// WHAT IS MEASURED, with no delay line in the argument: ACTION 0x19 is
		// followed by a word SOURCING tempA in 74 of 89 distinct-image sites
		// (base rate 16.0%, shuffled null 42.7%).  DESTINATION = tempA is
		// measured; SOURCE (bus vs acc) is untested and OPEN.  It keeps
		// shipping under the owner's 2026-07-27 decision.  See upd6383d.h
		// LO_ACT_CAP_TA2 and dsp/analysis/adjudication-round8.md.
		m_ta = u32(L) & 0xffffff;
		pv_wr_ta(u32(L));                                          // ★ §221 §E1
		break;
	case upd6383_disassembler::LO_ACT_CAP_TB:
		m_tb = u32(L) & 0xffffff;
		pv_wr_tb(u32(L));                                          // ★ §221 §E1
		break;
	case upd6383_disassembler::LO_ACT_ST_BUS:
	{
		//  ★★★ ACTION 0x07's TARGET IS MODE-DEPENDENT, 2026-07-28, register row 21.
		//  alu_decoded() refuses this code off mode 2 precisely because its target
		//  there is unproven -- "...and neither is action 07's".  The speculative
		//  gate admits it anyway, and it was then storing to the POINTER on mode-1
		//  words, which is why the epilogue's registers stayed empty: its
		//  `000.1.8C.107' is a MODE-1 STORE to register 0x8C and the value was
		//  going to mem[m_dp] instead.
		//
		//  ★ THE RULE IS NOT NEW.  isa-adjudication.md behavioural note 1 already
		//  establishes exactly this for the bit-4 store -- "hi12 bit 4's target is
		//  mode-dependent -- mem[ptr] ONLY IN MODE 2.  Eight kernel words
		//  mis-execute otherwise." -- and do_store() implements it.  ⛔ Applying the
		//  same mode rule to ACTION 0x07 is the CONSISTENT reading, not a separate
		//  proof: it extends a proven rule to a second opcode.
		const u8 mode07 = upd6383_disassembler::c_format(word)
				? 2 : u8(upd6383_disassembler::class4(word) & 7);
		//  ★★★ §161 (mask bit 61): A DELAY WORD'S `addr8' IS A DIRECTION FIELD,
		//  NOT A REGISTER ADDRESS -- so ACTION 0x07 must not store to it.
		//  MEASURED consequence: CHORUS's four `880.1.20.2C7' delay READs carry
		//  ACT 0x07 and class 1, so this line takes d07 = addr8 = 0x20 and stores
		//  there 4 times a frame -- 4 513 920 stores, matching the census exactly.
		//  Register cell 0x20 is LFO WAVETABLE INDEX 3, and §160 measured it as the
		//  single destroyed entry in an otherwise bit-exact 36-entry sine
		//  (23 of 24 cells within 3 LSB; index 3 reads 0 where the sine needs
		//  +6 169 476, confirmed by index 15's exact -6 169 476).
		//  `addr8' bit 6 selecting READ/WRITE on these words is FORCED
		//  (adjudication-round5 item D; 0x20/0x30 READ, 0x60 WRITE, 276/276), so
		//  0x20 is a direction code that cannot also be a destination.
		//  ⚠ The other 22 addr8==0x20 words in the frame carry ACT 0x15 or 0x0B and
		//  never reach this line -- which is why the count is 4 and not 26, and is a
		//  built-in check that this gate is aimed at the right words.
		const bool esc_dly = (upd6383_disassembler::hi12(word) & 0x800)
				&& upd6383_disassembler::class4(word) == 1;
		//  ★★★ §222(c) THE UNIT REBASE, UNIFIED WITH THE OTHER TWO MODE-1 SITES.
		//  This line used to take a BARE `addr8' while the mode-1 bit-4 store (:3357)
		//  and the mode-1 READ (:3268) both take `addr8 | (m_cur_unit1 ? 0x80 : 0)' --
		//  a latent divergence beneath store_mode()'s own "one rule for both store
		//  sites" banner, found by PREDICT_D0_producer.md §3.3.  DECIDED by the corpus
		//  (body images name mode-1 destinations UNIT-RELATIVE 7 of 7, ABSOLUTE 0 of 7)
		//  and MEASURED on the one resident unit-1 case (iw332 -> m_rf[0x8F], read back
		//  by w65 on 540 000/540 000 frames, §221).  Left as it was, a04 FLANGER w64 and
		//  a05 PHASER w105 (both mode 1, ACT 07, addr8 = 0x0E) would write UNIT 0's cell
		//  while running as unit 1.
		//  ⚠ The two readings are computed SIDE BY SIDE and every disagreement is
		//  counted UNCONDITIONALLY, so "provably inert in the resident frame" is a
		//  measurement in the log and not a claim in a comment (rule 8).
		const bool d07_ptr = !(mode07 == 1
				&& !(m_speculative && (m_specmask & (1ull << 61)) && esc_dly));
		const u8 d07_bare  = upd6383_disassembler::addr8(word);
		const u8 d07_rebas = u8(d07_bare | (m_cur_unit1 ? 0x80 : 0x00));
		if (!d07_ptr)
		{
			m_rebase_eval++;
			if (d07_bare != d07_rebas) m_rebase_diff++;
		}
		u8 d07 = d07_ptr ? m_dp : d07_rebas;
		if (m_speculative && (m_specmask & (1ull << 61)) && esc_dly && mode07 == 1)
			m_dlystore_fix_n++;
		//======================================================================
		//  ★★★ §109 SPECULATIVE (mask bit 28, 0x10000000): ACTION 0x07's MODE-2
		//  store lands on the POST-increment cell.
		//
		//  The shipped model uses m_dp, and the ONLY pointer advance on this path is
		//  at the very end of exec_alu(), so every ACT-07 store today is on the
		//  PRE-increment cell.  That was never enumerated: lfo_ramp.py:868 hard-codes
		//  mem[p] for ACTION 0x07 while offering `next_ptr' for the bit-4 store, so
		//  the project's 276 480-machine search settled the timing of bit 4 and
		//  silently ASSUMED it for ACTION 0x07.  This bit is that missing arm.
		//
		//  ⛔ NOT A FIX and NOT A DECODE -- a DIAGNOSTIC with a FIRED COUNT, default
		//  OFF.  It moves every mode-2 ACT-07 store in the machine, not just iw32:
		//  kernel iw34/iw39, body-0 iw92 and ~300 body words.  Read the fired count
		//  before reading any consequence.
		//
		//  The K6 input-stage words are EXCLUDED because exec_addressing_only() has
		//  ALREADY advanced m_dp for them (exec_alu_k6() restores it afterwards), so
		//  m_dp is the POST cell there in BOTH arms.  That makes iw11 -- the one K6
		//  word carrying ACTION 0x07 -- a built-in POSITIVE CONTROL: the probe must
		//  report iw11 landing on its post-increment cell with the bit OFF, and if it
		//  does not, the probe cannot see a post-increment at all and any null here
		//  is worthless.
		//======================================================================
		if (m_speculative && (m_specmask & 0x10000000)
				&& mode07 == 2 && upd6383_disassembler::ptr_postinc(word))
		{
			if (m_in_k6)
				m_act07_post_k6_n++;            // pointer already advanced: left alone
			else
			{
				d07 = u8(m_dp + s8(upd6383_disassembler::addr8(word)));
				m_act07_post_n++;
			}
		}
		//======================================================================
		//  ★★★ §119 SPECULATIVE (mask bit 34, 0x400000000): THE MEMORY-TO-MEMORY MOVE.
		//
		//  Same geometry as bit 28 but restricted to the two sources that read the
		//  DESTINATION CELL: SRC 0x00 and SRC 0x11 are both mem[m_dp], so under the
		//  shipped PRE-increment target the word is `mem[dp] <- mem[dp]', an IDENTITY.
		//  Corpus census over the 41 committed listings (3057 words): of the 444
		//  mode-2 ACTION-0x07 words, 52 carry SRC 0x11 and 4 carry SRC 0x00 -- all 56
		//  degenerate under PRE, 46 of them with addr8 != 0 so POST makes them real
		//  MOVEs.  The other 388 (SRC 0x10 x256, 0x1A x43, 0x19 x41, 0x0B x46, ...)
		//  name a source that is not the destination and are left at PRE, so §109's
		//  two PRE anchors iw34 and iw88 -- both SRC 0x10 -- do not move.
		//
		//  ★ THE WORD THIS IS AIMED AT is CHORUS body-0 iw92 `000.2.09.447': SRC 0x11
		//  at dp = 0x07 (the LFO phase cell Q), addr8 = +9.  lfo-ramp.md's tail motif
		//  calls it "the phase leaves Q here; addr8 repositions".  Under PRE it stores
		//  the phase onto the phase cell and the only surviving effect is the pointer
		//  move; under POST it deposits the phase at 0x10, which is exactly the cell
		//  iw93/iw94 then read (iw94 = `192.A.40.000', SRC 0x00 = mem[m_dp], class A).
		//
		//  ⛔ NOT A DECODE.  A diagnostic with a fired count, default OFF, whose only
		//  claim is two-sided: either cell 0x10 becomes the phase sawtooth or it does
		//  not.  K6 excluded for the same reason bit 28 excludes it (m_dp is already
		//  the post cell inside exec_alu for those words).
		//======================================================================
		if (m_speculative && (m_specmask & 0x400000000ull)
				&& mode07 == 2 && !m_in_k6
				&& (src == 0x00 || src == 0x11)
				&& upd6383_disassembler::addr8(word) != 0
				&& upd6383_disassembler::ptr_postinc(word))
		{
			d07 = u8(m_dp + s8(upd6383_disassembler::addr8(word)));
			m_act07_memmove_n++;
			if (u32(L) & 0xffffff) m_act07_memmove_nz++;
		}
		//======================================================================
		//  ★★★ §110 THE iw11 TIMING DEFECT -- FIXED (mask bit 30 REVERTS to the old
		//  behaviour; the fix is ON by default).
		//
		//  §109 MEASURED that iw11 (`0400201447', the ONE K6 input-stage word
		//  carrying ACTION 0x07) stored at its POST-increment cell 0x06 while EVERY
		//  other ACT-07 word in the build stored at its PRE-increment cell.  Two
		//  timings for one action code in one binary.
		//
		//  CAUSE: exec_alu_k6() is called by exec_addressing_only() AFTER that
		//  function has already advanced m_dp, so inside exec_alu() the pointer is
		//  the post-increment cell.  §35's `if (m_in_k6)' short-circuit -- which
		//  exists precisely to stop a K6 word storing twice at the wrong cell --
		//  covers ONLY the bit-4 site a few hundred lines above.  This site was
		//  never given the same treatment.
		//
		//  WHY CORRECT THE ADDRESS RATHER THAN SKIP THE STORE: the bit-4 site can
		//  skip, because exec_addressing_only() performs that store itself at
		//  `cell = m_dp' captured on entry.  It performs NO ACT-07 store, and iw11
		//  carries no bit 4 (hi12 = 0x400), so skipping here would lose the store
		//  entirely.  Undoing the advance reproduces the pre-increment cell.
		//
		//  PRE is the right convention on independent evidence, not by symmetry:
		//  §109 confirmed it on iw34, a FULLY DECODED anchored ACT-07 word, and
		//  lfo-ramp.md §8.3 ran the post-increment hypothesis over 276 480 machines
		//  with ZERO survivors.
		if (m_in_k6 && !(m_speculative && (m_specmask & 0x40000000))
				&& mode07 == 2 && upd6383_disassembler::ptr_postinc(word))
		{
			const u8 pre = u8(m_dp - s8(upd6383_disassembler::addr8(word)));
			if (pre != d07) m_k6_act07_fix_n++;
			d07 = pre;
		}
		if (mode07 == 1 && m_st07n < 8)
		{   // ★ where is the pointer, and what is under it, at these five stores?
			bool seen = false;
			for (u32 q = 0; q < m_st07n; q++) if (m_st07_dest[q] == d07) seen = true;
			if (!seen)
			{
				m_st07_dest[m_st07n] = d07;
				m_st07_ptr[m_st07n] = m_dp;
				m_st07_val[m_st07n] = L;
				m_st07_src[m_st07n] = upd6383_disassembler::lo_src(word);
				m_st07n++;
			}
		}
		//  ★★★ §41 SPECULATIVE (mask bit 5): DO NOT LET AN UNSUPPORTED SOURCE
		//  OVERWRITE A HOST-PROGRAMMED REGISTER.
		//  MEASURED: register 0x06 -- the unit-0 OUTPUT LEVEL, which cold boot sets
		//  to +0.500000 and which do_presentation() reads back -- is written
		//  1 613 627 times, ONCE PER FRAME, and EVERY WRITE IS ZERO.  0x86 (unit 1,
		//  +0.183992) likewise.  So the presentation's `if (lvl != 0)' guard skips
		//  the level multiply entirely: the per-unit output level is never applied.
		//  The value written comes from `w72' (000.1.06.087) and `w77' -- ACT 0x07
		//  stores whose SOURCE is SRC 0x02, which this register grades "PURE
		//  ENUMERATION ... no independent support" and which reads mem[ptr] = 0.
		//  This is the input-latch failure again, one register along: a store with an
		//  invented value landing on a value the HOST established.  r2-output.md §3.1
		//  describes w77 as one that "aims a POINTER at reg 0x86", not one that
		//  writes it -- so the store itself is likely the mis-decode.
		//  ⛔ A GUARD, NOT A DECODE: it suppresses the symptom so the level survives
		//  and the presentation can be measured; what w72/w77 really do is OPEN.
		const bool unsupported_src = (src == 0x02 || src == 0x03);
		const bool host_reg = (d07 == 0x06 || d07 == 0x86);
		//  ★ §109: the two suppressors made explicit so the probe records only the
		//  stores that ACTUALLY happen.  Behaviour is unchanged -- the if/else-if/else
		//  ladder below is the same ladder, and kwatch()/watch_store() still run on
		//  every visit exactly as they did (the indentation always lied about that).
		const bool lvl_hit = m_speculative && (m_specmask & 0x20)
				&& unsupported_src && host_reg;
		const bool ab_hit  = !lvl_hit && m_ab_nostore08 && src == 0x08;
		//  ★★★ §213: THE THIRD SUPPRESSOR, WHICH THE COMMENT ABOVE PREDATES.
		//  §112's arm below (mask bit 25, ON in the shipped default) performs NO
		//  D-RAM store -- it latches P instead -- but it was added AFTER the two
		//  suppressors were made explicit, and the `else' in front of store_mode()
		//  is UNBRACED, so kwatch()/watch_store()/store_probe()/m_dwr[] kept running
		//  on every VISIT.  The probe therefore reported stores the machine does not
		//  perform, at exactly three words per frame (§112 fired 3 630 720 times =
		//  3 x 1 210 240 settled frames = iw32, iw34, iw39).
		//  ⇒ §211 §6's headline lead -- "iw39 stores TWICE to cell 0x06 and the
		//  second one wins" -- was ONE REAL STORE AND ONE PHANTOM.
		//  ★ MEASURED, from §211's own log, independently of this source: iw34
		//  (`000.A.FF.407', class A, ACT 0x07) was logged storing 8 388 607 to cell
		//  0x06, yet §104's residency column shows 0x06 still holding 6 039 795 --
		//  what iw33's bit-4 store put there -- at iw38 AND at iw39, with nothing
		//  writing it in between.  The store did not happen.
		//  Default ON; UPD6383_STPROBE=0 restores the old accounting for the A/B.
		const bool act07_latch = m_speculative && (m_specmask & 0x2000000u)
				&& upd6383_disassembler::class4(word) == 0xa
				&& !upd6383_disassembler::c_format(word);
		const bool phantom = act07_latch && m_stprobe;
		if (lvl_hit)
			m_lvlguard_n++;
		else if (ab_hit)                          // ★ §104 A/B, diagnostic only
			m_ab_nostore08_n++;
		else
		//  ★★★ §112 SPECULATIVE (mask bit 26 was the §106 diagnostic; this is bit 25's
		//  neighbour -- see below): ACTION 0x07 ON A CLASS-A WORD LATCHES P, IT DOES
		//  NOT STORE TO D-RAM.
		//
		//  class4 == 0xA is the COEFFICIENT CONSUMER (it advances the cursor), and
		//  lfo-ramp.md §11 annotates iw32's two SIBLING class-A / SRC-0x08 words in
		//  exactly those terms:
		//      092.A.dd.200   ... acc += P ; P := INC
		//      094.A.dd.200   ... op2      ; P := 0x7FFFFF
		//  i.e. a class-A word reading SRC 0x08 LATCHES the coefficient into the
		//  multiplier input.  iw32 (000.A.FF.207) is the same family with ACT 0x07.
		//  Guard 6 already concedes the point being tested here: "Applying the same
		//  mode rule to ACTION 0x07 is the CONSISTENT reading, not a separate proof".
		//
		//  ★ TWO-SIDED CRITERION, CURRENTLY FAILING: iw32 stores 0x400000 = 4194304
		//  onto cell 0x07, and 4194304 is EXACTLY the value the CHORUS LFO phase cell
		//  is pinned at every frame.  If this reading is right the phase stops being
		//  reset and RAMPS by 114 per frame (the §111-corrected increment).  If it is
		//  wrong the phase stays pinned and nothing else should move either.
		if (act07_latch)
		{
			//  ★★★ §136: THE REGISTER SPLIT ALREADY EXISTS -- THIS SITE USES THE
			//  WRONG HALF OF IT.  `m_k'/`m_l' are declared "multiplier input
			//  latches" (upd6383.h:451) and `m_p' is the "MPLY product register"
			//  (:450).  §112's own reasoning above is *"a class-A word reading
			//  SRC 0x08 LATCHES the coefficient into the multiplier input"* -- but
			//  the code writes the PRODUCT register, so it does not latch an input
			//  at all, it overwrites the outcome of the last multiply with a raw
			//  24-bit datum.  §133 proved a raw datum in P is wrong by 2^ACC_SHIFT.
			//
			//  ⛔⛔ §165 2026-07-30: THE PAIR HAS NOW BEEN EVALUATED TOGETHER, AND
			//  IT IS REFUTED.  Bit 54 alone is BIT-IDENTICAL to the control in every
			//  D-RAM cell.  Bit 54 + bit 4 produces `§70 ACCA min = max =
			//  176 471 605 248' -- the exact DC constant §137 already retracted, and
			//  min == max, so standing rule 1 catches it before it can be reported as
			//  output.  Both bits stay off.  The paragraph below is kept because its
			//  REASONING is still the best account of why the two are coupled; only
			//  its closing claim that they were never tested together is now stale.
			//  ⚠ §112 AND §40 ARE COUPLED, and neither can be right alone:
			//    * writing `m_k' here is a NO-OP unless the multiply reads it, and
			//      the default multiply (:3126) bypasses the latch and uses the
			//      freshly-read `coef' -- "a latched-coefficient MAC with the latch
			//      bypassed" in this file's own words (:3136).
			//    * §40 (mask bit 4) makes the multiply read `m_k', and was REFUSED
			//      because it "measurably destroys the result" -- but it was tested
			//      while THIS site was writing the wrong register, so the pair has
			//      never been evaluated together.
			//  Bit 54 routes the latch to the input register; the §40 arm is bit 4.
			if (m_speculative && (m_specmask & (1ull << 54)))
			{
				m_k = u32(L) & 0xffffff;    // the MULTIPLIER INPUT latch
				m_act07_latchk_n++;
			}
			else
			{
				m_p = u32(L) & 0xffffff;    // the PRODUCT register (§112 as shipped)
				m_pw = 5; /* §175: who last wrote P -- "§112 classA-ACT07" */
				m_act07_latchp_n++;
			}
		}
		else
		{
			//  ★★★ §222 §E-D85: the crossbar's STORE half.  `SRC 0x03' is corpus-unique
			//  (w70, the only site in 2557 plain words), so this touches exactly ONE
			//  word and cannot leak into the five sites mask bit 23 controls.
			const bool xb_wr = xb_route() && src == 0x03 && mode07 == 1;
			if (xb_wr) m_xb_wr_dram_n++;
			store_mode(mode07, u8(d07), u32(L), 3, xb_wr);             // §99, site 3
		}
		//  ★★★ §213: THE BOOKKEEPING NOW FOLLOWS THE STORE, NOT THE VISIT.
		//  These four lines used to sit outside the `else' with no braces around it,
		//  so they ran even when the §112 arm above had latched P and stored nothing.
		//  The `!lvl_hit && !ab_hit' guard on store_probe() is the hand-patch that
		//  covered the first two suppressors; the third one never got it.
		if (!phantom)
		{
			kwatch(d07, s32(u32(L) & 0xffffff));
			watch_store(d07, s32(L) & 0xffffff, 3);
			if (!lvl_hit && !ab_hit)
				store_probe(u8(d07), s32(L) & 0xffffff, 3);            // §109
			m_dwr[d07]++;
			if (u32(L) & 0xffffff) m_dwr_nz[d07]++;
		}
		else
			m_stprobe_n++;
		break;
	}
	case upd6383_disassembler::LO_ACT_ACC_BUS:
		break;                  // 0x00: its whole effect is the adder, above
	default:
		break;                  // 0x12 and 0x15: no temp / memory side effect
	}

	// ---- the multiply, and the ONE place the cursor advances ----------------
	// class A only.  class 8 sets bit 23 -- so it FETCHES -- but it does NOT
	// advance the cursor (K4, FORCED), and this model does not give it a
	// multiply either: the biquad, which is the block that determines class 8's
	// position, reproduces to 0.094 dB with class 8 doing no multiply at all.
	// coeff_consumer() carries the C-format guard, so a C-format word whose
	// immediate happens to read `class4 == 0xA' -- e.g. the frame terminator
	// C00.A.47.407 -- can never reach here.
	//  ★ §29: FETCH (the multiply) and CONSUME (the cursor advance) are separate.
	if ((m_speculative && (m_specmask & 4)) ? upd6383_disassembler::coeff_fetch(word)
					  : upd6383_disassembler::coeff_consumer(word))
	{
		//  ★★★★ §72 SPECULATIVE (mask bit 17): THE BODY'S COEFFICIENT BANK IS 0x90+,
		//  NOT THE RAMP AT 0x50..0x8B.
		//  MEASURED this session over all 91 algorithms' parameter streams:
		//      C-RAM writes into 0x50..0x8B :   0   (from  0 algorithms)
		//      C-RAM writes into 0x90..0xB5 : 445   (from 12 algorithms)
		//  NO algorithm ever writes the ramp bank.  Its monotonic contents are boot
		//  residue, which is why no scaling of it ever worked (§43 Q0.23 -> silence,
		//  §44 unity -> saturation, §53 Q0.16 -> saturation) and why its shape never
		//  looked like a gain set.
		//  cram-unit-base.md item A is MEASURED: the unit-1 reverbs' class-A fetches
		//  resolve 33/33 at base 0x90 and 0/33 at base 0x00, in 12/12 algorithms.
		//  The in-program ldptr aims the cursor at 0x50 (unit 1) / 0x70 (unit 0), so
		//  relocate that window onto the bank the host actually fills.
		u32 ccur = m_cursor;
		if (m_speculative && (m_specmask & 0x20000) && ccur >= 0x50 && ccur <= 0x8b)
			ccur = u8(ccur + 0x40);
		u32 coef = m_cram.read_dword(ccur) & 0xffffff;
		//  ★ §53 SPECULATIVE (mask bit 13): READ THE RAMP BANK AT Q0.16, NOT Q0.23.
		//  §52 established that the microcode DELIBERATELY aims the coefficient cursor
		//  at 0x50..0x8B (three ldptr 0x821 loads: iw42->0x70, iw50->0x50, iw69->0x90)
		//  and that 1590 body words fetch from it as coefficients while NO delay word
		//  ever does (disjoint, 91 programs).  So the ramps ARE multiplicands -- but as
		//  Q0.23 they are 0.006..0.008 and cost 10^4 per frame.
		//  As Q0.16 the same cells are 0.5..0.98: 0x008000 << 7 = 0x400000 = exactly
		//  +0.5, and 0x00FC00 << 7 = 0x7E0000 = 0.984.  Plausible reverb gains.
		//  ⛔ FALSIFIER, stated before the run: a no-stimulus window must be SILENT and
		//  the output must TRACK the input.  A non-zero silent window kills this
		//  outright, whatever the note windows do.
		if (m_speculative && (m_specmask & 0x2000)
				&& m_cursor >= 0x50 && m_cursor <= 0x8b)
			coef = (coef << 7) & 0xffffff;
		//  ★★★ §44 SPECULATIVE (mask bit 8): C-RAM 0x50..0x8B IS A DELAY-TAP TABLE,
		//  NOT COEFFICIENTS.  Dumped, the space has three clearly distinct regions:
		//      0x00..0x13  real parameters (LFO rate 000072, wrap 7FFFFF, 400000 ...)
		//      0x50..0x6F  LINEAR RAMP, step 0x400:  008000 008400 ... 00FC00
		//      0x70..0x8B  LINEAR RAMP, step 0x4BE:  000000 0004BE ... 007FFF
		//      0x90..0xB4  real coefficients (200000 400000 3B9885 2DF3A0 C62251 ...)
		//  The two ramps are exactly the host's two 30-cell write runs, and they are
		//  monotonic, evenly spaced and address-shaped -- 0x8000..0xFC00 spans the
		//  upper half of a 64 K space in steps of 1024.  This chip's block diagram
		//  (PROVEN) gives it "an on-chip controller for external DRAM; ring-buffer
		//  address generation (echo / reverb-A / reverb-B regions)", which is what a
		//  table like that is for.
		//  MEASURED CONSEQUENCE of consuming them as coefficients: as Q0.23 they are
		//  0.006..0.008, and the body's ladder multiplies the accumulator by one at
		//  each stage -- 1.97e11 -> 2.5e9 -> 3.3e7 -> 424 000 -> 10 656 -> 0. That
		//  chain IS the missing 10^4, and the kernel (cursor 0x90+, real
		//  coefficients) shows no such decay.
		//  ⛔ The delay-DRAM datapath is NOT modelled, so the honest action is to stop
		//  MULTIPLYING BY AN ADDRESS rather than to invent a delay read.
		const bool tap_table = (m_cursor >= 0x50 && m_cursor <= 0x8b)
				&& !(m_speculative && (m_specmask & 0x20000));
		if (m_speculative && (m_specmask & 0x100) && tap_table)
		{
			m_tap_n++;
			if (upd6383_disassembler::coeff_consumer(word)) m_cursor++;
			return;
		}
		m_k = coef;
		m_l = u32(L) & 0xffffff;
		{   // ★ which multiply overflows?  record the biggest |product| and its operands
			const s64 pre = s64(util::sext(coef, 24)) * s64(L);
			if (std::abs(pre) > std::abs(m_mulmax))
			{ m_mulmax = pre; m_mul_coef = coef; m_mul_L = L; m_mul_src = src; m_mul_iw = u32(m_pc / upd6383_disassembler::WORD_BYTES); }
		}
		//  ★★★ SPECULATIVE, 2026-07-28, APPLIED ON THE OWNER'S INSTRUCTION.
		//  An `hi12[3:1] == 2' (HI_ACC_HOLD) word does NOT update the product
		//  register.  See kn5000-roms-disasm/dsp/analysis/
		//  unblocking-and-discriminators.md sect. 17.
		//
		//  EVIDENCE.  The LFO's ramp constant is the one number on this chip
		//  whose value is known independently -- floor(f * 2^23 / 44100), read
		//  out of the ROM by dsp/tools/lfo_ramp.py.  Over the 16 LFO-bearing
		//  images the model reproduces 14 of 19 such constants with this line
		//  suppressed and 11 with it live, and EVERY constant reproduced
		//  without it is still reproduced with it -- a strict superset, not a
		//  trade.  It also fixes the structural defect that motivated the
		//  search: a program carrying LFOs at DIFFERENT rates previously ran
		//  only its first, because the wrap word (f31 == 2, coefficient
		//  0x7FFFFF) left that constant in P and the next block's `acc <- P'
		//  word inherited it.  MODULATED CHORUS now runs both its rates and
		//  MIX UP two of its three.
		//
		//  CONTROLS.  SINGLE DELAY's validated output is unchanged (lag 1001,
		//  gain +0.02149296, itself a three-factor ROM coefficient product
		//  matched to 0.001 %); execution coverage is unchanged; and the
		//  PARAMETRIC EQ biquad reproduces its designer at 0.198 dB either way.
		//  ⛔ The biquad NEITHER CONFIRMS NOR REFUTES -- only 1 of its 9 words
		//  is f31 == 2, so it is nearly blind here.  THE LFO IS THE SOLE
		//  ANCHOR, and 5 of the 19 constants are still unexplained
		//  (RING MODULATOR 190217, MIX UP's 1407, PEQ+CHORUS/FLANGER/VIBRATO),
		//  so this may be one refinement short of the real rule.
		//
		//  The CURSOR still advances and m_k/m_l still latch: the coefficient
		//  is consumed either way, and K4's cursor result is untouched.
		if (upd6383_disassembler::hi_f31(upd6383_disassembler::hi12(word))
				!= upd6383_disassembler::HI_ACC_HOLD
				&& !(m_speculative && (m_specmask & 0x10)))
		{
			m_mul_issued = true;    // ★ §29: it RAN -- distinct from "P came out 0"
			m_p = u64((s64(util::sext(coef, 24)) * s64(L)) >> P_SHIFT) & 0xfffffffffffULL;
			m_pw = 6; /* §175: who last wrote P -- "THE MULTIPLY" */
			//==============================================================
			//  ★★★ §174 PROBE (read-only): WHICH OPERAND IS ZERO?
			//
			//  §169 claimed the LFO index multiply "never issues" because
			//  ACT 0x15 decodes as a no-op.  ⛔ THAT IS WRONG AT SOURCE LEVEL:
			//  the gate above is `coeff_consumer(word)' = class4 == 0xA and not
			//  C-format -- the ACTION FIELD IS NOT IN IT.  CHORUS's word is
			//  `202.A.07.1D5': class A, f31 = 1, so it multiplies already.
			//  §169's MEASUREMENT stands (m_p 0..0 chg 0 two words later); its
			//  CAUSE does not.
			//
			//  If the multiply issues and the product is still zero, then one of
			//  its operands is zero, and WHICH one names the defect:
			//     L    == 0  ->  the D-RAM read is empty  -> the POINTER (§168)
			//     coef == 0  ->  the coefficient is empty -> the CURSOR
			//  ⚠ Measure at THE MULTIPLY, not at the consumer two words later --
			//  measuring downstream is what made §169 mis-attribute this.
			//  ★ Change-counts, not ranges (§167): a range cannot tell a live
			//  operand from two constants.
			if (upd6383_disassembler::class4(word) == 0xa
					&& (word & 0x1f) == 0x15)
			{
				//  ★★ §175 FIX: KEY THIS BY WORD.  The first cut pooled every
				//  class-A ACT-0x15 site in every program and reported "both
				//  operands live" -- while §175 showed THE MULTIPLY is the last
				//  writer of P at CHORUS's lookup and P is still 0 there.  A
				//  pooled census cannot see one dead site among 36 million live
				//  firings.  That is §155's error in a new place.
				const s64 cf0 = s64(util::sext(coef, 24));
				int sl = -1;
				for (int q = 0; q < m_a15w_n; q++) if (m_a15w_word[q] == word) { sl = q; break; }
				if (sl < 0 && m_a15w_n < 24) { sl = m_a15w_n++; m_a15w_word[sl] = word; }
				if (sl >= 0)
				{
					if (!m_a15w_hits[sl])
					{
						m_a15w_cmin[sl] = m_a15w_cmax[sl] = cf0;
						m_a15w_lmin[sl] = m_a15w_lmax[sl] = s64(L);
						m_a15w_pmin[sl] = m_a15w_pmax[sl] = s64(m_p);
						m_a15w_dmin[sl] = m_a15w_dmax[sl] = m_dp;                 // §176 F2
					}
					else
					{
						m_a15w_cmin[sl] = std::min(m_a15w_cmin[sl], cf0); m_a15w_cmax[sl] = std::max(m_a15w_cmax[sl], cf0);
						m_a15w_lmin[sl] = std::min(m_a15w_lmin[sl], s64(L)); m_a15w_lmax[sl] = std::max(m_a15w_lmax[sl], s64(L));
						m_a15w_pmin[sl] = std::min(m_a15w_pmin[sl], s64(m_p)); m_a15w_pmax[sl] = std::max(m_a15w_pmax[sl], s64(m_p));
						m_a15w_dmin[sl] = std::min<u32>(m_a15w_dmin[sl], m_dp);   // §176 F2
						m_a15w_dmax[sl] = std::max<u32>(m_a15w_dmax[sl], m_dp);
					}
					if (cf0) m_a15w_cnz[sl]++;
					if (L)   m_a15w_lnz[sl]++;
					m_a15w_hits[sl]++;
				}
				const s64 cf = cf0;
				if (!m_a15_n)
				{
					m_a15_cmin = m_a15_cmax = cf;  m_a15_lmin = m_a15_lmax = s64(L);
					m_a15_pmin = m_a15_pmax = s64(m_p);
				}
				else
				{
					m_a15_cmin = std::min(m_a15_cmin, cf);  m_a15_cmax = std::max(m_a15_cmax, cf);
					m_a15_lmin = std::min(m_a15_lmin, s64(L)); m_a15_lmax = std::max(m_a15_lmax, s64(L));
					m_a15_pmin = std::min(m_a15_pmin, s64(m_p)); m_a15_pmax = std::max(m_a15_pmax, s64(m_p));
					if (cf != m_a15_cprev) m_a15_cchg++;
					if (s64(L) != m_a15_lprev) m_a15_lchg++;
				}
				m_a15_cprev = cf;  m_a15_lprev = s64(L);
				if (cf) m_a15_cnz++;
				if (L)  m_a15_lnz++;
				m_a15_n++;
			}
		}
		//  ★ §29: the cursor still advances ONLY on class 0xA -- K4's forced result
		//  is untouched by the fetch/consume split.
		if (upd6383_disassembler::coeff_consumer(word))
			m_cursor++;
	}

	//  ★★★ §40 SPECULATIVE (mask bit 4): THE MULTIPLY IS NOT GATED BY THE FETCH.
	//  dsp_disasm.py's cursor_fetch() is documented as "CURSOR-FETCH enable (NOT
	//  multiply-enable)", and this device declares m_k/m_l as "multiplier input
	//  latches" -- latched on fetch (above) and then never used, because the
	//  multiply reads the freshly-read `coef' instead.  That is a latched-coefficient
	//  MAC with the latch bypassed.
	//  The reading: bit 23 RELOADS K from C-RAM[cursor]; the multiplier computes
	//  P = K x L on every word that is not f31 == HOLD, using whatever K currently
	//  holds.  Words with no coefficient of their own reuse the last one -- which is
	//  what a coefficient LATCH is for, and what makes "not multiply-enable" true.
	if (m_speculative && (m_specmask & 0x10)
			&& upd6383_disassembler::hi_f31(hi) != upd6383_disassembler::HI_ACC_HOLD)
	{
		m_mul_issued = true;
		m_l = u32(L) & 0xffffff;
		m_p = u64((s64(util::sext(m_k, 24)) * s64(L)) >> P_SHIFT) & 0xfffffffffffULL;
		m_pw = 7; /* §175: who last wrote P -- "§40 m_k multiply" */
	}

	//  ⚠⚠ §223: THIS PRINT WAS A LATENT RUNAWAY, and the nop-guard narrowing set it
	//  off.  Its bound was `m_dbg213 <= 3', but `m_dbg213' is incremented ONLY by the
	//  probe at the top of this function, whose own bound is `< 3' -- so once that one
	//  stops at 3 this one is true FOREVER.  It was harmless only because `iw213' was
	//  swallowed by the nop guard and never reached exec_alu() at all.  With the guard
	//  narrowed it fired 1 020 000 times and made the log 300x larger.
	//  ★ The class of defect is the instrument audit's own: a bound that depends on a
	//  counter some OTHER site owns.  Give it its own counter and its own bound.
	if (m_cur_iw == 213 && m_dbg213b < 3 && m_frames_run > 420000)
	{
		m_dbg213b++;
		logerror("upd6383: §90 iw213 REACHED post-increment: cl=%X dd=%d dp=%02X\n",
				cl, (int)dd, m_dp);
	}
	// ---- the pointer post-increment (classes 2 and A) -----------------------
	if ((cl & 7) == 2)
		m_dp = u8(m_dp + dd);

	//  ★ §222 `§E-D0': the AFTER half -- the parked pointer and the accumulators the
	//  word actually left behind.  Deliberately AFTER the post-increment, which is the
	//  whole point of having two columns.
	if (m_pk_pending >= 0)
		pk_after();

	//  ★ §29: now that the product and the accumulator are final, present.
	if (m_pres_pending)
	{
		m_pres_pending = false;
		do_presentation();
	}
}


//**************************************************************************
//  THE DECODED FORMS -- ONE IMPLEMENTATION, TWO CALLERS
//**************************************************************************

//  execute_run() (the debugger path) and run_frame() (the audio path) used to
//  carry two hand-copied dispatch ladders.  They agreed, but "they agree" is a
//  property that has to be re-established after every edit, and this file exists
//  inside a project whose most expensive recent bug was two mirrors drifting
//  apart.  So there is now exactly one ladder and both callers use it.
//
//  EVERY BRANCH BELOW IS A DECODED FORM.  Anything not listed here traps; that
//  is the rule this device is for.

void upd6383_device::exec_decoded(u64 word)
{
	const u8 ad = upd6383_disassembler::addr8(word);

	if (upd6383_disassembler::is_setvec(word))
	{
		// THE PER-UNIT CALL VECTOR (K5, DETERMINED destination).  Stored, and
		// deliberately NOT wired to the call sequencer in this pass: the
		// sequencer's target table (0x0E -> 84, 0x0F -> 200) is an OBSERVED
		// upload layout, and swapping it for these registers changes the PC
		// ORDER of every frame.  That is a separate, testable change --
		// enumerated in the note, not smuggled in here.
		m_vec[upd6383_disassembler::vector_unit(upd6383_disassembler::lo12(word))]
				= upd6383_disassembler::c_a(word);
	}
	else if (upd6383_disassembler::is_ldptr(word))
	{
		// ★ THIS NO LONGER LOADS THE D-RAM OPERAND POINTER.
		// K3 (dsp/analysis/k3-pointers.md sect. 4) MEASURED that lo12 = 0x821
		// addresses the COEFFICIENT space -- its three in-program payloads
		// 0x70 / 0x50 / 0x90 are three of the four structural bases of the
		// host's own C-RAM map -- and FORCED that it is not the implicit
		// coefficient cursor either.  Both halves of that result say it is not
		// the D-RAM pointer, so `m_dp = ad' was executing a semantic the corpus
		// has since withdrawn (notes/kn5000-dsp-pointer.md headline 2).
		//
		// It is displayed as CP because CP is the CDJ-500 block diagram's
		// COEFFICIENT POINTER and this register addresses C-RAM; that
		// IDENTIFICATION is an EDUCATED GUESS.  What is FORCED is the negative
		// part -- it is neither the cursor nor the D-RAM operand pointer.
		//
		// CONSEQUENCE, stated because it is observable: NO decoded word loads
		// m_dp.  ★ THAT IS STILL TRUE AND IT IS NO LONGER A HOLE (2026-07-27).
		// The D-RAM ORIGIN IS PINNED -- base = 0x05 | (unit << 7), FORCED, see
		// DRAM_UNIT_BASE -- and it is established at the per-unit CALL, not by an
		// instruction.  K3's `0x827' candidate stays falsified (0 of 85 streams).
		// What is still OPEN is WHICH word, if any, performs the rebase: the site
		// is constrained to the window between the last pointer-moving word and
		// the body's first, and nothing selects an instruction inside it.
		m_cp = ad;
		//  ★★★ ldptr ALSO SEEDS THE COEFFICIENT CURSOR -- register row 25, and it
		//  SUBSUMES rows 19 and 24.  MEASURED: the epilogue was multiplying by
		//  0x0004BE = 1214, a value from the linear RAMP TABLE at cursor 0x71 left
		//  over from unit 1's body -- 1214/2^23 = 0.000145, an attenuation of ~6900x,
		//  which is the whole reason its output was ~1 LSB.  Its own bank is 0x90,
		//  named by its own `iw69 = 801.0.90.821', but that word only ever set m_cp.
		//  The corpus loads this pointer exactly three times and each load precedes
		//  the block that needs that bank: iw42 -> 0x70 (unit 0), iw50 -> 0x50
		//  (unit 1), iw69 -> 0x90 (the epilogue, and therefore the next frame's
		//  kernel -- which is exactly the 0x90 row 19 had to seed by hand).
		//  ⛔ STILL AGAINST K3, which proves 0x21 is NOT the implicit cursor.  One
		//  rule now replaces two hand-placed seeds, which is better, but it does not
		//  make the coupling proven.
		if (m_speculative)
			//  ★★★ §52 (mask bit 12 CLEARS this): row 25 seeds the coefficient
			//  cursor from ldptr -- and this file already records that it is
			//  "⛔ STILL AGAINST K3, which proves 0x21 is NOT the implicit cursor".
			//  K3 is FORCED; row 25 is speculative and contradicts it.
			//  MEASURED consequence: with row 25 the body's cursor sits at
			//  0x50..0x71, the DELAY-DESCRIPTOR ramps, and the body multiplies by
			//  0.0066 per stage (10^4 loss) -- while the sixteen genuine
			//  coefficients at 0xA5..0xB4 are read by NOBODY.  Without it the cursor
			//  runs continuously: kernel 0x90..0xA4 (21 cells) then body 0xA5..0xB4
			//  (16), and 21 + 16 = 37 = exactly the host's coefficient run count.
			if (!(m_specmask & 0x1000))
				m_cursor = ad;
	}
	else if (upd6383_disassembler::is_ldptrd(word))
	{
		// ldptr.d -- the DELAY-DESCRIPTOR pointer (tag-0x4C space).  PROVEN BY
		// CONSTRUCTION in both halves.  Nothing reads it yet: the DRAM words
		// that would consume the descriptor cells are not decoded, so this is a
		// register that is correctly written and honestly unused.
		m_dsc = ad;
	}
	else if (upd6383_disassembler::is_rstcur(word))
	{
		// rstcur -- resets the implicit coefficient cursor to its per-unit BASE.
		// VERIFIED on algo39 (PARAMETRIC EQ): its class-A count at the ten
		// section starts runs 0,6,12,18,24 | rstcur | 0,6,12,18,24.
		// The base is modelled as 0 because that is the unit-0 value; K4 FORCED
		// that the real base lives in a per-unit COEFFICIENT-BASE register
		// (0x00 at I-RAM 84, 0x90 at 200) that nothing in the instruction stream
		// loads, so 0 is a placeholder and is labelled as one.
		m_cursor = 0;
	}
	else if (upd6383_disassembler::hi12(word) == 0x000
			&& upd6383_disassembler::class4(word) == 2
			//  ★★★ §223 (BUILD-LANE-QUEUE item 1): AND `addr8 == 0x00'.
			//  The evidence for the `nop' reading is, in every note that carries it,
			//  evidence about the single word `000.2.00.000'.  Without this term the
			//  guard also swallowed 41 corpus words carrying a LIVE signed pointer
			//  delta (+72, -70, -75, +75 ...), 100 % of them isolated, 46 % of them
			//  immediately followed by a bit-4 STORE, and 103 of 103 MID-LADDER --
			//  zero at the end of an image, zero carrying the END bit.
			//  ★ THE NARROWER PREDICATE ALREADY EXISTS TWICE IN THIS TREE:
			//  `decoded()' in upd6383d.cpp requires `ad == 0x00', and the shipped
			//  listings render the 41 as `?word'.  The core was the only one of the
			//  three implementations that swallowed them.
			//  ★ SAFE FOR THE ADDRESS GENERATOR BY CONSTRUCTION: exec_alu() ends
			//  with the identical `(cl & 7) == 2 -> m_dp += (s8)addr8', and
			//  ptrd_a_suppressed() can never fire on a word whose lo12 is 0x000
			//  (it tests `(word & 0xfff) == 0x1c0').
			&& upd6383_disassembler::addr8(word) == 0x00
			&& upd6383_disassembler::lo12(word) == 0x000)
	{
		// nop -- INFERRED.  (The old "PROVEN BY CONSTRUCTION, writer
		// LABEL_038922" citation was WITHDRAWN: that routine emits
		// 801.0.NN.825 plus a tag-0x4C packet and never emits this word.  What
		// supports it now is that the host injects this exact pattern three
		// times in the PARAMETRIC EQ stream as the only word matching no known
		// form.)
		//
		//  ★★★★ §90: "NOP" MUST NOT MEAN "NO ADDRESSING".
		//  This word has class4 == 2, and `class4 & 7 == 2 -> p += (s8)addr8' is
		//  MEASURED (ptr_postinc, and this file's own header says "THE ADDRESS
		//  GENERATOR IS DECODED EVEN WHERE THE ALU IS NOT ... EXECUTE WHAT
		//  ADDRESSES, NEVER WHAT COMPUTES").  Swallowing the pointer move as well
		//  lets an INFERRED reading override a MEASURED one.
		//  MEASURED CONSEQUENCE: body 1's word iw213 = `000.2.BA.000' carries
		//  delta -70 and lost it, so body 1 walked -63 where the ROM sums to
		//  exactly -133 -- and that single omission displaced the whole input
		//  window by 0x46, put the kernel's audio deposit at 0x4C where no body
		//  word can address it, and left the reverb unexcited and silent.
		if (upd6383_disassembler::ptr_postinc(word) && !ptrd_a_suppressed(word))
			m_dp = u8(m_dp + s8(upd6383_disassembler::addr8(word)));
	}
	else
	{
		//  ★★★ §223 `§NG': COUNT THE WORDS THE NARROWING HANDED BACK.
		//  A narrowing whose fired count is zero is UNTESTED, not inert, so this
		//  runs unconditionally and is printed unconditionally.  By construction
		//  `addr8 != 0x00' on every word that gets here through this shape: the
		//  guard above claims `addr8 == 0x00' and nothing else in the ladder
		//  matches `hi12 == 0x000 && class4 == 2 && lo12 == 0x000'.
		if (upd6383_disassembler::hi12(word) == 0x000
				&& upd6383_disassembler::class4(word) == 2
				&& upd6383_disassembler::lo12(word) == 0x000)
		{
			m_ng_n++;
			u32 q = 0;
			for (; q < m_ng_slots; q++) if (m_ng_iw[q] == m_cur_iw) break;
			if (q == m_ng_slots && m_ng_slots < 16)
			{ m_ng_iw[q] = m_cur_iw; m_ng_slots++; }
			if (q < 16) m_ng_cnt[q]++;
		}
		exec_alu(word);     // the lo12 routing / hi12[3:1] operation decode
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
			// AN UNDECODED WORD IS ALWAYS ON THE WORKLIST -- that is what this
			// device is for -- but it may still have an ADDRESSING effect that is
			// decoded, and skipping that was corrupting the words that DO execute.
			// See exec_addressing_only().  Bit 4 (= store the accumulator to
			// mem[ptr]) is still NOT acted on outside the K6 twelve: one bit of a
			// 36-bit word is not a decode, and performing half a word is how a
			// draft core starts producing plausible-but-wrong results.
			trap(raw, m_pc - upd6383_disassembler::WORD_BYTES);

			const bool k6 = upd6383_disassembler::addressing_only(word);
			if (k6 || upd6383_disassembler::has_addressing(word))
			{
				exec_addressing_only(word, k6);
				m_partial_total++;
			}
			(void)cl;

			if (ending)
			{
				m_frame_done = 1;
				m_icount = 0;       // "wait for the next sample" -- SPECULATIVE
			}
			continue;
		}

		LOGMASKED(LOG_EXEC, "%010X  %s\n", raw,
				upd6383_disassembler::text(raw, int((m_pc - upd6383_disassembler::WORD_BYTES)
						/ upd6383_disassembler::WORD_BYTES)));

		exec_decoded(word);
		(void)hi; (void)cl; (void)ad; (void)lo; (void)dd;
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

	// the pointer this frame starts on -- see m_last_dp_delta in the header
	const u8 dp_at_entry = m_dp;

	// ---- PRESENT THE SAMPLES (K6) ------------------------------------------
	// The DI latches land in the two D-RAM cells the input stage reads, at
	// offsets +2 and +5 from the pointer the previous frame left.  Unconditional
	// and before the first word, because that is what the serial receivers do:
	// they do not wait to see whether the microcode is interested.
	//  ★ §54: score the PREVIOUS frame before starting this one.
	if (m_frames_run > 300000)   // ★ §54: score only AFTER the last program upload
	{                            //   (§38: all boot transients end by frame 264 002)
		const bool in_nz  = (m_in_val[0] != 0) || (m_in_val[1] != 0);
		const bool out_nz = m_frame_out_nz;
		m_trk[in_nz ? 1 : 0][out_nz ? 1 : 0]++;
		s32 &pk = in_nz ? m_out_peak_loud : m_out_peak_quiet;
		if (std::abs(m_frame_out_peak) > std::abs(pk)) pk = m_frame_out_peak;
		m_frame_out_nz = false; m_frame_out_peak = 0;
	}
	m_slotn = 0;                //  ★ §49: the pipeline ring is per-frame
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
		//
		// ★ THE "OPEN CONTRADICTION" HERE IS NOW RESOLVED, and it resolved
		// AGAINST the class reading.  This word looks like class 0xA and would
		// therefore advance the coefficient cursor -- but it is C-FORMAT, and in
		// that family bits [24:12] are ONE 13-bit immediate, so there is no
		// class4 to read.  The immediate is 2631 = 82*32 + 7, i.e. A = 82 = THIS
		// WORD'S OWN I-RAM ADDRESS (both C00 words in the machine do that, 2/2),
		// which is what a self-addressing wait looks like.  coeff_consumer() now
		// carries the C-format guard, so it is no longer a cursor consumer
		// anywhere in this device or in either disassembler.
		// (dsp/analysis/isa-adjudication.md sect. 3, k5-output-stage.md.)
		//
		// It still stops the frame here rather than executing: the ADDRESS is
		// decoded, the WAIT semantics are INFERRED, and one inferred word is not
		// a reason to let a frame's datapath run past it.
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

		const u32 prof_iw = (m_pc / upd6383_disassembler::WORD_BYTES) & 0x1ff;
		//  ★★★ SPECULATIVE, register row 23: REBASE AT THE EPILOGUE ENTRY.
		//  Measured defect: the bodies deposit at 0x07 (unit 0 = base 0x05 + 2) and
		//  0x8E (unit 1 = base 0x85 + 9), and the epilogue's five mode-1 stores
		//  execute with the pointer at 0x00 -- a cell that is never non-zero.  The
		//  walk does not carry from producer to consumer.
		//  The device already applies base = 0x05 | unit<<7 AT THE PER-UNIT CALL
		//  (DRAM_UNIT_BASE, FORCED to exist and in its value; only its SITE is open).
		//  ⛔ GUESSED: that the epilogue gets the same treatment on entry.  It is the
		//  one place in the frame that runs without a CALL and therefore never
		//  receives the rebase, which is exactly the shape of the observed defect.
		//  ★★★ ROW 23, RESHAPED: the epilogue's pointer is ONE BELOW the data.
		//  MEASURED walk: 0x46 at every slot 60..79, 0x45 at 80..81.  The bodies'
		//  live cells are 0x47/0x48/0x4B/0x4C/0x4D -- the pointer parks exactly one
		//  short of the first of them.  ⛔ GUESSED: a +1.  It is the smallest change
		//  that puts the consumer on the producer, and an off-by-one is the standing
		//  shape of this project's frame-closure residue -- but "smallest" is not
		//  "proven".
		//  ⛔ WITHDRAWN: the +1 was tried and changed nothing -- the stores still read
		//  zero at 0x47, a cell with 3.1 M non-zero writes.  So the epilogue is not
		//  merely mis-aimed by one; either it runs BEFORE the bodies deposit in the
		//  frame order, or the value it needs is not in D-RAM at all.  Two guesses
		//  in a row that a measurement cannot separate is the signal to stop.
		//  ⛔ ROW 23 (first form) WITHDRAWN.  Rebasing here moved the stores from ptr 0x00 to
		//  ptr 0x05 and they still read zero -- but it also revealed that the
		//  epilogue ARRIVES with the pointer at 0x46, immediately below the live
		//  cells 0x47/0x48/0x4B/0x4C/0x4D the bodies deposit in.  The arrival is
		//  RIGHT; the walk from there to the store words is what loses it.
		if (m_speculative && prof_iw == 60)
			m_epi_ptr_before = m_dp;
		if (m_speculative && prof_iw >= 60 && prof_iw <= 82)
			m_epi_ptr[prof_iw - 60] = m_dp;
		m_pc += upd6383_disassembler::WORD_BYTES;
		slots++;

		//  ★ the speculative gate widens what counts as executable; with
		//  m_speculative clear this is EXACTLY decoded(), bit for bit.
		const bool word_ok = upd6383_disassembler::decoded(word)
				|| (m_speculative && upd6383_disassembler::alu_decoded_speculative(word));
		//======================================================================
		//  ★★★ §109 THE STORE-SITE PROBE arms HERE, one slot at a time, and the
		//  four decode predicates are evaluated on the SAME word the machine is
		//  about to run -- so "guard 7 fires" / "guard 7 is never consulted" is a
		//  MEASUREMENT of this build, not a reading of the source.
		//  Same boot gate as §86/§98/§104 (§46: the first 420 000 frames are one
		//  contiguous boot transient and counting them puts phantoms in the census).
		//======================================================================
		m_sprobe_cur = (m_frames_run > 420000) ? sprobe_idx(u16(prof_iw)) : -1;
		if (m_sprobe_cur >= 0)
		{
			sprobe_t &sp = m_sprobe[m_sprobe_cur];
			sp.iw = u16(prof_iw);
			sp.word = raw;
			sp.n_exec++;
			sp.dp_pre = m_dp;
			sp.decoded = upd6383_disassembler::alu_decoded(raw) ? 1 : 0;
			sp.gfail = upd6383_disassembler::alu_guard_fail(raw);
			{   //  the LIVE store gate (bit 29 aware), evaluated WITHOUT touching the
				//  fired counter -- the probe must not inflate the arm's own statistic.
				const u16 phi = upd6383_disassembler::hi12(raw);
				sp.supp = ((m_specmask & 0x20000000)
						? bool((phi & upd6383_disassembler::HI_B7)
						       && upd6383_disassembler::hi_f31(phi) != 2)
						: upd6383_disassembler::st_suppressed(raw)) ? 1 : 0;
			}
			sp.g7 = upd6383_disassembler::guard7_would_refuse(raw) ? 1 : 0;
			sp.path = !word_ok
					? (upd6383_disassembler::addressing_only(raw)
					   || upd6383_disassembler::has_addressing(raw) ? 2 : 3)
					: (upd6383_disassembler::decoded(raw) ? 0 : 1);
			//  ★ the cross-frame LFO PHASE witness: what the body's LFO block finds
			//  resident in the phase cell when it arrives.  A free-running ramp shows
			//  a DIFFERENT value on consecutive frames; a reset one shows the same.
			if (prof_iw == 89 && m_lfo_phase_n < 8)
			{
				m_lfo_phase_frame[m_lfo_phase_n] = u32(m_frames_run);
				m_lfo_phase[m_lfo_phase_n++] =
						s32(util::sext(m_dram.read_dword(m_dp) & 0xffffff, 24));
			}
			//  ★ §119 RULE-8: sample the two DOWNSTREAM cells on the same frames.
			if (prof_iw == 94 && m_lfo_dst_n < 8)
			{
				m_lfo_dst_dp[m_lfo_dst_n] = m_dp;
				m_lfo_dst[m_lfo_dst_n++] =
						s32(util::sext(m_dram.read_dword(m_dp) & 0xffffff, 24));
			}
			if (prof_iw == 95 && m_lfo_tap_n < 8)
			{
				m_lfo_tap_dp[m_lfo_tap_n] = m_dp;
				m_lfo_tap[m_lfo_tap_n++] =
						s32(util::sext(m_dram.read_dword(m_dp) & 0xffffff, 24));
			}
		}
		if (!word_ok)
		{
			// UNDECODED -- and that is ONE state with TWO sub-cases, not two
			// states.  Either way the word's arithmetic is unknown, so it goes on
			// the worklist and the frame's return is discarded (`clean' below).
			// What differs is how much of it we can honestly perform:
			//
			//   PARTIAL   its ADDRESSING is decoded (pointer post-increment,
			//             coefficient cursor) and is executed.  That is not a
			//             favour to the word -- it is what makes the DECODED words
			//             around it address the right cells.
			//   TRAP      nothing at all is known, nothing at all is done.
			//
			// Both are counted on the worklist because both block the frame.
			if (traps + partials == 0)
				order_before = slots - 1;   // this word is already counted in `slots'
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

			const bool k6 = upd6383_disassembler::addressing_only(word);
			if (k6 || upd6383_disassembler::has_addressing(word))
			{
				partials++;
				m_partial_total++;
				exec_addressing_only(word, k6);
			}
			else
			{
				traps++;
			}
			(void)cl;
		}
		else
		{
			LOGMASKED(LOG_EXEC, "%010X  %s\n", raw,
					upd6383_disassembler::text(raw, int(pc / upd6383_disassembler::WORD_BYTES)));

			// ONE implementation, shared with execute_run().  It used to be a
			// hand-copied second ladder; two copies of a decode is exactly the
			// drift this pass exists to remove.
			m_mul_issued = false;
			//  ★ §49: deliver any delay datum scheduled to land on THIS slot.
			if (m_speculative && (m_specmask & 0x400))
			{
				const u32 k = m_slotn & 7;
				if (m_dr_pipe_v[k])
				{
					m_dr = m_dr_pipe[k];
					//  ★★★ §50 (mask bit 11): LAND IT IN tempA TOO.
					//  §49 delivered 32 986 560 data into m_dr and NOTHING changed,
					//  because this program contains exactly ONE word naming
					//  SRC 0x0B -- 1.0 consumption per frame against ~20.8 reads.
					//  So m_dr cannot be where the ladder takes its feedback.
					//  dram-datapath.md item H says where: "the multiply at slot 5
					//  reads SRC 0x19 = tempA and the read is at slot 4 with nothing
					//  between them", i.e. a read's datum reaches the multiplicand
					//  through tempA, one slot later.
					if (m_specmask & 0x800)
					{ m_ta = m_dr_pipe[k] & 0xffffff; pv_wr_ta(m_ta); }   // ★ §221 §E1
					m_dr_pipe_v[k] = false;
					m_dr_landed++;
				}
			}
			m_slotn++;
			m_cur_word = raw;
			m_cur_iw = u16(pc / upd6383_disassembler::WORD_BYTES);
			//  ★ §191: the probe belongs HERE, on the per-word dispatch, not in
			//  exec_addressing_only() -- that function is only reached from the k6
			//  path (:1708), so bit-11 words never entered it and the first run
			//  logged ZERO sites.  LEDGER rule 10 applied to my own instrument:
			//  I placed it in the function whose NAME matched the concept rather
			//  than on the path the words take.
			//  ★★★ §201: RESET THE DESCRIPTOR INDEX AT EACH BODY ENTRY.
			//  adjudication-round5.md §1 FORCES the IDENTITY map -- "the k-th class-1
			//  format-escape consumer takes the k-th descriptor cell of ITS OWN
			//  BODY's block".  `m_delay_ix' is frame-global and reset only at frame
			//  end (:4622), so body 1 continues body 0's count: §200 MEASURED the
			//  indices in use as 0x29 0x2B 0x2D 0x2F 0x31 and 0x33 (1 135 149 hits)
			//  where unit 1 should be drawing its own block -- "no delay line at all"
			//  (§198 gap 3), confirmed by frames_since_written 0..0 on every line.
			//  ⚠ The u64 spec mask is EXHAUSTED; env gate, as §104/§200 did.
			if (m_bodyix && (m_cur_iw == 84 || m_cur_iw == 200))
			{ m_delay_ix = 0; m_bodyix_n++; }
			//  ★★★ §203 (§198 gap #4): `C40.1.80.000' MUST CONSUME A DESCRIPTOR CELL.
			//  r3-delaydram.md §6.1 FORCES it -- all 8 exact solutions require it --
			//  and it is verified arithmetically from the .dsm: 28 non-C-format
			//  consumers + 4 C-format = 32 = n.  The delay path excludes C-format, so
			//  the cursor runs FOUR SHORT inside every reverb.
			//  round5 §1's IDENTITY map counts consumers in PROGRAM ORDER, so the
			//  advance belongs here, at the dispatch, alongside §201's reset.
			//  ⚠ u64 spec mask exhausted; env gate UPD6383_CFMTIX.
			if (m_cfmtix && upd6383_disassembler::c_format(raw)
					&& upd6383_disassembler::class4(raw) == 1)
			{ m_delay_ix++; m_cfmtix_n++; }
			b11_probe(raw);
			f31_probe(raw);         // ★ §193
			//  ★★★ §153: `lo12 == 0x44C' APPLIES THE MODULATION OFFSET (§152).
			//  Taken as the accumulator in DATUM units, i.e. a signed sample count,
			//  because the depth the idiom loads is a sample count (ENHANCER's
			//  15435 = 350 ms).  ⚠ This is the SIMPLEST defensible transport and it
			//  is deliberately NOT scaled to make any particular excursion come out:
			//  the tap-address census below MEASURES the excursion, so a wrong
			//  quantity shows up as a wrong range instead of being fitted away.
			if (m_speculative && (m_specmask & (1ull << 60))
					&& upd6383_disassembler::lo12(word) == 0x44c)
			{
				m_tapmod = s32(acc_to_datum(
						(m_specmask & 0x4000) && m_cur_unit1 ? m_accb : m_acc));
				m_tapmod_n++;
				//  ★ §157 per-SLOT census -- no pooling, so a constant reads range 0.
				if (m_cur_iw < 384)
				{
					const u16 q = m_cur_iw;
					if (!m_tapslot_seen[q])
					{ m_tapslot_seen[q] = true; m_tapslot_lo[q] = m_tapslot_hi[q] = m_tapmod; }
					else { if (m_tapmod < m_tapslot_lo[q]) m_tapslot_lo[q] = m_tapmod;
					       if (m_tapmod > m_tapslot_hi[q]) m_tapslot_hi[q] = m_tapmod; }
				}
			}
			//  ★ §104: the pointer and the cell UNDER it, sampled BEFORE the word
			//  runs.  This is the RESIDENCY of the cell the word is about to read,
			//  which is a different question from §86/§96's census of what gets
			//  WRITTEN to a cell (a cell can be written with audio once and with a
			//  constant three times and still be graded "input-dependent" there).
			const u8  s104_dp  = m_dp;
			const s32 s104_mem = s32(util::sext(m_dram.read_dword(m_dp) & 0xffffff, 24));
			exec_decoded(word);
			if (m_trace_armed && m_trace_n < 400)
			{   // ★★★ THE TIME-ORDERED FRAME TRACE -- execution order, not maxima
				trace_t &t = m_trace[m_trace_n++];
				t.iw = u16(prof_iw); t.word = raw; t.dp = m_dp;
				t.mem = s32(util::sext(m_dram.read_dword(m_dp) & 0xffffff, 24));
				t.acc = util::sext(m_acc, 44); t.p = s64(util::sext(m_p, 44));
				//  ★ tempB and the cursor: sect. 12.3 pinned the death to a class-A
				//  multiply with SRC 0x1A (tempB), so P = coef * tempB and one of the
				//  two is empty.  These two columns say which.
				t.ta = s32(util::sext(m_ta, 24)); t.tb = s32(util::sext(m_tb, 24));
				t.cur = u8(m_cursor); t.coef = m_cram.read_dword(m_cursor) & 0xffffff;
				t.l = m_last_l; t.mul = m_mul_issued;
				t.accb = util::sext(m_accb, 44); t.u1 = m_cur_unit1;   // ★ §65
			}
			if (prof_iw <= 24 && m_curprof_n < 25)
			{   // ★ which C-RAM cell does each kernel slot consume?
				m_curprof[prof_iw] = m_cursor;
				m_curprof_seen[prof_iw] = 1;
				if (std::abs(s64(m_p)) > std::abs(m_pprof[prof_iw])) m_pprof[prof_iw] = s64(m_p);
			}
			//  ★ §81: probes -- header exit (iw 12), body-0 end (iw 152),
			//  body-1 entry (iw 201), body-1 end (iw 332).
			if (m_frames_run > 420000)
			{
				int p = -1;
				switch (prof_iw) {
				case 12:  p=0; break;   case 20:  p=1; break;   case 30: p=2; break;
				case 40:  p=3; break;   case 90:  p=4; break;   case 152: p=5; break;
				case 210: p=6; break;   case 332: p=7; break;
				//  ★ §102: the DEATH WINDOW.  iw30 still DIFFERS and iw40 is a
				//  constant, and the window holds FOUR `f31 = 0' words -- acc <- P,
				//  which discards the accumulator by design.
				//  ⚠ THESE PROBES ARE POST-EXECUTION.  exec_decoded() is called
				//  above; probe `iwN' is the accumulator AFTER slot N ran.  Reading
				//  them as pre-execution puts the blame one slot early and made iw31
				//  (a C-format word) look like the culprit when it is iw32.
				case 31:  p=8; break;   case 34:  p=9; break;
				case 36:  p=10; break;  case 39:  p=11; break; }
				if (p >= 0)
				{
					const s64 v = util::sext(m_cur_unit1 ? m_accb : m_acc, 44);
					const bool nz = (m_in_val[0] != 0) || (m_in_val[1] != 0);
					s64 &lo = nz ? m_pr_min[p] : m_pq_min[p];
					s64 &hi2 = nz ? m_pr_max[p] : m_pq_max[p];
					if (v < lo) lo = v;
					if (v > hi2) hi2 = v;
				}
			}
			if (prof_iw < 384)
			{
				const s64 a = util::sext(m_acc, 44);
				m_slotseen[prof_iw]++;
				if (std::abs(a) > std::abs(m_accprof[prof_iw])) m_accprof[prof_iw] = a;
			}
			//  ★ §104: the full per-slot quiet/loud split (see upd6383.h).  Same
			//  arming threshold and the same quiet/loud predicate as §81, so the two
			//  instruments are directly comparable; §81's 12 probes are a subset of
			//  these 384 and act as the calibration.
			if (m_frames_run > 420000 && prof_iw < 384)
			{
				const s64  a  = util::sext(m_cur_unit1 ? m_accb : m_acc, 44);
				const s32  lv = m_last_l;
				const bool nz = (m_in_val[0] != 0) || (m_in_val[1] != 0);
				m_sp_dp[prof_iw] = s104_dp;
				m_sp_word[prof_iw] = raw;
				if (nz)
				{
					if (m_sp_nr[prof_iw]++ == 0)
					{ m_sp_accr_lo[prof_iw] = m_sp_accr_hi[prof_iw] = a;
					  m_sp_memr_lo[prof_iw] = m_sp_memr_hi[prof_iw] = s104_mem;
					  m_sp_lr_lo[prof_iw] = m_sp_lr_hi[prof_iw] = lv; }
					else
					{ if (a < m_sp_accr_lo[prof_iw]) m_sp_accr_lo[prof_iw] = a;
					  if (a > m_sp_accr_hi[prof_iw]) m_sp_accr_hi[prof_iw] = a;
					  if (s104_mem < m_sp_memr_lo[prof_iw]) m_sp_memr_lo[prof_iw] = s104_mem;
					  if (s104_mem > m_sp_memr_hi[prof_iw]) m_sp_memr_hi[prof_iw] = s104_mem;
					  if (lv < m_sp_lr_lo[prof_iw]) m_sp_lr_lo[prof_iw] = lv;
					  if (lv > m_sp_lr_hi[prof_iw]) m_sp_lr_hi[prof_iw] = lv; }
				}
				else
				{
					if (m_sp_nq[prof_iw]++ == 0)
					{ m_sp_accq_lo[prof_iw] = m_sp_accq_hi[prof_iw] = a;
					  m_sp_memq_lo[prof_iw] = m_sp_memq_hi[prof_iw] = s104_mem;
					  m_sp_lq_lo[prof_iw] = m_sp_lq_hi[prof_iw] = lv; }
					else
					{ if (a < m_sp_accq_lo[prof_iw]) m_sp_accq_lo[prof_iw] = a;
					  if (a > m_sp_accq_hi[prof_iw]) m_sp_accq_hi[prof_iw] = a;
					  if (s104_mem < m_sp_memq_lo[prof_iw]) m_sp_memq_lo[prof_iw] = s104_mem;
					  if (s104_mem > m_sp_memq_hi[prof_iw]) m_sp_memq_hi[prof_iw] = s104_mem;
					  if (lv < m_sp_lq_lo[prof_iw]) m_sp_lq_lo[prof_iw] = lv;
					  if (lv > m_sp_lq_hi[prof_iw]) m_sp_lq_hi[prof_iw] = lv; }
				}
				//  ★★★ §213: the same split for `P' and `tempA'.  §104 shows tempA
				//  only at the slots that SOURCE it (`L') and never shows P at all,
				//  so the kernel's send chain -- delay-read -> tempA -> P -> acc --
				//  is invisible to it between the hops.  Sampled AFTER the slot, on
				//  the same predicate, so the tables line up row for row.
				const s64 pv = util::sext(m_p, 44);
				const s32 tv = s32(util::sext(m_ta, 24));
				m_s213_pwm[prof_iw] |= (1u << (m_pw & 31));
				if (nz)
				{
					if (m_s213_nr[prof_iw]++ == 0)
					{ m_s213_pr_lo[prof_iw] = m_s213_pr_hi[prof_iw] = pv;
					  m_s213_tar_lo[prof_iw] = m_s213_tar_hi[prof_iw] = tv; }
					else
					{ if (pv < m_s213_pr_lo[prof_iw]) m_s213_pr_lo[prof_iw] = pv;
					  if (pv > m_s213_pr_hi[prof_iw]) m_s213_pr_hi[prof_iw] = pv;
					  if (tv < m_s213_tar_lo[prof_iw]) m_s213_tar_lo[prof_iw] = tv;
					  if (tv > m_s213_tar_hi[prof_iw]) m_s213_tar_hi[prof_iw] = tv; }
				}
				else
				{
					if (m_s213_nq[prof_iw]++ == 0)
					{ m_s213_pq_lo[prof_iw] = m_s213_pq_hi[prof_iw] = pv;
					  m_s213_taq_lo[prof_iw] = m_s213_taq_hi[prof_iw] = tv; }
					else
					{ if (pv < m_s213_pq_lo[prof_iw]) m_s213_pq_lo[prof_iw] = pv;
					  if (pv > m_s213_pq_hi[prof_iw]) m_s213_pq_hi[prof_iw] = pv;
					  if (tv < m_s213_taq_lo[prof_iw]) m_s213_taq_lo[prof_iw] = tv;
					  if (tv > m_s213_taq_hi[prof_iw]) m_s213_taq_hi[prof_iw] = tv; }
				}
			}
			(void)hi; (void)cl; (void)ad; (void)lo; (void)dd;
		}

		//  ★ §109: the pointer AFTER the slot -- the second half of the pre/post
		//  question, read from the machine rather than from the source.
		if (m_sprobe_cur >= 0)
		{
			m_sprobe[m_sprobe_cur].dp_post = m_dp;
			m_sprobe_cur = -1;
		}

		// ---- the transfer, AFTER the word has done its datapath work -------
		if (tagged)
		{
			if (m_sp == 0)
			{
				const bool unit1 = (upd6383_disassembler::addr8(raw) != 0x0e);
				m_stack[m_sp++] = m_pc;     // return to the word after this one
				m_pc = (unit1 ? UNIT1_ENTRY : UNIT0_ENTRY)
						* upd6383_disassembler::WORD_BYTES;

				// ★ THE PER-UNIT D-RAM REBASE.  base = 0x05 | (unit << 7).
				// FORCED to exist and forced in its VALUE; see DRAM_UNIT_BASE in
				// the header for the three-step derivation and for the one thing
				// that is NOT forced -- the site, which is why this is written
				// here (at the CALL) rather than as a word decode.  No word gains
				// a semantic from it and no word stops trapping: it is the frame
				// SEQUENCER's model, not the ISA's, exactly like the call itself.
				//
				// It is the missing absolute reload that dsp/analysis/
				// retraction-sweep.md P1/P13 re-opened -- "NOTHING loads m_dp".
				// WITHDRAWN with it: the +121 closure residue as an open defect
				// -- it was the same phenomenon, and one change answers both.
				//  ★★★ §108 SPECULATIVE (mask bit 27): the per-unit base is 0x06,
				//  not 0x05.  From reconstructing what CHORUS must compute at
				//  iw84..92, and it is OVER-DETERMINED -- one parameter, two
				//  independently measured symptoms:
				//
				//   (a) THE LFO PHASE CANNOT RAMP.  lfo-ramp.md §1 names iw89/90/91
				//       as the LFO block and §11 records "the block stores the phase
				//       back unchanged -- no ramp".  The §104 census shows why: the
				//       phase cell reads 4194304 at iw89/90/91 but 4194304+57 at
				//       iw92, so the body DOES increment it (by 57; lfo-ramp.md
				//       predicts 114 for CHORUS -- the familiar factor of 2) and it
				//       is reset before the next frame.  Reset to 0x400000, which is
				//       exactly what kernel iw32 stores.  Under base 0x05 the phase
				//       lands on 0x07, INSIDE kernel A's measured 01..07 window.
				//       Under base 0x06 it lands on 0x08, outside it, and can ramp.
				//   (b) THE BODY READS AN EMPTY INPUT CELL.  iw85 reads base+0, and
				//       base+0 = 0x05 is measurably 0..0 in every frame while the
				//       kernel's audio is at 0x06/0x07 (§86).  Under base 0x06 the
				//       read lands on the audio.
				//
				//  ⚠ THIS CONTRADICTS DRAM_UNIT_BASE, WHICH IS LABELLED FORCED, and
				//  §94 measured both units reading base+0 / base+2 at 0x05/0x07 and
				//  0x85/0x87.  So this is a DIRECT CHALLENGE to a forced reading and
				//  is gated OFF by default.  It also moves the frame closure: the
				//  arithmetic 0x85-133-1 = 0xFF, 0xFF+6 = 0x05 becomes 0x86-133-1 =
				//  0x00, 0x00+6 = 0x06, so the closure residue MUST be re-measured
				//  rather than assumed.
				//
				//  ★ PREDICTION, stated before the run: (a) fires -- the phase cell
				//  advances across frames.  (b) does NOT fire on its own, because
				//  iw85's ACTION 0x0D is still undecoded (§107) and routes the value
				//  nowhere; §106 already showed that filling base+0 alone changes
				//  nothing.  If (b) DOES fire, ACTION 0x0D is doing more than §106
				//  concluded and that is the more valuable outcome.
				//
				//  ⛔⛔ REFUTED BY MEASUREMENT, AND THE REFUTATION IS THE USEFUL PART.
				//  The gate fires (dp is 0x06 at iw84/85 and 0x08 at iw89..92) and
				//  EVERY value is bit-identical, phase still pinned at 4194304.
				//  Because the whole frame moves together: kernel A's window shifted
				//  from 01..07 to 02..08, so iw32 writes 0x08 -- the LFO phase cell
				//  again.  THE BASE AND THE KERNEL'S WINDOW ARE COUPLED THROUGH THE
				//  FRAME CLOSURE: the kernel's walk starts where the previous frame
				//  closed, and the closure is downstream of the base, so both move
				//  as one.
				//
				//  ★★★ CONSEQUENCE, and it retires a whole family of attempts: NO
				//  value of DRAM_UNIT_BASE can fix the deposit/pickup collision,
				//  because the collision is in the RELATIVE geometry and the base
				//  cancels out of it.  That is why §105's off-by-one framing was
				//  doomed and why §106's mirror changed nothing.  What CAN change the
				//  relative geometry is a per-word ADDRESSING decode: some word's
				//  addr8 contribution to the walk, or iw30/iw32's store target, or
				//  the body's LFO block not really sitting at base+2.  Look there,
				//  not at the anchor.
				//
				//  Kept gated OFF and implemented, so the refutation is reproducible
				//  rather than a claim.  ⚠ NOTE the PER-UNIT REBASE audit still
				//  prints DRAM_UNIT_BASE rather than this gated value, so its
				//  "already delivered 0x05" percentages are stale whenever bit 27 is
				//  on -- do not read them under the gate.
				const u8 dub = (m_speculative && (m_specmask & 0x8000000))
						? u8(DRAM_UNIT_BASE + 1) : DRAM_UNIT_BASE;
				const u8 base = u8(dub | (unit1 ? DRAM_UNIT_STRIDE : 0));

				// DIAGNOSTIC, not a criterion.  For unit 1 the rebase is forced
				// to do work (net(body0) takes 8 values, so no walk can deliver
				// 0x85).  For unit 0 the closure model says the header walk from
				// X = 0xFF ALREADY delivers 0x05 -- so applying it there should
				// be a NO-OP, and "should be" is not "is".  These two counters
				// measure it every frame instead of assuming it, and they are
				// what would show the unit-0 half being load-bearing (which
				// would mean the closure arithmetic is wrong somewhere).
				if (unit1)
				{
					m_calls_u1++;
					if (m_dp == base) m_rebase_agreed_u1++;
				}
				else
				{
					m_calls_u0++;
					if (m_dp == base) m_rebase_agreed_u0++;
				}

				m_dp = base;
				m_cur_unit1 = unit1;    // ★ row 27: who is executing
				//  ★★★★ §73 SPECULATIVE (mask bit 18): SEED THE COEFFICIENT CURSOR
				//  WITH THE PER-UNIT BASE AT THE CALL.
				//  cram-unit-base.md item A is MEASURED over 91 programs / 1546
				//  class-A words: "The C-RAM cursor is UNIT-RELATIVE: base 0x00 for
				//  unit 0, 0x90 for unit 1."  Unit 1's twelve reverbs resolve 33/33
				//  at 0x90 and 0/33 at 0x00, keys running 0x90..0xB4 and NOTHING
				//  below 0x90; item E rejects the tempting global "always add 0x90"
				//  79/79 on unit 0.  The tools count k from ZERO within each unit's
				//  body and add the base -- i.e. the cursor is reset per unit, not
				//  aimed by the in-program ldptr, whose 0x50/0x70 payloads land in
				//  the never-written ramp bank (§72: 0 writes from 0 algorithms).
				//  ⛔ §130: THIS GATE WAS DOUBLE-BOOKED ON BIT 18 with §113
				//  (`SRC 0x11 = mem[ptr]', upd6383.cpp:2151) -- two unrelated readings
				//  behind one mask bit, so neither could ever be A/B'd alone.  §129's
				//  first rebase run turned BOTH on and was confounded: §121 had
				//  deliberately removed §113 because it destroys the audio deposit
				//  (iw11 becomes a self-copy of mem[0x05]).  The rebase moves to its
				//  own bit 38; bit 18 stays §113's alone.
				//  ★ The miss was a grep bug worth recording: `0x40000\b' does not
				//  match `0x40000u', so the second site did not show up in the audit
				//  that checked this bit was free.  Match the bit, not the spelling.
				if (m_speculative && (m_specmask & 0x4000000000ull))
				{
					m_cursor = unit1 ? 0x90 : 0x00;
					m_cursor_rebase_n++;
				}

				//  ★★★ §133 THE INJECTOR.  Write the trial's stimulus into the two
				//  candidate source cells at the unit-0 CALL.  This is deliberately
				//  DOWNSTREAM of the `iw45'/`iw32' SRC 0x08 clobber, which is why the
				//  decode does not have to wait for that fix: whatever the kernel did
				//  to 0x05/0x0F, the body sees these two values.
				//  ⚠ It also replaces a DC stimulus with a non-repeating one.  With
				//  the injector off, cell 0x05 is railed at 0x7FFFFF every loud frame
				//  (§129), and a DC input drives the state cells to a fixed point
				//  where the shift identity mem[B+1] == mem[B+0] holds TRIVIALLY --
				//  a criterion that cannot fail.  The distinct-value count below is
				//  the guard that catches exactly that.
				if (m_bx_on && m_bx_armed && !unit1)
				{
					m_dram.write_dword(0x05, bx_stim(m_bx_tframe, false));
					m_dram.write_dword(0x0f, bx_stim(m_bx_tframe, m_bx_distinct));
					pk_write(0x05, bx_stim(m_bx_tframe, false), 8, false, m_cur_iw);
					pv_wr_dram_tag(0x05, bx_stim(m_bx_tframe, false), E1_PV_IN);
					pv_wr_dram_tag(0x0f, bx_stim(m_bx_tframe, m_bx_distinct), E1_PV_IN);
					m_bx_inj_n++;
				}

				//  ★★★ SEED THE COEFFICIENT CURSOR AT THE CALL, register row 24.
				//  MEASURED defect: the reverb dies at I-RAM 302, a class-A multiply
				//  with SRC 0x1A, because P = coef * tempB and the COEFFICIENT is
				//  zero -- tempB holds 5 872 025, a healthy 0.70 of full scale.  The
				//  cursor there is 0xCE, OUTSIDE every C-RAM run the host writes
				//  (0x50..0xB4 and 0x00..0x13): it free-ran past the end of the bank.
				//
				//  The kernel loads each unit's bank immediately before its CALL --
				//  iw42 `801.0.70.821' -> 0x70 for unit 0, iw50 `801.0.50.821' ->
				//  0x50 for unit 1 -- and those are the two banks the coefficient
				//  stream fills.  Applying that pointer to the cursor at the CALL is
				//  the same shape as the D-RAM rebase directly above.
				//
				//  ⛔ GUESSED, and against a FORCED result: K3 proves selector 0x21
				//  loads a C-RAM POINTER that is *NOT* the implicit cursor.  This
				//  couples them anyway, on the functional grounds that a body must
				//  read its own bank and nothing else re-seeds the cursor.  If K3 is
				//  right the coupling is wrong and some other word does this job.
				//  ⛔ ROW 24 RETIRED: subsumed by row 25 -- iw42/iw50 now seed the
				//  cursor themselves, before the call rather than at it.
			}
			else
			{
				// NO rebase on the RETURN.  The closure arithmetic requires the
				// body's exit pointer to survive into the header words that
				// follow it (delta(50..58) = +2 is measured on top of whatever
				// body 0 left), and net(body0) varying over 8 values is only a
				// constraint at all because those words see it.
				m_pc = m_stack[--m_sp];
			m_cur_unit1 = false;    // ★ row 27: back in the kernel/epilogue
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

	//  ★★★ THE KERNEL'S COEFFICIENT CURSOR -- SPECULATIVE, register row 19.
	//  MEASURED: the cursor was FREE-RUNNING across frames (it had drifted to 0x77
	//  and kept climbing), so a fixed program read different coefficients every
	//  frame -- which cannot be right.  It reads a LINEAR RAMP there, i.e. a lookup
	//  table, not its own bank.
	//
	//  WHY 0x90.  The corpus loads the C-RAM POINTER exactly three times and K3
	//  names 0x70/0x50/0x90 as three of the four structural bases of the host's
	//  C-RAM map:
	//      kernel iw42  801.0.70.821  -> 0x70   the unit-0 body's bank
	//      kernel iw50  801.0.50.821  -> 0x50   the unit-1 body's bank
	//      epilogue iw69 801.0.90.821 -> 0x90   ★ the LAST load of the frame, so it
	//                                             is what the NEXT frame's kernel
	//                                             inherits
	//  and the coefficient stream fills [0x90..0xAD] with 30 values, unclaimed by
	//  either body and enough for the kernel's 23 slots.
	//
	//  ⛔ GUESSED: that the implicit cursor should be RE-SEEDED here at all.  K3
	//  proves 0x21 loads a C-RAM POINTER that is NOT the implicit cursor, and the
	//  only `rstcur' in the corpus is in PARAMETRIC EQ's body -- so what resets the
	//  cursor per frame is genuinely unknown.  Seeding it from the epilogue's
	//  payload is the reading that makes a fixed program read fixed coefficients.
	//  ⛔ ROW 19 RETIRED: subsumed by row 25 -- the epilogue's own iw69 ldptr now
	//  leaves the cursor at 0x90, which is what this line was seeding by hand.

	if (m_trace_armed && !m_trace_done)
	{   // one frame only
		m_trace_done = true;
		m_trace_armed = false;
	}
	m_delay_ix = 0;         // ★ SPECULATIVE: descriptor cells are consumed in
	                        //   program order, restarting every frame.
	bx_frame_end();         // ★ §133, after the frame has fully executed
	//==========================================================================
	//  ★★★ §164 PROBE (read-only, always on): DOES ANY D-RAM CELL RAMP?
	//
	//  §112's two-sided criterion is *"the phase stops being reset and RAMPS"*
	//  vs *"the phase stays pinned and nothing else should move either"*, and
	//  there is no instrument that can tell those apart.  This is it.
	//
	//  ⚠ min/max ALONE IS NOT ENOUGH and this is the §137 trap in a new place: a
	//  cell that is pinned at 0x400000 and a cell that takes two values a frame
	//  apart both report a range.  So also count the frames in which the cell
	//  CHANGED from the previous frame.  A pinned cell changes 0 times; a ramp
	//  changes essentially every frame.  The two numbers together cannot be
	//  satisfied by a constant, which is what makes this a test.
	//  ★ The NULL, stated in advance: under the shipped default every cell in
	//  0x00..0x1F must report chg = 0 or a tiny startup count.
	//  ★ §179: sweep ALL 256 cells, not 0x00..0x1F.  D-RAM is map(0x00,0xff) and
	//  §176 censused one EIGHTH of it -- while the owning pointer note measures the
	//  operand origin at 0x70/0x50 and this device ships DRAM_UNIT_BASE = 0x05.
	//  If the live data sits near 0x50..0x8B then §176's window was an empty corner.
	for (u32 i = 0; i < 0x100; i++)
	{
		const s32 v = s32(util::sext(m_dram.read_dword(i) & 0xffffff, 24));
		if (!m_frames_run) { m_rampmin[i] = m_rampmax[i] = v; }
		else
		{
			if (v < m_rampmin[i]) m_rampmin[i] = v;
			if (v > m_rampmax[i]) m_rampmax[i] = v;
			if (v != m_rampprev[i]) m_rampchg[i]++;
		}
		//  ★★★ §196: COUNT LFO WRAP EVENTS.  §114 §3 flags that the wrap modulus is
		//  exactly half -- mod 2^24 where `lfo-ramp.md' item C anchors mod 2^23 --
		//  and the two give LFO periods of 147 169 and 73 584 frames, i.e. 0.2997 Hz
		//  and 0.5993 Hz.  item C anchors 0.5993 Hz across 29 LFO blocks in 16
		//  programs with NINE DISTINCT INCREMENTS, so it is not one coincidence.
		//  ★ A wrap is a large NEGATIVE step in an otherwise rising ramp.  Counting
		//  them in the phase cell discriminates the two moduli 2:1 with NO gate
		//  change and no implementation -- a pure measurement against an
		//  independently derived number.
		if (m_frames_run && v < m_rampprev[i] && (m_rampprev[i] - v) > 0x400000)
			m_rampwrap[i]++;
		m_rampprev[i] = v;
	}
	m_frames_run++;
	m_last_slots = slots;
	m_last_traps = traps;
	m_last_partials = partials;

	// FRAME CLOSURE.  Signed net displacement of the D-RAM operand pointer, mod
	// 256 mapped to [-128, 127].
	//
	// ★ THIS MEASUREMENT CHANGED MEANING TWICE.  While only the executing words
	// moved the pointer, a non-zero residue mostly measured OUR COVERAGE.  Once
	// EVERY word's post-increment was performed it measured THE MACHINE -- and
	// it read +121 on 1 130 880 of 1 130 880 frames.  ★ THAT NUMBER WAS NOT AN
	// ALU DEFECT AND IT IS NOW GONE: it was the arithmetic of walking ONE pointer
	// straight through a machine that REBASES it per unit (DRAM_UNIT_BASE).  With
	// the rebase performed, 0x85 - 133 - 1 = 0xFF and 0xFF + 6 = 0x05, so the
	// walk returns to where it started and the residue is 0.
	//
	// The CRITERION is still only CONSISTENT, not FORCED (retraction-sweep.md
	// P10): it used to say "and it is FORCED that it must be", on the strength of
	// K6 finding 5, which dsp/analysis/closure-pointer.md item F FALSIFIED -- 79
	// of 79 unit-0 bodies enter the I/O window, not 0 of 38.  What changed is the
	// MEASUREMENT, not the entitlement to call a non-zero value a defect.  A
	// residue of 0 is therefore evidence FOR the rebase, not proof of it; the
	// proof of the rebase is the ROM (see DRAM_UNIT_BASE), and this is its
	// strongest live consequence.  See dump_frame_report().
	//
	// AND IT STILL CANNOT SUCCEED FOR FREE.  A complete frame closes only if its
	// ENTRY pointer was 0xFF, i.e. only if the PREVIOUS frame also completed --
	// the frames that hit the slot cap or overran I-RAM leave the pointer
	// anywhere, and the complete frame that follows one of those does NOT close.
	// So a run with capped frames in it must report a shortfall, and if it ever
	// reports 100.00 % on a run that also reports capped frames, this counter has
	// stopped measuring anything.
	//
	// COUNTED ONLY ON COMPLETE FRAMES.  A frame that hit the slot cap or ran off
	// the end of I-RAM never finished its program -- at boot, before the host has
	// uploaded anything, I-RAM is all zeros -- so its residue is not a
	// measurement of anything.  Mixing those in made the run-wide spread read
	// `VARIES' when the quantity that matters is dead constant.
	m_last_dp_delta = s32(s8(u8(m_dp - dp_at_entry)));
	//  ★ §38: place the non-completing frames in time, exactly as §37 did for the
	//  closure residue -- a boot transient and a steady-state fault look identical
	//  in a run-wide total.
	{
		const u32 b = u32((m_frames_run * 16) / 1900000) < 16
				? u32((m_frames_run * 16) / 1900000) : 15;
		if (overrun)
		{
			m_ovr_bucket[b]++;
			if (!m_ovr_first) m_ovr_first = m_frames_run;
			m_ovr_last = m_frames_run;
			if (slots < m_ovr_slots_min) m_ovr_slots_min = slots;
			if (slots > m_ovr_slots_max) m_ovr_slots_max = slots;
		}
		else if (capped)
		{
			m_cap_bucket[b]++;
			if (!m_cap_first) m_cap_first = m_frames_run;
			m_cap_last = m_frames_run;
			if (slots < m_cap_slots_min) m_cap_slots_min = slots;
			if (slots > m_cap_slots_max) m_cap_slots_max = slots;
		}
	}
	if (hit_wait)
	{
		m_in_base_hist[dp_at_entry]++;
		m_frames_dp_measured++;
		if (m_last_dp_delta == 0)
			m_frames_dp_closed++;
		if (m_last_dp_delta < m_dp_delta_min) m_dp_delta_min = m_last_dp_delta;
		if (m_last_dp_delta > m_dp_delta_max) m_dp_delta_max = m_last_dp_delta;
		//  ★ §37: distribution and time-placement of the non-closing frames.
		m_disp_hist[u8(m_last_dp_delta)]++;
		if (m_last_dp_delta != 0)
		{
			if (!m_disp_first) m_disp_first = m_frames_run;
			m_disp_last = m_frames_run;
			m_disp_bucket[(m_frames_run * 16) / 1900000 < 16
					? (m_frames_run * 16) / 1900000 : 15]++;
			if (++m_disp_open_run > m_disp_open_run_max)
				m_disp_open_run_max = m_disp_open_run;
		}
		else m_disp_open_run = 0;
	}
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
		m_order_before = (traps || partials) ? order_before : slots;
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


//  ★★★ §133 THE BANK-ENTRY DEMULTIPLEXER -- one trial per 64 frames, scored in
//  device, one line per trial.  Called once per frame after the frame completes.
//
//  ARMED BY IDENTITY, NOT BY TIME: the sweep only runs once I-RAM slot 84 holds
//  PARAMETRIC EQ's first word.  §129 showed a frame-count arm silently described
//  CHORUS instead, for every "PEQ" measurement ever taken.
//  ★★★ §180 SPECULATIVE (mask bit 62): PTRD-A -- `lo12 == 0x1C0' DOES NOT MOVE
//  THE POINTER.
//
//  Provenance: an exhaustive search over 21 364 736 candidate delta rules
//  (sign x class-subset x one field-level gate) returns `class4 in {2,0xA}' AND
//  `lo12 != 0x1C0' as the UNIQUE best NON-DEGENERATE rule in the whole space --
//  it satisfies C4 + P1 + P2 + P3 and nothing else does.
//  ⚠ The search's four 7/7 rules are DEGENERATE: they freeze the pointer so every
//  constraint reads 0 == 0 (N cells [1,1,1]).  A criterion that cannot fail.
//  ⚠ The gate is NOT vacuous: 103 sites carry lo12 0x1C0 on a pointer-moving
//  class and 36 of them have a non-zero addr8 (+66, -11, +69..+78, +/-1 ...).
//  ⚠ And it does NOT solve the rule: C1/C2/C3 are satisfied by ZERO of 6 088 704
//  non-degenerate rules, and C3 is PROVABLY unreachable -- it demands
//  77x - 80y = 0 with x,y in {0,1}, and gcd(77,80) = 1 forces the inert case.
bool upd6383_device::ptrd_a_suppressed(u64 word)
{
	if (!m_speculative || !(m_specmask & (1ull << 62)))
		return false;
	if ((word & 0xfff) != 0x1c0)
		return false;
	m_ptrd_a_n++;
	return true;
}

//  ★★★ §193 PROBE (read-only): THE f31 = 4 WINDOW.
//
//  PEQ+CHORUS w38..w46 and PEQ+FLANGER w38..w46 are byte-identical for NINE
//  words and differ at ONE BIT -- `020.A.06.1D5' (f31 = 0, decoded acc <- P)
//  vs `028.A.06.1D5' (f31 = 4).  Body 0 loads at I-RAM 84, so the window is
//  I-RAM slots 122..130:
//        +0..+2   the INPUT CONTROL
//        +3       the f31 word            (I-RAM 125)
//        +4       `182.2.00.407' -- store acc to memory: THE READOUT (I-RAM 126)
//        +5..+8   C63, the class-6 lookup, and two 1CE words
//
//  ★ THE CRITERION, and why this family is worth a run where the bit-11 family
//  is not (§192): the ground truth is THE OTHER PROGRAM, not a guess.  Run both,
//  compare the accumulator slot by slot.
//  ⚠ AND ITS FAILURE MODE, which is why +0..+2 are instrumented: the two
//  programs differ OUTSIDE the window, so the accumulator arriving into it may
//  already differ.  If it does, the comparison is confounded and the run says
//  nothing about f31 -- a control that can fail.
//  ★ Keyed by I-RAM SLOT, not by word value: several of these words recur
//  elsewhere in the same program, and §174 measured what pooling costs.
void upd6383_device::f31_probe(u64 word)
{
	//  ★ §195: KEY BY WORD, NOT BY SLOT.  PEQ+VIBRATO carries the same nine-word
	//  window at program word 31, i.e. I-RAM 115..123, where PEQ+CHORUS and
	//  PEQ+FLANGER carry it at 122..130 -- a slot key cannot compare all three.
	//  Eight of the nine word values are distinct, so the word identifies the
	//  offset unambiguously.  ⚠ And the SLOT is recorded per word as a
	//  self-check: if a window word recurs elsewhere in the program the slot
	//  range widens and the sample is pooled (§174's error).  slot min == max is
	//  the pass condition.
	if (m_cur_iw < 100 || m_cur_iw > 140) return;
	//  ⚠ GATE ON THE EXPECTED WORD.  The first version sampled from frame 0 --
	//  before the program is uploaded -- so `word' logged as 0000000000 and the
	//  min/max were dominated by boot content.  Both arms then reported
	//  BYTE-IDENTICAL accumulator ranges for two different programs, which is the
	//  symptom.  Slot alone does not identify the instruction; slot AND word does.
	static const u64 WIN[] = {
		0x0202AFC415ull, 0x0204200000ull, 0x00922FA700ull,
		0x0020A061D5ull, 0x0028A061D5ull,          // the f31 pair
		0x0182200407ull, 0x0040000C63ull, 0x00006184CDull,
		0x00124011CEull, 0x01042061CEull };
	bool ok = false;
	for (u64 w : WIN) if (w == word) { ok = true; break; }
	if (!ok) { m_f31_reject++; return; }
	int i = -1;
	for (int q = 0; q < 10; q++) if (WIN[q] == word) { i = (q < 4) ? q : (q == 4 ? 3 : q - 1); break; }
	if (i < 0) return;
	if (!m_f31_hits[i]) { m_f31_smin[i] = m_f31_smax[i] = m_cur_iw; }
	else { m_f31_smin[i] = std::min<u32>(m_f31_smin[i], m_cur_iw);
	       m_f31_smax[i] = std::max<u32>(m_f31_smax[i], m_cur_iw); }
	const s64 a = util::sext(m_cur_unit1 ? m_accb : m_acc, 44);
	if (!m_f31_hits[i]) { m_f31_amin[i] = m_f31_amax[i] = a; }
	else
	{
		m_f31_amin[i] = std::min(m_f31_amin[i], a);
		m_f31_amax[i] = std::max(m_f31_amax[i], a);
		if (a != m_f31_aprev[i]) m_f31_achg[i]++;
	}
	m_f31_word[i] = word;
	m_f31_aprev[i] = a;
	m_f31_hits[i]++;
}

//  ★★★ §191 PROBE (read-only): the pointer AT every bit-11 word.
//
//  §185 INFERS that `050.0.00.921' (MULTI TAP DELAY w33) writes addr8 = 0 to
//  selector 0x21 -- the POINTER register -- resetting it at the tap->filter
//  section boundary.  §187 FORCED that the selector space is the chip's internal
//  control registers, so selector 0x21's effect is `m_dp', which is the one
//  family member whose predicted effect is observable.
//
//  ⚠ MEASURE BEFORE IMPLEMENTING (§162's rule, fourth occurrence).  If `m_dp' at
//  the word and at its successor is ALREADY constant across frames, a reset is
//  unobservable and any "it works" reading would be a criterion that cannot fail.
//  If it varies, the reset should make the successor constant -- a real two-sided
//  test.  This probe decides which experiment is even possible.
void upd6383_device::b11_probe(u64 word)
{
	//  ⚠ EXCLUDE C-FORMAT.  On a C-format word bits [24:12] are one 13-bit
	//  immediate -- there is no `lo12' field at all, so an immediate that happens
	//  to carry bit 11 is not a member of this family.  The static census excluded
	//  them; the first version of this probe did not, and its 12 slots filled with
	//  C-format false positives (0C0A292820, 0C04312820, ...) before 0x921, 0xC63
	//  or 0x8BC were ever seen.  A probe whose sample is chosen by arrival order
	//  must be filtered at the door, not afterwards.
	if (upd6383_disassembler::c_format(word)) return;
	if (!((word & 0xfff) & 0x800)) return;
	int sl = -1;
	for (int i = 0; i < m_b11_n; i++) if (m_b11_word[i] == word) { sl = i; break; }
	if (sl < 0 && m_b11_n < 24) { sl = m_b11_n++; m_b11_word[sl] = word; }
	if (sl < 0) return;
	if (!m_b11_hits[sl]) { m_b11_dmin[sl] = m_b11_dmax[sl] = m_dp; }
	else
	{
		m_b11_dmin[sl] = std::min<u32>(m_b11_dmin[sl], m_dp);
		m_b11_dmax[sl] = std::max<u32>(m_b11_dmax[sl], m_dp);
		if (m_dp != m_b11_dprev[sl]) m_b11_dchg[sl]++;
	}
	m_b11_dprev[sl] = m_dp;
	m_b11_hits[sl]++;
}

void upd6383_device::bx_frame_end()
{
	if (!m_bx_on && !m_bx_sweep)
		return;
	if (!m_bx_armed)
	{
		u64 w0 = 0;
		for (u32 i = 0; i < upd6383_disassembler::WORD_BYTES; i++)
			w0 = (w0 << 8) | m_iram.read_byte(84 * upd6383_disassembler::WORD_BYTES + i);
		if (w0 != 0x000020B1CDULL)       // PARAMETRIC EQ's w0, `000.2.0B.1CD'
			return;
		m_bx_armed = true;
		//  ⛔ §134 FIX: clear the state cells AT ARM, not only at trial end.  In the
		//  first run trial 0 inherited whatever ordinary PEQ execution had left in
		//  0x50..0x77 and scored nz = 18, which fired the pre-registered F1 ("trial 0
		//  nz > 0 -> the injector leaks -> run VOID").  It was not a leak: trials 1-3
		//  with the SAME selector settings scored nz = 3.  Rather than argue the
		//  criterion away after the fact, the instrument is fixed so trial 0 starts
		//  from the same state as every other trial and F1 can be scored as written.
		for (u32 i = 0; i < 40; i++)
		{ m_dram.write_dword(0x50 + i, 0); pv_wr_dram_tag(u8(0x50 + i), 0, E1_PV_BOOT); }
		std::memset(m_bx_prev, 0, sizeof(m_bx_prev));
		logerror("upd6383: ★ §133 ARMED on I-RAM[84] = PARAMETRIC EQ, frame %u\n",
				u32(m_frames_run));
		logerror("upd6383: §133 trial sel0D sel0E f4 f5 | nz/40 chg/63 "
				"feed1(s,t) feed2(s,t) shift/%u\n", 20 * (BX_TRIAL_FRAMES - 1));
		return;
	}

	//  read the 40 Direct-Form-I state cells: bank 1 at 0x50..0x63, bank 2 at
	//  0x64..0x77, four cells per section, five sections each (§129 §1, MEASURED).
	u32 cell[40];
	for (u32 i = 0; i < 40; i++)
		cell[i] = m_dram.read_dword(0x50 + i) & 0xffffff;

	const u32 n = m_bx_tframe;
	if (n > 0)
	{
		//  C1 non-degeneracy: does mem[0x64] actually MOVE?  A live feed gives 63,
		//  a DC fixed point gives 0.  Scored first, because every other predicate
		//  is meaningless on a constant.
		if (cell[20] != m_bx_prev[20]) m_bx_chg++;
		//  C3 shift identity, model-free: mem[B+1][n] must equal mem[B+0][n-1] for
		//  all ten sections.  It uses only the ANCHORED core, none of the four
		//  unknowns, so it is a control -- if it fails on an arm that feeds a bank,
		//  the CORE model is wrong and nothing may be concluded about the entry.
		for (u32 k = 0; k < 10; k++)
		{
			const u32 b = (k < 5) ? (4 * k) : (20 + 4 * (k - 5));
			if (cell[b + 1] == m_bx_prev[b + 0]) m_bx_shift++;
			if (cell[b + 3] == (m_bx_prev[b + 2] >> 1)) m_bx_shift++;
		}
	}
	//  C2 feed identity: a 24-bit bit-exact match against the two injected streams
	//  says WHICH cell each bank's entry fed from.  Chance is 2^-24 per frame.
	if (cell[0]  == bx_stim(n, false)) m_bx_f1s++;
	if (cell[0]  == bx_stim(n, true))  m_bx_f1t++;
	if (cell[20] == bx_stim(n, false)) m_bx_f2s++;
	if (cell[20] == bx_stim(n, true))  m_bx_f2t++;

	std::memcpy(m_bx_prev, cell, sizeof(cell));
	m_bx_tframe++;

	if (m_bx_tframe >= BX_TRIAL_FRAMES)
	{
		for (u32 i = 0; i < 40; i++) if (cell[i]) m_bx_nz++;
		logerror("upd6383: §133 %4u  %u %u %u %u | %2u %2u | %2u %2u | %2u %2u | %u\n",
				m_bx_trial, m_bx_sel0d, m_bx_sel0e, m_bx_f4, m_bx_f5,
				m_bx_nz, m_bx_chg, m_bx_f1s, m_bx_f1t, m_bx_f2s, m_bx_f2t, m_bx_shift);
		m_bx_nz = m_bx_chg = m_bx_f1s = m_bx_f1t = m_bx_f2s = m_bx_f2t = m_bx_shift = 0;
		m_bx_tframe = 0;
		//  clear the state cells so trials cannot contaminate each other
		for (u32 i = 0; i < 40; i++)
		{ m_dram.write_dword(0x50 + i, 0); pv_wr_dram_tag(u8(0x50 + i), 0, E1_PV_BOOT); }
		std::memset(m_bx_prev, 0, sizeof(m_bx_prev));

		if (m_bx_sweep && ++m_bx_trial < BX_TRIALS)
		{   //  8 x 8 x 4 x 4 = 1024 joint readings, ALL FOUR MOVING TOGETHER.
			//  §125 point 4 / §121's failure: three of the four held at a guess
			//  while one varies cannot decide anything, because they share one
			//  five-word block and compete for one register (§131).
			m_bx_sel0d = (m_bx_trial >> 7) & 7;
			m_bx_sel0e = (m_bx_trial >> 4) & 7;
			m_bx_f4    = (m_bx_trial >> 2) & 3;
			m_bx_f5    =  m_bx_trial       & 3;
		}
		else if (m_bx_sweep)
		{
			logerror("upd6383: ★ §133 SWEEP COMPLETE, %u trials\n", m_bx_trial);
			m_bx_sweep = false;
			//  ⛔ §134 FIX: and STOP.  The first run kept scoring after the sweep
			//  finished, emitting 11 826 further lines all labelled trial 1024 --
			//  92 % of the log.  A naive parse of that file reports 84.6 % of trials
			//  passing (they are one frozen arm repeated) instead of the true 21.9 %,
			//  i.e. the contamination turns a discriminating criterion into one that
			//  looks like it cannot fail.
			m_bx_on = false;
			m_bx_armed = false;
		}
	}
}


void upd6383_device::dump_frame_report() const
{
	// NB: plain %u / %d only, matching the rest of this file.  (A u64 count only
	// overflows u32 after ~25 hours of emulated audio at 48 kHz.)
	{   //  ★ §44: dump C-RAM.  The body's multiplies consume cursor 0x62..0x70 and
		//  the values there run 00C800, 00CC00, 00D000 ... -- a LINEAR RAMP of step
		//  0x400, which is not a coefficient set.  The kernel's cursor 0x90+ carries
		//  what look like real coefficients (200000, 400000, 3B9885, C62251 ...).
		//  Print the whole space so the two can be compared directly.
		for (u32 base = 0; base < 256; base += 16)
		{
			std::string ln;
			for (u32 i = 0; i < 16; i++)
				ln += string_format(" %06X", const_cast<upd6383_device *>(this)->m_cram.read_dword(base + i) & 0xffffff);
			logerror("upd6383: C-RAM %02X:%s\n", base, ln);
		}
	}
	logerror("upd6383: §44 TAP-TABLE fetches (C-RAM 0x50..0x8B, treated as addresses "
			"not coefficients): %u\n", m_tap_n);
	{
		std::string ds;
		for (u32 q = 0; q < m_dly_n; q++)
			ds += string_format(" [%c dsc %02X = %04X]", m_dly_dir[q], m_dly_dsc[q], m_dly_val[q]);
		{   // ★ §54 THE TRACKING TEST
		const u32 qq = m_trk[0][0], ql = m_trk[0][1], lq = m_trk[1][0], ll = m_trk[1][1];
		const u32 quiet = qq + ql, loud = lq + ll;
		logerror("upd6383: ★ §54 TRACKING: quiet-in %u frames -> %u silent / %u LOUD (peak %d)"
				" | loud-in %u -> %u silent / %u loud (peak %d)\n",
				quiet, qq, ql, m_out_peak_quiet, loud, lq, ll, m_out_peak_loud);
		logerror("upd6383:   VERDICT: %s  (DC leak %.2f%% of quiet frames; pass-through %.2f%% "
				"of loud frames)\n",
				(quiet && ql * 20 > quiet) ? "DC -- output present with NO input"
					: (!loud || ll * 20 <= loud) ? "SILENT -- chip eats the signal"
					: "★ TRACKS THE INPUT",
				quiet ? 100.0 * double(ql) / double(quiet) : 0.0,
				loud ? 100.0 * double(ll) / double(loud) : 0.0);
	}
	{   // ★ §59 P1.1 report
		std::string db;
		for (u32 i = 0; i < 256; i++)
			if (m_dscbank[i]) db += string_format(" %02X:%04X", i, m_dscbank[i]);
		logerror("upd6383: ★ §70 ACCA AT w73: quiet frames %u  min %lld  max %lld  |  "
			"loud frames %u  min %lld  max %lld\n",
			m_pa_n[0], (long long)(m_pa_n[0] ? m_pa_min[0] : 0), (long long)(m_pa_n[0] ? m_pa_max[0] : 0),
			m_pa_n[1], (long long)(m_pa_n[1] ? m_pa_min[1] : 0), (long long)(m_pa_n[1] ? m_pa_max[1] : 0));
		logerror("upd6383: ★★★ §211 ACCB AT w78 (the unit-1 half, never measured before): "
			"quiet frames %u  min %lld  max %lld  |  loud frames %u  min %lld  max %lld"
			"  | ⚠ min == max is a CONSTANT, not audio (standing rule 1)\n",
			m_pb_n[0], (long long)(m_pb_n[0] ? m_pb_min[0] : 0), (long long)(m_pb_n[0] ? m_pb_max[0] : 0),
			m_pb_n[1], (long long)(m_pb_n[1] ? m_pb_min[1] : 0), (long long)(m_pb_n[1] ? m_pb_max[1] : 0));
		//  ★★★ STANDING RULE 19 (§221): THE MEAN AND THE AC SPAN, SEPARATELY.
		//  Rule 1 (min != max) and §211's translation rule are JOINTLY INSUFFICIENT --
		//  OUTPUT-STAGE-NULL_findings.md §6.5(ii) constructs a pedestal of 79 438 with
		//  a +/-90 ripple that passes BOTH and is a DC at -59 dB.  A DC is what
		//  `|mean| >> AC span' looks like, so print the two quantities that decide it
		//  rather than trusting a reader to remember the note.
		{
			const auto mean = [](s64 sum, u32 n) { return n ? double(sum) / double(n) : 0.0; };
			logerror("upd6383: ★★★ §221 RULE 19 -- MEAN vs AC SPAN (a DC is |mean| >> span):\n"
				"            §70  ACCA@w73  quiet mean %.1f span %lld | loud mean %.1f span %lld\n"
				"            §211 ACCB@w78  quiet mean %.1f span %lld | loud mean %.1f span %lld\n"
				"            ⚠ min != max alone does NOT establish audio; neither does §211's "
				"translation rule.  See OUTPUT-STAGE-NULL_findings.md §6.5(ii).\n",
				mean(m_pa_sum[0], m_pa_n[0]),
				(long long)(m_pa_n[0] ? m_pa_max[0] - m_pa_min[0] : 0),
				mean(m_pa_sum[1], m_pa_n[1]),
				(long long)(m_pa_n[1] ? m_pa_max[1] - m_pa_min[1] : 0),
				mean(m_pb_sum[0], m_pb_n[0]),
				(long long)(m_pb_n[0] ? m_pb_max[0] - m_pb_min[0] : 0),
				mean(m_pb_sum[1], m_pb_n[1]),
				(long long)(m_pb_n[1] ? m_pb_max[1] - m_pb_min[1] : 0));
		}
		e1_report();
		pk_report();                                             // ★ §222 §E-D0
		//  ★★★ §222 §E-D85 -- FOUR fired counts, printed UNCONDITIONALLY beside the
		//  arm's own state (rule 8, as §220 sharpened it after `m_mirror06_n' made
		//  "0 fires" and "never ran" the same log line).  ANY ZERO IN ARM 1 VOIDS THE
		//  RUN: the arm is compound, and a half-armed compound arm is unattributable.
		logerror("upd6383: ★★★ §222 §E-D85 EPILOGUE CROSSBAR (UPD6383_XB85 = %u; route %d, "
				"latch %d): w63 read->D-RAM %llu | w63 ACT-03 latch %llu | w70 SRC-03 load "
				"%llu | w70 store->D-RAM %llu\n",
				m_xb85, xb_route() ? 1 : 0, xb_latch() ? 1 : 0,
				(unsigned long long)m_xb_rd_dram_n, (unsigned long long)m_xb_st_n,
				(unsigned long long)m_xb_ld_n, (unsigned long long)m_xb_wr_dram_n);
		logerror("upd6383:    §222 the LATCHED value (settled frames): quiet n %llu "
				"[%d .. %d] span %lld | loud n %llu [%d .. %d] span %lld  ⚠ RULE 19: a "
				"constant quiet bucket is what the NOZ05 RIG rails produce, not evidence "
				"of a DC and not evidence of audio\n",
				(unsigned long long)m_xb_n[0], m_xb_n[0] ? m_xb_lo[0] : 0,
				m_xb_n[0] ? m_xb_hi[0] : 0,
				(long long)(m_xb_n[0] ? s64(m_xb_hi[0]) - s64(m_xb_lo[0]) : 0),
				(unsigned long long)m_xb_n[1], m_xb_n[1] ? m_xb_lo[1] : 0,
				m_xb_n[1] ? m_xb_hi[1] : 0,
				(long long)(m_xb_n[1] ? s64(m_xb_hi[1]) - s64(m_xb_lo[1]) : 0));
		//  ★★★ §222(c): the mode-1 unit-rebase unification, with the evidence that it
		//  is inert PRINTED rather than asserted.  A NON-ZERO divergence count means the
		//  two rules disagree somewhere in the resident frame -- the unification is then
		//  a behaviour change, every other number in the run is confounded, and the
		//  pre-registered fallback (gate it) applies.
		logerror("upd6383: ★★★ §222 MODE-1 UNIT REBASE (the :2914 / :3491 divergence, now "
				"UNIFIED): ACT-07 mode-1 destinations resolved %llu, of which the bare "
				"`addr8' and the rebased `addr8 | unit<<7' DISAGREED %llu times "
				"(PREDICTED 0 -- 0 of 9 resident mode-1 ACT-07 words execute in unit-1 "
				"context; corpus body images are unit-relative 7 of 7)\n",
				(unsigned long long)m_rebase_eval, (unsigned long long)m_rebase_diff);
	logerror("upd6383: ★ §61 PER-UNIT PRESENTATION: unit0/DO1 %u exec, %u non-zero, peak %d | "
			"unit1/DO2 %u exec, %u non-zero, peak %d\n",
			m_pres_u[0], m_pres_u_nz[0], m_pres_u_peak[0],
			m_pres_u[1], m_pres_u_nz[1], m_pres_u_peak[1]);
	logerror("upd6383: ★ §60 DESCRIPTOR BANK (non-zero cells):%s\n", db.c_str());
		std::string tg;
		for (u32 i = 0; i < 256; i++) if (m_pk_tag[i]) tg += string_format(" %02X:%u", i, m_pk_tag[i]);
		logerror("upd6383: ★ §59 POKE PORT: %u pointer words | data packets -> D-RAM %u, "
				"DESCRIPTOR %u, C-RAM %u, unrecognised %u | tags:%s\n",
				m_pk_ptr, m_pk_dram, m_pk_dsc, m_pk_cram, m_pk_other, tg.c_str());
	}
	{
		static const char *NM[12] = { "kernel iw12", "kernel iw20", "kernel iw30",
		                              "kernel iw40", "body-0 iw90", "body-0 END iw152",
		                              "body-1 iw210", "body-1 END iw332",
		                              "  after iw31 C-fmt", "  after iw34 SRC10",
		                              "  after iw36 SRC00", "  after iw39 SRC19" };
		for (int p = 0; p < 12; p++)
			logerror("upd6383: ★ §81 PROBE %-19s quiet [%lld .. %lld]  loud [%lld .. %lld]  %s\n",
					NM[p], (long long)(m_pq_min[p]==INT64_MAX?0:m_pq_min[p]),
					(long long)(m_pq_max[p]==INT64_MIN?0:m_pq_max[p]),
					(long long)(m_pr_min[p]==INT64_MAX?0:m_pr_min[p]),
					(long long)(m_pr_max[p]==INT64_MIN?0:m_pr_max[p]),
					(m_pq_min[p]==m_pr_min[p] && m_pq_max[p]==m_pr_max[p])
						? "IDENTICAL -- input has NOT reached here" : "★ DIFFERS -- input reaches here");
	}
	{   //  ★ §104: THE FULL PER-SLOT QUIET/LOUD SPLIT.
		//  Reported for every slot that executed at least once in EACH bucket --
		//  a slot seen in only one bucket is printed with its counts and the verdict
		//  "NO-NULL", because a comparison with an empty cell carries no information.
		logerror("upd6383: ★ §104 PER-SLOT QUIET/LOUD SPLIT (acc AFTER the slot | mem UNDER the pointer BEFORE it | L the selected bus)\n");
		logerror("upd6383:    iw  word        dp  nq/nl   acc: quiet[..]/loud[..]           mem: quiet[..]/loud[..]        L: quiet[..]/loud[..]\n");
		int first_acc = -1, first_mem = -1, first_l = -1;
		for (u32 i = 0; i < 384; i++)
		{
			if (!m_sp_nq[i] && !m_sp_nr[i]) continue;
			const bool both = m_sp_nq[i] && m_sp_nr[i];
			const bool da = both && (m_sp_accq_lo[i] != m_sp_accr_lo[i] || m_sp_accq_hi[i] != m_sp_accr_hi[i]);
			const bool dm = both && (m_sp_memq_lo[i] != m_sp_memr_lo[i] || m_sp_memq_hi[i] != m_sp_memr_hi[i]);
			const bool dl = both && (m_sp_lq_lo[i] != m_sp_lr_lo[i] || m_sp_lq_hi[i] != m_sp_lr_hi[i]);
			if (i >= 84 && i <= 199)
			{
				if (da && first_acc < 0) first_acc = int(i);
				if (dm && first_mem < 0) first_mem = int(i);
				if (dl && first_l < 0) first_l = int(i);
			}
			logerror("upd6383:   %3u %010llX %02X %5u/%-5u %14lld..%-14lld %14lld..%-14lld %c | %9d..%-9d %9d..%-9d %c | %9d..%-9d %9d..%-9d %c%s\n",
					i, (unsigned long long)m_sp_word[i], m_sp_dp[i], m_sp_nq[i], m_sp_nr[i],
					(long long)m_sp_accq_lo[i], (long long)m_sp_accq_hi[i],
					(long long)m_sp_accr_lo[i], (long long)m_sp_accr_hi[i], da ? '*' : '=',
					m_sp_memq_lo[i], m_sp_memq_hi[i], m_sp_memr_lo[i], m_sp_memr_hi[i], dm ? '*' : '=',
					m_sp_lq_lo[i], m_sp_lq_hi[i], m_sp_lr_lo[i], m_sp_lr_hi[i], dl ? '*' : '=',
					both ? "" : "  NO-NULL");
		}
		logerror("upd6383: ★ §104 SUMMARY over body-0 range iw84..199: first acc DIFFERS at %d, "
				"first mem DIFFERS at %d, first L DIFFERS at %d  (-1 = never)\n",
				first_acc, first_mem, first_l);
		logerror("upd6383: ★ §104 A/B: ACT-0x07 stores suppressed on SRC 0x08 = %u (0 = A/B not enabled)\n",
				m_ab_nostore08_n);
	}
	{   //======================================================================
		//  ★★★ §213: `P' AND `tempA', PER SLOT, SAME BUCKETS AS §104.
		//  Kernel A only (iw 0..59): this exists to trace the SEND's datapath, and
		//  the send is built and consumed there.  Same '*' / '=' convention, and the
		//  SAME CAVEAT: the flag is not by itself a test of input dependence -- score
		//  it with `dsp/tools/s104_score.py'`s rule (both endpoints translating by
		//  one constant = free-running, not a signal).
		//  `pw' is the bitmask of who wrote P at that slot: bit 5 = §112 class-A
		//  ACT-07 latch, bit 6 = THE MULTIPLY, bit 7 = the §40 m_k multiply.
		//======================================================================
		logerror("upd6383: ★★★ §213 KERNEL-A P / tempA PER-SLOT (both sampled AFTER the slot)\n");
		logerror("upd6383:    iw  word        nq/nl   P: quiet[..]/loud[..]                    tempA: quiet[..]/loud[..]    pw\n");
		for (u32 i = 0; i < 60; i++)
		{
			if (!m_s213_nq[i] && !m_s213_nr[i]) continue;
			const bool both = m_s213_nq[i] && m_s213_nr[i];
			const bool dp2 = both && (m_s213_pq_lo[i] != m_s213_pr_lo[i] || m_s213_pq_hi[i] != m_s213_pr_hi[i]);
			const bool dt  = both && (m_s213_taq_lo[i] != m_s213_tar_lo[i] || m_s213_taq_hi[i] != m_s213_tar_hi[i]);
			logerror("upd6383:   %3u %010llX %5u/%-5u %14lld..%-14lld %14lld..%-14lld %c | %9d..%-9d %9d..%-9d %c | %02X%s\n",
					i, (unsigned long long)m_sp_word[i], m_s213_nq[i], m_s213_nr[i],
					(long long)m_s213_pq_lo[i], (long long)m_s213_pq_hi[i],
					(long long)m_s213_pr_lo[i], (long long)m_s213_pr_hi[i], dp2 ? '*' : '=',
					m_s213_taq_lo[i], m_s213_taq_hi[i], m_s213_tar_lo[i], m_s213_tar_hi[i], dt ? '*' : '=',
					m_s213_pwm[i], both ? "" : "  NO-NULL");
		}
		logerror("upd6383: ★★★ §213 STORE-PROBE FIX: %llu phantom store records suppressed "
				"(must EQUAL the §112 latch count %llu; UPD6383_STPROBE = %d)\n",
				(unsigned long long)m_stprobe_n,
				(unsigned long long)(m_act07_latchp_n + m_act07_latchk_n), m_stprobe ? 1 : 0);
	}
	{   //======================================================================
		//  ★★★ §109 THE STORE-SITE PROBE.  SCOPE: this build, DSPCFG as configured,
		//  UPD6383_SPEC as logged above, frames after 420 000 only, notes playing.
		//======================================================================
		logerror("upd6383: ★★★ §109 STORE-SITE PROBE  (mask bit 28 ACT-07 POST-increment: "
				"FIRED %u non-K6 + %u K6-excluded | mask bit 29 alt store gate: "
				"DISAGREED on %u store-gate evaluations)\n",
				m_act07_post_n, m_act07_post_k6_n, m_stgate_alt_n);
		logerror("upd6383:   path: 0=decoded() 1=speculative catch-all 2=PARTIAL 3=TRAP\n");
		logerror("upd6383:   gfail: 0=passes 1=class 21=bit11 22=ptrmode 23=SRC/ACT anchor "
				"5=bit4-off-mode2 6=ACT07-off-mode2 7=GUARD7 3=operation 4=c-format\n");
		logerror("upd6383:   site: 1=exec_addressing_only K6 store  2=exec_alu bit-4 store  "
				"3=exec_alu ACTION-0x07 store\n");
		logerror("upd6383:    iw  word        n_exec  dpPre dpPost dlt | dec gfail supp g7 path | stores\n");
		for (u32 i = 0; i < SPROBE_MAX; i++)
		{
			const sprobe_t &s = m_sprobe[i];
			if (s.iw == 0xffff || !s.n_exec) continue;
			std::string st;
			for (u32 q = 0; q < s.nst; q++)
				st += string_format("  [site%u addr %02X val %d..%d x%u]",
						s.st_site[q], s.st_addr[q], s.st_lo[q], s.st_hi[q], s.st_n[q]);
			if (s.nst == 0) st = "  (NO STORE)";
			logerror("upd6383:   %3u %010llX %7u   %02X    %02X   %+4d |  %u  %5u   %u   %u   %u |%s\n",
					s.iw, (unsigned long long)s.word, s.n_exec, s.dp_pre, s.dp_post,
					int(s8(u8(s.dp_post - s.dp_pre))), s.decoded, s.gfail, s.supp, s.g7,
					s.path, st.c_str());
		}
		//  ★ the CROSS-FRAME LFO PHASE WITNESS, and it is TWO-SIDED: identical values
		//  on consecutive frames = the phase is reset every frame (no modulation);
		//  a per-frame advance = the ramp is free-running.
		std::string ph;
		for (u32 q = 0; q < m_lfo_phase_n; q++)
			ph += string_format(" f%u:%d", m_lfo_phase_frame[q], m_lfo_phase[q]);
		logerror("upd6383: ★ §109 LFO PHASE resident at body-0 iw89 on %u consecutive frames:%s\n",
				m_lfo_phase_n, ph.c_str());
		//  ★ §119 RULE-8: the two downstream cells on the SAME frames.  A value that
		//  merely stops being constant proves nothing -- these must TRACK the phase
		//  printed above, frame for frame.
		{
			std::string a, b;
			for (u32 q = 0; q < m_lfo_dst_n; q++)
				a += string_format(" [dp%02X]%d", m_lfo_dst_dp[q], m_lfo_dst[q]);
			for (u32 q = 0; q < m_lfo_tap_n; q++)
				b += string_format(" [dp%02X]%d", m_lfo_tap_dp[q], m_lfo_tap[q]);
			logerror("upd6383: ★ §119 TRACK iw94 mem[dp] on the same frames:%s\n", a.c_str());
			logerror("upd6383: ★ §119 TRACK iw95 mem[dp] on the same frames:%s\n", b.c_str());
		}
	}
	{
		logerror("upd6383: ★ §86 KERNEL D-RAM WRITES -- cells whose value depends on the INPUT:\n");
		u32 dep = 0, tot = 0;
		for (u32 i = 0; i < 256; i++)
		{
			if (!m_kw_n[i]) continue;
			tot++;
			const bool q = (m_kq_min[i] != INT32_MAX), l = (m_kl_min[i] != INT32_MAX);
			const bool diff = q && l && (m_kq_min[i] != m_kl_min[i] || m_kq_max[i] != m_kl_max[i]);
			if (diff) { dep++;
				logerror("upd6383:    ★ cell %02X  quiet [%d .. %d]  loud [%d .. %d]  (%u writes)\n",
						i, m_kq_min[i], m_kq_max[i], m_kl_min[i], m_kl_max[i], m_kw_n[i]); }
		}
		logerror("upd6383:    %u of %u kernel-written cells are INPUT-DEPENDENT\n", dep, tot);
		for (u32 q = 0; q < m_kw_who_n; q++)
			logerror("upd6383:    §96 cell %02X written by iw%-4u  word %09llX\n",
					m_kw_cell[q], m_kw_who[q], (unsigned long long)m_kw_word[q]);
	}
	logerror("upd6383: §80 LATCH/PUBLISH: latched %u (%u non-zero) | publish attempts %u, "
			"hits %u (%u non-zero)\n", m_latch_n, m_latch_nz, m_pub_try, m_pub_hit, m_pub_nz);
	logerror("upd6383: §77 DELAY-PATH ALU: entered %u times, skipped %u; SRC 0x0B words "
			"among them %u\n", m_dly_alu, m_dly_noalu, m_dly_alu_0b);
	logerror("upd6383: §75 DELAY WRITES WITH CONTENT: %u of %u\n", m_dly_w_nz, m_dly_w);
	logerror("upd6383: §49 PIPELINE: %u delay data LANDED, %u lost to ring collisions "
			"(land = %u)\n", m_dr_landed, m_dr_lost, m_land);
	logerror("upd6383: §48 DELAY READ CONSUMED (SRC 0x0B): %u times, %u with a "
			"non-zero datum\n", m_dr_reads, m_dr_reads_nz);
	//  ★★★ §215: the class-2 half of §48, split out.  §48 minus §77 already implied
	//  this number; printing it directly is what lets the gate be graded against a
	//  pre-registered null (data/PREDICT_215.md §2 predicted 1 211 520 +/- 1 %).
	//  `mem nz' and `dr nz' are counted in BOTH arms: they say what each reading
	//  WOULD deliver, so the default run measures the counterfactual for free.
	logerror("upd6383: ★★★ §215 CLASS-2 SRC 0x0B (no delay access -- kernel iw25): "
			"%llu evaluations | mem[ptr] non-zero on %llu | m_dr non-zero on %llu | "
			"RIVAL FIRED %llu (UPD6383_SRC0B2 = %d)\n",
			(unsigned long long)m_src0b2_n, (unsigned long long)m_src0b2_memnz,
			(unsigned long long)m_src0b2_drnz, (unsigned long long)m_src0b2_fired,
			m_src0b2 ? 1 : 0);
	//  ★★★ §217: WHERE THE DATUM COMES FROM, not whether it is alive.
	logerror("upd6383: ★★★ §217 `m_dr' PROVENANCE AT THE CLASS-2 SRC 0x0B WORD (iw25), "
			"SETTLED FRAMES > 900000: %llu evaluations | age %llu..%llu frames | "
			"UPD6383_DRPUB = %d, fired %llu\n",
			(unsigned long long)m_prov_tot,
			(unsigned long long)(m_prov_age_min == ~0ull ? 0 : m_prov_age_min),
			(unsigned long long)m_prov_age_max, m_drpub ? 1 : 0,
			(unsigned long long)m_drpub_fired);
	for (u32 q = 0; q < m_prov_cnt; q++)
		logerror("upd6383:    §217 read by iw%-5u  x%-12llu  (%llu with a NON-ZERO datum)\n",
				m_prov_iw[q], (unsigned long long)m_prov_n[q],
				(unsigned long long)m_prov_nz[q]);
	if (m_prov_other)
		logerror("upd6383:    §217 producers beyond slot %u: %llu\n",
				PROV_SLOTS, (unsigned long long)m_prov_other);
	logerror("upd6383: ★★★ §217 WHERE A DATUM TAGGED `iw12' IS PUBLISHED (settled):\n");
	for (u32 q = 0; q < m_p12_cnt; q++)
		logerror("upd6383:    §217 published at iw%-5u  x%llu\n",
				m_p12_iw[q], (unsigned long long)m_p12_n[q]);
	if (m_p12_cnt == 0)
		logerror("upd6383:    §217 (never -- no publish ever carried an iw12 tag)\n");
	logerror("upd6383: §217 publishes strictly between iw12 and iw25: %llu  "
			"(structurally 0 -- the kernel has no delay word in iw13..iw24)\n",
			(unsigned long long)m_pub_between);
	logerror("upd6383: §46 DELAY PORT: %u reads (%u returned NON-ZERO), %u writes; "
				"descriptor cell non-zero on %u accesses.%s\n",
				m_dly_r, m_dly_r_nz, m_dly_w, m_dly_cell_nz, ds.c_str());
	}
	logerror("upd6383: FRAME REPORT (experimental IC311 audio path)\n");
	logerror("    frames run          %u\n", u32(m_frames_run));
	logerror("    frames that TRAPPED %u (%d.%02d %%) -- their return was DISCARDED\n",
			u32(m_frames_trapped),
			u32(m_frames_run ? (100 * m_frames_trapped) / m_frames_run : 0),
			u32(m_frames_run ? ((10000 * m_frames_trapped) / m_frames_run) % 100 : 0));
	logerror("    frames with PARTIAL words (addressing executed, ALU unknown) %u\n",
			u32(m_frames_partial));
	logerror("    partial words executed, all frames %u\n", u32(m_partial_total));
	logerror("    last frame: %u slots = %u DECODED + %u PARTIAL (addressing only) + %u TRAP\n",
			m_last_slots, m_last_slots - m_last_partials - m_last_traps,
			m_last_partials, m_last_traps);
	logerror("    ended on the wait word %010X: %u\n", FRAME_WAIT_WORD,
			u32(m_frames_run - m_frames_capped - m_frames_overrun));
	//  ★★★ §38, 2026-07-28: THE CAP AND OVERRUN FRAMES ARE ALSO A BOOT TRANSIENT.
	//  13 % of frames never reach the wait word, which reads like a standing fault.
	//  Measured over 1 824 001 frames, they are bounded in time and END AT THE SAME
	//  FRAME as §37's closure residue (~264 002 -- the last program upload):
	//     CAP     frames 1 .. 264 001,        always EXACTLY 384 slots (the cap)
	//     OVERRUN frames 231 362 .. 258 241,  always EXACTLY 350 slots
	//  After that boundary, every one of the remaining ~1.56 M frames reaches the
	//  wait word, traps 0 times and closes with residue 0.  Neither kind produces
	//  audio either: `clean' requires hit_wait && !overrun, so the tone generator
	//  discards them.  ⇒ Not a defect; do not chase.
	logerror("    ended on the %u-slot CAP:      %u\n", FRAME_SLOT_CAP, u32(m_frames_capped));
	logerror("    ended by I-RAM OVERRUN:        %u\n", u32(m_frames_overrun));
	{   // ★ §38
		std::string cb, ob;
		for (int b = 0; b < 16; b++) cb += string_format(" %u", m_cap_bucket[b]);
		for (int b = 0; b < 16; b++) ob += string_format(" %u", m_ovr_bucket[b]);
		logerror("    §38 CAP     over time:%s\n", cb.c_str());
		logerror("    §38 CAP     first %u last %u, slots %u..%u\n",
				u32(m_cap_first), u32(m_cap_last),
				m_cap_slots_min == 0xffffffff ? 0 : m_cap_slots_min, m_cap_slots_max);
		logerror("    §38 OVERRUN over time:%s\n", ob.c_str());
		logerror("    §38 OVERRUN first %u last %u, slots %u..%u\n",
				u32(m_ovr_first), u32(m_ovr_last),
				m_ovr_slots_min == 0xffffffff ? 0 : m_ovr_slots_min, m_ovr_slots_max);
	}
	logerror("    last frame: %u slots, %u partial, %u traps\n",
			m_last_slots, m_last_partials, m_last_traps);

	// ---- FRAME CLOSURE -- a criterion that CAN fail, and today does ---------
	//
	// ★ RETRACTION, 2026-07-26 (dsp/analysis/retraction-sweep.md, premise P10).
	// THIS BLOCK USED TO SAY "THE CRITERION IS FORCED".  IT IS NOT, ANY MORE.
	// The forcing ran: the DI latches are at FIXED addresses in the chip's D-RAM
	// (the serial receivers write them, no instruction does), the microcode reads
	// them at ptr+2 / ptr+5, therefore the pointer at PC-restart must be the same
	// every frame, therefore net displacement == 0 (mod 256).
	//
	// The middle step is K6 finding 4, and K6 ITSELF flagged that its step 1 --
	// finding 5, "0 of 38 body images touch X+0..X+6" -- was "not origin-free: it
	// uses the standing reading that `801.0.NN.821' loads the data pointer".
	// K3 WITHDREW EXACTLY THAT READING (0x821 addresses C-RAM, FORCED), and with
	// the pointer shared across the CALL boundary dsp/analysis/closure-pointer.md
	// item F MEASURED the opposite: 79 OF 79 unit-0 images enter the window and
	// 10 of 79 touch an input latch.  "Read and never written" is not a property
	// of the corpus; it was a property of a withdrawn origin model.
	//
	// SO THE LABEL IS NOW **CONSISTENT**, NOT FORCED.  The criterion may still be
	// true -- closure-pointer.md sect. 4.1 Package B, which is the better bet --
	// but it is no longer proved.  ★ And the other arm of that sentence --
	// "Package A would make the +121 residue not a defect at all" -- is WITHDRAWN
	// (2026-07-27).  The choice between the packages is still open; the residue
	// is not what hangs on it any more -- see the paragraph below.
	//
	// ★ AND THE +121 IS ANSWERED, 2026-07-27.  Candidate (P-1) below -- "SOME
	// WORD RELOADS THE POINTER, and we do not decode it" -- was the right one,
	// with one correction: it is not a WORD, it is the per-unit CALL.  The
	// D-RAM origin is pinned (DRAM_UNIT_BASE: base = 0x05 | unit << 7, FORCED),
	// a rebase between the two calls is FORCED to exist because net(body0) takes
	// eight different values across the 37 unit-0 images, and with it performed
	// the walk returns to its start exactly.  (P-2), (P-3) and (P-4) are NOT
	// resolved by that and are kept below, unchanged, because a residue of 0 is
	// consistent with all of them too.
	//
	//   (P-1) ANSWERED: the pointer is re-established per unit, at the CALL.
	//         Its old wording survives as a record of what was searched: nothing
	//         loaded m_dp at all (K3 withdrew `0x821', adjudication sect. 5.1
	//         falsified `0x827' at 0 of 85 streams) and the five undecoded
	//         C-format words with selector 0x20 (I-RAM 15, 22, 29, 31, 40) were
	//         the favoured carriers.  They are STILL undecoded and they still may
	//         be the instruction that does this -- what is settled is the VALUE
	//         and the fact that it happens, not which word performs it.
	//   (P-2) the post-increment rule is not `class4 & 7 == 2' everywhere.  It is
	//         MEASURED, but on body words; the kernel is where it is least tested.
	//   (P-3) the CALL/RETURN sequencer (EDUCATED GUESS G-5) puts words in the
	//         wrong order, or a body is entered that the real machine skips.
	//   (P-4) some words are CONDITIONAL -- the part has a COND field (CDJ-500
	//         block diagram) that nothing in this decode models.
	logerror("    FRAME CLOSURE (the criterion is CONSISTENT, not FORCED -- it rests on K6\n");
	logerror("    finding 5, which closure-pointer.md item F FALSIFIED.  What IS forced is\n");
	logerror("    the per-unit D-RAM base 0x%02X | unit<<7 this core now applies at the CALL;\n",
			DRAM_UNIT_BASE);
	logerror("    a residue of 0 is that base's strongest live consequence, not its proof):\n");
	//  ★★★ §37, 2026-07-28: THE DRIFT IS A BOOT TRANSIENT, NOT A STEADY-STATE DEFECT.
	//  The run-wide "min -1 max +116 (VARIES)" line below reads like an ongoing
	//  problem and is not one.  Measured over 1 824 001 frames: EVERY non-closing
	//  frame falls between frame 204 482 and 264 002 -- one contiguous window of
	//  ~60 000 frames (~4.6 s to ~6.0 s of emulated audio, i.e. while the host is
	//  still uploading programs).  From frame 264 003 to the end of the run, all
	//  1 560 959 measured frames close with residue EXACTLY 0.
	//  The residues are -1 x 21 120 (one contiguous run), +5 x 2880, +6 x 960,
	//  +7 x 960, +116 x 1 -- transient programs, each internally consistent.
	//  ⇒ Do NOT chase this as a pointer bug. The 1.69 % of frames whose X is not
	//  0x45 are the SAME frames, so the input-window spread is the same transient.
	logerror("        net D-RAM pointer displacement, last frame %+d\n", m_last_dp_delta);
	logerror("        over every COMPLETE frame (%u of them): min %+d  max %+d  %s\n",
			u32(m_frames_dp_measured), m_dp_delta_min, m_dp_delta_max,
			(m_dp_delta_min == m_dp_delta_max) ? "(CONSTANT -- a fixed per-frame drift)"
					: "(VARIES between frames)");
	{   // ★ §37
		std::string dh;
		for (int d = 0; d < 256; d++)
			if (m_disp_hist[d]) dh += string_format(" %+d:%u", (d < 128) ? d : d - 256, m_disp_hist[d]);
		logerror("        §37 RESIDUE HISTOGRAM:%s\n", dh.c_str());
		std::string tb;
		for (int b = 0; b < 16; b++) tb += string_format(" %u", m_disp_bucket[b]);
		logerror("        §37 non-closing frames over time (16 buckets):%s\n", tb.c_str());
		logerror("        §37 first non-closing frame %u, last %u, longest consecutive run %u\n",
				u32(m_disp_first), u32(m_disp_last), m_disp_open_run_max);
	}
	logerror("        frames that closed %u of %u\n",
			u32(m_frames_dp_closed), u32(m_frames_dp_measured));
	// A complete frame can only close if its ENTRY pointer was the steady-state
	// one, i.e. if the frame BEFORE it also completed.  So the honest target is
	// not the whole denominator -- it is the denominator minus the complete
	// frames that follow a capped or overrun one.  Printed so that a shortfall
	// is read as arithmetic rather than as a defect, and so that a 100.00 % on a
	// run WITH capped frames reads as a broken counter.
	logerror("        (frames that did NOT complete, and so denied the NEXT frame its\n");
	logerror("         entry pointer: %u capped + %u overrun)\n",
			u32(m_frames_capped), u32(m_frames_overrun));
	if (m_frames_dp_measured != 0 && m_frames_dp_closed != m_frames_dp_measured)
		logerror("        *** THE POINTER WALK DOES NOT CLOSE ON %u FRAME(S) -- see the"
				" candidate list in dump_frame_report() ***\n",
				u32(m_frames_dp_measured - m_frames_dp_closed));

	// ---- THE PER-UNIT REBASE AUDIT -----------------------------------------
	// Does the rebase do WORK, and where?  For unit 1 it must (net(body0) takes
	// eight values, so no walk delivers 0x85).  For unit 0 the closure
	// arithmetic says the header walk from X = 0xFF already delivers 0x05, so
	// the rebase should be a NO-OP there -- a claim that is measured here rather
	// than assumed, because if it is not a no-op the closure model is wrong.
	logerror("    PER-UNIT D-RAM REBASE (base = 0x%02X | unit<<7, FORCED -- see DRAM_UNIT_BASE):\n",
			DRAM_UNIT_BASE);
	logerror("        unit 0 (I-RAM %u): %u calls, the walk ALREADY delivered 0x%02X on %u"
			" (%u.%02u %%)\n",
			UNIT0_ENTRY, u32(m_calls_u0), DRAM_UNIT_BASE, u32(m_rebase_agreed_u0),
			u32(m_calls_u0 ? (100 * m_rebase_agreed_u0) / m_calls_u0 : 0),
			u32(m_calls_u0 ? ((10000 * m_rebase_agreed_u0) / m_calls_u0) % 100 : 0));
	logerror("        unit 1 (I-RAM %u): %u calls, the walk ALREADY delivered 0x%02X on %u"
			" (%u.%02u %%)\n",
			UNIT1_ENTRY, u32(m_calls_u1), u8(DRAM_UNIT_BASE | DRAM_UNIT_STRIDE),
			u32(m_rebase_agreed_u1),
			u32(m_calls_u1 ? (100 * m_rebase_agreed_u1) / m_calls_u1 : 0),
			u32(m_calls_u1 ? ((10000 * m_rebase_agreed_u1) / m_calls_u1) % 100 : 0));

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
	// WHERE the window sat.  The map of dsp/analysis/output-stage-decode.md
	// sect. 3.5 predicts X = 0xFF and therefore latch cells 0x01 / 0x04; this
	// prints what actually happened, with no expected value compiled in, so it
	// can contradict the map.
	{
		u32 best = 0, second = 0, distinct = 0, total = 0;
		u8 best_x = 0;
		for (u32 i = 0; i < 256; i++)
		{
			total += m_in_base_hist[i];
			if (m_in_base_hist[i] != 0) distinct++;
			if (m_in_base_hist[i] > best) { second = best; best = m_in_base_hist[i]; best_x = u8(i); }
			else if (m_in_base_hist[i] > second) second = m_in_base_hist[i];
		}
		logerror("        WHERE THE WINDOW SAT, over %u complete frames: %u distinct values of X;\n",
				total, distinct);
		logerror("        most common X = 0x%02X on %u (%u.%02u %%) -> latch cells 0x%02X / 0x%02X"
				"  (runner-up %u)\n",
				best_x, best, u32(total ? (100 * u64(best)) / total : 0),
				u32(total ? ((10000 * u64(best)) / total) % 100 : 0),
				u8(best_x + IN_LATCH_L_OFF), u8(best_x + IN_LATCH_R_OFF), second);
	}
		{   // ★ §33: how far had the pointer moved by the time the header read?
			std::string dh; u32 tot = 0, best = 0; int bestd = 0;
			for (int d = 0; d < 256; d++) { tot += m_in_delta_hist[d];
				if (m_in_delta_hist[d] > best) { best = m_in_delta_hist[d]; bestd = d; } }
			for (int d = 0; d < 256; d++) if (m_in_delta_hist[d])
				dh += string_format(" %+d:%u", (d < 128) ? d : d - 256, m_in_delta_hist[d]);
			logerror("        §33 POINTER DRIFT between deposit and read: most common %+d "
					"on %u of %u (%.2f%%) --%s\n", (bestd < 128) ? bestd : bestd - 256,
					best, tot, tot ? 100.0 * double(best) / double(tot) : 0.0, dh.c_str());
		}
	//  ★★★ §98 THE POINTER WINDOW, MEASURED.  Replaces the static walk's figures,
	//  which failed calibration (§97 sect. 3).  Per region: the mode-2 cells the
	//  pointer actually reaches, and -- listed separately, never pooled -- the
	//  mode-1 register cells the same region names.
	{
		logerror("        ★ §98 POINTER WINDOW (live, after the boot transient)\n");
		static const u8 marked[4] = { 0x05, 0x07, 0x85, 0x87 };
		for (u32 r = 0; r < PW_NREGION; r++)
		{
			std::string m2, m1;
			u32 lo2 = 0x100, hi2 = 0, n2 = 0, n1 = 0, nd2 = 0;
			for (u32 c = 0; c < 256; c++)
			{
				const u32 rd = m_pw_rd[r][c], wr = m_pw_wr[r][c];
				if (rd || wr)
				{
					if (c < lo2) lo2 = c;
					hi2 = c; n2 += rd + wr; nd2++;
					bool mk = false;
					for (u8 q : marked) if (q == c) mk = true;
					m2 += string_format(" %s%02X%s%s", mk ? "[" : "", c,
							(rd && wr) ? "rw" : (wr ? "w" : "r"), mk ? "]" : "");
				}
				if (m_rw_rd[r][c] || m_rw_wr[r][c])
				{
					n1 += m_rw_rd[r][c] + m_rw_wr[r][c];
					m1 += string_format(" %02X%s", c,
							(m_rw_rd[r][c] && m_rw_wr[r][c]) ? "rw"
									: (m_rw_wr[r][c] ? "w" : "r"));
				}
			}
			if (!n2 && !n1) { logerror("            %-24s (no accesses)\n", pw_name(r)); continue; }
			logerror("            %-24s mode-2 %2u cells %02X..%02X, %u acc:%s\n",
					pw_name(r), nd2, lo2 & 0xff, hi2, n2, m2.c_str());
			if (n1)
				logerror("            %-24s mode-1                        %u acc:%s\n",
						"", n1, m1.c_str());
		}
		logerror("            [..] marks the per-unit base/input cells 05 07 85 87\n");
		{
			std::string ov;
			for (u32 i = 0; i < 256; i++)
				if (m_ovc_hist[i]) ov += string_format(" %02X:%u", i, m_ovc_hist[i]);
			logerror("            §116 OVC loads: %u, values seen:%s (bit3 = wrap)\n",
					m_ovc_loads, ov.empty() ? " (none)" : ov.c_str());
		}
		logerror("            §119 mem-to-mem ACT-07 MOVEs re-targeted POST (bit 34): "
				"%u fired, %u with a non-zero datum\n",
				m_act07_memmove_n, m_act07_memmove_nz);
		logerror("            §121 ACT 0x0D routed (dest sel %u): %u\n",
				u32((m_specmask >> 35) & 7), m_act0d_n);
		logerror("            §114 accumulator stores WRAPPED mod 2^23: %u\n", m_wrap_n);
		logerror("            §113 SRC 0x11 read as mem[ptr]: %u\n", m_src11_mem_n);
		logerror("            §112 class-A ACT-07 latched P instead of storing: %u\n",
				m_act07_latchp_n);
		logerror("            §111 host payload x2 applied to %u packets\n", m_pk_x2_n);
		logerror("            §110 K6 ACT-07 stores re-pointed to pre-increment: %u\n",
				m_k6_act07_fix_n);
		//  ★ §220 rule 8: print the fired count UNCONDITIONALLY, with the arm's own
		//  flag beside it.  `m_mirror06_n's `if' makes 0 fires and "the block never
		//  ran" look identical in a log, which is precisely the ambiguity a fired
		//  count exists to remove -- so this one does not repeat it.
		logerror("            §106 DIAGNOSTIC (mask bit 26 = %d): mirrored %u writes of "
				"cell 0x06 into 0x05\n",
				(m_speculative && (m_specmask & 0x4000000)) ? 1 : 0, m_mirror06_n);
		{   // ★★★ §220: the OVERWRITE half.  Count AND the words it fired on.
			std::string r;
			for (u32 q = 0; q < m_noz05_slots; q++)
				r += string_format(" iw%u:%u", m_noz05_iw[q], m_noz05_cnt[q]);
			logerror("            §220/§223 NOZ05 (UPD6383_NOZ05 = %d): %u site-2 bit-4 stores "
					"to cell 0x05 in kernel A SUPPRESSED |%s\n",
					(int)m_noz05, m_noz05_n, r.empty() ? " (none)" : r.c_str());
		}
		{   //  ★★★ §223 `§NG': the NOP-GUARD NARROWING, printed UNCONDITIONALLY.
			//  Zero here means the narrowing is UNTESTED in this vehicle, not that
			//  it is inert -- 82 of the 103 corpus words sit in body images no
			//  archived log ever loads.  Say which, do not average.
			std::string r;
			for (u32 q = 0; q < m_ng_slots; q++)
				r += string_format(" iw%u:%u", m_ng_iw[q], m_ng_cnt[q]);
			logerror("            ★ §223 §NG NOP-GUARD NARROWED (addr8 == 0x00 added): "
					"%u words handed to exec_alu() that the old guard swallowed, "
					"%u distinct slots (cap 16)%s |%s\n",
					m_ng_n, m_ng_slots, m_ng_slots >= 16 ? " ⚠ CAPPED" : "",
					r.empty() ? " (none -- UNTESTED in this vehicle)" : r.c_str());
		}
		{   //  ★★★★ §223 `§S1': THE SATURATION CENSUS.
			//  `§54' can only see a DC that reaches the OUTPUT.  This sees the
			//  clamp that MAKES one, at the single point where the 44-bit
			//  accumulator becomes a 24-bit datum.  Pre-clamp values, per `iw',
			//  split by `§54's own quiet/loud predicate, settled frames only.
			logerror("upd6383: ★★★★ §223 §S1 SATURATION CENSUS (pre-clamp acc >> %u, "
					"frames > %u, bucket = §54's in_nz).  ⚠ COUNTS CONVERSIONS, NOT "
					"STORES: one store calls acc_to_datum() up to five times, so read "
					"the RATIO, not the count.\n",
					(unsigned)ACC_SHIFT, (unsigned)S1_ARM_FRAME);
			logerror("upd6383:    TOTALS  quiet %llu clip / %llu conversions (%.3f %%)  |  "
					"loud %llu clip / %llu conversions (%.3f %%)  |  off-range iw %u\n",
					(unsigned long long)m_s1_total_clip[0], (unsigned long long)m_s1_total_calls[0],
					m_s1_total_calls[0] ? 100.0 * double(m_s1_total_clip[0]) / double(m_s1_total_calls[0]) : 0.0,
					(unsigned long long)m_s1_total_clip[1], (unsigned long long)m_s1_total_calls[1],
					m_s1_total_calls[1] ? 100.0 * double(m_s1_total_clip[1]) / double(m_s1_total_calls[1]) : 0.0,
					m_s1_offrange_n);
			logerror("upd6383:    iw   region    calls q/l        clips q/l        "
					"pre-clamp quiet[min..max]            pre-clamp loud[min..max]\n");
			u32 rows = 0, dropped = 0;
			for (u32 i = 0; i < 384; i++)
			{
				if (!m_s1_clip[0][i] && !m_s1_clip[1][i]) continue;
				if (rows >= S1_MAX_ROWS) { dropped++; continue; }
				rows++;
				const u32 rg = pw_region(u16(i));
				const char *rn = (rg == PW_KERNEL_A) ? "kernelA"
						: (i >= 84 && i <= 199) ? "body0"
						: (i >= 200 && i <= 332) ? "body1"
						: (i >= 60 && i <= 83) ? "epilog" : "other";
				logerror("upd6383:   %3u %-8s %8u/%-8u %8u/%-8u %14lld..%-14lld %14lld..%lld\n",
						i, rn, m_s1_calls[0][i], m_s1_calls[1][i],
						m_s1_clip[0][i], m_s1_clip[1][i],
						(long long)(m_s1_seen[0][i] ? m_s1_min[0][i] : 0),
						(long long)(m_s1_seen[0][i] ? m_s1_max[0][i] : 0),
						(long long)(m_s1_seen[1][i] ? m_s1_min[1][i] : 0),
						(long long)(m_s1_seen[1][i] ? m_s1_max[1][i] : 0));
			}
			//  ★ store_probe()'s missing overflow counter cost the audit a finding.
			//  This one has it, and it prints even when it is zero.
			logerror("upd6383:    §S1 rows printed %u of cap %u, DROPPED %u\n",
					rows, (unsigned)S1_MAX_ROWS, dropped);
			//  ★ THE CONTROL, printed beside the result so it cannot be quoted apart
			//  from it: two conversions PREDICT_223 §3.1 S2 requires to be CLEAN.
			logerror("upd6383:    §S1 CONTROL (must be clips = 0): iw34 q %u/%u l %u/%u "
					"[q %lld..%lld] | iw40 q %u/%u l %u/%u [q %lld..%lld]\n",
					m_s1_clip[0][34], m_s1_calls[0][34], m_s1_clip[1][34], m_s1_calls[1][34],
					(long long)m_s1_min[0][34], (long long)m_s1_max[0][34],
					m_s1_clip[0][40], m_s1_calls[0][40], m_s1_clip[1][40], m_s1_calls[1][40],
					(long long)m_s1_min[0][40], (long long)m_s1_max[0][40]);
		}
		{   // ★ §99: where the mode-1 stores went, now that they no longer go to D-RAM
			std::string r; u32 n = 0;
			for (u32 c = 0; c < 256; c++)
				if (m_rf_st[c]) { r += string_format(" %02X:%u", c, m_rf_st[c]); n++; }
		{   //  ★★★ §160: WHAT IS ACTUALLY IN THE REGISTER FILE, by value.
			//  §159 measured D-RAM 0x1D..0x40 -- the 36-entry LFO wavetable range --
			//  as ~800 writes per cell with NOT ONE non-zero, so the table never
			//  lands there.  Tag 0x15 routes host pokes to m_rf instead (:919,
			//  mask bit 23, SET in the default), and §97 split that space off from
			//  the pointer-walked D-RAM deliberately.  The open half of §159 §2 is
			//  whether the table ARRIVES in m_rf or never arrives at all -- two
			//  different fixes.  The §99 line below counts MICROCODE stores, not
			//  host writes, so it cannot answer that.  This dumps the contents.
			//  ★ The wavetable window is printed separately and in full, zeros
			//  included, so "absent" is visible rather than inferred from a gap.
			std::string wt;
			u32 wnz = 0;
			for (u32 c = 0x1d; c <= 0x40; c++)
			{
				wt += string_format(" %06X", m_rf[c] & 0xffffff);
				if (m_rf[c] & 0xffffff) wnz++;
			}
			{
			std::string rr;
			//  ★ §176 F1: report EVERY cell, not only the ones that moved.  §164
			//  listed movers only, so it could not tell "static and non-zero" from
			//  "static and ZERO" -- and the whole H1/H2 fork turns on exactly that.
			u32 nz = 0, mv = 0, nzlo = 0;
			for (u32 i = 0; i < 0x100; i++)
			{
				if (m_rampprev[i]) { nz++; if (i < 0x20) nzlo++; }
				if (m_rampchg[i]) mv++;
				if (m_rampprev[i] || m_rampchg[i])
				{
					rr += string_format(" %02X:%d", i, m_rampprev[i]);
					if (m_rampchg[i]) rr += string_format("(%d..%d/chg%llu)", m_rampmin[i],
							m_rampmax[i], (unsigned long long)m_rampchg[i]);
				}
			}
			rr += string_format("  ||  NON-ZERO %u of 256 (%u of them below 0x20), MOVING %u", nz, nzlo, mv);
			{
				std::string ww;
				for (u32 i = 0; i < 0x100; i++)
					if (m_rampwrap[i])
						ww += string_format(" %02X:%llu wraps -> period %llu frames (%.4f Hz)",
								i, (unsigned long long)m_rampwrap[i],
								(unsigned long long)(m_frames_run / m_rampwrap[i]),
								48000.0 * double(m_rampwrap[i]) / double(m_frames_run));
				logerror("upd6383: ★★ §196 LFO WRAP CENSUS over %llu frames:%s\n",
						(unsigned long long)m_frames_run,
						ww.empty() ? "  NO CELL EVER WRAPS" : ww.c_str());
			}
			logerror("upd6383: ★★ §176 D-RAM CENSUS, ALL 32 CELLS, over %llu frames:%s\n",
					(unsigned long long)m_frames_run, rr.c_str());
		}
		for (int i = 0; i < m_c6_n; i++)
			logerror("upd6383: ★★ §162 CLASS-6 SITE %010llX addr8=%02X lo12=%03X : hits %llu | "
					"acc %lld .. %lld (%s) | m_dp %u..%u | cursor %u..%u\n",
					(unsigned long long)m_c6_word[i],
					unsigned((m_c6_word[i] >> 12) & 0xff), unsigned(m_c6_word[i] & 0xfff),
					(unsigned long long)m_c6_hits[i],
					(long long)m_c6_amin[i], (long long)m_c6_amax[i],
					(m_c6_amin[i] == m_c6_amax[i]) ? "CONSTANT -- phase is NOT here" : "VARIES",
					m_c6_pmin[i], m_c6_pmax[i], m_c6_cmin[i], m_c6_cmax[i]);
		for (int i = 0; i < m_c6_n; i++)
			logerror("upd6383:    §167 SAME SITE, THE TEMPS: tB %lld..%lld chg %llu (%s) | "
					"tA %lld..%lld | K %lld..%lld | L %lld..%lld\n",
					(long long)m_c6_tbmin[i], (long long)m_c6_tbmax[i],
					(unsigned long long)m_c6_tbchg[i],
					(m_c6_tbmin[i] == m_c6_tbmax[i]) ? "CONSTANT -- tB is NOT the index" : "VARIES",
					(long long)m_c6_tamin[i], (long long)m_c6_tamax[i],
					(long long)m_c6_kmin[i], (long long)m_c6_kmax[i],
					(long long)m_c6_lmin[i], (long long)m_c6_lmax[i]);
		for (int i = 0; i < m_a15w_n; i++)
			logerror("upd6383: ★★ §175 PER-SITE %010llX hits %llu | coef %lld..%lld nz %llu | "
					"L %lld..%lld nz %llu | P %lld..%lld | m_dp %u..%u  %s\n",
					(unsigned long long)m_a15w_word[i], (unsigned long long)m_a15w_hits[i],
					(long long)m_a15w_cmin[i], (long long)m_a15w_cmax[i], (unsigned long long)m_a15w_cnz[i],
					(long long)m_a15w_lmin[i], (long long)m_a15w_lmax[i], (unsigned long long)m_a15w_lnz[i],
					(long long)m_a15w_pmin[i], (long long)m_a15w_pmax[i],
					m_a15w_dmin[i], m_a15w_dmax[i],
					(!m_a15w_cnz[i] && !m_a15w_lnz[i]) ? "<= BOTH DEAD"
					: !m_a15w_cnz[i] ? "<= coef ALWAYS 0 -> CURSOR"
					: !m_a15w_lnz[i] ? "<= L ALWAYS 0 -> POINTER"
					: (m_a15w_pmin[i] == 0 && m_a15w_pmax[i] == 0) ? "<= operands live but P ALWAYS 0 (?!)"
					: "live");
		{
			std::string cl; u32 nc = 0, nnz = 0, tot = 0;
			for (u32 i = 0; i < 0x100; i++)
				if (m_hostw_cell[i])
				{
					nc++; tot += m_hostw_cell[i];
					if (m_hostw_nz[i]) nnz++;
					cl += string_format(" %02X:%u%s", i, m_hostw_cell[i],
							m_hostw_nz[i] ? "" : "(z)");
				}
			logerror("upd6383: §193 window samples REJECTED (slot in range, word not a window word): %llu\n",
				(unsigned long long)m_f31_reject);
		for (int i = 0; i < 9; i++)
			if (m_f31_hits[i])
				logerror("upd6383: ★★ §193 f31 WINDOW +%d (I-RAM %d) %010llX : hits %llu | "
						"acc %lld .. %lld chg %llu | slot %u..%u %s\n",
						i, 122 + i, (unsigned long long)m_f31_word[i],
						(unsigned long long)m_f31_hits[i],
						(long long)m_f31_amin[i], (long long)m_f31_amax[i],
						(unsigned long long)m_f31_achg[i], m_f31_smin[i], m_f31_smax[i],
						(m_f31_smin[i] == m_f31_smax[i]) ? "" : "⚠ POOLED");
		for (int i = 0; i < m_b11_n; i++)
			logerror("upd6383: ★★ §191 BIT-11 WORD %010llX (lo12 %03X sel %02X sub %d): hits %llu | "
					"m_dp %u..%u chg %llu (%s)\n",
					(unsigned long long)m_b11_word[i], unsigned(m_b11_word[i] & 0xfff),
					unsigned(m_b11_word[i] & 0xff), unsigned((m_b11_word[i] >> 8) & 7),
					(unsigned long long)m_b11_hits[i], m_b11_dmin[i], m_b11_dmax[i],
					(unsigned long long)m_b11_dchg[i],
					m_b11_dchg[i] ? "VARIES -- a reset here is observable"
					: "CONSTANT -- a reset would be unobservable");
		for (int b = 0; b < 2; b++)
		{
			std::string r;
			for (int k = 0; k < m_c2c_n[b]; k++)
				//  ⛔ §208: DO NOT PRINT A DERIVED CELL LABEL.  The old field
				//  `dsc%02X' = u8(m_dsc + ix) was +1 for body consumers -- §204's own
				//  output showed `ix3(dsc29,cell05A0)' while 0x05A0 is cell 0x28 --
				//  and §202 quoted two matches computed through it, so its
				//  "bit-exact" numbers were body-1 consumers reading body-0's block.
				//  ★ The base is not a simple register anyway: `dram-unit-cursor.md'
				//  (4440 survivors of 766 576 machines, all B1 = 0x00, L1 <= 0x26)
				//  makes it per-unit state established at the CALL, so `m_dsc + ix'
				//  is not the cell for unit 1 under ANY correction.
				//  ⇒ print the RAW INGREDIENTS and let the reader derive nothing.
				//  ★ §209: `cell' is now MEASURED -- recorded at the access site
				//  from dsc_cell(), the same value that indexed m_dscbank -- so it
				//  is printed again.  It is not a reconstruction from m_dsc.
				r += string_format(" iw%u:ix%u,cell%02X,val%04X", m_c2c_iw[b][k],
						m_c2c_ix[b][k], m_c2c_dsc[b][k], m_c2c_cell[b][k]);
			//  ⚠ §204 label fix: bucket 0 collects everything below I-RAM 200, which
			//  includes the KERNEL (0..59) and the epilogue, not only body 0.  The A/B
			//  compares like with like so the result stands, but the label was wrong
			//  and would mislead if the data were quoted elsewhere.
			logerror("upd6383: ★★ §204 CONSUMER->CELL %s (%d consumers, m_dsc=%02X):%s\n",
					b ? "unit 1 (I-RAM >= 200)" : "kernel + body 0 (I-RAM < 200)",
					m_c2c_n[b], m_dsc, r.c_str());
		}
		//  ★ §205: these two counters were incremented and NEVER PRINTED -- the
		//  project's own "every gate logs a fired-count" rule, breached for exactly
		//  the field (§133's f31=4/5 alias) whose decode is most contested.
		logerror("upd6383: ★★ §205 f31 alias counts: f31=4 %u | f31=5 %u  "
				"(mask bits 48-51 = %u; default runs 4 as LOAD, 5 as ADD)\n",
				m_bx_f4_n, m_bx_f5_n, u32((m_specmask >> 48) & 0xf));
		//  ★★★ §209: THE PER-UNIT DESCRIPTOR RING.  Two independent gates, each with
		//  its own fired count -- a null with no fired count cannot distinguish
		//  "did nothing" from "never ran", and this project has been bitten by that.
		//  ⚠ `wrap CHANGED the cell' is the number that matters: the ring is
		//  DESIGNED to be inert for unit 0 (its ring top 0x40 is never reached by
		//  any shipped algorithm), so a unit-0 firing would itself be a defect.
		logerror("upd6383: ★★★ §209 DESCRIPTOR RING: DSCPRE=%d applied %llu | "
				"DSCRING=%d evaluated %llu, wrapped %llu (unit 1: %llu, unit 0: %llu) | "
				"rings [%02X,%02X) unit 1 / [%02X,%02X) unit 0\n",
				m_dscpre ? 1 : 0, (unsigned long long)m_dscpre_n,
				m_dscring ? 1 : 0, (unsigned long long)m_dscring_seen,
				(unsigned long long)m_dscring_n, (unsigned long long)m_dscring_u1,
				(unsigned long long)(m_dscring_n - m_dscring_u1),
				DSC_RING1_BASE, DSC_RING1_TOP, DSC_RING0_BASE, DSC_RING0_TOP);
		//  ★ §209 falsifier 4, localised.  Unit 0's ring must be UNREACHABLE.
		if (m_dscring_n - m_dscring_u1)
			logerror("upd6383: ★★ §209 UNIT-0 WRAPS (must be pre-upload only): %llu total, "
					"%llu in a SETTLED frame (> 900k) | last at frame %llu of %llu | "
					"I-RAM %u..%u | raw cursor reached 0x%02X\n",
					(unsigned long long)(m_dscring_n - m_dscring_u1),
					(unsigned long long)m_dscring_u0_late,
					(unsigned long long)m_dscring_u0_lastframe,
					(unsigned long long)m_frames_run,
					m_dscring_u0_iwmin, m_dscring_u0_iwmax, m_dscring_u0_rawmax);
		logerror("upd6383: ★ §203 C-format class-1 descriptor consumption: FIRED %llu times\n",
				(unsigned long long)m_cfmtix_n);
		logerror("upd6383: ★ §201 per-body descriptor-index reset: FIRED %llu times\n",
				(unsigned long long)m_bodyix_n);
		for (int i = 0; i < m_age_n; i++)
			logerror("upd6383: ★★ §200 DELAY AGE dsc %02X: hits %llu | frames_since_written "
					"%u .. %u  (%.2f .. %.2f ms @44.1k)\n",
					m_age_dsc[i], (unsigned long long)m_age_hits[i], m_age_min[i], m_age_max[i],
					1000.0 * m_age_min[i] / 44100.0, 1000.0 * m_age_max[i] / 44100.0);
		logerror("upd6383: ★ §200 rotation sign FALLING (UPD6383_ROTSIGN): applied %llu times\n",
				(unsigned long long)m_rotsign_n);
		logerror("upd6383: ★ §197 0x0B poke packets accepted: %llu\n",
				(unsigned long long)m_pk_0b_n);
		logerror("upd6383: ★ §188 host payload LSB restored (mask bit 63 = %d): "
				"FIRED %llu of %llu packets (%.1f%%)\n",
				(m_specmask & (1ull << 63)) ? 1 : 0,
				(unsigned long long)m_pk_lsb_n, (unsigned long long)m_pk_lsb_seen,
				m_pk_lsb_seen ? 100.0 * double(m_pk_lsb_n) / double(m_pk_lsb_seen) : 0.0);
		logerror("upd6383: ★★ §186 HOST tag-0x15 WRITE TARGETS: %u writes over %u cells "
					"(%u ever non-zero) | 0x63 written %u times |%s\n",
					tot, nc, nnz, m_hostw_cell[0x63], cl.c_str());
		}
		logerror("upd6383: ★ §180 PTRD-A `lo12 == 0x1C0' suppressed from the walk "
				"(mask bit 62 = %d): FIRED %llu times\n",
				(m_specmask & (1ull << 62)) ? 1 : 0, (unsigned long long)m_ptrd_a_n);
		logerror("upd6383: ★★ §174 AT THE class-A ACT-0x15 MULTIPLY: fired %llu | "
				"coef %lld..%lld chg %llu nonzero %llu | L %lld..%lld chg %llu nonzero %llu | "
				"P %lld..%lld  => %s\n",
				(unsigned long long)m_a15_n,
				(long long)m_a15_cmin, (long long)m_a15_cmax,
				(unsigned long long)m_a15_cchg, (unsigned long long)m_a15_cnz,
				(long long)m_a15_lmin, (long long)m_a15_lmax,
				(unsigned long long)m_a15_lchg, (unsigned long long)m_a15_lnz,
				(long long)m_a15_pmin, (long long)m_a15_pmax,
				!m_a15_n ? "NEVER FIRED -- the word is not reached"
				: (!m_a15_lnz && !m_a15_cnz) ? "BOTH operands always zero"
				: !m_a15_lnz ? "L is ALWAYS ZERO -> the D-RAM read is empty -> POINTER (§168)"
				: !m_a15_cnz ? "coef is ALWAYS ZERO -> the coefficient is empty -> CURSOR"
				: "both operands live -- the product is NOT structurally zero");
		{
			static const char *const PW[8] = { "none", "ACT-05 raw", "ACT-07 shl",
					"ACT-05 raw(b)", "ACT-07 shl(b)", "§112 classA-ACT07", "THE MULTIPLY",
					"§40 m_k multiply" };
			for (int i = 0; i < m_c6_n; i++)
			{
				std::string who;
				for (int b2 = 0; b2 < 8; b2++)
					if (m_c6_pwseen[i] & (1u << b2)) { who += ' '; who += PW[b2]; }
				logerror("upd6383: ★★ §175 WHO LAST WROTE P AT THE LOOKUP:%s\n",
						who.empty() ? " (never observed)" : who.c_str());
			}
		}
		for (int i = 0; i < m_c6_n; i++)
			logerror("upd6383:    §169 SAME SITE, THE PRODUCT: P %lld..%lld chg %llu (%s)\n",
					(long long)m_c6_pmin2[i], (long long)m_c6_pmax2[i],
					(unsigned long long)m_c6_pchg[i],
					(m_c6_pchg[i] < 100) ? "NOT the index -- at most a few steps" : "VARIES per execution");
		logerror("upd6383: ★ §161 delay-word ACT-07 store re-aimed off addr8 "
				"(mask bit 61 = %d): FIRED %u times\n",
				(m_specmask & (1ull << 61)) ? 1 : 0, u32(m_dlystore_fix_n));
		logerror("upd6383: ★★ §160 REGISTER FILE, LFO WAVETABLE WINDOW 0x1D..0x40 "
					"(%u of 36 non-zero):%s\n", wnz, wt.c_str());
			std::string rf;
			u32 rnz = 0;
			for (u32 c = 0; c < 256; c++)
				if (m_rf[c] & 0xffffff)
				{ rf += string_format(" %02X=%06X", c, m_rf[c] & 0xffffff); rnz++; }
			logerror("upd6383:    §160 register file, ALL non-zero cells (%u):%s\n",
					rnz, rf.empty() ? " NONE" : rf.c_str());
		}
			logerror("            §99 MODE-1 STORES -> register file: %u cells%s\n",
					n, r.empty() ? " (none)" : r.c_str());
		}
	}
	logerror("        §41 LEVEL AT PRESENTATION: unit0 0x%06X (non-zero on %u), "
			"unit1 0x%06X (non-zero on %u)  [cold boot set 0x06=+0.5=0x400000, "
			"0x86=+0.183992=0x178D50]\n", m_lvl_seen[0], m_lvl_nz[0],
			m_lvl_seen[1], m_lvl_nz[1]);
	if (m_lvlguard_n)
		logerror("        §41 LEVEL GUARD: suppressed %u zero-stores onto the per-unit "
				"OUTPUT LEVEL registers 0x06/0x86\n", m_lvlguard_n);
	if (m_latchguard_n)
	{
		std::string gs;
		for (u32 i = 0; i < 384; i++)
			if (m_latchguard_slot[i]) gs += string_format(" iw%u:%u", i, m_latchguard_slot[i]);
		logerror("        §34 WHICH SLOTS store onto the latch:%s\n", gs.c_str());
	}
	if (m_latchguard_n)
	{
		for (u32 q = 0; q < m_lg_n; q++)
			logerror("        §36 residue: word %09llX  iw%u  mode %u  dest %02X  x%u\n",
					(unsigned long long)m_lg_word[q], m_lg_iw[q], m_lg_mode[q],
					m_lg_dest[q], m_lg_cnt[q]);
		logerror("        §36 LATCH ALARM: %u stores landed on the input window; NOT suppressed, "
				"and the input stays 100%% intact. Last %09llX\n", m_latchguard_n,
				(unsigned long long)m_latchguard_word);
	}
	if (m_in_frames == 0)
		logerror("        NOTHING ENTERED THE CHIP -- the input stage never ran to completion\n");
	else if (m_in_bad != 0)
		logerror("        *** THE DEPOSIT AND THE READ DISAGREE -- the cell map is wrong ***\n");

	if (m_order_valid)
	{
		logerror("    MOST RECENT REPRESENTATIVE FRAME: %u slots, %u DECODED,"
				" %u PARTIAL (addressing only), %u TRAP.\n",
				m_order_slots, m_order_slots - m_order_partials - m_order_total,
				m_order_partials, m_order_total);
		logerror("    %u words fully DECODED before the first undecoded one.  The first %u\n",
				m_order_before, m_order_n);
		logerror("    IN EXECUTION ORDER -- THIS IS THE DECODING WORKLIST.  `A' marks a word\n");
		logerror("    whose ADDRESSING was executed and whose ALU is what blocks the frame:\n");
		for (u32 i = 0; i < m_order_n; i++)
		{
			const u64 w = m_order_word[i];
			const bool k6 = upd6383_disassembler::addressing_only(w);
			logerror("      %2u.  iw %3u  %010X  %s  %s\n", i, m_order_iw[i], w,
					(k6 || upd6383_disassembler::has_addressing(w)) ? "A" : "-",
					upd6383_disassembler::text(w, int(m_order_iw[i])));
		}
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

			// the pointer LOADS -- absolute 8-bit immediates.  Matched by the
			// shared REGISTER-LOAD predicate (selector = lo12[7:0], payload flag
			// = bit 11) rather than by three literal lo12 constants, because
			// PROVEN BY CONSTRUCTION they are one route plus a modifier.
			if (upd6383_disassembler::is_regload(w) && upd6383_disassembler::lo_imm(w))
			{
				switch (upd6383_disassembler::lo_sel(w))
				{
				case 0x21: p821 = ad; break;
				case 0x27: p827 = ad; break;
				case 0x25: p825 = ad; break;
				default: break;
				}
			}

			// the shared predicate, so this instrument and the executor can no
			// longer disagree about which words move the pointer
			const bool moves = upd6383_disassembler::ptr_postinc(w);
			util::stream_format(f, "  %3u  %010X    %03X.%X.%02X.%03X   %-21s  %+4d  ",
					iw, w, hi, cl, ad, lo,
					upd6383_disassembler::hi12_text(hi), moves ? int(dd) : 0);

			auto col = [&f](int v) { if (v < 0) f << "  -- "; else util::stream_format(f, "  %02X ", v & 0xff); };
			col(p821); col(p827); col(p825);

			// the store -- LOGGED, never performed (one bit is not a decode)
			if ((hi & upd6383_disassembler::HI_ST) && !(hi & upd6383_disassembler::HI_ESC))
				f << "  ST->mem[p]";
			// FETCH IS NOT ADVANCE (K4, FORCED): bit 23 fetches, only class A
			// advances.  This column used to print `cur+' for both.
			if (upd6383_disassembler::cursor_fetch(w))
				f << (upd6383_disassembler::coeff_consumer(w) ? "  cur+" : "  cur");
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

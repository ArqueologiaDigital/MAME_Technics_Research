// license:GPL2+
// copyright-holders:Felipe Sanches
/***************************************************************************

    Technics KN5000 DSP1 Device (IC311 - NEC uPD6383GF-3BA)

    Parallel-host-interface digital signal processor used for audio effects.
    See kn5000_dsp.h for the part identification, the chip architecture, and
    why this device captures the host byte stream.

    Emulation status: HOST INTERFACE ONLY. The DSP core is not emulated -- no
    instruction set, no audio. This models enough of the uC-IF to accept the
    firmware's uploads without stalling it, and records them so the program
    image can be inspected offline.

***************************************************************************/

#include "emu.h"
#include "kn5000_dsp.h"

#include <cinttypes>
#include <fstream>

#define LOG_REG      (1U << 1)  // command/data bytes
#define LOG_UPLOAD   (1U << 2)  // completed transfers + group analysis

#define VERBOSE (0)
#include "logmacro.h"

DEFINE_DEVICE_TYPE(KN5000_DSP1, kn5000_dsp1_device, "kn5000_dsp1", "KN5000 DSP1 (NEC uPD6383GF-3BA)")


//**************************************************************************
//  DSP1 DEVICE
//**************************************************************************

kn5000_dsp1_device::kn5000_dsp1_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock)
	: device_t(mconfig, KN5000_DSP1, tag, owner, clock)
	, m_cmd(0)
	, m_addr_latch(0)
	, m_have_current(false)
{
}

void kn5000_dsp1_device::device_start()
{
	save_item(NAME(m_cmd));
	save_item(NAME(m_addr_latch));
	save_item(NAME(m_regs));
	// m_transfers / m_current are capture instrumentation, not chip state,
	// so they are deliberately not save-state items.
}

void kn5000_dsp1_device::device_reset()
{
	// NOTE: the firmware pulses reset (PH.1) before uploading, so a reset is
	// the natural transfer boundary -- close the open transfer rather than
	// discarding it, or the last upload before a reset would be lost.
	flush_transfer();

	m_cmd = 0;
	m_addr_latch = 0;
	std::fill(std::begin(m_regs), std::end(m_regs), 0);
}

void kn5000_dsp1_device::flush_transfer()
{
	if (!m_have_current)
		return;

	if (!m_current.payload.empty())
		m_transfers.push_back(m_current);

	m_have_current = false;
	m_current.payload.clear();
}

//-------------------------------------------------
//  host_w - the real uC-IF (Sub CPU port PZ)
//-------------------------------------------------

void kn5000_dsp1_device::host_w(bool cd, uint8_t data)
{
	if (!cd)
	{
		// Command byte: ends whatever data run preceded it.
		flush_transfer();

		m_cmd = data;
		m_current.cmd = data;
		m_current.payload.clear();
		m_have_current = true;

		LOGMASKED(LOG_REG, "DSP1 CMD 0x%02X\n", data);
		return;
	}

	if (!m_have_current)
	{
		// Data with no preceding command: still captured, flagged with a
		// sentinel so it is not silently merged into the next run.
		m_current.cmd = 0xff;
		m_current.payload.clear();
		m_have_current = true;
	}
	m_current.payload.push_back(data);

	LOGMASKED(LOG_REG, "DSP1 cmd 0x%02X data[%u] <- 0x%02X\n",
			m_cmd, unsigned(m_current.payload.size() - 1), data);
}


//-------------------------------------------------
//  0x130000 register block -- NOT the uC-IF
//-------------------------------------------------

void kn5000_dsp1_device::reg_addr_w(uint16_t data)
{
	m_addr_latch = data & 0xff;
	LOGMASKED(LOG_REG, "DSP1 reg addr latch: 0x%02X\n", m_addr_latch);
}

void kn5000_dsp1_device::reg_data_w(uint16_t data)
{
	uint8_t const val = data & 0xff;
	m_regs[m_addr_latch] = val;
	LOGMASKED(LOG_REG, "DSP1 reg[0x%02X] <- 0x%02X\n", m_addr_latch, val);
}

uint16_t kn5000_dsp1_device::reg_data_r()
{
	uint16_t const val = m_regs[m_addr_latch];
	LOGMASKED(LOG_REG, "DSP1 reg[0x%02X] -> 0x%02X\n", m_addr_latch, val);
	return val;
}

void kn5000_dsp1_device::device_stop()
{
	flush_transfer();

	if (m_transfers.empty())
		return;

	// Two artefacts, written next to the working directory:
	//   .bin - raw payload bytes, concatenated, for a disassembler to chew on
	//   .txt - one line per transfer with the group-width analysis
	// The .txt is the interesting one: a payload whose length is a multiple of
	// 5 is a candidate I-RAM instruction run (36-bit words in 40-bit
	// containers); a multiple of 3 is a candidate C-RAM/D-RAM run (24-bit).
	// Both divide 15, so lengths that are multiples of 15 are AMBIGUOUS and
	// are reported as such rather than being claimed for either.
	std::ofstream bin("kn5000_dsp1_upload.bin", std::ios::binary);
	std::ofstream txt("kn5000_dsp1_upload.txt");

	if (!txt)
		return;

	txt << "KN5000 DSP1 (uPD6383GF-3BA) host uploads\n";
	txt << "I-RAM capacity is " << IRAM_WORDS << " words of 36 bits; a program may use FEWER,\n";
	txt << "so a run of N groups-of-5 with N <= " << IRAM_WORDS << " is plausible. The evidence to look\n";
	txt << "for is N VARYING BY EFFECT ALGORITHM -- fixed-size register traffic would not.\n";
	txt << "5 bytes = one 36-bit I-RAM word, 3 bytes = one 24-bit C-RAM/D-RAM word (confirmed:\n";
	txt << "the ROM handlers divide by literal 5 and 3, and captured uploads tile I-RAM exactly).\n\n";

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

	osd_printf_info("KN5000 DSP1: wrote %u transfers (%u bytes) to kn5000_dsp1_upload.{bin,txt}\n",
			unsigned(m_transfers.size()), unsigned(total));
}

// license:BSD-3-Clause
// copyright-holders:Felipe Sanches
/*
    Panasonic MN10300 (AM33) CPU core - SKELETON

    Derived from the MAME MN10200 CPU device (src/devices/cpu/mn10200/).
    Only the device boilerplate is filled in; the instruction decoder in
    execute_run() is a stub. Everything that differs from the MN10200 is
    flagged with TODO(MN10300).
*/

#ifndef MAME_CPU_MN10300_MN10300_H
#define MAME_CPU_MN10300_MN10300_H

#pragma once

#include "mn10300_timing.h"

// Debugger/state-table indices (unique, non-zero; value order is cosmetic)
enum
{
	MN10300_PC = 1,
	MN10300_PSW,
	MN10300_MDR,
	MN10300_SP,
	MN10300_D0, MN10300_D1, MN10300_D2, MN10300_D3,
	MN10300_A0, MN10300_A1, MN10300_A2, MN10300_A3,
	MN10300_TINSN, MN10300_TMEM, MN10300_TICMISS, MN10300_TDCMISS   // timing-model counters
	// TODO(MN10300/AM33): E0..E7, MDRQ, LIR/LAR, MCRH/MCRL/MCVF, SSP/MSP/USP, ...
};

// External interrupt input lines (placeholder; wire to KN7000 IRQ sources)
enum
{
	MN10300_IRQ0 = 0,
	MN10300_IRQ1,
	MN10300_IRQ2,
	// TODO(MN10300): real NMI + maskable IRQ-group layout
	MN10300_MAX_EXT_IRQ
};


class mn10300_device : public cpu_device
{
public:
	// construction/destruction (single concrete, instantiable device)
	mn10300_device(const machine_config &mconfig, const char *tag, device_t *owner, uint32_t clock);

	// Legacy external-INTC hooks (the on-chip INTC now lives in this core; these
	// remain so a machine may still override the vector/level directly -- the
	// KN7000 driver used them before the INTC-in-core migration). The core's own
	// INTC recompute/accept paths overwrite both from the per-level vector table.
	void set_irq_vector(uint32_t v) { m_irq_vector = v; }
	void set_irq_level(int l) { m_irq_level = l; }

	// ---- on-chip interrupt controller (INTC) @ 0x34000100 ------------------
	//
	// Byte-exact port of the KN7000 driver's proven HLE (kn7000.cpp intc_r/
	// intc_w/intc_assert/intc_recompute/irq_ack before the INTC-in-core
	// refactor); the behavior was reverse-engineered from the KN7000 firmware
	// (kn7000_mame overlay: notes/interrupt-mechanism.md).
	//
	// GxICR(group) = 0x34000100 + group*4 (16-bit): bits 3:0 DETECT, bit4
	// REQUEST, bit8 ENABLE, bits 14:12 LEVEL. A source is pending when its
	// REQUEST bit is set; the maskable line is asserted while any
	// ENABLE&REQUEST source exists; among pending groups the winner is the
	// LOWEST level value (highest priority). Quirks preserved from the HLE:
	//  * 0x34000100/0x104 double as the IAGR the (self-loaded) library
	//    dispatcher reads: 0x34000100 returns the latched group << 3; the
	//    0x34000200 group register returns it << 2. Both latch at the accept
	//    instant (real INTC latches IAGR at acknowledge).
	//  * GxICR write: high byte (ENABLE+LEVEL) stored as written; DETECT bits
	//    are write-1-to-clear, limited to the byte lanes actually written;
	//    REQUEST is derived from the surviving DETECT bits.
	//  * group 0x17 software-trigger self-ack: writing DETECT bit0 latches
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
	void intc_assert(int group);                  // set DETECT bit0 + REQUEST, recompute delivery
	// The KN7000 effects-DSP handshake on group 0x17 (see intc_w): with the self-ack on (the
	// default), a firmware write that clears the group answers at once, as a DSP that grants
	// the bus immediately does (host boot). With it off, the write clears DETECT like any other
	// group, and the board raises the request itself (intc_assert) when the DSP lets the host in.
	void set_dsp_handshake_selfack(bool on) { m_g17_selfack = on; }
	// Raw ICR access for POLLED lines a board drives directly (e.g. the KN7000
	// SD card-detect pin on group 0x1B). Deliberately NO recompute -- byte-
	// exact with the driver HLE's direct m_gxicr pokes (such polled lines never
	// have ENABLE set, so delivery is unaffected).
	uint16_t intc_icr(int group) const { return m_gxicr[group & 0x1f]; }
	void intc_icr_set(int group, uint16_t bits) { m_gxicr[group & 0x1f] |= bits; }
	void intc_icr_clear(int group, uint16_t bits) { m_gxicr[group & 0x1f] &= ~bits; }
	// Per-level maskable vector table (see the delivery note above).
	void set_maskable_vector(int level, uint32_t vector) { m_level_vector[level & 7] = vector; }
	// Outward event callbacks (all optional):
	//   intc_ack_cb    (write8, data = group): a GxICR write carried DETECT-ack
	//        bits (data & mem_mask & 0x000f). The KN7000 uses it for the panel
	//        transfer-complete "level-like until serviced" re-delivery (its
	//        c11_unserviced flag + deferred re-assert stay driver-side).
	//   intc_accept_cb (write8, data = group): this group was latched into the
	//        IAGR at interrupt accept (KN7000: group 0x11 accept clears the
	//        c11_unserviced flag).
	//   intc_extmd_cb  (write16): new EXTMD value after each write (the driver
	//        keeps its own previous-value shadow to decode transitions).
	auto intc_ack_cb() { return m_intc_ack_cb.bind(); }
	auto intc_accept_cb() { return m_intc_accept_cb.bind(); }
	auto intc_extmd_cb() { return m_intc_extmd_cb.bind(); }

	// ---- on-chip serial (SIO): three channels @ 0x34000800/0x810/0x820 -----
	//
	// Modeled in the core, following the MN10200 core's precedent (its on-chip
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
	//   +4  control  (byte)
	//   +8  TX data  (byte, write; the data write itself clocks one transfer)
	//   +9  RX data  (byte, read; pops the 64-byte RX FIFO)
	//   +C  status   bit4 = RxRDY only. ch2's bit7 (RX-empty) / bit6 (TxRDY)
	//                are deliberately NOT modeled (doing so wedged boot).
	//
	// Interrupt-worthy events are routed OUT through per-channel callbacks and
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
	// Unbound callbacks are no-ops, so a machine may wire only what it needs.
	template <unsigned Ch> auto sio_tx_cb() { return m_sio_tx_cb[Ch].bind(); }
	template <unsigned Ch> auto sio_tx_done_cb() { return m_sio_tx_done_cb[Ch].bind(); }
	template <unsigned Ch> auto sio_rx_rdy_cb() { return m_sio_rx_rdy_cb[Ch].bind(); }
	template <unsigned Ch> auto sio_rx_enable_cb() { return m_sio_rx_enable_cb[Ch].bind(); }

	// The on-chip DMA controller's channel 0 is driven by an external request
	// (the floppy controller's DRQ); when its byte count runs out the channel
	// pulses terminal count back to the requesting device. Ported from upstream
	// MAME (#16394, cpu/mn10300 + matsushita/kn7000).
	auto dma_tc_cb() { return m_dma_tc_cb.bind(); }
	void dma_req_w(int state);

	// Endpoint devices (panel HLE, MIDI UART bridges) deliver received bytes
	// here; each successful push fires sio_rx_rdy_cb for that channel.
	void sio_rx_push(int ch, uint8_t data);
	bool sio_rx_ready(int ch) const { return m_sio_rx_head[ch] != m_sio_rx_tail[ch]; }

	// ---- on-chip 16-bit timers @ 0x34001080 (TM4/TM5 pair) -----------------
	//
	// Byte-exact port of the KN7000 driver's "tempo timer" model (kn7000.cpp
	// tmr7_* -- named after its INTC group there; the register addresses are
	// the AM33 TM5: mode byte @0x34001082, 16-bit reload @0x34001092, down-
	// counter @0x340010A2). TM5 underflow asserts INTC group 7 = the KN7000
	// firmware's 96-PPQN sequencer tick (and the KN6000/KN6500 firmware's
	// ms-counter tick -- both program THIS timer). TM5BC writes fall through
	// to the machine map (the driver mapped the counter window read-only).
	// Full RE in the members' comments and kn7000_mame notes/sequenced-
	// playback-and-style-data-rootcause.md.
	//
	// TM4, the other half of each register word (offset 0 of each window:
	// mode @0x34001080, reload @0x34001090, down-counter @0x340010A0), counts
	// the same way. The KN7000 firmware programs it for its 1 kHz system tick
	// (893 0x484D707F, 941 0x484D728C: reload 0x7D0, mode 0x81, so a period of
	// 2001 counts at 2 MHz) and never reads it; on Felipe's unit the DSP
	// probe's pass 8 read its counter as a fine clock (2,000 down to 0 between
	// ticks). Its underflow asserts the INTC group the board sets here (the
	// KN7000: group 6, the scheduler tick); -1, the default, asserts nothing.
	void set_tm4_irq_group(int group) { m_tm4_irq_group = group; }

protected:
	// device_t overrides
	virtual void device_start() override ATTR_COLD;
	virtual void device_reset() override ATTR_COLD;
	virtual void device_post_load() override ATTR_COLD;

	// device_execute_interface overrides
	virtual uint32_t execute_min_cycles() const noexcept override { return 1; }
	// worst single instruction: a 38-cycle div, or a movm of the whole register set whose
	// stack lines all miss to slow memory (mn10300_timing.h). A hint for the scheduler only.
	virtual uint32_t execute_max_cycles() const noexcept override { return 400; }
	// (device_execute_interface::execute_input_lines() was removed from MAME;
	//  the input-line count is implicit. MN10300_MAX_EXT_IRQ lines are still used
	//  via set_input_line/execute_set_input.)
	virtual void execute_run() override;
	virtual void execute_set_input(int inputnum, int state) override;
	virtual bool execute_input_edge_triggered(int inputnum) const noexcept override { return inputnum == INPUT_LINE_NMI; }
	// The device clock is the core clock fc (the KN7000: 16 MHz x 4 = 64 MHz), one cycle per
	// clock; the peripherals run on IOCLK = fc / mn10300_timing::IOCLK_DIV (ioclk()).

	// device_memory_interface overrides
	virtual space_config_vector memory_space_config() const override;

	// device_state_interface overrides
	virtual void state_import(const device_state_entry &entry) override;
	virtual void state_export(const device_state_entry &entry) override;
	virtual void state_string_export(const device_state_entry &entry, std::string &str) const override;

	// device_disasm_interface overrides
	virtual std::unique_ptr<util::disasm_interface> create_disassembler() override;

private:
	static constexpr unsigned NUM_SIO = 3;

	// ---- address space -----------------------------------------------------
	// Flat 32-bit little-endian space with a 32-bit data bus. The internal map
	// decodes the on-chip peripherals: the INTC (0x34000100-0x340002FF), the
	// SIO (0x34000800-0x3400082F) and the TM4/TM5 timer windows (0x34001080/
	// 0x34001090/0x340010A0, 4 bytes each); the rest of the machine is mapped
	// by the driver. MAME appends a device's internal map AFTER the driver's
	// map ("last so it takes priority" -- src/emu/addrmap.cpp), so these
	// windows layer cleanly over any driver-side entries.
	void internal_map(address_map &map) ATTR_COLD;
	address_space_config m_program_config;
	address_space *m_program;

	// ---- on-chip SIO state (see the public section for the register model) --
	uint16_t sio_r(offs_t offset, uint16_t mem_mask = ~0);
	void sio_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);
	void sio_tx_byte(int ch, uint8_t data);
	uint8_t sio_rx_pop(int ch);

	devcb_write8::array<NUM_SIO>     m_sio_tx_cb;
	devcb_write_line::array<NUM_SIO> m_sio_tx_done_cb;
	devcb_write_line::array<NUM_SIO> m_sio_rx_rdy_cb;
	devcb_write_line::array<NUM_SIO> m_sio_rx_enable_cb;

	uint16_t m_sio_config[NUM_SIO];
	uint8_t  m_sio_control[NUM_SIO];
	uint8_t  m_sio_rx_fifo[NUM_SIO][64];   // small RX ring buffer per channel
	uint8_t  m_sio_rx_head[NUM_SIO];
	uint8_t  m_sio_rx_tail[NUM_SIO];

	// ---- on-chip INTC state (see the public section for the model) ---------
	static constexpr unsigned NUM_INTC_GROUPS = 0x20;
	uint16_t intc_r(offs_t offset, uint16_t mem_mask = ~0);
	void intc_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);
	void intc_recompute();       // re-arbitrate + drive the maskable line/vector
	void intc_accept();          // latch IAGR (group+vector) at interrupt accept
	int  intc_pending_group() const;

	devcb_write8  m_intc_ack_cb;
	devcb_write8  m_intc_accept_cb;
	devcb_write16 m_intc_extmd_cb;

	uint16_t m_gxicr[NUM_INTC_GROUPS];
	bool     m_g17_selfack = true;   // see set_dsp_handshake_selfack
	int      m_iagr_latch;       // group latched at interrupt accept
	uint16_t m_intc_280;         // 0x34000280 (EXTMD) latched control fields
	uint32_t m_level_vector[8];  // per-level maskable vector (board-configured)

	// ---- on-chip TM4/TM5 timer state (see the public section) --------------
	uint16_t tm45_mode_r(offs_t offset);
	void tm45_mode_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);
	uint16_t tm45_base_r(offs_t offset);
	void tm45_base_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);
	uint16_t tm45_count_r(offs_t offset);
	void tm4_mode_w(uint8_t data);
	void tm4_base_w(uint16_t data);
	void tm4_rearm(bool restart_phase);
	TIMER_CALLBACK_MEMBER(tm4_tick);
	void tm5_mode_w(uint8_t data);
	void tm5_base_w(uint16_t data);
	void tm5_rearm(bool restart_phase);
	TIMER_CALLBACK_MEMBER(tm5_tick);

	// ---- 16-bit timer 6 (mode 0x34001084, 0x340010B4, compare A 0x340010C4) ----
	// The KN6000/KN6500 tempo timer (see tm6_mode_w).
	uint16_t tm6_mode_r(offs_t offset);
	void tm6_mode_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);
	uint16_t tm6_mda_r(offs_t offset);
	void tm6_mda_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);
	uint16_t tm6_ca_r(offs_t offset);
	void tm6_ca_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);
	void tm6_rearm(bool restart_phase);
	TIMER_CALLBACK_MEMBER(tm6_tick);

	static constexpr unsigned TM5_PRESCALE = 8;  // IOCLK / 8 = 2 MHz on the KN7000 (see tm5_rearm)
	uint32_t ioclk() const;                      // the peripheral clock (16 MHz on the KN7000)

	uint8_t   m_tm4_mode;        // TM4: as TM5
	uint16_t  m_tm4_base;
	emu_timer *m_tm4_timer;
	int       m_tm4_irq_group = -1;  // board configuration (set_tm4_irq_group), not runtime state
	uint8_t   m_tm5_mode;        // bit7 = count enable, bit6 = load pulse, low bits = source/prescale
	uint16_t  m_tm5_base;        // 16-bit reload (underflow period)
	emu_timer *m_tm5_timer;
	uint16_t  m_tm6_mode;        // bit15 = count enable, bit14 = load pulse, low bits = clock source
	uint16_t  m_tm6_mda;         // 0x340010B4 (low byte): compare/capture mode, stored only
	uint16_t  m_tm6_ca;          // compare A: the counter clears on a match (the period)
	emu_timer *m_tm6_timer;

	// ---- on-chip DMA controller, channel 0 (registers at 0x32000800) --------
	uint32_t dmac_r(offs_t offset);
	void dmac_w(offs_t offset, uint32_t data, uint32_t mem_mask = ~0);
	TIMER_CALLBACK_MEMBER(dma_transfer);

	devcb_write_line m_dma_tc_cb;
	emu_timer *m_dma_timer;
	uint32_t m_dma_ctrl;
	uint32_t m_dma_src;
	uint32_t m_dma_dst;
	uint16_t m_dma_count;
	uint32_t m_dma_remain;
	bool m_dma_active;
	bool m_dma_started;
	bool m_dma_drq;

	// ---- timing model (the numbers: mn10300_timing.h) ------------------------
	// Time is charged in quarter cycles. Per instruction (timing_pre): the instruction
	// cache, the fetch queue, a load-use stall, and the fixed execute cost; handlers add
	// control flow and data-dependent costs. Data accesses add cache misses and write-backs,
	// uncached bus time per chip select (measured on the unit, pass 9), and on-chip register
	// time. Caches hold tags only: data always comes from the address space.
	uint16_t chctr_r(offs_t offset);
	void chctr_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);
	uint16_t memctr_r(offs_t offset);
	void memctr_w(offs_t offset, uint16_t data, uint16_t mem_mask = ~0);
	uint32_t dcache_purge_r(offs_t offset);
	void timing_recompute_cs(int cs);
	void icache_invalidate();
	void dcache_invalidate();
	inline void charge(int quarters);
	inline void timing_pre(uint32_t pc, uint8_t op);
	inline int data_cost(uint32_t a, bool wide, bool write);   // charges; returns the load-use latency
	inline void loaded(unsigned regs);                         // a single load wrote these registers
	inline int dcache_access(uint32_t a, bool wide, bool write, int cs);
	inline int line_fill_cost(uint32_t a, int cs);
	inline int line_writeback_cost(uint32_t tag);

	static constexpr unsigned NSETS = 128;          // mn10300_timing::SETS
	uint16_t m_memctr[8];          // MEMCTR0-7 (0x32000020 + 2n), as the firmware wrote them
	uint16_t m_chctr;              // CHCTR (0x20000070)
	int      m_cs_rd16[8], m_cs_rd32[8];   // quarter cycles beyond a hit: one uncached load,
	int      m_cs_wr16[8], m_cs_wr32[8];   //   one uncached store, of 8/16 and of 32 bits on CSn,
	int      m_cs_fill[8], m_cs_wb[8];     //   a line fill, and a dirty line's write-back
	int      m_qacc;               // quarter cycles not yet taken from m_icount (0-3)
	uint64_t m_qclock;             // quarter cycles charged since start (the queue and load-use clock)
	int      m_fq;                 // fetch queue fill, in 1/FQ_UNIT bytes
	uint64_t m_fq_qclock;          // m_qclock when the current instruction started executing
	uint32_t m_seq_pc;             // where the next instruction starts if nothing jumps
	unsigned m_ld_dst;             // registers the last single load wrote (0: none pending)
	uint64_t m_ld_ready;           // m_qclock when that load's data can be used
	int      m_ld_lu;              // load-use latency of the last data read (set by read_mem*)
	uint32_t m_ic_tag[NSETS * 2];  // line address (addr >> 4) per set and way; ~0 = invalid
	uint8_t  m_ic_lru[NSETS];      // the way to replace next
	uint32_t m_dc_tag[NSETS * 2];
	uint8_t  m_dc_dirty[NSETS * 2];
	uint8_t  m_dc_lru[NSETS];
	uint32_t m_ic_line;            // the line the last instruction was fetched from (~0: none)
	// Counters for measuring the model (debugger state TINSN, TMEM, TICMISS, TDCMISS; Lua
	// reads them as manager.machine.devices[":maincpu"].state["TMEM"].value). Not saved.
	uint64_t m_cnt_insn;           // instructions executed
	uint64_t m_cnt_mem;            // QUARTER cycles memory added beyond the cache-hit counts
	uint64_t m_cnt_icmiss;         // instruction-cache line fills
	uint64_t m_cnt_dcmiss;         // data-cache line fills

	// ---- architectural state ----------------------------------------------
	uint32_t m_pc;    // full 32-bit PC (MN10200 was 24-bit, masked to 0xffffff)
	uint32_t m_d[4];  // data registers D0..D3 (full 32-bit)
	uint32_t m_a[4];  // address registers A0..A3 (full 32-bit)
	uint32_t m_e[8];  // AM33 extended data registers E0..E7 (saved by movm ext groups)
	uint32_t m_sp;    // dedicated stack pointer (MN10200 reused A3 as the stack)
	uint32_t m_mdr;   // multiply/divide register (32-bit on MN10300; 16-bit on MN10200)
	uint32_t m_mdrq;  // AM33 extended multiply/quotient register (getx/putx)
	uint32_t m_mcrh;  // AM33 MAC accumulator high (getchx / putchclx / mac)
	uint32_t m_mcrl;  // AM33 MAC accumulator low  (getclx / putchclx / mac)
	uint32_t m_mcvf;  // AM33 MAC overflow flag
	uint16_t m_psw;   // processor status word
	uint32_t m_lir;   // loop-instruction register (setlb) - modelled for movm completeness
	uint32_t m_lar;   // loop-address register     (setlb)
	// TODO(MN10300/AM33): extended registers E0..E7, MDRQ, register banks.

	// ---- interrupt state ---------------------------------------------------
	// The on-chip interrupt controller (0x34000100 block, above) drives the
	// single maskable IRQ input line and supplies the address the AM33 maskable
	// vector jumps to (per-level table). On accept the core latches IAGR, pushes
	// PC+PSW and clears IE; the (self-loaded library-ROM) handler reads IAGR,
	// dispatches, acks, and returns via rti. See notes/interrupt-mechanism.md.
	bool     m_possible_irq; // an IRQ may be serviceable; re-checked at the loop top
	int      m_irq_state;    // latched maskable IRQ line (execute_set_input)
	uint32_t m_irq_vector;   // where the maskable interrupt vectors to
	int      m_irq_level = 7; // priority level of the pending interrupt (0 = highest)
	bool     m_nmi_state = false;   // NMI pin level (execute_set_input)
	bool     m_nmi_pending = false; // a rising NMI edge not yet taken

	int m_icount;     // remaining cycles this timeslice (MN10200 named this m_cycles)

	// ---- opcode/operand fetch (mirror MN10200: byte-assembled => alignment safe) ---
	inline uint8_t  read_arg8 (uint32_t address) { return m_program->read_byte(address); }
	inline uint16_t read_arg16(uint32_t address) { return m_program->read_byte(address) | (m_program->read_byte(address + 1) << 8); }
	inline uint32_t read_arg24(uint32_t address) { return m_program->read_byte(address) | (m_program->read_byte(address + 1) << 8) | (m_program->read_byte(address + 2) << 16); }
	inline uint32_t read_arg32(uint32_t address) { return read_arg24(address) | (m_program->read_byte(address + 3) << 24); } // TODO(MN10300): 32-bit imm/disp

	// ---- data-side memory accessors (32-bit bus) ---------------------------
	// TODO(MN10300): decide alignment policy; read_word/read_dword on a byte-
	// granular little-endian space handle any offset. MN10200 forced (addr & ~1).
	// Each charges the access's time first (data_cost; defined in mn10300.cpp).
	inline uint8_t  read_mem8 (uint32_t address);
	inline uint16_t read_mem16(uint32_t address);
	inline uint32_t read_mem32(uint32_t address);
	inline uint32_t read_stack32(uint32_t address);
	inline uint8_t  read_rmw8(uint32_t address);   // bset/bclr/btst
	inline void write_mem8 (uint32_t address, uint8_t  data);
	inline void write_mem16(uint32_t address, uint16_t data);
	inline void write_mem32(uint32_t address, uint32_t data);

	inline void change_pc(uint32_t pc) { m_pc = pc; } // TODO(MN10300): full 32-bit PC, no 0xffffff mask

	// ---- flag / arithmetic helpers (32-bit) --------------------------------
	inline void set_nz32(uint32_t r);
	inline uint32_t do_add(uint32_t a, uint32_t b, uint32_t carry_in);
	inline uint32_t do_sub(uint32_t a, uint32_t b, uint32_t borrow_in);
	inline bool test_cond(int cc);

	// ---- stack + register-list helpers -------------------------------------
	inline void push32(uint32_t val);
	inline uint32_t pop32();
	void store_regs(uint8_t mask);   // movm push (SP moves)
	void load_regs(uint8_t mask);    // movm pop  (SP moves)
	// call/ret/retf use the AM33 imm8-total frame convention: the return PC sits at
	// [SP] and the saved registers at fixed negative offsets below it; SP is moved
	// only by imm8. These write/read the register block at those offsets WITHOUT
	// moving SP (mirrors the GDB simulator's ret/retf offset walk).
	void store_regs_at(uint32_t base, uint8_t mask); // call: regs -> [base-4], [base-8], ...
	void load_regs_at(uint32_t base, uint8_t mask);  // ret/retf: [base-4], ... -> regs

	// ---- prefixed-opcode group handlers ------------------------------------
	void execute_f0();   // 0xF0: reg-indirect moves + call/jmp/ret (aM)
	void execute_f1();   // 0xF1: cross-type reg-reg arithmetic
	void execute_f2();   // 0xF2: logical / mul / div / shift / special-reg moves
	void execute_f3();   // 0xF3: 32-bit indexed load/store (dI,aM)
	void execute_f4();   // 0xF4: byte/half indexed load/store (dI,aM)
	void execute_f5();   // 0xF5: AM33 DSP puts (putx/putchclx) etc.
	void execute_f6();   // 0xF6: AM33 DSP ops (mulq/getx/getchx/getclx/sat...)
	void execute_f8();   // 0xF8: imm8  / disp8  forms
	void execute_fa();   // 0xFA: imm16 / disp16 forms
	void execute_fc();   // 0xFC: imm32 / disp32 / abs32 forms
	void execute_fe();   // 0xFE: bit ops on absolute address

	// shift/logical flag helpers
	inline void set_logic_flags(uint32_t r);   // and/or/xor/not: Z,N; clear V

	// typed memory transfer used by the F8/FA/FC (disp,aM)/(disp,sp)/(abs) moves.
	// type: 0/1 = 32-bit mov (a-reg iff a_reg), 2 = movbu (byte), 3 = movhu (half).
	inline void typed_load_store(int type, bool a_reg, int reg, uint32_t ea, bool store);
	inline void do_shift(int op, int dst, uint32_t count);  // 0=asl 1=lsr 2=asr

	// ---- interrupts (stubs) ------------------------------------------------
	void check_irq();
	void take_irq(int level, int group);
	void take_nmi();
};

DECLARE_DEVICE_TYPE(MN10300, mn10300_device)

#endif // MAME_CPU_MN10300_MN10300_H

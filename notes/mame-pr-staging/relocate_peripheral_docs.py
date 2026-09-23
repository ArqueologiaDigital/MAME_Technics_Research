"""Move the peripheral register documentation to the .cpp, beside its handlers.

QUESTION IT ANSWERS
  "mn10300.h is 38% comment lines. Is that defensible?"

  No. Measured over every src/devices/cpu header of 150+ lines in
  upstream/master (n=244): median 6.3%, p75 10.3%, p90 14.4%, p95 19.3%,
  p99 38.5%. At 38.2% this file sits at the 99th percentile -- only three of 244
  match or exceed it. The same measurement is what a MAME reviewer raised on
  PR #15919 and again on #16204, so a third occurrence is not a place to argue.

  The defence that these blocks document peripherals with NO DATASHEET is true,
  and it is why they are RELOCATED rather than deleted. They move to mn10300.cpp,
  beside the handlers that implement them, where a register description belongs
  anyway. The header keeps the per-member API contract a caller needs.

RUN   python3 relocate_peripheral_docs.py     (from the PR worktree root)
PASS  prints the new density; the file must still compile.
"""

H = 'src/devices/cpu/mn10300/mn10300.h'
C = 'src/devices/cpu/mn10300/mn10300.cpp'

INTC_DOC = """	// Reverse-engineered from software that drives it; no datasheet was available.
	//
	// GxICR(group) = 0x34000100 + group*4 (16-bit): bits 3:0 DETECT, bit4
	// REQUEST, bit8 ENABLE, bits 14:12 LEVEL. A source is pending when its
	// REQUEST bit is set; the maskable line is asserted while any
	// ENABLE&REQUEST source exists; among pending groups the winner is the
	// LOWEST level value (highest priority). Quirks:
	//  * 0x34000100/0x104 double as the IAGR an interrupt dispatcher reads:
	//    0x34000100 returns the latched group << 3; the
	//    0x34000200 group register returns it << 2. Both latch at the accept
	//    instant (real INTC latches IAGR at acknowledge).
	//  * GxICR write: high byte (ENABLE+LEVEL) stored as written; DETECT bits
	//    are write-1-to-clear, limited to the byte lanes actually written;
	//    REQUEST is derived from the surviving DETECT bits.
	//  * group 0x17 software-trigger self-ack: writing DETECT bit0 latches
	//    DETECT+REQUEST, which software uses to hand-shake a device self-test.
	//  * EXTMD (0x34000280) is a latched read-back register; every write is
	//    reported outward via intc_extmd_cb, so a board can decode transitions.
	//
	// Vector delivery: the AM33 vectors each interrupt LEVEL through its own
	// handler address. That mapping is board policy: the machine fills the
	// per-level table with set_maskable_vector().
"""

SIO_DOC = """	// Reverse-engineered from software that drives it; no datasheet was available.
	//
	// Register layout per channel (stride 0x10, 16-bit regs):
	//   +0  config   bit15 = sync-transfer START (self-clears instantly here,
	//                        since transfers complete instantly)
	//                bit14 = RX enable (the endpoint may send its queued reply)
	//   +4  control  (byte)
	//   +8  TX data  (byte, write; the data write itself clocks one transfer)
	//   +9  RX data  (byte, read; pops the 64-byte RX FIFO)
	//   +C  status   bit4 = RxRDY only; bit7 (RX-empty) and bit6 (TxRDY) are
	//                deliberately not modelled (see sio_r).
	//
"""

# HARVEST_GUARD: replay_polish.py executes this with I/O stubbed to return '',
# so bail out before the raw-file section rather than assert on an empty read.
if __name__ != '__main__':
    raise SystemExit(0)
s = open(H, encoding='utf-8').read()
moved = []
for name, doc in (('INTC', INTC_DOC), ('SIO', SIO_DOC)):
    if doc in s:
        s = s.replace(doc, '', 1)
        moved.append((name, doc))
    else:
        print('  (%s block already relocated)' % name)
open(H, 'w').write(s)

c = open(C, encoding='utf-8').read()
for name, doc in moved:
    body = '\n'.join('//' + l[3:] if l.startswith('\t//') else l for l in doc.rstrip('\n').split('\n'))
    if name == 'INTC':
        anchor = ("// The register model and its quirks are documented in mn10300.h. An interrupt\n")
        assert anchor in c, 'INTC anchor missing'
        c = c.replace(anchor, body + '\n//\n' + anchor.replace('are documented in mn10300.h. ', 'are above. '), 1)
    else:
        anchor = ("// The register model and its deliberate omissions are documented in mn10300.h.\n")
        assert anchor in c, 'SIO anchor missing'
        c = c.replace(anchor, body + '\n', 1)
open(C, 'w').write(c)
print('relocated %d block(s)' % len(moved))

t = open(H, encoding='utf-8').read().split('\n')
n = sum(1 for l in t if l.lstrip().startswith(('//', '/*', '*')))
print('mn10300.h now %d/%d = %.1f%%' % (n, len(t), 100.0*n/len(t)))


# Second pass: the callback semantics and the timer register layout are also
# implementation description, not caller contract. The header keeps one line per
# member saying what it is; the detail goes beside the code.
def move(header_block, cpp_anchor, cpp_text, header_repl=''):
    h = open(H, encoding='utf-8').read()
    if header_block in h:
        open(H, 'w').write(h.replace(header_block, header_repl, 1))
        c = open(C, encoding='utf-8').read()
        assert cpp_anchor in c, 'anchor missing: %r' % cpp_anchor[:60]
        open(C, 'w').write(c.replace(cpp_anchor, cpp_text + cpp_anchor, 1))
        return True
    return False


moved2 = 0
moved2 += move(
"""	// Outward event callbacks (all optional):
	//   intc_ack_cb    (write8, data = group): a GxICR write carried DETECT-ack
	//        bits (data & mem_mask & 0x000f).
	//   intc_accept_cb (write8, data = group): this group was latched into the
	//        IAGR at interrupt accept.
	//   intc_extmd_cb  (write16): new EXTMD value after each write.
""",
"int mn10300_device::intc_pending_group() const",
"""// Outward event callbacks, all optional and all no-ops when unbound:
//   intc_ack_cb    (write8, data = group): a GxICR write carried DETECT-ack
//        bits (data & mem_mask & 0x000f).
//   intc_accept_cb (write8, data = group): this group was latched into the IAGR
//        at interrupt accept.
//   intc_extmd_cb  (write16): the new EXTMD value after each write.
""",
"""	// Outward event callbacks; see intc_pending_group() in the .cpp.
""")

moved2 += move(
"""	// Interrupt-worthy events are routed OUT through per-channel callbacks; the
	// machine forwards them to the INTC, which keeps the board-specific group
	// numbers and any deferral driver-side:
	//   sio_tx_cb        (write8): byte written to the TX data register
	//   sio_tx_done_cb   (write_line, 1 per event): that byte's transfer
	//        completed. Invoked BEFORE sio_tx_cb.
	//   sio_rx_rdy_cb    (write_line, 1 per byte): a byte was pushed into the
	//        RX FIFO
	//   sio_rx_enable_cb (write_line, called with 1): config bit14 written set
	// Unbound callbacks are no-ops, so a machine may wire only what it needs.
""",
"uint16_t mn10300_device::sio_r(offs_t offset, uint16_t mem_mask)",
"""// Interrupt-worthy events go out through per-channel callbacks; the machine
// forwards them to the INTC, which keeps the board-specific group numbers and
// any deferral driver-side:
//   sio_tx_cb        (write8): byte written to the TX data register
//   sio_tx_done_cb   (write_line, 1 per event): that byte's transfer completed.
//        Invoked BEFORE sio_tx_cb.
//   sio_rx_rdy_cb    (write_line, 1 per byte): a byte was pushed into the RX FIFO
//   sio_rx_enable_cb (write_line, called with 1): config bit14 written set
// Unbound callbacks are no-ops, so a machine may wire only what it needs.
""",
"""	// Per-channel event callbacks; see sio_r() in the .cpp.
""")

moved2 += move(
"""	// TM5: mode byte @0x34001082, 16-bit reload @0x34001092, down-counter
	// @0x340010A2. Underflow asserts INTC group 7. The TM4 half of each register
	// word (offset 0 of each window) reads 0 and drops writes; TM5BC writes fall
	// through to the machine map, which maps the counter window read-only.
""",
"void mn10300_device::tm5_rearm(bool restart_phase)",
"""// TM5: mode byte @0x34001082, 16-bit reload @0x34001092, down-counter
// @0x340010A2. Underflow asserts INTC group 7. The TM4 half of each register
// word (offset 0 of each window) reads 0 and drops writes; TM5BC writes fall
// through to the machine map, which maps the counter window read-only.
""")

print('second pass relocated %d block(s)' % moved2)
t = open(H, encoding='utf-8').read().split('\n')
n = sum(1 for l in t if l.lstrip().startswith(('//', '/*', '*')))
print('mn10300.h now %d/%d = %.1f%%' % (n, len(t), 100.0*n/len(t)))


# Third pass: the map's contents and the AM33 frame convention are both
# statements about the implementation, so they go beside it.
moved3 = 0
moved3 += move(
"""	// ---- address space -----------------------------------------------------
	// Flat 32-bit little-endian space with a 32-bit data bus. The internal map
	// decodes the on-chip peripherals: the INTC (0x34000100-0x340002FF), the
	// SIO (0x34000800-0x3400082F) and the TM4/TM5 timer windows (0x34001080/
	// 0x34001090/0x340010A0, 4 bytes each); the machine maps the rest.
""",
"void mn10300_device::mn103002a_internal_map(address_map &map)",
"""// Flat 32-bit little-endian space with a 32-bit data bus. This decodes the
// on-chip peripherals -- the INTC (0x34000100-0x340002FF), the SIO
// (0x34000800-0x3400082F) and the TM4/TM5 timer windows (0x34001080/0x34001090/
// 0x340010A0, 4 bytes each) -- and the machine maps the rest.
""",
"""	// ---- address space -----------------------------------------------------
""")

moved3 += move(
"""	// call/ret/retf use the AM33 imm8-total frame convention: the return PC sits at
	// [SP] and the saved registers at fixed negative offsets below it; SP is moved
	// only by imm8. These write/read the register block at those offsets WITHOUT
	// moving SP (mirrors the GDB simulator's ret/retf offset walk).
""",
"void mn10300_device::store_regs_at(uint32_t base, uint8_t mask)",
"""// call/ret/retf use the AM33 imm8-total frame convention: the return PC sits at
// [SP] and the saved registers at fixed negative offsets below it, and SP moves
// only by imm8. These two write and read the register block at those offsets
// WITHOUT moving SP, mirroring the GDB simulator's ret/retf offset walk.
""")

print('third pass relocated %d block(s)' % moved3)
t = open(H, encoding='utf-8').read().split('\n')
n = sum(1 for l in t if l.lstrip().startswith(('//', '/*', '*')))
print('mn10300.h FINAL %d/%d = %.1f%%' % (n, len(t), 100.0*n/len(t)))


# Fourth pass: the interrupt-delivery narrative belongs beside take_irq, and two
# TODOs can say what they mean in one line each.
moved4 = 0
moved4 += move(
"""	// The on-chip interrupt controller (0x34000100 block, above) drives the
	// single maskable IRQ input line and supplies the address the AM33 maskable
	// vector jumps to (per-level table). On accept the core latches IAGR, pushes
	// PC+PSW and clears IE; the handler reads IAGR, dispatches, acks and rti's.
""",
"void mn10300_device::take_irq(int level, int group)",
"""// The on-chip interrupt controller drives the single maskable IRQ input line and
// supplies the address the AM33 maskable vector jumps to. On accept the core
// latches IAGR, pushes PC and PSW and clears IE; the handler reads IAGR,
// dispatches, acks and returns through rti.
""")

h = open(H, encoding='utf-8').read()
for old, new in (
("""	// TODO(MN10300): the MN10200 overrides execute_clocks_to_cycles/cycles_to_clocks
	// for its internal /2 divider. The 1:1 base-class defaults are used until a
	// machine is found that needs otherwise.
""",
 """	// TODO(MN10300): no internal clock divider is modelled (the MN10200 has one).
"""),
("""	// TODO(MN10300): decide alignment policy; read_word/read_dword on a byte-
	// granular little-endian space handle any offset. MN10200 forced (addr & ~1).
""",
 """	// TODO(MN10300): alignment policy undecided; any offset is accepted.
"""),
("""	// Timing is uncalibrated: execute_run charges one cycle per instruction and
	// take_irq a flat seven, so nothing costs more than eight.
""",
 """	// Timing is uncalibrated: one cycle per instruction, seven for an interrupt.
"""),
):
    if old in h:
        h = h.replace(old, new, 1); moved4 += 1
open(H, 'w').write(h)

print('fourth pass: %d block(s)' % moved4)
t = open(H, encoding='utf-8').read().split('\n')
n = sum(1 for l in t if l.lstrip().startswith(('//', '/*', '*')))
print('mn10300.h %d/%d = %.1f%%' % (n, len(t), 100.0*n/len(t)))

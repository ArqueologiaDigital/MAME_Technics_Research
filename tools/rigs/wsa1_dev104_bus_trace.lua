-- wsa1_dev104_bus_trace.lua -- an A/B witness for the 0x00104000 register file.
--
-- QUESTION IT ANSWERS: when the handling of CPU 2's 0x00104000 window moved out of
-- wsa1.cpp's inline synth2_* handlers and into the wsa1_modeling_device, did the
-- traffic change?  A refactor that changes what reaches the register file is a bug,
-- not an improvement, and "it still builds" does not test that.
--
-- WHY IT TAPS THE BUS AND NOT THE DEVICE: the tap is installed on CPU 2's PROGRAM
-- SPACE, so it sees exactly the same thing before and after the move -- it knows
-- nothing about which object owns the handler.  A probe that reached into the
-- device's members would only exist on one side of the A/B and could not be run on
-- the other.
--
-- WHAT IT RECORDS, in order:
--   * every write in 0x104000..0x104003 on CPU 2, as (address, data)
--   * the running FNV-1a hash of that whole sequence -- the actual A/B signal
--   * the reconstructed register file, replayed from the bus exactly as the
--     hardware model does it (+0 latches, +2 stores at the latch), and its hash
--   * the count of READS in the window, which prom_c is not known to make at all
--
-- RUN (from ~/compartilhado/kn7000-emulator):
--   DEV104_UNTIL=60 DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms -skip_gameinfo \
--       -window -nomax \
--       -autoboot_script ~/compartilhado/kn7000_mame/tools/rigs/wsa1_dev104_bus_trace.lua
--
-- Environment:
--   DEV104_UNTIL   emulated seconds to run before reporting and exiting (default 60)
--   DEV104_DUMP    if set, also print the first N (address, data) pairs verbatim
--
-- PASS = the two runs print the same SEQ HASH, the same FILE HASH, the same write
-- count and the same read count.  Those are the whole result; the verbatim dump is
-- only there to make a mismatch readable.
--
-- ⚠ Held in globals.  A tap or notifier kept only in a local is collected by MAME's
-- Lua GC and then silently never fires -- which looks exactly like "zero writes".

local m     = manager.machine
local UNTIL = tonumber(os.getenv("DEV104_UNTIL")) or 60
local DUMP  = tonumber(os.getenv("DEV104_DUMP")) or 0

local cpu2 = m.devices[":cpu2"]
if cpu2 == nil then
	emu.print_error("DEV104: no :cpu2 in this machine")
	m:exit()
	return
end

-- FNV-1a over 32 bits, in pure Lua integer arithmetic.
local function fnv(h, byte)
	h = (h ~ byte) & 0xffffffff
	h = (h * 16777619) & 0xffffffff
	return h
end

local function fnv_word(h, v)
	h = fnv(h, v & 0xff)
	h = fnv(h, (v >> 8) & 0xff)
	h = fnv(h, (v >> 16) & 0xff)
	h = fnv(h, (v >> 24) & 0xff)
	return h
end

G_seq_hash  = 0x811c9dc5   -- hash of the raw bus sequence
G_writes    = 0
G_reads     = 0
G_latch     = 0
G_regs      = {}           -- sparse: only what was actually written
G_dumped    = 0

G_wtap = cpu2.spaces["program"]:install_write_tap(0x104000, 0x104003, "dev104_w",
	function (offset, data, mask)
		G_writes = G_writes + 1
		G_seq_hash = fnv_word(G_seq_hash, offset)
		G_seq_hash = fnv_word(G_seq_hash, data)
		G_seq_hash = fnv_word(G_seq_hash, mask)

		-- Replay the model: +0 is the select, +2 is the data.
		if offset < 0x104002 then
			G_latch = data & 0xffff
		else
			G_regs[G_latch] = data & 0xffff
		end

		if G_dumped < DUMP then
			G_dumped = G_dumped + 1
			emu.print_error(string.format("DEV104 W %06X = %04X (mask %04X)",
				offset, data & 0xffff, mask & 0xffff))
		end
	end)

G_rtap = cpu2.spaces["program"]:install_read_tap(0x104000, 0x104003, "dev104_r",
	function (offset, data, mask)
		G_reads = G_reads + 1
		emu.print_error(string.format("DEV104 R %06X (unexpected: prom_c has no known reader)",
			offset))
	end)

G_report = function ()
	-- Hash the reconstructed file in ASCENDING REGISTER ORDER, so it does not
	-- depend on Lua's table iteration order.
	local keys = {}
	for k, _ in pairs(G_regs) do keys[#keys + 1] = k end
	table.sort(keys)
	local fh = 0x811c9dc5
	for _, k in ipairs(keys) do
		fh = fnv_word(fh, k)
		fh = fnv_word(fh, G_regs[k])
	end

	emu.print_error("-------- DEV104 BUS TRACE --------")
	emu.print_error(string.format("  window writes      : %d", G_writes))
	emu.print_error(string.format("  window reads       : %d", G_reads))
	emu.print_error(string.format("  distinct registers : %d", #keys))
	emu.print_error(string.format("  SEQ HASH           : %08X", G_seq_hash))
	emu.print_error(string.format("  FILE HASH          : %08X", fh))
	if #keys > 0 then
		emu.print_error(string.format("  register span      : 0x%04X .. 0x%04X",
			keys[1], keys[#keys]))
	end
	emu.print_error("----------------------------------")
end

G_timer = emu.add_machine_frame_notifier(function ()
	if m.time:as_double() >= UNTIL then
		G_report()
		m:exit()
	end
end)

-- QUESTION: does the emulated SX-WSA1R's firmware talk to the floppy disk
-- controller, and if so what does it say?
--
-- The device at CPU 1's 0x7B0004/0x7B0005 (+ 0x7A0000 on the DMA-acknowledged
-- decode) is a uPD765-family FDC -- established in
-- wsa1-roms-disasm/notes/FINDINGS-prom_a-fdc.md and wired to an upd765a_device
-- in src/mame/matsushita/wsa1.cpp.  This probe answers three separate things:
--
--   1. is the DRIVER's public entry reached at all?  Fdc_Request (prom_a
--      0xFE66C7) sets the re-entry guard byte (0x605A09) to 0xA5 and copies its
--      16-byte request block to (0x605A30).  Both are DATA writes, so a write
--      tap catches them; an opcode-fetch tap would not (the CPU cache).
--   2. does the CONTROLLER answer?  Every access to the two register windows is
--      counted and the first few are printed with their values, so an MSR that
--      reads 0xFF ("no controller", the firmware's error 0xFC) can be told from
--      one that reads 0x80 (RQM, idle and ready for a command).
--   3. what is written to the control register at 0x7B0004?  The driver reads
--      that register as the uPD765 DSR: 0x80 = software reset, 0x00 = 500 kbps,
--      0x02 = 250 kbps.  If those are the only three values that ever appear,
--      the reading is consistent with what the machine actually does.
--
-- It also snapshots the panel every 15 emulated seconds, so one run doubles as
-- the boot screen series (snapshots land in snap/wsa1r/ or snap/wsa1/).
--
-- Run:
--   cd ~/compartilhado/kn7000_mame_build
--   DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms -skip_gameinfo -str 200 -window \
--       -autoboot_script ~/compartilhado/kn7000_mame/notes/wsa1-probes/wsa1_fdc_probe.lua
--
-- Give it at least 200 emulated seconds: this machine's boot takes ~90 s of
-- emulated time (see README.md).
--
-- ⚠ Every tap and notifier is held in a global -- MAME's Lua GC collects them
-- otherwise -- and every tap starts on a word boundary, which these 16-bit
-- spaces require.

_G.n_msr, _G.n_dsr, _G.n_fifo_r, _G.n_fifo_w = 0, 0, 0, 0
_G.n_dma_r, _G.n_dma_w = 0, 0
_G.n_guard, _G.n_req = 0, 0
_G.dsr_values, _G.msr_values = {}, {}
_G.first = {}
_G.printed = 0

local function note(tag)
	if _G.first[tag] == nil then
		_G.first[tag] = manager.machine.time:as_double()
		print(string.format("FDC-FIRST %-10s t=%.4f s  pc=%06X", tag, _G.first[tag],
			manager.machine.devices[":cpu1"].state["CURPC"].value))
	end
end

local function tally(t, v)
	t[v] = (t[v] or 0) + 1
end

local sp = manager.machine.devices[":cpu1"].spaces["program"]
_G.taps = {}

-- 0x7B0004 low lane = MSR (read) / control (write); 0x7B0005 high lane = data.
_G.taps[#_G.taps+1] = sp:install_read_tap(0x7b0004, 0x7b0005, "fdc_reg_r",
	function (offset, data, mask)
		if mask & 0x00ff ~= 0 then
			_G.n_msr = _G.n_msr + 1
			tally(_G.msr_values, data & 0xff)
			note("msr_r")
		end
		if mask & 0xff00 ~= 0 then
			_G.n_fifo_r = _G.n_fifo_r + 1
			note("fifo_r")
		end
		return data
	end)

_G.taps[#_G.taps+1] = sp:install_write_tap(0x7b0004, 0x7b0005, "fdc_reg_w",
	function (offset, data, mask)
		if mask & 0x00ff ~= 0 then
			_G.n_dsr = _G.n_dsr + 1
			tally(_G.dsr_values, data & 0xff)
			note("ctrl_w")
			print(string.format("FDC ctrl 0x7B0004 <- 0x%02X  t=%.4f",
				data & 0xff, manager.machine.time:as_double()))
		end
		if mask & 0xff00 ~= 0 then
			_G.n_fifo_w = _G.n_fifo_w + 1
			note("fifo_w")
			if _G.printed < 40 then
				_G.printed = _G.printed + 1
				print(string.format("FDC data 0x7B0005 <- 0x%02X  t=%.4f",
					(data >> 8) & 0xff, manager.machine.time:as_double()))
			end
		end
		return data
	end)

_G.taps[#_G.taps+1] = sp:install_read_tap(0x7a0000, 0x7a0001, "fdc_dma_r",
	function (offset, data, mask) _G.n_dma_r = _G.n_dma_r + 1 note("dma_r") return data end)
_G.taps[#_G.taps+1] = sp:install_write_tap(0x7a0000, 0x7a0001, "fdc_dma_w",
	function (offset, data, mask) _G.n_dma_w = _G.n_dma_w + 1 note("dma_w") return data end)

-- Fdc_Request's own footprints in work DRAM.
_G.taps[#_G.taps+1] = sp:install_write_tap(0x605a08, 0x605a09, "fdc_guard",
	function (offset, data, mask) _G.n_guard = _G.n_guard + 1 note("guard") return data end)
_G.taps[#_G.taps+1] = sp:install_write_tap(0x605a30, 0x605a3f, "fdc_reqblk",
	function (offset, data, mask) _G.n_req = _G.n_req + 1 note("reqblock") return data end)

_G.frames, _G.shots = 0, 0
_G.sub = emu.add_machine_frame_notifier(function ()
	_G.frames = _G.frames + 1
	if (_G.frames % 900) ~= 0 then return end        -- 15 s at 60 fps
	_G.shots = _G.shots + 1
	manager.machine.video:snapshot()

	local dsr = {}
	for v, c in pairs(_G.dsr_values) do dsr[#dsr+1] = string.format("%02X x%d", v, c) end
	table.sort(dsr)
	local msr = {}
	for v, c in pairs(_G.msr_values) do msr[#msr+1] = string.format("%02X x%d", v, c) end
	table.sort(msr)

	print(string.format(
		"FDC t=%6.1f  shot=%d  msr_r=%d fifo_r=%d fifo_w=%d ctrl_w=%d dma_r=%d dma_w=%d"
		.. "  Fdc_Request: guard=%d reqblk=%d  cpu1pc=%06X",
		manager.machine.time:as_double(), _G.shots,
		_G.n_msr, _G.n_fifo_r, _G.n_fifo_w, _G.n_dsr, _G.n_dma_r, _G.n_dma_w,
		_G.n_guard, _G.n_req,
		manager.machine.devices[":cpu1"].state["CURPC"].value))
	if #msr > 0 then print("     MSR values read : " .. table.concat(msr, ", ")) end
	if #dsr > 0 then print("     control written : " .. table.concat(dsr, ", ")) end
end)

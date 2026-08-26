-- Is CPU 1's SC1 RECEIVE RING in phase with what the panel sends?
--
-- QUESTION IT ANSWERS.  Every message on this link is an even number of bytes, so
-- the ring's read and write indices must stay the same parity.  If they ever
-- differ by an odd amount, SC1_RxOp0_ThreeByte (prom_b 0xF5B0FD) pairs the
-- PREVIOUS message's data byte with THIS message's address byte, and every panel
-- button silently lands in the wrong shadow slot carrying the wrong value.  That
-- was gap Y.
--
-- THE TWO WORDS, from the receive path itself:
--   (0x2A90)  read index   -- SC1_RxOp0_ThreeByte saves it at 0xF5B125
--   (0x2A92)  write index  -- incremented at 0xF5AF25 / 0xF5AF69, wrapped at 0x4C
--   0x2A94    the ring itself, 0x4C bytes (0xF5AF54 / 0xF5AF25)
--
-- Every write to either index is logged with the PC that made it, so a rewind
-- shows up by its address:
--   0xF5AF25 / 0xF5AF69  a byte arrived                     (write index +1)
--   0xF5AC4A             INT6 arrived MID-FRAME             (write index -1)  ★
--   0xF5B129             a message was consumed             (read index +2)
--   0xF5B23A             a sync packet was discarded        (read index +2)
--
-- RUN
--   cd ~/compartilhado/kn7000-emulator
--   DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms -skip_gameinfo -window -nomax \
--       -autoboot_script ~/compartilhado/kn7000_mame/notes/wsa1-probes/wsa1_sc1_ring_phase.lua
--
-- PASS = the final line reads RD == WR.  Stop time defaults to 22 emulated
-- seconds (RING_UNTIL), by which point the boot handshake is long over.
--
-- MEASURED 2026-08-26, wsa1r:
--   before the request_tick guard:  three 0xF5AC4A rewinds at t = 0.326 / 0.334 /
--       0.342, write index 0000 -> 004C -> 0049, final RD=004A WR=004B  (OUT OF PHASE)
--   after:                          no rewinds at all, final RD=0006 WR=0006
--
-- ⚠ Held in a global: a notifier kept only in a local is collected by MAME's Lua
-- GC and then silently never fires.

local m     = manager.machine
local sp    = m.devices[":cpu1"].spaces["program"]
local UNTIL = tonumber(os.getenv("RING_UNTIL")) or 22

_G.RP = _G.RP or {}
_G.RP.log = {}

local function pc() return m.devices[":cpu1"].state["CURPC"].value end

_G.RP.tap = sp:install_write_tap(0x2a90, 0x2a93, "sc1ringidx", function (o, d, k)
	if #_G.RP.log < 500 then
		_G.RP.log[#_G.RP.log + 1] = string.format("t=%8.4f %s<-%04X pc=%06X",
			m.time:as_double(), (o == 0x2a90) and "RD" or "WR", d & 0xffff, pc())
	end
	return d
end)

_G.RP.h = emu.add_machine_frame_notifier(function ()
	if m.time:as_double() < UNTIL then return end
	local rewinds = 0
	for _, l in ipairs(_G.RP.log) do
		emu.print_error("RING " .. l)
		if l:find("pc=F5AC4E") then rewinds = rewinds + 1 end
	end
	local rd, wr = sp:read_u16(0x2a90), sp:read_u16(0x2a92)
	emu.print_error(string.format(
		"RING final RD=%04X WR=%04X  (%d index writes, %d MID-FRAME REWINDS)  %s",
		rd, wr, #_G.RP.log, rewinds, (rd == wr) and "PASS: in phase" or "FAIL: out of phase"))
	m:exit()
end)

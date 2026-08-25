-- IS INTTR4 ACTUALLY BEING DISPATCHED, AND INTO WHICH HANDLER?
--
-- QUESTION IT ANSWERS: the 16-bit timer fix makes INTTR4's REQUEST flag get
-- raised.  That is not the same as the CPU accepting the interrupt and jumping
-- to the firmware's handler -- the level could be 0, the CPU mask could be
-- closed, or tlcs900_check_irqs() might never be called.  This probe watches
-- the acceptance itself.
--
-- WHAT IS BEING READ, and why it means acceptance:
--   tmp95c061_device::tlcs900_check_irqs() ends with
--       m_pc.d = RDMEML( 0xffff00 + vector );
--   so the ONLY way a longword read of 0xFFFF50 happens is that the CPU has
--   accepted INTTR4 and is fetching its entry point.  Table 3.3 (1) on page 12
--   of the TMP95C061 databook gives INTTR4 -- "16-bit timer4 (TREG4)" --
--   address FFFF50H.  The DATA the tap sees is therefore the handler PC.
--   The other three rows are the same trick for INTT1 (FFFF44H, the
--   millisecond tick), INTT3 (FFFF4CH, the RTOS tick) and INTTR5/6/7
--   (FFFF54/58/5C), which on this machine are all at priority 0 and must show
--   ZERO -- vectors 0x54/0x58/0x5C point at prom_a 0xF82D09, a deliberate
--   `jr T,self` infinite loop, so a single spurious dispatch would hang the
--   machine and the zero is a real pass/fail criterion, not decoration.
--
-- ⚠ The program space is 16 bits wide, so one longword vector fetch shows up as
-- TWO tap calls (low word then high word).  Only the call that covers the LOW
-- byte of the vector is counted, so the count is dispatches, not accesses.
--
-- RUN:
--   cd ~/compartilhado/kn7000_mame_build
--   DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms -skip_gameinfo -str 45 -window \
--     -autoboot_script ~/compartilhado/kn7000_mame/notes/wsa1-probes/wsa1_inttr4_dispatch.lua
--
-- PASS: INTTR4 climbs, its "-> handler" reads F82EA2, and TR5/TR6/TR7 stay 0.
--
-- MEASURED 2026-08-25, wsa1r, build with OVERLAY FIX 1-4 (this session):
--   INTT1  n=22164  488.3 Hz steady  -> handler F82D0B
--   INTT3  n= 6616  first dispatch t=19.65 s -> handler F42D64  (prom_b, so
--          the RTOS tick is enabled late, by INTET32 = 0x20 at prom_a 0xF856F5)
--   INTTR4 n= 9217  192.0 Hz steady  -> handler F82EA2   <-- the musical clock
--          (the running average shown in the table is dragged up by the ~12 s
--          224 Hz boot transient; the per-second delta is 192)
--   INTTR5/6/7 n=0 each        (levels are 0; the vectors are hang loops)
-- With the timers reverted to upstream (tlcs900_timer_control.sh null):
--   INTT1  n= 1370   30.5 Hz   -> handler F82D0B
--   INTT3  n=  713   15.9 Hz   -> handler F857D4
--   INTTR4 n=    0             -- never dispatched, the sequencer cannot run

local sp = manager.machine.devices[":cpu1"].spaces["program"]

_G.rows = {
	{ name = "INTT1 ", addr = 0xffff44 },
	{ name = "INTT3 ", addr = 0xffff4c },
	{ name = "INTTR4", addr = 0xffff50 },
	{ name = "INTTR5", addr = 0xffff54 },
	{ name = "INTTR6", addr = 0xffff58 },
	{ name = "INTTR7", addr = 0xffff5c },
}
_G.taps = {}   -- held in a global: a tap collected by the GC is silently dead
_G.t0 = nil

for i, r in ipairs(_G.rows) do
	r.n = 0
	r.pc = nil
	_G.taps[i] = sp:install_read_tap(r.addr, r.addr + 1, "v" .. r.name,
		function (offset, data, mask)
			if (mask & 0x00ff) ~= 0 then
				r.n = r.n + 1
				if r.pc == nil and not r.reading then
					-- The vector's low word is this read and the high word
					-- follows, so read the longword back out of the space.
					-- ⚠ That read RE-ENTERS this very tap; without the guard
					-- the "first dispatch" line prints once per nesting level
					-- (observed: five times for INTT3).
					r.reading = true
					local pc = sp:read_u32(r.addr)
					r.reading = false
					r.pc = pc
					print(string.format("FIRST DISPATCH %s at t=%.4f s -> handler %06X",
						r.name, manager.machine.time:as_double(), r.pc))
				end
			end
			return data
		end)
end

_G.n = 0
_G.sub = emu.add_machine_frame_notifier(function ()
	_G.n = _G.n + 1
	if (_G.n % 60) ~= 0 then return end
	local t = manager.machine.time:as_double()
	if _G.t0 == nil then
		-- start the rate window once the boot block has programmed the timers
		if _G.rows[1].n > 0 then
			_G.t0 = t
			for _, r in ipairs(_G.rows) do r.base = r.n end
		end
		return
	end
	local dt = t - _G.t0
	if dt < 0.5 then return end
	local s = ""
	for _, r in ipairs(_G.rows) do
		s = s .. string.format("  %s n=%-6d %7.1f Hz %s", r.name, r.n,
			(r.n - r.base) / dt, r.pc and string.format("@%06X", r.pc) or "@------")
	end
	print(string.format("t=%6.2f%s", t, s))
end)

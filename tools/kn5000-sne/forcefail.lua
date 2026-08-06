-- OBSERVE + POSITIVE CONTROL for the "Sound Name Error" detector.
--
-- 0xFEE671 calls 0xFEF252, which builds a 10-byte packet at RAM 0xE2B8 with byte 0 =
-- 0x2B (the SubCPU sound-name query), sends it over the inter-CPU latch via 0xEF32F4
-- -> 0xEF3345 (`ld (0x140000),A'), and then returns L = (0xE2BF) -- byte +7 of the
-- REPLY.  That byte is the sound number handed to the name lookup at 0xFEE55A.
--
-- SNE_BADNUM unset  -> OBSERVE only: log every value the firmware reads from 0xE2BF.
-- SNE_BADNUM = N    -> also FORCE that read to N, which must produce the fallback
--                      string if the detector can see it at all.

local mach = manager.machine
local cpu  = mach.devices[":maincpu"]
local sp   = cpu.spaces["program"]
local st   = cpu.state
local env  = os.getenv("SNE_BADNUM")
local BAD  = env and tonumber(env) or nil
local function T() return mach.time.seconds + mach.time.attoseconds/1e18 end
local function log(s) emu.print_error("FORCE| " .. s) end

log(BAD and string.format("FORCING (0xE2BF) -> 0x%02X", BAD) or "OBSERVE ONLY (no forcing)")

_G.FORCE = { n = 0, seen = {} }
_G.FORCE.tap = sp:install_read_tap(0xE2BE, 0xE2BF, "soundnum",
	function(off, data, mask)
		-- 16-bit space: 0xE2BF is the HIGH byte of the word at 0xE2BE.
		if mask < 0x100 then return end
		_G.FORCE.n = _G.FORCE.n + 1
		local v = math.floor(data / 0x100) % 0x100
		_G.FORCE.seen[v] = (_G.FORCE.seen[v] or 0) + 1
		local pc = st["PC"].value
		if _G.FORCE.n <= 60 then
			log(string.format("read#%d t=%.3f (0xE2BF)=0x%02X PC=%06X", _G.FORCE.n, T(), v, pc))
		end
		-- Force ONLY the value 0xFEF28E hands back to its caller (PC has already
		-- advanced to 0xFEF292).  The other reader, PC=0xEF3443, is the transmit
		-- loop: forcing that one would change the tag actually SENT, and the SubCPU
		-- would echo the forced tag back, so the lookup would still succeed.
		if BAD and pc == 0xFEF292 then
			local newv = (BAD >= 0) and BAD or ((v + 0x40) % 0x80)
			return (data % 0x100) + newv * 0x100
		end
	end)

local last = -1
emu.register_periodic(function()
	local t = math.floor(T())
	if t > last and (t % 10) == 0 then
		last = t
		local keys = {}
		for k, c in pairs(_G.FORCE.seen) do keys[#keys+1] = string.format("%02X:%d", k, c) end
		table.sort(keys)
		log(string.format("t=%3ds  reads of (0xE2BF)=%d  values seen = %s",
			t, _G.FORCE.n, table.concat(keys, " ")))
	end
end)

local sched = os.getenv("SNE_SCHEDULE2")
if sched and #sched > 0 then
	log("loading schedule " .. sched)
	dofile(sched)
end

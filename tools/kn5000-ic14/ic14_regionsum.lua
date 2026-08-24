-- Fingerprint the rhythm_data region AS LOADED. Compared against the same fingerprint
-- computed on the de-scrambled file, and against the OLD ROM_CONTINUE permutation
-- applied to the raw read. If the single ROM_LOAD is equivalent to the eight-block
-- ROM_CONTINUE it replaced, all three agree. This CAN fail: any wrong block order
-- changes the position-weighted term.
local done = false
_G.ic14sum = emu.register_frame_done(function()
	local m = manager.machine
	if done or m.time.seconds < 20 then return end
	done = true
	local r = m.memory.regions[":rhythm_data"]
	local sum, wsum = 0, 0
	for a = 0, r.size - 1 do
		local b = r:read_u8(a)
		sum = (sum + b) % 4294967296
		wsum = (wsum + b * ((a % 251) + 1)) % 4294967296
	end
	emu.print_error(string.format("[ic14] size=0x%X sum=%u wsum=%u", r.size, sum, wsum))
	m:exit()
end)

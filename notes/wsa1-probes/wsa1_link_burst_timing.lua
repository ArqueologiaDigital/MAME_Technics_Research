-- How fast does the SENDER push bytes into the one-byte link latch, and does the
-- receiver get to drain it?  (SX-WSA1R, 2026-08-27)
--
-- CONTEXT.  With OVERLAY FIX 6 in tmp95c061.cpp the link runs, but
-- wsa1_udma3_audit.lua measures CPU 2 writing 71 bytes to 0x100000 while CPU 1
-- reads 0x7C0000 only 21 times: the latch is overwritten mid-burst and the
-- 0xE1 record at 0x6007D3 comes out garbage (INTTC3_Sel2_ArmPayload then arms
-- DMAC3 with 0xFFEF instead of the real count).
--
-- TWO DIFFERENT CAUSES LOOK THE SAME FROM THE COUNTS, and this probe separates
-- them by printing the EMULATED TIME of every latch access to microsecond
-- resolution:
--
--   * SCHEDULING GRANULARITY -- the sender's bytes are correctly spaced (the
--     transmit block paces micro-DMA channel 2 from timer 2, DMA2V = 0x12 ->
--     vector 0x48 = INTT2, prom_c 0xF99A2A) but MAME's quantum lets CPU 2 run
--     several of those spacings before CPU 1 gets a timeslice.  wsa1r() sets
--     config.set_maximum_quantum(attotime::from_usec(50)) and the CPUs are
--     28 MHz, so a quantum is ~1400 cycles.  ⇒ EXPECT gaps of a few tens of µs
--     and several writes bunched inside one 50 µs window.
--
--   * PACING TOO FAST -- timer 2 itself ticks faster than the hardware's, so
--     the bytes really are microseconds apart and no quantum could keep up.
--     That would be the same family of defect as OVERLAY FIX 1 (the 8-bit timer
--     rate) and would belong in the CPU core, not the driver.  ⇒ EXPECT gaps of
--     well under a microsecond.
--
-- Run:
--   cd ~/compartilhado/kn7000_mame_build
--   DISPLAY=:0 ./kn7000 wsa1r -rompath ./roms -skip_gameinfo -str 75 -window \
--       -autoboot_delay 1 \
--       -autoboot_script ~/compartilhado/kn7000_mame/notes/wsa1-probes/wsa1_link_burst_timing.lua

local m   = manager.machine
local sp1 = m.devices[":cpu1"].spaces["program"]
local sp2 = m.devices[":cpu2"].spaces["program"]
local taps = {}

local function now() return m.time:as_double() end
local ev, EVMAX = {}, 250
local last_w, last_r = nil, nil
local gaps_w = {}
local n_w, n_r = 0, 0

local function rec(s) if #ev < EVMAX then ev[#ev+1] = s end end

taps[#taps+1] = sp2:install_write_tap(0x100000, 0x100001, "w", function (off, data, mask)
	local t = now() ; n_w = n_w + 1
	local d = last_w and (t - last_w) or -1
	if last_w then gaps_w[#gaps_w+1] = d end
	rec(string.format("W #%-3d t=%14.9f  gap=%10.3f us   byte=0x%02X",
		n_w, t, d * 1e6, data & 0xff))
	last_w = t
	return data
end)

taps[#taps+1] = sp1:install_read_tap(0x7c0000, 0x7c0001, "r", function (off, data, mask)
	local t = now() ; n_r = n_r + 1
	rec(string.format("R #%-3d t=%14.9f  since last W = %10.3f us  byte=0x%02X",
		n_r, t, last_w and (t - last_w) * 1e6 or -1, data & 0xff))
	last_r = t
	return data
end)
_G.wsa1_burst_taps = taps

local done = false
_G.wsa1_burst_rep = emu.add_machine_frame_notifier(function ()
	if done or m.time.seconds < 74 then return end
	done = true
	local P = emu.print_error
	for i = 1, #ev do P(ev[i]) end
	table.sort(gaps_w)
	local n = #gaps_w
	if n > 0 then
		local sum = 0 ; for _, g in ipairs(gaps_w) do sum = sum + g end
		P(string.format("SENDER GAPS  n=%d  min=%.3f us  median=%.3f us  mean=%.3f us  max=%.3f us",
			n, gaps_w[1] * 1e6, gaps_w[(n + 1) // 2] * 1e6, (sum / n) * 1e6, gaps_w[n] * 1e6))
	end
	P(string.format("TOTAL cpu2 writes=%d  cpu1 reads=%d  (quantum is 50 us; 28 MHz CPUs)", n_w, n_r))
end)

-- sibling_boot.lua -- question: does a machine sharing kn7000.cpp (kn6000, kn6500, kn2400, kn2600)
-- boot and sound exactly as it did before IC311 / IC25 / PMUT were modelled for the KN7000?
-- Runs T seconds of emulated time (default 25), saves a snapshot and exits; run_siblings.sh runs it
-- on two builds and compares the snapshots and -wavwrite captures by md5.
local mac = manager.machine
local T = tonumber(os.getenv("T") or "25")
local done = false
_G.SB = emu.add_machine_frame_notifier(function()
	if done then return end
	if mac.time.seconds >= T then
		done = true
		mac.video:snapshot()
		mac:exit()
	end
end)

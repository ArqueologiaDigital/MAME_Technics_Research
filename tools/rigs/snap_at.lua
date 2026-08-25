-- snap_at.lua -- take one screenshot at a chosen emulated time, then exit.
--
-- Model-agnostic, like liveness.lua next to it. liveness.lua answers "did it draw?"
-- with a number; this answers "what does it look like?" with a PNG, so a regression
-- can be EYEBALLED as well as hashed. The two are meant to be used together.
--
--   SNAP_AT=30 ./kn7000 <machine> -rompath ./roms -skip_gameinfo -window \
--       -snapshot_directory <dir> -autoboot_script tools/rigs/snap_at.lua
--
-- SNAP_AT defaults to 30 emulated seconds. Give a model enough time to finish its
-- boot: the KN5000 and KN7000 reach their play screens well before 30 s, and the
-- SX-WSA1R reaches SOUND MODE at ~20 s.
-- (This note used to say the SX-WSA1R needed ~25 s "because its 8-bit timer tap runs
-- 16x slow". That defect is fixed -- see OVERLAY FIX 1 in tmp95c061.cpp -- and the
-- machine now draws its first LCD byte at t = 0.50 s instead of 7.21 s and its first
-- SWI7 text at t = 19.62 s instead of 72.24 s.)
--
-- Prints exactly one line to stderr so a caller can tell a real capture from a
-- timeout:  SNAP <machine> t=<seconds>
--
-- ⚠ Held in a global. MAME's Lua GC collects a notifier kept only in a local, and the
-- callback then silently never fires -- this has cost the project real time before.
--
-- ⚠ Pass -snapshot_directory. MAME's default snap/<machine>/ is shared, and two
-- concurrent runs interleave their auto-numbered files, so a run that does not name
-- its own directory cannot prove which PNG is its own.

local mac = manager.machine
local AT = tonumber(os.getenv("SNAP_AT")) or 30

_G.SNAP = _G.SNAP or {}

_G.SNAP.h = emu.add_machine_frame_notifier(function()
	if _G.SNAP.done then return end
	if mac.time.seconds < AT then return end
	_G.SNAP.done = true
	mac.video:snapshot()
	emu.print_error(string.format("SNAP %s t=%.1f", emu.romname(), mac.time:as_double()))
	mac:exit()
end)

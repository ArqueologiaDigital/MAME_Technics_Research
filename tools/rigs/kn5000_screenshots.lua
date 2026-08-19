-- kn5000_screenshots.lua -- what is actually on screen, at several times?
-- rig-machine: kn5000
--
-- QUESTION ANSWERED: which screen is the machine showing? Used when a scripted button press
-- produces no effect and it is not clear whether the machine is even where you think it is.
-- Nine scripted DEMO presses produced zero tone-generator writes; before changing the press,
-- find out what the machine was looking at.
--
--   SNAP_AT="20,40,60" ./tools/rig.sh kn5000_screenshots kn5000 -s 70 -- -snapshot_directory /tmp/snaps
--
-- Snapshots land in the snapshot directory, named by the machine and an index.

local mac = manager.machine
local function log(s) emu.print_error(s) end

local times = {}
for t in string.gmatch(os.getenv("SNAP_AT") or "20,40,60", "[^,]+") do
    table.insert(times, tonumber(t))
end

_G.SNAP = _G.SNAP or { i = 1 }

_G.SNAP.h = emu.add_machine_frame_notifier(function()
    local S = _G.SNAP
    if S.i > #times then return end
    if mac.time.seconds >= times[S.i] then
        mac.video:snapshot()
        log(string.format("SNAP t=%.1f -> snapshot %d taken", mac.time.seconds, S.i))
        S.i = S.i + 1
    end
end)

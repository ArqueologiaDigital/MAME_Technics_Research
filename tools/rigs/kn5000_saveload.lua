-- kn5000_saveload.lua -- does a KN5000 save-state round trip actually work?
-- rig-machine: kn5000
--
-- Added 2026-08-15 with the shadowing of m_keybed_queue / m_pending_notes
-- (notes/FINDINGS-savestate-audit.md). Those two containers hold real machine state and were
-- not saved; the fix flattens them into arrays around device_pre_save/device_post_load. This
-- rig is the check that the round trip runs at all on this driver -- a device whose save
-- registration is broken fails loudly at save or load time, and nothing else in the gate
-- exercises KN5000 save states.
--
-- ⚠ WHAT IT DOES NOT PROVE. It does not show the queues survive with their CONTENTS intact --
--   only that save and load complete and the machine keeps running. Proving content survival
--   needs a state saved with notes genuinely in flight, which needs a stimulus this rig does
--   not apply. Said plainly so the pass is not read as more than it is.
--
--   ./tools/rig.sh kn5000_saveload kn5000 -s 40
--
-- Prints SL save / SL load / SL PASS, or SL FAIL with the error. Exits when done.

local mac = manager.machine
local function log(s) emu.print_error(s) end

local SAVE_AT = tonumber(os.getenv("SL_SAVE_AT") or "") or 26
local LOAD_AT = tonumber(os.getenv("SL_LOAD_AT") or "") or 30
local DONE_AT = tonumber(os.getenv("SL_DONE_AT") or "") or 34

_G.SL = _G.SL or { phase = 0 }

_G.SL.h = emu.add_machine_frame_notifier(function()
    local t = mac.time.seconds
    local S = _G.SL

    if S.phase == 0 and t >= SAVE_AT then
        S.phase = 1
        local ok, err = pcall(function() mac:save("sltest") end)
        log(ok and string.format("SL save requested at t=%d", t)
               or ("SL FAIL save: " .. tostring(err)))
        if not ok then S.phase = 9 mac:exit() end
    elseif S.phase == 1 and t >= LOAD_AT then
        S.phase = 2
        local ok, err = pcall(function() mac:load("sltest") end)
        log(ok and string.format("SL load requested at t=%d", t)
               or ("SL FAIL load: " .. tostring(err)))
        if not ok then S.phase = 9 mac:exit() end
    elseif S.phase == 2 and t >= DONE_AT then
        S.phase = 3
        -- Still running several seconds after the load is the actual signal: a broken
        -- registration typically takes the machine down at load time.
        log(string.format("SL PASS -- machine still running at t=%d after save+load", t))
        log("SL (this shows the round trip completes; it does NOT show queue contents survived)")
        mac:exit()
    end
end)

-- api_probe.lua -- what does THIS build's MAME Lua API actually offer?
--
-- Written because liveness.lua needed to know the shape of screen:pixels() and the
-- docs for the Lua API drift between MAME versions. Kept because the next model that
-- needs a liveness signal (kn1500 has NO screen device -- it renders through SVG
-- artwork off an HD44780) will need the same discovery step.
--
-- Answers: which screens exist, what pixels() returns, and which top-level manager
-- tables are populated for this machine.
--
-- Measured on kn7000, 2026-08-14:
--   SCREEN tag=:screen w=640 h=240
--     pixels() ok=true type=string len=614400        (= 640*240*4, so 32bpp)
--
-- Usage:
--   ./tools/rig.sh api_probe -s 5

local mac = manager.machine
local function log(s) emu.print_error(s) end

_G.AP = _G.AP or {}
_G.AP.h = emu.add_machine_frame_notifier(function()
    if _G.AP.done or mac.time.seconds < 3 then return end
    _G.AP.done = true

    local n = 0
    for tag, scr in pairs(mac.screens) do
        n = n + 1
        log("SCREEN tag=" .. tostring(tag) ..
            " w=" .. tostring(scr.width) .. " h=" .. tostring(scr.height))
        local ok, px = pcall(function() return scr:pixels() end)
        log("  pixels() ok=" .. tostring(ok) .. " type=" .. type(px) ..
            " len=" .. tostring(ok and type(px) == "string" and #px or "-"))
    end
    if n == 0 then
        log("SCREEN none -- this driver has no screen device; look at artwork/outputs instead")
        local c = 0
        for k, _ in pairs(mac.devices) do
            c = c + 1
            if c <= 40 then log("  DEV " .. tostring(k)) end
        end
        log("  DEV total=" .. c)
    end
    mac:exit()
end)

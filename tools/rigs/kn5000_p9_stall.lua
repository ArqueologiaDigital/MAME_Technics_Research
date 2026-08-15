-- kn5000_p9_stall.lua -- when exactly does the Feature Presentation stop, and into what state?
--
-- Task-queue item P9 records: after the INT0 fix the demo plays 19.26 -> 131.5 s, then
-- `transport` (0x0420) goes 04 -> 00, at beat 171 of 292 = 58% of the song.
--
-- A 160 s run on 2026-08-15 does NOT match that: the demo is still healthy at t=139, and the
-- documented terminal value 0x00 never appears -- what shows up is 0x10. This rig logs the
-- CURRENT values every second (demo_max.lua reports running MAXIMA, which hides the
-- transition) so the stall time and terminal state can be stated exactly.
--
-- Navigation is demo_probe.lua's: DEMO -> LEFT 4 -> LEFT 2. Pressing DEMO alone does nothing.
--
--   ./run.sh kn5000 -window -nothrottle -seconds_to_run 170 \
--       -cfg_directory <fresh> -nvram_directory <fresh> \
--       -autoboot_script tools/rigs/kn5000_p9_stall.lua
--
-- Prints one line per second once past P9_FROM (default 100 s):
--   P9 t=131.0 transport=04 subtick=19 wd=00 acc=03 8d38=E4
-- and a single summary naming the first second at which transport left 0x04.

local mac = manager.machine
local sp  = mac.devices[":maincpu"].spaces["program"]
local function log(s) emu.print_error(s) end
local function u8(a) local ok, v = pcall(function() return sp:read_u8(a) end) return ok and v or -1 end

local FROM = tonumber(os.getenv("P9_FROM")) or 100
local PRESS_AT = tonumber(os.getenv("P9_PRESS_AT")) or 20.0

_G.P9 = _G.P9 or { phase = "wait", base = 0, last = -1, changed_at = nil, from_val = nil }

local function field(tag, mask)
    local p = mac.ioport.ports[":" .. tag] or mac.ioport.ports[":cpanel:" .. tag]
    if not p then return nil end
    for _, f in pairs(p.fields) do if f.mask == mask then return f end end
    return nil
end
local function btn(tag, mask, v) local f = field(tag, mask) if f then f:set_value(v) end end

_G.P9.h = emu.add_machine_frame_notifier(function()
    local t = mac.time.seconds + mac.time.attoseconds / 1e18
    local S = _G.P9

    -- navigation
    if S.phase == "wait" and t >= PRESS_AT then btn("CPL_SEG3", 0x01, 1) S.phase = "d1" S.base = t
    elseif S.phase == "d1" and t >= S.base + 0.3 then btn("CPL_SEG3", 0x01, 0) S.phase = "d2" S.base = t
    elseif S.phase == "d2" and t >= S.base + 1.5 then btn("CPL_SEG9", 0x02, 1) S.phase = "d3" S.base = t
    elseif S.phase == "d3" and t >= S.base + 0.3 then btn("CPL_SEG9", 0x02, 0) S.phase = "d4" S.base = t
    elseif S.phase == "d4" and t >= S.base + 1.5 then btn("CPL_SEG10", 0x01, 1) S.phase = "d5" S.base = t
    elseif S.phase == "d5" and t >= S.base + 0.3 then btn("CPL_SEG10", 0x01, 0) S.phase = "obs"
        log(string.format("P9 demo engaged at t=%.2f", t))
    end
    if S.phase ~= "obs" then return end

    local tr = u8(0x0420)
    -- record the FIRST departure from 'running', whatever it goes to
    if S.from_val == nil and tr == 0x04 then S.from_val = tr end
    if S.from_val ~= nil and not S.changed_at and tr ~= 0x04 then
        S.changed_at = t
        log(string.format("P9 ★ transport LEFT 0x04 at t=%.2f -> 0x%02X", t, tr))
    end

    local sec = math.floor(t)
    if sec >= FROM and sec ~= S.last then
        S.last = sec
        log(string.format("P9 t=%d transport=%02X subtick=%02X wd=%02X acc=%02X 8d38=%02X",
            sec, tr, u8(0x0417), u8(0x32ed), u8(0x22FC), u8(0x8D38)))
    end
end)

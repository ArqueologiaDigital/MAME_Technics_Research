-- kn5000_demotimer.lua -- why does no NEXT song start after the first one ends?
--
-- Per kn5000-docs/ssf-presentation.md the Feature Presentation drives itself:
--     enter state 0xE4 -> Demo_ResetCountdownTimer sets DRAM[0x0D2F] = 15
--     -> timer ticks down -> at 10: parse slide, Demo_SelectEntry_PlaySong
--     -> FDemo_MultiGuardCheck, which FAILS if state != 0xE4
--        or if DRAM[0x10420] != 0 (sequencer parts still active)
--
-- Measured 2026-08-15: the manual path plays ONE song (t=25..139.47), stops cleanly, and then
-- nothing follows for 180 s -- yet `0x8D38` stays 0xE4, so the machine is STILL inside the
-- Feature Presentation the whole time. If the timer is ticking and the guard is what blocks
-- the next song, DRAM[0x10420] will be non-zero. That is the documented failure mode:
-- sequencer parts that never finish.
--
-- Note the idle machine has no demo at all -- the timer lives INSIDE the presentation, so
-- "wait at the home screen and see if a demo starts" tests something that does not exist.
--
--   ./run.sh kn5000 -window -nothrottle -seconds_to_run 220 \
--       -cfg_directory <fresh> -nvram_directory <fresh> \
--       -autoboot_script tools/rigs/kn5000_demotimer.lua
--
-- Prints once a second from DT_FROM: the countdown, the parts mask, the state byte and the
-- transport, so "timer stopped" and "guard blocked" are distinguishable rather than lumped
-- together as "nothing happens".

local mac = manager.machine
local sp  = mac.devices[":maincpu"].spaces["program"]
local function log(s) emu.print_error(s) end
local function u8(a) local ok, v = pcall(function() return sp:read_u8(a) end) return ok and v or -1 end
local function u16(a) local ok, v = pcall(function() return sp:read_u16(a) end) return ok and v or -1 end

local FROM = tonumber(os.getenv("DT_FROM")) or 120
local PRESS_AT = tonumber(os.getenv("DT_PRESS_AT")) or 20.0

_G.DT = _G.DT or { phase = "wait", base = 0, last = -1 }

local function field(tag, mask)
    local p = mac.ioport.ports[":" .. tag] or mac.ioport.ports[":cpanel:" .. tag]
    if not p then return nil end
    for _, f in pairs(p.fields) do if f.mask == mask then return f end end
    return nil
end
local function btn(tag, mask, v) local f = field(tag, mask) if f then f:set_value(v) end end

_G.DT.h = emu.add_machine_frame_notifier(function()
    local t = mac.time.seconds + mac.time.attoseconds / 1e18
    local S = _G.DT
    if S.phase == "wait" and t >= PRESS_AT then btn("CPL_SEG3", 0x01, 1) S.phase = "d1" S.base = t
    elseif S.phase == "d1" and t >= S.base + 0.3 then btn("CPL_SEG3", 0x01, 0) S.phase = "d2" S.base = t
    elseif S.phase == "d2" and t >= S.base + 1.5 then btn("CPL_SEG9", 0x02, 1) S.phase = "d3" S.base = t
    elseif S.phase == "d3" and t >= S.base + 0.3 then btn("CPL_SEG9", 0x02, 0) S.phase = "d4" S.base = t
    elseif S.phase == "d4" and t >= S.base + 1.5 then btn("CPL_SEG10", 0x01, 1) S.phase = "d5" S.base = t
    elseif S.phase == "d5" and t >= S.base + 0.3 then btn("CPL_SEG10", 0x01, 0) S.phase = "obs"
        log(string.format("DT demo engaged at t=%.2f", t))
    end
    if S.phase ~= "obs" then return end

    local sec = math.floor(t)
    if sec >= FROM and sec ~= S.last then
        S.last = sec
        log(string.format("DT t=%3d  countdown[0x0D2F]=%3d  parts[0x10420]=0x%04X  state[0x8D38]=0x%02X  transport=0x%02X",
            sec, u8(0x0D2F), u16(0x10420), u8(0x8D38), u8(0x0420)))
    end
end)

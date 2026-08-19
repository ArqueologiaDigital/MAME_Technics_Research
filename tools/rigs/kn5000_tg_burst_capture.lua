-- kn5000_tg_burst_capture.lua -- log EVERY tone generator register write, with its voice.
-- rig-machine: kn5000
--
-- QUESTION ANSWERED: what does the sub-CPU actually send the chip for one note? Not just the eight
-- registers the HLE decodes -- ALL of them, so that the undecoded fields can be traced back to
-- whatever produced them.
--
-- Output (stdout via -log, one line per data write):
--     TGB <time> <latch:04X> <data:04X>
-- The latch encodes (group << 8) | (bank << 6) | channel, so the analysis can group a burst by
-- voice and segment it at each note-on gate (group 0, data 0x81xx).
--
--   ./tools/rig.sh kn5000_tg_burst_capture kn5000 -s 90 > /tmp/burst.log
--   (pair with the three-press demo start; this rig performs it itself)
--
-- ⚠ HIGH VOLUME: ~137k writes over 140 s of the demo. That is the point -- the correlation needs
--   every field, not a sample.

local mac = manager.machine
local function log(s) emu.print_error(s) end

local START = tonumber(os.getenv("DEMO_PRESS_AT") or "") or 40.0
local HOLD  = 0.5
local GAP   = 4.0

local function field(tag, mask)
    local p = mac.ioport.ports[":cpanel:" .. tag] or mac.ioport.ports[":" .. tag]
    if not p then return nil end
    for _, f in pairs(p.fields) do if f.mask == mask then return f end end
end

local SEQUENCE = {
    { "DEMO",   field("CPL_SEG3",  0x01) },
    { "LEFT 4", field("CPL_SEG9",  0x02) },
    { "LEFT 2", field("CPL_SEG10", 0x01) },
}

local sub = mac.devices[":subcpu"]
if sub == nil then log("TGB FATAL -- no :subcpu"); mac:exit(); return end

_G.TGB = _G.TGB or { latch = 0, i = 1, n = 0 }

_G.TGB.tap = sub.spaces["program"]:install_write_tap(0x100000, 0x100003, "tgb", function (offset, data, mask)
    local S = _G.TGB
    if offset < 0x100002 then
        S.latch = data
    else
        S.n = S.n + 1
        log(string.format("TGB %.6f %04X %04X", mac.time.seconds, S.latch, data))
    end
    return data
end)

_G.TGB.h = emu.add_machine_frame_notifier(function()
    local S = _G.TGB
    local t = mac.time.seconds
    if S.i > #SEQUENCE then return end
    local at = START + (S.i - 1) * GAP
    local name, f = SEQUENCE[S.i][1], SEQUENCE[S.i][2]
    if f == nil then log("TGB FATAL -- missing " .. name); mac:exit(); return end
    if not S.down and t >= at then
        f:set_value(1); S.down = true
        log(string.format("TGB press %s at t=%.2f", name, t))
    elseif S.down and t >= at + HOLD then
        f:set_value(0); S.down = false; S.i = S.i + 1
    end
end)

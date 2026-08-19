-- kn5000_softkey_sweep.lua -- which LCD soft key does what on the current screen?
-- rig-machine: kn5000
--
-- QUESTION ANSWERED: press each of LEFT 1..LEFT 5 in turn, and after each one report how many
-- tone-generator note-on gates appeared and take a screenshot. Used to map a menu whose soft-key
-- layout is not obvious from the driver.
--
-- WHY IT EXISTS: the DEMO button was believed to start the built-in demo. It does not -- it opens
-- a menu, and the entry has to be chosen with a soft key. Guessing the key from where the arrows
-- appear on screen was also wrong twice. This rig answers it by trying all five and MEASURING,
-- which took one run after several wasted ones.
--
--   ./tools/rig.sh kn5000_softkey_sweep kn5000 -s 95 -- -snapshot_directory /tmp/snaps
--
-- Read the gate counts, then read the screenshots: the key that starts music is the one whose
-- count jumps from zero.
--
-- ⚠ A wrong key may navigate away, after which later presses act on a different screen. Treat the
--   first key that produces gates as the answer and re-run to confirm it in isolation.

local mac = manager.machine
local function log(s) emu.print_error(s) end

-- LEFT 1..5 as declared in kn5000_cpanel.cpp
local KEYS = {
    { "LEFT1", "CPL_SEG10", 0x02 },
    { "LEFT2", "CPL_SEG10", 0x01 },
    { "LEFT3", "CPL_SEG9",  0x04 },
    { "LEFT4", "CPL_SEG9",  0x02 },
    { "LEFT5", "CPL_SEG9",  0x01 },
}
local function fld(tag, mask)
    local p = mac.ioport.ports[":cpanel:" .. tag] or mac.ioport.ports[":" .. tag]
    if not p then return nil end
    for _, f in pairs(p.fields) do if f.mask == mask then return f end end
end
local demo = fld("CPL_SEG3", 0x01)

local sub = mac.devices[":subcpu"].spaces["program"]
_G.SK = { latch = 0, gates = 0, i = 0 }
_G.SK.tap = sub:install_write_tap(0x100000, 0x100003, "sk", function(off, data, mask)
    local S = _G.SK
    if off < 0x100002 then S.latch = data
    elseif (S.latch & 0xFFC0) == 0 and (data & 0xFF00) == 0x8100 then S.gates = S.gates + 1 end
    return data
end)

_G.SK.h = emu.add_machine_frame_notifier(function()
    local S, t = _G.SK, mac.time.seconds
    if t >= 40.0 and not S.demo_dn then S.demo_dn = true; demo:set_value(1); log("SK DEMO down") end
    if t >= 40.5 and not S.demo_up then S.demo_up = true; demo:set_value(0)
        mac.video:snapshot(); log("SK menu snapshot taken") end

    -- one soft key every 8 s: press, wait, snapshot, report gates
    local base = 46.0
    for i = 1, #KEYS do
        local at = base + (i - 1) * 8.0
        local name, tag, mask = table.unpack(KEYS[i])
        if t >= at and not S["dn" .. i] then
            S["dn" .. i] = true; S["g" .. i] = S.gates
            local f = fld(tag, mask)
            if f then f:set_value(1) else log("SK " .. name .. " MISSING") end
            log(string.format("SK %s down at t=%.1f", name, t))
        end
        if t >= at + 0.5 and not S["up" .. i] then
            S["up" .. i] = true
            local f = fld(tag, mask); if f then f:set_value(0) end
        end
        if t >= at + 4.0 and not S["sn" .. i] then
            S["sn" .. i] = true
            mac.video:snapshot()
            log(string.format("SK %s -> %d new gates, snapshot", name, S.gates - S["g" .. i]))
        end
    end
end)

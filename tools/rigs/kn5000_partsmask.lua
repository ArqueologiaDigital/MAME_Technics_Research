-- kn5000_partsmask.lua -- what clears the sequencer part-active mask, and why not these four?
-- rig-machine: kn5000
--
-- Established 2026-08-15: after the Feature Presentation's song stops, DRAM[0x10420] holds
-- 0x044A -- bits 1, 3, 6, 10 -- forever, and FDemo_MultiGuardCheck therefore refuses to start
-- the next song. All tone-generator voices DO release at the stop (0x1CE0 -> 0x0000), so this
-- is bookkeeping, not audio, and it is independent of the undumped waveform ROMs.
--
-- Twelve of sixteen parts clear normally, so the clearing path works. The question is what is
-- different about the four that do not.
--
-- This taps every WRITE to the mask and reports the value, the PC, and which bits changed --
-- so "who clears bits" and "who never clears these" are both answered from one run.
--
--   ./tools/rig.sh kn5000_partsmask kn5000 -s 200
--
-- ⚠ The tap range must be word-aligned (16-bit bus): 0x10420-0x10421, not 0x10420-0x10420.
-- ⚠ The reported PC is a prefetch neighbourhood, not exactly the writing instruction --
--    disassemble before naming anything.

local mac = manager.machine
local cpu = mac.devices[":maincpu"]
local mp  = cpu.spaces["program"]
local function log(s) emu.print_error(s) end

local PRESS_AT = tonumber(os.getenv("PM_PRESS_AT")) or 20.0

_G.PM = _G.PM or { phase = "wait", base = 0, prev = nil, seen = {}, n = 0 }

local function pc()
    local ok, v = pcall(function() return cpu.state["PC"].value end)
    return ok and v or -1
end

_G.PM.tap = mp:install_write_tap(0x10420, 0x10421, "parts", function(offset, data, mask)
    local S = _G.PM
    if S.phase ~= "obs" then return nil end
    local t = mac.time.seconds + mac.time.attoseconds / 1e18
    local v = data & 0xFFFF
    local p = pc()
    S.n = S.n + 1
    local cleared = S.prev and (S.prev & ~v) or 0
    local set     = S.prev and (v & ~S.prev) or v
    local key = string.format("%04X/%08X", v, p)
    -- Report every transition that CHANGES the mask, plus the first sighting of each writer.
    if S.prev ~= v then
        log(string.format("PM t=%7.2f 0x%04X -> 0x%04X  cleared=0x%04X set=0x%04X  PC=0x%08X",
            t, S.prev or 0xFFFF, v, cleared, set, p))
    elseif not S.seen[key] then
        log(string.format("PM t=%7.2f rewrite 0x%04X (no change)  PC=0x%08X   (first time)", t, v, p))
    end
    S.seen[key] = true
    S.prev = v
    return nil
end)

local function field(tag, mask)
    local p = mac.ioport.ports[":" .. tag] or mac.ioport.ports[":cpanel:" .. tag]
    if not p then return nil end
    for _, f in pairs(p.fields) do if f.mask == mask then return f end end
    return nil
end
local function btn(tag, mask, v) local f = field(tag, mask) if f then f:set_value(v) end end

_G.PM.h = emu.add_machine_frame_notifier(function()
    local t = mac.time.seconds + mac.time.attoseconds / 1e18
    local S = _G.PM
    if S.phase == "wait" and t >= PRESS_AT then btn("CPL_SEG3", 0x01, 1) S.phase = "d1" S.base = t
    elseif S.phase == "d1" and t >= S.base + 0.3 then btn("CPL_SEG3", 0x01, 0) S.phase = "d2" S.base = t
    elseif S.phase == "d2" and t >= S.base + 1.5 then btn("CPL_SEG9", 0x02, 1) S.phase = "d3" S.base = t
    elseif S.phase == "d3" and t >= S.base + 0.3 then btn("CPL_SEG9", 0x02, 0) S.phase = "d4" S.base = t
    elseif S.phase == "d4" and t >= S.base + 1.5 then btn("CPL_SEG10", 0x01, 1) S.phase = "d5" S.base = t
    elseif S.phase == "d5" and t >= S.base + 0.3 then btn("CPL_SEG10", 0x01, 0) S.phase = "obs"
        log(string.format("PM demo engaged at t=%.2f -- watching 0x10420", t))
    end
end)
